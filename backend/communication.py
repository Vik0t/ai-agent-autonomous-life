from typing import Dict, List
import asyncio
import json

class Message:
    def __init__(self, sender_id: str, receiver_id: str, content: str, message_type: str = "text"):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.content = content
        self.message_type = message_type
        self.timestamp = asyncio.get_event_loop().time()

class CommunicationHub:
    def __init__(self):
        self.messages: List[Message] = []
        self.agent_connections: Dict[str, asyncio.Queue] = {}
        
    def register_agent(self, agent_id: str):
        """Register an agent to receive messages"""
        if agent_id not in self.agent_connections:
            self.agent_connections[agent_id] = asyncio.Queue()
            
    async def send_message(self, message: Message):
        """Send a message from one agent to another"""
        self.messages.append(message)
        
        # If the receiver is registered, add the message to their queue
        if message.receiver_id in self.agent_connections:
            await self.agent_connections[message.receiver_id].put(message)
            
    async def receive_messages(self, agent_id: str) -> List[Message]:
        """Get all pending messages for an agent"""
        if agent_id not in self.agent_connections:
            return []
            
        messages = []
        queue = self.agent_connections[agent_id]
        
        # Get all available messages without blocking
        while not queue.empty():
            try:
                message = queue.get_nowait()
                messages.append(message)
            except asyncio.QueueEmpty:
                break
                
        return messages
        
    def broadcast_message(self, sender_id: str, content: str):
        """Send a message from one agent to all other agents"""
        for agent_id in self.agent_connections:
            if agent_id != sender_id:
                message = Message(sender_id, agent_id, content, "broadcast")
                self.messages.append(message)
                asyncio.create_task(self._deliver_message(agent_id, message))
                
    async def _deliver_message(self, agent_id: str, message: Message):
        """Deliver a message to an agent's queue"""
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].put(message)
            
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get the most recent messages in the system"""
        return self.messages[-limit:] if self.messages else []