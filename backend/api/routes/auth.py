"""Эндпоинты регистрации и логина."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import repository as repo
from backend.api.auth_utils import create_token

router = APIRouter()


class AuthRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: AuthRequest, db: Session = Depends(get_db)):
    if repo.get_user_by_login(db, body.login):
        raise HTTPException(status_code=409, detail="Логин уже занят")
    user = repo.create_user(db, body.login, body.password)
    return TokenResponse(access_token=create_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: AuthRequest, db: Session = Depends(get_db)):
    user = repo.authenticate(db, body.login, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return TokenResponse(access_token=create_token(user.id))
