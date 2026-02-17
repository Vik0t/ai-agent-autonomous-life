# backend/main.py
"""
Cyber BDI Simulator с полной базой данных и Social Engine
"""

import os
import sys
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импорты модулей
from agent import Agent
from simulator import WorldSimulator
from communication import Message
from database.Database import Database, get_db
from database.social_engine import SocialEngine, get_social_engine
from database.memory import VectorMemory, get_memory
from database.social_types import SocialEvent, SocialEventType, SocialSentiment, SocialEventCreate, SocialEventType, SummarizeRequest

simulator = WorldSimulator()
active_connections: list[WebSocket] = []

async def broadcast_state():
    while True:
        try:
            if active_connections:
                agents_data = [agent.to_dict() for agent in simulator.agents.values()]
                recent_msgs = simulator.communication_hub.get_recent_messages(10)
                recent_events = simulator.get_recent_events(20)
                relationships = simulator.get_relationships_data()

                state = jsonable_encoder({
                    "type": "state_update",
                    "agents": agents_data,
                    "time_speed": simulator.time_speed,
                    "recent_messages": [
                        {
                            "id": m.id,
                            "sender_id": m.sender_id,
                            "receiver_id": m.receiver_id,
                            "content": m.content,
                            "message_type": m.message_type.value,
                            "conversation_id": m.conversation_id,
                            "topic": m.topic,
                            "timestamp": m.timestamp
                        }
                        for m in recent_msgs
                    ],
                    "recent_events": recent_events,
                    "relationships": relationships,
                    "conversations": [
                        c.to_dict()
                        for c in simulator.communication_hub.get_all_active_conversations()
                    ]
                })

                for connection in active_connections:
                    try:
                        await connection.send_json(state)
                    except Exception:
                        pass
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Broadcast error: {e}")
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Cyber BDI Simulator...")
    # # ============================================
    # # УДАЛИТЬ СТАРУЮ БД (только для разработки!)
    # # ============================================
    # db_path = "database/agents.db"
    # if os.path.exists(db_path):
    #     os.remove(db_path)
    #     print("🗑️  Старая БД удалена")
    # ============================================
    # 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
    # ============================================
    print("📁 Инициализация базы данных...")
    db = Database()
    
    # Создать тестовых агентов в БД
    db.add_agent("agent-0", "Алекса", "🤖, экстраверт, дружелюбная")
    db.add_agent("agent-1", "Нексус", "👾, аналитичный, осторожный")
    
    # Добавить начальные отношения
    social = SocialEngine(db)
    social.get_relationship("agent-0", "agent-1")  # Инициализировать нейтральные
    
    print("✅ База данных готова!")
    
    # ============================================
    # 2. ИНИЦИАЛИЗАЦИЯ АГЕНТОВ
    # ============================================
    configs = [
        (
            "agent-0", "Алекса", "🤖",
            {
                "openness": 0.85,
                "conscientiousness": 0.6,
                "extraversion": 0.9,
                "agreeableness": 0.8,
                "neuroticism": 0.2
            }
        ),
        (
            "agent-1", "Нексус", "👾",
            {
                "openness": 0.7,
                "conscientiousness": 0.8,
                "extraversion": 0.45,
                "agreeableness": 0.6,
                "neuroticism": 0.5
            }
        ),
    ]

    for aid, name, avatar, personality in configs:
        agent = Agent(aid, name, avatar, personality, llm_interface=simulator.llm_interface)
        simulator.add_agent(agent)

    # ============================================
    # 3. ЗАПУСК СИМУЛЯЦИИ
    # ============================================
    asyncio.create_task(simulator.run_simulation())
    asyncio.create_task(broadcast_state())
    
    print("✅ Симуляция запущена!")
    yield
    simulator.running = False
    print("🛑 Симуляция остановлена")

