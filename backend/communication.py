# backend/communication.py
"""
Enhanced Communication System с поддержкой полноценных диалогов

Изменения:
- Message теперь структурированный с типами и контекстом
- Conversation для отслеживания диалогов
- ConversationManager в CommunicationHub
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import uuid


class MessageType(Enum):
    """Типы сообщений в диалоге"""
    GREETING = "greeting"       # Приветствие
    QUESTION = "question"       # Вопрос
    ANSWER = "answer"           # Ответ
    STATEMENT = "statement"     # Утверждение/рассказ
    FAREWELL = "farewell"       # Прощание
    ACKNOWLEDGMENT = "ack"      # Подтверждение "ок", "понял"


class ConversationStatus(Enum):
    """Статус диалога"""
    ACTIVE = "active"
    WAITING = "waiting"  # Ожидание ответа
    ENDED = "ended"
    TIMED_OUT = "timed_out"


@dataclass
class Message:
    """
    Улучшенное сообщение с контекстом диалога
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    content: str = ""
    
    # Тип и контекст
    message_type: MessageType = MessageType.STATEMENT
    conversation_id: Optional[str] = None
    in_reply_to: Optional[str] = None  # ID сообщения на которое отвечаем
    
    # Эмоциональный окрас
    emotion: Optional[str] = None  # "happy", "curious", "concerned"
    tone: str = "neutral"  # "friendly", "formal", "casual"
    
    # Тема разговора
    topic: Optional[str] = None
    
    # Временные метки
    timestamp: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    
    # Ожидание ответа
    requires_response: bool = False
    response_timeout: float = 30.0
    
    def to_dict(self) -> Dict:
        """Сериализация для API/WebSocket"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'content': self.content,
            'message_type': self.message_type.value,
            'conversation_id': self.conversation_id,
            'in_reply_to': self.in_reply_to,
            'emotion': self.emotion,
            'tone': self.tone,
            'topic': self.topic,
            'timestamp': self.timestamp,
            'delivered_at': self.delivered_at,
            'read_at': self.read_at,
            'requires_response': self.requires_response,
            'response_timeout': self.response_timeout
        }


@dataclass
class Conversation:
    """
    Диалог между агентами
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    participants: List[str] = field(default_factory=list)  # [agent_id_1, agent_id_2]
    topic: str = "general"
    messages: List[Message] = field(default_factory=list)
    
    status: ConversationStatus = ConversationStatus.ACTIVE
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    
    # Для BDI waiting
    waiting_for_response_from: Optional[str] = None
    expected_response_by: Optional[float] = None
    
    def add_message(self, message: Message):
        """Добавить сообщение в диалог"""
        self.messages.append(message)
        self.last_activity = message.timestamp
        message.delivered_at = message.timestamp
        
        # Обновляем статус ожидания
        if message.requires_response:
            self.waiting_for_response_from = message.receiver_id
            self.expected_response_by = message.timestamp + message.response_timeout
            self.status = ConversationStatus.WAITING
        else:
            self.waiting_for_response_from = None
            self.expected_response_by = None
            if self.status == ConversationStatus.WAITING:
                self.status = ConversationStatus.ACTIVE
    
    def get_context_for_agent(self, agent_id: str, max_messages: int = 5) -> List[Message]:
        """
        Получить контекст диалога для агента (последние N сообщений)
        """
        return self.messages[-max_messages:] if self.messages else []
    
    def is_timed_out(self) -> bool:
        """Проверить истёк ли timeout ожидания"""
        if self.expected_response_by:
            return time.time() > self.expected_response_by
        return False
    
    def mark_as_ended(self):
        """Завершить диалог"""
        self.status = ConversationStatus.ENDED
        self.ended_at = time.time()
    
    def to_dict(self) -> Dict:
        """Сериализация для API"""
        return {
            'id': self.id,
            'participants': self.participants,
            'topic': self.topic,
            'message_count': len(self.messages),
            'status': self.status.value,
            'started_at': self.started_at,
            'last_activity': self.last_activity,
            'ended_at': self.ended_at,
            'waiting_for': self.waiting_for_response_from,
            'messages': [msg.to_dict() for msg in self.messages[-10:]]  # Последние 10
        }


