"""
Planning System - Система планирования

Plan (план) - последовательность действий для достижения цели
PlanStep (шаг плана) - одно конкретное действие
Planner (планировщик) - создаёт планы для достижения целей
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ActionType(Enum):
    """Типы действий, которые может выполнять агент"""
    MOVE = "move"                   # Переместиться в другую локацию
    COMMUNICATE = "communicate"     # Общаться с другим агентом
    WAIT = "wait"                   # Подождать
    SEARCH = "search"               # Искать что-то
    ACQUIRE = "acquire"             # Получить ресурс/предмет
    USE = "use"                     # Использовать предмет
    OBSERVE = "observe"             # Наблюдать/изучать
    THINK = "think"                 # Размышлять/анализировать
    EXPRESS = "express"             # Выразить эмоцию
    HELP = "help"                   # Помочь кому-то
    REQUEST = "request"             # Запросить что-то
    GIVE = "give"                   # Отдать что-то


@dataclass
class PlanStep:
    """
    Один шаг в плане - конкретное действие
    
    Примеры:
        PlanStep(action_type=MOVE, parameters={"destination": "cafe"})
        PlanStep(action_type=COMMUNICATE, parameters={"target": "agent_2", "message": "Hello"})
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.WAIT
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    estimated_duration: float = 1.0  # В тактах симуляции
    
    # Результаты выполнения (заполняется после)
    executed: bool = False
    success: bool = False
    actual_duration: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self):
        status = "✓" if self.executed else "○"
        return f"{status} Step({self.action_type.value}: {self.description})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'action_type': self.action_type.value,
            'parameters': self.parameters,
            'description': self.description,
            'estimated_duration': self.estimated_duration,
            'executed': self.executed,
            'success': self.success,
            'actual_duration': self.actual_duration,
            'result': self.result
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        """Десериализация из словаря"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            action_type=ActionType(data['action_type']),
            parameters=data.get('parameters', {}),
            description=data.get('description', ''),
            estimated_duration=data.get('estimated_duration', 1.0),
            executed=data.get('executed', False),
            success=data.get('success', False),
            actual_duration=data.get('actual_duration', 0.0),
            result=data.get('result', {})
        )


@dataclass
class Plan:
    """
    План действий для достижения цели
    
    Содержит последовательность шагов и метаинформацию.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""                          # Описание цели
    steps: List[PlanStep] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)  # Что нужно до начала
    expected_outcome: str = ""              # Ожидаемый результат
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    estimated_total_duration: float = 0.0   # Сумма длительностей шагов
    
    def __post_init__(self):
        """Вычисляем общую длительность"""
        if self.steps:
            self.estimated_total_duration = sum(step.estimated_duration for step in self.steps)
    
    def get_next_step(self, current_step_index: int) -> Optional[PlanStep]:
        """Получить следующий невыполненный шаг"""
        if current_step_index < len(self.steps):
            return self.steps[current_step_index]
        return None
    
    def is_complete(self, current_step_index: int) -> bool:
        """Проверить, завершён ли план"""
        return current_step_index >= len(self.steps)
    
    def get_progress(self, current_step_index: int) -> float:
        """Получить прогресс выполнения (0.0 - 1.0)"""
        if not self.steps:
            return 0.0
        return min(1.0, current_step_index / len(self.steps))
    
    def get_completed_steps(self) -> List[PlanStep]:
        """Получить выполненные шаги"""
        return [step for step in self.steps if step.executed]
    
    def get_remaining_steps(self) -> List[PlanStep]:
        """Получить невыполненные шаги"""
        return [step for step in self.steps if not step.executed]
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'goal': self.goal,
            'steps': [step.to_dict() for step in self.steps],
            'preconditions': self.preconditions,
            'expected_outcome': self.expected_outcome,
            'created_at': self.created_at.isoformat(),
            'estimated_total_duration': self.estimated_total_duration
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """Десериализация из словаря"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            goal=data.get('goal', ''),
            steps=[PlanStep.from_dict(step) for step in data.get('steps', [])],
            preconditions=data.get('preconditions', []),
            expected_outcome=data.get('expected_outcome', ''),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        )
    
    def __repr__(self):
        return f"Plan({self.goal}, {len(self.steps)} steps)"


class Planner:
    """
    Планировщик - создаёт планы для достижения целей
    
    Использует шаблоны и эвристики для создания планов.
    Может интегрироваться с LLM для более сложного планирования.
    """
    
    def __init__(self, llm_interface=None):
        """
        Args:
            llm_interface: Опциональный LLM для генерации планов
        """
        self.llm = llm_interface
        self.plan_templates = self._initialize_templates()
    
    def _initialize_templates(self) -> Dict[str, Any]:
        """Инициализация шаблонов планов"""
        return {
            'communicate': self._create_communication_plan,
            'move': self._create_movement_plan,
            'search': self._create_search_plan,
            'learn': self._create_learning_plan,
            'help': self._create_help_plan,
            'acquire': self._create_acquisition_plan,
        }
    
    def create_plan(
        self,
        desire,
        beliefs_base,
        agent_id: str
    ) -> Plan:
        """
        Создать план для достижения цели
        
        Args:
            desire: Желание (объект Desire)
            beliefs_base: База убеждений агента
            agent_id: ID агента
        
        Returns:
            План действий
        """
        description_lower = desire.description.lower()
        
        # Определяем тип плана по ключевым словам
        if any(word in description_lower for word in ['поговорить', 'общаться', 'сказать', 'пообщаться']):
            return self._create_communication_plan(desire, beliefs_base, agent_id)
        
        elif any(word in description_lower for word in ['пойти', 'переместиться', 'идти']):
            return self._create_movement_plan(desire, beliefs_base, agent_id)
        
        elif any(word in description_lower for word in ['найти', 'искать', 'поиск']):
            return self._create_search_plan(desire, beliefs_base, agent_id)
        
        elif any(word in description_lower for word in ['изучить', 'узнать', 'прочитать', 'исследовать']):
            return self._create_learning_plan(desire, beliefs_base, agent_id)
        
        elif any(word in description_lower for word in ['помочь', 'помощь', 'поддержать']):
            return self._create_help_plan(desire, beliefs_base, agent_id)
        
        elif any(word in description_lower for word in ['получить', 'взять', 'приобрести']):
            return self._create_acquisition_plan(desire, beliefs_base, agent_id)
        
        else:
            # Общий план
            return self._create_generic_plan(desire, beliefs_base, agent_id)
    
    def _create_communication_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для общения с кем-то"""
        from .beliefs import BeliefType
        
        steps = []
        
        # Извлечь target из описания или контекста
        target = desire.context.get('target_agent')
        
        if not target:
            # Пытаемся извлечь из описания
            words = desire.description.split()
            for word in words:
                if word.startswith('agent_'):
                    target = word
                    break
        
        if not target:
            target = "any_agent"
        
        # Проверить текущую локацию агента
        my_location_belief = beliefs_base.get_belief(
            BeliefType.SELF,
            agent_id,
            "location"
        )
        my_location = my_location_belief.value if my_location_belief else "unknown"
        
        # Проверить локацию цели
        target_location_belief = beliefs_base.get_belief(
            BeliefType.AGENT,
            target,
            "location"
        )
        
        # Если цель в другой локации - сначала переместиться
        if target_location_belief and target_location_belief.value != my_location:
            steps.append(PlanStep(
                action_type=ActionType.MOVE,
                parameters={"destination": target_location_belief.value},
                description=f"Переместиться в {target_location_belief.value}",
                estimated_duration=2.0
            ))
        
        # Начать разговор
        steps.append(PlanStep(
            action_type=ActionType.COMMUNICATE,
            parameters={
                "target": target,
                "message_type": "greeting",
                "topic": desire.description
            },
            description=f"Начать разговор с {target}",
            estimated_duration=1.0
        ))
        
        # Обменяться информацией
        steps.append(PlanStep(
            action_type=ActionType.COMMUNICATE,
            parameters={
                "target": target,
                "message_type": "exchange"
            },
            description="Обменяться информацией",
            estimated_duration=2.0
        ))
        
        # Завершить разговор
        steps.append(PlanStep(
            action_type=ActionType.COMMUNICATE,
            parameters={
                "target": target,
                "message_type": "farewell"
            },
            description="Попрощаться",
            estimated_duration=0.5
        ))
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Успешный разговор с {target}"
        )
    
    def _create_movement_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для перемещения"""
        # Извлечь пункт назначения из описания
        destination = desire.context.get('destination', 'cafe')
        
        steps = [
            PlanStep(
                action_type=ActionType.MOVE,
                parameters={"destination": destination},
                description=f"Переместиться в {destination}",
                estimated_duration=2.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Находиться в {destination}"
        )
    
    def _create_search_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для поиска чего-то"""
        search_query = desire.context.get('search_query', desire.description)
        
        steps = [
            PlanStep(
                action_type=ActionType.SEARCH,
                parameters={"query": search_query},
                description=f"Искать: {search_query}",
                estimated_duration=3.0
            ),
            PlanStep(
                action_type=ActionType.OBSERVE,
                parameters={},
                description="Изучить результаты поиска",
                estimated_duration=2.0
            ),
            PlanStep(
                action_type=ActionType.THINK,
                parameters={"topic": search_query},
                description="Оценить найденное",
                estimated_duration=1.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome="Найти искомое"
        )
    
    def _create_learning_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для изучения чего-то"""
        topic = desire.context.get('topic', 'general knowledge')
        
        steps = [
            PlanStep(
                action_type=ActionType.MOVE,
                parameters={"destination": "library"},
                description="Пойти в библиотеку",
                estimated_duration=2.0
            ),
            PlanStep(
                action_type=ActionType.SEARCH,
                parameters={"query": topic},
                description=f"Найти материалы по теме: {topic}",
                estimated_duration=2.0
            ),
            PlanStep(
                action_type=ActionType.OBSERVE,
                parameters={"subject": topic},
                description="Изучить материал",
                estimated_duration=4.0
            ),
            PlanStep(
                action_type=ActionType.THINK,
                parameters={"topic": topic},
                description="Обдумать полученную информацию",
                estimated_duration=2.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Получить знания по теме: {topic}"
        )
    
    def _create_help_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для помощи кому-то"""
        target = desire.context.get('target_agent', 'someone')
        
        steps = [
            PlanStep(
                action_type=ActionType.COMMUNICATE,
                parameters={
                    "target": target,
                    "message_type": "offer_help"
                },
                description=f"Предложить помощь {target}",
                estimated_duration=1.0
            ),
            PlanStep(
                action_type=ActionType.WAIT,
                parameters={"for": "response"},
                description="Дождаться ответа",
                estimated_duration=1.0
            ),
            PlanStep(
                action_type=ActionType.HELP,
                parameters={"target": target},
                description="Оказать помощь",
                estimated_duration=3.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Помочь {target}"
        )
    
    def _create_acquisition_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """План для получения чего-то"""
        item = desire.context.get('item', 'resource')
        
        steps = [
            PlanStep(
                action_type=ActionType.SEARCH,
                parameters={"query": item},
                description=f"Найти {item}",
                estimated_duration=2.0
            ),
            PlanStep(
                action_type=ActionType.ACQUIRE,
                parameters={"item": item},
                description=f"Получить {item}",
                estimated_duration=1.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome=f"Иметь {item}"
        )
    
    def _create_generic_plan(self, desire, beliefs_base, agent_id: str) -> Plan:
        """Общий план (fallback)"""
        steps = [
            PlanStep(
                action_type=ActionType.THINK,
                parameters={"topic": desire.description},
                description=f"Обдумать: {desire.description}",
                estimated_duration=1.0
            ),
            PlanStep(
                action_type=ActionType.OBSERVE,
                parameters={},
                description="Оценить ситуацию",
                estimated_duration=1.0
            )
        ]
        
        return Plan(
            goal=desire.description,
            steps=steps,
            expected_outcome="Достичь цели"
        )


# Utility функции

def create_simple_plan(goal: str, action_type: ActionType, **parameters) -> Plan:
    """Создать простой план из одного действия"""
    step = PlanStep(
        action_type=action_type,
        parameters=parameters,
        description=goal
    )
    
    return Plan(
        goal=goal,
        steps=[step],
        expected_outcome=goal
    )


def create_multi_step_plan(goal: str, steps: List[Dict[str, Any]]) -> Plan:
    """
    Создать план из нескольких шагов
    
    Args:
        goal: Описание цели
        steps: Список словарей с описанием шагов
            [
                {"action": ActionType.MOVE, "params": {...}, "desc": "..."},
                {"action": ActionType.COMMUNICATE, "params": {...}, "desc": "..."}
            ]
    """
    plan_steps = []
    
    for step_data in steps:
        plan_steps.append(PlanStep(
            action_type=step_data['action'],
            parameters=step_data.get('params', {}),
            description=step_data.get('desc', ''),
            estimated_duration=step_data.get('duration', 1.0)
        ))
    
    return Plan(
        goal=goal,
        steps=plan_steps,
        expected_outcome=goal
    )
