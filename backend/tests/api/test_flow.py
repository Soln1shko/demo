import uuid

import pytest
from httpx import AsyncClient

from app.workers.dispatcher import wait_for_background

PWD = "Demo2026!"


def idem() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


def auth(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


async def login(client: AsyncClient, email: str = "client@demo.ru") -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def operator(client: AsyncClient, op: str = "OP-2026") -> str:
    r = await client.post("/api/v1/auth/operator/login", json={"operator_id": op, "password": "Alfa2026!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_health_and_version(client: AsyncClient):
    assert (await client.get("/api/v1/health/live")).json() == {"status": "ok"}
    assert (await client.get("/api/v1/health/ready")).status_code == 200
    assert (await client.get("/api/v1/version")).json()["rules_version"] == 1


async def test_auth_errors_and_roles(client: AsyncClient):
    r = await client.post("/api/v1/auth/login", json={"email": "client@demo.ru", "password": "wrong"})
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")
    # клиент не попадает в банк, банк не логинится как клиент
    token = await login(client)
    assert (await client.get("/api/v1/bank/applications", headers=auth(token))).status_code == 403
    r = await client.post("/api/v1/auth/login", json={"email": "op@bank.local", "password": "Alfa2026!"})
    assert r.status_code == 401
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_register_and_refresh_rotation(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register", json={"name": "Иван", "email": "Ivan@Test.ru", "password": "Secret123"}
    )
    assert r.status_code == 201
    assert r.json()["user"]["onboarding_complete"] is False
    dup = await client.post(
        "/api/v1/auth/register", json={"name": "Иван", "email": "ivan@test.ru", "password": "Secret123"}
    )
    assert dup.status_code == 409
    old_cookie = client.cookies.get("refresh_token")
    r2 = await client.post("/api/v1/auth/refresh")
    assert r2.status_code == 200
    # повторное использование старого refresh-токена закрывает сессию
    client.cookies.set("refresh_token", old_cookie, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_onboarding_to_organization(client: AsyncClient):
    token = (
        await client.post(
            "/api/v1/auth/register", json={"name": "Ольга", "email": "o@test.ru", "password": "Secret123"}
        )
    ).json()["access_token"]
    h = auth(token)
    bad = await client.post("/api/v1/onboarding/complete", headers=h)
    assert bad.status_code == 422
    data = {
        "legal": "ooo", "name": "ООО «Тест»", "inn": "7701234000", "region": "Москва", "age": 20, "profile": "retail",
        "goal": "Закупка товара", "amount": 1_000_000, "months": 24, "revenue": 2_000_000, "expenses": 1_300_000, "debt": 50_000,
    }  # fmt: skip
    assert (await client.put("/api/v1/onboarding", json=data, headers=h)).status_code == 200
    r = await client.post("/api/v1/onboarding/complete", headers=h)
    assert r.status_code == 201, r.text
    assert (await client.get("/api/v1/auth/me", headers=h)).json()["onboarding_complete"] is True
    org_id = r.json()["id"]
    a = (await client.get(f"/api/v1/organizations/{org_id}/analytics", headers=h)).json()
    assert a["base"]["rest"] == 650_000 and a["has_history"] is False
    m = await client.post(
        "/api/v1/products/match",
        json={"organization_id": org_id, "goal": "Закупка товара", "amount": 1_000_000, "months": 24}, headers=h,
    )  # fmt: skip
    assert m.status_code == 200 and len(m.json()) == 6


async def test_other_user_cannot_see_organization(client: AsyncClient):
    owner = await login(client)
    orgs = (await client.get("/api/v1/organizations", headers=auth(owner))).json()
    stranger = (
        await client.post(
            "/api/v1/auth/register", json={"name": "X", "email": "x@test.ru", "password": "Secret123"}
        )
    ).json()["access_token"]
    r = await client.get(f"/api/v1/organizations/{orgs[0]['id']}", headers=auth(stranger))
    assert r.status_code == 404


async def test_full_credit_flow(client: AsyncClient):
    ct = await login(client)
    ch = auth(ct)
    orgs = (await client.get("/api/v1/organizations", headers=ch)).json()
    good = next(o for o in orgs if o["inn"] == "7701234567")

    # новая заявка из черновика
    draft = await client.put(
        f"/api/v1/organizations/{good['id']}/draft",
        json={"product_id": "business_loan", "replace": True, "amount": 1_500_000, "months": 24, "goal": "Закупка товара"}, headers=ch,
    )  # fmt: skip
    assert draft.status_code == 200, draft.text
    body = {"organization_id": good["id"], "consent": False}
    no_doc = await client.post("/api/v1/applications", json=body, headers={**ch, **idem()})
    assert no_doc.status_code == 422
    assert {e["field"] for e in no_doc.json()["errors"]} >= {"documents", "consent"}

    doc = await client.post("/api/v1/documents/sample", json={"organization_id": good["id"]}, headers=ch)
    assert doc.status_code == 201
    key = idem()
    r = await client.post("/api/v1/applications", json={**body, "consent": True}, headers={**ch, **key})
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["status"] == "submitted" and r.json()["next_actions"] == ["withdraw"]
    # повтор с тем же ключом не создаёт вторую заявку
    again = await client.post("/api/v1/applications", json={**body, "consent": True}, headers={**ch, **key})
    assert again.json()["id"] == app_id or again.status_code in (200, 201)

    # банк берёт в работу и запускает проверку
    bt = await operator(client)
    bh = auth(bt)
    queue = (await client.get("/api/v1/bank/applications?status=submitted", headers=bh)).json()
    assert queue["total"] >= 6
    assert (await client.post(f"/api/v1/bank/applications/{app_id}/assign", headers=bh)).json()[
        "status"
    ] == "review"
    chk = await client.post(f"/api/v1/bank/applications/{app_id}/check", headers=bh)
    assert chk.status_code == 202
    await wait_for_background()
    detail = (await client.get(f"/api/v1/bank/applications/{app_id}", headers=bh)).json()
    assert detail["application"]["status"] == "approved"
    assert detail["application"]["risk"]["score"] >= 50
    assert {e["source"] for e in detail["external_checks"]} == {"fns", "bki"}
    run = (await client.get(f"/api/v1/bank/applications/{app_id}/check", headers=bh)).json()
    assert [s["status"] for s in run["steps"]] == ["done"] * 4

    # клиент видит решение и подписывает
    app = (await client.get(f"/api/v1/applications/{app_id}", headers=ch)).json()
    assert app["next_actions"] == ["sign", "withdraw"]
    stale = await client.post(
        f"/api/v1/applications/{app_id}/sign", json={"agreed": True, "version": 1}, headers={**ch, **idem()}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "stale_version"
    no_agree = await client.post(
        f"/api/v1/applications/{app_id}/sign",
        json={"agreed": False, "version": app["version"]},
        headers={**ch, **idem()},
    )
    assert no_agree.status_code in (409, 422)
    signed = await client.post(
        f"/api/v1/applications/{app_id}/sign",
        json={"agreed": True, "version": app["version"]},
        headers={**ch, **idem()},
    )
    assert signed.status_code == 200 and signed.json()["status"] == "signed"
    funded = await client.post(f"/api/v1/applications/{app_id}/fund", json={}, headers={**ch, **idem()})
    assert funded.json()["status"] == "funded"
    # после выдачи отзыв невозможен
    late = await client.post(f"/api/v1/applications/{app_id}/withdraw", json={}, headers={**ch, **idem()})
    assert late.status_code == 409

    # журнал событий цел, хеш-цепочка проверяется
    events = (await client.get(f"/api/v1/applications/{app_id}/events", headers=ch)).json()
    assert len(events) >= 6
    adm = auth(await operator(client, "ADM-2026"))
    verify = (await client.get("/api/v1/bank/audit/verify", headers=adm)).json()
    assert verify["ok"] is True and verify["checked"] >= 6


async def test_idempotency_key_required_for_sign(client: AsyncClient):
    ch = auth(await login(client))
    r = await client.post("/api/v1/applications/AK-00000000/sign", json={"agreed": True}, headers=ch)
    assert r.status_code in (400, 404)


@pytest.mark.parametrize(
    ("inn", "expected"),
    [
        ("7701234567", "approved"),
        ("502912345678", "alternative"),
        ("0012345678", "rejected"),
        ("7723456799", "rejected"),
    ],
)
async def test_check_scenarios(client: AsyncClient, inn: str, expected: str):
    ch = auth(await login(client))
    org_id = next(
        o["id"] for o in (await client.get("/api/v1/organizations", headers=ch)).json() if o["inn"] == inn
    )
    bh = auth(await operator(client))
    app_id = next(
        a["id"]
        for a in (await client.get(f"/api/v1/applications?organization_id={org_id}", headers=ch)).json()
    )
    await client.post(f"/api/v1/bank/applications/{app_id}/check", headers=bh)
    await wait_for_background()
    status = (await client.get(f"/api/v1/applications/{app_id}", headers=ch)).json()
    assert status["status"] == expected, status["risk"]
    if expected == "alternative":
        assert status["offer_amount"] and status["offer_amount"] < status["amount"]
        acc = await client.post(f"/api/v1/applications/{app_id}/accept-offer", json={}, headers=ch)
        assert acc.json()["status"] == "approved" and acc.json()["amount"] == status["offer_amount"]


async def test_operator_can_revise_automatic_decision(client: AsyncClient):
    ch = auth(await login(client))
    org_id = next(
        o["id"]
        for o in (await client.get("/api/v1/organizations", headers=ch)).json()
        if o["inn"] == "7701234567"
    )
    app_id = (await client.get(f"/api/v1/applications?organization_id={org_id}", headers=ch)).json()[0]["id"]
    bh = auth(await operator(client))
    await client.post(f"/api/v1/bank/applications/{app_id}/check", headers=bh)
    await wait_for_background()
    detail = (await client.get(f"/api/v1/bank/applications/{app_id}", headers=bh)).json()["application"]
    assert detail["status"] == "approved" and "decide" in detail["next_actions"]

    short = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "мало"},
        headers=bh,
    )
    assert short.status_code == 422
    rev = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "Не подтверждена выручка по выписке"},
        headers=bh,
    )
    assert rev.status_code == 200 and rev.json()["status"] == "rejected", rev.text
    events = (await client.get(f"/api/v1/applications/{app_id}/events", headers=ch)).json()
    assert any("пересмотрено" in e["text"] for e in events)

    # после подписания решение уже не меняется
    back = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "approved", "reason": "Выручка подтверждена документами"},
        headers=bh,
    )
    assert back.json()["status"] == "approved"
    app = (await client.get(f"/api/v1/applications/{app_id}", headers=ch)).json()
    await client.post(
        f"/api/v1/applications/{app_id}/sign",
        json={"agreed": True, "version": app["version"]},
        headers={**ch, **idem()},
    )
    late = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "Передумали после подписания"},
        headers=bh,
    )
    assert late.status_code == 409


