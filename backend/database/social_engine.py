from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from database import Database
from database.social_types import RelationshipVector, SocialEvent, SocialEventType, SocialSentiment
import math

class SocialEngine:
    """
    Модуль социального графа и репутации.
    Управляет отношениями между агентами.
    """
    
    # Веса влияния событий на параметры отношений
    EVENT_WEIGHTS = {
        SocialEventType.HELP: {
            "affinity": 0.15,
            "trust": 0.10,
            "respect": 0.08
        },
        SocialEventType.BETRAY: {
            "affinity": -0.30,
            "trust": -0.40,
            "respect": -0.20
        },
        SocialEventType.COMMUNICATE: {
            "affinity": 0.05,
            "familiarity": 0.10,
            "trust": 0.02
        },
        SocialEventType.GIFT: {
            "affinity": 0.20,
            "trust": 0.15,
            "respect": 0.10
        },
        SocialEventType.INSULT: {
            "affinity": -0.20,
            "respect": -0.15
        },
        SocialEventType.IGNORE: {
            "affinity": -0.05,
            "respect": -0.03
        },
        SocialEventType.SHARE: {
            "affinity": 0.12,
            "trust": 0.08
        },
        SocialEventType.STEAL: {
            "affinity": -0.35,
            "trust": -0.50,
            "respect": -0.25
        },
        SocialEventType.DEFEND: {
            "affinity": 0.25,
            "trust": 0.20,
            "respect": 0.15
        }
    }
    
    # Скорость забывания (decay rate)
    DECAY_RATE = 0.02  # 2% в день к нейтральному значению
    
    def __init__(self, db: Database):
        self.db = db
        self._init_relationships_table()
        self._relationship_cache: Dict[Tuple[str, str], RelationshipVector] = {}
    
    def _init_relationships_table(self):
        """Создать таблицу отношений в SQLite"""
        cursor = self.db.conn.cursor()
        
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
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_pair
            ON relationships(agent_from, agent_to)
        """)
        
        self.db.conn.commit()
    
    def get_relationship(self, agent_from: str, agent_to: str) -> RelationshipVector:
        """
        Получить вектор отношений между агентами.
        Если отношений нет - создать дефолтные.
        """
        # Проверка кэша
        cache_key = (agent_from, agent_to)
        if cache_key in self._relationship_cache:
            return self._relationship_cache[cache_key]
        
        # Поиск в БД
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM relationships
            WHERE agent_from = ? AND agent_to = ?
        """, (agent_from, agent_to))
        
        row = cursor.fetchone()
        
        if row:
            # Десериализация
            import json
            rel = RelationshipVector(
                agent_from=row['agent_from'],
                agent_to=row['agent_to'],
                affinity=row['affinity'],
                trust=row['trust'],
                dominance=row['dominance'],
                familiarity=row['familiarity'],
                respect=row['respect'],
                interaction_count=row['interaction_count'],
                last_interaction=row['last_interaction'],
                history_log=json.loads(row['history_log']) if row['history_log'] else [],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        else:
            # Создать новые отношения (незнакомцы)
            rel = RelationshipVector(
                agent_from=agent_from,
                agent_to=agent_to
            )
            self._save_relationship(rel)
        
        # Кэшировать
        self._relationship_cache[cache_key] = rel
        return rel
    
    def _save_relationship(self, rel: RelationshipVector):
        """Сохранить отношения в БД"""
        import json
        cursor = self.db.conn.cursor()
        
        rel.updated_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO relationships
            (agent_from, agent_to, affinity, trust, dominance, familiarity, respect,
             interaction_count, last_interaction, history_log, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rel.agent_from, rel.agent_to, rel.affinity, rel.trust, rel.dominance,
            rel.familiarity, rel.respect, rel.interaction_count, rel.last_interaction,
            json.dumps(rel.history_log[-10:]), rel.created_at, rel.updated_at
        ))
        
        self.db.conn.commit()
        
        # Обновить кэш
        self._relationship_cache[(rel.agent_from, rel.agent_to)] = rel
    
    def process_social_event(self, event: SocialEvent):
        """
        Обработать социальное событие и обновить отношения.
        
        Args:
            event: Событие для обработки
        """
        # Получить текущие отношения
        rel = self.get_relationship(event.agent_from, event.agent_to)
        
        # Получить веса для типа события
        weights = self.EVENT_WEIGHTS.get(event.event_type, {})
        
        # Множитель от sentiment
        sentiment_multiplier = event.sentiment.value
        
        # Обновить параметры
        for param, weight in weights.items():
            current_value = getattr(rel, param)
            delta = weight * sentiment_multiplier
            
            # Применить с учетом инерции (чем экстремальнее значение, тем медленнее меняется)
            inertia = 1.0 - abs(current_value) * 0.3
            new_value = self._clamp(current_value + delta * inertia, -1.0, 1.0)
            
            setattr(rel, param, new_value)
        
        # Увеличить знакомство (familiarity) при любом взаимодействии
        rel.familiarity = min(1.0, rel.familiarity + 0.05)
        
        # Обновить счетчик и время
        rel.interaction_count += 1
        rel.last_interaction = event.timestamp
        
        # Добавить в историю
        rel.history_log.append({
            "timestamp": event.timestamp,
            "event_type": event.event_type.value,
            "sentiment": event.sentiment.value,
            "description": event.description[:100]
        })
        
        # Сохранить
        self._save_relationship(rel)
        
        # Обработка свидетелей (они тоже меняют мнение)
        for witness_id in event.witnesses:
            if witness_id != event.agent_from and witness_id != event.agent_to:
                self._process_witness_effect(witness_id, event)
        
        print(f"👥 [{event.agent_from} → {event.agent_to}] {event.event_type.value}: "
              f"Affinity={rel.affinity:.2f}, Trust={rel.trust:.2f}")
    
    def _process_witness_effect(self, witness_id: str, event: SocialEvent):
        """
        Обработать эффект свидетеля события.
        Если witness видит, как agent_from делает плохое agent_to, меняет мнение.
        """
        witness_to_actor = self.get_relationship(witness_id, event.agent_from)
        
        # Свидетель меняет мнение о действующем агенте
        if event.sentiment.value < 0:
            # Негативное событие - доверие к актору падает
            witness_to_actor.affinity = self._clamp(
                witness_to_actor.affinity - 0.05,
                -1.0, 1.0
            )
            witness_to_actor.trust = self._clamp(
                witness_to_actor.trust - 0.08,
                0.0, 1.0
            )
        else:
            # Позитивное - растет уважение
            witness_to_actor.respect = self._clamp(
                witness_to_actor.respect + 0.03,
                0.0, 1.0
            )
        
        self._save_relationship(witness_to_actor)
    
    def apply_relationship_decay(self, agent_id: str, days_passed: float = 1.0):
        """
        Применить забывание: отношения стремятся к нейтральным без взаимодействий.
        
        Args:
            agent_id: ID агента
            days_passed: Сколько дней прошло
        """
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM relationships
            WHERE agent_from = ? OR agent_to = ?
        """, (agent_id, agent_id))
        
        rows = cursor.fetchall()
        
        for row in rows:
            last_interaction = row['last_interaction']
            if not last_interaction:
                continue
            
            # Проверить, сколько времени прошло
            last_time = datetime.fromisoformat(last_interaction)
            time_delta = datetime.now() - last_time
            days_idle = time_delta.total_seconds() / 86400
            
            if days_idle < days_passed:
                continue
            
            # Применить decay
            decay_factor = self.DECAY_RATE * days_idle
            
            import json
            affinity = row['affinity']
            trust = row['trust']
            
            # Affinity стремится к 0, Trust к 0.5 (нейтраль)
            new_affinity = affinity * (1.0 - decay_factor)
            new_trust = trust + (0.5 - trust) * decay_factor
            
            cursor.execute("""
                UPDATE relationships
                SET affinity = ?, trust = ?
                WHERE id = ?
            """, (new_affinity, new_trust, row['id']))
        
        self.db.conn.commit()
    
    def get_social_context_for_llm(self, agent_id: str, target_id: str) -> str:
        """
        Сформировать блок SOCIAL CONTEXT для промпта LLM.
        
        Returns:
            Текстовое описание отношений для промпта
        """
        rel = self.get_relationship(agent_id, target_id)
        
        context = f"""СОЦИАЛЬНЫЙ КОНТЕКСТ (отношение {agent_id} к {target_id}):
