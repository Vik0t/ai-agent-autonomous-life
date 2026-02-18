# backend/main.py
"""
Cyber BDI Simulator — Database-First
- Агенты загружаются из БД при старте
- Лента событий через db.get_recent_events()
- Все эндпоинты полностью реализованы
"""

import os
import sys
import asyncio
import time
import json

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
from simulator import WorldSimulator
from communication import Message
from database.Database import Database, get_db
from database.social_engine import SocialEngine, get_social_engine
from database.memory import VectorMemory, get_memory
from database.social_types import (
    SocialEvent, SocialEventType, SocialSentiment,
    SocialEventCreate, SummarizeRequest,
)

simulator = WorldSimulator()
active_connections: list[WebSocket] = []

print("📁 Инициализация базы данных...")
db: Database = None   # будет инициализирован в lifespan


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_state():
    while True:
        try:
            if active_connections:
                agents_data = [agent.to_dict() for agent in simulator.agents.values()]
                recent_msgs = simulator.communication_hub.get_recent_messages(50)
                recent_events = db.get_events(20)
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
                            "timestamp": m.timestamp,
                        }
                        for m in recent_msgs
                    ],
                    "recent_events": recent_events,
                    "relationships": relationships,
                    "conversations": [
                        c.to_dict()
                        for c in simulator.communication_hub.get_all_active_conversations()
                    ],
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


# ============================================================
# ЗАГРУЗКА АГЕНТОВ ИЗ БД
# ============================================================

def load_agents_from_db():
    """
    Загружает агентов из БД.
    Если БД пустая — симулятор стартует без агентов
    (создать через POST /api/agents).
    """
    existing_agents = db.get_all_agents()
    if not existing_agents:
        print("⚠️  В БД нет агентов. Создайте их через POST /api/agents.")
        return

    print(f"📂 Загружаю {len(existing_agents)} агентов из БД...")
    for agent_data in existing_agents:
        personality = {
            "openness":          agent_data.get("openness", 0.5),
            "conscientiousness": agent_data.get("conscientiousness", 0.5),
            "extraversion":      agent_data.get("extraversion", 0.5),
            "agreeableness":     agent_data.get("agreeableness", 0.5),
            "neuroticism":       agent_data.get("neuroticism", 0.5),
        }
        agent = Agent(
            agent_id=agent_data["id"],
            name=agent_data["name"],
            avatar=agent_data.get("avatar", "🤖"),
            personality_data=personality,
            llm_interface=simulator.llm_interface,
        )
        simulator.add_agent(agent)
        print(f"  ✅ {agent.name} ({agent.id})")


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = Database()
    print("🚀 Запуск Cyber BDI Simulator...")

    # 1. Инициализация отношений (нейтральные по умолчанию)
    social = SocialEngine(db)
    print("✅ База данных готова!")

    # 2. Загрузка агентов из БД
    load_agents_from_db()

    # 3. Регистрируем виртуального пользователя
    simulator.communication_hub.register_agent("user")

    # 4. Запуск симуляцииg
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
    allow_headers=["*"],
)


# ============================================================
# WebSocket — стриминг состояния
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        social = SocialEngine(db)
        relationships = social.get_graph_data()

        init_data = jsonable_encoder({
            "type": "init",
            "agents": [agent.to_dict() for agent in simulator.agents.values()],
            "time_speed": simulator.time_speed,
            "relationships": relationships,
        })
        await websocket.send_json(init_data)

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "send_message":
                receiver_id = data.get("receiver_id", "")
                content = data.get("content", "")
                topic = data.get("topic", "user_input")

                if receiver_id in simulator.agents:
                    if not simulator.communication_hub.get_active_conversation("user", receiver_id):
                        simulator.communication_hub.start_conversation("user", receiver_id, topic)

                msg = Message(
                    sender_id=data.get("sender_id", "user"),
                    receiver_id=receiver_id,
                    content=content,
                    topic=topic,
                    requires_response=True,
                )
                await simulator.communication_hub.send_message(msg)
                simulator._log_event(
                    "user_message",
                    f"Пользователь → {receiver_id}: {content[:60]}",
                    [receiver_id],
                    {"content": content},
                )

            elif data.get("type") == "add_event":
                event_desc = data.get("event_description", "Global Event")
                agent_ids = list(simulator.agents.keys())
                simulator._log_event(
                    "world_event",
                    f"Событие: {event_desc}",
                    agent_ids,
                    {"description": event_desc},
                )
                print(f"🌍 Событие «{event_desc}» → {len(agent_ids)} агентов")

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ============================================================
# REST API — АГЕНТЫ
# ============================================================

