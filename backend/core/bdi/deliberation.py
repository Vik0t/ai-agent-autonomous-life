"""
Deliberation Cycle - Цикл обдумывания BDI

DeliberationCycle - главный класс, объединяющий все компоненты BDI.
Управляет полным циклом: восприятие → убеждения → желания → намерения → действия.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from .beliefs import BeliefBase, Belief, BeliefType
from .desires import Desire, DesireGenerator, DesireStatus
from .intentions import Intention, IntentionSelector, IntentionStatus, create_intention_from_desire
from .plans import Planner


class DeliberationCycle:
    """
    Полный цикл обдумывания (BDI Deliberation Cycle)
    
    Этот класс управляет процессом принятия решений агента:
    1. PERCEIVE - воспринять окружение
    2. UPDATE BELIEFS - обновить убеждения
    3. GENERATE DESIRES - сгенерировать желания
    4. SELECT INTENTION - выбрать намерение (deliberation)
    5. PLAN - создать план действий
    6. EXECUTE - выполнить действие
    
    Повторяется циклически.
    """
    
    def __init__(self, llm_interface=None):
        """
        Args:
            llm_interface: Опциональный LLM для продвинутого планирования
        """
        self.desire_generator = DesireGenerator()
        self.intention_selector = IntentionSelector()
        self.planner = Planner(llm_interface)
        self.llm = llm_interface
        
        # Статистика
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None
    
    def run_cycle(
        self,
        agent_id: str,
        beliefs: BeliefBase,
        desires: List[Desire],
        intentions: List[Intention],
        personality: Dict[str, float],
        emotions: Dict[str, float],
        perceptions: List[Dict[str, Any]],
        max_intentions: int = 3
    ) -> Dict[str, Any]:
        """
        Выполнить один полный цикл обдумывания
        
        Args:
            agent_id: ID агента
            beliefs: База убеждений агента
            desires: Текущие желания
            intentions: Текущие намерения
            personality: OCEAN traits
            emotions: Текущие эмоции
            perceptions: Новые восприятия из окружения
            max_intentions: Максимум одновременных намерений
        
        Returns:
            {
                "new_beliefs": List[Belief],
                "new_desires": List[Desire],
                "new_intention": Intention or None,
                "actions_to_execute": List[Dict],
                "updated_intentions": List[Intention],
                "cycle_info": Dict
            }
        """
        cycle_start = datetime.now()
        self.cycle_count += 1
        
        # ========================================
        # 1. PERCEPTION → BELIEF UPDATE
        # ========================================
        new_beliefs = []
        for perception in perceptions:
            updated = beliefs.update_from_perception(perception)
            new_beliefs.extend(updated)
        
        # Обновляем убеждение о себе (например, текущее эмоциональное состояние)
        self_belief_updates = self._update_self_beliefs(agent_id, beliefs, emotions)
        new_beliefs.extend(self_belief_updates)
        
        # ========================================
        # 2. DESIRE GENERATION
        # ========================================
        new_desires = self.desire_generator.generate_desires(
            personality=personality,
            emotions=emotions,
            beliefs_base=beliefs,
            current_desires=desires
        )
        
        # Добавляем новые желания к существующим
        desires.extend(new_desires)
        
        # Очищаем устаревшие желания
        self._cleanup_desires(desires)
        
        # ========================================
        # 3. RECONSIDER CURRENT INTENTIONS
        # ========================================
        # Проверяем, нужно ли пересмотреть текущие намерения
        if self.intention_selector.should_reconsider_intentions(intentions, perceptions):
            # Переупорядочиваем по приоритету
            intentions[:] = self.intention_selector.reorder_intentions(
                intentions,
                {'perceptions': perceptions, 'emotions': emotions}
            )
        
        # ========================================
        # 4. INTENTION SELECTION (DELIBERATION)
        # ========================================
        selected_desire = self.intention_selector.select_intention(
            desires=desires,
            current_intentions=intentions,
            beliefs_base=beliefs,
            max_intentions=max_intentions
        )
        
        new_intention = None
        if selected_desire:
            # ========================================
            # 5. PLANNING
            # ========================================
            plan = self.planner.create_plan(
                desire=selected_desire,
                beliefs_base=beliefs,
                agent_id=agent_id
            )
            
            # Создать намерение
            new_intention = create_intention_from_desire(selected_desire, plan)
            
            # Добавить к намерениям
            intentions.append(new_intention)
            
            # Отметить желание как преследуемое
            selected_desire.status = DesireStatus.PURSUED
        
        # ========================================
        # 6. EXECUTION
        # ========================================
        actions_to_execute = []
        
        # Получаем активные намерения
        active_intentions = [
            i for i in intentions
            if i.status == IntentionStatus.ACTIVE
        ]
        
        # Для каждого активного намерения получаем следующее действие
        for intention in active_intentions:
            current_action = intention.get_current_action()
            
            if current_action and not current_action.executed:
                actions_to_execute.append({
                    'intention_id': intention.id,
                    'action': current_action,
                    'step_index': intention.current_step
                })
        
        # ========================================
        # 7. CLEANUP
        # ========================================
        # Удаляем завершённые намерения (опционально, для управления памятью)
        self._cleanup_intentions(intentions)
        
        # Вычисляем время цикла
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        self.last_cycle_time = datetime.now()
        
        # ========================================
        # RETURN RESULTS
        # ========================================
        return {
            'new_beliefs': new_beliefs,
            'new_desires': new_desires,
            'new_intention': new_intention,
            'actions_to_execute': actions_to_execute,
            'updated_intentions': intentions,
            'cycle_info': {
                'cycle_number': self.cycle_count,
                'duration_seconds': cycle_duration,
                'timestamp': cycle_start.isoformat(),
                'active_intentions_count': len(active_intentions),
                'total_desires': len(desires),
                'total_beliefs': len(beliefs)
            }
        }
    
    def _update_self_beliefs(
        self,
        agent_id: str,
        beliefs: BeliefBase,
        emotions: Dict[str, float]
    ) -> List[Belief]:
        """Обновить убеждения агента о себе"""
        new_beliefs = []
        
        # Обновляем эмоциональное состояние
        for emotion_name, value in emotions.items():
            belief = Belief(
                type=BeliefType.SELF,
                subject=agent_id,
                key=f"emotion_{emotion_name}",
                value=value,
                confidence=1.0,
                source="introspection"
            )
            beliefs.add_belief(belief)
            new_beliefs.append(belief)
        
        # Можно добавить другие self-beliefs (энергия, состояние, etc.)
        
        return new_beliefs
    
    def _cleanup_desires(self, desires: List[Desire]) -> None:
        """Удалить старые/неактуальные желания"""
        # Удаляем достигнутые и оставленные желания старше 1 часа
        cutoff_time = datetime.now()
        
        to_remove = []
        for i, desire in enumerate(desires):
            # Удаляем истёкшие
            if desire.is_expired():
                to_remove.append(i)
                continue
            
            # Удаляем старые неактивные
            age_hours = (cutoff_time - desire.created_at).total_seconds() / 3600
            if age_hours > 24 and desire.status in [DesireStatus.ACHIEVED, DesireStatus.ABANDONED]:
                to_remove.append(i)
        
        # Удаляем в обратном порядке чтобы не сбить индексы
        for i in reversed(to_remove):
            desires.pop(i)
    
    def _cleanup_intentions(self, intentions: List[Intention]) -> None:
        """Удалить старые завершённые намерения"""
        cutoff_time = datetime.now()
        
        to_remove = []
        for i, intention in enumerate(intentions):
            if intention.completed_at:
                age_hours = (cutoff_time - intention.completed_at).total_seconds() / 3600
                
                # Удаляем завершённые старше 24 часов
                if age_hours > 24 and intention.status in [
                    IntentionStatus.COMPLETED,
                    IntentionStatus.FAILED,
                    IntentionStatus.ABANDONED
                ]:
                    to_remove.append(i)
        
        for i in reversed(to_remove):
            intentions.pop(i)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику работы deliberation cycle"""
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None
        }


