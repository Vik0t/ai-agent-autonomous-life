# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import json
import random
import time
from datetime import datetime
from enum import Enum
import uuid

app = FastAPI(title="Cyber Hackathon - Virtual World Simulator")

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class Emotions(BaseModel):
    happiness: float = 0.5
    sadness: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0

class Personality(BaseModel):
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float

class Relationship(BaseModel):
    affinity: float  # -1 to 1 (негатив/позитив)
    familiarity: float  # 0 to 1 (знакомство)

class Memory(BaseModel):
    id: str
    timestamp: str
    content: str
    importance: float
    emotions: Dict[str, float]

class Agent(BaseModel):
    id: str
    name: str
    avatar: str
    personality: Personality
    emotions: Emotions
    relationships: Dict[str, Relationship] = {}
    memories: List[Memory] = []
    current_plan: str = "Ожидание"
    status: str = "active"
    last_action: str = ""
    location: str = "Центральная площадь"

class EventRequest(BaseModel):
    event_description: str
    target_agents: Optional[List[str]] = None

class MessageRequest(BaseModel):
    sender_id: str
    receiver_id: str
    content: str

class SpeedRequest(BaseModel):
    speed: float

# Хранилище
agents_db: Dict[str, Agent] = {}
events_history: List[dict] = []
time_speed = 1.0
active_connections: List[WebSocket] = []

# Имена и аватары для генерации
AGENT_NAMES = ['Алекса', 'Нексус', 'Кайрос', 'Зефир', 'Орион', 'Луна', 'Титан', 'Вега']
AGENT_AVATARS = ['🤖', '👾', '🦾', '👽', '🚀', '🌟', '⚡', '🔮']

# Инициализация агентов
def init_agents():
    personalities = [
        Personality(openness=0.8, conscientiousness=0.6, extraversion=0.9, agreeableness=0.7, neuroticism=0.3),
        Personality(openness=0.4, conscientiousness=0.9, extraversion=0.3, agreeableness=0.5, neuroticism=0.6),
        Personality(openness=0.9, conscientiousness=0.4, extraversion=0.7, agreeableness=0.8, neuroticism=0.2),
        Personality(openness=0.6, conscientiousness=0.7, extraversion=0.5, agreeableness=0.6, neuroticism=0.4),
        Personality(openness=0.7, conscientiousness=0.5, extraversion=0.8, agreeableness=0.4, neuroticism=0.5),
        Personality(openness=0.5, conscientiousness=0.8, extraversion=0.4, agreeableness=0.9, neuroticism=0.3),
        Personality(openness=0.8, conscientiousness=0.3, extraversion=0.6, agreeableness=0.5, neuroticism=0.7),
        Personality(openness=0.3, conscientiousness=0.9, extraversion=0.2, agreeableness=0.7, neuroticism=0.4)
    ]
    
    for i, (name, avatar) in enumerate(zip(AGENT_NAMES, AGENT_AVATARS)):
        agent_id = f"agent-{i}"
        
        # Генерация начальных воспоминаний
        memories = [
            Memory(
                id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat(),
                content=f"Активация в системе. Назначено имя {name}",
                importance=0.9,
                emotions={"happiness": 0.6, "surprise": 0.4}
            ),
            Memory(
                id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat(),
                content="Первое знакомство с окружением",
                importance=0.7,
                emotions={"curiosity": 0.8, "fear": 0.2}
            )
        ]
        
        agents_db[agent_id] = Agent(
            id=agent_id,
            name=name,
            avatar=avatar,
            personality=personalities[i],
            emotions=Emotions(
                happiness=random.uniform(0.3, 0.8),
                sadness=random.uniform(0, 0.3),
                anger=random.uniform(0, 0.2),
                fear=random.uniform(0, 0.4),
                surprise=random.uniform(0, 0.5),
                disgust=random.uniform(0, 0.1)
            ),
            memories=memories,
            current_plan=random.choice([
                "Анализ данных окружения",
                "Поиск других агентов",
                "Формирование стратегии",
                "Изучение доступных ресурсов"
            ])
        )

