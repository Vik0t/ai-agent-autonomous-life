# deliberation.py  [v6 — Reactive Interrupts + Idle Drive]
"""
Изменения v6:
1. _cleanup_desires освобождает PURSUED desires чьи намерения завершились.
2. Передача active_conversation_partners в generate_desires.
3. notify_conversation_ended → desire_generator.
4. notify_solo_action() — для Social Satiety счётчика.
5. [NEW] Реактивное прерывание: incoming_message приостанавливает рутинные намерения.
6. [NEW] Восстановление SUSPENDED намерений после завершения ответа.
7. [NEW] Страховочный Idle Drive через deliberation если desires.py его не сгенерировал.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from .beliefs import BeliefBase, Belief, BeliefType
from .desires import Desire, DesireGenerator, DesireStatus, MotivationType
from .intentions import Intention, IntentionSelector, IntentionStatus, create_intention_from_desire
from .plans import Planner


class DeliberationCycle:
    def __init__(self, llm_interface=None):
        self.desire_generator = DesireGenerator()
        self.intention_selector = IntentionSelector()
        self.planner = Planner(llm_interface)
        self.llm = llm_interface
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None

    def run_cycle(
        self,
        agent_id: str,
        beliefs: BeliefBase,
        desires: List[Desire],
        intentions: List[Intention],
        personality: Dict[str, float],
        emotions: Dict[str, float],
        perceptions: List[Dict[str, Any]],
        max_intentions: int = 1,
        active_conversation_partners: List[str] = None
    ) -> Dict[str, Any]:
        cycle_start = datetime.now()
        self.cycle_count += 1

        # ── 1. Очистка ──────────────────────────────────────────────
        self._cleanup_desires(desires, intentions)
        self._cleanup_intentions(intentions)

        # Жёсткий лимит размера
        if len(desires) > 12:
            keep_incoming = [d for d in desires
                             if d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE]
            other = [d for d in desires
                     if not (d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE)]
            other.sort(key=lambda d: d.calculate_utility(), reverse=True)
            desires[:] = keep_incoming + other[:6]

        # ── 2. Perception → Belief ───────────────────────────────────
        new_beliefs = []
        for perception in perceptions:
            new_beliefs.extend(beliefs.update_from_perception(perception))
        new_beliefs.extend(self._update_self_beliefs(agent_id, beliefs, emotions))

        # ── 3. Desire generation ─────────────────────────────────────
        new_desires = self.desire_generator.generate_desires(
            personality=personality,
            emotions=emotions,
            beliefs_base=beliefs,
            current_desires=desires,
            agent_id=agent_id,
            perceptions=perceptions,
            active_conversation_partners=active_conversation_partners or []
        )
        desires.extend(new_desires)

        # ── 3b. Страховочный Idle Drive ──────────────────────────────
        # Если нет ни одного активного/pursued несоциального желания
        # И нет активных/suspended намерений — агент в тупике. Вставляем idle.
        # Idle засчитывается как solo ТОЛЬКО после реального выполнения шага
        # (через notify_solo_action в simulator — не авансом).
        has_any_nonsocial = any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.motivation_type != MotivationType.SOCIAL
            for d in desires
        )
        has_active_intention = any(
            i.status in [IntentionStatus.ACTIVE, IntentionStatus.SUSPENDED]
            for i in intentions
        )
        if not has_any_nonsocial and not has_active_intention:
            idle = self.desire_generator._generate_idle_desire(agent_id, personality)
            # Не дублируем если такой idle уже есть
            already_idle = any(
                d.description == idle.description
                and d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
                for d in desires
            )
            if not already_idle:
                desires.append(idle)
                new_desires.append(idle)
                print(f"💤 [{agent_id}] Страховочный Idle Drive: «{idle.description}»")

        # ── 4. Реактивное прерывание ─────────────────────────────────
        # Если пришло СРОЧНОЕ социальное желание (incoming_message),
        # немедленно приостанавливаем прерываемые рутинные намерения.
        urgent_social = next(
            (d for d in desires
             if d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE),
            None
        )
        suspended_now = []
        if urgent_social:
            # Прерываем только если нет уже активного НЕСОЦИАЛЬНОГО (!) намерения
            # отвечающего на входящее — т.е. мы ещё не начали обрабатывать этот запрос.
            # interruptible=False означает "социальное/важное" — его НЕ прерываем.
            # Прерываем только interruptible=True (рутина: think/move/observe/learn).
            target_agent = urgent_social.context.get('target_agent')
            already_responding = any(
                i.status == IntentionStatus.ACTIVE
                and not i.interruptible  # это уже социальное намерение
                for i in intentions
            )
            if not already_responding:
                suspended_now = self.intention_selector.interrupt_for_social(
                    intentions, urgent_social
                )
                if suspended_now:
                    print(f"⚡ [{agent_id}] Прерывание для ответа «{urgent_social.description}» "
                          f"→ пауза {len(suspended_now)} намерений: "
                          f"{[i.desire_description[:25] for i in suspended_now]}")

        # ── 5. Intention selection ───────────────────────────────────
        new_intention = None
        has_active = any(i.status == IntentionStatus.ACTIVE for i in intentions)

        if not has_active:
            selected = self.intention_selector.select_intention(
                desires=desires,
                current_intentions=intentions,
                beliefs_base=beliefs,
                max_intentions=max_intentions
            )
            if selected:
                plan = self.planner.create_plan(selected, beliefs, agent_id)
                new_intention = create_intention_from_desire(selected, plan)
                intentions.append(new_intention)
                selected.status = DesireStatus.PURSUED
            else:
                # Нет новых кандидатов — проверяем: можно ли возобновить приостановленные?
                # Возобновляем только если нет активных (тем более социальных) намерений.
                has_any_active_or_social_desire = any(
                    d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE
                    for d in desires
                )
                if not has_any_active_or_social_desire:
                    for intention in intentions:
                        if intention.status == IntentionStatus.SUSPENDED:
                            intention.resume()
                            print(f"▶ [{agent_id}] Возобновлено: "
                                  f"«{intention.desire_description[:40]}»")

        # ── 6. Execution ─────────────────────────────────────────────
        actions_to_execute = []
        for intention in [i for i in intentions if i.status == IntentionStatus.ACTIVE]:
            action = intention.get_current_action()
            if action and not action.executed:
                actions_to_execute.append({
                    'intention_id': intention.id,
                    'action': action,
                    'step_index': intention.current_step
                })

        self.last_cycle_time = datetime.now()

        return {
            'new_beliefs': new_beliefs,
            'new_desires': new_desires,
            'new_intention': new_intention,
            'actions_to_execute': actions_to_execute,
            'updated_intentions': intentions,
            'cycle_info': {
                'cycle_number': self.cycle_count,
                'duration_seconds': (datetime.now() - cycle_start).total_seconds(),
                'active_intentions_count': sum(1 for i in intentions
                                               if i.status == IntentionStatus.ACTIVE),
                'suspended_count': sum(1 for i in intentions
                                       if i.status == IntentionStatus.SUSPENDED),
                'total_desires': len(desires),
                'total_beliefs': len(beliefs),
                'interrupted': len(suspended_now),
            }
        }

    def _update_self_beliefs(self, agent_id: str, beliefs: BeliefBase,
                             emotions: Dict[str, float]) -> List[Belief]:
        result = []
        for name, val in emotions.items():
            b = Belief(type=BeliefType.SELF, subject=agent_id,
                       key=f"emotion_{name}", value=val,
                       confidence=1.0, source="introspection")
            beliefs.add_belief(b)
            result.append(b)
        return result

    def _cleanup_desires(self, desires: List[Desire], intentions: List[Intention]) -> None:
        """
        Освобождение desires:
        - Истёкшие → удалить
        - PURSUED чьё intention завершено → пометить ACHIEVED
        - ACHIEVED/ABANDONED старше 30 сек → удалить
        - Дубликаты по description → удалить
        """
        now = datetime.now()
        # Маппинг desire_id → intention для быстрой проверки
        d2i: Dict[str, Intention] = {i.desire_id: i for i in intentions if i.desire_id}

        to_remove = []
        seen: set = set()

        for idx, desire in enumerate(desires):
            # 1. Истёк
            if desire.is_expired():
                to_remove.append(idx)
                continue

            # 2. PURSUED → проверяем намерение
            if desire.status == DesireStatus.PURSUED:
                intention = d2i.get(desire.id)
                if intention is None:
                    # Намерение уже удалено → desire завершён
                    desire.status = DesireStatus.ACHIEVED
                elif intention.status in [IntentionStatus.COMPLETED,
                                          IntentionStatus.FAILED,
                                          IntentionStatus.ABANDONED]:
                    desire.status = DesireStatus.ACHIEVED

            # 3. Старые завершённые
            age = (now - desire.created_at).total_seconds()
            if desire.status in [DesireStatus.ACHIEVED, DesireStatus.ABANDONED] and age > 30:
                to_remove.append(idx)
                continue

            # 4. Дубликаты
            key = desire.description.lower().strip()
            if key in seen:
                to_remove.append(idx)
                continue
            seen.add(key)

        for idx in reversed(to_remove):
            desires.pop(idx)

    def _cleanup_intentions(self, intentions: List[Intention]) -> None:
        done = [IntentionStatus.COMPLETED, IntentionStatus.FAILED, IntentionStatus.ABANDONED]
        to_remove = [i for i, intention in enumerate(intentions) if intention.status in done]
        for i in reversed(to_remove):
            intentions.pop(i)

    def notify_conversation_ended(self, partner_id: str):
        """Симулятор вызывает это чтобы активировать кулдаун в desire_generator."""
        self.desire_generator.mark_conversation_ended(partner_id)

    def notify_solo_action(self, action_type: str):
        """
        Симулятор вызывает это после каждого несоциального действия агента.
        Продвигает счётчик Social Satiety — после MIN_SOLO_ACTIONS разблокирует социальность.
        """
        self.desire_generator.mark_solo_action(action_type)
        count = self.desire_generator._solo_actions_after_conversation
        needed = self.desire_generator.MIN_SOLO_ACTIONS
        if count <= needed:
            print(f"🔨 Solo action «{action_type}»: {count}/{needed} до разблокировки соц.")

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None
        }


def create_perception(perception_type: str, subject: str, data: Dict[str, Any],
                      confidence: float = 0.9, importance: float = 0.5) -> Dict[str, Any]:
    return {
        'type': perception_type, 'subject': subject, 'data': data,
        'confidence': confidence, 'importance': importance,
        'timestamp': datetime.now().isoformat()
    }


def extract_actions_summary(result: Dict[str, Any]) -> str:
    actions = result.get('actions_to_execute', [])
    if not actions:
        return "Нет действий"
    return "\n".join(f"{i+1}. {a['action'].description}" for i, a in enumerate(actions))