class CommunicationHub:
    """
    Центр коммуникации с поддержкой диалогов
    """
    
    def __init__(self):
        # Оригинальные компоненты
        self.messages: List[Message] = []
        self.agent_connections: Dict[str, asyncio.Queue] = {}
        
        # НОВОЕ: Управление диалогами
        self.conversations: Dict[str, Conversation] = {}  # conversation_id -> Conversation
        self.agent_conversations: Dict[str, List[str]] = {}  # agent_id -> [conversation_ids]
        
    def register_agent(self, agent_id: str):
        """Register an agent to receive messages"""
        if agent_id not in self.agent_connections:
            self.agent_connections[agent_id] = asyncio.Queue()
        
        if agent_id not in self.agent_conversations:
            self.agent_conversations[agent_id] = []
    
    # ========================================
    # CONVERSATION MANAGEMENT
    # ========================================
    
    def start_conversation(self, initiator: str, target: str, topic: str = "general") -> Conversation:
        """
        Начать новый диалог между двумя агентами
        
        Returns:
            Созданный Conversation объект
        """
        # Проверяем нет ли уже активного диалога
        existing = self.get_active_conversation(initiator, target)
        if existing:
            return existing
        
        # Создаём новый
        conv_id = f"conv_{initiator}_{target}_{int(time.time())}"
        conversation = Conversation(
            id=conv_id,
            participants=[initiator, target],
            topic=topic
        )
        
        self.conversations[conv_id] = conversation
        
        # Регистрируем у обоих агентов
        self.agent_conversations[initiator].append(conv_id)
        self.agent_conversations[target].append(conv_id)
        
        return conversation
    
    def get_active_conversation(self, agent_1: str, agent_2: str) -> Optional[Conversation]:
        """
        Найти активный диалог между двумя агентами
        """
        for conv in self.conversations.values():
            if (agent_1 in conv.participants and 
                agent_2 in conv.participants and 
                conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]):
                return conv
        return None
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Получить диалог по ID"""
        return self.conversations.get(conversation_id)
    
    def is_agent_in_conversation(self, agent_id: str) -> bool:
        """
        Проверить занят ли агент активным диалогом
        """
        agent_convs = self.agent_conversations.get(agent_id, [])
        for conv_id in agent_convs:
            conv = self.conversations.get(conv_id)
            if conv and conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]:
                return True
        return False
    
    def get_agent_active_conversations(self, agent_id: str) -> List[Conversation]:
        """Получить все активные диалоги агента"""
        agent_convs = self.agent_conversations.get(agent_id, [])
        active = []
        
        for conv_id in agent_convs:
            conv = self.conversations.get(conv_id)
            if conv and conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]:
                active.append(conv)
        
        return active
    
    def end_conversation(self, conversation_id: str):
        """Завершить диалог"""
        conv = self.conversations.get(conversation_id)
        if conv:
            conv.mark_as_ended()
    
    # ========================================
    # MESSAGE HANDLING
    # ========================================
    
    async def send_message(self, message: Message):
        """
        Отправить сообщение (улучшенная версия)
        """
        self.messages.append(message)
        
        # Если сообщение в контексте диалога - добавляем его туда
        if message.conversation_id:
            conv = self.conversations.get(message.conversation_id)
            if conv:
                conv.add_message(message)
        
        # Доставляем получателю
        if message.receiver_id in self.agent_connections:
            await self.agent_connections[message.receiver_id].put(message)
            message.delivered_at = time.time()
    
    async def receive_messages(self, agent_id: str) -> List[Message]:
        """
        Получить все ожидающие сообщения для агента
        """
        if agent_id not in self.agent_connections:
            return []
        
        messages = []
        queue = self.agent_connections[agent_id]
        
        # Забираем все доступные сообщения
        while not queue.empty():
            try:
                message = queue.get_nowait()
                message.read_at = time.time()
                messages.append(message)
            except asyncio.QueueEmpty:
                break
        
        return messages
    
    def broadcast_message(self, sender_id: str, content: str, topic: str = "announcement"):
        """
        Отправить сообщение всем агентам (broadcast)
        """
        for agent_id in self.agent_connections:
            if agent_id != sender_id:
                message = Message(
                    sender_id=sender_id,
                    receiver_id=agent_id,
                    content=content,
                    message_type=MessageType.STATEMENT,
                    topic=topic,
                    tone="formal"
                )
                self.messages.append(message)
                asyncio.create_task(self._deliver_message(agent_id, message))
    
    async def _deliver_message(self, agent_id: str, message: Message):
        """Доставить сообщение в очередь агента"""
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].put(message)
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Получить последние сообщения в системе"""
        return self.messages[-limit:] if self.messages else []
    
    def get_all_active_conversations(self) -> List[Conversation]:
        """Получить все активные диалоги"""
        return [
            conv for conv in self.conversations.values()
            if conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
        ]
    
    def cleanup_old_conversations(self, max_age_hours: float = 24.0):
        """
        Очистка старых завершённых диалогов
        """
        current_time = time.time()
        to_remove = []
        
        for conv_id, conv in self.conversations.items():
            if conv.status == ConversationStatus.ENDED:
                age_hours = (current_time - (conv.ended_at or conv.last_activity)) / 3600
                if age_hours > max_age_hours:
                    to_remove.append(conv_id)
        
        for conv_id in to_remove:
            # Удаляем из conversations
            conv = self.conversations.pop(conv_id)
            
            # Удаляем из agent_conversations
            for agent_id in conv.participants:
                if agent_id in self.agent_conversations:
                    if conv_id in self.agent_conversations[agent_id]:
                        self.agent_conversations[agent_id].remove(conv_id)
        
        return len(to_remove)


# ========================================
# HELPER FUNCTIONS
# ========================================

def create_message(
    sender_id: str,
    receiver_id: str,
    content: str,
    message_type: MessageType = MessageType.STATEMENT,
    conversation_id: Optional[str] = None,
    requires_response: bool = False,
    **kwargs
) -> Message:
    """
    Utility функция для создания сообщения
    """
    return Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type,
        conversation_id=conversation_id,
        requires_response=requires_response,
        **kwargs
    )


def format_conversation_for_llm(conversation: Conversation, max_messages: int = 5) -> str:
    """
    Форматировать историю диалога для передачи в LLM
    
    Returns:
        Строка вида:
        "[Alice]: Hello!
         [Bob]: Hi there!
         [Alice]: How are you?"
    """
    messages = conversation.messages[-max_messages:]
    
    lines = []
    for msg in messages:
        sender_name = msg.sender_id  # Можно заменить на имя агента
        lines.append(f"[{sender_name}]: {msg.content}")
    
    return "\n".join(lines)