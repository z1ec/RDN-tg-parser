"""
Чанкер: группирует нормализованные сообщения в смысловые куски (разговоры).

Логика разделения:
  - Новый чанк — если пауза между сообщениями >= gap_minutes.
  - Новый чанк — если текущий чанк вырос >= max_chars.
  - overlap_messages последних сообщений переносится в начало следующего чанка.
"""
from datetime import datetime
from backend.config import settings


def _format_message(msg: dict) -> str:
    """Одна строка формата [Имя]: текст."""
    return f"[{msg['sender']}]: {msg['text']}"


def _flush(msgs: list[dict], chat_id: int, owner_id: int) -> dict | None:
    """Собирает чанк из списка сообщений."""
    if not msgs:
        return None
    text = "\n".join(_format_message(m) for m in msgs)
    participants = list(dict.fromkeys(m["sender"] for m in msgs))
    return {
        "text": text,
        "metadata": {
            "chat_id": str(chat_id),
            "owner_id": str(owner_id),
            "date_start": msgs[0]["date"].isoformat(),
            "date_end": msgs[-1]["date"].isoformat(),
            "participants": ", ".join(participants),
            "first_msg_id": msgs[0]["id"],
            "last_msg_id": msgs[-1]["id"],
            "msg_count": len(msgs),
        },
    }


def chunk_messages(
    messages: list[dict],
    chat_id: int,
    owner_id: int,
    gap_minutes: int | None = None,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    """
    Возвращает список чанков. Каждый чанк — dict с ключами 'text' и 'metadata'.
    Параметры берутся из конфига, если не переданы явно.
    """
    gap_min = gap_minutes if gap_minutes is not None else settings.chunk_gap_minutes
    max_ch = max_chars if max_chars is not None else settings.chunk_max_chars
    overlap_n = overlap if overlap is not None else settings.chunk_overlap_messages

    if not messages:
        return []

    chunks: list[dict] = []
    current: list[dict] = []
    current_chars = 0
    prev_date: datetime | None = None

    for msg in messages:
        # Проверяем паузу с предыдущим сообщением
        if prev_date is not None:
            gap_sec = (msg["date"] - prev_date).total_seconds()
            if gap_sec / 60 >= gap_min:
                chunk = _flush(current, chat_id, owner_id)
                if chunk:
                    chunks.append(chunk)
                # Начинаем новый чанк с overlap сообщений из конца прошлого
                current = current[-overlap_n:] if overlap_n > 0 else []
                current_chars = sum(len(m["text"]) for m in current)

        current.append(msg)
        current_chars += len(msg["text"])
        prev_date = msg["date"]

        # Принудительное закрытие при превышении размера
        if current_chars >= max_ch:
            chunk = _flush(current, chat_id, owner_id)
            if chunk:
                chunks.append(chunk)
            current = current[-overlap_n:] if overlap_n > 0 else []
            current_chars = sum(len(m["text"]) for m in current)

    # Остаток
    chunk = _flush(current, chat_id, owner_id)
    if chunk:
        chunks.append(chunk)

    return chunks
