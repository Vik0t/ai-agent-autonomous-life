"""
plans.py  [v4 — финальный рефакторинг]

Ключевые изменения:
1. _create_respond_plan — только answer + end_conversation.
   Без встречного question — это провоцировало новый respond_desire у инициатора.
2. _create_initiator_plan — только ОДИН wait_for_response (после greeting).
   Второй wait убран — он вызывал timeout и бесконечное повторение.
3. Структура диалога:
   Инициатор: init → greeting → wait → statement → farewell → end
   Ответчик:  init → answer → end
   Итого: 2 round-trip, чистое завершение с обеих сторон.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ActionType(Enum):
    MOVE = "move"
    COMMUNICATE = "communicate"
    WAIT = "wait"
    SEARCH = "search"
    ACQUIRE = "acquire"
    USE = "use"
    OBSERVE = "observe"
    THINK = "think"
    EXPRESS = "express"
    HELP = "help"
    REQUEST = "request"
    GIVE = "give"
    INITIATE_CONVERSATION = "initiate_conversation"
    SEND_MESSAGE = "send_message"
    WAIT_FOR_RESPONSE = "wait_for_response"
    RESPOND_TO_MESSAGE = "respond_to_message"
    END_CONVERSATION = "end_conversation"


@dataclass
class PlanStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.WAIT
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    estimated_duration: float = 1.0
    executed: bool = False
    success: bool = False
    actual_duration: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    # Флаг: шаг завершился по таймауту (собеседник не ответил)
    timed_out: bool = False

    def __repr__(self):
        status = "⏱" if self.timed_out else ("✓" if self.executed else "○")
        return f"{status} {self.action_type.value}: {self.description}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'action_type': self.action_type.value,
            'parameters': self.parameters, 'description': self.description,
            'estimated_duration': self.estimated_duration,
            'executed': self.executed, 'success': self.success,
            'actual_duration': self.actual_duration, 'result': self.result,
            'timed_out': self.timed_out
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            action_type=ActionType(data['action_type']),
            parameters=data.get('parameters', {}),
            description=data.get('description', ''),
            estimated_duration=data.get('estimated_duration', 1.0),
            executed=data.get('executed', False), success=data.get('success', False),
            actual_duration=data.get('actual_duration', 0.0), result=data.get('result', {}),
            timed_out=data.get('timed_out', False)
        )


@dataclass
class Plan:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    expected_outcome: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    estimated_total_duration: float = 0.0

    def __post_init__(self):
        self.estimated_total_duration = sum(s.estimated_duration for s in self.steps)

    def get_next_step(self, idx: int) -> Optional[PlanStep]:
        return self.steps[idx] if idx < len(self.steps) else None

    def is_complete(self, idx: int) -> bool:
        return idx >= len(self.steps)

    def get_progress(self, idx: int) -> float:
        return min(1.0, idx / len(self.steps)) if self.steps else 0.0

    def skip_to_end_conversation(self, current_idx: int) -> int:
        """
        При таймауте wait_for_response — пропустить statement/farewell,
        найти ближайший END_CONVERSATION и вернуть его индекс.
        Если не найден — вернуть len(steps) (план завершён).
        """
        for i in range(current_idx, len(self.steps)):
            if self.steps[i].action_type == ActionType.END_CONVERSATION:
                # Пометить пропущенные шаги как «не нужны»
                for j in range(current_idx, i):
                    self.steps[j].executed = True
                    self.steps[j].success = False
                    self.steps[j].timed_out = True
                return i
        # Нет END_CONVERSATION — просто заканчиваем план
        for j in range(current_idx, len(self.steps)):
            self.steps[j].executed = True
            self.steps[j].success = False
            self.steps[j].timed_out = True
        return len(self.steps)

    def get_completed_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.executed]

    def get_remaining_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if not s.executed]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'goal': self.goal,
            'steps': [s.to_dict() for s in self.steps],
            'preconditions': self.preconditions, 'expected_outcome': self.expected_outcome,
            'created_at': self.created_at.isoformat(),
            'estimated_total_duration': self.estimated_total_duration
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        return cls(
            id=data.get('id', str(uuid.uuid4())), goal=data.get('goal', ''),
            steps=[PlanStep.from_dict(s) for s in data.get('steps', [])],
            preconditions=data.get('preconditions', []),
            expected_outcome=data.get('expected_outcome', ''),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        )

    def __repr__(self):
        return f"Plan({self.goal}, {len(self.steps)} steps)"


class Planner:
    def __init__(self, llm_interface=None):
        self.llm = llm_interface

    def create_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        desc = desire.description.lower()

        # Ответ на входящее сообщение
        if desire.source == 'incoming_message' or desc.startswith('ответить'):
            return self._create_respond_plan(desire, beliefs_base, agent_id)

        # Idle Drive — минимальный план одного действия
        if getattr(desire, 'source', '') == 'idle_drive' or desire.context.get('is_idle'):
            return self._create_idle_plan(desire, beliefs_base, agent_id)

        # Социальное желание — инициатор диалога
        social_kw = ['поговорить', 'общаться', 'сказать', 'пообщаться',
                     'поделиться', 'помочь', 'найти утешение']
        if any(w in desc for w in social_kw):
            return self._create_initiator_plan(desire, beliefs_base, agent_id)

        if any(w in desc for w in ['пойти', 'переместиться', 'идти', 'прогуляться']):
            return self._create_movement_plan(desire, beliefs_base, agent_id)
        if any(w in desc for w in ['найти', 'искать', 'поиск']):
            return self._create_search_plan(desire, beliefs_base, agent_id)
        if any(w in desc for w in ['изучить', 'узнать', 'прочитать', 'исследовать']):
            return self._create_learning_plan(desire, beliefs_base, agent_id)

        # Несоциальные личностные желания → план автономной деятельности
        if any(w in desc for w in ['тихое место', 'размышлени', 'побыть одному', 'уединени']):
            return self._create_solo_plan(desire, beliefs_base, agent_id, mode='reflection')
        if any(w in desc for w in ['организовать', 'упорядочить', 'дела']):
            return self._create_solo_plan(desire, beliefs_base, agent_id, mode='organize')

        return self._create_generic_plan(desire, beliefs_base, agent_id)

    # ──────────────────────────────────────────────────────────────────
    # ОТВЕТЧИК FSM: init → answer → wait(6 тиков) → end
    # Ждём реакции собеседника на наш ответ 30 сек (6 тиков по 5с).
    # Завершаем по таймауту или farewell от партнёра.
    # На быстрый ответ farewell от собеседника — сразу END без ожидания.
    # ──────────────────────────────────────────────────────────────────
    def _create_respond_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        target = desire.context.get('target_agent', '')
        topic = desire.context.get('topic', 'general')
        msg_id = desire.context.get('in_reply_to_msg', '')
        incoming = desire.context.get('incoming_content', '')

        return Plan(
            goal=f"Ответить {target}",
            steps=[
                # 1. Войти в диалог (или переиспользовать существующий)
                PlanStep(
                    action_type=ActionType.INITIATE_CONVERSATION,
                    parameters={"target": target, "topic": topic},
                    description=f"Войти в диалог с {target}",
                    estimated_duration=0.5
                ),
                # 2. Отправить содержательный ответ
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target,
                        "message_type": "answer",
                        "topic": topic,
                        "in_reply_to": msg_id,
                        "incoming_content": incoming,
                        "requires_response": False,
                        "tone": "friendly"
                    },
                    description=f"Ответить {target}",
                    estimated_duration=1.5
                ),
                # 3. Ждём реакции — 6 тиков (30 сек при тике 5с).
                #    on_timeout="end": тишина → завершаем разговор чисто.
                #    farewell от партнёра → тоже сразу END.
                PlanStep(
                    action_type=ActionType.WAIT_FOR_RESPONSE,
                    parameters={
                        "expected_from": target,
                        "timeout": 30.0,
                        "max_ticks": 6,
                        "on_timeout": "end"
                    },
                    description=f"Ждать реакции {target}",
                    estimated_duration=5.0
                ),
                # 4. Завершить разговор
                PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": target},
                    description="Завершить разговор",
                    estimated_duration=0.5
                ),
            ],
            expected_outcome=f"Диалог с {target} завершён"
        )

    # ──────────────────────────────────────────────────────────────────
    # ИНИЦИАТОР: init → greeting → wait(1) → statement → farewell → end
    # Только ОДИН wait_for_response. Второй wait убран — он вызывал
    # timeout и запуск нового разговора.
    # ──────────────────────────────────────────────────────────────────
    def _create_initiator_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        from .beliefs import BeliefType

        target = desire.context.get('target_agent')
        if not target:
            agent_beliefs = beliefs_base.get_beliefs_by_type(BeliefType.AGENT)
            known = list(set(
                b.subject for b in agent_beliefs if b.subject and b.subject != agent_id
            ))
            target = known[0] if known else None

        if not target:
            return Plan(
                goal="Найти кого-нибудь",
                steps=[
                    PlanStep(action_type=ActionType.MOVE,
                             parameters={"destination": "Центральная площадь"},
                             description="Пойти в людное место"),
                    PlanStep(action_type=ActionType.OBSERVE,
                             parameters={}, description="Осмотреться")
                ]
            )

        desire.context['target_agent'] = target
        topic = desire.context.get('topic', 'общие темы')

        return Plan(
            goal=desire.description,
            steps=[
                # 1. Инициируем диалог
                PlanStep(
                    action_type=ActionType.INITIATE_CONVERSATION,
                    parameters={"target": target, "topic": topic},
                    description=f"Начать разговор с {target}",
                    estimated_duration=0.5
                ),
                # 2. Приветствие
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": "greeting",
                        "topic": topic, "requires_response": True,
                        "response_timeout": 30.0, "tone": "friendly"
                    },
                    description=f"Поздороваться с {target}",
                    estimated_duration=1.0
                ),
                # 3. Ждём ответа на приветствие (единственный wait)
                PlanStep(
                    action_type=ActionType.WAIT_FOR_RESPONSE,
                    parameters={"expected_from": target, "timeout": 30.0},
                    description="Ждать ответа",
                    estimated_duration=5.0
                ),
                # 4. Основное сообщение (НЕ ждём ответа — не создаём второй wait)
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": "statement",
                        "topic": topic, "requires_response": False,
                        "tone": "friendly"
                    },
                    description=f"Обсудить {topic}",
                    estimated_duration=2.0
                ),
                # 5. Прощание
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": "farewell",
                        "requires_response": False, "tone": "friendly"
                    },
                    description="Попрощаться",
                    estimated_duration=1.0
                ),
                # 6. Завершить разговор
                PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": target},
                    description="Завершить разговор",
                    estimated_duration=0.5
                ),
            ],
            expected_outcome=f"Разговор с {target} завершён"
        )

    def _create_movement_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        dest = desire.context.get('destination', 'Центральная площадь')
        return Plan(goal=desire.description, steps=[
            PlanStep(action_type=ActionType.MOVE,
                     parameters={"destination": dest},
                     description=f"Переместиться в {dest}")
        ], expected_outcome=f"В {dest}")

    def _create_search_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        q = desire.context.get('search_query', desire.description)
        return Plan(goal=desire.description, steps=[
            PlanStep(action_type=ActionType.SEARCH, parameters={"query": q},
                     description=f"Искать: {q}"),
            PlanStep(action_type=ActionType.OBSERVE, parameters={},
                     description="Изучить результаты"),
            PlanStep(action_type=ActionType.THINK, parameters={"topic": q},
                     description="Осмыслить"),
        ], expected_outcome="Найти искомое")

    def _create_learning_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        topic = desire.context.get('topic', 'general')
        return Plan(goal=desire.description, steps=[
            PlanStep(action_type=ActionType.MOVE,
                     parameters={"destination": "library"}, description="В библиотеку"),
            PlanStep(action_type=ActionType.SEARCH,
                     parameters={"query": topic}, description=f"Найти: {topic}"),
            PlanStep(action_type=ActionType.OBSERVE,
                     parameters={"subject": topic}, description="Изучить"),
            PlanStep(action_type=ActionType.THINK,
                     parameters={"topic": topic}, description="Обдумать"),
        ], expected_outcome=f"Знания по {topic}")

    def _create_generic_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        return Plan(goal=desire.description, steps=[
            PlanStep(action_type=ActionType.THINK,
                     parameters={"topic": desire.description},
                     description=f"Обдумать: {desire.description}"),
            PlanStep(action_type=ActionType.OBSERVE,
                     parameters={}, description="Оценить ситуацию"),
        ], expected_outcome="Достичь цели")

    def _create_idle_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """
        Idle Drive план: одно простое несоциальное действие.
        Быстро завершается (1 шаг) — чтобы агент не «застрял» в idle.
        Вид действия определяется контекстом желания (action поле).
        """
        action_hint = desire.context.get('action', 'observe')
        dest = desire.context.get('destination', 'Центральная площадь')
        topic = desire.context.get('topic', 'текущие мысли')

        if action_hint == 'move':
            steps = [PlanStep(
                action_type=ActionType.MOVE,
                parameters={"destination": dest},
                description=f"Прогуляться к {dest}",
                estimated_duration=1.0
            )]
        elif action_hint == 'think':
            steps = [PlanStep(
                action_type=ActionType.THINK,
                parameters={"topic": topic},
                description="Мечтать и размышлять",
                estimated_duration=1.0
            )]
        else:  # observe
            steps = [PlanStep(
                action_type=ActionType.OBSERVE,
                parameters={"subject": "surroundings"},
                description="Осмотреться вокруг",
                estimated_duration=1.0
            )]

        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome="Idle завершён"
        )

    def _create_solo_plan(self, desire, beliefs_base, agent_id: str, mode: str = 'reflection') -> Plan:
        """
        Автономный план для несоциальных желаний (размышление, организация дел).
        Специально содержит несколько шагов move/think/observe/search —
        чтобы продвигать счётчик Social Satiety (solo_actions_after_conversation).
        """
        import random
        locations = ['Парк', 'Библиотека', 'Центральная площадь', 'Набережная', 'Кафе']

        if mode == 'reflection':
            dest = random.choice(['Парк', 'Библиотека', 'Набережная'])
            topic = desire.context.get('topic', 'недавние события')
            return Plan(
                goal=desire.description,
                steps=[
                    PlanStep(action_type=ActionType.MOVE,
                             parameters={"destination": dest},
                             description=f"Найти тихое место — {dest}",
                             estimated_duration=1.0),
                    PlanStep(action_type=ActionType.OBSERVE,
                             parameters={"subject": "surroundings"},
                             description="Осмотреться, почувствовать атмосферу",
                             estimated_duration=1.0),
                    PlanStep(action_type=ActionType.THINK,
                             parameters={"topic": topic},
                             description=f"Поразмышлять о {topic}",
                             estimated_duration=2.0),
                    PlanStep(action_type=ActionType.OBSERVE,
                             parameters={"subject": "inner_state"},
                             description="Прислушаться к себе",
                             estimated_duration=1.0),
                ],
                expected_outcome="Уединение и размышление"
            )
        else:  # organize
            return Plan(
                goal=desire.description,
                steps=[
                    PlanStep(action_type=ActionType.THINK,
                             parameters={"topic": "приоритеты и планы"},
                             description="Обдумать приоритеты",
                             estimated_duration=1.5),
                    PlanStep(action_type=ActionType.OBSERVE,
                             parameters={"subject": "environment"},
                             description="Оценить обстановку",
                             estimated_duration=1.0),
                    PlanStep(action_type=ActionType.SEARCH,
                             parameters={"query": "полезные ресурсы"},
                             description="Найти нужные ресурсы",
                             estimated_duration=1.5),
                    PlanStep(action_type=ActionType.THINK,
                             parameters={"topic": "структура дел"},
                             description="Систематизировать задачи",
                             estimated_duration=1.0),
                ],
                expected_outcome="Дела организованы"
            )


# ── Утилиты ──────────────────────────────────────────────────────────

def create_simple_plan(goal: str, action_type: ActionType, **parameters) -> Plan:
    return Plan(goal=goal,
                steps=[PlanStep(action_type=action_type, parameters=parameters, description=goal)],
                expected_outcome=goal)

def create_multi_step_plan(goal: str, steps: List[Dict[str, Any]]) -> Plan:
    return Plan(goal=goal, steps=[
        PlanStep(action_type=s['action'], parameters=s.get('params', {}),
                 description=s.get('desc', ''), estimated_duration=s.get('duration', 1.0))
        for s in steps
    ], expected_outcome=goal)

def create_response_plan(target_agent: str, message_id: str, topic: str) -> Plan:
    return Plan(goal=f"Ответить {target_agent}", steps=[
        PlanStep(action_type=ActionType.RESPOND_TO_MESSAGE,
                 parameters={"target": target_agent, "in_reply_to": message_id,
                              "message_type": "answer", "topic": topic,
                              "requires_response": False},
                 description=f"Ответить {target_agent}")
    ], expected_outcome="Ответ отправлен")