init_agents()

# Установка начальных отношений
def init_relationships():
    agent_ids = list(agents_db.keys())
    for i, agent_id in enumerate(agent_ids):
        for j, other_id in enumerate(agent_ids):
            if i != j:
                affinity = random.uniform(-0.5, 0.8)
                agents_db[agent_id].relationships[other_id] = Relationship(
                    affinity=affinity,
                    familiarity=random.uniform(0, 0.5)
                )

init_relationships()

# WebSocket менеджер
class ConnectionManager:
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in active_connections:
            active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# WebSocket для real-time обновлений
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Отправка начального состояния
        await websocket.send_json({
            "type": "init",
            "agents": [agent.dict() for agent in agents_db.values()],
            "time_speed": time_speed
        })
        
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Обработка команд от клиента
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API Endpoints

@app.get("/api")
async def root():
    return {"message": "Cyber Hackathon API", "agents_count": len(agents_db)}

# Статические файлы (фронтенд) - должен быть последним
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.get("/agents")
async def get_agents():
    return {"agents": [agent.dict() for agent in agents_db.values()]}

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    if agent_id not in agents_db:
        return {"error": "Agent not found"}
    return agents_db[agent_id]

@app.post("/events")
async def create_event(request: EventRequest):
    event_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    event_data = {
        "id": event_id,
        "type": "global_event",
        "description": request.event_description,
        "timestamp": timestamp,
        "affected_agents": request.target_agents or list(agents_db.keys())
    }
    
    events_history.append(event_data)
    
    # Влияние на эмоции агентов
    for agent_id in event_data["affected_agents"]:
        if agent_id in agents_db:
            agent = agents_db[agent_id]
            # Простая модель эмоциональной реакции
            if "клад" in request.event_description.lower() or "праздник" in request.event_description.lower():
                agent.emotions.happiness = min(1.0, agent.emotions.happiness + 0.3)
                agent.emotions.surprise = min(1.0, agent.emotions.surprise + 0.4)
            elif "буря" in request.event_description.lower() or "опасность" in request.event_description.lower():
                agent.emotions.fear = min(1.0, agent.emotions.fear + 0.4)
                agent.emotions.happiness = max(0, agent.emotions.happiness - 0.2)
            
            # Добавление воспоминания
            agent.memories.insert(0, Memory(
                id=str(uuid.uuid4()),
                timestamp=timestamp,
                content=f"Событие: {request.event_description}",
                importance=0.8,
                emotions=agent.emotions.dict()
            ))
            
            # Ограничение памяти (суммаризация при переполнении)
            if len(agent.memories) > 20:
                # Удаляем старые маловажные воспоминания
                agent.memories = sorted(agent.memories, key=lambda x: x.importance, reverse=True)[:15]
    
    # Отправка через WebSocket
    await manager.broadcast({
        "type": "event",
        "data": event_data
    })
    
    return {"status": "success", "event": event_data}

@app.post("/messages")
async def send_message(request: MessageRequest):
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    message_data = {
        "id": msg_id,
        "type": "message",
        "sender_id": request.sender_id,
        "receiver_id": request.receiver_id,
        "content": request.content,
        "timestamp": timestamp
    }
    
    # Обработка получением
    if request.receiver_id in agents_db and request.receiver_id != "user":
        receiver = agents_db[request.receiver_id]
        
        # Эмоциональная реакция на сообщение
        if request.sender_id == "user":
            receiver.emotions.happiness = min(1.0, receiver.emotions.happiness + 0.1)
        
        # Обновление отношений
        if request.sender_id in receiver.relationships:
            rel = receiver.relationships[request.sender_id]
            rel.familiarity = min(1.0, rel.familiarity + 0.05)
            # Простой анализ тональности
            if any(word in request.content.lower() for word in ["спасибо", "отлично", "хорошо", "друг"]):
                rel.affinity = min(1.0, rel.affinity + 0.1)
            elif any(word in request.content.lower() for word in ["плохо", "ненавижу", "враг", "уйди"]):
                rel.affinity = max(-1.0, rel.affinity - 0.1)
        
        # Добавление в память
        receiver.memories.insert(0, Memory(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            content=f"Сообщение от {request.sender_id}: {request.content[:50]}...",
            importance=0.7,
            emotions=receiver.emotions.dict()
        ))
        
        # Генерация ответа (простая эмуляция)
        asyncio.create_task(generate_response(request.receiver_id, request.sender_id, request.content))
    
    await manager.broadcast({
        "type": "message",
        "data": message_data
    })
    
    return {"status": "success", "message": message_data}

