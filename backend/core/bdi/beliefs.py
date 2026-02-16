"""
Belief System - Система убеждений агента

Belief (убеждение) - это то, что агент знает или думает, что знает о мире.
BeliefBase - база знаний агента, организованная для быстрого доступа.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class BeliefType(Enum):
    """Типы убеждений агента"""
    SELF = "self"           # Убеждения о себе (местоположение, состояние, ресурсы)
    AGENT = "agent"         # Убеждения о других агентах
    WORLD = "world"         # Убеждения о мире/окружении
    EVENT = "event"         # Убеждения о событиях
    SOCIAL = "social"       # Социальные убеждения (нормы, репутация)


@dataclass
class Belief:
    """
    Одно убеждение агента
    
    Примеры:
        Belief(type=SELF, subject="agent_1", key="location", value="park")
        Belief(type=AGENT, subject="agent_2", key="mood", value="happy")
        Belief(type=WORLD, subject="weather", key="condition", value="sunny")
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: BeliefType = BeliefType.WORLD
    subject: str = ""           # О ком/чём убеждение (id агента, название объекта)
    key: str = ""               # Атрибут (location, mood, weather, etc.)
    value: Any = None           # Значение
    confidence: float = 1.0     # Уверенность в убеждении (0.0 - 1.0)
    source: str = "observation" # Источник: observation, communication, inference
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __repr__(self):
        return f"Belief({self.type.value}:{self.subject}.{self.key}={self.value} @{self.confidence:.2f})"
    
    def __hash__(self):
        """Для использования в множествах"""
        return hash(f"{self.type.value}:{self.subject}:{self.key}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'type': self.type.value,
            'subject': self.subject,
            'key': self.key,
            'value': self.value,
            'confidence': self.confidence,
            'source': self.source,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Belief':
        """Десериализация из словаря"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            type=BeliefType(data['type']),
            subject=data['subject'],
            key=data['key'],
            value=data['value'],
            confidence=data.get('confidence', 1.0),
            source=data.get('source', 'observation'),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
        )


class BeliefBase:
    """
    База знаний агента - всё, что агент знает о мире
    
    Организована по категориям для быстрого доступа.
    Поддерживает обновление, поиск и консистентность убеждений.
    """
    
    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}
        self._index_by_type: Dict[BeliefType, List[str]] = {
            belief_type: [] for belief_type in BeliefType
        }
        self._index_by_subject: Dict[str, List[str]] = {}
        
    def _generate_key(self, belief: Belief) -> str:
        """Генерация ключа для убеждения"""
        return f"{belief.type.value}:{belief.subject}:{belief.key}"
    
    def add_belief(self, belief: Belief) -> None:
        """
        Добавить или обновить убеждение
        
        Если убеждение уже существует, обновляет его с учётом confidence.
        """
        key = self._generate_key(belief)
        
        # Если убеждение уже существует
        if key in self.beliefs:
            old_belief = self.beliefs[key]
            
            # Обновляем значение и усредняем уверенность
            if old_belief.value != belief.value:
                # Если новое убеждение более уверенное, принимаем его
                if belief.confidence >= old_belief.confidence:
                    old_belief.value = belief.value
                    old_belief.confidence = belief.confidence
                    old_belief.timestamp = belief.timestamp
                    old_belief.source = belief.source
                else:
                    # Усредняем уверенность
                    total_conf = old_belief.confidence + belief.confidence
                    old_belief.confidence = total_conf / 2
            else:
                # То же значение - усиливаем уверенность
                old_belief.confidence = min(1.0, old_belief.confidence + 0.1)
                old_belief.timestamp = belief.timestamp
        else:
            # Новое убеждение
            self.beliefs[key] = belief
            
            # Обновляем индексы
            if belief.type not in self._index_by_type:
                self._index_by_type[belief.type] = []
            self._index_by_type[belief.type].append(key)
            
            if belief.subject not in self._index_by_subject:
                self._index_by_subject[belief.subject] = []
            self._index_by_subject[belief.subject].append(key)
    
    def remove_belief(self, belief_type: BeliefType, subject: str, key: str) -> bool:
        """Удалить убеждение"""
        lookup_key = f"{belief_type.value}:{subject}:{key}"
        
        if lookup_key in self.beliefs:
            belief = self.beliefs[lookup_key]
            del self.beliefs[lookup_key]
            
            # Обновляем индексы
            if lookup_key in self._index_by_type.get(belief_type, []):
                self._index_by_type[belief_type].remove(lookup_key)
            if lookup_key in self._index_by_subject.get(subject, []):
                self._index_by_subject[subject].remove(lookup_key)
            
            return True
        return False
    
    def get_belief(self, belief_type: BeliefType, subject: str, key: str) -> Optional[Belief]:
        """Получить конкретное убеждение"""
        lookup_key = f"{belief_type.value}:{subject}:{key}"
        return self.beliefs.get(lookup_key)
    
    def get_beliefs_by_type(self, belief_type: BeliefType) -> List[Belief]:
        """Получить все убеждения определённого типа"""
        keys = self._index_by_type.get(belief_type, [])
        return [self.beliefs[key] for key in keys if key in self.beliefs]
    
    def get_beliefs_about(self, subject: str) -> List[Belief]:
        """Получить все убеждения о чём-то/ком-то"""
        keys = self._index_by_subject.get(subject, [])
        return [self.beliefs[key] for key in keys if key in self.beliefs]
    
    def update_from_perception(self, perception: Dict[str, Any]) -> List[Belief]:
        """
        Обновить убеждения на основе нового восприятия
        
        Args:
            perception: Словарь с данными восприятия
                {
                    "type": "observation",
                    "subject": "agent_2",
                    "data": {"location": "park", "mood": "happy"},
                    "confidence": 0.9
                }
        
        Returns:
            Список новых/обновлённых убеждений
        """
        perception_type = perception.get("type", "observation")
        subject = perception.get("subject", "world")
        data = perception.get("data", {})
        base_confidence = perception.get("confidence", 0.9)
        
        new_beliefs = []
        
        # Определяем тип убеждения
        if subject.startswith("agent_") or subject == "self":
            belief_type = BeliefType.AGENT if subject != "self" else BeliefType.SELF
        elif perception_type == "event":
            belief_type = BeliefType.EVENT
        elif "social" in perception_type:
            belief_type = BeliefType.SOCIAL
        else:
            belief_type = BeliefType.WORLD
        
        # Создаём убеждения для каждого поля
        for key, value in data.items():
            belief = Belief(
                type=belief_type,
                subject=subject,
                key=key,
                value=value,
                confidence=base_confidence,
                source=perception_type,
                timestamp=datetime.now()
            )
            self.add_belief(belief)
            new_beliefs.append(belief)
        
        return new_beliefs
    
    def query(self, query_str: str, min_confidence: float = 0.0) -> List[Belief]:
        """
        Простой текстовый поиск по убеждениям
        
        Args:
            query_str: Строка поиска
            min_confidence: Минимальная уверенность
        
        Returns:
            Список подходящих убеждений
        """
        query_lower = query_str.lower()
        results = []
        
        for belief in self.beliefs.values():
            if belief.confidence < min_confidence:
                continue
                
            # Проверяем совпадение в subject, key или value
            if (query_lower in belief.subject.lower() or
                query_lower in belief.key.lower() or
                query_lower in str(belief.value).lower()):
                results.append(belief)
        
        return results
    
    def get_uncertain_beliefs(self, threshold: float = 0.5) -> List[Belief]:
        """Получить убеждения с низкой уверенностью"""
        return [
            belief for belief in self.beliefs.values()
            if belief.confidence < threshold
        ]
    
    def revise_belief(self, belief_type: BeliefType, subject: str, key: str, 
                     new_value: Any, new_confidence: float) -> bool:
        """
        Пересмотреть убеждение (изменить значение и уверенность)
        """
        belief = self.get_belief(belief_type, subject, key)
        if belief:
            belief.value = new_value
            belief.confidence = new_confidence
            belief.timestamp = datetime.now()
            return True
        return False
    
    def clear_old_beliefs(self, max_age_hours: float = 24.0) -> int:
        """
        Удалить старые убеждения (для управления памятью)
        
        Returns:
            Количество удалённых убеждений
        """
        now = datetime.now()
        to_remove = []
        
        for key, belief in self.beliefs.items():
            age_hours = (now - belief.timestamp).total_seconds() / 3600
            if age_hours > max_age_hours and belief.confidence < 0.7:
                to_remove.append((belief.type, belief.subject, belief.key))
        
        for belief_type, subject, key in to_remove:
            self.remove_belief(belief_type, subject, key)
        
        return len(to_remove)
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'beliefs': [belief.to_dict() for belief in self.beliefs.values()],
            'count': len(self.beliefs)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BeliefBase':
        """Десериализация из словаря"""
        belief_base = cls()
        for belief_data in data.get('beliefs', []):
            belief = Belief.from_dict(belief_data)
            belief_base.add_belief(belief)
        return belief_base
    
    def __len__(self) -> int:
        """Количество убеждений"""
        return len(self.beliefs)
    
    def __repr__(self) -> str:
        return f"BeliefBase({len(self.beliefs)} beliefs)"


# Utility функции для работы с убеждениями

def create_self_belief(agent_id: str, key: str, value: Any, confidence: float = 1.0) -> Belief:
    """Создать убеждение о себе"""
    return Belief(
        type=BeliefType.SELF,
        subject=agent_id,
        key=key,
        value=value,
        confidence=confidence,
        source="self_awareness"
    )


def create_agent_belief(observer_id: str, target_id: str, key: str, 
                       value: Any, confidence: float = 0.9) -> Belief:
    """Создать убеждение о другом агенте"""
    return Belief(
        type=BeliefType.AGENT,
        subject=target_id,
        key=key,
        value=value,
        confidence=confidence,
        source="observation"
    )


def create_world_belief(subject: str, key: str, value: Any, confidence: float = 0.9) -> Belief:
    """Создать убеждение о мире"""
    return Belief(
        type=BeliefType.WORLD,
        subject=subject,
        key=key,
        value=value,
        confidence=confidence,
        source="observation"
    )