- Отношение: {rel.get_relationship_label()} (симпатия: {rel.affinity:.2f})
- Доверие: {rel.get_trust_label()} ({rel.trust:.2f})
- Знакомство: {"Близкий друг" if rel.familiarity > 0.7 else "Знакомый" if rel.familiarity > 0.3 else "Малознакомый"}
- Уважение: {"Высокое" if rel.respect > 0.7 else "Среднее" if rel.respect > 0.4 else "Низкое"}
- Взаимодействий: {rel.interaction_count}"""
        
        # Добавить последние значимые события
        if rel.history_log:
            recent = rel.history_log[-3:]
            context += "\n\nПоследние события:"
            for event in recent:
                context += f"\n  - {event['description']}"
        
        return context
    
    def get_filtered_belief_credibility(self, believer_id: str, source_id: str) -> float:
        """
        Получить коэффициент доверия к информации от source_id.
        Используется для фильтрации убеждений (Filtered Beliefs).
        
        Returns:
            float от 0.0 до 1.0 (насколько верить информации)
        """
        rel = self.get_relationship(believer_id, source_id)
        return rel.trust
    
    def get_desire_multiplier(self, agent_id: str, target_id: str, desire_type: str) -> float:
        """
        Получить множитель приоритета желания в зависимости от отношений.
        
        Args:
            desire_type: "help", "communicate", "attack", etc.
        
        Returns:
            Множитель от 0.0 (блокировать) до 2.0 (усилить)
        """
        rel = self.get_relationship(agent_id, target_id)
        
        if desire_type == "help":
            # Чем больше симпатия, тем больше желание помочь
            return max(0.0, 1.0 + rel.affinity)
        
        elif desire_type == "communicate":
            # Зависит от симпатии и знакомства
            return 0.5 + rel.affinity * 0.5 + rel.familiarity * 0.5
        
        elif desire_type == "attack" or desire_type == "conflict":
            # Чем меньше симпатия, тем выше желание конфликта
            return max(0.0, 1.0 - rel.affinity)
        
        elif desire_type == "trust_info":
            # Доверять информации от этого агента
            return rel.trust
        
        else:
            return 1.0
    
    def get_all_relationships(self, agent_id: str) -> List[RelationshipVector]:
        """Получить все отношения агента"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM relationships
            WHERE agent_from = ?
            ORDER BY affinity DESC
        """, (agent_id,))
        
        import json
        relationships = []
        for row in cursor.fetchall():
            rel = RelationshipVector(
                agent_from=row['agent_from'],
                agent_to=row['agent_to'],
                affinity=row['affinity'],
                trust=row['trust'],
                dominance=row['dominance'],
                familiarity=row['familiarity'],
                respect=row['respect'],
                interaction_count=row['interaction_count'],
                last_interaction=row['last_interaction'],
                history_log=json.loads(row['history_log']) if row['history_log'] else []
            )
            relationships.append(rel)
        
        return relationships
    
    def get_graph_data(self) -> Dict:
        """
        Получить данные для визуализации графа отношений.
        
        Returns:
            {"nodes": [...], "edges": [...]}
        """
        cursor = self.db.conn.cursor()
        
        # Получить всех агентов
        cursor.execute("SELECT id, name FROM agents")
        agents = cursor.fetchall()
        
        nodes = [{"id": a['id'], "name": a['name']} for a in agents]
        
        # Получить значимые отношения (|affinity| > 0.1)
        cursor.execute("""
            SELECT agent_from, agent_to, affinity, trust
            FROM relationships
            WHERE ABS(affinity) > 0.1
        """)
        
        edges = []
        for row in cursor.fetchall():
            edges.append({
                "from": row['agent_from'],
                "to": row['agent_to'],
                "affinity": round(row['affinity'], 2),
                "trust": round(row['trust'], 2),
                "color": self._get_edge_color(row['affinity'])
            })
        
        return {"nodes": nodes, "edges": edges}
    
    def _get_edge_color(self, affinity: float) -> str:
        """Получить цвет ребра графа по симпатии"""
        if affinity > 0.5:
            return "#00ff00"  # Зеленый (друзья)
        elif affinity > 0.2:
            return "#88ff88"  # Светло-зеленый
        elif affinity > -0.2:
            return "#888888"  # Серый (нейтраль)
        elif affinity > -0.5:
            return "#ff8888"  # Светло-красный
        else:
            return "#ff0000"  # Красный (враги)
    
    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Ограничить значение диапазоном"""
        return max(min_val, min(max_val, value))


def get_social_engine() -> SocialEngine:
    """
    FastAPI dependency для получения SocialEngine
    Возвращает singleton экземпляр
    """
    db = Database()
    return SocialEngine(db)