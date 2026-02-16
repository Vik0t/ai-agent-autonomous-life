# backend/agent.py
from typing import Dict, List, Any
from pydantic import BaseModel
from core.bdi import (
    BeliefBase, Desire, Intention, DeliberationCycle,
    create_self_belief, BeliefType, PlanStep, ActionType
)

class Personality(BaseModel):
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float

class Emotion(BaseModel):
    happiness: float = 0.5
    sadness: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0

class Agent:
    def __init__(self, agent_id: str, name: str, avatar: str, personality_data: Dict, llm_interface=None):
        self.id = agent_id
        self.name = name
        self.avatar = avatar
        
        # Конвертация в модель Pydantic
        self.personality = Personality(**personality_data)
        self.emotions = Emotion()
        
        self.beliefs = BeliefBase()
        self.desires: List[Desire] = []
        self.intentions: List[Intention] = []
        
        self.deliberation_cycle = DeliberationCycle(llm_interface=llm_interface)
        self._initialize_self_beliefs()
        self.current_plan = "Инициализация..."

    def _initialize_self_beliefs(self):
        from core.bdi.beliefs import create_self_belief
        self.beliefs.add_belief(create_self_belief(self.id, "name", self.name))
        self.beliefs.add_belief(create_self_belief(self.id, "location", "Центральная площадь"))

    def think(self, perceptions: List[Dict[str, Any]]) -> List[Dict]:
        result = self.deliberation_cycle.run_cycle(
            agent_id=self.id,
            beliefs=self.beliefs,
            desires=self.desires,
            intentions=self.intentions,
            personality=self.personality.dict(),
            emotions=self.emotions.dict(),
            perceptions=perceptions,
            max_intentions=2
        )
        
        if result.get('new_intention'):
            self.current_plan = result['new_intention'].desire_description

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

    def confirm_action_execution(self, intention_id: str, step_object: PlanStep, success: bool, message: str):
        step_object.executed = True
        step_object.success = success
        step_object.result = {"message": message}
        
        # Если действие было перемещением, BDI уже обновил убеждение, 
        # но мы можем залогировать результат
        for intention in self.intentions:
            if intention.id == intention_id:
                intention.update_progress({"success": success, "message": message})
                break

    def to_dict(self):
        """Безопасная сериализация для фронтенда"""
        # Достаем локацию из убеждений (Belief System)
        loc_belief = self.beliefs.get_belief(BeliefType.SELF, self.id, "location")
        current_location = loc_belief.value if loc_belief else "Неизвестно"

        return {
            "id": str(self.id),
            "name": str(self.name),
            "avatar": str(self.avatar),
            "personality": self.personality.dict(),
            "emotions": self.emotions.dict(),
            "current_plan": str(self.current_plan),
            "location": str(current_location),
            "status": "active"
        }