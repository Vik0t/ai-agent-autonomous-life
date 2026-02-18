import os
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from groq import Groq

# Загружаем переменные окружения
load_dotenv()


class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")

        if not self.api_key:
            print("⚠️ WARNING: No API Key found in .env (expected GROQ_API_KEY)")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)

        # Модель по умолчанию — быстрая модель Groq
        self._model = "llama-3.3-70b-versatile"

    # ──────────────────────────────────────────────────────────────────
    # Утилиты форматирования
    # ──────────────────────────────────────────────────────────────────

    def _format_personality(self, personality: Dict[str, float]) -> str:
        return (
            f"  - Openness: {personality.get('openness', 0.5):.2f}\n"
            f"  - Conscientiousness: {personality.get('conscientiousness', 0.5):.2f}\n"
            f"  - Extraversion: {personality.get('extraversion', 0.5):.2f}\n"
            f"  - Agreeableness: {personality.get('agreeableness', 0.5):.2f}\n"
            f"  - Neuroticism: {personality.get('neuroticism', 0.5):.2f}"
        )

    def _call_llm(self, system_msg: str, user_prompt: str,
                  max_tokens: int = 200, temperature: float = 0.8) -> Optional[str]:
        """Базовый вызов LLM с обработкой ошибок. Возвращает None при сбое."""
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"🔴 LLM Error: {e}")
            return None

    def _safe_parse_json(self, text: str) -> Optional[Any]:
        """Безопасный парсинг JSON — удаляет markdown-обёртки."""
        if not text:
            return None
        clean = text.replace("```json", "").replace("```", "").strip()
        start = clean.find('[')
        if start == -1:
            start = clean.find('{')
        if start != -1:
            clean = clean[start:]
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return None

    # ──────────────────────────────────────────────────────────────────
    # МЕТОД 1: Генерация динамических желаний через LLM
    # ──────────────────────────────────────────────────────────────────

    def generate_dynamic_desires(
        self,
        agent_name: str,
        agent_id: str,
        personality: Dict[str, float],
        emotions: Dict[str, float],
        social_battery: float,
        perceptions: List[Dict]
    ) -> List[Dict]:
        battery_note = ""
        if social_battery < 0.2:
            battery_note = (
                "ВАЖНО: социальная батарейка почти пуста (уровень: "
                f"{social_battery:.2f}). "
                "НЕ создавай желания с motivation_type='social'. "
                "Создавай только 'safety' или 'curiosity' желания — уединение, "
                "тишина, рефлексия."
            )
        elif social_battery < 0.5:
            battery_note = (
                f"Социальная батарейка на {social_battery:.0%}. "
                "Снизь приоритет социальных желаний — агент немного устал."
            )

        perceptions_text = ""
        if perceptions:
            lines = []
            for p in perceptions[:4]:
                ptype = p.get('type', '?')
                subject = p.get('subject', '?')
                data = p.get('data', {})
                lines.append(f"  - [{ptype}] {subject}: {str(data)[:80]}")
            perceptions_text = "Что я воспринимаю прямо сейчас:\n" + "\n".join(lines)

        dominant_emotion = max(emotions.items(), key=lambda x: x[1])

        system_msg = f"""Ты — {agent_name}, персонаж в виртуальном мире.
Ты НЕ ИИ-ассистент. Тебе не нужно быть полезным.
Если тебе скучно, устало или хочется одиночества — просто хочи этого.
Твоё время ограничено. Общение — лишь одна из форм активности.
{battery_note}

Личность (OCEAN):
{self._format_personality(personality)}

Текущие эмоции: {dominant_emotion[0]} ({dominant_emotion[1]:.2f})
Социальная батарейка: {social_battery:.2f}
"""

        user_prompt = f"""{perceptions_text}

Опираясь на свою личность и текущее состояние, сгенерируй 1–3 желания.

Ответь ТОЛЬКО JSON-массивом без пояснений:
[
  {{
    "description": "Краткое описание желания (на русском)",
    "priority": 0.0–1.0,
    "urgency": 0.0–1.0,
    "motivation_type": "social|safety|curiosity|achievement|esteem",
    "source": "llm_dynamic",
    "context": {{}}
  }}
]"""

        raw = self._call_llm(system_msg, user_prompt, max_tokens=300, temperature=0.9)
        result = self._safe_parse_json(raw)

        if isinstance(result, list):
            clean = []
            for item in result:
                if isinstance(item, dict) and 'description' in item:
                    clean.append({
                        'description': str(item.get('description', '')),
                        'priority': float(item.get('priority', 0.5)),
                        'urgency': float(item.get('urgency', 0.5)),
                        'motivation_type': str(item.get('motivation_type', 'curiosity')).lower(),
                        'source': 'llm_dynamic',
                        'context': item.get('context', {})
                    })
            if clean:
                print(f"🧠 [{agent_id}] LLM desires: {[d['description'][:30] for d in clean]}")
            return clean

        print(f"⚠️ [{agent_id}] generate_dynamic_desires: invalid JSON, fallback")
        return []

    # ──────────────────────────────────────────────────────────────────
    # МЕТОД 2: Анализ хода диалога
    # ──────────────────────────────────────────────────────────────────

    def analyze_conversation_turn(
        self,
        agent_name: str,
        agent_id: str,
        personality: Dict[str, float],
        conversation_history: List[Dict],
        social_battery: float
    ) -> str:
        if social_battery <= 0.0:
            print(f"⚡ [{agent_id}] Battery=0, FORCE_QUIT")
            return "FORCE_QUIT"

        if social_battery < 0.1:
            return "WRAP_UP"

        history_lines = []
        for msg in (conversation_history or [])[-8:]:
            sender = msg.get('sender_name', msg.get('sender_id', '?'))
            content = msg.get('content', '')[:100]
            history_lines.append(f"  {sender}: {content}")
        history_text = "\n".join(history_lines) if history_lines else "  (диалог только начался)"

        turn_count = len(conversation_history or [])

        system_msg = f"""Ты — {agent_name}, персонаж в виртуальном мире.
Ты НЕ ИИ-ассистент. Тебе не нужно поддерживать разговор ради вежливости.
Твоё время ограничено. Общение — лишь одна из форм активности.
Если цель достигнута (ты узнал что хотел или просто поздоровался) — заканчивай.
Не жди, пока собеседник попрощается. Прощайся первым, если устал.

Личность:
{self._format_personality(personality)}
Социальная батарейка: {social_battery:.2f} (0=пуста, 1=полная)
Реплик в диалоге: {turn_count}
"""

        user_prompt = f"""История диалога:
{history_text}

Оцени: нужно ли продолжать разговор?

Ответь ТОЛЬКО одним словом из трёх:
CONTINUE — если разговор ещё интересен и батарейка позволяет
WRAP_UP  — если пора начать прощаться (устал, цель достигнута, скучно)
FORCE_QUIT — если нужно резко прервать (батарейка пуста, обиделся, срочное дело)"""

        raw = self._call_llm(system_msg, user_prompt, max_tokens=10, temperature=0.3)
        if not raw:
            return "CONTINUE"

        upper = raw.strip().upper()
        for token in ["FORCE_QUIT", "WRAP_UP", "CONTINUE"]:
            if token in upper:
                print(f"🗣️ [{agent_id}] Conversation analysis: {token} (battery={social_battery:.2f})")
                return token

        return "CONTINUE"

    # ──────────────────────────────────────────────────────────────────
    # МЕТОД 3: Генерация следующего шага плана
    # ──────────────────────────────────────────────────────────────────

    def generate_next_plan_step(
        self,
        agent_name: str,
        agent_id: str,
        personality: Dict[str, float],
        current_desire_description: str,
        conversation_history: List[Dict],
        social_battery: float
    ) -> List[str]:
        VALID_ACTIONS = {
            "send_message", "wait_for_response", "end_conversation",
            "initiate_conversation", "respond_to_message", "think"
        }

        history_lines = []
        for msg in (conversation_history or [])[-6:]:
            sender = msg.get('sender_name', msg.get('sender_id', '?'))
            content = msg.get('content', '')[:80]
            history_lines.append(f"  {sender}: {content}")
        history_text = "\n".join(history_lines) if history_lines else "  (начало диалога)"

        system_msg = f"""Ты — {agent_name}, персонаж в виртуальном мире.
Планируй следующий шаг в диалоге коротко и реалистично.
Социальная батарейка: {social_battery:.2f}
Текущая цель: {current_desire_description}

Личность:
{self._format_personality(personality)}
"""

        user_prompt = f"""История диалога:
{history_text}

Предложи 1–2 следующих шага из этого списка:
  send_message        — отправить сообщение
  wait_for_response   — подождать ответа
  end_conversation    — завершить разговор
  respond_to_message  — ответить на сообщение
  think               — задуматься (пауза)

Ответь ТОЛЬКО JSON-массивом строк, например: ["send_message", "wait_for_response"]
Не более 2 шагов. Если батарейка низкая — заканчивай разговор."""

        raw = self._call_llm(system_msg, user_prompt, max_tokens=50, temperature=0.5)
        result = self._safe_parse_json(raw)

        if isinstance(result, list):
            steps = [str(s).lower() for s in result if str(s).lower() in VALID_ACTIONS]
            if steps:
                print(f"📋 [{agent_id}] Next plan steps: {steps}")
                return steps[:2]

        print(f"⚠️ [{agent_id}] generate_next_plan_step: fallback → think")
        return ["think"]

    # ──────────────────────────────────────────────────────────────────
    # Существующие методы
    # ──────────────────────────────────────────────────────────────────

    def generate_response(self, prompt: str, system_message: str = "") -> str:
        if not self.client:
            return f"[MOCK] No API Key. Response to: {prompt[:20]}..."
        raw = self._call_llm(system_message, prompt, max_tokens=150)
        return raw if raw else "..."

    def generate_plan(self, agent_name: str, personality: Dict, beliefs: str, desires: str) -> str:
        traits = self._format_personality(personality)
        system_msg = f"You are {agent_name}, a character in a virtual world. Act according to your traits."
        prompt = f"""
PERSONALITY:
{traits}
BELIEFS:
{beliefs}
DESIRES:
{desires}
TASK:
Describe your next action in 1 short sentence. Start with 'I will'.
"""
        return self.generate_response(prompt, system_msg)

    def generate_dialogue(
        self,
        agent_name: str,
        personality: Dict,
        context: str,
        incoming_message: str = "",
        conversation_history: List = None,
        message_type: str = "statement"
    ) -> str:
        if not self.client:
            return self._mock_dialogue_response(agent_name, message_type, incoming_message)

        traits = self._format_personality(personality)
        system_msg = f"""You are {agent_name}, a character in a virtual world.

Your personality traits:
{traits}

Important guidelines:
- Stay in character based on your personality
- Keep responses natural and conversational (1-3 sentences)
- Be consistent with previous messages
- Show emotions appropriate to your personality
- Don't break the fourth wall

Message type: {message_type}
"""
        history_text = ""
        if conversation_history:
            history_text = "\n\nConversation history:\n"
            for msg in conversation_history[-5:]:
                sender = "You" if msg.sender_id == agent_name else "Other person"
                history_text += f"{sender}: {msg.content}\n"

        if message_type == "greeting":
            instruction = "Start the conversation with a friendly greeting."
        elif message_type == "question":
            instruction = f"Ask a question about: {context}"
        elif message_type == "answer":
            instruction = f"Respond to: '{incoming_message}'\nBe helpful and relevant."
        elif message_type == "statement":
            instruction = f"Make a statement or share thoughts about: {context}"
        elif message_type == "farewell":
            instruction = "Say goodbye in a friendly way."
        else:
            instruction = "Continue the conversation naturally."

        user_prompt = f"""Context: {context}
{history_text}

{f"They just said: '{incoming_message}'" if incoming_message else ""}

{instruction}

Your response (in character, {agent_name}):"""

        try:
            print(f"User prompt for {agent_name} ({message_type}):\n{user_prompt}")
            response = self.client.chat.completions.create(
                model=self._model,  # ← используем self._model вместо захардкоженной строки
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=250,
                temperature=0.8,
            )
            reply = response.choices[0].message.content.strip()
            reply = reply.replace(f"{agent_name}:", "").strip()
            reply = reply.strip('"\'')
            return reply
        except Exception as e:
            print(f"🔴 LLM Error in generate_dialogue: {e}")
            return self._mock_dialogue_response(agent_name, message_type, incoming_message)

    def _mock_dialogue_response(self, agent_name: str, message_type: str,
                                 incoming_message: str = "") -> str:
        import random
        if message_type == "greeting":
            return random.choice(["Привет! Как дела?", "Здравствуй!", "Приветствую!", "О, привет!"])
        elif message_type == "question":
            return random.choice(["Что думаешь об этом?", "А как ты считаешь?", "Расскажи подробнее?"])
        elif message_type == "answer":
            return random.choice(["Понимаю. Интересная мысль!", "Да, согласен.", "Хм, неплохая идея!"])
        elif message_type == "farewell":
            return random.choice(["До встречи!", "Было приятно!", "Увидимся!", "Пока!"])
        else:
            return "Да, интересно. Что ещё скажешь?"

    def generate_emotional_dialogue(
        self,
        agent_name: str,
        personality: Dict,
        emotions: Dict,
        context: str,
        message_type: str = "statement"
    ) -> str:
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
        emotion_name, emotion_value = dominant_emotion
        if emotion_value < 0.3:
            emotion_context = "You're feeling calm and neutral."
        else:
            emotion_map = {
                "happiness": "You're feeling happy and cheerful.",
                "sadness": "You're feeling a bit down.",
                "anger": "You're feeling frustrated.",
                "fear": "You're feeling anxious or worried.",
                "surprise": "You're feeling surprised and curious.",
                "disgust": "You're feeling uncomfortable."
            }
            emotion_context = emotion_map.get(emotion_name, "You're feeling neutral.")
        enhanced_context = f"{context} (Emotional state: {emotion_context})"
        return self.generate_dialogue(
            agent_name=agent_name,
            personality=personality,
            context=enhanced_context,
            message_type=message_type
        )
