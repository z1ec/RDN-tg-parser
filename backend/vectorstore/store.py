"""
Обёртка над ChromaDB.
Единственная коллекция 'chunks' хранит все чанки всех пользователей.
Изоляция обеспечивается фильтрацией по owner_id при каждом поиске.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings
from backend.embeddings.embedder import get_embedder


class VectorStore:
    def __init__(self):
        settings.ensure_dirs()
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        chunks: list[dict],
        chat_id: int,
        owner_id: int,
        batch_size: int | None = None,
        progress_cb=None,
    ) -> None:
        """
        Добавляет чанки чата батчами, чтобы не исчерпать память.
        Перед добавлением удаляет старые данные чата.

        batch_size  — сколько чанков обрабатываем за один раз
                      (по умолчанию = размер батча эмбеддера, чтобы не дробить дважды)
        progress_cb — опциональный callback(added: int, total: int)
        """
        self.delete_chat(chat_id=chat_id, owner_id=owner_id)

        if not chunks:
            return

        embedder = get_embedder()
        total = len(chunks)
        batch = batch_size or settings.embedding_batch_size

        for batch_start in range(0, total, batch):
            batch_chunks = chunks[batch_start : batch_start + batch]
            texts = [c["text"] for c in batch_chunks]

            vectors = embedder.embed(texts)

            ids = [f"c{chat_id}_o{owner_id}_{batch_start + i}" for i in range(len(batch_chunks))]
            clean_meta = [
                {k: (str(v) if v is not None else "") for k, v in c["metadata"].items()}
                for c in batch_chunks
            ]

            self._collection.add(
                ids=ids,
                embeddings=vectors,
                documents=texts,
                metadatas=clean_meta,
            )

            if progress_cb:
                progress_cb(min(batch_start + batch, total), total)

    def search(
        self,
        query: str,
        owner_id: int,
        chat_ids: list[int] | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Семантический поиск. Всегда фильтруется по owner_id.
        chat_ids — опциональный дополнительный фильтр по конкретным чатам.
        """
        k = top_k or settings.rag_top_k
        embedder = get_embedder()
        query_vec = embedder.embed_one(query)

        # Строим where-фильтр
        if chat_ids:
            where: dict = {
                "$and": [
                    {"owner_id": {"$eq": str(owner_id)}},
                    {"chat_id": {"$in": [str(cid) for cid in chat_ids]}},
                ]
            }
        else:
            where = {"owner_id": {"$eq": str(owner_id)}}

        total = self._collection.count()
        if total == 0:
            return []

        results = self._collection.query(
            query_embeddings=[query_vec],
            n_results=min(k, total),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({"text": doc, "metadata": meta, "score": 1.0 - float(dist)})
        return chunks

    def delete_chat(self, chat_id: int, owner_id: int) -> None:
        """Удаляет все чанки чата из Chroma (вызывается при удалении чата)."""
        try:
            self._collection.delete(
                where={
                    "$and": [
                        {"chat_id": {"$eq": str(chat_id)}},
                        {"owner_id": {"$eq": str(owner_id)}},
                    ]
                }
            )
        except Exception:
            pass  # Если чанков нет — не ошибка

    def count(self) -> int:
        return self._collection.count()


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
