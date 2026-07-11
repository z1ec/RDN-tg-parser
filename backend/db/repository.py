"""
Все операции с SQLite. Никакой бизнес-логики выше этого слоя.
"""
import hashlib
from sqlalchemy.orm import Session
from backend.db.models import User, Chat, Group, chat_group_table


# ── Вспомогательная функция ────────────────────────────────────────────────

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ── Пользователи ───────────────────────────────────────────────────────────

def create_user(db: Session, login: str, password: str) -> User:
    user = User(login=login, password_hash=_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_login(db: Session, login: str) -> User | None:
    return db.query(User).filter(User.login == login).first()


def authenticate(db: Session, login: str, password: str) -> User | None:
    user = get_user_by_login(db, login)
    if user and user.password_hash == _hash(password):
        return user
    return None


# ── Чаты ───────────────────────────────────────────────────────────────────

def create_chat(
    db: Session,
    owner_id: int,
    title: str,
    source: str = "",
    tg_chat_id: int | None = None,
) -> Chat:
    chat = Chat(
        owner_id=owner_id,
        title=title,
        source=source,
        tg_chat_id=tg_chat_id,
        status="pending",
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_chats(db: Session, owner_id: int) -> list[Chat]:
    return db.query(Chat).filter(Chat.owner_id == owner_id).order_by(Chat.created_at.desc()).all()


def get_chat(db: Session, chat_id: int, owner_id: int) -> Chat | None:
    return db.query(Chat).filter(Chat.id == chat_id, Chat.owner_id == owner_id).first()


def update_chat_status(
    db: Session,
    chat_id: int,
    status: str,
    error_msg: str = "",
    chunk_count: int = 0,
) -> None:
    update_vals = {"status": status}
    if error_msg:
        update_vals["error_msg"] = error_msg
    if chunk_count:
        update_vals["chunk_count"] = chunk_count
    db.query(Chat).filter(Chat.id == chat_id).update(update_vals)
    db.commit()


def delete_chat(db: Session, chat_id: int, owner_id: int) -> bool:
    """
    Удаляет чат из SQLite.
    Чанки из Chroma удаляет вызывающий код (vectorstore.delete_chat),
    потому что репозиторий не знает о Chroma.
    """
    chat = get_chat(db, chat_id, owner_id)
    if not chat:
        return False
    db.delete(chat)
    db.commit()
    return True


# ── Группы ─────────────────────────────────────────────────────────────────

def create_group(db: Session, owner_id: int, name: str) -> Group:
    group = Group(owner_id=owner_id, name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def get_groups(db: Session, owner_id: int) -> list[Group]:
    return db.query(Group).filter(Group.owner_id == owner_id).all()


def get_group(db: Session, group_id: int, owner_id: int) -> Group | None:
    return db.query(Group).filter(Group.id == group_id, Group.owner_id == owner_id).first()


def delete_group(db: Session, group_id: int, owner_id: int) -> bool:
    """Удаляет только членства; чаты и векторы остаются."""
    group = get_group(db, group_id, owner_id)
    if not group:
        return False
    db.execute(chat_group_table.delete().where(chat_group_table.c.group_id == group_id))
    db.delete(group)
    db.commit()
    return True


def add_chat_to_group(db: Session, chat_id: int, group_id: int, owner_id: int) -> bool:
    chat = get_chat(db, chat_id, owner_id)
    group = get_group(db, group_id, owner_id)
    if not chat or not group:
        return False
    if group not in chat.groups:
        chat.groups.append(group)
        db.commit()
    return True


def remove_chat_from_group(db: Session, chat_id: int, group_id: int, owner_id: int) -> bool:
    chat = get_chat(db, chat_id, owner_id)
    group = get_group(db, group_id, owner_id)
    if not chat or not group:
        return False
    if group in chat.groups:
        chat.groups.remove(group)
        db.commit()
    return True


def get_tg_chat_ids_in_group(db: Session, group_id: int, owner_id: int) -> list[int]:
    """Возвращает список tg_chat_id чатов в группе (для фильтрации Chroma)."""
    group = get_group(db, group_id, owner_id)
    if not group:
        return []
    return [c.tg_chat_id for c in group.chats if c.tg_chat_id is not None]
