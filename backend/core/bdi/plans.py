"""
plans.py  [v5 — Динамический планировщик]

Ключевые изменения v5:
1. УДАЛЕНЫ: _create_initiator_plan, _create_respond_plan — жёсткие массивы шагов.
2. ДОБАВЛЕН: create_dynamic_plan — универсальный метод для диалоговых планов.
   - Максимум 2 шага: [Action, WAIT_FOR_RESPONSE] или [Action, END_CONVERSATION].
   - Использует llm.generate_next_plan_step для определения следующего шага.
   - При сбое LLM → fallback на минимальный plan.
3. СОХРАНЕНЫ: все не-диалоговые планы (movement, search, learning, idle, solo).
4. extend_conversation_plan — метод для «достройки» плана из deliberation_cycle
   после получения нового сообщения.
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


# Маппинг строк из LLM → ActionType
_ACTION_STRING_MAP = {
    "send_message": ActionType.SEND_MESSAGE,
    "wait_for_response": ActionType.WAIT_FOR_RESPONSE,
    "end_conversation": ActionType.END_CONVERSATION,
    "initiate_conversation": ActionType.INITIATE_CONVERSATION,
    "respond_to_message": ActionType.RESPOND_TO_MESSAGE,
    "think": ActionType.THINK,
}


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
        """При таймауте wait_for_response — пропустить до END_CONVERSATION."""
        for i in range(current_idx, len(self.steps)):
            if self.steps[i].action_type == ActionType.END_CONVERSATION:
                for j in range(current_idx, i):
                    self.steps[j].executed = True
                    self.steps[j].success = False
                    self.steps[j].timed_out = True
                return i
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

        # ── Диалоговые планы (теперь через create_dynamic_plan) ──────
        if desire.source == 'incoming_message' or desc.startswith('ответить'):
            return self.create_dynamic_plan(
                desire=desire,
                beliefs_base=beliefs_base,
                agent_id=agent_id,
                role='responder'
            )

        # Idle Drive — одно простое действие
        if getattr(desire, 'source', '') == 'idle_drive' or desire.context.get('is_idle'):
            return self._create_idle_plan(desire, beliefs_base, agent_id)

        # Социальное желание — инициатор через динамический план
        social_kw = ['поговорить', 'общаться', 'сказать', 'пообщаться',
                     'поделиться', 'помочь', 'найти утешение']
        if any(w in desc for w in social_kw):
            return self.create_dynamic_plan(
                desire=desire,
                beliefs_base=beliefs_base,
                agent_id=agent_id,
                role='initiator'
            )

        if any(w in desc for w in ['пойти', 'переместиться', 'идти', 'прогуляться']):
            return self._create_movement_plan(desire, beliefs_base, agent_id)
        if any(w in desc for w in ['найти', 'искать', 'поиск']):
            return self._create_search_plan(desire, beliefs_base, agent_id)
        if any(w in desc for w in ['изучить', 'узнать', 'прочитать', 'исследовать']):
            return self._create_learning_plan(desire, beliefs_base, agent_id)

        if any(w in desc for w in ['тихое место', 'размышлени', 'побыть одному', 'уединени']):
            return self._create_solo_plan(desire, beliefs_base, agent_id, mode='reflection')
        if any(w in desc for w in ['организовать', 'упорядочить', 'дела']):
            return self._create_solo_plan(desire, beliefs_base, agent_id, mode='organize')

        return self._create_generic_plan(desire, beliefs_base, agent_id)

    # ──────────────────────────────────────────────────────────────────
    # НОВЫЙ МЕТОД: create_dynamic_plan
    # Диалоговый план максимум из 2 шагов.
    # Первый шаг — строится детерминированно (INITIATE + SEND_MESSAGE).
    # Следующие шаги — либо из LLM, либо минимальный fallback.
    # ──────────────────────────────────────────────────────────────────

    def create_dynamic_plan(
        self,
        desire,
        beliefs_base,
        agent_id: str,
        role: str = 'initiator',     # 'initiator' | 'responder'
        conversation_history: List[Dict] = None,
        social_battery: float = 1.0,
        personality: Dict = None
    ) -> Plan:
        """
        Динамический диалоговый план.

        Структура (максимум 2 шага за один вызов):
          Инициатор:  INITIATE_CONVERSATION → SEND_MESSAGE(greeting) → WAIT_FOR_RESPONSE
          Ответчик:   INITIATE_CONVERSATION → SEND_MESSAGE(answer)   → (WAIT или END)

        После получения ответа deliberation_cycle вызывает extend_conversation_plan
        чтобы добавить следующие 1–2 шага.
        """
        target = desire.context.get('target_agent', '')
        if not target and beliefs_base is not None:
            target = self._find_target_from_beliefs(beliefs_base, agent_id)

        topic = desire.context.get('topic', 'общие темы')
        msg_id = desire.context.get('in_reply_to_msg', '')
        incoming = desire.context.get('incoming_content', '')

        steps = []

        # ── Шаг 0: Войти в диалог ─────────────────────────────────
        steps.append(PlanStep(
            action_type=ActionType.INITIATE_CONVERSATION,
            parameters={"target": target, "topic": topic},
            description=f"Войти в диалог с {target}",
            estimated_duration=0.5
        ))

        # ── Шаг 1: Первое сообщение (зависит от роли) ────────────
        if role == 'initiator':
            message_type = "greeting"
            desc = f"Поздороваться с {target}"
            requires_response = True
        else:
            message_type = "answer"
            desc = f"Ответить {target}"
            requires_response = False

        send_params = {
            "target": target,
            "message_type": message_type,
            "topic": topic,
            "requires_response": requires_response,
            "tone": "friendly"
        }
        if msg_id:
            send_params["in_reply_to"] = msg_id
        if incoming:
            send_params["incoming_content"] = incoming

        steps.append(PlanStep(
            action_type=ActionType.SEND_MESSAGE,
            parameters=send_params,
            description=desc,
            estimated_duration=1.5
        ))

        # ── Шаг 2: Следующее действие (из LLM или fallback) ───────
        next_steps = self._get_next_steps_from_llm(
            desire=desire,
            agent_id=agent_id,
            conversation_history=conversation_history or [],
            social_battery=social_battery,
            personality=personality or {},
            target=target,
            topic=topic
        )
        steps.extend(next_steps)

        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Диалог с {target} {'начат' if role == 'initiator' else 'продолжен'}"
        )

    def extend_conversation_plan(
        self,
        intention,             # Intention объект с текущим планом
        desire,
        agent_id: str,
        conversation_history: List[Dict] = None,
        social_battery: float = 1.0,
        personality: Dict = None,
        force_end: bool = False
    ) -> None:
        """
        Достраивает план в процессе диалога: добавляет 1–2 шага к концу плана.
        Вызывается из deliberation_cycle после получения нового входящего сообщения.

        force_end=True: принудительно добавить farewell + end_conversation (WRAP_UP).
        """
        target = desire.context.get('target_agent', '')
        topic = desire.context.get('topic', 'general')
        plan = intention.plan

        if force_end:
            # WRAP_UP — заменяем оставшиеся шаги на прощание
            remaining = plan.get_remaining_steps()
            for s in remaining:
                s.executed = True
                s.success = False
                s.timed_out = True

            plan.steps.extend([
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": "farewell",
                        "requires_response": False, "tone": "friendly"
                    },
                    description="Попрощаться",
                    estimated_duration=1.0
                ),
                PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": target},
                    description="Завершить разговор",
                    estimated_duration=0.5
                )
            ])
            plan.estimated_total_duration = sum(s.estimated_duration for s in plan.steps)
            print(f"🏁 [{agent_id}] WRAP_UP: добавлено farewell + end_conversation")
            return

        # Нормальное расширение плана через LLM
        next_steps = self._get_next_steps_from_llm(
            desire=desire,
            agent_id=agent_id,
            conversation_history=conversation_history or [],
            social_battery=social_battery,
            personality=personality or {},
            target=target,
            topic=topic
        )
        plan.steps.extend(next_steps)
        plan.estimated_total_duration = sum(s.estimated_duration for s in plan.steps)

    # ── Внутренние хелперы ────────────────────────────────────────────

    def _get_next_steps_from_llm(
        self,
        desire,
        agent_id: str,
        conversation_history: List[Dict],
        social_battery: float,
        personality: Dict,
        target: str,
        topic: str
    ) -> List[PlanStep]:
        """
        Запрашивает LLM за следующими 1–2 шагами плана.
        Возвращает список PlanStep готовых к добавлению в план.
        Fallback при сбое: [WAIT_FOR_RESPONSE] или [END_CONVERSATION].
        """
        if self.llm is None:
            return self._fallback_next_steps(target, social_battery)

        try:
            raw_steps = self.llm.generate_next_plan_step(
                agent_name=agent_id,
                agent_id=agent_id,
                personality=personality,
                current_desire_description=desire.description,
                conversation_history=conversation_history,
                social_battery=social_battery
            )
            return self._build_steps_from_action_list(raw_steps, target, topic, social_battery)
        except Exception as e:
            print(f"⚠️ [{agent_id}] _get_next_steps_from_llm failed: {e}. Fallback.")
            return self._fallback_next_steps(target, social_battery)

    def _build_steps_from_action_list(
        self,
        action_list: List[str],
        target: str,
        topic: str,
        social_battery: float
    ) -> List[PlanStep]:
        """Конвертирует список строк ActionType в PlanStep объекты."""
        steps = []
        for action_str in action_list[:2]:  # максимум 2 шага
            atype = _ACTION_STRING_MAP.get(action_str.lower())
            if atype is None:
                continue

            if atype == ActionType.SEND_MESSAGE:
                msg_type = "farewell" if social_battery < 0.2 else "statement"
                steps.append(PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": msg_type,
                        "topic": topic, "requires_response": False, "tone": "friendly"
                    },
                    description=f"Продолжить разговор с {target}",
                    estimated_duration=1.5
                ))
            elif atype == ActionType.WAIT_FOR_RESPONSE:
                steps.append(PlanStep(
                    action_type=ActionType.WAIT_FOR_RESPONSE,
                    parameters={
                        "expected_from": target,
                        "timeout": 30.0,
                        "max_ticks": 6,
                        "on_timeout": "end"
                    },
                    description=f"Ждать ответа {target}",
                    estimated_duration=5.0
                ))
            elif atype == ActionType.END_CONVERSATION:
                steps.append(PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": target},
                    description="Завершить разговор",
                    estimated_duration=0.5
                ))
            elif atype == ActionType.THINK:
                steps.append(PlanStep(
                    action_type=ActionType.THINK,
                    parameters={"topic": "диалог"},
                    description="Задуматься о разговоре",
                    estimated_duration=1.0
                ))
            elif atype == ActionType.RESPOND_TO_MESSAGE:
                steps.append(PlanStep(
                    action_type=ActionType.RESPOND_TO_MESSAGE,
                    parameters={
                        "target": target, "message_type": "answer",
                        "topic": topic, "requires_response": False
                    },
                    description=f"Ответить {target}",
                    estimated_duration=1.5
                ))
        return steps

    def _fallback_next_steps(self, target: str, social_battery: float) -> List[PlanStep]:
        """Fallback план при недоступности LLM."""
        if social_battery < 0.3:
            # Сил мало — сразу прощаться
            return [
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": target, "message_type": "farewell",
                        "requires_response": False, "tone": "friendly"
                    },
                    description="Попрощаться",
                    estimated_duration=1.0
                ),
                PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": target},
                    description="Завершить разговор",
                    estimated_duration=0.5
                )
            ]
        # Нормальное состояние — ждём ответа
        return [
            PlanStep(
                action_type=ActionType.WAIT_FOR_RESPONSE,
                parameters={
                    "expected_from": target,
                    "timeout": 30.0, "max_ticks": 6, "on_timeout": "end"
                },
                description=f"Ждать ответа {target}",
                estimated_duration=5.0
            ),
            PlanStep(
                action_type=ActionType.END_CONVERSATION,
                parameters={"target": target},
                description="Завершить разговор",
                estimated_duration=0.5
            )
        ]

    def _find_target_from_beliefs(self, beliefs_base, agent_id: str) -> str:
        try:
            try:
                from core.bdi.beliefs import BeliefType
            except ImportError:
                from beliefs import BeliefType
            agent_beliefs = beliefs_base.get_beliefs_by_type(BeliefType.AGENT)
            known = list(set(
                b.subject for b in agent_beliefs if b.subject and b.subject != agent_id
            ))
            return known[0] if known else ''
        except Exception:
            return ''

    # ── Не-диалоговые планы (без изменений) ──────────────────────────

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
        """Idle Drive план: одно простое несоциальное действие."""
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
        else:
            steps = [PlanStep(
                action_type=ActionType.OBSERVE,
                parameters={"subject": "surroundings"},
                description="Осмотреться вокруг",
                estimated_duration=1.0
            )]

        return Plan(goal=desire.description, steps=steps, expected_outcome="Idle завершён")

    def _create_solo_plan(self, desire, beliefs_base, agent_id: str, mode: str = 'reflection') -> Plan:
        """Автономный план для несоциальных желаний."""
        import random
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