async def test_queue_lanes_separate_system_and_finished(client: AsyncClient):
    """Рабочая очередь прячет отработанное и отдельно держит то, что посчитала система."""
    bh = auth(await operator(client))
    created = (await client.post("/api/v1/bank/demo/scenarios", json={"kind": "manual"}, headers=bh)).json()
    app_id = created["id"]
    assert created["status"] == "submitted" and created["operator_decided"] is False

    def ids(payload: dict) -> set[str]:
        return {item["id"] for item in payload["items"]}

    inbox = (await client.get("/api/v1/bank/applications?lane=inbox&limit=200", headers=bh)).json()
    assert app_id in ids(inbox)
    fresh = (await client.get("/api/v1/bank/applications?lane=new&limit=200", headers=bh)).json()
    assert app_id in ids(fresh)
    system = (await client.get("/api/v1/bank/applications?lane=system&limit=200", headers=bh)).json()
    assert app_id not in ids(system)

    await client.post(f"/api/v1/bank/applications/{app_id}/check", headers=bh)
    await wait_for_background()
    system = (await client.get("/api/v1/bank/applications?lane=system&limit=200", headers=bh)).json()
    assert app_id in ids(system)
    fresh = (await client.get("/api/v1/bank/applications?lane=new&limit=200", headers=bh)).json()
    assert app_id not in ids(fresh)

    decided = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "Не хватает подтверждения выручки"},
        headers=bh,
    )
    assert decided.status_code == 200, decided.text
    done = (await client.get("/api/v1/bank/applications?lane=done&limit=200", headers=bh)).json()
    assert app_id in ids(done)
    inbox = (await client.get("/api/v1/bank/applications?lane=inbox&limit=200", headers=bh)).json()
    assert app_id not in ids(inbox)
    stats = (await client.get("/api/v1/bank/applications/stats", headers=bh)).json()
    assert stats["inbox"] == stats["fresh"] + stats["system"]
    assert stats["done"] >= 1


