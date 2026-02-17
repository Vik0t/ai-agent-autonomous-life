# deliberation.py  [v8 — Fix WRAP_UP + FORCE_QUIT flag + Idle Guard]
"""
Изменения v8:
1. WRAP_UP создаёт новое высокоприоритетное Intention вместо мутации старого плана.
   Старое намерение помечается ABANDONED. Новое намерение содержит [farewell, end_conversation].
   Флаг _wrap_up_issued: set предотвращает повторные вставки на каждом тике.
2. FORCE_QUIT выставляет флаг _force_quit_partners — атомарная обработка в simulator.py.
   deliberation больше не мутирует планы напрямую — это делает simulator через consume_force_quit_partners().
3. Idle Guard: если агент выдаёт idle >= 2 тиков подряд И есть намерение в «мёртвом» состоянии
   (все шаги executed но intention не COMPLETED) — принудительно завершаем его и чистим desire.
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from .beliefs import BeliefBase, Belief, BeliefType
from .desires import Desire, DesireGenerator, DesireStatus, MotivationType
from .intentions import Intention, IntentionSelector, IntentionStatus, create_intention_from_desire
from .plans import Planner, ActionType, Plan, PlanStep


class DeliberationCycle:
    def __init__(self, llm_interface=None):
        self.desire_generator = DesireGenerator(llm_interface=llm_interface)
        self.intention_selector = IntentionSelector()
        self.planner = Planner(llm_interface)
        self.llm = llm_interface
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None

        # Hard Limit: счётчик реплик per partner
        self._conversation_turn_counts: Dict[str, int] = {}
        self.HARD_LIMIT_TURNS = 10

        # FIX 1: предотвращаем повторный WRAP_UP для одного и того же intention
        self._wrap_up_issued: Set[str] = set()   # intention_id

        # FIX 2: партнёры для атомарного FORCE_QUIT (читается и сбрасывается симулятором)
        self._force_quit_partners: Set[str] = set()  # partner_id

        # FIX 3: Idle Guard — счётчик idle тиков подряд
        self._idle_ticks: int = 0
        self.IDLE_GUARD_THRESHOLD = 2

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
        active_conversation_partners: List[str] = None,
        social_battery: float = 1.0,
        agent_name: str = "",
        conversation_history: Dict[str, List[Dict]] = None
    ) -> Dict[str, Any]:
        cycle_start = datetime.now()
        self.cycle_count += 1
        conv_history = conversation_history or {}

        # ── 1. Очистка ──────────────────────────────────────────────
        self._cleanup_desires(desires, intentions)
        self._cleanup_intentions(intentions)

        if len(desires) > 12:
            keep_incoming = [d for d in desires
                             if d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE]
            other = [d for d in desires
                     if not (d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE)]
            other.sort(key=lambda d: d.calculate_utility(), reverse=True)
            desires[:] = keep_incoming + other[:6]

        # ── 1b. FIX 3: Idle Guard ────────────────────────────────────
        has_any_active = any(i.status == IntentionStatus.ACTIVE for i in intentions)
        if not has_any_active:
            self._idle_ticks += 1
            if self._idle_ticks >= self.IDLE_GUARD_THRESHOLD:
                killed = self._kill_zombie_intentions(intentions, desires, agent_id)
                if killed:
                    self._idle_ticks = 0
        else:
            self._idle_ticks = 0

        # ── 2. Perception → Belief ───────────────────────────────────
        new_beliefs = []
        for perception in perceptions:
            new_beliefs.extend(beliefs.update_from_perception(perception))
        new_beliefs.extend(self._update_self_beliefs(agent_id, beliefs, emotions))

        # ── 2b. Обновление счётчика реплик (Hard Limit) ─────────────
        for perception in perceptions:
            if perception.get('type') != 'communication':
                continue
            partner_id = perception.get('subject', '')
            if partner_id and partner_id != agent_id:
                self._conversation_turn_counts[partner_id] = (
                    self._conversation_turn_counts.get(partner_id, 0) + 1
                )
                turns = self._conversation_turn_counts[partner_id]
                if turns >= self.HARD_LIMIT_TURNS:
                    if partner_id not in self._force_quit_partners:
                        self._force_quit_partners.add(partner_id)
                        print(f"⏰ [{agent_id}] Hard Limit: {partner_id} "
                              f"({turns} реплик) → FORCE_QUIT запрошен")

        # ── 3. Desire generation ─────────────────────────────────────
        new_desires = self.desire_generator.generate_desires(
            personality=personality,
            emotions=emotions,
            beliefs_base=beliefs,
            current_desires=desires,
            agent_id=agent_id,
            agent_name=agent_name or agent_id,
            perceptions=perceptions,
            active_conversation_partners=active_conversation_partners or [],
            social_battery=social_battery
        )
        desires.extend(new_desires)

        # ── 3b. Страховочный Idle Drive ──────────────────────────────
        has_any_nonsocial = any(
            d.status in [DesireStatus.ACTIVE, DesireStatus.PURSUED]
            and d.motivation_type != MotivationType.SOCIAL
            for d in desires
        )
        has_active_intention_check = any(
            i.status in [IntentionStatus.ACTIVE, IntentionStatus.SUSPENDED]
            for i in intentions
        )
        if not has_any_nonsocial and not has_active_intention_check:
            idle = self.desire_generator._generate_idle_desire(agent_id, personality)
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
        urgent_social = next(
            (d for d in desires
             if d.source == 'incoming_message' and d.status == DesireStatus.ACTIVE),
            None
        )
        suspended_now = []
        if urgent_social:
            already_responding = any(
                i.status == IntentionStatus.ACTIVE and not i.interruptible
                for i in intentions
            )
            if not already_responding:
                suspended_now = self.intention_selector.interrupt_for_social(
                    intentions, urgent_social
                )
                if suspended_now:
                    print(f"⚡ [{agent_id}] Прерывание для ответа «{urgent_social.description}» "
                          f"→ пауза {len(suspended_now)} намерений")

        # ── 5. FIX 1: Анализ диалога через LLM ──────────────────────
        wrap_up_created_for: Set[str] = set()
        if self.llm and active_conversation_partners:
            active_social_intentions = [
                i for i in intentions
                if i.status == IntentionStatus.ACTIVE and not i.interruptible
            ]
            for intent in active_social_intentions:
                partner_id = self._get_intention_target(intent, desires)
                if not partner_id:
                    continue
                if partner_id in self._force_quit_partners:
                    continue
                # WRAP_UP уже выпущен для этого намерения — пропускаем
                if intent.id in self._wrap_up_issued:
                    continue

                history = conv_history.get(partner_id, [])
                try:
                    decision = self.llm.analyze_conversation_turn(
                        agent_name=agent_name or agent_id,
                        agent_id=agent_id,
                        personality=personality,
                        conversation_history=history,
                        social_battery=social_battery
                    )
                except Exception as e:
                    print(f"⚠️ [{agent_id}] analyze_conversation_turn failed: {e}. Fallback → CONTINUE")
                    decision = "CONTINUE"
                    self._inject_think_step(intent, agent_id)

                if decision == "FORCE_QUIT":
                    self._force_quit_partners.add(partner_id)
                    print(f"💥 [{agent_id}] LLM → FORCE_QUIT с {partner_id}")

                elif decision == "WRAP_UP":
                    desire_for_intent = next(
                        (d for d in desires if d.id == intent.desire_id), None
                    )
                    if desire_for_intent:
                        wrap_intent = self._create_farewell_intention(
                            desire_for_intent, partner_id, agent_id
                        )
                        intent.abandon("WRAP_UP — заменено farewell намерением")
                        desire_for_intent.status = DesireStatus.ABANDONED
                        intentions.append(wrap_intent)
                        self._wrap_up_issued.add(intent.id)
                        wrap_up_created_for.add(partner_id)
                        print(f"🏁 [{agent_id}] WRAP_UP → создано farewell intention для {partner_id}")

        # ── 6. Динамическое расширение плана при новом сообщении ────
        if urgent_social and self.planner.llm:
            partner_id = urgent_social.context.get('target_agent', '')
            active_intent = next(
                (i for i in intentions
                 if i.status == IntentionStatus.ACTIVE and not i.interruptible),
                None
            )
            if (active_intent
                    and partner_id
                    and partner_id not in self._force_quit_partners
                    and partner_id not in wrap_up_created_for
                    and active_intent.id not in self._wrap_up_issued):
                desire_for_intent = next(
                    (d for d in desires if d.id == active_intent.desire_id), None
                )
                history = conv_history.get(partner_id, [])
                if desire_for_intent:
                    remaining = active_intent.plan.get_remaining_steps() if active_intent.plan else []
                    if len(remaining) <= 1:
                        self.planner.extend_conversation_plan(
                            intention=active_intent,
                            desire=desire_for_intent,
                            agent_id=agent_id,
                            conversation_history=history,
                            social_battery=social_battery,
                            personality=personality,
                            force_end=False
                        )
                        print(f"🔧 [{agent_id}] Достройка плана для {partner_id}")

        # ── 7. Intention selection ───────────────────────────────────
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

        # ── 8. Execution ─────────────────────────────────────────────
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
                'social_battery': social_battery,
                'wrap_up_triggered': len(wrap_up_created_for),
                'force_quit_count': len(self._force_quit_partners)
            }
        }

    # ── FIX 1: Создание farewell Intention ───────────────────────────

    def _create_farewell_intention(
        self, original_desire: Desire, partner_id: str, agent_id: str
    ) -> 'Intention':
        """
        Создаёт новое высокоприоритетное намерение [farewell → end_conversation].
        Не мутирует существующий план — добавляет чистый новый Intention.
        """
        farewell_plan = Plan(
            goal=f"Попрощаться с {partner_id}",
            steps=[
                PlanStep(
                    action_type=ActionType.SEND_MESSAGE,
                    parameters={
                        "target": partner_id,
                        "message_type": "farewell",
                        "requires_response": False,
                        "tone": "friendly"
                    },
                    description=f"Попрощаться с {partner_id}",
                    estimated_duration=1.0
                ),
                PlanStep(
                    action_type=ActionType.END_CONVERSATION,
                    parameters={"target": partner_id},
                    description="Завершить разговор",
                    estimated_duration=0.5
                )
            ],
            expected_outcome="Диалог завершён"
        )

        # Создаём временный desire для farewell (не добавляем в общий список)
        from .desires import Desire as FarewellDesire, MotivationType, DesireStatus
        farewell_desire = FarewellDesire(
            description=f"Попрощаться с {partner_id}",
            motivation_type=MotivationType.SOCIAL,
            priority=0.99,
            urgency=1.0,
            source='wrap_up',
            personality_alignment=1.0,
            status=DesireStatus.PURSUED,   # сразу PURSUED — не попадёт в повторный выбор
            context={'target_agent': partner_id}
        )

        intent = create_intention_from_desire(farewell_desire, farewell_plan)
        intent.interruptible = False
        intent.priority = 0.99
        return intent

    # ── FIX 2: API для simulator — атомарный FORCE_QUIT ──────────────

    def consume_force_quit_partners(self) -> Set[str]:
        """
        Симулятор вызывает ПОСЛЕ run_cycle.
        Возвращает partner_id'ы для принудительного завершения и очищает флаги.
        """
        result = set(self._force_quit_partners)
        self._force_quit_partners.clear()
        return result

    # ── FIX 3: Idle Guard ────────────────────────────────────────────

    def _kill_zombie_intentions(
        self, intentions: List[Intention], desires: List[Desire], agent_id: str
    ) -> int:
        """
        Убивает намерения у которых все шаги executed, но статус всё ещё ACTIVE/SUSPENDED.
        Возвращает количество уничтоженных намерений.
        """
        killed = 0
        for intention in list(intentions):
            if intention.status not in (IntentionStatus.ACTIVE, IntentionStatus.SUSPENDED):
                continue
            if intention.plan is None:
                intention.abandon("Idle Guard: нет плана")
                killed += 1
                continue

            all_executed = (
                len(intention.plan.steps) > 0
                and all(s.executed for s in intention.plan.steps)
            )
            if all_executed:
                intention.abandon("Idle Guard: все шаги выполнены, зомби-намерение")
                for d in desires:
                    if d.id == intention.desire_id:
                        d.status = DesireStatus.ABANDONED
                        break
                self._wrap_up_issued.discard(intention.id)
                killed += 1
                print(f"🧟 [{agent_id}] Idle Guard: убито «{intention.desire_description[:40]}»")

        return killed

    # ── Общие вспомогательные методы ─────────────────────────────────

    def _get_intention_target(self, intention: Intention, desires: List[Desire]) -> str:
        desire = next((d for d in desires if d.id == intention.desire_id), None)
        if desire:
            return desire.context.get('target_agent', '')
        return ''

    def _inject_think_step(self, intention: Intention, agent_id: str):
        if intention.plan:
            think_step = PlanStep(
                action_type=ActionType.THINK,
                parameters={"topic": "текущий диалог"},
                description="Задуматься (LLM fallback)",
                estimated_duration=1.0
            )
            intention.plan.steps.insert(intention.current_step, think_step)

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
        now = datetime.now()
        d2i: Dict[str, Intention] = {i.desire_id: i for i in intentions if i.desire_id}
        to_remove = []
        seen: set = set()

        for idx, desire in enumerate(desires):
            if desire.is_expired():
                to_remove.append(idx)
                continue
            if desire.status == DesireStatus.PURSUED:
                intention = d2i.get(desire.id)
                if intention is None:
                    desire.status = DesireStatus.ACHIEVED
                elif intention.status in [IntentionStatus.COMPLETED,
                                          IntentionStatus.FAILED,
                                          IntentionStatus.ABANDONED]:
                    desire.status = DesireStatus.ACHIEVED
            age = (now - desire.created_at).total_seconds()
            if desire.status in [DesireStatus.ACHIEVED, DesireStatus.ABANDONED] and age > 30:
                to_remove.append(idx)
                continue
            key = desire.description.lower().strip()
            if key in seen:
                to_remove.append(idx)
                continue
            seen.add(key)

        for idx in reversed(to_remove):
            desires.pop(idx)

    def _cleanup_intentions(self, intentions: List[Intention]) -> None:
        done = [IntentionStatus.COMPLETED, IntentionStatus.FAILED, IntentionStatus.ABANDONED]
        # Собираем id до удаления
        ids_to_remove = {i.id for i in intentions if i.status in done}
        to_remove_idx = [idx for idx, i in enumerate(intentions) if i.status in done]
        for idx in reversed(to_remove_idx):
            intentions.pop(idx)
        # Чистим wrap_up флаги для удалённых намерений
        self._wrap_up_issued -= ids_to_remove

    def notify_conversation_ended(self, partner_id: str):
        self.desire_generator.mark_conversation_ended(partner_id)
        self._conversation_turn_counts.pop(partner_id, None)
        self._force_quit_partners.discard(partner_id)

    def notify_solo_action(self, action_type: str):
        self.desire_generator.mark_solo_action(action_type)
        count = self.desire_generator._solo_actions_after_conversation
        needed = self.desire_generator.MIN_SOLO_ACTIONS
        if count <= needed:
            print(f"🔨 Solo action «{action_type}»: {count}/{needed} до разблокировки соц.")

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'total_cycles': self.cycle_count,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            'conversation_turn_counts': dict(self._conversation_turn_counts),
            'wrap_up_issued_count': len(self._wrap_up_issued)
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