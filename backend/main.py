# backend/main.py  [FIXED]
"""
Исправления:
1. Агенты имеют РАЗНЫЕ личности (не зеркалят друг друга)
2. Новые API эндпоинты для фронтенда:
   - GET  /api/events          — лента событий
   - GET  /api/conversations   — все диалоги
   - GET  /api/relationships   — граф отношений
   - GET  /api/agents/{id}     — детальный профиль агента
   - POST /api/agents/{id}/inject — ввести событие для конкретного агента
"""

import os
import sys
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from typing import Optional

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
    # ================================================================
    # FIX: Агенты с РАЗНЫМИ личностями чтобы вести себя по-разному
    # ================================================================
    configs = [
        (
            "agent-0", "Алекса", "🤖",
            {
                # Экстраверт, открытый, дружелюбный
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
                # Более интровертный, аналитичный, осторожный
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

    # Регистрируем "user" как виртуального участника — агенты смогут с ним говорить
    simulator.communication_hub.register_agent("user")

    asyncio.create_task(simulator.run_simulation())
    asyncio.create_task(broadcast_state())
    yield
    simulator.running = False


app = FastAPI(title="Cyber BDI Simulator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ================================================================
# WebSocket — стриминг состояния
# ================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        relationships = simulator.get_relationships_data()
        init_data = jsonable_encoder({
            "type": "init",
            "agents": [agent.to_dict() for agent in simulator.agents.values()],
            "time_speed": simulator.time_speed,
            "relationships": relationships
        })
        await websocket.send_json(init_data)
        while True:
            data = await websocket.receive_json()
            if data.get('type') == 'send_message':
                receiver_id = data.get('receiver_id', '')
                content = data.get('content', '')
                topic = data.get('topic', 'user_input')
                # Открываем диалог user ↔ agent ПЕРЕД отправкой сообщения,
                # чтобы агент увидел "user" в active_partners и создал respond_desire
                if receiver_id in simulator.agents:
                    if not simulator.communication_hub.get_active_conversation("user", receiver_id):
                        simulator.communication_hub.start_conversation("user", receiver_id, topic)
                msg = Message(
                    sender_id="user",
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
                    {"content": content}
                )
            elif data.get('type') == 'add_event':
                event_desc = data.get('event_description', 'Global Event')
                agent_ids = list(simulator.agents.keys())
                # Инжектируем напрямую в event_log с типом world_event —
                # НЕ через Message-канал, чтобы perception был строго world_event
                simulator._log_event(
                    "world_event",
                    f"Событие: {event_desc}",
                    agent_ids,
                    {"description": event_desc}
                )
                print(f"🌍 Событие «{event_desc}» добавлено в event_log для {len(agent_ids)} агентов")
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ================================================================
# REST API
# ================================================================

@app.get("/api/agents")
async def get_agents():
    return {"agents": [a.to_dict() for a in simulator.agents.values()]}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Детальный профиль агента для инспектора."""
    agent = simulator.agents.get(agent_id)
    if not agent:
        return {"error": "Agent not found"}, 404

    # Собираем историю воспоминаний
    all_beliefs = [b.to_dict() for b in agent.beliefs.beliefs.values()]

    # Активные намерения
    intentions = [i.to_dict() for i in agent.intentions]
    desires = [d.to_dict() for d in agent.desires]

    # Отношения этого агента
    agent_relationships = []
    for (a, b), strength in simulator.relationships.items():
        if agent_id in (a, b):
            other_id = b if a == agent_id else a
            other = simulator.agents.get(other_id)
            agent_relationships.append({
                "agent_id": other_id,
                "agent_name": other.name if other else other_id,
                "strength": round(strength, 3),
                "type": "friend" if strength > 0.3 else ("enemy" if strength < -0.3 else "neutral")
            })

    profile = agent.to_dict()
    profile.update({
        "beliefs": all_beliefs[:50],  # топ 50 убеждений
        "intentions": intentions,
        "desires": desires[:10],
        "relationships": agent_relationships
    })
    return profile


@app.get("/api/events")
async def get_events(limit: int = 50):
    """Лента событий для дашборда."""
    return {"events": simulator.get_recent_events(limit)}


@app.get("/api/conversations")
async def get_conversations():
    """Все активные и завершённые диалоги."""
    all_convs = list(simulator.communication_hub.conversations.values())
    return {
        "conversations": [c.to_dict() for c in all_convs[-20:]],
        "active_count": len(simulator.communication_hub.get_all_active_conversations())
    }


@app.get("/api/messages")
async def get_messages(limit: int = 50, conversation_id: Optional[str] = None):
    """История сообщений (все или по диалогу)."""
    if conversation_id:
        conv = simulator.communication_hub.get_conversation(conversation_id)
        if not conv:
            return {"messages": []}
        return {"messages": [m.to_dict() for m in conv.messages]}

    recent = simulator.communication_hub.get_recent_messages(limit)
    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "sender_name": simulator.agents[m.sender_id].name if m.sender_id in simulator.agents else m.sender_id,
                "receiver_name": simulator.agents[m.receiver_id].name if m.receiver_id in simulator.agents else m.receiver_id,
                "content": m.content,
                "message_type": m.message_type.value,
                "conversation_id": m.conversation_id,
                "topic": m.topic,
                "timestamp": m.timestamp
            }
            for m in recent
        ]
    }


@app.get("/api/relationships")
async def get_relationships():
    """Граф отношений для D3/визуализации."""
    nodes = [
        {
            "id": aid,
            "name": agent.name,
            "avatar": agent.avatar,
            "emotions": agent.emotions.dict()
        }
        for aid, agent in simulator.agents.items()
    ]
    edges = simulator.get_relationships_data()
    return {"nodes": nodes, "edges": edges}


@app.post("/api/messages")
async def send_message(data: dict = Body(...)):
    """Отправить сообщение конкретному агенту (от пользователя)."""
    receiver_id = data.get('receiver_id', '')
    content = data.get('content', '')
    topic = data.get('topic', 'external')
    # Открываем диалог ПЕРЕД отправкой — иначе агент не увидит "user" в active_partners
    if receiver_id in simulator.agents:
        if not simulator.communication_hub.get_active_conversation("user", receiver_id):
            simulator.communication_hub.start_conversation("user", receiver_id, topic)
    msg = Message(
        sender_id=data.get('sender_id', 'user'),
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
        {"content": content}
    )
    return {"status": "sent", "message_id": msg.id}


@app.post("/api/events")
async def add_event(data: dict = Body(...)):
    """Ввести глобальное событие (меняет желания агентов)."""
    desc = data.get("event_description", "Global Event")
    target_agent = data.get("agent_id")

    if target_agent and target_agent in simulator.agents:
        targets = [target_agent]
    else:
        targets = list(simulator.agents.keys())

    # Инжектируем напрямую в event_log — строгий тип world_event
    # НЕ через Message-канал (чтобы агент получил perception типа world_event, не communication)
    simulator._log_event("world_event", f"Событие: {desc}", targets, {"description": desc})
    print(f"🌍 [REST] Событие «{desc}» → {len(targets)} агентов")
    return {"status": "ok", "event": desc, "notified_agents": targets}


@app.post("/api/agents/{agent_id}/inject")
async def inject_message(agent_id: str, data: dict = Body(...)):
    """Ввести сообщение конкретному агенту напрямую (для отладки/управления)."""
    if agent_id not in simulator.agents:
        return {"error": "Agent not found"}

    content = data.get("content", "")
    msg = Message(
        sender_id="user",
        receiver_id=agent_id,
        content=content,
        topic=data.get("topic", "user_input")
    )
    await simulator.communication_hub.send_message(msg)
    return {"status": "injected", "agent": agent_id, "content": content}


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
async def get_full_state():
    """Полное состояние для первоначальной загрузки фронтенда."""
    return jsonable_encoder({
        "agents": [a.to_dict() for a in simulator.agents.values()],
        "relationships": simulator.get_relationships_data(),
        "recent_events": simulator.get_recent_events(30),
        "recent_messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "sender_name": simulator.agents[m.sender_id].name if m.sender_id in simulator.agents else m.sender_id,
                "receiver_name": simulator.agents[m.receiver_id].name if m.receiver_id in simulator.agents else m.receiver_id,
                "content": m.content,
                "message_type": m.message_type.value,
                "conversation_id": m.conversation_id,
                "topic": m.topic,
                "timestamp": m.timestamp
            }
            for m in simulator.communication_hub.get_recent_messages(20)
        ],
        "active_conversations": [
            c.to_dict()
            for c in simulator.communication_hub.get_all_active_conversations()
        ],
        "time_speed": simulator.time_speed
    })


# Статика
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)