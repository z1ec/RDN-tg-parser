"""
Точка входа: python run.py
Запускает uvicorn с параметрами из .env.
"""
import logging
import uvicorn
from backend.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    settings.ensure_dirs()
    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_dirs=["backend"],
    )
