# backend/agent.py  [REFACTOR v5 — Exponential Cooldown + Introvert/Extrovert + Deep Work]
"""
Изменения v5:
1. EXPONENTIAL COOLDOWN: recent_conversations_count передаётся в DesireGenerator
   через mark_conversation_ended с personality-контекстом.
2. INTROVERT/EXTROVERT BATTERY:
   - Интроверты (extraversion < 0.4): стандартный drain × 1.5 (дополнительно к двойному кулдауну)
   - Экстраверты (extraversion > 0.6): drain × 0.7 (медленнее тратят батарейку)
3. DEEP WORK STATE:
   - to_dict() экспортирует deep_work_active и deep_work_reason для frontend.
   - notify_conversation_ended передаёт personality в deliberation для динамического кулдауна.
4. EVENT BROADCAST helpers:
   - broadcast_world_event() — создаёт восприятие типа world_event с type="EVENT" для frontend.
   - get_event_interrupt_info() — делегирует к deliberation.consume_event_interrupt().
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from core.bdi import (
    BeliefBase, Desire, Intention, DeliberationCycle,
    create_self_belief, BeliefType, PlanStep, ActionType, IntentionStatus, DesireStatus
)


class Personality(BaseModel):
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float


class Emotion(BaseModel):
    """
    Начальное состояние — киберпанк/нуар-атмосфера:
    агенты умеренно подавлены, злы, счастье минимально.
    """
    happiness: float = 0.1
    sadness: float = 0.6
    anger: float = 0.4
    fear: float = 0.2
    surprise: float = 0.1
    disgust: float = 0.2
    # Дополнительные эмоциональные оси
    loneliness: float = 0.5   # Одиночество (высокое в начале)
    comfort: float = 0.2       # Комфорт (низкий в начале)


# ── Матрица эмоционального влияния (триггер → дельты) ──────────────────
# Формат: {trigger_type: {emotion_key: delta}}
EMOTION_IMPACT_MATRIX: Dict[str, Dict[str, float]] = {
    # Погода / физическая среда
    "rain":        {"sadness": +0.1, "comfort": -0.2},
    "cold":        {"sadness": +0.1, "comfort": -0.15},
    "heat":        {"anger": +0.1, "comfort": -0.1},
    "storm":       {"fear": +0.15, "comfort": -0.25},
    "sunny":       {"happiness": +0.1, "sadness": -0.05},
    # Угрозы / опасности
    "fire":        {"fear": +0.3, "surprise": +0.2, "anger": +0.1},
    "threat":      {"fear": +0.3, "anger": +0.2},
    "alarm":       {"fear": +0.25, "surprise": +0.3},
    "explosion":   {"fear": +0.4, "surprise": +0.35, "anger": +0.15},
    # Позитивные события
    "gift":        {"happiness": +0.2, "sadness": -0.1, "loneliness": -0.15},
    "praise":      {"happiness": +0.2, "sadness": -0.1, "anger": -0.05},
    "reward":      {"happiness": +0.25, "sadness": -0.15},
    # Социальные негативные
    "insult":      {"anger": +0.2, "sadness": +0.1},
    "conflict":    {"anger": +0.25, "fear": +0.1},
    "rejection":   {"sadness": +0.2, "anger": +0.1, "loneliness": +0.15},
    # Социальные позитивные
    "friendly_chat":     {"happiness": +0.05, "loneliness": -0.1},
    "long_pleasant_chat": {"happiness": +0.1, "loneliness": -0.2, "sadness": -0.05},
    # Общие события
    "world_event": {"surprise": +0.1, "fear": +0.05},
    "announcement": {"surprise": +0.05},
}


class Agent:
    def __init__(self, agent_id: str, name: str, avatar: str,
                 personality_data: Dict, llm_interface=None):
        self.id = agent_id
        self.name = name
        self.avatar = avatar
        self.personality = Personality(**personality_data)
        self.emotions = Emotion()
        self.beliefs = BeliefBase()
        self.desires: List[Desire] = []
        self.intentions: List[Intention] = []
        self.deliberation_cycle = DeliberationCycle(llm_interface=llm_interface)
        self._initialize_self_beliefs()
        self.current_plan = "Ожидание..."

        # ── Social Battery ──────────────────────────────────────────────
        # Заряд от 0.0 (опустошён) до 1.0 (полный).
        # Расходуется при отправке каждого сообщения.
        # Восстанавливается при несоциальных (solo) действиях.
        self.social_battery: float = 1.0

        # ── Счётчик недавних разговоров (для экспоненциального кулдауна) ──
        # Читается из DesireGenerator (синхронизируется автоматически)
        # Публичное свойство для мониторинга и тестов.

    def _initialize_self_beliefs(self):
        self.beliefs.add_belief(create_self_belief(self.id, "name", self.name))
        self.beliefs.add_belief(create_self_belief(self.id, "location", "Центральная площадь"))

    # ── Social Battery helpers ──────────────────────────────────────────

    def _drain_social_battery(self):
        """
        Уменьшает заряд после отправки сообщения.

        Personality-based модификаторы:
          - Интроверт (extraversion < 0.4): drain × 1.5
          - Экстраверт (extraversion > 0.6): drain × 0.7
          - Нейротики (neuroticism > 0.6): drain × 1.2 (тревожность = доп. усталость)

        Базовая формула: cost = (1.1 - extraversion) * 0.15
        """
        extraversion = self.personality.extraversion
        neuroticism = self.personality.neuroticism

        # Базовый расход
        cost = (1.1 - extraversion) * 0.15

        # Интроверт-штраф
        if extraversion < 0.4:
            cost *= 1.5
            modifier_tag = "introvert ×1.5"
        # Экстраверт-бонус
        elif extraversion > 0.6:
            cost *= 0.7
            modifier_tag = "extrovert ×0.7"
        else:
            modifier_tag = "neutral"

        # Нейротик-штраф (тревожность увеличивает социальную усталость)
        if neuroticism > 0.6:
            cost *= 1.2
            modifier_tag += " + neurotic ×1.2"

        self.social_battery = max(0.0, self.social_battery - cost)
        print(f"🔋 [{self.id}] Battery drain: -{cost:.3f} → {self.social_battery:.2f} ({modifier_tag})")

    def _restore_social_battery(self, amount: float = 0.05):
        """
        Восстанавливает заряд после несоциального (solo) действия.
        Экстраверты восстанавливаются быстрее (×1.2) — им одиночество менее ценно,
        но и социальная усталость у них меньше.
        Интроверты восстанавливаются стандартно.
        """
        extraversion = self.personality.extraversion

        # Экстраверты восстанавливаются чуть быстрее от любых действий
        if extraversion > 0.6:
            amount *= 1.2

        old = self.social_battery
        self.social_battery = min(1.0, self.social_battery + amount)
        if self.social_battery > old:
            print(f"🔋 [{self.id}] Battery restore: +{amount:.3f} → {self.social_battery:.2f}")

    # ── Recent conversations count (read-only property) ──────────────────

    @property
    def recent_conversations_count(self) -> int:
        """
        Количество завершённых разговоров в последнем скользящем окне (5 мин).
        Используется для exponential cooldown формулы:
            cooldown = base_cooldown * (1 + recent_conversations_count)
        """
        dg = self.deliberation_cycle.desire_generator
        dg._update_recent_conv_window()
        return dg.recent_conversations_count

    # ── Core BDI loop ───────────────────────────────────────────────────

    def think(
        self,
        perceptions: List[Dict[str, Any]],
        active_conversation_partners: List[str] = None
    ) -> List[Dict]:
        result = self.deliberation_cycle.run_cycle(
            agent_id=self.id,
            beliefs=self.beliefs,
            desires=self.desires,
            intentions=self.intentions,
            personality=self.personality.dict(),
            emotions=self.emotions.dict(),
            perceptions=perceptions,
            max_intentions=1,
            active_conversation_partners=active_conversation_partners or [],
            social_battery=self.social_battery
        )

        if result.get('new_intention'):
            self.current_plan = result['new_intention'].desire_description
        elif not any(i.status == IntentionStatus.ACTIVE for i in self.intentions):
            self.current_plan = "Обдумывание..."

        actions_to_perform = []
        for action_info in result['actions_to_execute']:
            action: PlanStep = action_info['action']
            actions_to_perform.append({
                "agent_id": self.id,
                "action_type": action.action_type.value,
                "params": action.parameters,
                "intention_id": action_info['intention_id'],
                "step_object": action
            })
        return actions_to_perform

    def confirm_action_execution(self, intention_id: str, step_object: PlanStep,
                                 success: bool, message: str):
        step_object.executed = True
        step_object.success = success

        SOCIAL_SOURCES = {
            'incoming_message', 'personality_extraversion', 'personality_agreeableness',
            'emotion_happiness', 'emotion_sadness', 'user_message'
        }

        # Расход батарейки при каждой отправке сообщения
        # GOD MODE: если message идёт к/от user — батарейка не расходуется
        bypass_battery = False
        for desire in self.desires:
            if desire.id == next((i.desire_id for i in self.intentions
                                   if i.id == intention_id), None):
                bypass_battery = desire.context.get('bypass_battery', False)
                break

        if (step_object.action_type in (ActionType.SEND_MESSAGE, ActionType.RESPOND_TO_MESSAGE)
                and not bypass_battery):
            self._drain_social_battery()

        for intention in self.intentions:
            if intention.id == intention_id:
                intention.update_progress({"success": success, "message": message})

                if intention.is_completed():
                    intention.complete()

                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.status = DesireStatus.ACHIEVED

                            if desire.source not in SOCIAL_SOURCES:
                                self.deliberation_cycle.notify_solo_action(
                                    desire.source or 'idle_drive'
                                )
                            break
                break

    def notify_conversation_ended(self, partner_id: str):
        """
        Уведомить BDI о завершении разговора с partner_id.
        Активирует экспоненциальный кулдаун в DesireGenerator.
        Передаёт personality для корректного расчёта introvert/extrovert cooldown.
        """
        self.deliberation_cycle.notify_conversation_ended(
            partner_id, personality=self.personality.dict()
        )
        print(f"📊 [{self.id}] Разговор с {partner_id} завершён. "
              f"Recent convs: {self.recent_conversations_count}")

    def notify_solo_action(self, action_type: str):
        """
        Social Satiety: уведомить BDI что выполнено несоциальное действие.
        После MIN_SOLO_ACTIONS действий снимает блок на новые социальные желания.
        Дополнительно восстанавливает social_battery.
        """
        self.deliberation_cycle.notify_solo_action(action_type)
        self._restore_social_battery(0.05)

    # ── Event Broadcast helpers ───────────────────────────────────────────

    @staticmethod
    def create_world_event_perception(
        event_id: str,
        description: str,
        event_type: str = "general",
        severity: str = "normal"
    ) -> Dict[str, Any]:
        """
        Фабричный метод для создания perception мирового события.
        Используется симулятором/CommunicationHub для broadcast.

        Args:
            event_id: Уникальный идентификатор события
            description: Описание события для агентов
            event_type: Тип события ('weather', 'fire', 'announcement', 'alarm', ...)
            severity: Серьёзность ('low', 'normal', 'high', 'critical')

        Returns:
            Словарь восприятия типа 'world_event' с frontend-маркерами.
        """
        from datetime import datetime
        return {
            'type': 'world_event',          # ← тип для BDI
            'frontend_type': 'EVENT',       # ← тип для frontend (highlight)
            'subject': 'world',
            'data': {
                'event_id': event_id,
                'description': description,
                'event_type': event_type,
                'severity': severity,
                'display_label': f"⚠️ {description}",   # ← готовая метка для UI
                'interrupt_social': True,                # ← сигнал прервать чат
            },
            'confidence': 1.0,
            'importance': 1.0,              # ← максимальная важность
            'timestamp': datetime.now().isoformat(),
            'is_broadcast': True,           # ← флаг для simulator broadcast
        }

    # ── Emotion Engine ────────────────────────────────────────────────

    def process_emotional_impact(self, trigger_type: str, content: str = "", intensity: float = 1.0):
        """
        Обрабатывает эмоциональное влияние события или диалога.

        Args:
            trigger_type: Ключ из EMOTION_IMPACT_MATRIX или произвольный тип
                          (автоматически матчится по ключевым словам контента)
            content: Текст события/сообщения для семантического матчинга
            intensity: Коэффициент усиления/ослабления (0.0–2.0)
        """
        # Сначала попробуем точное совпадение
        impacts = EMOTION_IMPACT_MATRIX.get(trigger_type.lower(), {})

        # Если не найдено — матчим по ключевым словам в контенте
        if not impacts and content:
            lower_content = content.lower()
            keyword_map = {
                "дождь": "rain", "ливень": "rain",
                "холод": "cold", "мороз": "cold",
                "жара": "heat", "пожар": "fire", "горит": "fire",
                "угроза": "threat", "опасность": "threat",
                "взрыв": "explosion", "тревога": "alarm",
                "шторм": "storm", "гроза": "storm",
                "подарок": "gift", "похвала": "praise", "награда": "reward",
                "оскорбление": "insult", "конфликт": "conflict",
                "отказ": "rejection",
                "sunny": "sunny", "солнечно": "sunny",
            }
            for keyword, mapped_type in keyword_map.items():
                if keyword in lower_content:
                    impacts = EMOTION_IMPACT_MATRIX.get(mapped_type, {})
                    if impacts:
                        trigger_type = mapped_type
                        break

        # Нейротизм усиливает негативные эмоции
        neuroticism_mult = 1.0 + (self.personality.neuroticism - 0.5) * 0.4

        for emotion_key, delta in impacts.items():
            current = getattr(self.emotions, emotion_key, None)
            if current is None:
                continue
            # Усиливаем негативные дельты для невротиков
            effective_delta = delta * intensity
            if delta > 0 and emotion_key in ('fear', 'anger', 'sadness'):
                effective_delta *= neuroticism_mult
            new_val = max(0.0, min(1.0, current + effective_delta))
            setattr(self.emotions, emotion_key, round(new_val, 3))

        if impacts:
            print(f"😤 [{self.id}] Emotion impact [{trigger_type}×{intensity:.1f}]: "
                  f"h={self.emotions.happiness:.2f} sad={self.emotions.sadness:.2f} "
                  f"ang={self.emotions.anger:.2f} fear={self.emotions.fear:.2f}")

    def update_emotions_from_dialogue(self, affinity: float, is_conflict: bool = False):
        """
        Обновить эмоции после диалога.
        - affinity > 0.5 → приятный диалог → больше счастья, меньше одиночества
        - is_conflict → конфликтный диалог → больше злости
        """
        if is_conflict:
            self.process_emotional_impact("conflict", intensity=0.8)
        elif affinity > 0.5:
            trigger = "long_pleasant_chat" if affinity > 0.7 else "friendly_chat"
            self.process_emotional_impact(trigger, intensity=affinity)

    def get_event_interrupt_info(self) -> Optional[Dict[str, Any]]:
        """
        Возвращает данные о последнем event-прерывании и сбрасывает флаг.
        Симулятор вызывает после run_cycle для отправки на frontend.
        """
        return self.deliberation_cycle.consume_event_interrupt()

    def is_in_deep_work(self) -> bool:
        """Возвращает True если агент в состоянии Deep Work / Solitude."""
        return self.deliberation_cycle.desire_generator._deep_work_active

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self):
        loc_belief = self.beliefs.get_belief(BeliefType.SELF, self.id, "location")
        current_location = loc_belief.value if loc_belief else "Неизвестно"

        dg = self.deliberation_cycle.desire_generator

        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar,
            "personality": self.personality.dict(),
            "emotions": self.emotions.dict(),
            "current_plan": self.current_plan,
            "location": current_location,
            "status": "active",
            "memory_count": len(self.beliefs.beliefs),
            "relationships": {},
            "memories": [],
            "social_battery": round(self.social_battery, 3),

            # ── v5 New fields ──────────────────────────────────────────
            "recent_conversations_count": self.recent_conversations_count,
            "deep_work_active": dg._deep_work_active,
            "deep_work_reason": dg._deep_work_reason,
            "current_cooldown_seconds": round(
                dg.get_dynamic_post_conv_cooldown(self.personality.dict()), 1
            ),
        }