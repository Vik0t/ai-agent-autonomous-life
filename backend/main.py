# backend/main.py
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder # <--- Добавлено

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
from simulator import WorldSimulator

simulator = WorldSimulator()
active_connections: list[WebSocket] = []

async def broadcast_state():
    print("📡 Broadcast task started...")
    while True:
        try:
            if active_connections:
                # Кодируем данные в JSON-совместимый формат
                agents_data = [agent.to_dict() for agent in simulator.agents.values()]
                state = jsonable_encoder({
                    "type": "state_update",
                    "agents": agents_data,
                    "time_speed": simulator.time_speed
                })
                
                disconnected = []
                for connection in active_connections:
                    try:
                        await connection.send_json(state)
                    except Exception as e:
                        print(f"❌ WebSocket Send Error: {e}")
                        disconnected.append(connection)
                
                for conn in disconnected:
                    if conn in active_connections:
                        active_connections.remove(conn)
            
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Error in broadcast_state: {e}")
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация
    configs = [
        ("agent-0", "Алекса", "🤖", {"openness": 0.8, "conscientiousness": 0.6, "extraversion": 0.9, "agreeableness": 0.7, "neuroticism": 0.3}),
        ("agent-1", "Нексус", "👾", {"openness": 0.4, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.5, "neuroticism": 0.6}),
    ]
    
    for aid, name, avatar, personality in configs:
        agent = Agent(aid, name, avatar, personality, llm_interface=simulator.llm_interface)
        simulator.add_agent(agent)
    
    sim_task = asyncio.create_task(simulator.run_simulation())
    broadcast_task = asyncio.create_task(broadcast_state())
    
    yield
    simulator.running = False

app = FastAPI(title="Cyber BDI Simulator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"✅ Client connected. Total: {len(active_connections)}")
    try:
        # Отправляем начальное состояние (тоже через энкодер)
        init_data = jsonable_encoder({
            "type": "init",
            "agents": [agent.to_dict() for agent in simulator.agents.values()]
        })
        await websocket.send_json(init_data)
        
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print("❌ Client disconnected")
    except Exception as e:
        print(f"⚠️ WS Error: {e}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")

@app.get("/api/agents")
async def get_agents():
    return jsonable_encoder({"agents": [a.to_dict() for a in simulator.agents.values()]})

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)