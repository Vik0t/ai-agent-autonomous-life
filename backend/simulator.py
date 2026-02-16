from typing import Dict, List
import asyncio
import time
from agent import Agent
from communication import CommunicationHub, Message
from llm import LLMInterface
from memory import VectorMemory

class WorldSimulator:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.communication_hub = CommunicationHub()
        self.llm_interface = LLMInterface()
        self.vector_memory = VectorMemory()
        self.running = False
        self.time_speed = 1.0  # 1.0 = real time, 2.0 = 2x speed, etc.
        
    def add_agent(self, agent: Agent):
        """Add an agent to the simulation"""
        self.agents[agent.id] = agent
        self.communication_hub.register_agent(agent.id)
        
    def remove_agent(self, agent_id: str):
        """Remove an agent from the simulation"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            
    async def run_simulation(self):
        """Main simulation loop"""
        self.running = True
        while self.running:
            # Process agent actions
            await self._process_agent_actions()
            
            # Process communications
            await self._process_communications()
            
            # Wait based on time speed
            await asyncio.sleep(1.0 / self.time_speed)
            
    async def _process_agent_actions(self):
        """Process actions for all agents"""
        for agent_id, agent in self.agents.items():
            # Generate a plan if the agent doesn't have one
            if not agent.current_plan:
                situation = f"Agent {agent.name} is in the world with {len(self.agents)} other agents."
                agent.current_plan = self.llm_interface.generate_plan(
                    agent.personality.dict(), 
                    situation
                )
                
            # Process the plan (simplified)
            if agent.current_plan:
                # In a real implementation, you would break down the plan into actions
                # For now, we'll just have agents send messages
                if "communicate" in agent.current_plan.lower() or "talk" in agent.current_plan.lower():
                    await self._agent_communicate(agent)
                    
    async def _agent_communicate(self, agent: Agent):
        """Have an agent communicate with others"""
        # Find another agent to communicate with
        other_agents = [a for a in self.agents.values() if a.id != agent.id]
        if not other_agents:
            return
            
        # Select a random other agent
        import random
        other_agent = random.choice(other_agents)
        
        # Generate a message
        context = f"Agent {agent.name} wants to communicate with {other_agent.name}"
        message_content = self.llm_interface.generate_dialogue(
            agent.personality.dict(),
            context
        )
        
        # Send the message
        message = Message(agent.id, other_agent.id, message_content)
        await self.communication_hub.send_message(message)
        
        # Update relationships
        agent.update_relationship(other_agent.id, 0.1, 0.1)
        other_agent.update_relationship(agent.id, 0.1, 0.1)
        
        # Add to memory
        agent.add_memory(f"Sent message to {other_agent.name}: {message_content}")
        other_agent.add_memory(f"Received message from {agent.name}: {message_content}")
        
    async def _process_communications(self):
        """Process incoming messages for all agents"""
        for agent_id, agent in self.agents.items():
            messages = await self.communication_hub.receive_messages(agent_id)
            for message in messages:
                # Update emotions based on message content
                agent.update_emotions(message.content)
                
                # Generate a response
                context = f"Agent {agent.name} received a message from Agent {self.agents[message.sender_id].name}"
                response_content = self.llm_interface.generate_dialogue(
                    agent.personality.dict(),
                    context,
                    message.content
                )
                
                # Send response
                response_message = Message(agent_id, message.sender_id, response_content)
                await self.communication_hub.send_message(response_message)
                
                # Update relationships
                agent.update_relationship(message.sender_id, 0.05, 0.05)
                
                # Add to memory
                agent.add_memory(f"Responded to {self.agents[message.sender_id].name}: {response_content}")
                
    def stop_simulation(self):
        """Stop the simulation"""
        self.running = False
        
    def set_time_speed(self, speed: float):
        """Set the simulation speed"""
        self.time_speed = max(0.1, speed)  # Minimum 0.1x speed
        
    def add_global_event(self, event_description: str):
        """Add a global event that affects all agents"""
        # Broadcast the event to all agents
        self.communication_hub.broadcast_message("SYSTEM", event_description)
        
        # Add to each agent's memory
        for agent in self.agents.values():
            agent.add_memory(f"Global event: {event_description}", importance=0.9)
            agent.update_emotions(event_description)