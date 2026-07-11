"""Эндпоинт вопрос-ответ (RAG)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import repository as repo
from backend.db.models import User
from backend.api.auth_utils import get_current_user
from backend.rag.retriever import ask
from backend.config import settings

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str
    chat_id: int | None = None    # фильтр по конкретному чату (id из нашей БД)
    group_id: int | None = None   # фильтр по группе
    top_k: int | None = None


class SourceOut(BaseModel):
    score: float
    date_start: str
    date_end: str
    participants: str
    chat_id: str
    first_msg_id: str | None
    last_msg_id: str | None


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


@router.post("", response_model=AnswerResponse)
def question(
    body: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    # Резолвим фильтр по tg_chat_id
    tg_chat_ids: list[int] | None = None

    if body.chat_id is not None:
        chat = repo.get_chat(db, body.chat_id, current_user.id)
        if not chat:
            raise HTTPException(status_code=404, detail="Чат не найден")
        if chat.tg_chat_id is None:
            raise HTTPException(status_code=400, detail="Чат ещё не обработан")
        tg_chat_ids = [chat.tg_chat_id]

    elif body.group_id is not None:
        tg_chat_ids = repo.get_tg_chat_ids_in_group(db, body.group_id, current_user.id)
        if not tg_chat_ids:
            raise HTTPException(status_code=404, detail="Группа не найдена или пуста")

    result = ask(
        question=body.question,
        owner_id=current_user.id,
        chat_ids=tg_chat_ids,
        top_k=body.top_k or settings.rag_top_k,
    )

    sources = [
        SourceOut(
            score=s["score"],
            date_start=s["date_start"],
            date_end=s["date_end"],
            participants=s["participants"],
            chat_id=str(s["chat_id"]),
            first_msg_id=str(s["first_msg_id"]) if s.get("first_msg_id") else None,
            last_msg_id=str(s["last_msg_id"]) if s.get("last_msg_id") else None,
        )
        for s in result["sources"]
    ]

    return AnswerResponse(answer=result["answer"], sources=sources)
