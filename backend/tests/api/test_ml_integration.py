"""Проверка, что кабинет показывает именно ответы ML-сервисов."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.core import cache
from app.integrations import ml


async def _client_auth(client: AsyncClient) -> tuple[dict[str, str], str]:
    login = await client.post("/api/v1/auth/login", json={"email": "client@demo.ru", "password": "Demo2026!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return {"Authorization": f"Bearer {token}"}, me.json()["organizations"][0]["id"]


@pytest.mark.asyncio
async def test_empty_ml_recommendations_stay_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def empty_nba(_: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def empty_advisor(_: dict[str, Any]) -> dict[str, Any]:
        return {"recommendations": [], "excluded_product_ids": ["business_loan"], "model": None}

    monkeypatch.setattr(ml, "nba", empty_nba)
    monkeypatch.setattr(ml, "advise", empty_advisor)
    cache._memory.clear()
    headers, org_id = await _client_auth(client)

    banners = await client.get("/api/v1/ml/banners", params={"organization_id": org_id}, headers=headers)
    assert banners.status_code == 200, banners.text
    assert banners.json() == []

    advisor = await client.get("/api/v1/ml/advisor", params={"organization_id": org_id}, headers=headers)
    assert advisor.status_code == 200, advisor.text
    assert advisor.json()["recommendations"] == []
    assert advisor.json()["excluded_product_ids"] == ["business_loan"]


@pytest.mark.asyncio
async def test_ml_unavailable_is_not_silently_replaced(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unavailable(_: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(ml, "nba", unavailable)
    monkeypatch.setattr(ml, "advise", unavailable)
    cache._memory.clear()
    headers, org_id = await _client_auth(client)

    for path in ("banners", "advisor"):
        response = await client.get(f"/api/v1/ml/{path}", params={"organization_id": org_id}, headers=headers)
        assert response.status_code == 503, response.text


@pytest.mark.asyncio
async def test_advisor_marks_catalog_only_product_without_calculator(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def advisor(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "recommendations": [
                {
                    "product_id": "business_refinancing",
                    "reason": "Высокая вероятность одобрения",
                    "reasons": ["Сумма и срок подходят предварительно."],
                    "rank": 1,
                }
            ],
            "excluded_product_ids": [],
            "model": "test",
        }

    monkeypatch.setattr(ml, "advise", advisor)
    cache._memory.clear()
    headers, org_id = await _client_auth(client)
    response = await client.get("/api/v1/ml/advisor", params={"organization_id": org_id}, headers=headers)
    assert response.status_code == 200, response.text
    item = response.json()["recommendations"][0]
    assert item["product_id"] == "business_refinancing"
    assert item["calculable"] is False
    assert item["source_url"].startswith("https://alfabank.ru/")
    assert item["reason"] == "Сумма и срок подходят предварительно."


@pytest.mark.asyncio
async def test_advisor_recalculates_when_purpose_changes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    purposes: list[str] = []

    async def advisor(payload: dict[str, Any]) -> dict[str, Any]:
        purposes.append(payload["purpose"])
        return {"recommendations": [], "excluded_product_ids": [], "model": payload["purpose"]}

    monkeypatch.setattr(ml, "advise", advisor)
    cache._memory.clear()
    headers, org_id = await _client_auth(client)
    answers = []
    for purpose in ("equipment", "working_capital"):
        response = await client.post(
            "/api/v1/ml/advisor", json={"organization_id": org_id, "purpose": purpose}, headers=headers
        )
        assert response.status_code == 200, response.text
        answers.append(response.json()["model"])
    assert answers == ["equipment", "working_capital"]
    assert purposes == answers


@pytest.mark.asyncio
async def test_quest_recalculate_reports_ml_failure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unavailable(_: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(ml, "quest_generate", unavailable)
    headers, org_id = await _client_auth(client)
    response = await client.post(
        "/api/v1/ml/quest/recalculate", json={"organization_id": org_id, "plan_index": 0}, headers=headers
    )
    assert response.status_code == 503, response.text


@pytest.mark.asyncio
async def test_refusal_draft_is_only_for_refusal(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/operator/login", json={"operator_id": "OP-2026", "password": "Alfa2026!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/v1/ml/applications/DEMO-UNKNOWN/explain", json={"decision": "approved"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refusal_draft_sends_only_ml_scoring_fields(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login = await client.post(
        "/api/v1/auth/operator/login", json={"operator_id": "OP-2026", "password": "Alfa2026!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    applications = (await client.get("/api/v1/bank/applications", headers=headers)).json()["items"]
    app_id = applications[0]["id"]
    seen: dict[str, Any] = {}

    async def score(_: dict[str, Any]) -> dict[str, Any]:
        return {"risk_probability": 0.4, "risk_band": "medium", "factors": [], "model_version": "test"}

    async def underwrite(_: dict[str, Any]) -> dict[str, Any]:
        return {"risks": [{"text": "Проверенный риск"}], "overall_assessment": {"summary": "Тест"}}

    async def explain(payload: dict[str, Any]) -> dict[str, str]:
        seen.update(payload)
        return {"message": "Причина отказа"}

    monkeypatch.setattr(ml, "score", score)
    monkeypatch.setattr(ml, "underwrite", underwrite)
    monkeypatch.setattr(ml, "explain_refusal", explain)
    response = await client.post(
        f"/api/v1/ml/applications/{app_id}/explain", json={"decision": "declined"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert set(seen["scoring"]) == {"risk_probability", "risk_band", "factors", "model_version"}


@pytest.mark.asyncio
async def test_refusal_draft_requires_confirmed_risk(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    login = await client.post(
        "/api/v1/auth/operator/login", json={"operator_id": "OP-2026", "password": "Alfa2026!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    app_id = (await client.get("/api/v1/bank/applications", headers=headers)).json()["items"][0]["id"]

    async def score(_: dict[str, Any]) -> dict[str, Any]:
        return {"risk_probability": 0.4, "risk_band": "medium", "factors": [], "model_version": "test"}

    async def underwrite(_: dict[str, Any]) -> dict[str, Any]:
        return {"risks": [], "overall_assessment": {"summary": "Рисков нет"}}

    monkeypatch.setattr(ml, "score", score)
    monkeypatch.setattr(ml, "underwrite", underwrite)
    response = await client.post(
        f"/api/v1/ml/applications/{app_id}/explain", json={"decision": "declined"}, headers=headers
    )
    assert response.status_code == 422
