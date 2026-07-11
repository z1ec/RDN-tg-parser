"""
Обёртка над sentence-transformers (BGE-M3).
Модель загружается один раз при первом использовании.
"""
from sentence_transformers import SentenceTransformer
from backend.config import settings


class Embedder:
    def __init__(self):
        self._model = SentenceTransformer(settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Возвращает нормализованные векторы для списка текстов."""
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
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
