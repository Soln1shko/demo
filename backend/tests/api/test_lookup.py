from httpx import AsyncClient

from app.core.config import get_settings
from app.integrations import dadata

SAMPLE = {
    "value": 'ООО "МОТОРИКА"',
    "data": {
        "inn": "7719402047",
        "type": "LEGAL",
        "okved": "72.19",
        "okveds": [{"main": True, "code": "72.19", "name": "Научные исследования"}],
        "management": {"name": "Давидюк Андрей Павлович"},
        "address": {"value": "г Москва, ул Примерная, д 1"},
        "state": {"status": "ACTIVE", "registration_date": 1423094400000},
    },
}


async def _headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": "client@demo.ru", "password": "Demo2026!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_dadata_mapping():
    c = dadata._map(SAMPLE, "7719402047")
    assert c["name"] == 'ООО "МОТОРИКА"' and c["legal"] == "ooo" and c["status"] == "active"
    assert c["registered_at"] == "2015-02-05" and c["okved"]["code"] == "72.19"
    assert c["head"].startswith("Давидюк")


def test_dadata_liquidating_status():
    item = {**SAMPLE, "data": {**SAMPLE["data"], "state": {"status": "LIQUIDATING"}}}
    c = dadata._map(item, "7719402047")
    assert c["status"] == "liquidating" and c["status_text"] == "В стадии ликвидации"


async def test_lookup_without_key_is_marked_demo(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "dadata_api_key", None)
    r = await client.get("/api/v1/lookup/company?inn=7719402047", headers=await _headers(client))
    assert r.status_code == 200 and r.json()["demo"] is True


async def test_lookup_with_key_returns_real_company(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "dadata_api_key", "test-key")

    async def fake(inn: str, key: str, wait_s: float = 4.0):
        assert key == "test-key"
        return dadata._map(SAMPLE, inn) if inn == "7719402047" else None

    monkeypatch.setattr(dadata, "find_company", fake)
    h = await _headers(client)
    ok = await client.get("/api/v1/lookup/company?inn=7719402047", headers=h)
    assert ok.status_code == 200 and ok.json()["name"] == 'ООО "МОТОРИКА"' and ok.json()["demo"] is False
    missing = await client.get("/api/v1/lookup/company?inn=7700000001", headers=h)
    assert missing.status_code == 404 and missing.json()["code"] == "company_not_found"


async def test_lookup_service_unavailable(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "dadata_api_key", "test-key")

    async def boom(inn: str, key: str, wait_s: float = 4.0):
        raise dadata.LookupUnavailable("down")

    monkeypatch.setattr(dadata, "find_company", boom)
    r = await client.get("/api/v1/lookup/company?inn=7719402047", headers=await _headers(client))
    assert r.status_code == 503 and r.json()["code"] == "lookup_unavailable"
