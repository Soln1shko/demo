"""Сидинг: каталог, тестовые аккаунты и демо-заявки (все данные синтетические)."""

from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    Application,
    Document,
    FinanceMonth,
    Organization,
    OrganizationMember,
    SupportMessage,
    SupportTicket,
    User,
)
from app.models.user import ROLE_ADMIN, ROLE_ANALYST, ROLE_CLIENT
from app.services import applications as apps
from app.services.catalog import get_product, seed_catalog, snapshot
from app.services.organizations import month_key

log = structlog.get_logger()

# Демо-компании и сценарии: хороший / альтернатива / ручной разбор / отказ по ФНС / просрочка БКИ.
DEMO_ORGS = [
    dict(key="good", name="ООО «Ромашка»", inn="7701234567", legal="ooo", profile="retail", region="Москва",
         age=36, revenue=2_400_000, expenses=1_750_000, debt=120_000, goal="Закупка товара", amount=1_500_000, months=24,
         late=False),
    dict(key="alt", name="ИП Петров А. В.", inn="502912345678", legal="ip", profile="services", region="Казань",
         age=24, revenue=1_450_000, expenses=1_000_000, debt=50_000, goal="Развитие бизнеса", amount=6_000_000, months=36,
         late=False),
    dict(key="manual", name="ООО «Новый старт»", inn="7712345678", legal="ooo", profile="production",
         region="Екатеринбург", age=4, revenue=900_000, expenses=700_000, debt=60_000, goal="Оборудование",
         amount=1_200_000, months=24, late=True),
    dict(key="fns", name="ООО «Ликвидатор»", inn="0012345678", legal="ooo", profile="retail", region="Москва",
         age=48, revenue=2_000_000, expenses=1_400_000, debt=80_000, goal="Закупка товара", amount=800_000, months=18,
         late=False),
    dict(key="bki", name="ООО «Просрочка»", inn="7723456799", legal="ooo", profile="services", region="Новосибирск",
         age=30, revenue=1_800_000, expenses=1_200_000, debt=200_000, goal="Развитие бизнеса", amount=1_000_000,
         months=24, late=False),
]  # fmt: skip

# Пять отдельных кабинетов: разные цели, история денег и сложность заявок.
# Имена и идентификаторы заведомо демонстрационные.
DEMO_PROFILES = [
    dict(key="store", name="ООО «Демо Магазин»", inn="0000000001", legal="ooo", profile="retail", region="Москва",
         age=60, revenue=2_400_000, expenses=1_750_000, debt=120_000, cash_balance=310_000,
         goal="Закупка товара", amount=1_500_000, months=24, late=False, seasonality="stable",
         frequency="regular", collateral="no", trend=[0.88, 0.92, 0.94, 0.97, 1.02, 1.0]),
    dict(key="season", name="ИП «Демо Сезон»", inn="000000000002", legal="ip", profile="retail", region="Казань",
         age=30, revenue=1_450_000, expenses=1_200_000, debt=50_000, cash_balance=90_000,
         goal="Покрыть кассовый разрыв", amount=700_000, months=12, late=False, seasonality="seasonal",
         frequency="regular", collateral="no", trend=[1.35, 0.75, 0.62, 1.4, 0.7, 1.0]),
    dict(key="workshop", name="ООО «Демо Цех»", inn="0000000003", legal="ooo", profile="production", region="Екатеринбург",
         age=5, revenue=900_000, expenses=750_000, debt=60_000, cash_balance=40_000,
         goal="Купить оборудование", amount=1_200_000, months=36, late=True, seasonality="stable",
         frequency="once", collateral="equipment", trend=[0.6, 0.7, 0.78, 0.84, 0.9, 1.0]),
    dict(key="studio", name="ООО «Демо Студия»", inn="0000000004", legal="ooo", profile="services", region="Новосибирск",
         age=18, revenue=500_000, expenses=620_000, debt=180_000, cash_balance=20_000,
         goal="Закрыть кассовый разрыв", amount=800_000, months=18, late=True, seasonality="seasonal",
         frequency="once", collateral="no", trend=[1.1, 0.92, 0.8, 0.7, 0.85, 1.0]),
    dict(key="factory", name="ООО «Демо Фабрика»", inn="0000000005", legal="ooo", profile="production", region="Самара",
         age=108, revenue=5_000_000, expenses=3_100_000, debt=250_000, cash_balance=1_200_000,
         goal="Инвестиции в оборудование", amount=8_000_000, months=60, late=False, seasonality="stable",
         frequency="once", collateral="realty", trend=[0.83, 0.87, 0.91, 0.94, 0.98, 1.0]),
]  # fmt: skip


