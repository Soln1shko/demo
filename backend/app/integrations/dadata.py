"""Поиск реальной компании по ИНН через DaData (метод findById/party).

Бесплатный тариф: 10 000 запросов в сутки (проверено на https://dadata.ru/pricing/). Нужен API-ключ
в переменной `DADATA_API_KEY`. Используется только для подсказки при вводе ИНН; проверка заявки
(ФНС/БКИ) по-прежнему идёт через детерминированные симуляторы.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx

URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
CACHE_TTL = 6 * 3600  # экономим дневной лимит

STATUS_TEXT = {
    "ACTIVE": "Действующая организация",
    "LIQUIDATING": "В стадии ликвидации",
    "LIQUIDATED": "Ликвидирована",
    "BANKRUPT": "Банкротство",
    "REORGANIZING": "В процессе реорганизации",
}

_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


class LookupUnavailable(Exception):
    """Сервис недоступен, ключ неверен или исчерпан лимит."""


def _date(ms: int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date().isoformat()


def _map(item: dict[str, Any], inn: str) -> dict[str, Any]:
    d = item.get("data") or {}
    individual = d.get("type") == "INDIVIDUAL" or len(inn) == 12
    state = d.get("state") or {}
    status = state.get("status") or "ACTIVE"
    main_okved = next((o for o in d.get("okveds") or [] if o.get("main")), None)
    name = item.get("value") or (d.get("name") or {}).get("short_with_opf") or ""
    return {
        "inn": d.get("inn") or inn,
        "legal": "ip" if individual else "ooo",
        "name": name,
        "status": "active" if status == "ACTIVE" else "liquidating",
        "status_text": STATUS_TEXT.get(status, status),
        "okved": {"code": d.get("okved") or "", "title": (main_okved or {}).get("name", "")},
        "registered_at": _date(state.get("registration_date")),
        "head": (d.get("management") or {}).get("name") or "",
        "address": ((d.get("address") or {}).get("value")) or "",
        "source": "DaData (данные ЕГРЮЛ/ЕГРИП)",
    }


async def find_company(inn: str, api_key: str, wait_s: float = 4.0) -> dict[str, Any] | None:
    """Возвращает компанию или None, если по ИНН ничего не найдено. Ошибки сервиса — LookupUnavailable."""
    hit = _cache.get(inn)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=wait_s) as client:
            resp = await client.post(
                URL,
                json={"query": inn, "count": 1, "branch_type": "MAIN"},
                headers={"Authorization": f"Token {api_key}", "Accept": "application/json"},
            )
    except httpx.HTTPError as e:
        raise LookupUnavailable(str(e)) from e
    if resp.status_code != 200:
        raise LookupUnavailable(f"DaData вернула {resp.status_code}")
    items = resp.json().get("suggestions") or []
    result = _map(items[0], inn) if items else None
    _cache[inn] = (time.monotonic(), result)
    return result
