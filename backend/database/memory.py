from typing import List, Dict, Optional
from datetime import datetime, timedelta
from database import Database
import uuid
import requests
from collections import defaultdict

class VectorMemory:
    """
    Высокоуровневый интерфейс для работы с эпизодической памятью агентов.
    Использует векторную БД через Database класс.
    """
    
    def __init__(self, db: Database):
        """
        Args:
            db: Экземпляр Database с доступом к ChromaDB
        """
        self.db = db
        self.memories_collection = db.memories
    
    def add_episodic_memory(
        self,
        agent_id: str,
        event_description: str,
        event_type: str = "observation",  # observation, interaction, action, goal
        emotion: str = "neutral",
        importance: float = 0.5,  # 0-1
        participants: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Добавить эпизодическое воспоминание в векторную память.
        
        Args:
            agent_id: ID агента
            event_description: Описание события (текст)
            event_type: Тип события
            emotion: Эмоция агента во время события
            importance: Важность события (0-1)
            participants: Другие агенты, участвующие в событии
            metadata: Дополнительные данные
        
        Returns:
            memory_id: UUID созданного воспоминания
        
        Example:
            >>> memory = VectorMemory(db)
            >>> memory.add_episodic_memory(
            ...     agent_id="alice",
            ...     event_description="Alice встретила Bob на площади и они поговорили о погоде",
            ...     event_type="interaction",
            ...     emotion="happy",
            ...     importance=0.7,
            ...     participants=["bob"]
            ... )
        """
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Формируем метаданные
        memory_metadata = {
            "agent_id": agent_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "emotion": emotion,
            "importance": importance
        }
        
        # Добавляем участников
        if participants:
            memory_metadata["participants"] = ",".join(participants)
        
        # Дополнительные метаданные
        if metadata:
            memory_metadata.update(metadata)
        
        # Сохраняем в ChromaDB
        self.memories_collection.add(
            ids=[memory_id],
            documents=[event_description],
            metadatas=[memory_metadata]
        )
        
        # Обновляем счетчик памяти в SQLite
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE agents 
            SET memory_count = memory_count + 1 
            WHERE id = ?
        """, (agent_id,))
        self.db.conn.commit()
        
        
        return memory_id
    
    def recall_relevant_memories(
        self,
        agent_id: str,
        current_situation: str,
        n_results: int = 5,
        event_type: Optional[str] = None,
        min_importance: Optional[int] = None,
        time_window_days: Optional[int] = None
    ) -> List[Dict]:
        """
        Извлечь релевантные воспоминания для текущей ситуации.
        
        Args:
            agent_id: ID агента
            current_situation: Описание текущей ситуации или вопроса
            n_results: Количество воспоминаний (топ-N)
            event_type: Фильтр по типу события (опционально)
            min_importance: Минимальная важность (опционально)
            time_window_days: Учитывать только последние N дней (опционально)
        
        Returns:
            Список релевантных воспоминаний с метаданными
        
        Example:
            >>> memories = memory.recall_relevant_memories(
            ...     agent_id="alice",
            ...     current_situation="Bob предлагает разделить клад",
            ...     n_results=3,
            ...     event_type="interaction"
            ... )
            >>> for mem in memories:
            ...     print(mem['text'], mem['importance'])
        """
        # Формируем фильтры для метаданных
        where_filter = {"agent_id": agent_id}
        
        if event_type:
            where_filter["event_type"] = event_type
        
        if min_importance:
            where_filter["importance"] = {"$gte": min_importance}
        
        # Фильтр по времени
        if time_window_days:
            cutoff_date = (datetime.now() - timedelta(days=time_window_days)).isoformat()
            where_filter["timestamp"] = {"$gte": cutoff_date}
        
        # Семантический поиск в ChromaDB
        results = self.memories_collection.query(
            query_texts=[current_situation],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Форматируем результаты
        memories = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                memory = {
                    "text": doc,
                    "metadata": results['metadatas'][0][i],
                    "relevance_score": 1 - results['distances'][0][i],  # Чем ближе, тем релевантнее
                    "timestamp": results['metadatas'][0][i].get('timestamp'),
                    "emotion": results['metadatas'][0][i].get('emotion'),
                    "importance": results['metadatas'][0][i].get('importance'),
                    "event_type": results['metadatas'][0][i].get('event_type')
                }
                memories.append(memory)
        
        
        return memories
    
    def get_key_memories(
        self,
        agent_id: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Получить ключевые (самые важные) воспоминания агента.
        
        Args:
            agent_id: ID агента
            n_results: Количество воспоминаний
        
        Returns:
            Список самых важных воспоминаний
        """
        # Поиск воспоминаний с высокой важностью
        results = self.memories_collection.get(
            where={
                "$and": [
                    {"agent_id": agent_id},
                    {"importance": {"$gte": 7}}  # Важность >= 7
                ]
            },
            limit=n_results,
            include=["documents", "metadatas"]
        )
        
        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents']):
                memories.append({
                    "text": doc,
                    "metadata": results['metadatas'][i]
                })
        
        return memories
    
    def recall_memories_about_agent(
        self,
        agent_id: str,
        target_agent_id: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Вспомнить все взаимодействия с конкретным агентом.
        
        Args:
            agent_id: Кто вспоминает
            target_agent_id: О ком вспоминает
            n_results: Количество воспоминаний
        
        Returns:
            Список воспоминаний о target_agent
        
        Example:
            >>> # Alice вспоминает все о Bob
            >>> memories = memory.recall_memories_about_agent("alice", "bob")
        """
        # Поиск по участникам в метаданных
        results = self.memories_collection.get(
            where={
                "$and": [
                    {"agent_id": agent_id},
                    {"participants": {"$contains": target_agent_id}}
                ]
            },
            limit=n_results,
            include=["documents", "metadatas"]
        )
        
        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents']):
                memories.append({
                    "text": doc,
                    "metadata": results['metadatas'][i]
                })
        
        
        return memories
    
    def get_recent_memories(
        self,
        agent_id: str,
        days: int = 1,
        n_results: int = 20
    ) -> List[Dict]:
        """
        Получить недавние воспоминания (кратковременная память).
        
        Args:
            agent_id: ID агента
            days: За последние N дней
            n_results: Максимум воспоминаний
        
        Returns:
            Список недавних воспоминаний
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        results = self.memories_collection.get(
            where={
                "$and": [
                    {"agent_id": agent_id},
                    {"timestamp": {"$gte": cutoff_date}}
                ]
            },
            limit=n_results,
            include=["documents", "metadatas"]
        )
        
        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents']):
                memories.append({
                    "text": doc,
                    "metadata": results['metadatas'][i]
                })
        
        return memories
    
    def format_memories_for_llm(self, memories: List[Dict]) -> str:
        """
        Форматировать воспоминания для промпта LLM.
        
        Args:
            memories: Список воспоминаний из recall_relevant_memories()
        
        Returns:
            Отформатированная строка для промпта
        
        Example:
            >>> memories = memory.recall_relevant_memories("alice", "клад")
            >>> prompt_text = memory.format_memories_for_llm(memories)
            >>> prompt = f"Воспоминания:\n{prompt_text}\n\nСитуация: найден клад"
        """
        if not memories:
            return "Нет релевантных воспоминаний."
        
        formatted = []
        for i, mem in enumerate(memories, 1):
            timestamp = mem['timestamp'][:10] if mem.get('timestamp') else "неизвестно"
            emotion = mem.get('emotion', 'neutral')
            importance = mem.get('importance', 5)
            
            formatted.append(
                f"{i}. [{timestamp}] ({emotion}, важность: {importance}/10)\n"
                f"   {mem['text']}"
            )
        
        return "\n\n".join(formatted)
    
    def summarize_old_memories(
        self,
        agent_id: str,
        older_than_days: int = 7,
        openrouter_api_key: str = None,
        model: str = "openai/gpt-3.5-turbo",
        min_memories_to_summarize: int = 10,
        cluster_by: str = "participants"  # participants, event_type, emotion
    ):
        """
        Суммаризовать старые воспоминания для экономии места.
        Группирует воспоминания по кластерам и создаёт сжатые версии через LLM.
        
        Args:
            agent_id: ID агента
            older_than_days: Воспоминания старше N дней
            openrouter_api_key: API ключ OpenRouter
            model: Модель для суммаризации (например, "openai/gpt-3.5-turbo")
            min_memories_to_summarize: Минимум воспоминаний для запуска
            cluster_by: По какому признаку группировать (participants/event_type/emotion)
        
        Returns:
            dict: Статистика суммаризации
        
        Example:
            >>> memory.summarize_old_memories(
            ...     agent_id="alice",
            ...     older_than_days=7,
            ...     openrouter_api_key="sk-or-v1-...",
            ...     model="openai/gpt-4o-mini",
            ...     cluster_by="participants"
            ... )
        """
        if not openrouter_api_key:
            print(f"⚠️  [{agent_id}] OpenRouter API ключ не предоставлен")
            return {"error": "API key required"}
        
        cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
        
        # 1. Получить старые воспоминания
        old_memories = self.memories_collection.get(
            where={
                "$and": [
                    {"agent_id": agent_id},
                    {"timestamp": {"$lt": cutoff_date}}
                ]
            },
            include=["documents", "metadatas", "ids"]
        )
        
        if not old_memories['documents'] or len(old_memories['documents']) < min_memories_to_summarize:
            print(f"[{agent_id}] Недостаточно старых воспоминаний для суммаризации "
                  f"({len(old_memories['documents']) if old_memories['documents'] else 0}/{min_memories_to_summarize})")
            return {"status": "skipped", "reason": "not enough memories"}
        
        
        # 2. Группировка по кластерам
        clusters = self._cluster_memories(
            old_memories['documents'],
            old_memories['metadatas'],
            old_memories['ids'],
            cluster_by=cluster_by
        )
        
        
        # 3. Суммаризация каждого кластера через LLM
        summarized_count = 0
        deleted_count = 0
        
        for cluster_key, cluster_data in clusters.items():
            if len(cluster_data['documents']) < 3:
                # Слишком мало воспоминаний в кластере - пропускаем
                continue
            
            
            # Суммаризовать через OpenRouter
            summary = self._call_openrouter_summarize(
                memories=cluster_data['documents'],
                cluster_context=cluster_key,
                agent_id=agent_id,
                api_key=openrouter_api_key,
                model=model
            )
            
            if summary:
                # Вычислить среднюю важность
                avg_importance = sum(m.get('importance', 5) for m in cluster_data['metadatas']) // len(cluster_data['metadatas'])
                
                # Определить временной период
                timestamps = [m.get('timestamp', '') for m in cluster_data['metadatas']]
                time_period = f"{min(timestamps)[:10]} - {max(timestamps)[:10]}"
                
                # Добавить сжатое воспоминание
                self.add_episodic_memory(
                    agent_id=agent_id,
                    event_description=summary,
                    event_type="summary",
                    emotion="neutral",
                    importance=avg_importance,
                    metadata={
                        "is_summary": True,
                        "original_count": len(cluster_data['documents']),
                        "time_period": time_period,
                        "cluster_key": cluster_key
                    }
                )
                
                # Удалить оригинальные воспоминания
                self.memories_collection.delete(ids=cluster_data['ids'])
                
                summarized_count += 1
                deleted_count += len(cluster_data['ids'])
                
        
        result = {
            "status": "completed",
            "agent_id": agent_id,
            "clusters_processed": summarized_count,
            "memories_deleted": deleted_count,
            "memories_created": summarized_count
        }
        
        
        return result
    
    def _cluster_memories(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
        cluster_by: str
    ) -> Dict[str, Dict]:
        """
        Группировка воспоминаний по выбранному признаку.
        
        Returns:
            Dict[cluster_key, {"documents": [...], "metadatas": [...], "ids": [...]}]
        """
        clusters = defaultdict(lambda: {"documents": [], "metadatas": [], "ids": []})
        
        for doc, meta, mem_id in zip(documents, metadatas, ids):
            # Определить ключ кластера
            if cluster_by == "participants":
                # Группировать по участникам
                participants = meta.get('participants', '')
                key = participants if participants else "_solo_"
            
            elif cluster_by == "event_type":
                # Группировать по типу события
                key = meta.get('event_type', 'general')
            
            elif cluster_by == "emotion":
                # Группировать по эмоции
                key = meta.get('emotion', 'neutral')
            
            else:
                key = "general"
            
            # Добавить в кластер
            clusters[key]["documents"].append(doc)
            clusters[key]["metadatas"].append(meta)
            clusters[key]["ids"].append(mem_id)
        
        return dict(clusters)
    
    def _call_openrouter_summarize(
        self,
        memories: List[str],
        cluster_context: str,
        agent_id: str,
        api_key: str,
        model: str
    ) -> Optional[str]:
        """
        Вызвать OpenRouter API для суммаризации воспоминаний.
        
        Args:
            memories: Список текстов воспоминаний
            cluster_context: Контекст кластера (например, "bob" или "interaction")
            agent_id: ID агента
            api_key: OpenRouter API ключ
            model: Модель для использования
        
        Returns:
            Сжатый текст или None при ошибке
        """
        # Формируем промпт для суммаризации
        memories_text = "\n".join([f"- {mem}" for mem in memories])
        
        prompt = f"""Ты - система сжатия памяти для AI-агента по имени {agent_id}.

ЗАДАЧА:
Суммаризуй следующие воспоминания в ОДНО связное предложение (максимум 2-3 предложения).
Сохрани ключевые события, эмоции и важные детали.
Контекст группы: {cluster_context}

ВОСПОМИНАНИЯ ДЛЯ СЖАТИЯ:
{memories_text}

ИНСТРУКЦИЯ:
- Объедини похожие события
- Сохрани важные имена и действия
- Используй прошедшее время
- Будь кратким и ёмким
- НЕ добавляй вводные фразы типа "Агент делал..."

СЖАТАЯ ВЕРСИЯ:"""

        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/your-hackathon-project",  # Опционально
                    "X-Title": "AI Agents Simulator",  # Опционально
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Низкая температура для точности
                    "max_tokens": 150
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            summary = result['choices'][0]['message']['content'].strip()
            
            return summary
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка OpenRouter API: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"❌ Ошибка парсинга ответа: {e}")
            return None
        

def get_memory() -> VectorMemory:
    """
    FastAPI dependency для получения VectorMemory
    Возвращает singleton экземпляр
    """
    db = Database()
    return VectorMemory(db) 