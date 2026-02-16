from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import json
import asyncio
from .agent import Agent
from .simulator import WorldSimulator
from .communication import Message

app = FastAPI(title="Cyber Hackathon - Virtual World Simulator API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the world simulator
simulator = WorldSimulator()

# Store active WebSocket connections
active_connections: List[WebSocket] = []

@app.on_event("startup")
async def startup_event():
    # Add some sample agents
    agent1 = Agent("1", "Alice")
    agent2 = Agent("2", "Bob")
    agent3 = Agent("3", "Charlie")
    
    simulator.add_agent(agent1)
    simulator.add_agent(agent2)
    simulator.add_agent(agent3)
    
    # Start the simulation in the background
    asyncio.create_task(simulator.run_simulation())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send real-time updates to the client
            await send_world_state(websocket)
            await asyncio.sleep(1)  # Update every second
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def send_world_state(websocket: WebSocket):
    """Send the current world state to a WebSocket client"""
    world_state = {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "emotions": agent.emotions.dict(),
                "relationships": {
                    rel_id: rel.dict() 
                    for rel_id, rel in agent.relationships.items()
                },
                "memory_count": len(agent.memories)
            }
            for agent in simulator.agents.values()
        ],
        "recent_messages": [
            {
                "sender_id": msg.sender_id,
                "receiver_id": msg.receiver_id,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in simulator.communication_hub.get_recent_messages(10)
        ]
    }
    
    await websocket.send_text(json.dumps(world_state))

@app.get("/")
def read_root():
    return {"message": "Cyber Hackathon - Virtual World Simulator API"}

@app.get("/agents")
def get_agents():
    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "personality": agent.personality.dict(),
                "emotions": agent.emotions.dict(),
                "relationships": {
                    rel_id: rel.dict() 
                    for rel_id, rel in agent.relationships.items()
                },
                "memory_count": len(agent.memories)
            }
            for agent in simulator.agents.values()
        ]
    }

@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    if agent_id not in simulator.agents:
        return {"error": "Agent not found"}
        
    agent = simulator.agents[agent_id]
    return {
        "id": agent.id,
        "name": agent.name,
        "personality": agent.personality.dict(),
        "emotions": agent.emotions.dict(),
        "relationships": {
            rel_id: rel.dict() 
            for rel_id, rel in agent.relationships.items()
        },
        "memories": [
            mem.dict() 
            for mem in agent.memories
        ],
        "current_plan": agent.current_plan
    }

@app.post("/agents")
def create_agent(name: str):
    agent_id = str(len(simulator.agents) + 1)
    agent = Agent(agent_id, name)
    simulator.add_agent(agent)
    return {"agent": agent_id}

@app.post("/events")
def add_event(event_description: str):
    simulator.add_global_event(event_description)
    # Broadcast to all WebSocket connections
    asyncio.create_task(broadcast_to_clients({
        "type": "event",
        "description": event_description
    }))
    return {"message": "Event added"}

@app.post("/messages")
def send_message(sender_id: str, receiver_id: str, content: str):
    if sender_id not in simulator.agents or receiver_id not in simulator.agents:
        return {"error": "Agent not found"}
        
    message = Message(sender_id, receiver_id, content)
    asyncio.create_task(simulator.communication_hub.send_message(message))
    
    # Broadcast to all WebSocket connections
    asyncio.create_task(broadcast_to_clients({
        "type": "message",
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content
    }))
    
    return {"message": "Message sent"}

@app.post("/control/speed")
def set_speed(speed: float):
    simulator.set_time_speed(speed)
    return {"message": f"Speed set to {speed}x"}

async def broadcast_to_clients(message: dict):
    """Broadcast a message to all active WebSocket connections"""
    for connection in active_connections:
        try:
            await connection.send_text(json.dumps(message))
        except:
            pass  # Ignore failed connections