"""
Intention System - Система намерений

Intention (намерение) - это выбранная цель с конкретным планом действий.
IntentionSelector - выбирает, какое желание превратить в намерение.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class IntentionStatus(Enum):
    """Статус намерения"""
    ACTIVE = "active"           # Активно выполняется
    SUSPENDED = "suspended"     # Приостановлено (временно)
    COMPLETED = "completed"     # Успешно выполнено
    FAILED = "failed"           # Провалено
    ABANDONED = "abandoned"     # Оставлено


@dataclass
class Intention:
    """
    Активное намерение - выбранная цель с планом
    
    Представляет собой commitment агента к достижению конкретной цели.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    desire_id: str = ""                     # ID желания
    desire_description: str = ""            # Копия описания для удобства
    plan: Any = None                              # Plan object
    status: IntentionStatus = IntentionStatus.ACTIVE
    priority: float = 0.5
    
    # Прогресс выполнения
    current_step: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    
    # Временные метки
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    
    # Контекст выполнения
    context: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[str] = field(default_factory=list)
    
    # Метрики
    actual_duration: float = 0.0
    retry_count: int = 0

    # Прерываемость: рутинные действия (think/move/observe) можно приостановить
    # если пришло срочное социальное событие (incoming_message).
    # Социальные намерения (respond, initiate) — НЕ прерываемы.
    interruptible: bool = True
    
    def update_progress(self, step_result: Dict[str, Any]) -> None:
        """
        Обновить прогресс выполнения плана
        
        Args:
            step_result: Результат выполнения шага
                {
                    "success": True/False,
                    "reason": "...",
                    "data": {...}
                }
        """
        self.last_action_at = datetime.now()
        
        if step_result.get("success", False):
            self.current_step += 1
            self.steps_completed += 1
            self.execution_log.append(
                f"✓ Step {self.current_step}: {step_result.get('message', 'Success')}"
            )
        else:
            self.steps_failed += 1
            failure_reason = step_result.get("reason", "unknown")
            self.execution_log.append(
                f"✗ Step {self.current_step}: Failed - {failure_reason}"
            )
            
            # Проверяем, нужно ли повторить или отказаться
            if self.retry_count < 3:
                self.retry_count += 1
                self.execution_log.append(f"  Retry attempt {self.retry_count}")
            else:
                self.status = IntentionStatus.FAILED
                self.completed_at = datetime.now()
    
    def is_completed(self) -> bool:
        """Проверить, завершено ли намерение"""
        if self.plan is None:
            return False
        return self.plan.is_complete(self.current_step)
    
    def get_progress_percentage(self) -> float:
        """Получить прогресс в процентах (0-100)"""
        if self.plan is None or not self.plan.steps:
            return 0.0
        return (self.current_step / len(self.plan.steps)) * 100
    
    def get_current_action(self) -> Optional[Any]:
        """Получить текущее действие (PlanStep)"""
        if self.plan is None:
            return None
        return self.plan.get_next_step(self.current_step)
    
    def suspend(self, reason: str = "") -> None:
        """Приостановить выполнение"""
        self.status = IntentionStatus.SUSPENDED
        self.execution_log.append(f"⏸ Suspended: {reason}")
    
    def resume(self) -> None:
        """Возобновить выполнение"""
        if self.status == IntentionStatus.SUSPENDED:
            self.status = IntentionStatus.ACTIVE
            self.execution_log.append("▶ Resumed")
    
    def abandon(self, reason: str = "") -> None:
        """Оставить намерение"""
        self.status = IntentionStatus.ABANDONED
        self.completed_at = datetime.now()
        self.execution_log.append(f"⛔ Abandoned: {reason}")
    
    def complete(self) -> None:
        """Отметить как выполненное"""
        self.status = IntentionStatus.COMPLETED
        self.completed_at = datetime.now()
        self.actual_duration = (self.completed_at - self.started_at).total_seconds()
        self.execution_log.append("✓ Completed successfully")
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'desire_id': self.desire_id,
            'desire_description': self.desire_description,
            'plan': self.plan.to_dict() if self.plan else None,
            'status': self.status.value,
            'priority': self.priority,
            'current_step': self.current_step,
            'steps_completed': self.steps_completed,
            'steps_failed': self.steps_failed,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_action_at': self.last_action_at.isoformat() if self.last_action_at else None,
            'context': self.context,
            'execution_log': self.execution_log,
            'actual_duration': self.actual_duration,
            'retry_count': self.retry_count,
            'interruptible': self.interruptible
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Intention':
        """Десериализация из словаря"""
        from .plans import Plan
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            desire_id=data.get('desire_id', ''),
            desire_description=data.get('desire_description', ''),
            plan=Plan.from_dict(data['plan']) if data.get('plan') else None,
            status=IntentionStatus(data.get('status', 'active')),
            priority=data.get('priority', 0.5),
            current_step=data.get('current_step', 0),
            steps_completed=data.get('steps_completed', 0),
            steps_failed=data.get('steps_failed', 0),
            started_at=datetime.fromisoformat(data['started_at']) if 'started_at' in data else datetime.now(),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            last_action_at=datetime.fromisoformat(data['last_action_at']) if data.get('last_action_at') else None,
            context=data.get('context', {}),
            execution_log=data.get('execution_log', []),
            actual_duration=data.get('actual_duration', 0.0),
            retry_count=data.get('retry_count', 0),
            interruptible=data.get('interruptible', True)
        )
    
    def __repr__(self):
        progress = self.get_progress_percentage()
        return f"Intention({self.desire_description[:30]}..., {progress:.0f}%, {self.status.value})"


