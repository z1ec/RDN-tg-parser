"""
Быстрая проверка парсера на реальном файле.
Запуск: python backend/scripts/test_parser.py ChatExport_2026-06-27/result.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.parsing.parser import parse_telegram_export
from backend.chunking.chunker import chunk_messages

if len(sys.argv) < 2:
    print("Укажи путь к result.json: python backend/scripts/test_parser.py <path>")
    sys.exit(1)

path = sys.argv[1]
print(f"\nПарсим: {path}")
chat_meta, messages = parse_telegram_export(path)

print(f"\nМета чата: {chat_meta}")
print(f"Сообщений после очистки: {len(messages)}")
print(f"\nПервые 3 сообщения:")
for m in messages[:3]:
    print(f"  [{m['date'].strftime('%Y-%m-%d %H:%M')}] {m['sender']}: {m['text'][:80]}")

print(f"\nЧанкуем...")
chunks = chunk_messages(messages, chat_id=chat_meta['id'], owner_id=1)
print(f"Чанков: {len(chunks)}")
print(f"\nПервые 3 чанка:")
for i, c in enumerate(chunks[:3]):
    meta = c['metadata']
    print(f"\n  Чанк #{i+1}")
    print(f"  Период: {meta['date_start'][:16]} — {meta['date_end'][:16]}")
    print(f"  Участники: {meta['participants']}")
    print(f"  Сообщений: {meta['msg_count']}, символов: {len(c['text'])}")
    print(f"  Текст (первые 200 симв): {c['text'][:200]}")
