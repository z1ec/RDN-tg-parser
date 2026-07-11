"""
Эндпоинты управления группами чатов.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import repository as repo
from backend.db.models import User
from backend.api.auth_utils import get_current_user

router = APIRouter()


class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseModel):
    id: int
    name: str
    chat_ids: list[int]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[GroupOut])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    groups = repo.get_groups(db, current_user.id)
    return [
        GroupOut(id=g.id, name=g.name, chat_ids=[c.id for c in g.chats])
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = repo.create_group(db, current_user.id, body.name)
    return GroupOut(id=group.id, name=group.name, chat_ids=[])


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = repo.delete_group(db, group_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Группа не найдена")


@router.post("/{group_id}/chats/{chat_id}", status_code=200)
def add_to_group(
    group_id: int,
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = repo.add_chat_to_group(db, chat_id, group_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Чат или группа не найдены")
    return {"ok": True}


@router.delete("/{group_id}/chats/{chat_id}", status_code=200)
def remove_from_group(
    group_id: int,
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = repo.remove_chat_from_group(db, chat_id, group_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Чат или группа не найдены")
    return {"ok": True}
