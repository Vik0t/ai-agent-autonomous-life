# backend/agent.py  [REFACTOR v3]
"""
Исправления:
1. think() принимает active_conversation_partners и передаёт в deliberation_cycle
2. confirm_action_execution при END_CONVERSATION уведомляет deliberation_cycle
   чтобы desire_generator поставил кулдаун и не создавал новые respond_desires
"""

from typing import Dict, List, Any
from pydantic import BaseModel
from core.bdi import (
    BeliefBase, Desire, Intention, DeliberationCycle,
    create_self_belief, BeliefType, PlanStep, ActionType, IntentionStatus, DesireStatus
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
    def __init__(self, agent_id: str, name: str, avatar: str,
                 personality_data: Dict, llm_interface=None):
        self.id = agent_id
        self.name = name
        self.avatar = avatar
        self.personality = Personality(**personality_data)
        self.emotions = Emotion()
        self.beliefs = BeliefBase()
        self.desires: List[Desire] = []
        self.intentions: List[Intention] = []
        self.deliberation_cycle = DeliberationCycle(llm_interface=llm_interface)
        self._initialize_self_beliefs()
        self.current_plan = "Ожидание..."

    def _initialize_self_beliefs(self):
        self.beliefs.add_belief(create_self_belief(self.id, "name", self.name))
        self.beliefs.add_belief(create_self_belief(self.id, "location", "Центральная площадь"))

    def think(
        self,
        perceptions: List[Dict[str, Any]],
        active_conversation_partners: List[str] = None  # FIX: агенты в активном диалоге
    ) -> List[Dict]:
        result = self.deliberation_cycle.run_cycle(
            agent_id=self.id,
            beliefs=self.beliefs,
            desires=self.desires,
            intentions=self.intentions,
            personality=self.personality.dict(),
            emotions=self.emotions.dict(),
            perceptions=perceptions,
            max_intentions=1,
            active_conversation_partners=active_conversation_partners or []
        )

        if result.get('new_intention'):
            self.current_plan = result['new_intention'].desire_description
        elif not any(i.status == IntentionStatus.ACTIVE for i in self.intentions):
            self.current_plan = "Обдумывание..."

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

    def confirm_action_execution(self, intention_id: str, step_object: PlanStep,
                                 success: bool, message: str):
        step_object.executed = True
        step_object.success = success

        for intention in self.intentions:
            if intention.id == intention_id:
                intention.update_progress({"success": success, "message": message})

                if intention.is_completed():
                    intention.complete()

                    # Помечаем desire как ACHIEVED
                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.status = DesireStatus.ACHIEVED
                            break
                break

    def notify_conversation_ended(self, partner_id: str):
        """
        FIX: Уведомить BDI о завершении разговора с partner_id.
        Это активирует кулдаун в DesireGenerator — не создавать respond_desires 30 сек.
        """
        self.deliberation_cycle.notify_conversation_ended(partner_id)

    def to_dict(self):
        loc_belief = self.beliefs.get_belief(BeliefType.SELF, self.id, "location")
        current_location = loc_belief.value if loc_belief else "Неизвестно"

        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar,
            "personality": self.personality.dict(),
            "emotions": self.emotions.dict(),
            "current_plan": self.current_plan,
            "location": current_location,
            "status": "active",
            "memory_count": len(self.beliefs.beliefs),
            "relationships": {},
            "memories": []
        }