"""
Эндпоинты управления чатами:
  POST   /chats/upload        — загрузить result.json (фоновая обработка)
  GET    /chats               — список чатов пользователя
  GET    /chats/{id}/status   — статус обработки
  POST   /chats/{id}/pause    — приостановить обработку
  POST   /chats/{id}/resume   — продолжить обработку (после паузы или ошибки)
  DELETE /chats/{id}          — удалить чат
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks

logger = logging.getLogger("tg_parser")
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.database import get_db, SessionLocal
from backend.db import repository as repo
from backend.db.models import Chat, User
from backend.api.auth_utils import get_current_user
from backend.parsing.parser import parse_telegram_export
from backend.chunking.chunker import chunk_messages
from backend.vectorstore.store import get_store

router = APIRouter()


# Запросы на паузу для чатов, которые сейчас обрабатываются в фоне (in-memory).
# Переживает в пределах одного процесса — при перезапуске сервера все "processing"-чаты
# и так считаются осиротевшими и авто-возобновляются (см. main.py).
_pause_requested: dict[int, bool] = {}


class ProcessingPaused(Exception):
    """Внутренний сигнал: обработку попросили остановиться между батчами."""


def _upload_path(chat_id: int) -> Path:
    return settings.uploads_dir / f"{chat_id}.json"


# ── Схемы ответов ──────────────────────────────────────────────────────────

class ChatOut(BaseModel):
    id: int
    title: str
    source: str
    status: str
    error_msg: str
    chunk_count: int
    total_chunks: int
    tg_chat_id: int | None
    groups: list[str]

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    chat_id: int
    message: str


# ── Фоновая задача обработки ───────────────────────────────────────────────

def _process_upload(chat_id: int, owner_id: int, file_path: str, resume: bool = False) -> None:
    """
    Запускается в фоне FastAPI BackgroundTasks (или из авто-возобновления при старте сервера).
    Парсит файл, чанкует, эмбеддит батчами, кладёт в Chroma.

    resume=True — не удалять уже сохранённые в Chroma чанки, а продолжить с того места,
    на котором обработка остановилась в прошлый раз (chat.chunk_count).
    Исходный файл удаляется только при полном успехе — это и позволяет возобновлять.
    """
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return

        start_index = chat.chunk_count if resume else 0
        _pause_requested[chat_id] = False
        repo.update_chat_status(db, chat_id, "processing")

        logger.info(f"[chat {chat_id}] Парсинг файла...")
        chat_meta, messages = parse_telegram_export(file_path)
        tg_id = chat_meta["id"]
        logger.info(f"[chat {chat_id}] Сообщений: {len(messages)}")

        db.query(Chat).filter(Chat.id == chat_id).update({"tg_chat_id": tg_id})
        db.commit()

        chunks = chunk_messages(messages, chat_id=tg_id, owner_id=owner_id)
        total = len(chunks)
        repo.update_chat_status(db, chat_id, "processing", total_chunks=total)
        logger.info(f"[chat {chat_id}] Чанков: {total} (уже готово: {start_index}). Продолжаю эмбеддинги...")

        if start_index < total:
            store = get_store()

            def on_progress(added: int) -> None:
                logger.info(f"[chat {chat_id}] Эмбеддинги: {added}/{total} чанков")
                repo.update_chat_status(db, chat_id, "processing", chunk_count=added, total_chunks=total)
                if _pause_requested.get(chat_id):
                    raise ProcessingPaused()

            store.add_chunks(
                chunks[start_index:],
                chat_id=tg_id,
                owner_id=owner_id,
                start_index=start_index,
                fresh=(start_index == 0),
                progress_cb=on_progress,
            )

        repo.update_chat_status(db, chat_id, "ready", chunk_count=total, total_chunks=total)
        logger.info(f"[chat {chat_id}] Готово! {total} чанков проиндексировано.")
        Path(file_path).unlink(missing_ok=True)
    except ProcessingPaused:
        logger.info(f"[chat {chat_id}] Обработка приостановлена.")
        repo.update_chat_status(db, chat_id, "paused")
    except Exception as exc:
        logger.error(f"[chat {chat_id}] Ошибка: {exc}")
        repo.update_chat_status(db, chat_id, "error", error_msg=str(exc)[:500])
    finally:
        _pause_requested.pop(chat_id, None)
        db.close()


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

    # Создаём запись чата (без tg_chat_id — узнаем после парсинга)
    chat = repo.create_chat(
        db,
        owner_id=current_user.id,
        title=file.filename.removesuffix(".json"),
        source=file.filename,
    )

    # Сохраняем файл в постоянное место (не /tmp!) — он нужен, чтобы можно было
    # возобновить обработку после паузы/сбоя/перезапуска сервера. Удаляется
    # только при полном успехе (см. _process_upload).
    settings.ensure_dirs()
    dest_path = _upload_path(chat.id)
    try:
        content = await file.read()
        dest_path.write_bytes(content)
    except Exception as exc:
        repo.delete_chat(db, chat.id, current_user.id)
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {exc}")

    background_tasks.add_task(_process_upload, chat.id, current_user.id, str(dest_path))

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
            total_chunks=c.total_chunks or 0,
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
        "total_chunks": chat.total_chunks or 0,
        "error_msg": chat.error_msg or "",
    }


@router.post("/{chat_id}/pause", status_code=202)
def pause_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = repo.get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat.status != "processing":
        raise HTTPException(status_code=400, detail="Чат сейчас не обрабатывается")
    _pause_requested[chat_id] = True
    return {"message": "Пауза запрошена, остановится после текущего батча"}


@router.post("/{chat_id}/resume", response_model=UploadResponse, status_code=202)
def resume_chat(
    chat_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = repo.get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat.status not in ("paused", "error"):
        raise HTTPException(status_code=400, detail="Чат нельзя продолжить из текущего статуса")

    file_path = _upload_path(chat_id)
    if not file_path.exists():
        raise HTTPException(status_code=400, detail="Исходный файл не найден, загрузите чат заново")

    _pause_requested[chat_id] = False
    background_tasks.add_task(_process_upload, chat.id, current_user.id, str(file_path), True)
    return UploadResponse(chat_id=chat.id, message="Обработка возобновлена")


@router.delete("/{chat_id}", status_code=204)
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = repo.get_chat(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    # Если чат прямо сейчас обрабатывается в фоне — просим его остановиться,
    # чтобы не писать чанки удалённого чата в Chroma после этого запроса.
    _pause_requested[chat_id] = True

    # Удаляем чанки из Chroma (единственное место, где трогаем векторы при удалении)
    if chat.tg_chat_id is not None:
        store = get_store()
        store.delete_chat(chat_id=chat.tg_chat_id, owner_id=current_user.id)

    repo.delete_chat(db, chat_id, current_user.id)
    _upload_path(chat_id).unlink(missing_ok=True)
