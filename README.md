# TG-parser — вопросы по Telegram-чатам (RAG)

Веб-приложение для семантического поиска и ответов по выгрузкам Telegram-чатов.
Подход: RAG (Retrieval-Augmented Generation), без дообучения модели.

## Быстрый старт

### 1. Клонировать и войти в папку

```bash
git clone <repo-url>
cd TG-parser
```

### 2. Создать виртуальное окружение и установить зависимости

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настроить окружение

```bash
cp .env.example .env
# Открыть .env и заполнить нужные ключи
```

### 4. Проверить установку (Этап 0)

```bash
python backend/scripts/check_stage0.py
```

Должно вывести `[OK] Этап 0 пройден.`

## Структура проекта

```
TG-parser/
  backend/
    config.py        # конфиг + чтение .env
    parsing/         # парсер экспорта Telegram
    chunking/        # разбивка сообщений на смысловые куски
    embeddings/      # обёртка над BGE-M3
    vectorstore/     # обёртка над Chroma
    llm/             # обёртка над LLM (Ollama / Gemini / Groq)
    rag/             # поиск → промпт → ответ
    db/              # SQLite: пользователи, чаты, группы
    api/             # FastAPI (этап 6)
    scripts/         # скрипты для ручной проверки каждого этапа
  frontend/          # этап 7
  data/              # локальные данные (в .gitignore)
  .env.example
  requirements.txt
```

## Стек

| Компонент       | Технология                          |
|-----------------|-------------------------------------|
| Бэкенд API      | FastAPI + Uvicorn                   |
| Векторная БД    | ChromaDB (локально)                 |
| Обычная БД      | SQLite (через SQLAlchemy)           |
| Эмбеддинги      | BGE-M3 (sentence-transformers)      |
| LLM             | Ollama / Gemini / Groq (pluggable)  |
| Конфиг          | pydantic-settings + python-dotenv   |

## Этапы разработки

- [x] Этап 0 — каркас проекта
- [ ] Этап 1 — парсер Telegram JSON
- [ ] Этап 2 — чанкинг (разбивка на разговоры)
- [ ] Этап 3 — эмбеддинги + векторная база
- [ ] Этап 4 — RAG-ответ (LLM)
- [ ] Этап 5 — модель данных (SQLite), управление чатами/группами
- [ ] Этап 6 — API (FastAPI)
- [ ] Этап 7 — фронтенд# RDN-tg-parser
