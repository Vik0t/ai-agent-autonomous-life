# backend/simulator.py
import asyncio
import traceback
from typing import Dict, List
from agent import Agent
from communication import CommunicationHub, Message
from llm import LLMInterface
from core.bdi.beliefs import BeliefType
from core.bdi.deliberation import create_perception

class WorldSimulator:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.communication_hub = CommunicationHub()
        self.llm_interface = LLMInterface()
        self.running = False
        self.time_speed = 1.0

    def add_agent(self, agent: Agent):
        self.agents[agent.id] = agent
        self.communication_hub.register_agent(agent.id)
        print(f"--- Agent {agent.name} added to simulator ---")

    async def run_simulation(self):
        self.running = True
        print("🚀 Simulation loop started...")
        while self.running:
            try:
                start_time = asyncio.get_event_loop().time()
                await self._process_game_tick()
                
                # Контроль скорости
                elapsed = asyncio.get_event_loop().time() - start_time
                wait_time = max(0.1, (5.0 / self.time_speed) - elapsed)
                await asyncio.sleep(wait_time)
            except Exception as e:
                print(f"❌ CRITICAL ERROR IN SIMULATION: {e}")
                traceback.print_exc()
                await asyncio.sleep(2)

    async def _process_game_tick(self):
        """Один такт жизни мира"""
        for agent_id, agent in self.agents.items():
            # 1. Собираем восприятия
            perceptions = await self._gather_perceptions(agent)
            
            # 2. Агент думает (BDI)
            # print(f"🧠 {agent.name} is thinking...")
            actions = agent.think(perceptions)
            
            # 3. Выполняем действия
            if actions:
                for action_cmd in actions:
                    print(f"⚡ {agent.name} executing: {action_cmd['action_type']} | {action_cmd['params']}")
                    await self._execute_agent_action(agent, action_cmd)

    async def _gather_perceptions(self, agent: Agent) -> List[Dict]:
        perceptions = []
        
        # Сообщения
        messages = await self.communication_hub.receive_messages(agent.id)
        for msg in messages:
            print(f"📩 {agent.name} received message: {msg.content}")
            perceptions.append(create_perception("communication", msg.sender_id, {"content": msg.content}))
            
        # Наблюдение за миром (другими агентами)
        for other_id, other_agent in self.agents.items():
            if other_id != agent.id:
                # Берем локацию из убеждений другого агента (или просто константу)
                loc_belief = other_agent.beliefs.get_belief(BeliefType.SELF, other_id, "location")
                location = loc_belief.value if loc_belief else "Unknown"
                
                perceptions.append(create_perception(
                    "observation", other_id, {"location": location}
                ))
        return perceptions

    async def _execute_agent_action(self, agent: Agent, command: Dict):
        """Физическое воплощение действий в симуляторе"""
        action_type = command['action_type']
        params = command['params']
        success = True
        msg = "Done"

        try:
            if action_type == "communicate":
                target_id = params.get("target")
                # Генерируем текст через LLM если нужно
                content = self.llm_interface.generate_dialogue(
                    agent.name, agent.personality.dict(), f"Talking to {target_id}"
                )
                message = Message(agent.id, target_id, content)
                await self.communication_hub.send_message(message)
                msg = content

            elif action_type == "move":
                dest = params.get("destination", "Central Square")
                # Обновляем убеждение о себе (вместо реальных координат)
                from core.bdi.beliefs import create_self_belief
                agent.beliefs.add_belief(create_self_belief(agent.id, "location", dest))
                msg = f"Moved to {dest}"
            
            # Подтверждаем агенту, что действие выполнено (для прогресса намерения)
            agent.confirm_action_execution(command['intention_id'], command['step_object'], success, msg)
        
        except Exception as e:
            print(f"⚠️ Error executing {action_type}: {e}")
            agent.confirm_action_execution(command['intention_id'], command['step_object'], False, str(e))

    def stop_simulation(self):
        self.running = False