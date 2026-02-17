"""
desires.py  [v4 — финальный рефакторинг]

Ключевые исправления:
1. respond_desire создаётся ТОЛЬКО если агент сейчас в активном диалоге с отправителем.
   Если разговор уже завершён — игнорируем все входящие от этого агента.
2. Кулдаун поднят до 60 сек и теперь применяется ко ВСЕМ сообщениям от партнёра,
   не только к farewell.
3. respond_desire не создаётся если агент-инициатор уже ведёт другой план общения
   с этим же агентом (проверка через current_intentions в context).
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


class DesireGenerator:

    def __init__(self):
        self.rules = self._initialize_rules()
        self.rule_last_triggered: Dict[str, float] = {}
        self.rule_cooldown_seconds = 300.0  # 5 мин между срабатываниями правил личности

        # agent_id → timestamp последнего конца разговора с ним
        self._conversation_ended_at: Dict[str, float] = {}
        # Кулдаун на конкретного партнёра — 120 сек (агент занят «перевариванием»)
        self.post_conversation_cooldown = 120.0

        # Глобальный timestamp последнего завершённого разговора.
        # Правила личности не срабатывают пока не прошло global_cooldown.
        self._last_conversation_ended_at: float = 0.0
        # Глобальный кулдаун на ЛЮБОЙ новый социальный контакт — 90 сек
        self.global_social_cooldown = 90.0

        # Тиковый счётчик: сколько тиков прошло с момента последнего завершения.
        # Используется КАК ДОПОЛНЕНИЕ к временному кулдауну, потому что тики
        # нерегулярны и время может не успевать обновляться.
        self._ticks_since_conversation_ended: int = 999  # старт = «давно»
        # Минимум тиков отдыха после разговора
        self.min_rest_ticks: int = 8

        # ── Social Satiety: счётчик индивидуальных (несоциальных) действий ──
        # После конца разговора агент должен выполнить MIN_SOLO_ACTIONS
        # несоциальных действий прежде чем снова инициировать общение.
        self._solo_actions_after_conversation: int = 999  # старт = «уже отдохнул»
        self.MIN_SOLO_ACTIONS: int = 4  # минимум: move/think/observe/search/...

    def mark_conversation_ended(self, partner_id: str):
        """Симулятор вызывает это при end_conversation."""
        now = time.time()
        self._conversation_ended_at[partner_id] = now
        self._last_conversation_ended_at = now
        # Сброс тикового счётчика — агент «только что» закончил разговор
        self._ticks_since_conversation_ended = 0
        # Сброс solo-счётчика — нужно сначала заняться своими делами
        self._solo_actions_after_conversation = 0

    def mark_solo_action(self, action_type: str):
        """
        Deliberation вызывает это когда агент завершает несоциальное намерение.
        Засчитываются: move, think, observe, search, learn, организация дел.
        НЕ засчитываются: initiate_conversation, send_message, respond_to_message.
        """
        SOCIAL_ACTION_TYPES = {
            'initiate_conversation', 'send_message', 'respond_to_message',
            'wait_for_response', 'end_conversation'
        }
        if action_type not in SOCIAL_ACTION_TYPES:
            self._solo_actions_after_conversation += 1

    def tick(self):
        """Вызывается из DeliberationCycle каждый цикл — продвигает тиковый счётчик."""
        self._ticks_since_conversation_ended += 1

    def is_on_cooldown(self, partner_id: str) -> bool:
        """True если разговор с этим партнёром завершился недавно."""
        last = self._conversation_ended_at.get(partner_id, 0)
        return (time.time() - last) < self.post_conversation_cooldown

    def is_globally_social_blocked(self) -> bool:
        """
        True если агент ещё «переваривает» прошедший разговор.
        Разблокировка требует выполнения ВСЕХ трёх условий:
          1. прошло достаточно реального времени
          2. прошло достаточно тиков
          3. выполнено достаточно индивидуальных (несоциальных) действий
        """
        time_ok = (time.time() - self._last_conversation_ended_at) >= self.global_social_cooldown
        ticks_ok = self._ticks_since_conversation_ended >= self.min_rest_ticks
        solo_ok = self._solo_actions_after_conversation >= self.MIN_SOLO_ACTIONS
        return not (time_ok and ticks_ok and solo_ok)

    def get_social_block_reason(self) -> str:
        """Возвращает читаемую причину блокировки (для логов)."""
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

    def _initialize_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'extravert_socialization',
                'condition': lambda p, e, b: p.get('extraversion', 0.5) > 0.6,
                'desire_template': {
                    'description': 'Поговорить с кем-то интересным',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.75, 'urgency': 0.6,
                    'source': 'personality_extraversion'
                }
            },
            {
                'name': 'introvert_solitude',
                'condition': lambda p, e, b: p.get('extraversion', 0.5) < 0.3,
                'desire_template': {
                    'description': 'Найти тихое место для размышлений',
                    'motivation_type': MotivationType.SAFETY,
                    'priority': 0.6, 'urgency': 0.4,
                    'source': 'personality_introversion'
                }
            },
            {
                'name': 'openness_exploration',
                'condition': lambda p, e, b: p.get('openness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Изучить что-то новое',
                    'motivation_type': MotivationType.CURIOSITY,
                    'priority': 0.65, 'urgency': 0.3,
                    'source': 'personality_openness'
                }
            },
            {
                'name': 'agreeableness_help',
                'condition': lambda p, e, b: p.get('agreeableness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Помочь кому-то в нужде',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.65, 'urgency': 0.5,
                    'source': 'personality_agreeableness'
                }
            },
            {
                'name': 'conscientiousness_organize',
                'condition': lambda p, e, b: p.get('conscientiousness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Организовать и упорядочить дела',
                    'motivation_type': MotivationType.ACHIEVEMENT,
                    'priority': 0.6, 'urgency': 0.4,
                    'source': 'personality_conscientiousness'
                }
            },
            {
                'name': 'sadness_comfort',
                'condition': lambda p, e, b: e.get('sadness', 0) > 0.6,
                'desire_template': {
                    'description': 'Найти утешение',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.8, 'urgency': 0.7,
                    'source': 'emotion_sadness'
                }
            },
            {
                'name': 'fear_safety',
                'condition': lambda p, e, b: e.get('fear', 0) > 0.6,
                'desire_template': {
                    'description': 'Найти безопасное место',
                    'motivation_type': MotivationType.SAFETY,
                    'priority': 0.9, 'urgency': 0.9,
                    'source': 'emotion_fear'
                }
            },
            {
                'name': 'happiness_share',
                'condition': lambda p, e, b: e.get('happiness', 0) > 0.7,
                'desire_template': {
                    'description': 'Поделиться радостью с другими',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.6, 'urgency': 0.5,
                    'source': 'emotion_happiness'
                }
            },
        ]

    def generate_desires(
        self,
        personality: Dict[str, float],
        emotions: Dict[str, float],
        beliefs_base,
        current_desires: List[Desire],
        agent_id: str = "",
        perceptions: List[Dict] = None,
        active_conversation_partners: List[str] = None
    ) -> List[Desire]:
        new_desires = []
        current_time = time.time()
        active_partners = set(active_conversation_partners or [])

        # ============================================================
        # 1. Желание ответить — только если сейчас в диалоге с отправителем
        # ============================================================
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

                # Не отвечаем на farewell/ack
                if msg_type in _NO_RESPOND_MESSAGE_TYPES:
                    print(f"🔇 [{agent_id}] Игнорируем {msg_type} от {sender_id}")
                    continue

                # Не отвечаем если на кулдауне после разговора с этим агентом
                if self.is_on_cooldown(sender_id):
                    print(f"⏸️ [{agent_id}] Кулдаун с {sender_id} — skip respond_desire")
                    continue

                # FIX A: Не создаём respond_desire если НЕ в активном диалоге с отправителем.
                # Это отсекает "хвостовые" сообщения из уже завершённого разговора.
                if sender_id not in active_partners:
                    print(f"🚫 [{agent_id}] Не в диалоге с {sender_id} — skip respond_desire")
                    continue

                # FIX B: Не создаём respond_desire если уже есть ИНИЦИАТОРСКОЕ желание/план
                # с этим агентом — агент и так общается с ним, ответ будет через statement/farewell.
                has_initiator = any(
                    d.context.get('target_agent') == sender_id
                    and d.source != 'incoming_message'
                    and d.status == DesireStatus.PURSUED
                    for d in current_desires
                )
                if has_initiator:
                    print(f"🚫 [{agent_id}] Уже инициирует диалог с {sender_id} — skip respond_desire")
                    continue

                # Нет уже активного желания ответить этому агенту
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

        # ============================================================
        # 2. Правила личности
        # ============================================================
        # Продвигаем тиковый счётчик отдыха
        self.tick()

        # Если агент ещё «переваривает» прошедший разговор — не генерируем ничего социального.
        # Несоциальные правила (SAFETY, CURIOSITY, ACHIEVEMENT) могут срабатывать.
        globally_blocked = self.is_globally_social_blocked()
        if globally_blocked:
            print(f"🛑 [{agent_id}] Соц. блок — {self.get_social_block_reason()}")

        for rule in self.rules:
            rule_name = rule['name']

            if current_time - self.rule_last_triggered.get(rule_name, 0) < self.rule_cooldown_seconds:
                continue
            if self._has_similar_active_desire(current_desires, rule_name):
                continue
            if not rule['condition'](personality, emotions, beliefs_base):
                continue

            desire = self._create_desire_from_template(
                rule['desire_template'], personality, emotions, beliefs_base, agent_id
            )

            # Социальное желание заблокировано в период отдыха
            if desire.motivation_type == MotivationType.SOCIAL:
                if globally_blocked:
                    continue
                target = desire.context.get('target_agent')
                # Нет цели или цель на кулдауне — пропускаем
                if not target or self.is_on_cooldown(target):
                    continue

            new_desires.append(desire)
            self.rule_last_triggered[rule_name] = current_time

        # ============================================================
        # 3. Idle Drive — автономное действие когда пул пуст
        # ============================================================
        # Если нет ни одного активного/pursued желания (кроме incoming_message)
        # и ничего нового не сгенерировалось — подкидываем фоновое несоциальное желание.
        # Это гарантирует что агент всегда чем-то занят, а не зависает в ожидании диалога.
        all_active = [
            d for d in current_desires + new_desires
            if d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
        ]
        has_non_social_active = any(
            d.motivation_type != MotivationType.SOCIAL for d in all_active
        )
        if not has_non_social_active:
            idle = self._generate_idle_desire(agent_id, personality)
            # Не дублируем — проверяем по описанию
            already_idle = any(
                d.description == idle.description
                and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                for d in current_desires
            )
            if not already_idle:
                new_desires.append(idle)
                print(f"💤 [{agent_id}] Idle Drive: «{idle.description}» (соц. блок: {globally_blocked})")

        return new_desires

    def _generate_idle_desire(self, agent_id: str, personality: Dict[str, float] = None) -> Desire:
        """
        Idle Drive: фоновое несоциальное желание когда пул пуст.
        Выбор опции зависит от черт личности агента.
        Приоритет 0.15: любое настоящее событие или правило перебьёт его.
        """
        import random
        p = personality or {}

        # Пулы опций по типу личности
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
            priority=0.15,
            urgency=0.1,
            motivation_type=chosen['motivation_type'],
            source='idle_drive',
            personality_alignment=0.5,
            status=DesireStatus.ACTIVE,
            context={**chosen['context'], 'is_idle': True}
        )

    def _create_desire_from_template(
        self, template: Dict, personality: Dict, emotions: Dict, beliefs_base, agent_id: str
    ) -> Desire:
        source = template.get('source', 'unknown')
        alignment = 0.7
        if 'extraversion' in source:
            alignment = personality.get('extraversion', 0.5)
        elif 'introversion' in source:
            alignment = 1.0 - personality.get('extraversion', 0.5)
        elif 'openness' in source:
            alignment = personality.get('openness', 0.5)
        elif 'agreeableness' in source:
            alignment = personality.get('agreeableness', 0.5)
        elif 'conscientiousness' in source:
            alignment = personality.get('conscientiousness', 0.5)

        context = {}
        motivation = template.get('motivation_type', MotivationType.SOCIAL)
        if motivation == MotivationType.SOCIAL:
            target = self._find_available_agent(beliefs_base, agent_id)
            if target:
                context = {
                    'target_agent': target,
                    'topic': self._pick_topic(personality),
                    'intent': 'chat'
                }

        return Desire(
            description=template['description'],
            priority=template.get('priority', 0.5),
            urgency=template.get('urgency', 0.5),
            motivation_type=motivation,
            source=template.get('source', 'generated'),
            personality_alignment=alignment,
            status=DesireStatus.ACTIVE,
            context=context
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

    def _has_similar_active_desire(self, desires: List[Desire], rule_name: str) -> bool:
        return any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.source in (f"personality_{rule_name}", rule_name)
            for d in desires
        )


def create_custom_desire(description: str,
                         motivation_type: MotivationType = MotivationType.SOCIAL,
                         priority: float = 0.5, urgency: float = 0.5, **kwargs) -> Desire:
    return Desire(description=description, motivation_type=motivation_type,
                  priority=priority, urgency=urgency, **kwargs)