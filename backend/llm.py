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
            # Проверка на случай, если ключ все еще лежит в OPENAI_API_KEY
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            print("⚠️ WARNING: No API Key found in .env (expected OPENROUTER_API_KEY)")
            self.client = None
        else:
            # Настройка клиента OpenAI для работы через OpenRouter
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
                model="openai/gpt-3.5-turbo", # Или "google/gemini-flash-1.5" - они быстрые
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

    def generate_dialogue(self, agent_name: str, personality: Dict, context: str, incoming_message: str = "") -> str:
        traits = self._format_personality(personality)
        system_msg = f"You are {agent_name}. Personality: {traits}. Keep it short and conversational."
        
        prompt = f"""
        CONTEXT:
        {context}
        
        {f"THEY SAID: '{incoming_message}'" if incoming_message else "Start a conversation."}

        Respond in character (max 2 sentences):
        """
        return self.generate_response(prompt, system_msg)