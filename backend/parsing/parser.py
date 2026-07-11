"""
Парсер экспорта Telegram Desktop.
Читает result.json, нормализует сообщения в список словарей.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _extract_text(raw_text: Any) -> str:
    """
    Извлекает плоский текст из поля 'text'.
    Поле может быть строкой или списком кусочков (строки + объекты с type/text).
    """
    if isinstance(raw_text, str):
        return raw_text
    if isinstance(raw_text, list):
        parts = []
        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


def parse_telegram_export(path: str | Path) -> tuple[dict, list[dict]]:
    """
    Читает result.json, возвращает (мета-чата, нормализованные сообщения).

    Нормализованное сообщение:
        id       — int
        date     — datetime
        sender   — str (имя или from_id если имя отсутствует)
        reply_to — int | None
        text     — str (плоский текст)

    Пропускает:
        - сообщения type != "message" (вступления, закрепы, etc.)
        - сообщения с пустым текстом
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    chat_meta = {
        "id": data.get("id"),
        "name": data.get("name", ""),
        "type": data.get("type", ""),
    }

    messages: list[dict] = []
    for msg in data.get("messages", []):
        if msg.get("type") != "message":
            continue

        text = _extract_text(msg.get("text", "")).strip()
        if not text:
            continue

        # Имя отправителя: поле from может быть null (анонимные боты и т.п.)
        sender = msg.get("from") or msg.get("from_id", "unknown")

        messages.append({
            "id": msg["id"],
            "date": datetime.fromisoformat(msg["date"]),
            "sender": str(sender),
            "reply_to": msg.get("reply_to_message_id"),
            "text": text,
        })

    return chat_meta, messages
