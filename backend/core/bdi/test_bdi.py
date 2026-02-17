"""
Тесты и примеры использования BDI архитектуры

Этот файл демонстрирует:
1. Базовое использование всех компонентов BDI
2. Полный deliberation cycle
3. Интеграцию с агентом
"""

import sys
from datetime import datetime

# Добавляем путь к модулям
sys.path.insert(0, '.')

from .beliefs import BeliefBase, Belief, BeliefType, create_self_belief, create_agent_belief
from .desires import Desire, DesireGenerator, MotivationType, DesireStatus
from .intentions import Intention, IntentionSelector, create_intention_from_desire
from .plans import Plan, PlanStep, Planner, ActionType
from .deliberation import DeliberationCycle, create_perception


def print_section(title: str):
    """Красиво печатать заголовок секции"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_beliefs():
    """Тест системы убеждений"""
    print_section("ТЕСТ: Belief System")
    
    # Создаём базу убеждений
    beliefs = BeliefBase()
    
    # Добавляем убеждения о себе
    beliefs.add_belief(create_self_belief("agent_1", "location", "park"))
    beliefs.add_belief(create_self_belief("agent_1", "energy", 0.8))
    beliefs.add_belief(create_self_belief("agent_1", "mood", "happy"))
    
    # Добавляем убеждения о других агентах
    beliefs.add_belief(create_agent_belief("agent_1", "agent_2", "location", "cafe"))
    beliefs.add_belief(create_agent_belief("agent_1", "agent_2", "relationship", "friend"))
    beliefs.add_belief(create_agent_belief("agent_1", "agent_2", "mood", "neutral"))
    
    # Добавляем убеждения о мире
    beliefs.add_belief(Belief(
        type=BeliefType.WORLD,
        subject="weather",
        key="condition",
        value="sunny",
        confidence=0.95
    ))
    
    print(f"\n📚 Создано {len(beliefs)} убеждений")
    
    # Поиск убеждений
    print("\n🔍 Поиск убеждений о 'agent_2':")
    agent_2_beliefs = beliefs.get_beliefs_about("agent_2")
    for belief in agent_2_beliefs:
        print(f"  {belief}")
    
    # Запрос
    print("\n🔍 Текстовый поиск 'friend':")
    friend_beliefs = beliefs.query("friend")
    for belief in friend_beliefs:
        print(f"  {belief}")
    
    return beliefs


def test_desires(beliefs):
    """Тест системы желаний"""
    print_section("ТЕСТ: Desire System")
    
    # Личность агента (экстраверт)
    personality = {
        "openness": 0.8,
        "conscientiousness": 0.6,
        "extraversion": 0.9,  # Высокая экстраверсия
        "agreeableness": 0.7,
        "neuroticism": 0.3
    }
    
    # Эмоции
    emotions = {
        "happiness": 0.7,
        "sadness": 0.1,
        "anger": 0.0,
        "fear": 0.0,
        "surprise": 0.2,
        "disgust": 0.0
    }
    
    print("\n🧠 Личность агента:")
    for trait, value in personality.items():
        print(f"  {trait}: {value:.2f}")
    
    print("\n😊 Эмоции агента:")
    for emotion, value in emotions.items():
        if value > 0:
            print(f"  {emotion}: {value:.2f}")
    
    # Генерируем желания
    generator = DesireGenerator()
    current_desires = []
    
    new_desires = generator.generate_desires(
        personality=personality,
        emotions=emotions,
        beliefs_base=beliefs,
        current_desires=current_desires
    )
    
    print(f"\n🎯 Сгенерировано {len(new_desires)} желаний:")
    for i, desire in enumerate(new_desires, 1):
        utility = desire.calculate_utility()
        print(f"\n  {i}. {desire.description}")
        print(f"     Приоритет: {desire.priority:.2f}, Срочность: {desire.urgency:.2f}")
        print(f"     Мотивация: {desire.motivation_type.value}")
        print(f"     Полезность: {utility:.3f}")
        print(f"     Источник: {desire.source}")
    
    return new_desires


def test_planning(desires, beliefs):
    """Тест системы планирования"""
    print_section("ТЕСТ: Planning System")
    
    if not desires:
        print("⚠️  Нет желаний для планирования")
        return None
    
    # Берём первое желание
    desire = desires[0]
    print(f"\n🎯 Создаём план для: {desire.description}")
    
    # Создаём плановщик
    planner = Planner()
    
    # Генерируем план
    plan = planner.create_plan(
        desire=desire,
        beliefs_base=beliefs,
        agent_id="agent_1"
    )
    
    print(f"\n📋 План создан:")
    print(f"  Цель: {plan.goal}")
    print(f"  Ожидаемый результат: {plan.expected_outcome}")
    print(f"  Предполагаемая длительность: {plan.estimated_total_duration:.1f} тактов")
    print(f"\n  Шаги плана:")
    for i, step in enumerate(plan.steps, 1):
        print(f"    {i}. [{step.action_type.value}] {step.description}")
        print(f"       Длительность: {step.estimated_duration:.1f}")
    
    return plan


def test_intentions(desires, plan):
    """Тест системы намерений"""
    print_section("ТЕСТ: Intention System")
    
    if not desires or not plan:
        print("⚠️  Нужны желание и план")
        return []
    
    desire = desires[0]
    
    # Создаём намерение
    intention = create_intention_from_desire(desire, plan)
    
    print(f"\n💡 Намерение создано:")
    print(f"  ID: {intention.id}")
    print(f"  Описание: {intention.desire_description}")
    print(f"  Статус: {intention.status.value}")
    print(f"  Приоритет: {intention.priority:.2f}")
    print(f"  Прогресс: {intention.get_progress_percentage():.0f}%")
    print(f"  Текущий шаг: {intention.current_step}/{len(plan.steps)}")
    
    # Симулируем выполнение
    print("\n▶️  Симуляция выполнения:")
    
    for i in range(min(3, len(plan.steps))):
        current_action = intention.get_current_action()
        if current_action:
            print(f"\n  Шаг {i+1}: {current_action.description}")
            
            # Симулируем успешное выполнение
            result = {
                "success": True,
                "message": f"Шаг выполнен успешно"
            }
            intention.update_progress(result)
            current_action.executed = True
            current_action.success = True
            
            print(f"  ✓ Выполнено. Прогресс: {intention.get_progress_percentage():.0f}%")
    
    print(f"\n📊 Лог выполнения:")
    for log_entry in intention.execution_log:
        print(f"  {log_entry}")
    
    return [intention]


def test_deliberation_cycle():
    """Тест полного цикла обдумывания"""
    print_section("ТЕСТ: Полный Deliberation Cycle")
    
    # Инициализация
    agent_id = "agent_1"
    
    # Создаём компоненты
    beliefs = BeliefBase()
    desires = []
    intentions = []
    
    # Личность
    personality = {
        "openness": 0.75,
        "conscientiousness": 0.65,
        "extraversion": 0.85,
        "agreeableness": 0.70,
        "neuroticism": 0.35
    }
    
    # Эмоции
    emotions = {
        "happiness": 0.6,
        "sadness": 0.2,
        "anger": 0.0,
        "fear": 0.1,
        "surprise": 0.1,
        "disgust": 0.0
    }
    
    # Восприятия (что агент видит/слышит)
    perceptions = [
        create_perception(
            perception_type="observation",
            subject="agent_2",
            data={
                "location": "cafe",
                "mood": "happy",
                "activity": "reading"
            }
        ),
        create_perception(
            perception_type="observation",
            subject="weather",
            data={
                "condition": "sunny",
                "temperature": "warm"
            }
        )
    ]
    
    print("\n🔄 Запуск Deliberation Cycle...")
    
    # Создаём deliberation cycle
    cycle = DeliberationCycle()
    
    # Запускаем несколько циклов
    for cycle_num in range(1, 4):
        print(f"\n{'─' * 80}")
        print(f"  ЦИКЛ #{cycle_num}")
        print(f"{'─' * 80}")
        
        result = cycle.run_cycle(
            agent_id=agent_id,
            beliefs=beliefs,
            desires=desires,
            intentions=intentions,
            personality=personality,
            emotions=emotions,
            perceptions=perceptions if cycle_num == 1 else [],  # Восприятия только в первом цикле
            max_intentions=3
        )
        
        # Результаты
        print(f"\n📊 Результаты цикла:")
        print(f"  Новых убеждений: {len(result['new_beliefs'])}")
        print(f"  Новых желаний: {len(result['new_desires'])}")
        print(f"  Новое намерение: {'Да' if result['new_intention'] else 'Нет'}")
        print(f"  Действий к выполнению: {len(result['actions_to_execute'])}")
        
        # Показываем новые желания
        if result['new_desires']:
            print(f"\n  🎯 Новые желания:")
            for desire in result['new_desires']:
                print(f"    • {desire.description} (utility: {desire.calculate_utility():.3f})")
        
        # Показываем новое намерение
        if result['new_intention']:
            intention = result['new_intention']
            print(f"\n  💡 Новое намерение:")
            print(f"    • {intention.desire_description}")
            print(f"    • План: {len(intention.plan.steps)} шагов")
        
        # Показываем действия
        if result['actions_to_execute']:
            print(f"\n  ⚡ Действия для выполнения:")
            for action_info in result['actions_to_execute']:
                action = action_info['action']
                print(f"    • {action.description}")
                
                # Симулируем выполнение
                for intention in intentions:
                    if intention.id == action_info['intention_id']:
                        intention.update_progress({
                            "success": True,
                            "message": "Действие выполнено"
                        })
                        action.executed = True
                        action.success = True
        
        # Информация о цикле
        cycle_info = result['cycle_info']
        print(f"\n  ⏱️  Длительность цикла: {cycle_info['duration_seconds']:.3f}с")
        print(f"  📈 Всего убеждений: {cycle_info['total_beliefs']}")
        print(f"  📈 Всего желаний: {cycle_info['total_desires']}")
        print(f"  📈 Активных намерений: {cycle_info['active_intentions_count']}")
    
    print("\n✅ Deliberation Cycle завершён")
    
    return {
        'beliefs': beliefs,
        'desires': desires,
        'intentions': intentions,
        'cycle': cycle
    }


def run_all_tests():
    """Запустить все тесты"""
    print("\n" + "🚀 " * 40)
    print("  BDI ARCHITECTURE - ПОЛНОЕ ТЕСТИРОВАНИЕ")
    print("🚀 " * 40)
    
    # 1. Тест убеждений
    beliefs = test_beliefs()
    
    # 2. Тест желаний
    desires = test_desires(beliefs)
    
    # 3. Тест планирования
    plan = test_planning(desires, beliefs)
    
    # 4. Тест намерений
    intentions = test_intentions(desires, plan)
    
    # 5. Полный deliberation cycle
    result = test_deliberation_cycle()
    
    print_section("ИТОГО")
    print("\n✅ Все тесты пройдены успешно!")
    print("\n📦 Компоненты BDI архитектуры готовы к использованию:")
    print("  ✓ Belief System (beliefs.py)")
    print("  ✓ Desire System (desires.py)")
    print("  ✓ Intention System (intentions.py)")
    print("  ✓ Planning System (plans.py)")
    print("  ✓ Deliberation Cycle (deliberation.py)")
    
    print("\n🎯 Следующие шаги:")
    print("  1. Интегрировать BDI в существующий класс Agent")
    print("  2. Добавить выполнение действий (execute_action)")
    print("  3. Подключить к базе данных для персистентности")
    print("  4. Интегрировать с LLM для продвинутого планирования")
    
    return result


if __name__ == "__main__":
    run_all_tests()
