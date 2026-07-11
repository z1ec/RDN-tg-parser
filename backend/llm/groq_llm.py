"""LLM через Groq API (бесплатный тир, OpenAI-совместимый)."""
import httpx
from backend.config import settings
from backend.llm.base import BaseLLM

_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLM(BaseLLM):
    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = httpx.post(
            _URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={"model": settings.groq_model, "messages": messages},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
