# backend/social_types.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================
# ENUMS
# ============================================

class SocialEventType(Enum):
    """Типы социальных событий"""
    HELP = "help"                    # Помощь
    BETRAY = "betray"                # Предательство
    COMMUNICATE = "communicate"      # Общение
    GIFT = "gift"                    # Подарок
    INSULT = "insult"                # Оскорбление
    IGNORE = "ignore"                # Игнорирование
    SHARE = "share"                  # Делиться ресурсами
    STEAL = "steal"                  # Воровство
    DEFEND = "defend"                # Защита
    GOSSIP = "gossip"                # Сплетня


class SocialSentiment(Enum):
    """Эмоциональная окраска события"""
    VERY_POSITIVE = 2.0
    POSITIVE = 1.0
    NEUTRAL = 0.0
    NEGATIVE = -1.0
    VERY_NEGATIVE = -2.0


# ============================================
# DATACLASSES (для внутреннего использования)
# ============================================

@dataclass
class RelationshipVector:
    """
    Вектор отношений между двумя агентами.
    Все значения в диапазоне [-1.0, 1.0]
    """
    agent_from: str
    agent_to: str
    
    # Основные параметры отношений
    affinity: float = 0.0        # Симпатия: -1 (враг) до +1 (друг)
    trust: float = 0.5           # Доверие: 0 (не верю) до +1 (полное доверие)
    dominance: float = 0.0       # Влияние: -1 (подчиненный) до +1 (лидер)
    
    # Динамические параметры
    familiarity: float = 0.0     # Знакомство: 0 (незнакомец) до 1 (близкий)
    respect: float = 0.5         # Уважение: 0 до 1
    
    # История
    interaction_count: int = 0
    last_interaction: Optional[str] = None  # ISO timestamp
    history_log: List[Dict] = field(default_factory=list)  # Последние 10 событий
    
    # Метаданные
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """Преобразовать в словарь для JSON"""
        return {
            "agent_from": self.agent_from,
            "agent_to": self.agent_to,
            "affinity": round(self.affinity, 3),
            "trust": round(self.trust, 3),
            "dominance": round(self.dominance, 3),
            "familiarity": round(self.familiarity, 3),
            "respect": round(self.respect, 3),
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction,
            "history_log": self.history_log[-5:],  # Только последние 5
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def get_relationship_label(self) -> str:
        """Получить текстовую метку отношений"""
        if self.affinity > 0.7:
            return "Лучший друг"
        elif self.affinity > 0.4:
            return "Друг"
        elif self.affinity > 0.1:
            return "Знакомый"
        elif self.affinity > -0.1:
            return "Нейтральный"
        elif self.affinity > -0.4:
            return "Неприятный"
        elif self.affinity > -0.7:
            return "Враг"
        else:
            return "Заклятый враг"
    
    def get_trust_label(self) -> str:
        """Получить текстовую метку доверия"""
        if self.trust > 0.8:
            return "Полностью доверяю"
        elif self.trust > 0.6:
            return "Доверяю"
        elif self.trust > 0.4:
            return "Осторожно доверяю"
        elif self.trust > 0.2:
            return "Не особо доверяю"
        else:
            return "Не доверяю"


@dataclass
class SocialEvent:
    """Событие, влияющее на отношения"""
    event_type: SocialEventType
    agent_from: str              # Кто совершил действие
    agent_to: str                # На кого направлено
    sentiment: SocialSentiment   # Эмоциональная окраска
    description: str             # Описание события
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    witnesses: List[str] = field(default_factory=list)  # Свидетели
    metadata: Dict = field(default_factory=dict)


# ============================================
# PYDANTIC MODELS (для FastAPI)
# ============================================

class SocialEventCreate(BaseModel):
    """Модель для создания социального события через API"""
    event_type: str = Field(..., description="Тип события: help, betray, communicate, etc.")
    agent_from: str = Field(..., description="ID агента, который совершил действие")
    agent_to: str = Field(..., description="ID агента, на которого направлено действие")
    sentiment: float = Field(..., ge=-2.0, le=2.0, description="Эмоциональная окраска: -2.0 до 2.0")
    description: str = Field(..., description="Описание события")
    witnesses: List[str] = Field(default_factory=list, description="Список ID свидетелей")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "help",
                "agent_from": "agent-0",
                "agent_to": "agent-1",
                "sentiment": 1.0,
                "description": "Алекса помогла Нексусу починить систему",
                "witnesses": ["agent-2"]
            }
        }