async def _ensure_user(
    session: AsyncSession, *, email: str, name: str, password: str, role: str, operator_id: str | None = None
) -> tuple[User, bool]:
    stmt = (
        select(User).where(User.operator_id == operator_id)
        if operator_id
        else select(User).where(User.email == email)
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user, False
    user = User(
        email=email,
        name=name,
        password_hash=hash_password(password),
        role=role,
        operator_id=operator_id,
        demo_consent=True,
    )
    session.add(user)
    await session.flush()
    return user, True


def _months_back(n: int) -> list[str]:
    today = date.today()
    out = []
    for i in range(n, 0, -1):
        m = today.month - i
        y = today.year + (m - 1) // 12
        out.append(f"{y}-{((m - 1) % 12) + 1:02d}")
    return out


async def _demo_application(session: AsyncSession, user: User, org: Organization, spec: dict) -> str:
    product = await get_product(session, "business_loan")
    app = Application(
        id=apps.new_app_id(), organization_id=org.id, product_id=product.id, status="submitted", version=1,
        amount=spec["amount"], months=spec["months"], days=30, rate=product.rate, scheme=product.scheme, fee=0,
        goal=spec["goal"], company=org.name, inn=org.inn, legal=org.legal, region=org.region, revenue=org.revenue,
        expenses=org.expenses, debt=org.debt, age=org.age, late=org.late, consent=True,
        product_snapshot=snapshot(product),
    )  # fmt: skip
    session.add(app)
    await session.flush()
    session.add(
        Document(organization_id=org.id, application_id=app.id, uploader_id=user.id, name="Выписка за 6 месяцев · образец 1.pdf",
                 size=0, mime="text/plain; charset=utf-8", kind="sample")
    )  # fmt: skip
    await apps.add_event(
        session, app.id, "submitted", "Заявка отправлена клиентом", actor=user, role="client"
    )
    return app.id


async def seed_demo_client(session: AsyncSession, user: User) -> None:
    for spec in DEMO_ORGS:
        data = {k: v for k, v in spec.items() if k not in ("key",)}
        org = Organization(**data)
        session.add(org)
        await session.flush()
        session.add(OrganizationMember(user_id=user.id, organization_id=org.id, role="owner"))
        session.add(
            FinanceMonth(
                organization_id=org.id,
                month=month_key(),
                revenue=org.revenue,
                expenses=org.expenses,
                debt=org.debt,
                source="Анкета",
            )  # fmt: skip
        )
        if spec["key"] == "good":
            for i, month in enumerate(_months_back(6)):
                session.add(
                    FinanceMonth(
                        organization_id=org.id,
                        month=month,
                        revenue=org.revenue * (0.9 + i * 0.03),
                        expenses=org.expenses * (0.95 + i * 0.01),
                        debt=org.debt,
                        source="Месячный отчет",
                    )  # fmt: skip
                )
        await session.flush()
        await _demo_application(session, user, org, spec)
    await session.commit()


async def seed_profile_clients(session: AsyncSession, password: str) -> None:
    """Идемпотентно добавляет пять отдельных учебных кабинетов и заявок."""
    for i, spec in enumerate(DEMO_PROFILES, start=1):
        user, _ = await _ensure_user(
            session, email=f"demo{i}@demo.ru", name=f"Демо клиент {i}", password=password, role=ROLE_CLIENT
        )
        existing = (
            await session.execute(
                select(Organization)
                .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                .where(OrganizationMember.user_id == user.id, Organization.inn == spec["inn"])
            )
        ).scalar_one_or_none()
        if existing is None:
            org = Organization(**{k: v for k, v in spec.items() if k not in ("key", "trend")})
            session.add(org)
            await session.flush()
            session.add(OrganizationMember(user_id=user.id, organization_id=org.id, role="owner"))
            trend = spec["trend"]
            assert isinstance(trend, list)
            for month, factor in zip(_months_back(6), trend, strict=True):
                session.add(
                    FinanceMonth(
                        organization_id=org.id,
                        month=month,
                        revenue=round(org.revenue * factor),
                        expenses=org.expenses,
                        debt=org.debt,
                        source="Синтетический сценарий",
                    )
                )
            session.add(
                FinanceMonth(
                    organization_id=org.id,
                    month=month_key(),
                    revenue=org.revenue,
                    expenses=org.expenses,
                    debt=org.debt,
                    source="Синтетический сценарий",
                )
            )
            await session.flush()
            await _demo_application(session, user, org, spec)
        else:
            org = existing
        if i in (2, 4):
            ticket_id = f"TK-DEMO-{i:02d}"
            if await session.get(SupportTicket, ticket_id) is None:
                question = (
                    "Выручка сезонная. Как подобрать сумму на короткий кассовый разрыв?"
                    if i == 2
                    else "Расходы выше выручки. Какие данные нужны для разбора заявки?"
                )
                session.add(
                    SupportTicket(
                        id=ticket_id,
                        organization_id=org.id,
                        user_id=user.id,
                        question=question,
                        status="open",
                    )
                )
                await session.flush()
                session.add(
                    SupportMessage(
                        ticket_id=ticket_id,
                        author_role="client",
                        author_name=user.name,
                        text=question,
                    )
                )
    await session.commit()


SCENARIO_KEYS = {"good": "good", "alt": "alt", "manual": "manual", "bad": "fns"}


async def create_scenario(session: AsyncSession, kind: str) -> Application:
    """Новая синтетическая заявка в очереди для демонстрации одного из исходов."""
    spec = next(s for s in DEMO_ORGS if s["key"] == SCENARIO_KEYS[kind])
    client = (await session.execute(select(User).where(User.email == "client@demo.ru"))).scalar_one_or_none()
    if client is None:
        client, _ = await _ensure_user(
            session,
            email="client@demo.ru",
            name="Алексей",
            password=get_settings().demo_client_password,
            role=ROLE_CLIENT,
        )
    org = (
        await session.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == client.id, Organization.inn == spec["inn"])
        )
    ).scalar_one_or_none()
    if org is None:
        org = Organization(**{k: v for k, v in spec.items() if k != "key"})
        session.add(org)
        await session.flush()
        session.add(OrganizationMember(user_id=client.id, organization_id=org.id, role="owner"))
    app_id = await _demo_application(session, client, org, spec)
    await session.commit()
    return await apps.get_app(session, app_id)


async def seed_all(session: AsyncSession, *, with_demo_data: bool = True) -> None:
    s = get_settings()
    await seed_catalog(session)
    await _ensure_user(
        session, email="new@demo.ru", name="Новый клиент", password=s.demo_client_password, role=ROLE_CLIENT
    )
    client, created = await _ensure_user(
        session, email="client@demo.ru", name="Алексей", password=s.demo_client_password, role=ROLE_CLIENT
    )
    await _ensure_user(
        session,
        email="op@bank.local",
        name="Мария Аналитик",
        password=s.demo_operator_password,
        role=ROLE_ANALYST,
        operator_id="op-2026",
    )
    await _ensure_user(
        session,
        email="adm@bank.local",
        name="Иван Администратор",
        password=s.demo_operator_password,
        role=ROLE_ADMIN,
        operator_id="adm-2026",
    )
    await session.commit()
    if created and with_demo_data:
        await seed_demo_client(session, client)
    if with_demo_data:
        await seed_profile_clients(session, s.demo_client_password)
    log.info("seed_done", demo_data=created and with_demo_data)
