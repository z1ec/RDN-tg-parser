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
    """Создаёт таблицы, если их нет, и докатывает недостающие колонки в уже существующих."""
    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Лёгкие ALTER TABLE для колонок, добавленных после первого релиза схемы."""
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(chats)").fetchall()}
        if "total_chunks" not in cols:
            conn.exec_driver_sql("ALTER TABLE chats ADD COLUMN total_chunks INTEGER DEFAULT 0")
        conn.commit()


def get_db():
    """Зависимость FastAPI — выдаёт сессию и закрывает после запроса."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