class GossipCreate(BaseModel):
    """Модель для распространения слуха через API"""
    gossiper_id: str = Field(..., description="ID агента, который сплетничает")
    listener_id: str = Field(..., description="ID агента, который слушает")
    target_id: str = Field(..., description="ID агента, о котором сплетничают")
    sentiment: float = Field(..., ge=-2.0, le=2.0, description="Тональность слуха: -2.0 до 2.0")
    content: str = Field(..., description="Содержание слуха")
    
    class Config:
        json_schema_extra = {
            "example": {
                "gossiper_id": "agent-2",
                "listener_id": "agent-0",
                "target_id": "agent-1",
                "sentiment": -1.5,
                "content": "Я видел, как Нексус украл данные из хранилища!"
            }
        }


class RelationshipQuery(BaseModel):
    """Модель для запроса отношений"""
    agent_from: str = Field(..., description="ID первого агента")
    agent_to: str = Field(..., description="ID второго агента")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_from": "agent-0",
                "agent_to": "agent-1"
            }
        }


class MemoryCreate(BaseModel):
    """Модель для создания воспоминания"""
    agent_id: str = Field(..., description="ID агента")
    event_description: str = Field(..., description="Описание события")
    event_type: str = Field(default="observation", description="Тип события: observation, interaction, action, goal")
    emotion: str = Field(default="neutral", description="Эмоция агента во время события")
    importance: int = Field(default=5, ge=1, le=10, description="Важность события (1-10)")
    participants: Optional[List[str]] = Field(default=None, description="Список ID участников события")
    metadata: Optional[Dict] = Field(default=None, description="Дополнительные метаданные")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "agent-0",
                "event_description": "Алекса нашла древний артефакт в заброшенной лаборатории",
                "event_type": "observation",
                "emotion": "excited",
                "importance": 9,
                "participants": [],
                "metadata": {"location": "old_lab", "item": "artifact"}
            }
        }


class MemoryRecall(BaseModel):
    """Модель для извлечения воспоминаний"""
    agent_id: str = Field(..., description="ID агента")
    current_situation: str = Field(..., description="Описание текущей ситуации или вопрос")
    n_results: int = Field(default=5, ge=1, le=20, description="Количество воспоминаний для извлечения")
    event_type: Optional[str] = Field(default=None, description="Фильтр по типу события")
    min_importance: Optional[int] = Field(default=None, ge=1, le=10, description="Минимальная важность")
    time_window_days: Optional[int] = Field(default=None, ge=1, description="Учитывать только последние N дней")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "agent-0",
                "current_situation": "Нужно принять решение о доверии Нексусу",
                "n_results": 5,
                "event_type": "interaction",
                "min_importance": 6
            }
        }


class SummarizeRequest(BaseModel):
    """Модель для суммаризации старых воспоминаний"""
    agent_id: str = Field(..., description="ID агента")
    older_than_days: int = Field(default=7, ge=1, description="Воспоминания старше N дней")
    model: str = Field(default="openai/gpt-4o-mini", description="Модель OpenRouter для суммаризации")
    cluster_by: str = Field(default="participants", description="По какому признаку группировать: participants, event_type, emotion")
    min_memories_to_summarize: int = Field(default=10, ge=5, description="Минимум воспоминаний для запуска")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "agent-0",
                "older_than_days": 7,
                "model": "openai/gpt-4o-mini",
                "cluster_by": "participants",
                "min_memories_to_summarize": 10
            }
        }


