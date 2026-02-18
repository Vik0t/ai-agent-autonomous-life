# backend/database/Database.py

import sqlite3
import chromadb
from datetime import datetime
from typing import Optional, List, Dict

class Database:
    def __init__(self):
        # SQLite для структурированных данных
        self.conn = sqlite3.connect('database/agents.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # для dict-like доступа
        
        # ChromaDB для векторной памяти
        self.chroma_client = chromadb.PersistentClient(path="database/chroma_data")
        self.memories = self._get_or_create_collection("agent_memories")
        
        self._init_tables()
    
    def _init_tables(self):
        cursor = self.conn.cursor()
        
        # ============================================
        # 1. AGENTS (расширенная версия)
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                avatar TEXT DEFAULT '🤖',
                openness FLOAT DEFAULT 0.0,
                conscientiousness FLOAT DEFAULT 0.0,
                extraversion FLOAT DEFAULT 0.0,
                agreeableness FLOAT DEFAULT 0.0,
                neuroticism FLOAT DEFAULT 0.0,
                memory_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_active TEXT
            )
        """)
        
        # ============================================
        # 2. MESSAGES
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                sender_id TEXT NOT NULL,
                receiver_id TEXT,
                message_type TEXT NOT NULL CHECK(message_type IN ('direct', 'broadcast', 'system')),
                content TEXT NOT NULL,
                emotion TEXT,
                is_read BOOLEAN DEFAULT 0,
                parent_message_id INTEGER,
                FOREIGN KEY (sender_id) REFERENCES agents(id),
                FOREIGN KEY (receiver_id) REFERENCES agents(id),
                FOREIGN KEY (parent_message_id) REFERENCES messages(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(sender_id, receiver_id, timestamp)")
        
        # ============================================
        # 3. RELATIONSHIPS (НОВАЯ СТРУКТУРА для Social Engine)
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_from TEXT NOT NULL,
                agent_to TEXT NOT NULL,
                affinity REAL DEFAULT 0.0,
                trust REAL DEFAULT 0.5,
                dominance REAL DEFAULT 0.0,
                familiarity REAL DEFAULT 0.0,
                respect REAL DEFAULT 0.5,
                interaction_count INTEGER DEFAULT 0,
                last_interaction TEXT,
                history_log TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(agent_from, agent_to),
                FOREIGN KEY (agent_from) REFERENCES agents(id),
                FOREIGN KEY (agent_to) REFERENCES agents(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_pair ON relationships(agent_from, agent_to)")
        
        # ============================================
        # 4. EVENTS LOG (ОБНОВЛЁННАЯ СТРУКТУРА)
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events_log (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                agent_ids TEXT,
                data TEXT,
                timestamp REAL NOT NULL
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events_log(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events_log(type)")
        
        self.conn.commit()
        print("✅ Все таблицы инициализированы")
        
        # ================== МЕТОДЫ ДЛЯ ЧАТОВ ==================
    
    def send_message(
        self,
        sender_id: str,
        content: str,
        receiver_id: Optional[str] = None,
        message_type: str = "direct",
        emotion: Optional[str] = None,
        parent_message_id: Optional[int] = None
    ) -> int:
        """Отправить сообщение"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO messages
            (sender_id, receiver_id, message_type, content, emotion, parent_message_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, message_type, content, emotion, parent_message_id))
        message_id = cursor.lastrowid
        
        self.conn.commit()
        return message_id
    
    def get_conversation(self, agent1_id: str, agent2_id: str, limit: int = 50) -> List[Dict]:
        """Получить историю разговора"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE (sender_id = ? AND receiver_id = ?)
            OR (sender_id = ? AND receiver_id = ?)
            ORDER BY id DESC
            LIMIT ?
        """, (agent1_id, agent2_id, agent2_id, agent1_id, limit))
        messages = [dict(row) for row in cursor.fetchall()]
        return list(reversed(messages))
    
    def get_agent_messages(self, agent_id: str, message_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Получить все сообщения агента"""
        cursor = self.conn.cursor()
        if message_type:
            cursor.execute("""
                SELECT * FROM messages
                WHERE (sender_id = ? OR receiver_id = ?)
                AND message_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_id, agent_id, message_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM messages
                WHERE sender_id = ? OR receiver_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_id, agent_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unread_messages(self, agent_id: str) -> List[Dict]:
        """Получить непрочитанные сообщения"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE receiver_id = ? AND is_read = 0
            ORDER BY timestamp ASC
        """, (agent_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def mark_as_read(self, message_id: int):
        """Отметить как прочитанное"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
        self.conn.commit()
    
    def get_broadcast_messages(self, limit: int = 20) -> List[Dict]:
        """Получить публичные сообщения"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE message_type = 'broadcast'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ================== МЕТОДЫ ДЛЯ ПАМЯТИ ==================
    
    def add_memory(
        self,
        agent_id: str,
        event_text: str,
        emotion: str,
        event_type: str = "general",
        importance: int = 5,
        participants: Optional[List[str]] = None
    ):
        """Добавить воспоминание в ChromaDB"""
        import uuid
        memory_id = str(uuid.uuid4())
        metadata = {
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
            "emotion": emotion,
            "event_type": event_type,
            "importance": importance
        }
        
        if participants:
            metadata["participants"] = ",".join(participants)
        
        self.memories.add(
            ids=[memory_id],
            documents=[event_text],
            metadatas=[metadata]
        )
        
        # Обновить счетчик
        cursor = self.conn.cursor()
        cursor.execute("UPDATE agents SET memory_count = memory_count + 1 WHERE id = ?", (agent_id,))
        self.conn.commit()
    
    def search_memories(self, agent_id: str, query: str, n_results: int = 5, event_type: Optional[str] = None) -> Dict:
        """Найти релевантные воспоминания"""
        where_filter = {"agent_id": agent_id}
        if event_type:
            where_filter["event_type"] = event_type
        
        return self.memories.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
    
    # ================== УПРАВЛЕНИЕ АГЕНТАМИ ==================
    
    def add_agent(self, agent_id: str, name: str, openness: float, conscientiousness: float, extraversion: float, 
                  agreeableness: float, neuroticism: float, avatar: str = "🤖") -> bool:
        print("Adding agent")
        """Добавить агента"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
            if cursor.fetchone():
                print(f"⚠️  Агент {agent_id} уже существует")
                return False
            
            cursor.execute("""
                INSERT INTO agents (id, name, openness, conscientiousness, extraversion, 
                  agreeableness, neuroticism, avatar, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, name, openness, conscientiousness, extraversion, 
                  agreeableness, neuroticism, avatar, datetime.now().isoformat()))
            
            self.conn.commit()
            print(f"✅ Агент {name} ({agent_id}) добавлен")
            return True
        except Exception as e:
            print(f"❌ Ошибка добавления агента: {e}")
            return False
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Получить агента"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_agents(self) -> List[Dict]:
        """Получить всех агентов"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agents ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_agent(self, agent_id: str) -> bool:
        """Удалить агента и все связанные данные"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            cursor.execute("DELETE FROM relationships WHERE agent_from = ? OR agent_to = ?", (agent_id, agent_id))
            cursor.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (agent_id, agent_id))
            self.conn.commit()
            
            # Удалить из ChromaDB
            try:
                self.memories.delete(where={"agent_id": agent_id})
            except:
                pass
            
            print(f"🗑️  Агент {agent_id} удалён")
            return True
        except Exception as e:
            print(f"❌ Ошибка удаления: {e}")
            return False
        

