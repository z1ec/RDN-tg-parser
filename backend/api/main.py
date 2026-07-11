"""
Главный файл FastAPI-приложения.
Запуск: uvicorn backend.api.main:app --reload
"""
import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.config import settings
from backend.db.database import init_db, SessionLocal
from backend.db import repository as repo
from backend.api.routes import auth, chats, groups, qa

logger = logging.getLogger("tg_parser")


def _resume_orphaned_chats() -> None:
    """
    Чаты, застрявшие в статусе 'processing' — это остатки от предыдущего запуска
    (сервер упал/перезапустился посреди эмбеддинга). Раз мы только что стартовали,
    точно никто их больше не обрабатывает — можно безопасно продолжить с сохранённого
    прогресса (chunk_count), если исходный файл ещё на диске.
    """
    db = SessionLocal()
    try:
        stuck = repo.get_stuck_processing_chats(db)
        for chat in stuck:
            file_path = settings.uploads_dir / f"{chat.id}.json"
            if file_path.exists():
                logger.info(f"[chat {chat.id}] Обработка была прервана — возобновляю с {chat.chunk_count} чанков.")
                threading.Thread(
                    target=chats._process_upload,
                    args=(chat.id, chat.owner_id, str(file_path), True),
                    daemon=True,
                ).start()
            else:
                logger.warning(f"[chat {chat.id}] Обработка прервана, исходный файл не найден.")
                repo.update_chat_status(
                    db, chat.id, "error",
                    error_msg="Обработка была прервана (перезапуск сервера), исходный файл не найден — загрузите чат заново.",
                )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.ensure_dirs()
    _resume_orphaned_chats()
    yield


app = FastAPI(
    title="TG-parser API",
    description="Вопросы по Telegram-чатам через RAG",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-роуты
app.include_router(auth.router, prefix="/auth", tags=["Аутентификация"])
app.include_router(chats.router, prefix="/chats", tags=["Чаты"])
app.include_router(groups.router, prefix="/groups", tags=["Группы"])
app.include_router(qa.router, prefix="/qa", tags=["Вопрос-ответ"])


@app.get("/health", tags=["Служебное"])
def health():
    return {"status": "ok"}


# Раздаём фронтенд
_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