class AgentCreate(BaseModel):
    """Модель для создания агента"""
    id: str = Field(..., description="Уникальный ID агента")
    name: str = Field(..., description="Имя агента")
    personality: str = Field(..., description="Описание личности")
    avatar_url: Optional[str] = Field(default=None, description="URL аватара")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "agent-3",
                "name": "Киберия",
                "personality": "Креативная, любопытная, импульсивная",
                "avatar_url": "🌸"
            }
        }


class MessageCreate(BaseModel):
    """Модель для отправки сообщения"""
    sender_id: str = Field(default="user", description="ID отправителя")
    receiver_id: str = Field(..., description="ID получателя")
    content: str = Field(..., description="Текст сообщения")
    message_type: str = Field(default="direct", description="Тип сообщения: direct, broadcast, system")
    topic: Optional[str] = Field(default="general", description="Тема разговора")
    emotion: Optional[str] = Field(default=None, description="Эмоция отправителя")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sender_id": "user",
                "receiver_id": "agent-0",
                "content": "Привет, Алекса! Как дела?",
                "message_type": "direct",
                "topic": "greeting",
                "emotion": "happy"
            }
        }


class EventCreate(BaseModel):
    """Модель для создания глобального события"""
    event_description: str = Field(..., description="Описание события")
    agent_id: Optional[str] = Field(default=None, description="ID конкретного агента (если None - всем)")
    event_type: str = Field(default="world_event", description="Тип события")
    metadata: Optional[Dict] = Field(default=None, description="Дополнительные данные")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_description": "В городе найден клад!",
                "agent_id": None,
                "event_type": "world_event",
                "metadata": {"location": "city_center", "value": "high"}
            }
        }


class SpeedControl(BaseModel):
    """Модель для управления скоростью симуляции"""
    speed: float = Field(..., ge=0.1, le=10.0, description="Множитель скорости (0.1 - 10.0)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "speed": 2.0
            }
        }


class BatchEventsRequest(BaseModel):
    """Модель для пакетной обработки событий"""
    events: List[SocialEventCreate] = Field(..., description="Список социальных событий")
    
    class Config:
        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_type": "help",
                        "agent_from": "agent-0",
                        "agent_to": "agent-1",
                        "sentiment": 1.0,
                        "description": "Помощь #1"
                    },
                    {
                        "event_type": "communicate",
                        "agent_from": "agent-1",
                        "agent_to": "agent-0",
                        "sentiment": 0.5,
                        "description": "Общение #1"
                    }
                ]
            }
        }


# ============================================
# RESPONSE MODELS
# ============================================

class RelationshipResponse(BaseModel):
    """Модель ответа с отношениями"""
    agent_from: str
    agent_to: str
    affinity: float
    trust: float
    dominance: float
    familiarity: float
    respect: float
    interaction_count: int
    relationship_label: str
    trust_label: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_from": "agent-0",
                "agent_to": "agent-1",
                "affinity": 0.65,
                "trust": 0.75,
                "dominance": 0.1,
                "familiarity": 0.8,
                "respect": 0.7,
                "interaction_count": 15,
                "relationship_label": "Друг",
                "trust_label": "Доверяю"
            }
        }


class MemoryResponse(BaseModel):
    """Модель ответа с воспоминанием"""
    text: str
    timestamp: str
    emotion: str
    importance: int
    event_type: str
    relevance_score: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Алекса помогла Нексусу починить систему",
                "timestamp": "2026-02-17T16:30:00",
                "emotion": "happy",
                "importance": 7,
                "event_type": "interaction",
                "relevance_score": 0.85
            }
        }


class SocialGraphResponse(BaseModel):
    """Модель ответа с графом отношений"""
    nodes: List[Dict]
    edges: List[Dict]
    
    class Config:
        json_schema_extra = {
            "example": {
                "nodes": [
                    {"id": "agent-0", "name": "Алекса", "avatar": "🤖"},
                    {"id": "agent-1", "name": "Нексус", "avatar": "👾"}
                ],
                "edges": [
                    {
                        "from": "agent-0",
                        "to": "agent-1",
                        "affinity": 0.65,
                        "trust": 0.75,
                        "color": "#00ff00"
                    }
                ]
            }
        }
