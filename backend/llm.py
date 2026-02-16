import openai
import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LLMInterface:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
            
    def generate_response(self, prompt: str, system_message: str = "") -> str:
        """
        Generate a response using OpenAI GPT
        """
        if not self.api_key:
            # Return a mock response if no API key is available
            return f"Mock response to: {prompt}"
            
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"
            
    def generate_plan(self, agent_personality: Dict, current_situation: str) -> str:
        """
        Generate a plan for an agent based on their personality and current situation
        """
        prompt = f"""
        You are an AI agent with the following personality traits:
        - Openness: {agent_personality['openness']}
        - Conscientiousness: {agent_personality['conscientiousness']}
        - Extraversion: {agent_personality['extraversion']}
        - Agreeableness: {agent_personality['agreeableness']}
        - Neuroticism: {agent_personality['neuroticism']}
        
        Current situation: {current_situation}
        
        Generate a short plan of action for this agent.
        """
        
        return self.generate_response(prompt, "You are an AI agent planner.")
        
    def generate_dialogue(self, agent_personality: Dict, context: str, other_agent_message: str = "") -> str:
        """
        Generate dialogue for an agent based on their personality and context
        """
        prompt = f"""
        You are an AI agent with the following personality traits:
        - Openness: {agent_personality['openness']}
        - Conscientiousness: {agent_personality['conscientiousness']}
        - Extraversion: {agent_personality['extraversion']}
        - Agreeableness: {agent_personality['agreeableness']}
        - Neuroticism: {agent_personality['neuroticism']}
        
        Context: {context}
        {f"Other agent says: {other_agent_message}" if other_agent_message else ""}
        
        Generate a short response in the style of this agent.
        """
        
        return self.generate_response(prompt, "You are an AI agent in a conversation.")