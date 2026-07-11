"""
Проверочный скрипт для Этапа 0.
Запускать из корня проекта:
  python backend/scripts/check_stage0.py
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь, чтобы импорты работали
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import settings

print("=" * 50)
print("ПРОВЕРКА ЭТАПА 0: Каркас проекта")
print("=" * 50)

print(f"\n[OK] Конфиг загружен")
print(f"     LLM-провайдер:     {settings.llm_provider}")
print(f"     Эмбеддинг-модель:  {settings.embedding_model}")
print(f"     Папка данных:      {settings.data_dir}")
print(f"     Chroma:            {settings.chroma_dir}")
print(f"     SQLite:            {settings.sqlite_path}")
print(f"     Чанк-пауза (мин):  {settings.chunk_gap_minutes}")
print(f"     Чанк-макс (симв):  {settings.chunk_max_chars}")
print(f"     RAG top-k:         {settings.rag_top_k}")

print("\nСоздаю директории для данных...")
settings.ensure_dirs()

# Проверяем, что директории созданы
ok = True
for p in [settings.data_dir, settings.chroma_dir, settings.sqlite_path.parent]:
    if p.exists():
        print(f"  [OK] {p}")
    else:
        print(f"  [FAIL] {p} — не создана!")
        ok = False

if ok:
    print("\n[OK] Этап 0 пройден. Каркас проекта готов.")
else:
    print("\n[FAIL] Что-то пошло не так. Проверьте права на запись в текущей папке.")
    sys.exit(1)