app = FastAPI(title="Cyber BDI Simulator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================
# WebSocket — стриминг состояния
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Инициальные данные
        db = Database()
        social = SocialEngine(db)
        relationships = social.get_graph_data()
        
        init_data = jsonable_encoder({
            "type": "init",
            "agents": [agent.to_dict() for agent in simulator.agents.values()],
            "time_speed": simulator.time_speed,
            "relationships": relationships
        })
        await websocket.send_json(init_data)
        while True:
            data = await websocket.receive_json()
            # Handle messages from frontend
            if data.get('type') == 'send_message':
                # Send message to agent
                msg = Message(
                    sender_id=data.get('sender_id', 'user'),
                    receiver_id=data['receiver_id'],
                    content=data['content'],
                    topic=data.get('topic', 'user_input')
                )
                await simulator.communication_hub.send_message(msg)
                simulator._log_event(
                    "user_message",
                    f"Пользователь → {data['receiver_id']}: {data['content'][:60]}",
                    [data['receiver_id']],
                    {"content": data['content']}
                )
            elif data.get('type') == 'add_event':
                # Add global event
                event_desc = data.get('event_description', 'Global Event')
                simulator._log_event("user_event", f"Событие: {event_desc}", list(simulator.agents.keys()))
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ============================================
# REST API - БАЗОВАЯ ФУНКЦИОНАЛЬНОСТЬ
# ============================================

@app.get("/api/agents")
async def get_agents(db: Database = Depends(get_db)):
    return {"agents": db.get_all_agents()}

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, db: Database = Depends(get_db)):
    """Детальный профиль агента для инспектора."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.get("/api/events")
async def get_events(limit: int = 50, db: Database = Depends(get_db)):
    """Лента событий для дашборда."""
    return {"events": db.get_recent_events(limit)}

@app.get("/api/conversations")
async def get_conversations(db: Database = Depends(get_db)):
    """Все диалоги."""
    return {"conversations": []}  # TODO: Интеграция с communication_hub

@app.get("/api/messages")
async def get_messages(limit: int = 50, db: Database = Depends(get_db)):
    """История сообщений."""
    return {"messages": []}  # TODO: Интеграция с communication_hub

@app.post("/api/messages")
async def send_message(data: dict = Body(...), db: Database = Depends(get_db)):
    """Отправить сообщение."""
    # TODO: Интеграция с communication_hub
    return {"status": "sent"}

@app.post("/api/events")
async def add_event(data: dict = Body(...), db: Database = Depends(get_db)):
    """Ввести глобальное событие."""
    # TODO: Интеграция с simulator
    return {"status": "ok"}

@app.post("/api/agents/{agent_id}/inject")
async def inject_message(agent_id: str, data: dict = Body(...), db: Database = Depends(get_db)):
    """Ввести сообщение агенту."""
    # TODO: Интеграция с simulator
    return {"status": "injected"}

@app.post("/api/agents")
async def create_agent(data: dict = Body(...)):
    """Создать нового агента."""
    try:
        agent_id = f"agent-{int(time.time() * 1000)}"
        name = data.get("name", f"Агент-{agent_id[-4:]}")
        avatar = data.get("avatar", "🤖")
        personality = data.get("personality", {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5
        })

        # Создаем нового агента
        agent = Agent(agent_id, name, avatar, personality, llm_interface=simulator.llm_interface)
        simulator.add_agent(agent)

        # Регистрируем агента в системе коммуникации
        simulator.communication_hub.register_agent(agent_id)

        return {"status": "ok", "agent": agent.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.post("/api/control/speed")
async def set_speed(data: dict = Body(...)):
    simulator.time_speed = float(data.get("speed", 1.0))
    return {"status": "ok", "speed": simulator.time_speed}

@app.get("/api/state")
async def get_full_state(db: Database = Depends(get_db)):
    """Полное состояние."""
    social = SocialEngine(db)
    return jsonable_encoder({
        "agents": db.get_all_agents(),
        "relationships": social.get_graph_data(),
        "recent_events": db.get_recent_events(30),
        "recent_messages": [],  # TODO
        "time_speed": simulator.time_speed
    })

# ============================================
# SOCIAL ENGINE API
# ============================================

@app.post("/api/social/event")
def process_social_event(
    event: SocialEventCreate,
    social: SocialEngine = Depends(get_social_engine)
):
    """Обработать социальное событие."""
    try:
        event_type = SocialEventType(event.event_type)
        sentiment = SocialSentiment.positive if event.sentiment > 0 else SocialSentiment.negative
        
        social_event = SocialEvent(
            event_type=event_type,
            agent_from=event.agent_from,
            agent_to=event.agent_to,
            sentiment=sentiment,
            description=event.description,
            witnesses=event.witnesses
        )
        social.process_social_event(social_event)
        rel = social.get_relationship(event.agent_from, event.agent_to)
        return {"status": "processed", "relationship": rel.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_type")

@app.get("/api/social/relationship/{agent_from}/{agent_to}")
def get_relationship(agent_from: str, agent_to: str, social: SocialEngine = Depends(get_social_engine)):
    """Получить отношения."""
    rel = social.get_relationship(agent_from, agent_to)
    return rel.to_dict()

@app.get("/api/social/relationships/{agent_id}")
def get_all_relationships(agent_id: str, social: SocialEngine = Depends(get_social_engine)):
    """Все отношения агента."""
    relationships = social.get_all_relationships(agent_id)
    return {"agent_id": agent_id, "relationships": [rel.to_dict() for rel in relationships]}

@app.get("/api/social/context/{agent_id}/{target_id}")
def get_social_context(agent_id: str, target_id: str, social: SocialEngine = Depends(get_social_engine)):
    """Социальный контекст для LLM."""
    context = social.get_social_context_for_llm(agent_id, target_id)
    rel = social.get_relationship(agent_id, target_id)
    return {"context_text": context, "relationship": rel.to_dict()}

@app.get("/api/social/graph")
def get_social_graph(social: SocialEngine = Depends(get_social_engine)):
    """Граф отношений."""
    return social.get_graph_data()

@app.post("/api/social/decay/{agent_id}")
def apply_decay(agent_id: str, days_passed: float = 1.0, social: SocialEngine = Depends(get_social_engine)):
    """Забывание отношений."""
    social.apply_relationship_decay(agent_id, days_passed)
    return {"status": "decay_applied"}

@app.get("/api/social/desire-multiplier/{agent_id}/{target_id}")
def get_desire_multiplier(agent_id: str, target_id: str, desire_type: str, social: SocialEngine = Depends(get_social_engine)):
    """Множитель желания."""
    multiplier = social.get_desire_multiplier(agent_id, target_id, desire_type)
    return {"multiplier": multiplier}

@app.get("/api/social/credibility/{believer_id}/{source_id}")
def get_credibility(believer_id: str, source_id: str, social: SocialEngine = Depends(get_social_engine)):
    """Доверие к информации."""
    credibility = social.get_filtered_belief_credibility(believer_id, source_id)
    return {"credibility": credibility}

# ============================================
# VECTOR MEMORY API
# ============================================

@app.post("/api/memory/add")
def add_memory(memory_data: dict = Body(...), memory: VectorMemory = Depends(get_memory)):
    """Добавить воспоминание."""
    memory_id = memory.add_episodic_memory(**memory_data)
    return {"memory_id": memory_id}

@app.post("/api/memory/recall")
def recall_memories(recall_data: dict = Body(...), memory: VectorMemory = Depends(get_memory)):
    """Извлечь воспоминания."""
    memories = memory.recall_relevant_memories(**recall_data)
    formatted = memory.format_memories_for_llm(memories)
    return {"memories": memories, "formatted_for_llm": formatted}

@app.post("/api/memory/summarize")
def summarize_memories(
    request: SummarizeRequest,
    memory: VectorMemory = Depends(get_memory)
):
    """Суммаризовать старые воспоминания."""
    import os
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")
    
    result = memory.summarize_old_memories(
        agent_id=request.agent_id,
        older_than_days=request.older_than_days,
        openrouter_api_key=api_key,
        model=request.model,
        cluster_by=request.cluster_by
    )
    return result

# ============================================
# Статика
# ============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
