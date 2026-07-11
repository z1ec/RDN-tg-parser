"""Базовый класс для всех LLM-провайдеров."""
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Отправляет промпт, возвращает текст ответа."""
        ...
