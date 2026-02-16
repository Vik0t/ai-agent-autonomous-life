# backend/core/bdi/deliberation.py
"""
Deliberation Cycle - Цикл обдумывания BDI
Исправленная версия: агрессивная очистка завершенных намерений для симулятора.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from .beliefs import BeliefBase, Belief, BeliefType
from .desires import Desire, DesireGenerator, DesireStatus
from .intentions import Intention, IntentionSelector, IntentionStatus, create_intention_from_desire
from .plans import Planner


class DeliberationCycle:
    def __init__(self, llm_interface=None):
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
        max_intentions: int = 1  # Для симуляции лучше 1 активное за раз
    ) -> Dict[str, Any]:
        cycle_start = datetime.now()
        self.cycle_count += 1
        
        # ========================================
        # 1. СНАЧАЛА ОЧИСТКА (Fix: Агенты не застревают)
        # ========================================
        self._cleanup_desires(desires)
        self._cleanup_intentions(intentions)

        # ========================================
        # 2. PERCEPTION → BELIEF UPDATE
        # ========================================
        new_beliefs = []
        for perception in perceptions:
            updated = beliefs.update_from_perception(perception)
            new_beliefs.extend(updated)
        
        self_belief_updates = self._update_self_beliefs(agent_id, beliefs, emotions)
        new_beliefs.extend(self_belief_updates)
        
        # ========================================
        # 3. DESIRE GENERATION
        # ========================================
        new_desires = self.desire_generator.generate_desires(
            personality=personality,
            emotions=emotions,
            beliefs_base=beliefs,
            current_desires=desires
        )
        desires.extend(new_desires)
        
        # ========================================
        # 4. INTENTION SELECTION (DELIBERATION)
        # ========================================
        # Если нет активных намерений - выбираем новое
        new_intention = None
        has_active = any(i.status == IntentionStatus.ACTIVE for i in intentions)
        
        if not has_active:
            selected_desire = self.intention_selector.select_intention(
                desires=desires,
                current_intentions=intentions,
                beliefs_base=beliefs,
                max_intentions=max_intentions
            )
            
            if selected_desire:
                plan = self.planner.create_plan(
                    desire=selected_desire,
                    beliefs_base=beliefs,
                    agent_id=agent_id
                )
                new_intention = create_intention_from_desire(selected_desire, plan)
                intentions.append(new_intention)
                selected_desire.status = DesireStatus.PURSUED
        
        # ========================================
        # 5. EXECUTION
        # ========================================
        actions_to_execute = []
        active_intentions = [i for i in intentions if i.status == IntentionStatus.ACTIVE]
        
        for intention in active_intentions:
            current_action = intention.get_current_action()
            if current_action and not current_action.executed:
                actions_to_execute.append({
                    'intention_id': intention.id,
                    'action': current_action,
                    'step_index': intention.current_step
                })
        
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        self.last_cycle_time = datetime.now()
        
        return {
            'new_beliefs': new_beliefs,
            'new_desires': new_desires,
            'new_intention': new_intention,
            'actions_to_execute': actions_to_execute,
            'updated_intentions': intentions,
            'cycle_info': {
                'cycle_number': self.cycle_count,
                'duration_seconds': cycle_duration,
                'active_intentions_count': len(active_intentions),
                'total_desires': len(desires),
                'total_beliefs': len(beliefs)
            }
        }
    
    def _update_self_beliefs(self, agent_id: str, beliefs: BeliefBase, emotions: Dict[str, float]) -> List[Belief]:
        new_beliefs = []
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
        return new_beliefs
    
    def _cleanup_desires(self, desires: List[Desire]) -> None:
        """Fix: Мгновенное удаление завершенных желаний для освобождения места в BDI"""
        to_remove = []
        for i, desire in enumerate(desires):
            if desire.status in [DesireStatus.ACHIEVED, DesireStatus.ABANDONED] or desire.is_expired():
                to_remove.append(i)
        
        for i in reversed(to_remove):
            desires.pop(i)
    
    def _cleanup_intentions(self, intentions: List[Intention]) -> None:
        """Fix: Мгновенное удаление завершенных намерений"""
        to_remove = []
        for i, intention in enumerate(intentions):
            if intention.status in [IntentionStatus.COMPLETED, IntentionStatus.FAILED, IntentionStatus.ABANDONED]:
                to_remove.append(i)
        
        for i in reversed(to_remove):
            intentions.pop(i)

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None
        }

def create_perception(perception_type: str, subject: str, data: Dict[str, Any], confidence: float = 0.9, importance: float = 0.5) -> Dict[str, Any]:
    return {
        'type': perception_type,
        'subject': subject,
        'data': data,
        'confidence': confidence,
        'importance': importance,
        'timestamp': datetime.now().isoformat()
    }

def extract_actions_summary(deliberation_result: Dict[str, Any]) -> str:
    actions = deliberation_result.get('actions_to_execute', [])
    if not actions: return "Нет действий"
    return "\n".join([f"{i+1}. {a['action'].description}" for i, a in enumerate(actions)])