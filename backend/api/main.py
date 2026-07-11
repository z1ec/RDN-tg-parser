"""
Главный файл FastAPI-приложения.
Запуск: uvicorn backend.api.main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.db.database import init_db
from backend.api.routes import auth, chats, groups, qa


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
