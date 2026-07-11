"""
Центральный конфиг проекта. Читает переменные из .env через pydantic-settings.
Все остальные модули импортируют settings отсюда — никаких os.getenv в коде.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Пути ---
    data_dir: Path = Path("data")
    chroma_dir: Path = Path("data/chroma")
    sqlite_path: Path = Path("data/db.sqlite")

    # --- Чанкинг ---
    chunk_gap_minutes: int = 15          # пауза между сообщениями → новый чанк
    chunk_max_chars: int = 2000          # максимум символов в чанке
    chunk_overlap_messages: int = 2      # сколько сообщений повторяется на границе

    # --- Эмбеддинги ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "auto"       # auto | cuda | mps | cpu
    embedding_batch_size: int = 64       # размер батча для model.encode()
    embedding_fp16: bool = True          # половинная точность (только на cuda)

    # --- LLM ---
    llm_provider: str = "ollama"         # ollama | gemini | groq

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # --- RAG ---
    rag_top_k: int = 5

    # --- Сервер ---
    host: str = "127.0.0.1"
    port: int = 8000

    # --- Аутентификация ---
    secret_key: str = "замените_на_случайную_строку_минимум_32_символа"

    def ensure_dirs(self) -> None:
        """Создаёт нужные директории, если их нет."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


# Глобальный экземпляр — импортировать его во всех модулях
settings = Settings()