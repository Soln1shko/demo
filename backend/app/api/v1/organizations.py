from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from app.api.v1.common import PathOrg
from app.core.config import get_settings
from app.core.deps import Client, Session
from app.core.errors import ApiError, not_found
from app.db.base import utcnow
from app.domain.finance import default_quote_input, quote_error, quote_math
from app.integrations import dadata, mocks
from app.models import FinanceMonth
from app.schemas.application import DraftIn, DraftOut
from app.schemas.organization import (
    CashBalanceIn,
    FinanceMonthIn,
    FinanceMonthOut,
    FinancialsIn,
    LookupOut,
    OnboardingData,
    OnboardingOut,
    OrganizationCreate,
    OrganizationOut,
    OrganizationPatch,
)
from app.services import drafts
from app.services import organizations as svc
from app.services.catalog import get_product, product_spec

router = APIRouter(tags=["organizations"])


# ── онбординг ──


@router.get("/onboarding", response_model=OnboardingOut)
async def get_onboarding(user: Client, session: Session):
    row = await svc.get_onboarding(session, user)
    return OnboardingOut(step=row.step, data=row.data)


@router.put("/onboarding", response_model=OnboardingOut)
async def put_onboarding(body: OnboardingData, user: Client, session: Session):
    row = await svc.save_onboarding(session, user, body)
    return OnboardingOut(step=row.step, data=row.data)


@router.post("/onboarding/complete", response_model=OrganizationOut, status_code=201)
async def complete_onboarding(user: Client, session: Session):
    return await svc.complete_onboarding(session, user)


@router.get("/lookup/company", response_model=LookupOut)
async def lookup_company(inn: Annotated[str, Query(pattern=r"^\d{10}(\d{2})?$")], _: Client):
    """Реальная компания по ИНН (DaData), если задан DADATA_API_KEY; иначе — синтетические данные с `demo: true`."""
    key = get_settings().dadata_api_key
    if not key:
        return {**await mocks.fns.company(inn), "demo": True}
    try:
        company = await dadata.find_company(inn, key)
    except dadata.LookupUnavailable as e:
        raise ApiError(503, "lookup_unavailable", "Поиск компании по ИНН сейчас недоступен") from e
    if company is None:
        raise ApiError(404, "company_not_found", "Компания с таким ИНН не найдена")
    return company


# ── организации ──


@router.get("/organizations", response_model=list[OrganizationOut])
async def list_organizations(user: Client, session: Session):
    return await svc.list_orgs(session, user)


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
async def create_organization(body: OrganizationCreate, user: Client, session: Session):
    if len(body.inn) != (12 if body.legal == "ip" else 10):
        raise ApiError(
            422,
            "validation_failed",
            "ИНН: 10 цифр для юрлица, 12 для ИП",
            errors=[{"field": "inn", "message": "Неверная длина ИНН"}],
        )
    return await svc.create_org(session, user, body.model_dump())


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
async def get_organization(org: PathOrg):
    return org


@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def patch_organization(body: OrganizationPatch, org: PathOrg, session: Session):
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(org, k, v)
    await session.commit()
    return org


@router.patch("/organizations/{org_id}/financials", response_model=OrganizationOut)
async def patch_financials(body: FinancialsIn, org: PathOrg, session: Session):
    org.revenue, org.expenses, org.debt = body.revenue, body.expenses, body.debt
    await session.commit()
    return org


@router.put("/organizations/{org_id}/cash-balance", response_model=OrganizationOut)
async def put_cash_balance(body: CashBalanceIn, org: PathOrg, session: Session):
    org.cash_balance, org.cash_balance_at = body.amount, utcnow()
    await session.commit()
    return org


# ── помесячные показатели ──


@router.get("/organizations/{org_id}/finance-history", response_model=list[FinanceMonthOut])
async def finance_history(org: PathOrg, session: Session, months: Annotated[int, Query(ge=1, le=36)] = 12):
    rows = [r for r in await svc.finance_rows(session, org.id) if r.source != "Анкета"]
    return rows[-months:]


@router.put("/organizations/{org_id}/finance-history/{month}", response_model=FinanceMonthOut)
async def put_finance_month(month: str, body: FinanceMonthIn, org: PathOrg, session: Session):
    return await svc.upsert_month(session, org, month, body.revenue, body.expenses, body.debt)


@router.delete("/organizations/{org_id}/finance-history/{month}", status_code=204)
async def delete_finance_month(month: str, org: PathOrg, session: Session):
    row = await session.get(FinanceMonth, (org.id, month))
    if row is None or row.source == "Анкета":
        raise not_found("Месяц")
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.get("/organizations/{org_id}/analytics")
async def analytics(
    org: PathOrg, session: Session, months: Annotated[int, Query(ge=3, le=12)] = 6
) -> dict[str, Any]:
    return await svc.build_analytics(session, org, months)


class StressIn(BaseModel):
    amount: float = Field(gt=0)
    months: int = Field(ge=1, le=120)
    product_id: str = "business_loan"
    revenue_shock_pct: float = Field(0, ge=-100, le=100)


@router.post("/organizations/{org_id}/stress-test")
async def stress_test(body: StressIn, org: PathOrg, session: Session) -> dict[str, Any]:
    product = await get_product(session, body.product_id)
    if not product.calculable:
        raise ApiError(422, "product_not_calculable", "Для этого продукта расчёт пока недоступен")
    spec = product_spec(product)
    q = default_quote_input(spec, body.amount, body.months)
    if (err := quote_error(spec, q)) is not None:
        raise ApiError(422, "validation_failed", err, errors=[{"field": "amount", "message": err}])
    res = quote_math(spec, q)
    revenue = org.revenue * (1 + body.revenue_shock_pct / 100)
    free = revenue - org.expenses - org.debt
    rest = free - res.peak
    load = (org.debt + res.peak) / revenue if revenue > 0 else None
    hint = (
        "Платёж помещается в свободный поток даже при снижении выручки."
        if rest >= 0
        else "При таком сценарии после платежа остаётся минус. Рассмотрите меньшую сумму или больший срок."
    )
    return {
        "payment": res.peak, "free_flow": free, "rest": rest, "load": load, "overpay": res.interest, "hint": hint,
    }  # fmt: skip


# ── черновик заявки ──


@router.get("/organizations/{org_id}/draft", response_model=DraftOut | None)
async def get_draft(org: PathOrg, session: Session):
    row = await drafts.get_draft_row(session, org.id)
    return await drafts.draft_out(session, row) if row else None


@router.put("/organizations/{org_id}/draft", response_model=DraftOut)
async def put_draft(body: DraftIn, org: PathOrg, session: Session):
    row = await drafts.upsert_draft(session, org, body)
    return await drafts.draft_out(session, row)


@router.delete("/organizations/{org_id}/draft", status_code=204)
async def delete_draft(org: PathOrg, session: Session):
    await drafts.delete_draft(session, org.id)
    return Response(status_code=204)
