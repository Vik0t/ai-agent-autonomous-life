# backend/communication.py
"""
Database-First Communication System
Все сообщения и диалоги хранятся только в БД
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import uuid
from datetime import datetime

from database.Database import Database


class MessageType(Enum):
    """Типы сообщений в диалоге"""
    GREETING = "greeting"
    QUESTION = "question"
    ANSWER = "answer"
    STATEMENT = "statement"
    FAREWELL = "farewell"
    ACKNOWLEDGMENT = "ack"


class ConversationStatus(Enum):
    """Статус диалога"""
    ACTIVE = "active"
    WAITING = "waiting"
    ENDED = "ended"
    TIMED_OUT = "timed_out"


@dataclass
class Message:
    """
    Сообщение (только для работы в коде, не хранится в RAM)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    content: str = ""
    
    # Тип и контекст
    message_type: MessageType = MessageType.STATEMENT
    conversation_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    # Эмоциональный окрас
    emotion: Optional[str] = None
    tone: str = "neutral"
    
    # Тема разговора
    topic: Optional[str] = None
    
    # Временные метки
    timestamp: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    
    # Ожидание ответа
    requires_response: bool = False
    response_timeout: float = 30.0
    
    @classmethod
    def from_db_row(cls, row: Dict) -> 'Message':
        """
        Создать Message из строки БД
        
        Args:
            row: sqlite3.Row преобразованный в dict
        
        Returns:
            Объект Message
        """        
        # Защита от sqlite3.Row
        if not isinstance(row, dict):
            try:
                row = dict(row)
            except Exception as e:
                return cls(content="[error loading message]")
        
        # Парсинг message_type
        type_str = row.get('message_type', 'direct')
        
        type_mapping = {
            'greeting': MessageType.GREETING,
            'question': MessageType.QUESTION,
            'answer': MessageType.ANSWER,
            'statement': MessageType.STATEMENT,
            'farewell': MessageType.FAREWELL,
            'ack': MessageType.ACKNOWLEDGMENT,
            'direct': MessageType.STATEMENT,
            'broadcast': MessageType.STATEMENT,
            'system': MessageType.STATEMENT
        }
        message_type = type_mapping.get(type_str, MessageType.STATEMENT)
        
        # Парсинг timestamp
        timestamp_str = row.get('timestamp')
        
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp = dt.timestamp()
            except Exception as e:
                timestamp = time.time()
        else:
            timestamp = time.time()
        
        # Создание объекта
        try:
            message = cls(
                id=str(row.get('id', uuid.uuid4())),
                sender_id=row.get('sender_id', ''),
                receiver_id=row.get('receiver_id', ''),
                content=row.get('content', ''),
                message_type=message_type,
                emotion=row.get('emotion'),
                tone=row.get('tone', 'neutral'),
                topic=row.get('topic'),
                timestamp=timestamp,
                conversation_id=row.get('conversation_id'),
                in_reply_to=row.get('parent_message_id')
            )
            return message
            
        except KeyError as e:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise


@dataclass
class Conversation:
    """
    Диалог (загружается из БД по требованию)
    """
    id: str
    participants: List[str]
    topic: str = "general"
    status: ConversationStatus = ConversationStatus.ACTIVE
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    
    waiting_for_response_from: Optional[str] = None
    expected_response_by: Optional[float] = None
    
    def get_context_for_agent(self, agent_id: str, max_messages: int = 5, db: Database = None) -> List[Message]:
        """
        Получить контекст диалога ИЗ БД
        """
        if not db:
            return []
        
        # Найти второго участника
        other_participant = None
        for p in self.participants:
            if p != agent_id:
                other_participant = p
                break
        
        if not other_participant:
            return []
        
        # Загрузить из БД
        db_messages = db.get_conversation(agent_id, other_participant, limit=max_messages)
        
        # Преобразовать в Message объекты
        messages = []
        for db_msg in db_messages:
            msg = Message(
                id=str(db_msg.get('id', uuid.uuid4())),
                sender_id=db_msg['sender_id'],
                receiver_id=db_msg.get('receiver_id', ''),
                content=db_msg['content'],
                message_type=MessageType.STATEMENT,
                emotion=db_msg.get('emotion'),
                topic=self.topic
            )
            messages.append(msg)
        
        return messages
    
    def is_timed_out(self) -> bool:
        """Проверить timeout"""
        if self.expected_response_by:
            return time.time() > self.expected_response_by
        return False
    
    def to_dict(self, db: Database = None) -> Dict:
        """Сериализация для API"""
        message_count = 0
        if db:
            # Подсчитать сообщения в БД
            try:
                messages = db.get_conversation(
                    self.participants[0], 
                    self.participants[1] if len(self.participants) > 1 else self.participants[0],
                    limit=1000
                )
                message_count = len(messages)
            except:
                pass
        
        return {
            'id': self.id,
            'participants': self.participants,
            'topic': self.topic,
            'message_count': message_count,
            'status': self.status.value,
            'started_at': self.started_at,
            'last_activity': self.last_activity,
            'ended_at': self.ended_at,
            'waiting_for': self.waiting_for_response_from
        }


