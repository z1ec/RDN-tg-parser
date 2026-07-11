"""SQLAlchemy-модели: users, chats, groups, chat_group."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# Таблица членства (чат ↔ группа, many-to-many)
chat_group_table = Table(
    "chat_group",
    Base.metadata,
    Column("chat_id", Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    chats = relationship("Chat", back_populates="owner", cascade="all, delete-orphan")
    groups = relationship("Group", back_populates="owner", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    source = Column(String, default="")           # имя загруженного файла
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")    # pending | processing | ready | error
    error_msg = Column(String, default="")
    tg_chat_id = Column(Integer, nullable=True)   # оригинальный ID чата из Telegram
    chunk_count = Column(Integer, default=0)      # число уже обработанных чанков (в Chroma)
    total_chunks = Column(Integer, default=0)     # общее число чанков (известно после чанкинга)

    owner = relationship("User", back_populates="chats")
    groups = relationship("Group", secondary=chat_group_table, back_populates="chats")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    owner = relationship("User", back_populates="groups")
    chats = relationship("Chat", secondary=chat_group_table, back_populates="groups")
