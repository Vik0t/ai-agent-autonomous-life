# backend/main.py
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
from simulator import WorldSimulator
from communication import Message

simulator = WorldSimulator()
active_connections: list[WebSocket] = []

async def broadcast_state():
    while True:
        try:
            if active_connections:
                agents_data = [agent.to_dict() for agent in simulator.agents.values()]
                # Добавляем последние сообщения для фронтенда
                recent_msgs = simulator.communication_hub.get_recent_messages(10)
                
                state = jsonable_encoder({
                    "type": "state_update",
                    "agents": agents_data,
                    "time_speed": simulator.time_speed,
                    "recent_messages": [
                        {"sender_id": m.sender_id, "content": m.content, "timestamp": m.timestamp} 
                        for m in recent_msgs
                    ]
                })
                
                for connection in active_connections:
                    try:
                        await connection.send_json(state)
                    except:
                        pass
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Broadcast error: {e}")
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    configs = [
        ("agent-0", "Алекса", "🤖", {"openness": 0.8, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.7, "neuroticism": 0.3}),
        ("agent-1", "Нексус", "👾", {"openness": 0.4, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.5, "neuroticism": 0.6}),
    ]
    
    for aid, name, avatar, personality in configs:
        agent = Agent(aid, name, avatar, personality, llm_interface=simulator.llm_interface)
        simulator.add_agent(agent)
    
    asyncio.create_task(simulator.run_simulation())
    asyncio.create_task(broadcast_state())
    yield
    simulator.running = False

app = FastAPI(title="Cyber BDI Simulator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        init_data = jsonable_encoder({
            "type": "init",
            "agents": [agent.to_dict() for agent in simulator.agents.values()],
            "time_speed": simulator.time_speed
        })
        await websocket.send_json(init_data)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections: active_connections.remove(websocket)

@app.get("/api/agents")
async def get_agents():
    return {"agents": [a.to_dict() for a in simulator.agents.values()]}

@app.post("/api/events")
async def add_event(data: dict = Body(...)):
    desc = data.get("event_description", "Global Event")
    # Логика события может быть расширена в симуляторе
    return {"status": "ok", "event": desc}

@app.post("/api/messages")
async def send_message(data: dict = Body(...)):
    msg = Message(data['sender_id'], data['receiver_id'], data['content'])
    await simulator.communication_hub.send_message(msg)
    return {"status": "sent"}

@app.post("/api/control/speed")
async def set_speed(data: dict = Body(...)):
    simulator.time_speed = float(data.get("speed", 1.0))
    return {"status": "ok", "speed": simulator.time_speed}

# Статика монтируется ПЕРЕД запуском, но после API
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)