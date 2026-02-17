# simulator.py  [v4 — финальный рефакторинг]
"""
Исправления:
1. _do_end_conversation уведомляет ОБОИХ агентов через notify_conversation_ended.
2. _process_game_tick передаёт active_conversation_partners в agent.think().
3. Сообщения читаются ОДИН РАЗ за тик (_tick_messages кеш).
4. wait_for_response использует тиковый счётчик (MAX_WAIT_TICKS=4, timeout→success).
5. Тип сообщения прокидывается в perception.data['message_type'] для desires.py.
"""

import asyncio
import traceback
import time
from typing import Dict, List
from collections import defaultdict

from agent import Agent
from communication import CommunicationHub, Message, MessageType
from llm import LLMInterface
from core.bdi.beliefs import BeliefType, Belief
from core.bdi.deliberation import create_perception
import uuid


class WorldSimulator:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.communication_hub = CommunicationHub()
        self.llm_interface = LLMInterface()
        self.running = False
        self.time_speed = 1.0

        self.relationships: Dict[tuple, float] = {}
        self.event_log: List[Dict] = []

        # Кеш сообщений текущего тика
        self._tick_messages: Dict[str, List[Message]] = defaultdict(list)
        # Тиковый счётчик ожидания {intention_id: count}
        self._wait_tick_counters: Dict[str, int] = defaultdict(int)
        self.MAX_WAIT_TICKS = 4

    # ── Вспомогательные ──────────────────────────────────────────────

    def _log_event(self, event_type: str, description: str,
                   agent_ids: List[str] = None, data: Dict = None) -> Dict:
        event = {
            "id": str(uuid.uuid4()), "type": event_type,
            "description": description, "agent_ids": agent_ids or [],
            "data": data or {}, "timestamp": time.time()
        }
        self.event_log.append(event)
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
        return event

    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        return self.event_log[-limit:]

    def get_relationships_data(self) -> List[Dict]:
        return [
            {"source": a, "target": b, "strength": round(v, 3),
             "type": "friend" if v > 0.3 else ("enemy" if v < -0.3 else "neutral")}
            for (a, b), v in self.relationships.items()
        ]

    def _update_relationship(self, a: str, b: str, delta: float):
        key = tuple(sorted([a, b]))
        self.relationships[key] = max(-1.0, min(1.0, self.relationships.get(key, 0.0) + delta))
        val = self.relationships[key]
        for aid, other in [(a, b), (b, a)]:
            if aid in self.agents:
                self.agents[aid].beliefs.add_belief(Belief(
                    type=BeliefType.AGENT, subject=other,
                    key="relationship_strength", value=val,
                    confidence=1.0, source="interaction"
                ))

    def add_agent(self, agent: Agent):
        self.agents[agent.id] = agent
        self.communication_hub.register_agent(agent.id)
        print(f"--- Agent {agent.name} added to simulator ---")

    # ── Главный цикл ─────────────────────────────────────────────────

    async def run_simulation(self):
        self.running = True
        print("🚀 Simulation loop started...")
        while self.running:
            try:
                start = asyncio.get_event_loop().time()
                await self._process_game_tick()
                elapsed = asyncio.get_event_loop().time() - start
                await asyncio.sleep(max(0.1, (5.0 / self.time_speed) - elapsed))
            except Exception as e:
                print(f"❌ CRITICAL: {e}")
                traceback.print_exc()
                await asyncio.sleep(2)

    async def _process_game_tick(self):
        # 1. Читаем входящие сообщения ОДИН РАЗ для всех агентов
        self._tick_messages.clear()
        for agent_id in self.agents:
            msgs = await self.communication_hub.receive_messages(agent_id)
            if msgs:
                self._tick_messages[agent_id] = msgs

        # 2. Обрабатываем каждого агента
        for agent_id, agent in self.agents.items():
            active_partners = self._get_active_partners(agent_id)
            perceptions = self._build_perceptions(agent)
            actions = agent.think(
                perceptions=perceptions,
                active_conversation_partners=active_partners
            )
            if not actions:
                # Агент не выполняет действий — логируем idle
                has_suspended = any(
                    i.status.value == 'suspended' for i in agent.intentions
                )
                if has_suspended:
                    print(f"⏸️  {agent.name}: ожидает завершения ответа (намерения приостановлены)")
                else:
                    print(f"💤 {agent.name}: idle — нет действий в этом тике")
            for cmd in actions:
                print(f"⚡ {agent.name} executing: {cmd['action_type']} | {cmd['params']}")
                await self._execute_agent_action(agent, cmd)

    def _get_active_partners(self, agent_id: str) -> List[str]:
        return [
            pid
            for conv in self.communication_hub.get_agent_active_conversations(agent_id)
            for pid in conv.participants if pid != agent_id
        ]

    def _build_perceptions(self, agent: Agent) -> List[Dict]:
        perceptions = []

        # Входящие сообщения из кеша (не из очереди!)
        for msg in self._tick_messages.get(agent.id, []):
            perceptions.append(create_perception(
                "communication", msg.sender_id,
                {
                    "content": msg.content,
                    "message_type": msg.message_type.value,  # "greeting", "farewell", etc.
                    "topic": msg.topic,
                    "conversation_id": msg.conversation_id,
                    "requires_response": msg.requires_response,
                    "message_id": msg.id
                },
                confidence=1.0,
                importance=0.9 if msg.requires_response else 0.5
            ))
            print(f"📨 {agent.name} получил [{msg.message_type.value}] "
                  f"от {msg.sender_id}: {msg.content[:60]}")
            self._update_relationship(agent.id, msg.sender_id, 0.04)

        # Наблюдение за другими агентами
        for other_id, other in self.agents.items():
            if other_id == agent.id:
                continue
            in_conv = self.communication_hub.is_agent_in_conversation(other_id)
            loc_b = other.beliefs.get_belief(BeliefType.SELF, other_id, "location")
            perceptions.append(create_perception(
                "observation", other_id,
                {"location": loc_b.value if loc_b else "Unknown",
                 "in_conversation": in_conv, "name": other.name}
            ))
            for key, val in [("name", other.name), ("in_conversation", in_conv)]:
                agent.beliefs.add_belief(Belief(
                    type=BeliefType.AGENT, subject=other_id, key=key,
                    value=val, confidence=1.0, source="observation"
                ))

        return perceptions

    # ── Диспетчер ────────────────────────────────────────────────────

    async def _execute_agent_action(self, agent: Agent, command: Dict):
        action_type = command['action_type']
        params = command['params']
        try:
            if action_type == "initiate_conversation":
                await self._do_initiate(agent, params, command)
            elif action_type in ("send_message", "respond_to_message"):
                await self._do_send(agent, params, command)
            elif action_type == "wait_for_response":
                await self._do_wait(agent, params, command)
            elif action_type == "end_conversation":
                await self._do_end(agent, params, command)
            elif action_type == "move":
                dest = params.get("destination", "Центральная площадь")
                from core.bdi.beliefs import create_self_belief
                agent.beliefs.add_belief(create_self_belief(agent.id, "location", dest))
                self._log_event("move", f"{agent.name} → {dest}", [agent.id])
                agent.confirm_action_execution(
                    command['intention_id'], command['step_object'], True, f"Moved to {dest}")
                # Solo Satiety: засчитываем индивидуальное действие
                agent.deliberation_cycle.notify_solo_action("move")
            elif action_type in ("think", "observe", "search", "communicate",
                                 "wait", "help", "request", "give", "use", "acquire", "express"):
                agent.confirm_action_execution(
                    command['intention_id'], command['step_object'], True, f"Done: {action_type}")
                # Solo Satiety: засчитываем индивидуальные действия (кроме communicate)
                if action_type != "communicate":
                    agent.deliberation_cycle.notify_solo_action(action_type)
            else:
                print(f"⚠️  Unknown action: {action_type}")
                agent.confirm_action_execution(
                    command['intention_id'], command['step_object'], False, f"Unknown: {action_type}")
        except Exception as e:
            print(f"⚠️  Error in {action_type} ({agent.name}): {e}")
            traceback.print_exc()
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], False, str(e))

    # ── Конкретные обработчики ────────────────────────────────────────

    async def _do_initiate(self, agent: Agent, params: Dict, command: Dict):
        target_id = params.get("target")
        topic = params.get("topic", "general")

        if not target_id or target_id not in self.agents:
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], False, f"Unknown: {target_id}")
            return

        # ── Context Awareness: проверяем кулдаун цели и собственный соц. блок ──
        dg = agent.deliberation_cycle.desire_generator
        if dg.is_on_cooldown(target_id):
            tname = self.agents[target_id].name
            print(f"🚫 {agent.name}: {tname} на кулдауне — отменяем initiate_conversation")
            # Перематываем план к концу — разговор не нужен
            for intention in agent.intentions:
                if intention.id == command['intention_id'] and intention.plan:
                    intention.plan.skip_to_end_conversation(intention.current_step)
                    intention.current_step = len(intention.plan.steps)  # завершаем план
                    break
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], False,
                f"Target {target_id} is on cooldown — conversation aborted")
            return

        if dg.is_globally_social_blocked():
            print(f"🚫 {agent.name}: соц. блок [{dg.get_social_block_reason()}] — "
                  f"отменяем initiate_conversation")
            for intention in agent.intentions:
                if intention.id == command['intention_id'] and intention.plan:
                    intention.plan.skip_to_end_conversation(intention.current_step)
                    intention.current_step = len(intention.plan.steps)
                    break
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], False,
                "Social block active — conversation aborted")
            return

        existing = self.communication_hub.get_active_conversation(agent.id, target_id)
        if existing:
            from core.bdi.beliefs import create_self_belief
            agent.beliefs.add_belief(
                create_self_belief(agent.id, "current_conversation", existing.id))
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], True, f"Joined: {existing.id}")
            return

        conv = self.communication_hub.start_conversation(agent.id, target_id, topic)
        from core.bdi.beliefs import create_self_belief
        agent.beliefs.add_belief(
            create_self_belief(agent.id, "current_conversation", conv.id))
        tname = self.agents[target_id].name
        print(f"💬 {agent.name} начинает разговор с {tname} о '{topic}'")
        self._log_event("conversation_start",
                        f"{agent.name} начал разговор с {tname} о '{topic}'",
                        [agent.id, target_id],
                        {"conversation_id": conv.id, "topic": topic})
        agent.confirm_action_execution(
            command['intention_id'], command['step_object'], True, f"Started: {conv.id}")

    async def _do_send(self, agent: Agent, params: Dict, command: Dict):
        target_id = params.get("target")
        msg_type_str = params.get("message_type", "statement")
        topic = params.get("topic", "general")
        requires_response = params.get("requires_response", False)
        timeout = params.get("response_timeout", params.get("timeout", 30.0))
        tone = params.get("tone", "friendly")
        in_reply_to = params.get("in_reply_to")
        incoming = params.get("incoming_content", "")

        if not target_id or target_id not in self.agents:
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], False, f"Unknown: {target_id}")
            return

        # ── Context Awareness: проверяем что разговор ещё жив ──────────
        conv = self.communication_hub.get_active_conversation(agent.id, target_id)
        if not conv:
            # Разговор уже завершён (собеседник вызвал end_conversation раньше нас).
            # Не отправляем сообщения в пустоту — сразу завершаем шаг как «ненужный».
            tname = self.agents[target_id].name
            print(f"🚫 {agent.name}: разговор с {tname} уже закрыт — "
                  f"пропускаем [{msg_type_str}] (не монологим)")
            # Перематываем план к end_conversation чтобы подчистить намерение
            for intention in agent.intentions:
                if intention.id == command['intention_id'] and intention.plan:
                    new_idx = intention.plan.skip_to_end_conversation(intention.current_step)
                    intention.current_step = new_idx
                    break
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], True,
                f"Skipped [{msg_type_str}] — conversation already closed")
            return

        ctx_msgs = conv.get_context_for_agent(agent.id, max_messages=5)

        content = self.llm_interface.generate_dialogue(
            agent_name=agent.name,
            personality=agent.personality.dict(),
            context=f"Разговор о {topic}" if topic else "Разговор",
            conversation_history=ctx_msgs,
            message_type=msg_type_str,
            incoming_message=incoming
        )

        type_map = {
            "greeting": MessageType.GREETING, "question": MessageType.QUESTION,
            "answer": MessageType.ANSWER, "statement": MessageType.STATEMENT,
            "farewell": MessageType.FAREWELL,
        }
        msg = Message(
            id=str(uuid.uuid4()), sender_id=agent.id, receiver_id=target_id,
            content=content, message_type=type_map.get(msg_type_str, MessageType.STATEMENT),
            conversation_id=conv.id, topic=topic,
            requires_response=requires_response, response_timeout=timeout,
            tone=tone, in_reply_to=in_reply_to
        )
        await self.communication_hub.send_message(msg)

        tname = self.agents[target_id].name
        print(f"💬 {agent.name} → {tname} [{msg_type_str}]: {content}")
        self._log_event("message", f"{agent.name} → {tname}: {content}",
                        [agent.id, target_id],
                        {"message_id": msg.id, "conversation_id": conv.id,
                         "message_type": msg_type_str, "content": content,
                         "sender_name": agent.name, "receiver_name": tname})
        self._update_relationship(agent.id, target_id, 0.03)
        agent.confirm_action_execution(
            command['intention_id'], command['step_object'], True,
            f"Sent [{msg_type_str}]: {content[:50]}")

    async def _do_wait(self, agent: Agent, params: Dict, command: Dict):
        expected_from = params.get("expected_from")
        on_timeout = params.get("on_timeout", "end")  # "end" или "continue"
        # Позволяем плану задать своё число тиков ожидания (для ответчика — больше)
        max_ticks = int(params.get("max_ticks", self.MAX_WAIT_TICKS))
        intention_id = command['intention_id']

        # Ищем любое сообщение от ожидаемого агента в этом тике
        incoming_msgs = [
            m for m in self._tick_messages.get(agent.id, [])
            if m.sender_id == expected_from
        ]
        response = incoming_msgs[0] if incoming_msgs else None

        if response:
            msg_type = response.message_type.value
            # Farewell = собеседник прощается → сразу END, не ждём
            if msg_type in ('farewell', 'ack'):
                print(f"👋 {agent.name}: получил [{msg_type}] от {expected_from} → END")
                for intention in agent.intentions:
                    if intention.id == intention_id and intention.plan:
                        new_idx = intention.plan.skip_to_end_conversation(intention.current_step)
                        intention.current_step = new_idx
                        break
                self._wait_tick_counters.pop(intention_id, None)
                agent.confirm_action_execution(
                    command['intention_id'], command['step_object'], True,
                    f"Got farewell from {expected_from} — ending")
                return

            # Нормальный ответ — фиксируем и продолжаем план
            print(f"✅ {agent.name} получил ожидаемый ответ от {expected_from}: "
                  f"{response.content[:60]}")
            agent.beliefs.add_belief(Belief(
                type=BeliefType.EVENT, subject=f"reply_{response.id}", key="received",
                value={"from": response.sender_id, "content": response.content,
                       "type": msg_type},
                confidence=1.0
            ))
            self._wait_tick_counters.pop(intention_id, None)
            agent.confirm_action_execution(
                command['intention_id'], command['step_object'], True,
                f"Got reply: {response.content[:50]}")
        else:
            self._wait_tick_counters[intention_id] += 1
            ticks = self._wait_tick_counters[intention_id]
            if ticks >= max_ticks:
                # Фикс Race Condition: перед перемоткой делаем финальный взгляд в inbox.
                # Сообщение могло прийти в самом конце тика — не хотим его пропустить.
                late_msg = next(
                    (m for m in self._tick_messages.get(agent.id, [])
                     if m.sender_id == expected_from),
                    None
                )
                if late_msg and late_msg.message_type.value not in ('farewell', 'ack'):
                    print(f"⏱️→✅ {agent.name}: поймал запоздалый ответ от {expected_from}!")
                    self._wait_tick_counters.pop(intention_id, None)
                    agent.confirm_action_execution(
                        command['intention_id'], command['step_object'], True,
                        f"Late reply caught: {late_msg.content[:50]}")
                    return

                print(f"⏱️  {agent.name}: timeout ({ticks} тиков) от {expected_from} → "
                      f"{'END' if on_timeout == 'end' else 'continue'}")
                self._wait_tick_counters.pop(intention_id, None)

                if on_timeout == "end":
                    # Перематываем к END_CONVERSATION (не монологим)
                    for intention in agent.intentions:
                        if intention.id == intention_id and intention.plan:
                            new_idx = intention.plan.skip_to_end_conversation(intention.current_step)
                            intention.current_step = new_idx
                            break
                    agent.confirm_action_execution(
                        command['intention_id'], command['step_object'], True,
                        "Timeout — skipped to end_conversation")
                else:
                    # continue: передаём управление дальше по плану
                    agent.confirm_action_execution(
                        command['intention_id'], command['step_object'], True,
                        "Timeout — continuing plan")
            else:
                print(f"⏳ {agent.name}: ждёт от {expected_from} "
                      f"(тик {ticks}/{max_ticks})")

    async def _do_end(self, agent: Agent, params: Dict, command: Dict):
        target_id = params.get("target")

        conv = self.communication_hub.get_active_conversation(agent.id, target_id)
        if conv:
            self.communication_hub.end_conversation(conv.id)
            tname = self.agents[target_id].name if target_id in self.agents else target_id
            print(f"🔚 {agent.name} завершил разговор с {tname}")
            self._log_event("conversation_end",
                            f"{agent.name} завершил разговор с {tname}",
                            [agent.id, target_id])
            agent.beliefs.remove_belief(BeliefType.SELF, agent.id, "current_conversation")

            # Уведомляем ОБОИХ агентов — запускает кулдаун в DesireGenerator
            # (вызывается НЕМЕДЛЕННО, до следующего тика)
            agent.notify_conversation_ended(target_id)
            print(f"⏸️  {agent.name}: кулдаун соц. желаний запущен (≥{agent.deliberation_cycle.desire_generator.min_rest_ticks} тиков)")
            if target_id in self.agents:
                self.agents[target_id].notify_conversation_ended(agent.id)
                print(f"⏸️  {tname}: кулдаун соц. желаний запущен")

        agent.confirm_action_execution(
            command['intention_id'], command['step_object'], True, "Conversation ended")

    def stop_simulation(self):
        self.running = False