"""
Desire System - Система желаний/целей агента

Desire (желание) - это цель, которую агент хочет достичь.
DesireGenerator - генерирует желания на основе личности, эмоций и ситуации.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class DesireStatus(Enum):
    """Статус желания"""
    ACTIVE = "active"           # Активно, можно преследовать
    PURSUED = "pursued"         # В процессе достижения (есть намерение)
    ACHIEVED = "achieved"       # Достигнуто
    ABANDONED = "abandoned"     # Оставлено
    IMPOSSIBLE = "impossible"   # Невозможно достичь


class MotivationType(Enum):
    """
    Типы мотивации (упрощённая иерархия Маслоу)
    """
    SURVIVAL = "survival"           # Базовые потребности (энергия, здоровье)
    SAFETY = "safety"               # Безопасность
    SOCIAL = "social"               # Социальные связи, общение
    ESTEEM = "esteem"               # Уважение, признание
    ACHIEVEMENT = "achievement"     # Достижения, самореализация
    CURIOSITY = "curiosity"         # Познание, исследование


@dataclass
class Desire:
    """
    Цель/желание агента
    
    Примеры:
        - "Поговорить с Алисой о проекте"
        - "Найти тихое место для размышлений"
        - "Изучить новую информацию"
        - "Помочь другу с проблемой"
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    priority: float = 0.5       # 0.0 - 1.0, насколько важно
    urgency: float = 0.5        # 0.0 - 1.0, насколько срочно
    status: DesireStatus = DesireStatus.ACTIVE
    
    # Мотивация
    motivation_type: MotivationType = MotivationType.SOCIAL
    source: str = "personality" # Откуда возникло: personality, emotion, event, external
    
    # Условия
    preconditions: List[str] = field(default_factory=list)      # Что нужно для начала
    success_conditions: List[str] = field(default_factory=list) # Критерии успеха
    
    # Связь с личностью
    personality_alignment: float = 0.5  # Насколько соответствует личности (0-1)
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)  # Дополнительная информация
    
    def calculate_utility(self) -> float:
        """
        Вычислить полезность/ценность цели
        
        Формула: priority * urgency * personality_alignment
        """
        return self.priority * self.urgency * self.personality_alignment
    
    def is_achievable(self, beliefs_query_func) -> bool:
        """
        Проверить, достижима ли цель на основе текущих убеждений
        
        Args:
            beliefs_query_func: Функция для поиска убеждений
        """
        # Если нет preconditions, считаем достижимой
        if not self.preconditions:
            return True
        
        # Проверяем каждое precondition
        for precondition in self.preconditions:
            results = beliefs_query_func(precondition)
            if not results:
                return False
        
        return True
    
    def is_expired(self) -> bool:
        """Проверить, истёк ли deadline"""
        if self.deadline is None:
            return False
        return datetime.now() > self.deadline
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'id': self.id,
            'description': self.description,
            'priority': self.priority,
            'urgency': self.urgency,
            'status': self.status.value,
            'motivation_type': self.motivation_type.value,
            'source': self.source,
            'preconditions': self.preconditions,
            'success_conditions': self.success_conditions,
            'personality_alignment': self.personality_alignment,
            'created_at': self.created_at.isoformat(),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'context': self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Desire':
        """Десериализация из словаря"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            description=data['description'],
            priority=data.get('priority', 0.5),
            urgency=data.get('urgency', 0.5),
            status=DesireStatus(data.get('status', 'active')),
            motivation_type=MotivationType(data.get('motivation_type', 'social')),
            source=data.get('source', 'personality'),
            preconditions=data.get('preconditions', []),
            success_conditions=data.get('success_conditions', []),
            personality_alignment=data.get('personality_alignment', 0.5),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now(),
            deadline=datetime.fromisoformat(data['deadline']) if data.get('deadline') else None,
            context=data.get('context', {})
        )
    
    def __repr__(self):
        return f"Desire({self.description[:30]}..., utility={self.calculate_utility():.2f})"


class DesireGenerator:
    """
    Генератор желаний/целей на основе личности, эмоций и ситуации
    
    Использует правила для создания желаний, соответствующих характеру агента.
    """
    
    def __init__(self):
        self.generation_rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[Dict[str, Any]]:
        """Инициализация правил генерации желаний"""
        return [
            # Правила на основе экстраверсии
            {
                'name': 'extravert_socialization',
                'condition': lambda p, e, b: p.get('extraversion', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Поговорить с кем-то интересным',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.7,
                    'urgency': 0.5,
                    'source': 'personality_extraversion'
                }
            },
            {
                'name': 'introvert_solitude',
                'condition': lambda p, e, b: p.get('extraversion', 0.5) < 0.3,
                'desire_template': {
                    'description': 'Найти тихое место для размышлений',
                    'motivation_type': MotivationType.SAFETY,
                    'priority': 0.6,
                    'urgency': 0.4,
                    'source': 'personality_introversion'
                }
            },
            
            # Правила на основе открытости
            {
                'name': 'openness_exploration',
                'condition': lambda p, e, b: p.get('openness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Изучить что-то новое',
                    'motivation_type': MotivationType.CURIOSITY,
                    'priority': 0.65,
                    'urgency': 0.3,
                    'source': 'personality_openness'
                }
            },
            
            # Правила на основе доброжелательности
            {
                'name': 'agreeableness_help',
                'condition': lambda p, e, b: p.get('agreeableness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Помочь кому-то в нужде',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.7,
                    'urgency': 0.6,
                    'source': 'personality_agreeableness'
                }
            },
            
            # Правила на основе сознательности
            {
                'name': 'conscientiousness_organize',
                'condition': lambda p, e, b: p.get('conscientiousness', 0.5) > 0.7,
                'desire_template': {
                    'description': 'Организовать и упорядочить дела',
                    'motivation_type': MotivationType.ACHIEVEMENT,
                    'priority': 0.6,
                    'urgency': 0.5,
                    'source': 'personality_conscientiousness'
                }
            },
            
            # Правила на основе эмоций
            {
                'name': 'sadness_support',
                'condition': lambda p, e, b: e.get('sadness', 0) > 0.6,
                'desire_template': {
                    'description': 'Получить эмоциональную поддержку',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.8,
                    'urgency': 0.7,
                    'source': 'emotion_sadness'
                }
            },
            {
                'name': 'fear_safety',
                'condition': lambda p, e, b: e.get('fear', 0) > 0.6,
                'desire_template': {
                    'description': 'Найти безопасное место',
                    'motivation_type': MotivationType.SAFETY,
                    'priority': 0.9,
                    'urgency': 0.9,
                    'source': 'emotion_fear'
                }
            },
            {
                'name': 'happiness_share',
                'condition': lambda p, e, b: e.get('happiness', 0) > 0.7,
                'desire_template': {
                    'description': 'Поделиться радостью с другими',
                    'motivation_type': MotivationType.SOCIAL,
                    'priority': 0.6,
                    'urgency': 0.5,
                    'source': 'emotion_happiness'
                }
            },
            {
                'name': 'anger_confront',
                'condition': lambda p, e, b: e.get('anger', 0) > 0.6,
                'desire_template': {
                    'description': 'Разрешить конфликтную ситуацию',
                    'motivation_type': MotivationType.ESTEEM,
                    'priority': 0.75,
                    'urgency': 0.8,
                    'source': 'emotion_anger'
                }
            },
        ]
    
    def generate_desires(
        self,
        personality: Dict[str, float],
        emotions: Dict[str, float],
        beliefs_base,
        current_desires: List[Desire]
    ) -> List[Desire]:
        """
        Генерация новых желаний
        
        Args:
            personality: OCEAN traits (openness, conscientiousness, extraversion, agreeableness, neuroticism)
            emotions: Текущие эмоции (happiness, sadness, anger, fear, surprise, disgust)
            beliefs_base: BeliefBase объект
            current_desires: Существующие желания (чтобы не дублировать)
        
        Returns:
            Список новых желаний
        """
        new_desires = []
        
        # Проходим по всем правилам
        for rule in self.generation_rules:
            # Проверяем условие
            try:
                if rule['condition'](personality, emotions, beliefs_base):
                    # Проверяем, нет ли уже такого желания
                    if not self._has_similar_desire(current_desires, rule['name']):
                        # Создаём желание из шаблона
                        desire = self._create_desire_from_template(
                            rule['desire_template'],
                            personality,
                            emotions,
                            beliefs_base
                        )
                        new_desires.append(desire)
            except Exception as e:
                # Игнорируем ошибки в правилах
                print(f"Error in rule {rule['name']}: {e}")
                continue
        
        # Генерируем ситуационные желания
        situational_desires = self._generate_situational_desires(
            beliefs_base,
            current_desires,
            personality
        )
        new_desires.extend(situational_desires)
        
        return new_desires
    
    def _create_desire_from_template(
        self,
        template: Dict[str, Any],
        personality: Dict[str, float],
        emotions: Dict[str, float],
        beliefs_base
    ) -> Desire:
        """Создать желание из шаблона"""
        
        # Вычисляем personality_alignment
        source = template.get('source', 'unknown')
        alignment = 0.7  # default
        
        if 'extraversion' in source:
            alignment = personality.get('extraversion', 0.5)
        elif 'introversion' in source:
            alignment = 1.0 - personality.get('extraversion', 0.5)
        elif 'openness' in source:
            alignment = personality.get('openness', 0.5)
        elif 'agreeableness' in source:
            alignment = personality.get('agreeableness', 0.5)
        elif 'conscientiousness' in source:
            alignment = personality.get('conscientiousness', 0.5)
        
        return Desire(
            description=template['description'],
            priority=template.get('priority', 0.5),
            urgency=template.get('urgency', 0.5),
            motivation_type=template.get('motivation_type', MotivationType.SOCIAL),
            source=template.get('source', 'generated'),
            personality_alignment=alignment,
            status=DesireStatus.ACTIVE
        )
    
    def _has_similar_desire(self, desires: List[Desire], rule_name: str) -> bool:
        """Проверить, есть ли уже похожее желание"""
        # Упрощённая проверка - по ключевым словам в описании
        keywords = {
            'extravert_socialization': ['поговорить', 'общаться'],
            'introvert_solitude': ['тихое', 'размышлен'],
            'openness_exploration': ['изучить', 'новое'],
            'agreeableness_help': ['помочь', 'помощь'],
            'conscientiousness_organize': ['организ', 'упорядоч'],
            'sadness_support': ['поддержк'],
            'fear_safety': ['безопас'],
            'happiness_share': ['поделиться', 'радост'],
            'anger_confront': ['конфликт', 'разреш']
        }
        
        rule_keywords = keywords.get(rule_name, [])
        
        for desire in desires:
            if desire.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]:
                desc_lower = desire.description.lower()
                if any(keyword in desc_lower for keyword in rule_keywords):
                    return True
        
        return False
    
    def _generate_situational_desires(
        self,
        beliefs_base,
        current_desires: List[Desire],
        personality: Dict[str, float]
    ) -> List[Desire]:
        """
        Генерация желаний на основе текущей ситуации (beliefs)
        """
        situational_desires = []
        
        # Импортируем BeliefType здесь чтобы избежать циклических импортов
        from .beliefs import BeliefType
        
        # Желание пообщаться с друзьями поблизости
        agent_beliefs = beliefs_base.get_beliefs_by_type(BeliefType.AGENT)
        
        for belief in agent_beliefs:
            # Если видим друга
            if belief.key == "relationship" and belief.value == "friend":
                friend_id = belief.subject
                
                # Проверяем, нет ли уже желания пообщаться с этим другом
                friend_desire_exists = any(
                    friend_id in d.description and d.status == DesireStatus.ACTIVE
                    for d in current_desires
                )
                
                if not friend_desire_exists:
                    # Проверяем, в одной ли мы локации
                    friend_location = beliefs_base.get_belief(
                        BeliefType.AGENT,
                        friend_id,
                        "location"
                    )
                    
                    if friend_location:
                        situational_desires.append(Desire(
                            description=f"Пообщаться с {friend_id}",
                            priority=0.7,
                            urgency=0.5,
                            motivation_type=MotivationType.SOCIAL,
                            source="situation_friend_nearby",
                            preconditions=[f"same_location_{friend_id}"],
                            personality_alignment=personality.get('extraversion', 0.5),
                            context={'target_agent': friend_id}
                        ))
        
        return situational_desires


# Utility функции

def create_custom_desire(
    description: str,
    motivation_type: MotivationType = MotivationType.SOCIAL,
    priority: float = 0.5,
    urgency: float = 0.5,
    **kwargs
) -> Desire:
    """Создать кастомное желание"""
    return Desire(
        description=description,
        motivation_type=motivation_type,
        priority=priority,
        urgency=urgency,
        **kwargs
    )
