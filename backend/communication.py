# backend/communication.py
"""
Database-First Communication System
Все сообщения и диалоги хранятся в БД.
send_message сохраняет в БД и доставляет через in-memory очередь.
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
    Сообщение (объект для работы в коде).
    Персистентность — только через БД.
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
            'response_timeout': self.response_timeout,
        }

    @classmethod
    def from_db_row(cls, row: Dict) -> 'Message':
        """
        Создать Message из строки БД.

        Args:
            row: sqlite3.Row, преобразованный в dict
        """
        if not isinstance(row, dict):
            try:
                row = dict(row)
            except Exception:
                return cls(content="[error loading message]")

        type_mapping = {
            'greeting':  MessageType.GREETING,
            'question':  MessageType.QUESTION,
            'answer':    MessageType.ANSWER,
            'statement': MessageType.STATEMENT,
            'farewell':  MessageType.FAREWELL,
            'ack':       MessageType.ACKNOWLEDGMENT,
            'direct':    MessageType.STATEMENT,
            'broadcast': MessageType.STATEMENT,
            'system':    MessageType.STATEMENT,
        }
        message_type = type_mapping.get(row.get('message_type', 'direct'), MessageType.STATEMENT)

        timestamp_str = row.get('timestamp')
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp = dt.timestamp()
            except Exception:
                timestamp = time.time()
        else:
            timestamp = time.time()

        try:
            return cls(
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
                in_reply_to=row.get('parent_message_id'),
            )
        except Exception:
            import traceback
            traceback.print_exc()
            raise


@dataclass
class Conversation:
    """
    Диалог — метаданные в RAM, сообщения загружаются из БД по требованию.
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

    def get_context_for_agent(
        self,
        agent_id: str,
        max_messages: int = 5,
        db: Database = None,
    ) -> List[Message]:
        """Получить последние N сообщений диалога из БД."""
        if not db:
            return []

        other_participant = next(
            (p for p in self.participants if p != agent_id), None
        )
        if not other_participant:
            return []

        db_messages = db.get_conversation(agent_id, other_participant, limit=max_messages)
        return [
            Message(
                id=str(db_msg.get('id', uuid.uuid4())),
                sender_id=db_msg['sender_id'],
                receiver_id=db_msg.get('receiver_id', ''),
                content=db_msg['content'],
                message_type=MessageType.STATEMENT,
                emotion=db_msg.get('emotion'),
                topic=self.topic,
            )
            for db_msg in db_messages
        ]

    def is_timed_out(self) -> bool:
        """Проверить истёк ли timeout ожидания."""
        if self.expected_response_by:
            return time.time() > self.expected_response_by
        return False

    def to_dict(self, db: Database = None) -> Dict:
        """Сериализация для API."""
        message_count = 0
        if db:
            try:
                msgs = db.get_conversation(
                    self.participants[0],
                    self.participants[1] if len(self.participants) > 1 else self.participants[0],
                    limit=1000,
                )
                message_count = len(msgs)
            except Exception:
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
            'waiting_for': self.waiting_for_response_from,
        }


