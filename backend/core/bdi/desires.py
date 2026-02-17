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
        self.post_conversation_cooldown = 120.0

        # ── Глобальный социальный блок ────────────────────────────────
        self._last_conversation_ended_at: float = 0.0
        self.global_social_cooldown = 90.0

        # ── Тиковый счётчик ──────────────────────────────────────────
        self._ticks_since_conversation_ended: int = 999
        self.min_rest_ticks: int = 8

        # ── Social Satiety (несоциальные действия после разговора) ───
        self._solo_actions_after_conversation: int = 999
        self.MIN_SOLO_ACTIONS: int = 4

    # ── Cooldown/block API ────────────────────────────────────────────

    def mark_conversation_ended(self, partner_id: str):
        now = time.time()
        self._conversation_ended_at[partner_id] = now
        self._last_conversation_ended_at = now
        self._ticks_since_conversation_ended = 0
        self._solo_actions_after_conversation = 0

    def mark_solo_action(self, action_type: str):
        SOCIAL_ACTION_TYPES = {
            'initiate_conversation', 'send_message', 'respond_to_message',
            'wait_for_response', 'end_conversation'
        }
        if action_type not in SOCIAL_ACTION_TYPES:
            self._solo_actions_after_conversation += 1

    def tick(self):
        self._ticks_since_conversation_ended += 1

    def is_on_cooldown(self, partner_id: str) -> bool:
        last = self._conversation_ended_at.get(partner_id, 0)
        return (time.time() - last) < self.post_conversation_cooldown

    def is_globally_social_blocked(self) -> bool:
        time_ok = (time.time() - self._last_conversation_ended_at) >= self.global_social_cooldown
        ticks_ok = self._ticks_since_conversation_ended >= self.min_rest_ticks
        solo_ok = self._solo_actions_after_conversation >= self.MIN_SOLO_ACTIONS
        return not (time_ok and ticks_ok and solo_ok)

    def get_social_block_reason(self) -> str:
        reasons = []
        time_left = self.global_social_cooldown - (time.time() - self._last_conversation_ended_at)
        if time_left > 0:
            reasons.append(f"время: ещё {time_left:.0f}с")
        ticks_left = self.min_rest_ticks - self._ticks_since_conversation_ended
        if ticks_left > 0:
            reasons.append(f"тики: ещё {ticks_left}")
        solo_left = self.MIN_SOLO_ACTIONS - self._solo_actions_after_conversation
        if solo_left > 0:
            reasons.append(f"solo-действий: ещё {solo_left}")
        return " | ".join(reasons) if reasons else "разблокирован"

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
        social_battery: float = 1.0        # ← НОВЫЙ параметр
    ) -> List[Desire]:
        new_desires = []
        current_time = time.time()
        active_partners = set(active_conversation_partners or [])

        # ════════════════════════════════════════════════════════════
        # 1. Реактивное желание ответить (остаётся rule-based — срочное)
        # ════════════════════════════════════════════════════════════
        if perceptions:
            for perception in perceptions:
                if perception.get('type') != 'communication':
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
                if self.is_on_cooldown(sender_id):
                    print(f"⏸️ [{agent_id}] Кулдаун с {sender_id} — skip respond_desire")
                    continue
                if sender_id not in active_partners:
                    print(f"🚫 [{agent_id}] Не в диалоге с {sender_id} — skip respond_desire")
                    continue

                has_initiator = any(
                    d.context.get('target_agent') == sender_id
                    and d.source != 'incoming_message'
                    and d.status == DesireStatus.PURSUED
                    for d in current_desires
                )
                if has_initiator:
                    print(f"🚫 [{agent_id}] Уже инициирует диалог с {sender_id} — skip")
                    continue

                already = any(
                    d.context.get('target_agent') == sender_id
                    and d.source == 'incoming_message'
                    and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                    for d in current_desires
                )
                if already:
                    continue

                desire = Desire(
                    description=f'Ответить {sender_id}',
                    motivation_type=MotivationType.SOCIAL,
                    priority=0.95, urgency=0.9,
                    source='incoming_message',
                    personality_alignment=personality.get('agreeableness', 0.7),
                    context={
                        'target_agent': sender_id,
                        'topic': topic,
                        'in_reply_to_msg': msg_id,
                        'incoming_content': content,
                        'intent': 'respond'
                    }
                )
                new_desires.append(desire)
                print(f"💡 [{agent_id}] Создано желание ответить {sender_id} (тип: {msg_type})")

        # ════════════════════════════════════════════════════════════
        # 2. Продвижение тикового счётчика
        # ════════════════════════════════════════════════════════════
        self.tick()

        globally_blocked = self.is_globally_social_blocked()
        if globally_blocked:
            print(f"🛑 [{agent_id}] Соц. блок — {self.get_social_block_reason()}")

        # ════════════════════════════════════════════════════════════
        # 3. LLM-генерация желаний личности (заменяет rule-based rules)
        # ════════════════════════════════════════════════════════════
        # Вызываем LLM не чаще раза в llm_cooldown_seconds,
        # и только если нет ни одного активного несоциального желания.
        has_active_nonsocial = any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.motivation_type != MotivationType.SOCIAL
            for d in current_desires
        )

        should_call_llm = (
            self.llm is not None
            and not has_active_nonsocial
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

                    # Не дублируем уже существующие желания
                    already_exists = any(
                        d.description.lower() == desc.lower()
                        and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                        for d in current_desires + new_desires
                    )
                    if already_exists:
                        continue

                    raw_mtype = item.get('motivation_type', 'curiosity').lower()
                    mtype = _MOTIVATION_MAP.get(raw_mtype, MotivationType.CURIOSITY)

                    # social желание заблокировано во время отдыха
                    if mtype == MotivationType.SOCIAL and globally_blocked:
                        print(f"🛑 [{agent_id}] LLM social desire заблокировано — {desc[:30]}")
                        continue

                    # При низкой батарейке принудительно меняем SOCIAL → SAFETY
                    if mtype == MotivationType.SOCIAL and social_battery < 0.2:
                        print(f"🔋 [{agent_id}] Battery low: меняем SOCIAL → SAFETY для '{desc[:30]}'")
                        mtype = MotivationType.SAFETY

                    # Для SOCIAL желаний ищем свободного партнёра
                    ctx = dict(item.get('context', {}) or {})
                    if mtype == MotivationType.SOCIAL:
                        target = self._find_available_agent(beliefs_base, agent_id)
                        if target:
                            ctx['target_agent'] = target
                            ctx['topic'] = ctx.get('topic') or self._pick_topic(personality)
                            ctx['intent'] = 'chat'
                        # Нет свободного партнёра — пропускаем социальное желание
                        if not ctx.get('target_agent'):
                            continue
                        # Проверяем cooldown на конкретного партнёра
                        if self.is_on_cooldown(ctx['target_agent']):
                            continue

                    desire = Desire(
                        description=desc,
                        priority=float(item.get('priority', 0.5)),
                        urgency=float(item.get('urgency', 0.5)),
                        motivation_type=mtype,
                        source='llm_dynamic',
                        personality_alignment=0.75,
                        status=DesireStatus.ACTIVE,
                        context=ctx
                    )
                    new_desires.append(desire)

            except Exception as e:
                # Fallback при ошибке LLM — агент задумывается
                print(f"⚠️ [{agent_id}] LLM desire generation failed: {e}. Fallback → THINK")
                new_desires.append(Desire(
                    description='Задуматься о происходящем',
                    motivation_type=MotivationType.CURIOSITY,
                    priority=0.3, urgency=0.2,
                    source='llm_fallback',
                    personality_alignment=0.5,
                    status=DesireStatus.ACTIVE,
                    context={'action': 'think', 'topic': 'general'}
                ))

        # ════════════════════════════════════════════════════════════
        # 4. Idle Drive — когда пул желаний полностью пуст
        # ════════════════════════════════════════════════════════════
        all_active = [
            d for d in current_desires + new_desires
            if d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
        ]
        has_non_social_active = any(
            d.motivation_type != MotivationType.SOCIAL for d in all_active
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
                      f"(соц. блок: {globally_blocked})")

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
            priority=0.15, urgency=0.1,
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