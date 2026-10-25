"""Пять отдельных демо-кабинетов и денежная история для сценариев."""

import pytest
from httpx import AsyncClient

from app.integrations import ml
from app.models import Organization
from app.services.ml_bridge import cash_gap_body, finance_history


@pytest.mark.asyncio
async def test_five_demo_accounts_have_distinct_organizations(client: AsyncClient) -> None:
    profiles = []
    for i in range(1, 6):
        login = await client.post(
            "/api/v1/auth/login", json={"email": f"demo{i}@demo.ru", "password": "Demo2026!"}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        orgs = me.json()["organizations"]
        assert len(orgs) == 1
        profiles.append(orgs[0])
    assert len({org["id"] for org in profiles}) == 5
    assert len({org["revenue"] for org in profiles}) == 5
    assert len({org["goal"] for org in profiles}) >= 4


@pytest.mark.asyncio
async def test_swagger_is_reachable_through_frontend_proxy_path(client: AsyncClient) -> None:
    spec = await client.get("/api/v1/openapi.json")
    docs = await client.get("/api/v1/docs")
    assert spec.status_code == docs.status_code == 200
    assert "/api/v1/ml/score/weights" in spec.json()["paths"]


def test_history_ends_at_current_balance() -> None:
    org = Organization(
        name="ООО Демо",
        inn="0000000000",
        legal="ooo",
        profile="retail",
        region="Демо",
        age=12,
        revenue=1_000_000,
        expenses=800_000,
        debt=50_000,
        cash_balance=90_000,
    )
    history = finance_history([], org)
    assert len(history) == 6
    assert history[-1]["cash_balance"] == 90_000
    cash_profile = cash_gap_body(org)
    assert cash_profile["monthly_fixed_costs"] == 50_000
    assert (
        round(cash_profile["monthly_revenue"] * cash_profile["net_margin_percent"] / 100)
        - cash_profile["monthly_fixed_costs"]
        == 150_000
    )


def test_cash_gap_includes_negative_margin_once() -> None:
    org = Organization(
        name="ООО Демо",
        inn="0000000004",
        legal="ooo",
        profile="services",
        region="Демо",
        age=12,
        revenue=500_000,
        expenses=620_000,
        debt=180_000,
        cash_balance=20_000,
    )
    cash_profile = cash_gap_body(org)
    assert cash_profile["net_margin_percent"] == 0
    assert cash_profile["monthly_fixed_costs"] == 300_000


@pytest.mark.asyncio
async def test_quote_uses_edited_business_data_without_rescoring(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unexpected_score(_: dict) -> None:
        raise AssertionError("quote must not call scoring on slider changes")

    monkeypatch.setattr(ml, "score", unexpected_score)
    login = await client.post("/api/v1/auth/login", json={"email": "demo1@demo.ru", "password": "Demo2026!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["organizations"][0]["id"]
    base = {
        "organization_id": org_id,
        "amount": 1_500_000,
        "months": 24,
        "monthly_revenue": 2_400_000,
        "net_margin_percent": 25,
        "stress_pct": 0,
    }
    first = await client.post("/api/v1/products/business_loan/quote", json=base, headers=headers)
    second = await client.post(
        "/api/v1/products/business_loan/quote",
        json={**base, "monthly_revenue": 1_600_000, "stress_pct": -20},
        headers=headers,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["rest_at_peak"] > second.json()["rest_at_peak"]