async def generate_response(agent_id: str, to_id: str, original_msg: str):
    """Эмуляция генерации ответа агентом"""
    await asyncio.sleep(random.uniform(2, 5) / time_speed)
    
    agent = agents_db[agent_id]
    
    # Простая генерация ответа на основе личности
    responses = [
        "Интересная мысль. Давай обсудим подробнее.",
        "Я согласен с твоей точкой зрения.",
        "Не уверен, что это правильный подход.",
        "Это напоминает мне прошлое событие...",
        "Давайте работать вместе над этим!",
        "Мне нужно время обдумать это.",
        "Звучит интригующе! Расскажи больше."
    ]
    
    # Выбор на осново экстраверсии
    if agent.personality.extraversion > 0.6:
        response = random.choice([r for r in responses if "!" in r or "Давай" in r])
    else:
        response = random.choice([r for r in responses if "..." in r or "не уверен" in r])
    
    # Отправка ответа
    msg_id = str(uuid.uuid4())
    await manager.broadcast({
        "type": "message",
        "data": {
            "id": msg_id,
            "sender_id": agent_id,
            "receiver_id": to_id,
            "content": response,
            "timestamp": datetime.now().isoformat(),
            "is_response": True
        }
    })

@app.post("/control/speed")
async def set_speed(request: SpeedRequest):
    global time_speed
    time_speed = max(0.1, min(5.0, request.speed))
    return {"status": "success", "speed": time_speed}

@app.get("/events/history")
async def get_events_history(limit: int = 50):
    return {"events": events_history[-limit:]}


# Фоновая симуляция жизни агентов
async def life_simulation():
    """Симуляция автономной жизни агентов"""
    while True:
        await asyncio.sleep(5 / time_speed)
        
        for agent in agents_db.values():
            # Случайные изменения эмоций (затухание)
            agent.emotions.happiness = max(0, agent.emotions.happiness - 0.01)
            agent.emotions.anger = max(0, agent.emotions.anger - 0.02)
            agent.emotions.fear = max(0, agent.emotions.fear - 0.01)
            
            # Случайные действия на основе личности
            if random.random() < (0.1 * agent.personality.extraversion):
                action = random.choice([
                    "исследует окрестности",
                    "анализирует данные",
                    "размышляет о целях",
                    "ищет других агентов",
                    "обновляет свои планы"
                ])
                agent.current_plan = action.capitalize()
                
                # Рассылка события
                await manager.broadcast({
                    "type": "agent_action",
                    "data": {
                        "agent_id": agent.id,
                        "action": action,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            # Случайные взаимодействия между агентами
            if random.random() < 0.05 and agent.personality.extraversion > 0.5:
                other_id = random.choice([k for k in agents_db.keys() if k != agent.id])
                if other_id:
                    # Обновление знакомства
                    if other_id in agent.relationships:
                        agent.relationships[other_id].familiarity = min(
                            1.0, 
                            agent.relationships[other_id].familiarity + 0.02
                        )
        
        # Периодическая рассылка обновлений состояния
        await manager.broadcast({
            "type": "state_update",
            "agents": [agent.dict() for agent in agents_db.values()]
        })

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(life_simulation())

# Статические файлы (фронтенд)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)