class IntentionSelector:
    """
    Выбирает, какое желание превратить в намерение
    
    Процесс deliberation - обдумывание того, какую цель преследовать.
    """
    
    def __init__(self):
        self.selection_strategy = "utility"  # "utility", "priority", "urgency", "random"
    
    def select_intention(
        self,
        desires: List,
        current_intentions: List[Intention],
        beliefs_base,
        max_intentions: int = 3,
        agent_resources: Optional[Dict[str, float]] = None
    ) -> Optional[Any]:
        """
        Выбрать желание для превращения в намерение (deliberation)
        
        Args:
            desires: Список желаний (Desire objects)
            current_intentions: Активные намерения
            beliefs_base: База убеждений
            max_intentions: Максимум одновременных намерений
            agent_resources: Ресурсы агента (энергия, время, etc.)
        
        Returns:
            Выбранное желание или None
        """
        # Импорт здесь чтобы избежать циклических зависимостей
        from .desires import DesireStatus
        
        # Проверка ограничений
        active_intentions = [
            i for i in current_intentions 
            if i.status == IntentionStatus.ACTIVE
        ]
        
        if len(active_intentions) >= max_intentions:
            # Слишком много активных намерений
            return None
        
        # Фильтруем кандидатов
        candidate_desires = []
        
        for desire in desires:
            # Только активные и не преследуемые желания
            if desire.status != DesireStatus.ACTIVE:
                continue
            
            # Проверяем, что это желание не уже в намерениях
            already_pursued = any(
                i.desire_id == desire.id and i.status == IntentionStatus.ACTIVE
                for i in current_intentions
            )
            if already_pursued:
                continue
            
            # Проверяем достижимость
            if not desire.is_achievable(beliefs_base.query):
                continue
            
            # Проверяем истечение срока
            if desire.is_expired():
                continue
            
            candidate_desires.append(desire)
        
        if not candidate_desires:
            return None
        
        # Выбираем лучшее по стратегии
        if self.selection_strategy == "utility":
            return self._select_by_utility(candidate_desires)
        elif self.selection_strategy == "priority":
            return self._select_by_priority(candidate_desires)
        elif self.selection_strategy == "urgency":
            return self._select_by_urgency(candidate_desires)
        else:
            # random
            import random
            return random.choice(candidate_desires)
    
    def _select_by_utility(self, desires: List) -> Any:
        """Выбрать желание с максимальной полезностью"""
        return max(desires, key=lambda d: d.calculate_utility())
    
    def _select_by_priority(self, desires: List) -> Any:
        """Выбрать желание с максимальным приоритетом"""
        return max(desires, key=lambda d: d.priority)
    
    def _select_by_urgency(self, desires: List) -> Any:
        """Выбрать самое срочное желание"""
        return max(desires, key=lambda d: d.urgency)

    def interrupt_for_social(
        self,
        intentions: List[Intention],
        urgent_desire
    ) -> List[Intention]:
        """
        Реактивное прерывание: если пришло срочное социальное желание
        (источник incoming_message), приостановить все прерываемые намерения.

        Возвращает список приостановленных намерений (для логирования).
        """
        from .desires import MotivationType
        suspended = []
        for intention in intentions:
            if (intention.status == IntentionStatus.ACTIVE
                    and intention.interruptible):
                intention.suspend(
                    reason=f"Прерван срочным: {urgent_desire.description[:40]}"
                )
                suspended.append(intention)
        return suspended
    
    def should_reconsider_intentions(
        self,
        current_intentions: List[Intention],
        new_perceptions: List[Dict[str, Any]]
    ) -> bool:
        """
        Определить, нужно ли пересмотреть текущие намерения
        
        Args:
            current_intentions: Активные намерения
            new_perceptions: Новые восприятия
        
        Returns:
            True если нужно пересмотреть
        """
        # Проверяем наличие важных событий
        for perception in new_perceptions:
            if perception.get('importance', 0) > 0.8:
                return True
            
            # Проверяем угрозы
            if perception.get('type') == 'threat':
                return True
        
        # Проверяем заблокированные намерения
        blocked_count = sum(
            1 for i in current_intentions
            if i.status == IntentionStatus.SUSPENDED or i.steps_failed > 2
        )
        
        if blocked_count >= len(current_intentions) / 2:
            return True
        
        return False
    
    def reorder_intentions(
        self,
        intentions: List[Intention],
        new_context: Dict[str, Any]
    ) -> List[Intention]:
        """
        Переупорядочить намерения по приоритету
        
        Args:
            intentions: Список намерений
            new_context: Новый контекст (события, изменения)
        
        Returns:
            Отсортированный список намерений
        """
        # Сортируем по приоритету и статусу
        def sort_key(intention: Intention):
            # Активные намерения выше
            status_weight = 1.0 if intention.status == IntentionStatus.ACTIVE else 0.5
            
            # Близкие к завершению выше
            progress_weight = intention.get_progress_percentage() / 100
            
            # Приоритет
            priority = intention.priority
            
            return status_weight * priority * (1 + progress_weight * 0.5)
        
        return sorted(intentions, key=sort_key, reverse=True)


