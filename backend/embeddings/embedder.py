"""
Обёртка над sentence-transformers (BGE-M3).
Модель загружается один раз при первом использовании.
"""
import torch
from sentence_transformers import SentenceTransformer
from backend.config import settings


def _resolve_device() -> str:
    """Автоопределение устройства: cuda > mps > cpu."""
    if settings.embedding_device != "auto":
        return settings.embedding_device
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class Embedder:
    def __init__(self):
        device = _resolve_device()
        self._model = SentenceTransformer(settings.embedding_model, device=device)
        # fp16 даёт заметный прирост скорости, но поддержан стабильно только на cuda
        if settings.embedding_fp16 and device == "cuda":
            self._model = self._model.half()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Возвращает нормализованные векторы для списка текстов."""
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=settings.embedding_batch_size,
        ).tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Ленивая инициализация — модель грузится при первом вызове."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