@app.get("/api/agents")
async def get_agents():
    """Список всех агентов (живые данные из симулятора)."""
    return {"agents": [a.to_dict() for a in simulator.agents.values()]}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Детальный профиль агента для инспектора."""
    agent = simulator.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    all_beliefs = [b.to_dict() for b in agent.beliefs.beliefs.values()]
    intentions = [i.to_dict() for i in agent.intentions]
    desires = [d.to_dict() for d in agent.desires]

    agent_relationships = []
    for (a, b), strength in simulator.relationships.items():
        if agent_id in (a, b):
            other_id = b if a == agent_id else a
            other = simulator.agents.get(other_id)
            agent_relationships.append({
                "agent_id": other_id,
                "agent_name": other.name if other else other_id,
                "strength": round(strength, 3),
                "type": "friend" if strength > 0.3 else ("enemy" if strength < -0.3 else "neutral"),
            })

    profile = agent.to_dict()
    profile.update({
        "beliefs": all_beliefs[:50],
        "intentions": intentions,
        "desires": desires[:10],
        "relationships": agent_relationships,
    })
    return profile


@app.post("/api/agents")
async def create_agent(data: dict = Body(...)):
    """Создать нового агента и сохранить в БД."""
    try:
        agent_id = f"agent-{int(time.time() * 1000)}"
        name = data.get("name", f"Агент-{agent_id[-4:]}")
        avatar = data.get("avatar", "🤖")
        personality = data.get("personality", {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
        })

        agent = Agent(agent_id, name, avatar, personality, llm_interface=simulator.llm_interface)
        simulator.add_agent(agent)

        db.add_agent(
            agent_id, name,
            personality["openness"],
            personality["conscientiousness"],
            personality["extraversion"],
            personality["agreeableness"],
            personality["neuroticism"],
            avatar,
        )

        simulator.communication_hub.register_agent(agent_id)
        print(f"➕ Создан агент {name} ({agent_id})")
        return {"status": "ok", "agent": agent.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/agents/{agent_id}/inject")
async def inject_message(agent_id: str, data: dict = Body(...)):
    """Ввести сообщение конкретному агенту напрямую (отладка)."""
    if agent_id not in simulator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    content = data.get("content", "")
    msg = Message(
        sender_id="user",
        receiver_id=agent_id,
        content=content,
        topic=data.get("topic", "user_input"),
    )
    await simulator.communication_hub.send_message(msg)
    return {"status": "injected", "agent": agent_id, "content": content}


# ============================================================
# REST API — СОБЫТИЯ
# ============================================================

@app.get("/api/events")
async def get_events(limit: int = 50):
    """Лента событий из БД."""
    return {"events": db.get_recent_events(limit)}


@app.post("/api/events")
async def add_event(data: dict = Body(...)):
    """Ввести глобальное или таргетированное событие."""
    desc = data.get("event_description", "Global Event")
    target_agent = data.get("agent_id")

    targets = [target_agent] if (target_agent and target_agent in simulator.agents) \
        else list(simulator.agents.keys())

    simulator._log_event("world_event", f"Событие: {desc}", targets, {"description": desc})
    print(f"🌍 [REST] Событие «{desc}» → {len(targets)} агентов")
    return {"status": "ok", "event": desc, "notified_agents": targets}


# ============================================================
# REST API — СООБЩЕНИЯ
# ============================================================

@app.get("/api/messages")
async def get_messages(limit: int = 50, conversation_id: Optional[str] = None):
    """История сообщений — все или по диалогу."""
    if conversation_id:
        conv = simulator.communication_hub.get_conversation(conversation_id)
        if not conv:
            return {"messages": []}
        # DB-First: загружаем из БД через историю диалога
        messages = simulator.communication_hub.get_conversation_history(
            conv.participants[0],
            conv.participants[1] if len(conv.participants) > 1 else conv.participants[0],
            limit=limit,
        )
        return {"messages": [m.to_dict() for m in messages]}

    recent = simulator.communication_hub.get_recent_messages(limit)
    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "sender_name": simulator.agents[m.sender_id].name
                    if m.sender_id in simulator.agents else m.sender_id,
                "receiver_name": simulator.agents[m.receiver_id].name
                    if m.receiver_id in simulator.agents else m.receiver_id,
                "content": m.content,
                "message_type": m.message_type.value,
                "conversation_id": m.conversation_id,
                "topic": m.topic,
                "timestamp": m.timestamp,
            }
            for m in recent
        ]
    }


@app.post("/api/messages")
async def send_message(data: dict = Body(...)):
    """Отправить сообщение агенту от пользователя."""
    receiver_id = data.get("receiver_id", "")
    content = data.get("content", "")
    topic = data.get("topic", "external")

    if receiver_id not in simulator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not simulator.communication_hub.get_active_conversation("user", receiver_id):
        simulator.communication_hub.start_conversation("user", receiver_id, topic)

    msg = Message(
        sender_id=data.get("sender_id", "user"),
        receiver_id=receiver_id,
        content=content,
        topic=topic,
        requires_response=True,
    )
    await simulator.communication_hub.send_message(msg)
    simulator._log_event(
        "user_message",
        f"Пользователь → {receiver_id}: {content[:60]}",
        [receiver_id],
        {"content": content},
    )
    return {"status": "sent", "message_id": msg.id}


# ============================================================
# REST API — ДИАЛОГИ И ОТНОШЕНИЯ
# ============================================================

@app.get("/api/conversations")
async def get_conversations():
    """Все активные и завершённые диалоги."""
    all_convs = list(simulator.communication_hub.active_conversations.values())
    return {
        "conversations": [c.to_dict() for c in all_convs[-20:]],
        "active_count": len(simulator.communication_hub.get_all_active_conversations()),
    }


@app.get("/api/relationships")
async def get_relationships():
    """Граф отношений для D3/визуализации."""
    nodes = [
        {
            "id": aid,
            "name": agent.name,
            "avatar": agent.avatar,
            "emotions": agent.emotions.dict(),
        }
        for aid, agent in simulator.agents.items()
    ]
    edges = simulator.get_relationships_data()
    return {"nodes": nodes, "edges": edges}


# ============================================================
# REST API — УПРАВЛЕНИЕ
# ============================================================

@app.post("/api/control/speed")
async def set_speed(data: dict = Body(...)):
    simulator.time_speed = float(data.get("speed", 1.0))
    return {"status": "ok", "speed": simulator.time_speed}


@app.get("/api/state")
async def get_full_state():
    """Полное состояние для первоначальной загрузки фронтенда."""
    social = SocialEngine(db)
    recent = simulator.communication_hub.get_recent_messages(20)
    return jsonable_encoder({
        "agents": [a.to_dict() for a in simulator.agents.values()],
        "relationships": social.get_graph_data(),
        "recent_events": db.get_recent_events(30),
        "recent_messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "sender_name": simulator.agents[m.sender_id].name
                    if m.sender_id in simulator.agents else m.sender_id,
                "receiver_name": simulator.agents[m.receiver_id].name
                    if m.receiver_id in simulator.agents else m.receiver_id,
                "content": m.content,
                "message_type": m.message_type.value,
                "conversation_id": m.conversation_id,
                "topic": m.topic,
                "timestamp": m.timestamp,
            }
            for m in recent
        ],
        "active_conversations": [
            c.to_dict()
            for c in simulator.communication_hub.get_all_active_conversations()
        ],
        "time_speed": simulator.time_speed,
    })


# ============================================================
# SOCIAL ENGINE API
# ============================================================

@app.post("/api/social/event")
def process_social_event(
    event: SocialEventCreate,
    social: SocialEngine = Depends(get_social_engine),
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
            witnesses=event.witnesses,
        )
        social.process_social_event(social_event)
        rel = social.get_relationship(event.agent_from, event.agent_to)
        return {"status": "processed", "relationship": rel.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_type")


@app.get("/api/social/relationship/{agent_from}/{agent_to}")
def get_relationship(agent_from: str, agent_to: str, social: SocialEngine = Depends(get_social_engine)):
    rel = social.get_relationship(agent_from, agent_to)
    return rel.to_dict()


@app.get("/api/social/relationships/{agent_id}")
def get_all_relationships(agent_id: str, social: SocialEngine = Depends(get_social_engine)):
    relationships = social.get_all_relationships(agent_id)
    return {"agent_id": agent_id, "relationships": [rel.to_dict() for rel in relationships]}


@app.get("/api/social/context/{agent_id}/{target_id}")
def get_social_context(agent_id: str, target_id: str, social: SocialEngine = Depends(get_social_engine)):
    context = social.get_social_context_for_llm(agent_id, target_id)
    rel = social.get_relationship(agent_id, target_id)
    return {"context_text": context, "relationship": rel.to_dict()}


@app.get("/api/social/graph")
def get_social_graph(social: SocialEngine = Depends(get_social_engine)):
    return social.get_graph_data()


@app.post("/api/social/decay/{agent_id}")
def apply_decay(agent_id: str, days_passed: float = 1.0, social: SocialEngine = Depends(get_social_engine)):
    social.apply_relationship_decay(agent_id, days_passed)
    return {"status": "decay_applied"}


@app.get("/api/social/desire-multiplier/{agent_id}/{target_id}")
def get_desire_multiplier(agent_id: str, target_id: str, desire_type: str, social: SocialEngine = Depends(get_social_engine)):
    multiplier = social.get_desire_multiplier(agent_id, target_id, desire_type)
    return {"multiplier": multiplier}


@app.get("/api/social/credibility/{believer_id}/{source_id}")
def get_credibility(believer_id: str, source_id: str, social: SocialEngine = Depends(get_social_engine)):
    credibility = social.get_filtered_belief_credibility(believer_id, source_id)
    return {"credibility": credibility}


# ============================================================
# VECTOR MEMORY API
# ============================================================

@app.post("/api/memory/add")
def add_memory(memory_data: dict = Body(...), memory: VectorMemory = Depends(get_memory)):
    memory_id = memory.add_episodic_memory(**memory_data)
    return {"memory_id": memory_id}


@app.post("/api/memory/recall")
def recall_memories(recall_data: dict = Body(...), memory: VectorMemory = Depends(get_memory)):
    memories = memory.recall_relevant_memories(**recall_data)
    formatted = memory.format_memories_for_llm(memories)
    return {"memories": memories, "formatted_for_llm": formatted}


@app.post("/api/memory/summarize")
def summarize_memories(request: SummarizeRequest, memory: VectorMemory = Depends(get_memory)):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")
    result = memory.summarize_old_memories(
        agent_id=request.agent_id,
        older_than_days=request.older_than_days,
        openrouter_api_key=api_key,
        model=request.model,
        cluster_by=request.cluster_by,
    )
    return result


# ============================================================
# Статика
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