# Utility функции

def create_intention_from_desire(desire, plan) -> Intention:
    """Создать намерение из желания и плана.

    Правило прерываемости (interruptible):
      - Рутинные (think, move, observe, idle_drive, llm_fallback) → прерываемые
      - Любое социальное намерение (ответ, инициация, user) → НЕ прерываемые
    """
    SOCIAL_SOURCES = {
        'incoming_message', 'user_message', 'wrap_up', 'deep_work_reject',
        'personality_extraversion', 'personality_agreeableness',
        'emotion_happiness', 'emotion_sadness',
    }
    source = getattr(desire, 'source', '')
    mtype = getattr(desire, 'motivation_type', None)

    # Любое SOCIAL / world_event / user желание — не прерываем
    try:
        from .desires import MotivationType
    except ImportError:
        try:
            from desires import MotivationType
        except ImportError:
            MotivationType = None

    is_social_source = source in SOCIAL_SOURCES
    is_social_type = (
        MotivationType is not None
        and mtype in (MotivationType.SOCIAL, MotivationType.WORLD_EVENT)
    )
    # LLM-желание поговорить с конкретным target_agent → не прерываем
    has_target = bool((getattr(desire, 'context', {}) or {}).get('target_agent'))
    is_llm_social = (source == 'llm_dynamic' and is_social_type and has_target)

    interruptible = not (is_social_source or is_social_type or is_llm_social)

    return Intention(
        desire_id=desire.id,
        desire_description=desire.description,
        plan=plan,
        priority=desire.priority,
        status=IntentionStatus.ACTIVE,
        context=desire.context.copy() if hasattr(desire, 'context') else {},
        interruptible=interruptible
    )


def get_active_intentions(intentions: List[Intention]) -> List[Intention]:
    """Получить только активные намерения"""
    return [
        i for i in intentions
        if i.status == IntentionStatus.ACTIVE
    ]


def get_completed_intentions(intentions: List[Intention]) -> List[Intention]:
    """Получить завершённые намерения"""
    return [
        i for i in intentions
        if i.status == IntentionStatus.COMPLETED
    ]


def get_failed_intentions(intentions: List[Intention]) -> List[Intention]:
    """Получить проваленные намерения"""
    return [
        i for i in intentions
        if i.status == IntentionStatus.FAILED
    ]