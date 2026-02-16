from pydantic import BaseModel
from typing import Dict, List
import numpy as np

class Personality(BaseModel):
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float

class Emotion(BaseModel):
    happiness: float
    sadness: float
    anger: float
    fear: float
    surprise: float
    disgust: float

class Memory(BaseModel):
    id: str
    content: str
    timestamp: float
    importance: float

class Relationship(BaseModel):
    agent_id: str
    affinity: float
    familiarity: float
    last_interaction: float

class Agent:
    def __init__(self, agent_id: str, name: str):
        self.id = agent_id
        self.name = name
        self.personality = Personality(
            openness=0.5,
            conscientiousness=0.5,
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5
        )
        self.emotions = Emotion(
            happiness=0.5,
            sadness=0.0,
            anger=0.0,
            fear=0.0,
            surprise=0.0,
            disgust=0.0
        )
        self.memories: List[Memory] = []
        self.relationships: Dict[str, Relationship] = {}
        self.current_plan = ""
        
    def update_emotions(self, event: str):
        # Simple emotion update based on event
        if "happy" in event.lower():
            self.emotions.happiness = min(1.0, self.emotions.happiness + 0.1)
        elif "sad" in event.lower():
            self.emotions.sadness = min(1.0, self.emotions.sadness + 0.1)
        elif "angry" in event.lower():
            self.emotions.anger = min(1.0, self.emotions.anger + 0.1)
            
    def add_memory(self, content: str, importance: float = 0.5):
        memory = Memory(
            id=str(len(self.memories)),
            content=content,
            timestamp=len(self.memories),
            importance=importance
        )
        self.memories.append(memory)
        
    def get_relationship(self, agent_id: str) -> Relationship:
        if agent_id not in self.relationships:
            self.relationships[agent_id] = Relationship(
                agent_id=agent_id,
                affinity=0.0,
                familiarity=0.0,
                last_interaction=0.0
            )
        return self.relationships[agent_id]
        
    def update_relationship(self, agent_id: str, affinity_change: float, familiarity_change: float):
        relationship = self.get_relationship(agent_id)
        relationship.affinity = np.clip(relationship.affinity + affinity_change, -1.0, 1.0)
        relationship.familiarity = np.clip(relationship.familiarity + familiarity_change, 0.0, 1.0)
        relationship.last_interaction = len(self.memories)