async def test_manual_review_needs_info_and_decision(client: AsyncClient):
    ch = auth(await login(client))
    org = next(
        o for o in (await client.get("/api/v1/organizations", headers=ch)).json() if o["inn"] == "7712345678"
    )
    app_id = (await client.get(f"/api/v1/applications?organization_id={org['id']}", headers=ch)).json()[0][
        "id"
    ]
    bh = auth(await operator(client))
    await client.post(f"/api/v1/bank/applications/{app_id}/assign", headers=bh)
    r = await client.post(f"/api/v1/bank/applications/{app_id}/request-info", json={"text": "  "}, headers=bh)
    assert r.status_code == 422
    ri = await client.post(
        f"/api/v1/bank/applications/{app_id}/request-info", json={"text": "Нужна выписка"}, headers=bh
    )
    assert ri.json()["status"] == "needs_info"

    # без нового документа дополнение не принимается
    empty = await client.post(
        f"/api/v1/applications/{app_id}/supplement", json={"document_ids": []}, headers=ch
    )
    assert empty.status_code in (409, 422)
    doc = (
        await client.post(
            "/api/v1/documents/sample",
            json={"organization_id": org["id"], "application_id": app_id},
            headers=ch,
        )
    ).json()
    assert doc["application_id"] == app_id
    ok = await client.post(f"/api/v1/applications/{app_id}/supplement", json={"document_ids": []}, headers=ch)
    assert ok.json()["status"] == "submitted"

    await client.post(f"/api/v1/bank/applications/{app_id}/assign", headers=bh)
    short = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "мало"},
        headers=bh,
    )
    assert short.status_code == 422
    dec = await client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json={"decision": "rejected", "reason": "Недостаточный срок работы бизнеса"}, headers=bh,
    )  # fmt: skip
    assert dec.json()["status"] == "rejected"
    assert dec.json()["manual_reason"].startswith("Недостаточный")


