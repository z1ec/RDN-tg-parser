"""Движок SQLAlchemy и сессии."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings
from backend.db.models import Base


def _make_engine():
    settings.ensure_dirs()
    return create_engine(
        f"sqlite:///{settings.sqlite_path}",
        connect_args={"check_same_thread": False},
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Создаёт таблицы, если их нет."""
    Base.metadata.create_all(engine)


def get_db():
    """Зависимость FastAPI — выдаёт сессию и закрывает после запроса."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
