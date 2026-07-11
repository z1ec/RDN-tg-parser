"""LLM через Google Gemini API (бесплатный тир)."""
import httpx
from backend.config import settings
from backend.llm.base import BaseLLM

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLM(BaseLLM):
    def complete(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = httpx.post(
            f"{_BASE}/{settings.gemini_model}:generateContent",
            params={"key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": full_prompt}]}]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
