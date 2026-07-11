FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (нужны для сборки chromadb и sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Зависимости Python — отдельный слой, чтобы не пересобирать при изменении кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py .

# Папки для данных (перекрываются volume при запуске)
RUN mkdir -p data/chroma

# Кэш HuggingFace-моделей (BGE-M3 ~1.5 GB) — выносим в volume,
# чтобы не скачивать заново при каждом пересборке
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models

EXPOSE 8000

CMD ["python", "run.py"]
