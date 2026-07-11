"""Фабрика LLM — выбор провайдера через LLM_PROVIDER в .env."""
from backend.config import settings
from backend.llm.base import BaseLLM


def get_llm() -> BaseLLM:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        from backend.llm.ollama_llm import OllamaLLM
        return OllamaLLM()
    if provider == "gemini":
        from backend.llm.gemini_llm import GeminiLLM
        return GeminiLLM()
    if provider == "groq":
        from backend.llm.groq_llm import GroqLLM
        return GroqLLM()
    raise ValueError(f"Неизвестный LLM_PROVIDER: '{provider}'. Допустимо: ollama, gemini, groq")
