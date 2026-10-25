"""Прокси к ML для кабинета: баннеры, подбор, скоринг, резюме, альтернатива, обоснование."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core import cache
from app.core.deps import Bank, Client, CurrentUser, Session, get_user_org
from app.core.errors import ApiError
from app.integrations import ml
from app.models import (
    Application,
    BankProduct,
    Document,
    ExternalCheck,
    Organization,
    RiskAssessment,
    SupportMessage,
    SupportTicket,
)
from app.services import applications as apps
from app.services import catalog
from app.services import documents as docs
from app.services import ml_bridge as bridge
from app.services import organizations as orgs

router = APIRouter(prefix="/ml", tags=["ml"])


class AdvisorIn(BaseModel):
    organization_id: str
    requested_amount: int | None = Field(None, gt=0)
    term_months: int | None = Field(None, gt=0)
    purpose: str | None = None


class ScoreIn(BaseModel):
    organization_id: str
    product_id: str
    amount: float = Field(gt=0)
    months: int = Field(gt=0)
    monthly_revenue: float | None = None
    net_margin_percent: float | None = None
    debt_to_revenue_ratio: float | None = None
    has_overdue_debt: bool | None = None
    credit_history_score: int | None = Field(None, ge=0, le=1000)
    has_collateral: bool | None = None
    legal_form: str | None = None
    business_age_months: int | None = None


class RecoveryIn(BaseModel):
    switch_product: bool = False


class ExplainIn(BaseModel):
    decision: str = "declined"


class QuestRecalcIn(BaseModel):
    organization_id: str
    plan_index: int = Field(0, ge=0, le=2)


class CopilotIn(BaseModel):
    ticket_id: str


ART = ("cards", "flow", "steps")
ADVISOR_TTL = 45 * 60


@router.get("/banners")
async def banners(
    organization_id: str, user: CurrentUser, session: Session, bg: BackgroundTasks
) -> list[dict[str, Any]]:
    org = await get_user_org(session, user, organization_id)
    bg.add_task(_warm_advisor, org.id)
    bg.add_task(_warm_cash_gap, org.id)
    items = await ml.nba(bridge.nba_body(org))
    if items is None:
        raise ApiError(503, "ml_unavailable", "Рекомендации сервисов сейчас недоступны")
    names = {row.id: row for row in (await session.execute(select(BankProduct))).scalars()}
    out: list[dict[str, Any]] = []
    for item in items:
        product = names.get(item.get("product_id", ""))
        if product is None:
            continue
        out.append(
            {
                "product_id": item.get("product_id"),
                "tag": "Для вашего бизнеса",
                "title": product.name,
                "text": item.get("reason") or "",
                "url": (
                    product.source_url
                    if str(product.source_url).startswith("http")
                    else "https://alfabank.ru/sme/"
                ),
                "art": ART[len(out) % 3],
                "score": item.get("score"),
            }
        )
        if len(out) == 3:
            break
    return out


@router.get("/advisor")
async def advisor_get(
    organization_id: str,
    user: Client,
    session: Session,
    requested_amount: int | None = None,
    term_months: int | None = None,
) -> dict[str, Any]:
    org = await get_user_org(session, user, organization_id)
    extra: dict[str, Any] = {}
    if requested_amount:
        extra["requested_amount"] = requested_amount
    if term_months:
        extra["term_months"] = term_months
    return await _advisor_payload(session, org, extra)


@router.get("/cash-gap")
async def cash_gap(organization_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, organization_id)
    data = await _cash_gap_payload(org)
    if data is None:
        raise ApiError(503, "ml_unavailable", "Прогноз кассового разрыва сейчас недоступен")
    return data


@router.get("/twin")
async def twin(organization_id: str, user: Client, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, organization_id)
    data = await _twin_payload(org, session)
    if data is None:
        raise ApiError(503, "ml_unavailable", "Финансовый двойник сейчас недоступен")
    return data


@router.get("/quest")
async def quest(organization_id: str, user: Client, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, organization_id)
    data = await _quest_payload(org, session)
    if data is None:
        raise ApiError(503, "ml_unavailable", "Сценарии улучшения заявки сейчас недоступны")
    return data


@router.post("/quest/recalculate")
async def quest_recalc(body: QuestRecalcIn, user: Client, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, body.organization_id)
    rows = await orgs.finance_rows(session, org.id)
    request = bridge.quest_request(org, rows)
    generated = await ml.quest_generate(request)
    if generated is None:
        raise ApiError(503, "ml_unavailable", "Сценарии улучшения заявки сейчас недоступны")
    plans = (generated or {}).get("plans") or []
    if body.plan_index >= len(plans):
        raise ApiError(404, "not_found", "Такого плана нет")
    result = await ml.quest_recalculate({**request, "actions": plans[body.plan_index].get("actions") or []})
    if result is None:
        raise ApiError(503, "ml_unavailable", "Пересчёт сценария сейчас недоступен")
    plan = result.get("plan") or plans[body.plan_index]
    return {
        "baseline_score": generated.get("baseline_score") if generated else None,
        "plan": plan,
        "simulation": bridge.compact_simulation(result.get("simulation")),
    }


@router.post("/parse")
async def parse_docs(organization_id: str, user: Client, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, organization_id)
    rows = list(
        (
            await session.execute(
                select(Document)
                .where(Document.organization_id == org.id)
                .order_by(Document.created_at.desc())
            )
        ).scalars()
    )
    uploads: list[tuple[str, bytes, str]] = []
    for doc in rows:
        if len(uploads) >= 8:
            break
        if doc.kind == "sample":
            continue
        content, mime = await docs.read_content(doc, org)
        if not content:
            continue
        uploads.append((doc.name or f"{doc.id}.bin", content, mime or "application/octet-stream"))
    if not uploads:
        raise ApiError(422, "no_documents", "Загрузите PDF, JPG или PNG — образцы распознать нельзя")
    data = await ml.parse_documents(bridge.case_id(org.id), uploads)
    if data is None:
        raise ApiError(503, "ml_unavailable", "Распознавание документов сейчас недоступно")
    return data


@router.post("/copilot")
async def copilot_reply(body: CopilotIn, user: Bank, session: Session) -> dict[str, Any]:
    ticket = await session.get(SupportTicket, body.ticket_id)
    if ticket is None:
        raise ApiError(404, "not_found", "Обращение не найдено")
    org = await session.get(Organization, ticket.organization_id)
    app = await session.get(Application, ticket.application_id) if ticket.application_id else None
    messages = list(
        (
            await session.execute(
                select(SupportMessage)
                .where(SupportMessage.ticket_id == ticket.id)
                .order_by(SupportMessage.id)
            )
        ).scalars()
    )
    data = await ml.copilot(bridge.copilot_body(ticket.id, ticket.question, messages, org, app))
    if data is None:
        raise ApiError(503, "ml_unavailable", "Черновик ответа сейчас недоступен")
    return data


@router.post("/advisor")
async def advisor(body: AdvisorIn, user: Client, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, body.organization_id)
    extra: dict[str, Any] = {}
    if body.requested_amount:
        extra["requested_amount"] = body.requested_amount
    if body.term_months:
        extra["term_months"] = body.term_months
    if body.purpose:
        extra["purpose"] = body.purpose
    return await _advisor_payload(session, org, extra)


@router.post("/score")
async def score(body: ScoreIn, user: CurrentUser, session: Session) -> dict[str, Any]:
    org = await get_user_org(session, user, body.organization_id)
    extra = {
        k: v
        for k, v in body.model_dump().items()
        if v is not None and k not in {"organization_id", "product_id", "amount", "months"}
    }
    scored = await bridge.live_score(body.product_id, body.amount, body.months, org, extra)
    if scored is None:
        raise ApiError(503, "ml_unavailable", "Оценка модели сейчас недоступна")
    return scored


@router.get("/score/weights")
async def score_weights(user: CurrentUser) -> dict[str, Any]:
    del user
    data = await ml.score_weights()
    if data is None:
        raise ApiError(503, "ml_unavailable", "Оценка сейчас недоступна")
    return data


@router.get("/applications/{app_id}/brief")
async def brief(app_id: str, user: Bank, session: Session) -> dict[str, Any]:
    app = await apps.get_app(session, app_id)
    scoring = await _stored_or_live(session, app)
    if scoring is None:
        raise ApiError(503, "ml_unavailable", "Резюме модели сейчас недоступно")
    checks = list(
        (await session.execute(select(ExternalCheck).where(ExternalCheck.application_id == app_id))).scalars()
    )
    text = await ml.underwrite(bridge.underwriting_request(app, scoring, checks))
    complexity, priority = scoring.get("complexity"), scoring.get("priority")
    if text is None:
        return {
            "overall_assessment": {"level": "mixed", "summary": _fallback_summary(app, scoring)},
            "risks": [],
            "strengths": [],
            "decision_complexity": {
                "level": complexity or "medium",
                "reason": "Локальная оценка по скорингу",
            },
            "analyst_priority": {"level": priority or "medium", "reason": "Отношение суммы к выручке"},
            "approval_pct": scoring.get("approval_pct"),
            "model": None,
        }
    return {**text, "approval_pct": scoring.get("approval_pct")}


@router.post("/applications/{app_id}/recovery")
async def recovery(
    app_id: str, user: Bank, session: Session, body: RecoveryIn | None = None
) -> dict[str, Any]:
    app = await apps.get_app(session, app_id)
    org = await session.get(Organization, app.organization_id)
    if org is None:
        raise ApiError(404, "not_found", "Организация не найдена")
    spec = catalog.spec_from_snapshot(app.product_snapshot)
    current = await bridge.live_score(app.product_id, app.amount, app.months, org)
    target = await bridge.amount_for_approval(
        app.product_id, org, app.months, int(spec.min_amount), int(spec.max_amount)
    )
    products: list[dict[str, Any]] = []
    catalog_rows = {p.id: p for p in await catalog.list_products(session)}
    if body and body.switch_product:
        advice = await ml.advise(
            bridge.advisor_body(org, {"requested_amount": int(app.amount), "term_months": app.months})
        )
        for item in (advice or {}).get("recommendations") or []:
            if item.get("product_id") == app.product_id:
                continue
            product = catalog_rows.get(item.get("product_id", ""))
            if product is None or not product.calculable:
                continue
            found = await bridge.amount_for_approval(
                product.id,
                org,
                min(app.months, product.max_months),
                int(product.min_amount),
                int(product.max_amount),
            )
            products.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "reason": item.get("reason"),
                    "amount": found[0] if found else int(product.min_amount),
                    "months": min(app.months, product.max_months),
                    "approval_pct": found[1] if found else None,
                    "min_amount": int(product.min_amount),
                    "max_amount": int(product.max_amount),
                }
            )
            if len(products) >= 2:
                break
    ids = [app.product_id, *[p.id for p in catalog_rows.values() if p.calculable]]
    recovered = await ml.recover(bridge.recovery_body(app, org, list(dict.fromkeys(ids))))
    variants = []
    for item in (recovered or {}).get("variants") or []:
        terms = item.get("suggested_terms") or {}
        product = catalog_rows.get(item.get("product_id", ""))
        variants.append(
            {
                "product_id": item.get("product_id"),
                "name": product.name if product else item.get("product_id"),
                "amount": terms.get("amount"),
                "months": terms.get("term_months"),
                "approval_pct": bridge.approval_pct(item),
                "explanation": item.get("explanation"),
            }
        )
    suggested_amount = target[0] if target else int(app.amount)
    suggested_pct = target[1] if target else (current or {}).get("approval_pct")
    if variants and not (body and body.switch_product):
        first = variants[0]
        if first.get("amount") is not None:
            suggested_amount = int(first["amount"])
            if first.get("approval_pct") is not None:
                suggested_pct = first["approval_pct"]
    return {
        "current_approval_pct": (current or {}).get("approval_pct"),
        "suggested_amount": suggested_amount,
        "suggested_approval_pct": suggested_pct,
        "products": products,
        "variants": variants,
    }


@router.post("/applications/{app_id}/explain")
async def explain(app_id: str, user: Bank, session: Session, body: ExplainIn | None = None) -> dict[str, str]:
    if body is not None and body.decision != "declined":
        raise ApiError(422, "unsupported_decision", "Черновик причины доступен только для отказа")
    app = await apps.get_app(session, app_id)
    scoring = await _stored_or_live(session, app)
    if scoring is None:
        raise ApiError(503, "ml_unavailable", "Обоснование модели сейчас недоступно")
    checks = list(
        (await session.execute(select(ExternalCheck).where(ExternalCheck.application_id == app_id))).scalars()
    )
    underwriting_input = bridge.underwriting_request(app, scoring, checks)
    uw = await ml.underwrite(underwriting_input)
    if uw is None:
        raise ApiError(503, "ml_unavailable", "Сначала нужна сводка заявки")
    risks = [item.get("text") for item in (uw.get("risks") or []) if item.get("text")]
    if not risks:
        raise ApiError(422, "no_confirmed_risks", "В резюме нет подтверждённых рисков для черновика отказа")
    text = await ml.explain_refusal(
        {"decision": "declined", "underwriting": uw, "scoring": underwriting_input["scoring"]}
    )
    if text and text.get("message"):
        return {"message": text["message"]}
    summary = uw.get("overall_assessment", {}).get("summary") or _fallback_summary(app, scoring)
    message = summary if not risks else f"{summary} Обратите внимание: {'; '.join(risks[:2])}."
    return {"message": message[:500]}


@router.post("/applications/{app_id}/score")
async def application_score(
    app_id: str, user: Bank, session: Session, amount: float | None = None, product_id: str | None = None
) -> dict[str, Any]:
    app = await apps.get_app(session, app_id)
    org = await session.get(Organization, app.organization_id)
    if org is None:
        raise ApiError(404, "not_found", "Организация не найдена")
    scored = await bridge.live_score(product_id or app.product_id, amount or app.amount, app.months, org)
    if scored is None:
        raise ApiError(503, "ml_unavailable", "Оценка модели сейчас недоступна")
    return scored


async def _stored_or_live(session: Session, app: Application) -> dict[str, Any] | None:
    row = (
        (
            await session.execute(
                select(RiskAssessment)
                .where(RiskAssessment.application_id == app.id)
                .order_by(RiskAssessment.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    stored = (row.inputs or {}).get("ml") if row else None
    if isinstance(stored, dict) and "risk_probability" in stored:
        return stored
    org = await session.get(Organization, app.organization_id)
    if org is None:
        return None
    return await bridge.live_score(app.product_id, app.amount, app.months, org)


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def _advisor_payload(session: Session, org: Organization, extra: dict[str, Any]) -> dict[str, Any]:
    key = f"ml:advisor:v3:{org.id}"
    request = bridge.advisor_body(org, extra)
    fingerprint = _fingerprint(request)
    cached = await cache.get_json(key)
    if isinstance(cached, dict) and cached.get("fp") == fingerprint and isinstance(cached.get("data"), dict):
        return cached["data"]
    advice = await ml.advise(request)
    if advice is None:
        raise ApiError(503, "ml_unavailable", "Подбор кредитных продуктов сейчас недоступен")
    catalog_rows = {p.id: p for p in await catalog.list_products(session)}
    recommendations = []
    for item in advice.get("recommendations") or []:
        product = catalog_rows.get(item.get("product_id"))
        if product is None:
            continue
        source = str(product.source_url or "")
        verified_reasons = [reason for reason in item.get("reasons") or [] if isinstance(reason, str)]
        recommendations.append(
            {
                **item,
                "reason": " ".join(verified_reasons[:2]) if verified_reasons else item.get("reason", ""),
                "name": product.name,
                "short": product.short,
                "category": product.category,
                "icon": product.icon,
                "calculable": product.calculable,
                "source_url": source
                if source.startswith("http")
                else f"https://alfabank.ru/sme/profits/{source.lstrip('/')}",
            }
        )
    payload = {
        "recommendations": recommendations,
        "excluded_product_ids": advice.get("excluded_product_ids") or [],
        "model": advice.get("model"),
    }
    await cache.set_json(key, {"fp": fingerprint, "data": payload}, ADVISOR_TTL)
    return payload


async def _warm_advisor(org_id: str) -> None:
    from app.db.session import session_factory

    async with session_factory()() as session:
        org = await session.get(Organization, org_id)
        if org is not None:
            try:
                await _advisor_payload(session, org, {})
            except ApiError:
                pass  # Прогрев необязателен: ошибка появится при явном открытии советника.


async def _cash_gap_payload(org: Organization) -> dict[str, Any] | None:
    key = f"ml:cashgap:v2:{org.id}"
    request = bridge.cash_gap_body(org)
    fingerprint = _fingerprint(request)
    cached = await cache.get_json(key)
    if isinstance(cached, dict) and cached.get("fp") == fingerprint and isinstance(cached.get("data"), dict):
        return cached["data"]
    raw = await ml.cash_gap(request)
    if raw is None:
        return None
    payload = {
        "probability_pct": max(0, min(100, round(float(raw.get("cash_gap_probability") or 0) * 100))),
        "risk_band": raw.get("risk_band") or "умеренный",
        "estimated_shortfall": int(raw.get("estimated_shortfall") or 0),
        "forecast_days": int(raw.get("forecast_days") or 30),
        "factors": list(raw.get("factors") or [])[:3],
    }
    await cache.set_json(key, {"fp": fingerprint, "data": payload}, ADVISOR_TTL)
    return payload


async def _twin_payload(org: Organization, session: Session) -> dict[str, Any] | None:
    key = f"ml:twin:v2:{org.id}"
    rows = await orgs.finance_rows(session, org.id)
    request = bridge.forecast_request(org, rows)
    loan = bridge.loan_of(org)
    fingerprint = _fingerprint({"forecast": request, "loan": loan})
    cached = await cache.get_json(key)
    if isinstance(cached, dict) and cached.get("fp") == fingerprint and isinstance(cached.get("data"), dict):
        return cached["data"]
    forecasted = await ml.forecast(request)
    if forecasted is None:
        return None
    without_loan = await ml.simulate({"forecast": forecasted})
    with_loan = await ml.simulate({"forecast": forecasted, "loan": loan})
    if without_loan is None or with_loan is None:
        return None
    payload = {
        "without_loan": bridge.compact_simulation(without_loan),
        "with_loan": bridge.compact_simulation(with_loan),
        "horizon_months": request["horizon_months"],
        "synthetic": True,
    }
    await cache.set_json(key, {"fp": fingerprint, "data": payload}, ADVISOR_TTL)
    return payload


async def _quest_payload(org: Organization, session: Session) -> dict[str, Any] | None:
    key = f"ml:quest:{org.id}"
    rows = await orgs.finance_rows(session, org.id)
    request = bridge.quest_request(org, rows)
    fingerprint = _fingerprint(request)
    cached = await cache.get_json(key)
    if isinstance(cached, dict) and cached.get("fp") == fingerprint and isinstance(cached.get("data"), dict):
        return cached["data"]
    raw = await ml.quest_generate(request)
    if raw is None:
        return None
    payload = {
        "baseline_score": raw.get("baseline_score"),
        "target_score": raw.get("target_score"),
        "plans": raw.get("plans") or [],
        "synthetic": True,
    }
    await cache.set_json(key, {"fp": fingerprint, "data": payload}, ADVISOR_TTL)
    return payload


async def _warm_cash_gap(org_id: str) -> None:
    from app.db.session import session_factory

    async with session_factory()() as session:
        org = await session.get(Organization, org_id)
        if org is not None:
            await _cash_gap_payload(org)


def _fallback_summary(app: Application, scoring: dict[str, Any]) -> str:
    pct = scoring.get("approval_pct")
    return f"{app.company} просит {int(app.amount):,} ₽ на {app.months} мес. ".replace(",", " ") + (
        f"Условная оценка модели {pct}%." if pct is not None else "Скоринг модели недоступен."
    )
