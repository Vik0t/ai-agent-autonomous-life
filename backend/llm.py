import os
from typing import Dict, List, Any
from dotenv import load_dotenv
from openai import OpenAI

# Загружаем переменные окружения
load_dotenv()

class LLMInterface:
    def __init__(self):
        # Используем OPENROUTER_API_KEY из вашего .env
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            self.api_key = os.getenv("OPENROUTER_API_KEY")

        if not self.api_key:
            print("⚠️ WARNING: No API Key found in .env (expected OPENROUTER_API_KEY)")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                # OpenRouter требует эти заголовки для корректного отображения в их статистике (опционально)
                default_headers={
                    "HTTP-Referer": "http://localhost:8000", # Ваш URL
                    "X-Title": "Cyber Hackathon Simulator",
                }
            )

    def _format_personality(self, personality: Dict[str, float]) -> str:
        """Форматирование личности для промпта"""
        return f"""
        - Openness: {personality.get('openness', 0.5):.2f}
        - Conscientiousness: {personality.get('conscientiousness', 0.5):.2f}
        - Extraversion: {personality.get('extraversion', 0.5):.2f}
        - Agreeableness: {personality.get('agreeableness', 0.5):.2f}
        - Neuroticism: {personality.get('neuroticism', 0.5):.2f}
        """

    def generate_response(self, prompt: str, system_message: str = "") -> str:
        if not self.client:
            return f"[MOCK] No API Key. Response to: {prompt[:20]}..."

        try:
            # Важно: для OpenRouter нужно указывать модель с префиксом (например, openai/gpt-3.5-turbo)
            response = self.client.chat.completions.create(
                model="meta-llama/llama-4-maverick:free", # Или "google/gemini-flash-1.5" - они быстрые
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.8,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"🔴 OpenRouter Error: {e}")
            return "..."

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
        """
        Генерация реплики в диалоге с полным контекстом
        
        Args:
            agent_name: Имя агента
            personality: OCEAN traits
            context: Общий контекст ("Разговор о погоде")
            incoming_message: Входящее сообщение (если есть)
            conversation_history: История диалога (List[Message])
            message_type: Тип сообщения (greeting, question, answer, farewell)
        
        Returns:
            Сгенерированный текст сообщения
        """
        if not self.client:
            return self._mock_dialogue_response(agent_name, message_type, incoming_message)
        
        # Форматируем личность
        traits = self._format_personality(personality)
        
        # Создаём system prompt
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
        
        # Формируем историю диалога
        history_text = ""
        if conversation_history:
            history_text = "\n\nConversation history:\n"
            for msg in conversation_history[-5:]:  # Последние 5 сообщений
                sender = "You" if msg.sender_id == agent_name else "Other person"
                history_text += f"{sender}: {msg.content}\n"
        
        # Формируем prompt в зависимости от типа сообщения
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
            instruction = f"Continue the conversation naturally."
        
        # Собираем полный prompt
        user_prompt = f"""Context: {context}
    {history_text}

    {f"They just said: '{incoming_message}'" if incoming_message else ""}

    {instruction}

    Your response (in character, {agent_name}):"""
        
        try:
            print(f"User prompt for {agent_name} ({message_type}):\n{user_prompt}")
            response = self.client.chat.completions.create(
                model="openrouter/aurora-alpha",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,  # Короткие реплики
                temperature=0.8,  # Больше креативности
            )
            
            reply = response.choices[0].message.content.strip()
            
            # Удаляем лишнее форматирование если есть
            reply = reply.replace(f"{agent_name}:", "").strip()
            reply = reply.strip('"\'')  # Убираем кавычки
            
            return reply
        
        except Exception as e:
            print(f"🔴 LLM Error in generate_dialogue: {e}")
            return self._mock_dialogue_response(agent_name, message_type, incoming_message)


    def _mock_dialogue_response(self, agent_name: str, message_type: str, incoming_message: str = "") -> str:
        """
        Mock ответы для тестирования без API
        """
        import random
        
        if message_type == "greeting":
            greetings = [
                "Привет! Как дела?",
                "Здравствуй!",
                "Приветствую!",
                "Рад тебя видеть!",
                "О, привет!"
            ]
            return random.choice(greetings)
        
        elif message_type == "question":
            questions = [
                "Что думаешь об этом?",
                "Интересно, а как ты считаешь?",
                "Расскажи подробнее?",
                "А у тебя какие планы?",
                "Может обсудим это?"
            ]
            return random.choice(questions)
        
        elif message_type == "answer":
            if incoming_message:
                answers = [
                    f"Понимаю. Интересная мысль!",
                    f"Да, согласен с тобой.",
                    f"Хм, неплохая идея!",
                    f"Можно и так сказать.",
                    f"Это интересно, спасибо что поделился!"
                ]
                return random.choice(answers)
            return "Интересно!"
        
        elif message_type == "farewell":
            farewells = [
                "До встречи!",
                "Было приятно поговорить!",
                "Увидимся!",
                "Пока!",
                "До скорого!"
            ]
            return random.choice(farewells)
        
        else:
            return "Да, интересно. Что ещё скажешь?"


    # ========================================
    # ДОПОЛНИТЕЛЬНЫЙ МЕТОД: Генерация на основе эмоций
    # ========================================

    def generate_emotional_dialogue(
        self,
        agent_name: str,
        personality: Dict,
        emotions: Dict,  # {"happiness": 0.8, "surprise": 0.3, ...}
        context: str,
        message_type: str = "statement"
    ) -> str:
        """
        Генерация диалога с учётом текущих эмоций агента
        
        Эмоции влияют на тон и содержание сообщения
        """
        # Определяем доминирующую эмоцию
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
        
        # Вызываем обычный generate_dialogue с дополнительным контекстом
        enhanced_context = f"{context} (Emotional state: {emotion_context})"
        
        return self.generate_dialogue(
            agent_name=agent_name,
            personality=personality,
            context=enhanced_context,
            message_type=message_type
        )