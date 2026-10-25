"""HTTP-клиент к inference-сервису из папки `ml/`. Если сервис молчит — вызывающий получает None."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()
TIMEOUT = 12.0
SLOW = 180.0


def _base() -> str:
    url = (get_settings().ml_base_url or "").rstrip("/")
    return url


def available() -> bool:
    return bool(_base())


async def call(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    request_timeout: float = TIMEOUT,
) -> Any | None:
    """Вызывает ML. 4xx/5xx и сеть не роняют кабинет: возвращается None."""
    if not available():
        return None
    url = f"{_base()}{path}"
    kwargs: dict[str, Any] = {}
    if files is not None:
        kwargs["files"] = files
        if payload:
            kwargs["data"] = payload
    elif payload is not None:
        kwargs["json"] = payload
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            response = await client.request(method, url, **kwargs)
    except httpx.HTTPError as error:
        log.warning("ml_unreachable", path=path, error=str(error))
        return None
    if response.status_code >= 400:
        log.warning("ml_rejected", path=path, status=response.status_code, detail=response.text[:300])
        return None
    if not response.content:
        return None
    return response.json()


async def score(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/scoring", body)
    return data if isinstance(data, dict) else None


async def score_weights() -> dict[str, Any] | None:
    data = await call("GET", "/v1/scoring/weights")
    return data if isinstance(data, dict) else None


async def nba(body: dict[str, Any]) -> list[dict[str, Any]] | None:
    data = await call("POST", "/v1/nba/recommendations", body)
    return data if isinstance(data, list) else None


async def advise(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/credit-advisor/recommendations", body, request_timeout=25)
    return data if isinstance(data, dict) else None


async def recover(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/offer-recovery/recommendations", body)
    return data if isinstance(data, dict) else None


async def underwrite(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/underwriting/summary", body, request_timeout=25)
    return data if isinstance(data, dict) else None


async def explain_refusal(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/decision-explainer/refusal", body, request_timeout=25)
    return data if isinstance(data, dict) else None


async def cash_gap(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/cash-gap/forecast", body)
    return data if isinstance(data, dict) else None


async def forecast(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/ml/forecast", body, request_timeout=20)
    return data if isinstance(data, dict) else None


async def simulate(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/ml/simulate", body, request_timeout=20)
    return data if isinstance(data, dict) else None


async def quest_generate(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/ml/quest/generate", body, request_timeout=20)
    return data if isinstance(data, dict) else None


async def quest_recalculate(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/ml/quest/recalculate", body, request_timeout=20)
    return data if isinstance(data, dict) else None


async def assistant_answer(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/assistant/answer", body, request_timeout=25)
    return data if isinstance(data, dict) else None


async def assistant_search(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = await call("POST", "/v1/assistant/search", body)
    return data if isinstance(data, list) else []


async def copilot(body: dict[str, Any]) -> dict[str, Any] | None:
    data = await call("POST", "/v1/crm-copilot/reply", body, request_timeout=25)
    return data if isinstance(data, dict) else None


async def parse_documents(case_id: str, uploads: list[tuple[str, bytes, str]]) -> dict[str, Any] | None:
    files = [("files", (name, content, mime)) for name, content, mime in uploads]
    data = await call("POST", "/v1/documents/parse", {"case_id": case_id}, files=files, request_timeout=SLOW)
    return data if isinstance(data, dict) else None
