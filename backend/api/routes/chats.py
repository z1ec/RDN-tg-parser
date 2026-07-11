"""
Эндпоинты управления чатами:
  POST   /chats/upload        — загрузить result.json (фоновая обработка)
  GET    /chats               — список чатов пользователя
  GET    /chats/{id}/status   — статус обработки
  DELETE /chats/{id}          — удалить чат
"""
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks

logger = logging.getLogger("tg_parser")
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db, SessionLocal
from backend.db import repository as repo
from backend.db.models import Chat, User
from backend.api.auth_utils import get_current_user
from backend.parsing.parser import parse_telegram_export
from backend.chunking.chunker import chunk_messages
from backend.vectorstore.store import get_store

router = APIRouter()


# ── Схемы ответов ──────────────────────────────────────────────────────────

class ChatOut(BaseModel):
    id: int
    title: str
    source: str
    status: str
    error_msg: str
    chunk_count: int
    tg_chat_id: int | None
    groups: list[str]

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    chat_id: int
    message: str


# ── Фоновая задача обработки ───────────────────────────────────────────────

def _process_upload(chat_id: int, owner_id: int, file_path: str) -> None:
    """
    Запускается в фоне FastAPI BackgroundTasks.
    Парсит файл, чанкует, эмбеддит батчами, кладёт в Chroma.
    """
    db = SessionLocal()
    try:
        repo.update_chat_status(db, chat_id, "processing")

        logger.info(f"[chat {chat_id}] Парсинг файла...")
        chat_meta, messages = parse_telegram_export(file_path)
        tg_id = chat_meta["id"]
        logger.info(f"[chat {chat_id}] Сообщений: {len(messages)}")

        db.query(Chat).filter(Chat.id == chat_id).update({"tg_chat_id": tg_id})
        db.commit()

        chunks = chunk_messages(messages, chat_id=tg_id, owner_id=owner_id)
        total = len(chunks)
        logger.info(f"[chat {chat_id}] Чанков: {total}. Начинаю эмбеддинги...")

        store = get_store()

        def on_progress(added: int, _total: int) -> None:
            logger.info(f"[chat {chat_id}] Эмбеддинги: {added}/{_total} чанков")
            repo.update_chat_status(db, chat_id, "processing", chunk_count=added)

        store.add_chunks(
            chunks,
            chat_id=tg_id,
            owner_id=owner_id,
            batch_size=100,
            progress_cb=on_progress,
        )

        repo.update_chat_status(db, chat_id, "ready", chunk_count=total)
        logger.info(f"[chat {chat_id}] Готово! {total} чанков проиндексировано.")
    except Exception as exc:
        logger.error(f"[chat {chat_id}] Ошибка: {exc}")
        repo.update_chat_status(db, chat_id, "error", error_msg=str(exc)[:500])
    finally:
        db.close()
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass


# ── Эндпоинты ──────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_chat(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Ожидается файл .json")

    # Сохраняем во временный файл
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()
    except Exception as exc:
        tmp.close()
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {exc}")

    # Создаём запись чата (без tg_chat_id — узнаем после парсинга)
    chat = repo.create_chat(
        db,
        owner_id=current_user.id,
        title=file.filename.removesuffix(".json"),
        source=file.filename,
    )

    background_tasks.add_task(_process_upload, chat.id, current_user.id, tmp.name)

    return UploadResponse(chat_id=chat.id, message="Файл принят, обработка запущена")


@router.get("", response_model=list[ChatOut])
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chats = repo.get_chats(db, current_user.id)
    result = []
    for c in chats:
        result.append(ChatOut(
            id=c.id,
            title=c.title,
            source=c.source,
            status=c.status,
            error_msg=c.error_msg or "",
            chunk_count=c.chunk_count or 0,
            tg_chat_id=c.tg_chat_id,
            groups=[g.name for g in c.groups],
        ))
    return result


@router.get("/{chat_id}/status")
def chat_status(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = repo.get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return {
        "id": chat.id,
        "status": chat.status,
        "chunk_count": chat.chunk_count or 0,
        "error_msg": chat.error_msg or "",
    }


@router.delete("/{chat_id}", status_code=204)
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = repo.get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    # Удаляем чанки из Chroma (единственное место, где трогаем векторы при удалении)
    if chat.tg_chat_id is not None:
        store = get_store()
        store.delete_chat(chat_id=chat.tg_chat_id, owner_id=current_user.id)

    repo.delete_chat(db, chat_id, current_user.id)