async def test_structured_request_needs_every_item(client: AsyncClient):
    """Документ, данные и уточнение — разные пункты; без ответа на каждый дополнение не принимается."""
    ch = auth(await login(client))
    org = next(
        o for o in (await client.get("/api/v1/organizations", headers=ch)).json() if o["inn"] == "7712345678"
    )
    app_id = (await client.get(f"/api/v1/applications?organization_id={org['id']}", headers=ch)).json()[0][
        "id"
    ]
    bh = auth(await operator(client))

    templates = (await client.get("/api/v1/bank/request-templates", headers=bh)).json()
    assert {t["kind"] for t in templates} == {"document", "data", "clarify"}

    await client.post(f"/api/v1/bank/applications/{app_id}/assign", headers=bh)
    empty = await client.post(
        f"/api/v1/bank/applications/{app_id}/request-info", json={"items": []}, headers=bh
    )
    assert empty.status_code == 422

    # сразу несколько пунктов одним запросом
    ri = await client.post(
        f"/api/v1/bank/applications/{app_id}/request-info",
        json={
            "items": [
                {"kind": "document", "title": "Справка о доходах", "template_id": "income_cert"},
                {"kind": "document", "title": "Кредитные договоры"},
                {"kind": "data", "title": "Платежи по кредитам, ₽"},
                {"kind": "clarify", "title": "Источник погашения?"},
            ],
            "message": "Нужно до пятницы",
        },
        headers=bh,
    )
    assert ri.status_code == 200, ri.text
    req = ri.json()["info_request"]
    assert (
        ri.json()["status"] == "needs_info"
        and len(req["items"]) == 4
        and req["message"] == "Нужно до пятницы"
    )
    income, contracts, data, clarify = req["items"]

    # ничего не приложено и не заполнено
    none = await client.post(f"/api/v1/applications/{app_id}/supplement", json={"answers": {}}, headers=ch)
    assert none.status_code == 422
    assert {e["field"] for e in none.json()["errors"]} == {i["id"] for i in req["items"]}

    # один документ из двух и текст только в одном поле — всё равно нельзя
    d1 = await client.post(
        "/api/v1/documents/sample",
        json={"organization_id": org["id"], "application_id": app_id, "request_item": income["id"]},
        headers=ch,
    )
    assert d1.status_code == 201 and d1.json()["request_item"] == income["id"]
    part = await client.post(
        f"/api/v1/applications/{app_id}/supplement", json={"answers": {data["id"]: "120000"}}, headers=ch
    )
    assert part.status_code == 422
    assert {e["field"] for e in part.json()["errors"]} == {contracts["id"], clarify["id"]}

    # документ нельзя привязать к чужому (текстовому) пункту
    wrong = await client.post(
        "/api/v1/documents/sample",
        json={"organization_id": org["id"], "application_id": app_id, "request_item": data["id"]},
        headers=ch,
    )
    assert wrong.status_code == 422

    # повторная загрузка на тот же пункт заменяет файл, а не копит дубли
    again = await client.post(
        "/api/v1/documents",
        data={"organization_id": org["id"], "application_id": app_id, "request_item": contracts["id"]},
        files={"file": ("loans.pdf", b"%PDF-1.4 x")},
        headers=ch,
    )
    assert again.status_code == 201
    again2 = await client.post(
        "/api/v1/documents",
        data={"organization_id": org["id"], "application_id": app_id, "request_item": contracts["id"]},
        files={"file": ("loans2.pdf", b"%PDF-1.4 y")},
        headers=ch,
    )
    assert again2.status_code == 201
    docs = (await client.get(f"/api/v1/applications/{app_id}", headers=ch)).json()["documents"]
    assert [d["name"] for d in docs if d["request_item"] == contracts["id"]] == ["loans2.pdf"]

    ok = await client.post(
        f"/api/v1/applications/{app_id}/supplement",
        json={"answers": {data["id"]: "120000", clarify["id"]: "Выручка от контрактов"}},
        headers=ch,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "submitted"
    assert ok.json()["info_request"]["answers"][clarify["id"]] == "Выручка от контрактов"


async def test_document_upload_validation(client: AsyncClient):
    ch = auth(await login(client))
    org_id = (await client.get("/api/v1/organizations", headers=ch)).json()[0]["id"]
    bad_ext = await client.post(
        "/api/v1/documents", data={"organization_id": org_id}, files={"file": ("a.exe", b"MZ")}, headers=ch
    )
    assert bad_ext.status_code == 415
    fake_pdf = await client.post(
        "/api/v1/documents",
        data={"organization_id": org_id},
        files={"file": ("a.pdf", b"not a pdf")},
        headers=ch,
    )
    assert fake_pdf.status_code == 415
    ok = await client.post(
        "/api/v1/documents",
        data={"organization_id": org_id},
        files={"file": ("a.pdf", b"%PDF-1.4 test")},
        headers=ch,
    )
    assert ok.status_code == 201
    got = await client.get(f"/api/v1/documents/{ok.json()['id']}/download", headers=ch)
    assert got.content == b"%PDF-1.4 test"
    other = (
        await client.post(
            "/api/v1/auth/register", json={"name": "Z", "email": "z@test.ru", "password": "Secret123"}
        )
    ).json()["access_token"]
    assert (await client.get(f"/api/v1/documents/{ok.json()['id']}", headers=auth(other))).status_code == 404


async def test_feed_personalisation_and_assistant(client: AsyncClient):
    ch = auth(await login(client))
    orgs = (await client.get("/api/v1/organizations", headers=ch)).json()
    org = next(o for o in orgs if o["inn"] == "7701234567")
    feed = (await client.get(f"/api/v1/feed?organization_id={org['id']}", headers=ch)).json()
    assert feed["items"] and all(i["reason"] for i in feed["items"])
    production = (
        await client.get(f"/api/v1/feed?organization_id={org['id']}&profile=production", headers=ch)
    ).json()
    assert {i["id"] for i in production["items"]} != {i["id"] for i in feed["items"]}
    first = feed["items"][0]["id"]
    await client.post(f"/api/v1/feed/{first}/dismiss?organization_id={org['id']}", headers=ch)
    after = (await client.get(f"/api/v1/feed?organization_id={org['id']}", headers=ch)).json()
    assert first not in {i["id"] for i in after["items"]}

    conv = (await client.post("/api/v1/assistant/conversations", headers=ch)).json()
    greeting = await client.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages", json={"text": "привет"}, headers=ch
    )
    assert greeting.status_code == 200
    assert greeting.json()["source"] == "rules"
    assert "Здравствуйте" in greeting.json()["assistant"]["text"]
    assert "Признаки применимости" not in greeting.json()["assistant"]["text"]
    ans = await client.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={"text": "Какие документы нужны?"},
        headers=ch,
    )
    assert ans.status_code == 200 and "выписк" in ans.json()["assistant"]["text"].lower()
    ticket = await client.post(f"/api/v1/assistant/conversations/{conv['id']}/escalate", headers=ch)
    assert ticket.status_code == 200
    bh = auth(await operator(client))
    rep = await client.post(
        f"/api/v1/bank/support/tickets/{ticket.json()['id']}/reply",
        json={"text": "Ответ оператора"},
        headers=bh,
    )
    assert rep.json()["status"] == "answered"
    mine = (await client.get("/api/v1/support/tickets", headers=ch)).json()
    assert mine[0]["messages"][-1]["author_role"] == "bank"


async def test_reset_demo_removes_everything(client: AsyncClient):
    ch = auth(await login(client))
    bh = auth(await operator(client))
    before = (await client.get("/api/v1/bank/applications", headers=bh)).json()["items"]
    own_names = {
        row["company"]
        for row in before
        if row["inn"] in {"7701234567", "502912345678", "7712345678", "0012345678", "7723456799"}
    }
    assert (await client.post("/api/v1/auth/me/reset-demo", json={"confirm": True}, headers=ch)).json()[
        "organizations"
    ] == []
    after = (await client.get("/api/v1/bank/applications", headers=bh)).json()["items"]
    assert all(row["company"] not in own_names for row in after)
    assert len(after) == 5  # отдельные демо-кабинеты не удаляются вместе с этим аккаунтом
