"""
RAG-пайплайн: вопрос → поиск → промпт → ответ LLM.
"""
from backend.config import settings
from backend.vectorstore.store import get_store
from backend.llm.factory import get_llm

_SYSTEM = (
    "Ты — помощник, который отвечает на вопросы строго на основе "
    "предоставленных фрагментов переписки из Telegram-чата. "
    "Отвечай на том языке, на котором задан вопрос. "
    "Если ответ не найден во фрагментах — честно скажи об этом. "
    "Не придумывай информацию, которой нет в переписке."
)

_USER_TMPL = """\
Вопрос: {question}

Фрагменты переписки (по убыванию релевантности):
{context}

Дай развёрнутый ответ на основе этих фрагментов.
В конце кратко укажи временной диапазон источников."""


def ask(
    question: str,
    owner_id: int,
    chat_ids: list[int] | None = None,
    top_k: int | None = None,
) -> dict:
    """
    Возвращает:
        answer  — текст ответа
        sources — список метаданных использованных чанков
    """
    store = get_store()
    chunks = store.search(question, owner_id=owner_id, chat_ids=chat_ids, top_k=top_k)

    if not chunks:
        return {
            "answer": "Не нашёл релевантных фрагментов переписки по этому вопросу.",
            "sources": [],
        }

    # Формируем контекст для промпта
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        date_range = f"{meta.get('date_start', '')[:10]} — {meta.get('date_end', '')[:10]}"
        context_parts.append(
            f"[Источник {i} | {date_range} | оценка: {chunk['score']:.2f}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = _USER_TMPL.format(question=question, context=context)
    llm = get_llm()
    answer = llm.complete(prompt=prompt, system=_SYSTEM)

    return {
        "answer": answer,
        "sources": [
            {
                "score": round(c["score"], 3),
                "date_start": c["metadata"].get("date_start", ""),
                "date_end": c["metadata"].get("date_end", ""),
                "participants": c["metadata"].get("participants", ""),
                "chat_id": c["metadata"].get("chat_id", ""),
                "first_msg_id": c["metadata"].get("first_msg_id"),
                "last_msg_id": c["metadata"].get("last_msg_id"),
            }
            for c in chunks
        ],
    }