# ================== МЕТОДЫ ДЛЯ СОБЫТИЙ ==================

    def add_event(
        self,
        event: Dict,
    ) -> str:
        """
        Добавить событие в лог
        
        Args:
            event_type: Тип события (chat, action, emotion, memory, etc.)
            description: Описание события
            agent_ids: Список ID агентов участвующих в событии
            data: Дополнительные данные события (dict)
            event_id: ID события (генерируется автоматически если не указан)
            timestamp: Unix timestamp (текущее время если не указан)
        
        Returns:
            ID созданного события
        
        Example:
            >>> db.add_event(
            ...     event_type="chat",
            ...     description="Алекса отправила сообщение Нексусу",
            ...     agent_ids=["agent-0", "agent-1"],
            ...     data={"message": "Привет!", "emotion": "happy"}
            ... )
        """
        import json
        import uuid
        import time
        
        # Преобразовать списки и dict в JSON
        agent_ids_str = json.dumps(event.get("agents_ids") or [])
        data_str = json.dumps(event.get("data") or {})
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events_log
            (id, type, description, agent_ids, data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.get("id"),
            event.get("type"),
            event.get("description"),
            agent_ids_str,
            data_str,
            event.get("timestamp"),
        ))
        
        self.conn.commit()
        return event.get("id")


    def get_events(
        self,
        limit: int = 20,
        event_type: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить события из лога
        
        Args:
            limit: Максимальное количество событий
            event_type: Фильтр по типу события (опционально)
            agent_id: Фильтр по участвующему агенту (опционально)
        
        Returns:
            Список событий в формате:
            {
                "id": str,
                "type": str,
                "description": str,
                "agent_ids": List[str],
                "data": Dict,
                "timestamp": float
            }
        
        Example:
            >>> # Все последние события
            >>> events = db.get_events(limit=10)
            
            >>> # События конкретного типа
            >>> events = db.get_events(event_type="chat", limit=15)
            
            >>> # События с участием агента
            >>> events = db.get_events(agent_id="agent-0", limit=5)
        """
        import json
        
        cursor = self.conn.cursor()
        
        # Построить запрос с фильтрами
        query = "SELECT * FROM events_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        
        if agent_id:
            # Поиск агента в JSON массиве
            query += " AND agent_ids LIKE ?"
            params.append(f'%"{agent_id}"%')
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            event = dict(row)
            
            # Парсинг JSON полей
            try:
                event['agent_ids'] = json.loads(event.get('agent_ids', '[]'))
            except:
                event['agent_ids'] = []
            
            try:
                event['data'] = json.loads(event.get('data', '{}'))
            except:
                event['data'] = {}
            
            events.append(event)
        
        return events


    def get_agent_events(self, agent_id: str, limit: int = 20) -> List[Dict]:
        """
        Получить все события агента
        
        Args:
            agent_id: ID агента
            limit: Максимальное количество событий
        
        Returns:
            Список событий
        """
        return self.get_events(limit=limit, agent_id=agent_id)


    def get_events_by_type(self, event_type: str, limit: int = 20) -> List[Dict]:
        """
        Получить события определённого типа
        
        Args:
            event_type: Тип события (chat, action, emotion, etc.)
            limit: Максимальное количество
        
        Returns:
            Список событий
        """
        return self.get_events(limit=limit, event_type=event_type)


    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """
        Получить событие по ID
        
        Args:
            event_id: ID события
        
        Returns:
            Событие или None если не найдено
        """
        import json
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events_log WHERE id = ?", (event_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        event = dict(row)
        
        # Парсинг JSON полей
        try:
            event['agent_ids'] = json.loads(event.get('agent_ids', '[]'))
        except:
            event['agent_ids'] = []
        
        try:
            event['data'] = json.loads(event.get('data', '{}'))
        except:
            event['data'] = {}
        
        return event


    def count_events(
        self,
        event_type: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> int:
        """
        Подсчитать количество событий
        
        Args:
            event_type: Фильтр по типу (опционально)
            agent_id: Фильтр по агенту (опционально)
        
        Returns:
            Количество событий
        """
        cursor = self.conn.cursor()
        
        query = "SELECT COUNT(*) as count FROM events_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        
        if agent_id:
            query += " AND agent_ids LIKE ?"
            params.append(f'%"{agent_id}"%')
        
        cursor.execute(query, params)
        return cursor.fetchone()['count']


    def delete_event(self, event_id: str) -> bool:
        """
        Удалить событие по ID
        
        Args:
            event_id: ID события
        
        Returns:
            True если удалено, False если не найдено
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM events_log WHERE id = ?", (event_id,))
        self.conn.commit()
        
        return cursor.rowcount > 0


    def delete_old_events(self, older_than_seconds: int = 604800) -> int:
        """
        Удалить старые события
        
        Args:
            older_than_seconds: Удалить события старше N секунд (по умолчанию 7 дней)
        
        Returns:
            Количество удалённых событий
        """
        import time
        
        cutoff_timestamp = time.time() - older_than_seconds
        
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM events_log
            WHERE timestamp < ?
        """, (cutoff_timestamp,))
        
        deleted_count = cursor.rowcount
        self.conn.commit()
        
        print(f"🗑️  Удалено {deleted_count} старых событий")
        return deleted_count


    def clear_all_events(self) -> int:
        """
        Удалить все события (осторожно!)
        
        Returns:
            Количество удалённых событий
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM events_log")
        count = cursor.fetchone()['count']
        
        cursor.execute("DELETE FROM events_log")
        self.conn.commit()
        
        print(f"🗑️  Удалено всех событий: {count}")
        return count

    
    # ================== ВСПОМОГАТЕЛЬНЫЕ ==================
    
    def _get_or_create_collection(self, name: str):
        """Получить или создать коллекцию ChromaDB"""
        try:
            return self.chroma_client.get_collection(name)
        except:
            return self.chroma_client.create_collection(name)


# ========== DEPENDENCY INJECTION ==========
def get_db() -> Database:
    """FastAPI dependency"""
    return Database()