class CommunicationHub:
    """
    Database-First Communication Hub.
    Метаданные активных диалогов — в RAM.
    Сообщения — только в БД + real-time доставка через asyncio.Queue.
    """

    def __init__(self, db: Database):
        self.db = db
        # Real-time очереди доставки (только RAM)
        self.agent_connections: Dict[str, asyncio.Queue] = {}
        # Метаданные активных диалогов (только статус, не сообщения)
        self.active_conversations: Dict[str, Conversation] = {}

    def register_agent(self, agent_id: str):
        """Зарегистрировать агента для получения сообщений."""
        if agent_id not in self.agent_connections:
            self.agent_connections[agent_id] = asyncio.Queue()

    # ========================================
    # CONVERSATION MANAGEMENT (Database-First)
    # ========================================

    def start_conversation(self, initiator: str, target: str, topic: str = "general") -> Conversation:
        """
        Начать новый диалог или вернуть существующий активный.
        Если в БД есть сообщения не старше 1 часа — продолжает тот диалог.
        """
        existing = self.get_active_conversation(initiator, target)
        if existing:
            return existing

        # Проверить наличие недавних сообщений в БД
        db_messages = self.db.get_conversation(initiator, target, limit=1)
        if db_messages:
            last_msg = db_messages[-1]
            timestamp_str = last_msg.get('timestamp', '')
            try:
                if timestamp_str:
                    last_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if (datetime.now() - last_time).total_seconds() < 3600:
                        conv_id = f"conv_{initiator}_{target}"
                        conversation = Conversation(
                            id=conv_id,
                            participants=[initiator, target],
                            topic=topic,
                            status=ConversationStatus.ACTIVE,
                        )
                        self.active_conversations[conv_id] = conversation
                        return conversation
            except Exception:
                pass

        # Создать новый диалог
        conv_id = f"conv_{initiator}_{target}_{int(time.time())}"
        conversation = Conversation(
            id=conv_id,
            participants=[initiator, target],
            topic=topic,
            status=ConversationStatus.ACTIVE,
        )
        self.active_conversations[conv_id] = conversation
        return conversation

    def get_active_conversation(self, agent_1: str, agent_2: str) -> Optional[Conversation]:
        """Найти активный диалог между двумя агентами."""
        for conv in self.active_conversations.values():
            if (
                agent_1 in conv.participants
                and agent_2 in conv.participants
                and conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
            ):
                return conv
        return None

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Получить диалог по ID."""
        return self.active_conversations.get(conversation_id)

    def is_agent_in_conversation(self, agent_id: str) -> bool:
        """Проверить занят ли агент активным диалогом."""
        for conv in self.active_conversations.values():
            if (
                agent_id in conv.participants
                and conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
            ):
                return True
        return False

    def get_agent_active_conversations(self, agent_id: str) -> List[Conversation]:
        """Получить все активные диалоги агента."""
        return [
            conv for conv in self.active_conversations.values()
            if agent_id in conv.participants
            and conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
        ]

    def end_conversation(self, conversation_id: str):
        """Завершить диалог."""
        conv = self.active_conversations.get(conversation_id)
        if conv:
            conv.status = ConversationStatus.ENDED
            conv.ended_at = time.time()

    # ========================================
    # MESSAGE HANDLING
    # ========================================

    async def send_message(self, message: Message):
        """
        Отправить сообщение:
        1. Сохранить в БД (персистентность).
        2. Обновить статус ожидания в активном диалоге (если есть).
        3. Доставить получателю через in-memory очередь (real-time).
        """
        # 1. Сохранение в БД
        self.db.send_message(
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            content=message.content,
            message_type=message.message_type.value,
            emotion=message.emotion,
            tone=message.tone,
            topic=message.topic,
            conversation_id=message.conversation_id,
            parent_message_id=message.in_reply_to,
        )

        # 2. Обновление метаданных активного диалога
        if message.conversation_id:
            conv = self.active_conversations.get(message.conversation_id)
            if conv:
                conv.last_activity = message.timestamp
                if message.requires_response:
                    conv.waiting_for_response_from = message.receiver_id
                    conv.expected_response_by = message.timestamp + message.response_timeout
                    conv.status = ConversationStatus.WAITING
                else:
                    conv.waiting_for_response_from = None
                    conv.expected_response_by = None
                    if conv.status == ConversationStatus.WAITING:
                        conv.status = ConversationStatus.ACTIVE

        # 3. Real-time доставка
        if message.receiver_id in self.agent_connections:
            await self.agent_connections[message.receiver_id].put(message)
            message.delivered_at = time.time()

    async def receive_messages(self, agent_id: str) -> List[Message]:
        """
        Получить все ожидающие сообщения из очереди агента
        (только real-time уведомления, не история).
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
        """Загрузить историю диалога из БД."""
        db_messages = self.db.get_conversation(agent1_id, agent2_id, limit)
        return [
            Message(
                id=str(db_msg.get('id', uuid.uuid4())),
                sender_id=db_msg['sender_id'],
                receiver_id=db_msg.get('receiver_id', ''),
                content=db_msg['content'],
                message_type=MessageType.STATEMENT,
                emotion=db_msg.get('emotion'),
            )
            for db_msg in db_messages
        ]

    def broadcast_message(self, sender_id: str, content: str, topic: str = "announcement"):
        """Отправить сообщение всем агентам (broadcast)."""
        for agent_id in self.agent_connections:
            if agent_id != sender_id:
                message = Message(
                    sender_id=sender_id,
                    receiver_id=agent_id,
                    content=content,
                    message_type=MessageType.STATEMENT,
                    topic=topic,
                    tone="formal",
                )
                # Сохранить в БД
                self.db.send_message(
                    sender_id=sender_id,
                    receiver_id=agent_id,
                    content=content,
                    message_type="broadcast",
                )
                # Доставить через очередь
                asyncio.create_task(self._deliver_message(agent_id, message))

    async def _deliver_message(self, agent_id: str, message: Message):
        """Доставить сообщение в очередь агента."""
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].put(message)

    # ========================================
    # UTILITY METHODS
    # ========================================

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Получить последние сообщения из БД."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [Message.from_db_row(dict(row)) for row in cursor.fetchall()]

    def get_all_active_conversations(self) -> List[Conversation]:
        """Получить все активные диалоги."""
        return [
            conv for conv in self.active_conversations.values()
            if conv.status in [ConversationStatus.ACTIVE, ConversationStatus.WAITING]
        ]

    def cleanup_old_conversations(self, max_age_hours: float = 24.0) -> int:
        """
        Очистка старых завершённых диалогов из active_conversations.
        Данные остаются в БД.
        """
        current_time = time.time()
        to_remove = [
            conv_id
            for conv_id, conv in self.active_conversations.items()
            if conv.status == ConversationStatus.ENDED
            and (current_time - (conv.ended_at or conv.last_activity)) / 3600 > max_age_hours
        ]
        for conv_id in to_remove:
            self.active_conversations.pop(conv_id)
        return len(to_remove)

    def get_agent_message_count(self, agent_id: str) -> Dict[str, int]:
        """Получить статистику сообщений агента из БД."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE sender_id = ?", (agent_id,))
        sent = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE receiver_id = ?", (agent_id,))
        received = cursor.fetchone()['count']
        return {"sent": sent, "received": received, "total": sent + received}


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
    **kwargs,
) -> Message:
    """Utility-функция для создания сообщения."""
    return Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type,
        conversation_id=conversation_id,
        requires_response=requires_response,
        **kwargs,
    )


def format_conversation_for_llm(
    conversation: Conversation,
    db: Database,
    max_messages: int = 5,
) -> str:
    """
    Форматировать историю диалога для передачи в LLM (загрузка из БД).

    Returns:
        Строка вида "[Alice]: Hello!\\n[Bob]: Hi there!"
    """
    messages = conversation.get_context_for_agent(
        conversation.participants[0],
        max_messages=max_messages,
        db=db,
    )
    return "\n".join(f"[{msg.sender_id}]: {msg.content}" for msg in messages)