class SimplifiedDeliberationCycle:
    """
    Упрощённый цикл обдумывания для быстрого тестирования
    
    Использует более простую логику без глубокого анализа.
    """
    
    def __init__(self):
        self.desire_generator = DesireGenerator()
        self.planner = Planner()
    
    def quick_decision(
        self,
        agent_id: str,
        current_situation: str,
        personality: Dict[str, float],
        emotions: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Быстрое принятие решения без полного BDI цикла
        
        Полезно для простых сценариев или тестирования.
        """
        # Создаём минимальную beliefs base
        beliefs = BeliefBase()
        
        # Генерируем одно желание на основе ситуации
        desire = Desire(
            description=current_situation,
            priority=0.7,
            urgency=0.6,
            motivation_type=self._infer_motivation(current_situation),
            source="situation",
            personality_alignment=0.7
        )
        
        # Создаём простой план
        plan = self.planner.create_plan(desire, beliefs, agent_id)
        
        return {
            'desire': desire,
            'plan': plan,
            'next_action': plan.steps[0] if plan.steps else None
        }
    
    def _infer_motivation(self, situation: str) -> Any:
        """Определить тип мотивации по ситуации"""
        from .desires import MotivationType
        
        situation_lower = situation.lower()
        
        if any(word in situation_lower for word in ['поговорить', 'общаться', 'друг']):
            return MotivationType.SOCIAL
        elif any(word in situation_lower for word in ['изучить', 'узнать', 'исследовать']):
            return MotivationType.CURIOSITY
        elif any(word in situation_lower for word in ['безопас', 'защит', 'спрят']):
            return MotivationType.SAFETY
        elif any(word in situation_lower for word in ['достич', 'выполн', 'завершить']):
            return MotivationType.ACHIEVEMENT
        else:
            return MotivationType.SOCIAL


# Utility функции для работы с циклом

def create_perception(
    perception_type: str,
    subject: str,
    data: Dict[str, Any],
    confidence: float = 0.9,
    importance: float = 0.5
) -> Dict[str, Any]:
    """
    Создать объект восприятия для передачи в deliberation cycle
    
    Args:
        perception_type: Тип восприятия ("observation", "communication", "event")
        subject: О ком/чём восприятие
        data: Данные восприятия
        confidence: Уверенность в восприятии
        importance: Важность восприятия
    
    Returns:
        Словарь восприятия
    """
    return {
        'type': perception_type,
        'subject': subject,
        'data': data,
        'confidence': confidence,
        'importance': importance,
        'timestamp': datetime.now().isoformat()
    }


def extract_actions_summary(deliberation_result: Dict[str, Any]) -> str:
    """
    Извлечь человеко-читаемое резюме действий из результата deliberation
    """
    actions = deliberation_result.get('actions_to_execute', [])
    
    if not actions:
        return "Нет действий для выполнения"
    
    summary_lines = []
    for i, action_info in enumerate(actions, 1):
        action = action_info['action']
        summary_lines.append(f"{i}. {action.description}")
    
    return "\n".join(summary_lines)
