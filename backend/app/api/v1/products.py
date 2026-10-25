from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import Client, CurrentUser, Session, get_user_org
from app.core.errors import ApiError
from app.domain.finance import ProductSpec, QuoteInput, quote_error, quote_math
from app.domain.matching import MatchProfile, match_product
from app.models import BankProduct, Organization, Product
from app.schemas.product import (
    BankProductOut,
    CompareIn,
    CompareRow,
    MatchIn,
    MatchItem,
    MatchOut,
    ProductOut,
    ProductWithMatch,
    QuoteIn,
    QuoteOut,
    ScheduleOut,
    ScheduleRowOut,
)
from app.services.catalog import SPECIAL_PRODUCTS, get_product, list_products, product_out, product_spec

router = APIRouter(prefix="/products", tags=["products"])


async def get_calculable(session: Session, product_id: str) -> Product:
    """Продукт, для которого есть ставки и можно считать платёж."""
    p = await get_product(session, product_id)
    if not p.calculable:
        raise ApiError(422, "product_not_calculable", "Для этого продукта расчёт и заявка пока недоступны")
    return p


def _profile(org: Organization | None) -> MatchProfile:
    if org is None:
        return MatchProfile()
    return MatchProfile(
        goal=org.goal, amount=org.amount, months=org.months, frequency=org.frequency, collateral=org.collateral,
        age=org.age, late=org.late,
    )  # fmt: skip


def _input(spec: ProductSpec, body: QuoteIn) -> QuoteInput:
    return QuoteInput(
        amount=body.amount,
        months=body.months if body.months is not None else spec.min_months,
        days=body.days if body.days is not None else 30,
        rate=body.rate if body.rate is not None else (spec.daily if spec.daily is not None else spec.rate),
        scheme=body.scheme or spec.scheme,
        fee=body.fee,
    )


async def _quote(session: Session, user: CurrentUser, spec: ProductSpec, body: QuoteIn):
    q = _input(spec, body)
    if (err := quote_error(spec, q)) is not None:
        return q, None, QuoteOut(error=err, scheme=q.scheme)
    res = quote_math(spec, q)
    rest = None
    if body.organization_id:
        org = await get_user_org(session, user, body.organization_id)
        revenue = body.monthly_revenue if body.monthly_revenue is not None else org.revenue
        expenses = (
            revenue * (1 - body.net_margin_percent / 100)
            if body.net_margin_percent is not None
            else org.expenses
        )
        rest = revenue * (1 + body.stress_pct / 100) - expenses - org.debt - res.peak
    return q, res, QuoteOut(
        interest=res.interest, cost=res.cost, total=res.total, first=res.first, last=res.last, peak=res.peak,
        monthly=res.monthly, rest_at_peak=rest, scheme=q.scheme,
        note="Расчёт ориентировочный, итоговые условия определяет банк.",
        approval_pct=None, risk_band=None,
    )  # fmt: skip


@router.get("", response_model=list[ProductWithMatch])
async def products(
    user: CurrentUser,
    session: Session,
    category: Annotated[str | None, Query(pattern="^(working|gap|investment)$")] = None,
    secured: bool | None = None,
    sort: Annotated[str, Query(pattern="^(match|max|name|default)$")] = "default",
    organization_id: str | None = None,
    include_all: Annotated[bool, Query(description="Включить продукты без калькулятора")] = False,
):
    org = await get_user_org(session, user, organization_id) if organization_id else None
    rows = await list_products(session)
    if not include_all:
        rows = [p for p in rows if p.calculable]
    if category:
        rows = [p for p in rows if p.category == category]
    if secured is not None:
        rows = [p for p in rows if p.secured == secured]
    profile = _profile(org)
    out = []
    for p in rows:
        m = match_product(product_spec(p), profile) if org else None
        out.append(
            ProductWithMatch(
                **product_out(p).model_dump(),
                match=MatchOut(score=m.score, reasons=m.reasons, warnings=m.warnings) if m else None,
            )
        )
    if sort == "match" and org:
        out.sort(key=lambda x: -(x.match.score if x.match else 0))
    elif sort == "max":
        out.sort(key=lambda x: -x.max_amount)
    elif sort == "name":
        out.sort(key=lambda x: x.name)
    return out


@router.get("/special")
async def special(_: CurrentUser) -> list[dict[str, Any]]:
    return SPECIAL_PRODUCTS


@router.post("/match", response_model=list[MatchItem])
async def match(body: MatchIn, user: Client, session: Session):
    org = await get_user_org(session, user, body.organization_id)
    profile = MatchProfile(
        goal=body.goal or org.goal, amount=body.amount, months=body.months, frequency=body.frequency,
        collateral=body.collateral, age=org.age, late=org.late,
    )  # fmt: skip
    items = []
    for p in (p for p in await list_products(session) if p.calculable):
        m = match_product(product_spec(p), profile)
        items.append(
            MatchItem(product_id=p.id, match=MatchOut(score=m.score, reasons=m.reasons, warnings=m.warnings))
        )
    items.sort(key=lambda i: -i.match.score)
    return items


@router.post("/compare", response_model=list[CompareRow])
async def compare(body: CompareIn, user: CurrentUser, session: Session):
    rows = []
    for item in body.items:
        p = await get_calculable(session, item.product_id)
        spec = product_spec(p)
        q = _input(spec, item)
        err = quote_error(spec, q)
        res = None if err else quote_math(spec, q)
        rows.append(
            CompareRow(
                product_id=p.id,
                name=p.name,
                amount=q.amount,
                months=q.months,
                days=q.days,
                rate=q.rate,
                secured=p.secured,
                daily=spec.daily is not None,
                interest=res.interest if res else 0,
                peak=res.peak if res else 0,
                cost=res.cost if res else 0,
                error=err,
            )  # fmt: skip
        )
    return rows


@router.get("/services", response_model=list[BankProductOut])
async def services(
    _: CurrentUser,
    session: Session,
    segment: Annotated[str | None, Query(pattern="^(msb|corporate)$")] = None,
):
    """Некредитные продукты банка (справочник CSV; id совпадают с ML)."""
    stmt = select(BankProduct).order_by(BankProduct.sort_order)
    if segment:
        stmt = stmt.where(BankProduct.segment == segment)
    return list((await session.execute(stmt)).scalars())


@router.get("/{product_id}", response_model=ProductOut)
async def get_one(product_id: str, _: CurrentUser, session: Session):
    return product_out(await get_product(session, product_id))


@router.post("/{product_id}/quote", response_model=QuoteOut)
async def quote(product_id: str, body: QuoteIn, user: CurrentUser, session: Session):
    spec = product_spec(await get_calculable(session, product_id))
    _, _, out = await _quote(session, user, spec, body)
    return out


@router.post("/{product_id}/schedule", response_model=ScheduleOut)
async def schedule(product_id: str, body: QuoteIn, user: CurrentUser, session: Session):
    spec = product_spec(await get_calculable(session, product_id))
    q, res, out = await _quote(session, user, spec, body)
    if res is None:
        return ScheduleOut(unit="day" if spec.kind == "overdraft" else "month", interest=0, rows=[])
    return ScheduleOut(
        unit="day" if spec.kind == "overdraft" else "month", interest=res.interest,
        rows=[ScheduleRowOut(n=r.n, payment=r.payment, principal=r.principal, interest=r.interest, balance=r.balance) for r in res.rows],
    )  # fmt: skip
