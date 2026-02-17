# backend/agent.py  [REFACTOR v4 — Social Battery]
"""
Изменения v4:
1. Добавлен атрибут social_battery (0.0–1.0, дефолт 1.0).
2. Механика расхода батарейки при каждом отправленном сообщении:
   cost = (1.1 - extraversion) * 0.15
3. notify_solo_action восстанавливает батарейку на +0.05.
4. social_battery передаётся в deliberation_cycle.run_cycle и отображается в to_dict().
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
    def get_emotion_label(self) -> str:
        emotions = {
            "happy": self.happiness,
            "sad": self.sadness,
            "angry": self.anger,
            "fearful": self.fear,
            "surprised": self.surprise,
            "disgusted": self.disgust
        }
        # Получаем эмоцию с наибольшим значением
        dominant_emotion = max(emotions, key=emotions.get)
        return dominant_emotion


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

        # ── Social Battery ──────────────────────────────────────────────
        # Заряд от 0.0 (опустошён) до 1.0 (полный).
        # Расходуется при отправке каждого сообщения.
        # Восстанавливается при несоциальных (solo) действиях.
        self.social_battery: float = 1.0

    def _initialize_self_beliefs(self):
        self.beliefs.add_belief(create_self_belief(self.id, "name", self.name))
        self.beliefs.add_belief(create_self_belief(self.id, "location", "Центральная площадь"))

    # ── Social Battery helpers ──────────────────────────────────────────

    def _drain_social_battery(self):
        """
        Уменьшает заряд после отправки сообщения.
        Интроверты (низкая extraversion) тратят больше энергии.
        cost = (1.1 - extraversion) * 0.15
        """
        extraversion = self.personality.extraversion
        cost = (1.1 - extraversion) * 0.15
        self.social_battery = max(0.0, self.social_battery - cost)
        print(f"🔋 [{self.id}] Battery drain: -{cost:.3f} → {self.social_battery:.2f}")

    def _restore_social_battery(self, amount: float = 0.05):
        """Восстанавливает заряд после несоциального (solo) действия."""
        old = self.social_battery
        self.social_battery = min(1.0, self.social_battery + amount)
        if self.social_battery > old:
            print(f"🔋 [{self.id}] Battery restore: +{amount:.3f} → {self.social_battery:.2f}")

    # ── Core BDI loop ───────────────────────────────────────────────────

    def think(
        self,
        perceptions: List[Dict[str, Any]],
        active_conversation_partners: List[str] = None
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
            active_conversation_partners=active_conversation_partners or [],
            social_battery=self.social_battery          # ← НОВЫЙ параметр
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

        SOCIAL_SOURCES = {
            'incoming_message', 'personality_extraversion', 'personality_agreeableness',
            'emotion_happiness', 'emotion_sadness'
        }

        # Расход батарейки при каждой отправке сообщения
        if step_object.action_type in (ActionType.SEND_MESSAGE, ActionType.RESPOND_TO_MESSAGE):
            self._drain_social_battery()

        for intention in self.intentions:
            if intention.id == intention_id:
                intention.update_progress({"success": success, "message": message})

                if intention.is_completed():
                    intention.complete()

                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.status = DesireStatus.ACHIEVED

                            if desire.source not in SOCIAL_SOURCES:
                                self.deliberation_cycle.notify_solo_action(
                                    desire.source or 'idle_drive'
                                )
                            break
                break

    def notify_conversation_ended(self, partner_id: str):
        """
        Уведомить BDI о завершении разговора с partner_id.
        Активирует кулдаун в DesireGenerator.
        """
        self.deliberation_cycle.notify_conversation_ended(partner_id)

    def notify_solo_action(self, action_type: str):
        """
        Social Satiety: уведомить BDI что выполнено несоциальное действие.
        После MIN_SOLO_ACTIONS действий снимает блок на новые социальные желания.
        Дополнительно восстанавливает social_battery на +0.05.
        """
        self.deliberation_cycle.notify_solo_action(action_type)
        # Восстановление батарейки за несоциальное действие
        self._restore_social_battery(0.05)

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
            "memories": [],
            "social_battery": round(self.social_battery, 3)   # ← НОВОЕ поле
        }