class CommunicationHub:
    """
    Database-First Communication Hub
    Все данные хранятся только в БД, никакого RAM кэша
    """
    
    def __init__(self, db: Database):
        self.db = db
        
        # Только очереди для доставки (живут в RAM)
        self.agent_connections: Dict[str, asyncio.Queue] = {}
        
        # Временное хранилище метаданных активных диалогов (только статус, не сообщения)
        self.active_conversations: Dict[str, Conversation] = {}
    
    def register_agent(self, agent_id: str):
        """Регистрация агента для получения сообщений"""
        if agent_id not in self.agent_connections:
            self.agent_connections[agent_id] = asyncio.Queue()
    
    # ========================================
    # CONVERSATION MANAGEMENT (Database-First)
    # ========================================
    
    def start_conversation(self, initiator: str, target: str, topic: str = "general") -> Conversation:
        """
        Начать новый диалог (или найти существующий в БД)
        """
        # Проверить в активных
        existing = self.get_active_conversation(initiator, target)
        if existing:
            return existing
        
        # Проверить в БД (есть ли недавние сообщения)
        db_messages = self.db.get_conversation(initiator, target, limit=1)
        
        # Если есть недавние сообщения (последние 1 час) - продолжить диалог
        if db_messages:
            last_msg = db_messages[-1]
            timestamp_str = last_msg.get('timestamp', '')
            try:
                # Парсинг timestamp из БД
                if timestamp_str:
                    last_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    time_diff = (datetime.now() - last_time).total_seconds()
                    
                    if time_diff < 3600:  # Меньше часа
                        # Продолжить существующий диалог
                        conv_id = f"conv_{initiator}_{target}"
                        conversation = Conversation(
                            id=conv_id,
                            participants=[initiator, target],
                            topic=topic,
                            status=ConversationStatus.ACTIVE
                        )
                        self.active_conversations[conv_id] = conversation
                        return conversation
            except:
                pass
        
        # Создать новый диалог
        conv_id = f"conv_{initiator}_{target}_{int(time.time())}"
        conversation = Conversation(
            id=conv_id,
            participants=[initiator, target],
            topic=topic,
            status=ConversationStatus.ACTIVE
        )
        
        self.active_conversations[conv_id] = conversation
        return conversation
    
    def get_active_conversation(self, agent_1: str, agent_2: str) -> Optional[Conversation]:
        """
        Найти активный диалог между агентами
        """
        for conv in self.active_conversations.values():
            if (agent_1 in conv.participants and 
                agent_2 in conv.participants and 
                conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]):
                return conv
        return None
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Получить диалог по ID"""
        return self.active_conversations.get(conversation_id)
    
    def is_agent_in_conversation(self, agent_id: str) -> bool:
        """Проверить занят ли агент активным диалогом"""
        for conv in self.active_conversations.values():
            if (agent_id in conv.participants and 
                conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]):
                return True
        return False
    
    def get_agent_active_conversations(self, agent_id: str) -> List[Conversation]:
        """Получить все активные диалоги агента"""
        active = []
        for conv in self.active_conversations.values():
            if (agent_id in conv.participants and 
                conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]):
                active.append(conv)
        return active
    
    def end_conversation(self, conversation_id: str):
        """Завершить диалог"""
        conv = self.active_conversations.get(conversation_id)
        if conv:
            conv.status = ConversationStatus.ENDED
            conv.ended_at = time.time()
    
    # ========================================
    # MESSAGE HANDLING (Database-First)
    # ========================================
    
    async def receive_messages(self, agent_id: str) -> List[Message]:
        """
        Получить новые сообщения из очереди
        (Только для real-time уведомлений, не для истории)
        """
        if agent_id not in self.agent_connections:
            return []
        
        messages = []
        queue = self.agent_connections[agent_id]
        
        while not queue.empty():
            try:
                message = queue.get_nowait()
                message.read_at = time.time()
                messages.append(message)
            except asyncio.QueueEmpty:
                break
        
        return messages
    
    def get_conversation_history(self, agent1_id: str, agent2_id: str, limit: int = 50) -> List[Message]:
        """
        Загрузить историю диалога ИЗ БД
        """
        db_messages = self.db.get_conversation(agent1_id, agent2_id, limit)
        
        messages = []
        for db_msg in db_messages:
            msg = Message(
                id=str(db_msg.get('id', uuid.uuid4())),
                sender_id=db_msg['sender_id'],
                receiver_id=db_msg.get('receiver_id', ''),
                content=db_msg['content'],
                message_type=MessageType.STATEMENT,
                emotion=db_msg.get('emotion')
            )
            messages.append(msg)
        
        return messages
    
    def broadcast_message(self, sender_id: str, content: str, topic: str = "announcement"):
        """
        Отправить всем агентам (broadcast)
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
                
                # Сохранить в БД
                self.db.send_message(
                    sender_id=sender_id,
                    receiver_id=agent_id,
                    content=content,
                    message_type="broadcast"
                )
                
                # Доставить через очередь
                asyncio.create_task(self._deliver_message(agent_id, message))
    
    async def _deliver_message(self, agent_id: str, message: Message):
        """Доставить в очередь агента"""
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].put(message)
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Получить последние сообщения из БД
        """
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        # Преобразовать каждую строку в Message объект
        return [Message.from_db_row(dict(row)) for row in cursor.fetchall()]
        

    
    def get_all_active_conversations(self) -> List[Conversation]:
        """Получить все активные диалоги"""
        return [
            conv for conv in self.active_conversations.values()
            if conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
        ]
    
    def cleanup_old_conversations(self, max_age_hours: float = 24.0):
        """
        Очистка старых диалогов из active_conversations
        (Данные остаются в БД!)
        """
        current_time = time.time()
        to_remove = []
        
        for conv_id, conv in self.active_conversations.items():
            if conv.status == ConversationStatus.ENDED:
                age_hours = (current_time - (conv.ended_at or conv.last_activity)) / 3600
                if age_hours > max_age_hours:
                    to_remove.append(conv_id)
        
        for conv_id in to_remove:
            self.active_conversations.pop(conv_id)
        
        return len(to_remove)
    
    def get_agent_message_count(self, agent_id: str) -> Dict[str, int]:
        """
        Получить статистику сообщений агента из БД
        """
        cursor = self.db.conn.cursor()
        
        # Отправленные
        cursor.execute("""
            SELECT COUNT(*) as count FROM messages WHERE sender_id = ?
        """, (agent_id,))
        sent = cursor.fetchone()['count']
        
        # Полученные
        cursor.execute("""
            SELECT COUNT(*) as count FROM messages WHERE receiver_id = ?
        """, (agent_id,))
        received = cursor.fetchone()['count']
        
        return {
            "sent": sent,
            "received": received,
            "total": sent + received
        }


# ========================================
# HELPER FUNCTIONS
# ========================================

def format_conversation_for_llm(conversation: Conversation, db: Database, max_messages: int = 5) -> str:
    """
    Форматировать историю диалога для LLM (загрузка из БД)
    """
    messages = conversation.get_context_for_agent(
        conversation.participants[0], 
        max_messages=max_messages,
        db=db
    )
    
    lines = []
    for msg in messages:
        lines.append(f"[{msg.sender_id}]: {msg.content}")
    
    return "\n".join(lines)


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
