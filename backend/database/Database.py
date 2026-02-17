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
                personality TEXT,
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
        # 4. EVENTS LOG
        # ============================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                agent_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT NOT NULL,
                target_agent TEXT,
                emotion_before TEXT,
                emotion_after TEXT,
                metadata TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events_log(timestamp DESC)")
        
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
        
        # Добавить в events_log
        description = f"{sender_id} → {receiver_id or 'все'}: {content[:50]}..."
        cursor.execute("""
            INSERT INTO events_log
            (agent_id, action_type, description, target_agent, emotion_after)
            VALUES (?, ?, ?, ?, ?)
        """, (sender_id, "chat", description, receiver_id, emotion))
        
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
    
    def add_agent(self, agent_id: str, name: str, personality: str, avatar: str = "🤖") -> bool:
        """Добавить агента"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
            if cursor.fetchone():
                print(f"⚠️  Агент {agent_id} уже существует")
                return False
            
            cursor.execute("""
                INSERT INTO agents (id, name, personality, avatar, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (agent_id, name, personality, avatar, datetime.now().isoformat()))
            
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
