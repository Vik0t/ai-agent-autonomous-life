"""
desires.py  [v5 — LLM-генератор желаний]

Ключевые изменения v5:
1. УДАЛЕНЫ: self.rules, _initialize_rules — правила с lambda-условиями.
2. generate_desires теперь использует llm.generate_dynamic_desires для создания
   желаний на основе личности, эмоций, social_battery и восприятий.
3. Если social_battery < 0.2 — LLM принудительно получает инструкцию
   игнорировать SOCIAL мотивы (SAFETY/CURIOSITY вместо них).
4. Сохранены: реактивные respond_desires, cooldown-система, idle_drive,
   все вспомогательные методы.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import time
import random

# Типы сообщений, на которые НИКОГДА не отвечаем новым desire
_NO_RESPOND_MESSAGE_TYPES = {"farewell", "ack"}

# ID пользователя (God Mode) — жёстко зашит
USER_ID = "user"

# ══════════════════════════════════════════════════════════════════════
# Иерархия приоритетов желаний (чем выше — тем важнее):
#   Tier 5 (1.00) — world_event, user_message       → ABSOLUTE
#   Tier 4 (0.90) — incoming_message, wrap_up       → HIGH
#   Tier 3 (0.65) — LLM social (инициатор разговора) → MEDIUM-HIGH
#   Tier 2 (0.40) — LLM non-social (любопытство…)   → MEDIUM
#   Tier 1 (0.10) — idle_drive                       → LOW (фоновый)
# ══════════════════════════════════════════════════════════════════════
PRIORITY_WORLD_EVENT    = 1.00
PRIORITY_USER_MESSAGE   = 1.00
PRIORITY_INCOMING       = 0.90
PRIORITY_LLM_SOCIAL     = 0.65   # LLM-желание поговорить
PRIORITY_LLM_NONSOCIAL  = 0.40   # LLM-желание не-социальное
PRIORITY_IDLE           = 0.10   # Idle drive — самый низкий


class DesireStatus(Enum):
    ACTIVE = "active"
    PURSUED = "pursued"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"
    IMPOSSIBLE = "impossible"


class MotivationType(Enum):
    SURVIVAL = "survival"
    SAFETY = "safety"
    SOCIAL = "social"
    ESTEEM = "esteem"
    ACHIEVEMENT = "achievement"
    CURIOSITY = "curiosity"
    WORLD_EVENT = "world_event"   # ← мировые события: максимальный приоритет


@dataclass
class Desire:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    priority: float = 0.5
    urgency: float = 0.5
    status: DesireStatus = DesireStatus.ACTIVE
    motivation_type: MotivationType = MotivationType.SOCIAL
    source: str = "personality"
    preconditions: List[str] = field(default_factory=list)
    success_conditions: List[str] = field(default_factory=list)
    personality_alignment: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def calculate_utility(self) -> float:
        return self.priority * self.urgency * self.personality_alignment

    def is_achievable(self, beliefs_query_func) -> bool:
        if not self.preconditions:
            return True
        for pre in self.preconditions:
            if not beliefs_query_func(pre):
                return False
        return True

    def is_expired(self) -> bool:
        return self.deadline is not None and datetime.now() > self.deadline

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'description': self.description,
            'priority': self.priority, 'urgency': self.urgency,
            'status': self.status.value, 'motivation_type': self.motivation_type.value,
            'source': self.source, 'preconditions': self.preconditions,
            'success_conditions': self.success_conditions,
            'personality_alignment': self.personality_alignment,
            'created_at': self.created_at.isoformat(),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'context': self.context
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Desire':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            description=data['description'],
            priority=data.get('priority', 0.5), urgency=data.get('urgency', 0.5),
            status=DesireStatus(data.get('status', 'active')),
            motivation_type=MotivationType(data.get('motivation_type', 'social')),
            source=data.get('source', 'personality'),
            preconditions=data.get('preconditions', []),
            success_conditions=data.get('success_conditions', []),
            personality_alignment=data.get('personality_alignment', 0.5),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            deadline=datetime.fromisoformat(data['deadline']) if data.get('deadline') else None,
            context=data.get('context', {})
        )

    def __repr__(self):
        return f"Desire({self.description[:30]}, util={self.calculate_utility():.2f}, {self.status.value})"


# Маппинг строковых motivation_type → MotivationType enum
_MOTIVATION_MAP = {
    'survival': MotivationType.SURVIVAL,
    'safety': MotivationType.SAFETY,
    'social': MotivationType.SOCIAL,
    'esteem': MotivationType.ESTEEM,
    'achievement': MotivationType.ACHIEVEMENT,
    'curiosity': MotivationType.CURIOSITY,
    'world_event': MotivationType.WORLD_EVENT,
}


class DesireGenerator:

    def __init__(self, llm_interface=None):
        # ── LLM-интерфейс ────────────────────────────────────────────
        self.llm = llm_interface

        # ── Cooldown для LLM-генерации (не вызываем каждый тик) ──────
        self._llm_last_called: float = 0.0
        self.llm_cooldown_seconds: float = 60.0   # раз в минуту

        # ── Cooldown на конкретного партнёра (после разговора) ───────
        self._conversation_ended_at: Dict[str, float] = {}
        self.base_post_conversation_cooldown = 120.0  # базовый кулдаун
        # Обратная совместимость: атрибут post_conversation_cooldown
        # теперь динамический — используй get_dynamic_post_conv_cooldown()
        self.post_conversation_cooldown = 120.0

        # ── Экспоненциальный кулдаун ──────────────────────────────────
        # recent_conversations_count растёт с каждым завершённым разговором
        # и уменьшается по скользящему окну в 5 минут.
        # Formula: cooldown = base * (1 + recent_conversations_count)
        self.recent_conversations_count: int = 0
        self._recent_conv_window_seconds: float = 300.0
        self._recent_conv_timestamps: List[float] = []

        # ── Глобальный социальный блок ────────────────────────────────
        self._last_conversation_ended_at: float = 0.0
        self.base_global_social_cooldown = 90.0
        self.global_social_cooldown = 90.0  # обратная совместимость

        # ── Тиковый счётчик ──────────────────────────────────────────
        self._ticks_since_conversation_ended: int = 999
        self.min_rest_ticks: int = 8

        # ── Social Satiety (несоциальные действия после разговора) ───
        self._solo_actions_after_conversation: int = 999
        self.MIN_SOLO_ACTIONS: int = 4

        # ── Deep Work State ──────────────────────────────────────────
        self._deep_work_active: bool = False
        self._deep_work_reason: str = ""

    # ── Экспоненциальный кулдаун helpers ─────────────────────────────

    def _update_recent_conv_window(self):
        """Убирает из окна разговоры старше recent_conv_window_seconds."""
        cutoff = time.time() - self._recent_conv_window_seconds
        self._recent_conv_timestamps = [t for t in self._recent_conv_timestamps if t > cutoff]
        self.recent_conversations_count = len(self._recent_conv_timestamps)

    def get_dynamic_post_conv_cooldown(self, personality: Dict[str, float] = None) -> float:
        """
        cooldown = base_cooldown * (1 + recent_conversations_count)
        Интроверты (extraversion < 0.4) получают двойной базовый кулдаун.
        """
        self._update_recent_conv_window()
        extraversion = (personality or {}).get('extraversion', 0.5)
        base = self.base_post_conversation_cooldown
        if extraversion < 0.4:
            base *= 2.0
        return base * (1 + self.recent_conversations_count)

    def get_dynamic_global_cooldown(self, personality: Dict[str, float] = None) -> float:
        """Динамический глобальный кулдаун с учётом личности."""
        self._update_recent_conv_window()
        extraversion = (personality or {}).get('extraversion', 0.5)
        base = self.base_global_social_cooldown
        if extraversion < 0.4:
            base *= 2.0
        return base * (1 + self.recent_conversations_count)

    # ── Cooldown/block API ────────────────────────────────────────────

    def mark_conversation_ended(self, partner_id: str, personality: Dict[str, float] = None):
        now = time.time()
        self._conversation_ended_at[partner_id] = now
        self._last_conversation_ended_at = now
        self._ticks_since_conversation_ended = 0
        self._solo_actions_after_conversation = 0
        # Экспоненциальный учёт
        self._recent_conv_timestamps.append(now)
        self._update_recent_conv_window()
        print(f"📊 Recent conversations in window: {self.recent_conversations_count}")

    def mark_solo_action(self, action_type: str):
        SOCIAL_ACTION_TYPES = {
            'initiate_conversation', 'send_message', 'respond_to_message',
            'wait_for_response', 'end_conversation'
        }
        if action_type not in SOCIAL_ACTION_TYPES:
            self._solo_actions_after_conversation += 1

    def tick(self):
        self._ticks_since_conversation_ended += 1

    def is_on_cooldown(self, partner_id: str, personality: Dict[str, float] = None) -> bool:
        last = self._conversation_ended_at.get(partner_id, 0)
        return (time.time() - last) < self.get_dynamic_post_conv_cooldown(personality)

    def is_globally_social_blocked(self, personality: Dict[str, float] = None) -> bool:
        dynamic_cd = self.get_dynamic_global_cooldown(personality)
        time_ok = (time.time() - self._last_conversation_ended_at) >= dynamic_cd
        ticks_ok = self._ticks_since_conversation_ended >= self.min_rest_ticks
        solo_ok = self._solo_actions_after_conversation >= self.MIN_SOLO_ACTIONS
        return not (time_ok and ticks_ok and solo_ok)

    def get_social_block_reason(self, personality: Dict[str, float] = None) -> str:
        dynamic_cd = self.get_dynamic_global_cooldown(personality)
        reasons = []
        time_left = dynamic_cd - (time.time() - self._last_conversation_ended_at)
        if time_left > 0:
            reasons.append(f"время: ещё {time_left:.0f}с")
        ticks_left = self.min_rest_ticks - self._ticks_since_conversation_ended
        if ticks_left > 0:
            reasons.append(f"тики: ещё {ticks_left}")
        solo_left = self.MIN_SOLO_ACTIONS - self._solo_actions_after_conversation
        if solo_left > 0:
            reasons.append(f"solo-действий: ещё {solo_left}")
        return " | ".join(reasons) if reasons else "разблокирован"

    # ── Deep Work State ───────────────────────────────────────────────

    def evaluate_deep_work_state(self, social_battery: float,
                                 personality: Dict[str, float]) -> bool:
        """
        Возвращает True если агент должен войти в Deep Work / Solitude.
        Триггеры: battery < 0.25 ИЛИ (conscientiousness > 0.75 AND battery < 0.5).
        """
        conscientiousness = personality.get('conscientiousness', 0.5)
        if social_battery < 0.25:
            self._deep_work_active = True
            self._deep_work_reason = f"low battery ({social_battery:.2f})"
            return True
        if conscientiousness > 0.75 and social_battery < 0.5:
            self._deep_work_active = True
            self._deep_work_reason = f"high conscient. + mid battery"
            return True
        if self._deep_work_active and social_battery >= 0.5:
            self._deep_work_active = False
            self._deep_work_reason = ""
            print(f"🟢 Deep Work state lifted (battery={social_battery:.2f})")
        return self._deep_work_active

    @staticmethod
    def is_talking_to_user(active_partners: List[str]) -> bool:
        return USER_ID in (active_partners or [])

    # ── Главный метод: generate_desires ──────────────────────────────

    def generate_desires(
        self,
        personality: Dict[str, float],
        emotions: Dict[str, float],
        beliefs_base,
        current_desires: List[Desire],
        agent_id: str = "",
        agent_name: str = "",
        perceptions: List[Dict] = None,
        active_conversation_partners: List[str] = None,
        social_battery: float = 1.0
    ) -> List[Desire]:
        new_desires = []
        current_time = time.time()
        active_partners = set(active_conversation_partners or [])

        # ── Deep Work и Conversation Lock ─────────────────────────────
        in_deep_work = self.evaluate_deep_work_state(social_battery, personality)
        talking_to_user = self.is_talking_to_user(list(active_partners))
        if in_deep_work:
            print(f"🧘 [{agent_id}] DEEP_WORK: {self._deep_work_reason}")
        if talking_to_user:
            print(f"🔒 [{agent_id}] Conversation Lock: диалог с User активен")

        # ════════════════════════════════════════════════════════════
        # 1. Реактивные желания (rule-based, срочные)
        # ════════════════════════════════════════════════════════════
        if perceptions:
            for perception in perceptions:
                p_type = perception.get('type')

                # ── Tier 5: Мировые события ──────────────────────────
                if p_type == 'world_event':
                    event_desc = perception.get('data', {}).get('description', '')
                    event_id   = perception.get('data', {}).get('event_id', '')
                    if not event_desc:
                        continue
                    already = any(
                        d.context.get('event_id') == event_id
                        and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED,
                                         DesireStatus.ACHIEVED]
                        for d in current_desires + new_desires
                    )
                    if already:
                        continue
                    reaction = Desire(
                        description=f'⚠️ Осмыслить событие: {event_desc[:60]}',
                        motivation_type=MotivationType.WORLD_EVENT,
                        priority=PRIORITY_WORLD_EVENT,
                        urgency=1.0,
                        source='world_event',
                        personality_alignment=1.0,
                        status=DesireStatus.ACTIVE,
                        context={
                            'action': 'react_to_event',
                            'topic': event_desc,
                            'event_id': event_id,
                            'is_event_reaction': True,
                            'interrupt_social': True,
                        }
                    )
                    new_desires.append(reaction)
                    print(f"🌍 [{agent_id}] ⚠️ WORLD EVENT (priority=1.0): «{event_desc[:50]}»")
                    continue

                if p_type != 'communication':
                    continue

                sender_id = perception.get('subject', '')
                data = perception.get('data', {})
                msg_type = data.get('message_type', 'statement')
                content = data.get('content', '')
                msg_id = data.get('message_id', '')
                topic = data.get('topic') or 'general'

                if not sender_id or sender_id == agent_id:
                    continue
                if msg_type in _NO_RESPOND_MESSAGE_TYPES:
                    print(f"🔇 [{agent_id}] Игнорируем {msg_type} от {sender_id}")
                    continue

                # ── Tier 5: User (God Mode) — обходит ВСЕ проверки ──
                if sender_id == USER_ID:
                    already_user = any(
                        d.context.get('target_agent') == USER_ID
                        and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                        for d in current_desires + new_desires
                    )
                    if not already_user:
                        new_desires.append(Desire(
                            description='Ответить Пользователю',
                            motivation_type=MotivationType.SOCIAL,
                            priority=PRIORITY_USER_MESSAGE,
                            urgency=1.0,
                            source='user_message',
                            personality_alignment=1.0,
                            context={
                                'target_agent': USER_ID,
                                'topic': topic,
                                'in_reply_to_msg': msg_id,
                                'incoming_content': content,
                                'intent': 'respond',
                                'is_user_message': True,
                                'bypass_battery': True,
                            }
                        ))
                        print(f"👑 [{agent_id}] GOD MODE: desire для User (priority=1.0)")
                    continue

                # ── Deep Work: отклоняем обычные чаты ────────────────
                if in_deep_work:
                    already_busy = any(
                        d.context.get('target_agent') == sender_id
                        and d.source == 'deep_work_reject'
                        and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                        for d in current_desires + new_desires
                    )
                    if not already_busy:
                        new_desires.append(Desire(
                            description=f'Сообщить {sender_id} что занят',
                            motivation_type=MotivationType.SAFETY,
                            priority=0.6, urgency=0.5,
                            source='deep_work_reject',
                            personality_alignment=0.8,
                            status=DesireStatus.ACTIVE,
                            context={
                                'target_agent': sender_id,
                                'intent': 'busy_signal',
                                'message_type': 'statement',
                                'busy_message': "Я сейчас глубоко сосредоточен, не могу отвлечься.",
                                'topic': 'busy',
                            }
                        ))
                    continue

                # ── Conversation Lock: занят User ─────────────────────
                if talking_to_user:
                    print(f"🔒 [{agent_id}] Conv. Lock: игнорируем {sender_id}")
                    continue

                # ── Tier 4: Стандартный ответ агенту ─────────────────
                if self.is_on_cooldown(sender_id, personality):
                    print(f"⏸️ [{agent_id}] Кулдаун с {sender_id} — skip")
                    continue
                if sender_id not in active_partners:
                    print(f"🚫 [{agent_id}] Не в диалоге с {sender_id} — skip")
                    continue

                has_initiator = any(
                    d.context.get('target_agent') == sender_id
                    and d.source != 'incoming_message'
                    and d.status == DesireStatus.PURSUED
                    for d in current_desires
                )
                if has_initiator:
                    continue

                already = any(
                    d.context.get('target_agent') == sender_id
                    and d.source == 'incoming_message'
                    and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                    for d in current_desires
                )
                if already:
                    continue

                new_desires.append(Desire(
                    description=f'Ответить {sender_id}',
                    motivation_type=MotivationType.SOCIAL,
                    priority=PRIORITY_INCOMING,
                    urgency=0.9,
                    source='incoming_message',
                    personality_alignment=personality.get('agreeableness', 0.7),
                    context={
                        'target_agent': sender_id,
                        'topic': topic,
                        'in_reply_to_msg': msg_id,
                        'incoming_content': content,
                        'intent': 'respond'
                    }
                ))
                print(f"💡 [{agent_id}] Respond desire → {sender_id} (priority={PRIORITY_INCOMING})")

        # ════════════════════════════════════════════════════════════
        # 2. Тиковый счётчик
        # ════════════════════════════════════════════════════════════
        self.tick()

        globally_blocked = self.is_globally_social_blocked(personality)
        if globally_blocked:
            print(f"🛑 [{agent_id}] Соц. блок — {self.get_social_block_reason(personality)}")

        # ════════════════════════════════════════════════════════════
        # 3. LLM-генерация желаний личности
        #    Tier 3 (social) и Tier 2 (non-social) по calculate_utility()
        # ════════════════════════════════════════════════════════════
        has_active_nonsocial = any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.motivation_type not in (MotivationType.SOCIAL, MotivationType.WORLD_EVENT)
            for d in current_desires
        )
        llm_blocked = talking_to_user or in_deep_work

        should_call_llm = (
            self.llm is not None
            and not has_active_nonsocial
            and not llm_blocked
            and (current_time - self._llm_last_called) >= self.llm_cooldown_seconds
        )

        if should_call_llm:
            try:
                llm_raw = self.llm.generate_dynamic_desires(
                    agent_name=agent_name or agent_id,
                    agent_id=agent_id,
                    personality=personality,
                    emotions=emotions,
                    social_battery=social_battery,
                    perceptions=perceptions or []
                )
                self._llm_last_called = current_time

                for item in (llm_raw or []):
                    desc = item.get('description', '').strip()
                    if not desc:
                        continue

                    already_exists = any(
                        d.description.lower() == desc.lower()
                        and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                        for d in current_desires + new_desires
                    )
                    if already_exists:
                        continue

                    raw_mtype = item.get('motivation_type', 'curiosity').lower()
                    mtype = _MOTIVATION_MAP.get(raw_mtype, MotivationType.CURIOSITY)

                    if mtype == MotivationType.SOCIAL and globally_blocked:
                        print(f"🛑 [{agent_id}] LLM social заблокировано: {desc[:30]}")
                        continue
                    if mtype == MotivationType.SOCIAL and social_battery < 0.2:
                        print(f"🔋 [{agent_id}] Battery low → SOCIAL→SAFETY: {desc[:30]}")
                        mtype = MotivationType.SAFETY
                    if mtype == MotivationType.SOCIAL and talking_to_user:
                        print(f"🔒 [{agent_id}] Conv. Lock: LLM SOCIAL заблокировано")
                        continue

                    ctx = dict(item.get('context', {}) or {})

                    # ── Tier 3: LLM хочет поговорить ─────────────────
                    if mtype == MotivationType.SOCIAL:
                        target = self._find_available_agent(beliefs_base, agent_id)
                        if target:
                            ctx['target_agent'] = target
                            ctx['topic'] = ctx.get('topic') or self._pick_topic(personality)
                            ctx['intent'] = 'chat'
                        if not ctx.get('target_agent'):
                            continue
                        if self.is_on_cooldown(ctx['target_agent'], personality):
                            continue
                        # Tier 3: высокий приоритет для социальных LLM-желаний
                        desire_priority = PRIORITY_LLM_SOCIAL
                        desire_urgency  = 0.7
                    else:
                        # Tier 2: средний приоритет для non-social
                        desire_priority = PRIORITY_LLM_NONSOCIAL
                        desire_urgency  = float(item.get('urgency', 0.5))

                    desire = Desire(
                        description=desc,
                        priority=desire_priority,
                        urgency=desire_urgency,
                        motivation_type=mtype,
                        source='llm_dynamic',
                        personality_alignment=0.9,  # выше 0.75 → лучший utility
                        status=DesireStatus.ACTIVE,
                        context=ctx
                    )
                    new_desires.append(desire)
                    print(f"🧠 [{agent_id}] LLM desire «{desc[:40]}» "
                          f"(priority={desire_priority:.2f}, type={mtype.value})")

            except Exception as e:
                print(f"⚠️ [{agent_id}] LLM desire generation failed: {e}. Fallback → THINK")
                new_desires.append(Desire(
                    description='Задуматься о происходящем',
                    motivation_type=MotivationType.CURIOSITY,
                    priority=PRIORITY_LLM_NONSOCIAL,
                    urgency=0.2,
                    source='llm_fallback',
                    personality_alignment=0.5,
                    status=DesireStatus.ACTIVE,
                    context={'action': 'think', 'topic': 'general'}
                ))

        # ════════════════════════════════════════════════════════════
        # 4. Idle Drive — Tier 1 (минимальный приоритет)
        #    Срабатывает только если нет ни одного не-социального желания
        # ════════════════════════════════════════════════════════════
        all_active = [
            d for d in current_desires + new_desires
            if d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
        ]
        has_non_social_active = any(
            d.motivation_type not in (MotivationType.SOCIAL, MotivationType.WORLD_EVENT)
            for d in all_active
        )
        if not has_non_social_active:
            idle = self._generate_idle_desire(agent_id, personality)
            already_idle = any(
                d.description == idle.description
                and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                for d in current_desires
            )
            if not already_idle:
                new_desires.append(idle)
                print(f"💤 [{agent_id}] Idle Drive: «{idle.description}» "
                      f"(priority={PRIORITY_IDLE:.2f}, соц.блок={globally_blocked})")

        return new_desires

    # ── Вспомогательные методы ────────────────────────────────────────

    def _generate_idle_desire(self, agent_id: str, personality: Dict[str, float] = None) -> Desire:
        """Фоновое несоциальное желание когда пул пуст."""
        p = personality or {}
        curious_options = [
            {'description': 'Изучить что-то новое в округе',
             'motivation_type': MotivationType.CURIOSITY,
             'context': {'action': 'observe', 'subject': 'surroundings'}},
            {'description': 'Поразмышлять о прочитанном',
             'motivation_type': MotivationType.CURIOSITY,
             'context': {'action': 'think', 'topic': 'ideas'}},
            {'description': 'Исследовать библиотеку',
             'motivation_type': MotivationType.CURIOSITY,
             'context': {'action': 'move', 'destination': 'Библиотека'}},
            {'description': 'Понаблюдать за окружением',
             'motivation_type': MotivationType.CURIOSITY,
             'context': {'action': 'observe', 'subject': 'world'}},
        ]
        organized_options = [
            {'description': 'Привести мысли в порядок',
             'motivation_type': MotivationType.ACHIEVEMENT,
             'context': {'action': 'think', 'topic': 'planning'}},
            {'description': 'Составить план на день',
             'motivation_type': MotivationType.ACHIEVEMENT,
             'context': {'action': 'think', 'topic': 'schedule'}},
            {'description': 'Пройтись по площади',
             'motivation_type': MotivationType.SAFETY,
             'context': {'action': 'move', 'destination': 'Центральная площадь'}},
        ]
        wander_options = [
            {'description': 'Прогуляться без цели',
             'motivation_type': MotivationType.SAFETY,
             'context': {'action': 'move', 'destination': 'Парк'}},
            {'description': 'Осмотреться вокруг',
             'motivation_type': MotivationType.CURIOSITY,
             'context': {'action': 'observe', 'subject': 'surroundings'}},
            {'description': 'Помечтать в тишине',
             'motivation_type': MotivationType.SAFETY,
             'context': {'action': 'think', 'topic': 'daydream'}},
        ]

        openness = p.get('openness', 0.5)
        conscientiousness = p.get('conscientiousness', 0.5)
        if openness > 0.7:
            pool = curious_options
        elif conscientiousness > 0.7:
            pool = organized_options
        else:
            pool = wander_options

        chosen = random.choice(pool)
        return Desire(
            description=chosen['description'],
            priority=PRIORITY_IDLE,   # Tier 1 — самый низкий
            urgency=0.1,
            motivation_type=chosen['motivation_type'],
            source='idle_drive',
            personality_alignment=0.5,
            status=DesireStatus.ACTIVE,
            context={**chosen['context'], 'is_idle': True}
        )

    def _find_available_agent(self, beliefs_base, self_id: str) -> Optional[str]:
        try:
            from beliefs import BeliefType
        except ImportError:
            try:
                from core.bdi.beliefs import BeliefType
            except ImportError:
                return None
        agent_beliefs = beliefs_base.get_beliefs_by_type(BeliefType.AGENT)
        candidates = list(set(
            b.subject for b in agent_beliefs if b.subject and b.subject != self_id
        ))
        if not candidates:
            return None
        for aid in candidates:
            b = beliefs_base.get_belief(BeliefType.AGENT, aid, 'in_conversation')
            if not (b and b.value):
                return aid
        return candidates[0]

    def _pick_topic(self, personality: Dict) -> str:
        topics = (
            ['новые идеи', 'искусство', 'наука', 'будущее', 'технологии']
            if personality.get('openness', 0.5) > 0.7
            else ['последние события', 'хобби', 'планы', 'общие интересы']
            if personality.get('extraversion', 0.5) > 0.7
            else ['работа', 'книги', 'кино']
        )
        return random.choice(topics)

    def _has_similar_active_desire(self, desires: List[Desire], source: str) -> bool:
        return any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.source in (f"personality_{source}", source, 'llm_dynamic')
            for d in desires
        )


def create_custom_desire(description: str,
                         motivation_type: MotivationType = MotivationType.SOCIAL,
                         priority: float = 0.5, urgency: float = 0.5, **kwargs) -> Desire:
    return Desire(description=description, motivation_type=motivation_type,
                  priority=priority, urgency=urgency, **kwargs)