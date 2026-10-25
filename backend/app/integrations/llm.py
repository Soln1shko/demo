"""Клиент LLM с открытыми весами через Ollama. Необязателен: без него работает сценарный помощник."""

from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()

SYSTEM_PROMPT = (
    "Ты — помощник кредитного кабинета предпринимателя. Отвечай по-русски, кратко и простыми словами. "
    "Используй ТОЛЬКО факты из блока «Контекст». Если данных нет — так и скажи и предложи позвать оператора. "
    "Не обещай одобрения кредита и не выдумывай условия."
)


async def ask_llm(question: str, context: str) -> str | None:
    """Возвращает ответ модели или None, если LLM не настроена/недоступна."""
    s = get_settings()
    if not s.llm_base_url:
        return None
    payload = {
        "model": s.llm_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {question}"},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{s.llm_base_url.rstrip('/')}/api/chat", json=payload)
            r.raise_for_status()
            text = r.json().get("message", {}).get("content", "").strip()
            return text or None
    except Exception as exc:  # noqa: BLE001 — деградация к сценарному помощнику
        log.warning("llm_unavailable", error=str(exc))
        return None
