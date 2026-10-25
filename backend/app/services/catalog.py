"""Каталог продуктов: данные, преобразования, посев в БД."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.domain.finance import ProductSpec
from app.domain.scoring import ScoringRules
from app.models import Application, ApplicationDraft, BankProduct, FeedItem, Product, Setting
from app.schemas.product import ProductOut
from app.services import product_data

# Условия сверены со страницами Альфа-Банка 22.10.2026 (см. docs/research-v4.md старого прототипа).
CATALOG: list[dict[str, Any]] = [
    dict(
        id="business_loan",
        name="Бизнес-кредит одной суммой",
        short="Деньги на развитие",
        desc="Одна сумма на закупки, развитие компании или рефинансирование.",
        icon="briefcase-business",
        min_amount=300_000,
        max_amount=30_000_000,
        min_months=12,
        max_months=60,
        rate=23.5,
        rate_label="от 23,5% годовых",
        discount="От 14% при оформлении Защиты бизнеса и Подписки. Их стоимость рассчитывается отдельно.",
        kind="loan",
        scheme="annuity",
        secured=False,
        min_age=9,
        category="working",
        term="1–5 лет",
        source_url="businesscredit/",
        features=[
            "До 30 млн ₽ без залога",
            "Для ИП без поручителей; для ООО поручительство уточняется",
            "Аннуитетный или дифференцированный график",
        ],
    ),
    dict(
        id="credit_line",
        name="Возобновляемая кредитная линия",
        short="Запас на регулярные закупки",
        desc="Берите деньги частями. Погашенный основной долг восстанавливает доступный лимит.",
        icon="repeat-2",
        min_amount=300_000,
        max_amount=30_000_000,
        min_months=1,
        max_months=6,
        rate=23.5,
        rate_label="от 23,5% годовых",
        discount="С подпиской от 14,5%; срок транша может быть увеличен до 12 месяцев. Стоимость подписки индивидуальна.",
        kind="line",
        scheme="diff",
        secured=False,
        min_age=9,
        category="working",
        term="Транш 1–6 мес.",
        source_url="creditline/",
        features=[
            "Лимит без залога до 30 млн ₽",
            "Договор на 18 месяцев с продлением",
            "Проценты на использованную сумму",
        ],
    ),
    dict(
        id="overdraft",
        name="Овердрафт",
        short="Когда поступление задержалось",
        desc="Резерв на расчетном счете для короткого разрыва между платежом и поступлением денег.",
        icon="arrow-left-right",
        min_amount=50_000,
        max_amount=20_000_000,
        min_months=1,
        max_months=2,
        rate=13,
        rate_label="от 13% со скидкой",
        discount="13% — нижняя ставка со скидкой, не универсальный тариф. Условия и стоимость подписки уточняются банком; в расчете услуги не учтены.",
        kind="overdraft",
        scheme="bullet",
        secured=False,
        min_age=9,
        category="gap",
        term="Долг до 60 дней",
        source_url="overdraft/",
        features=[
            "Лимит 50 тыс. — 20 млн ₽",
            "Без залога и комиссии за подключение",
            "Проценты только за дни использования",
        ],
    ),
    dict(
        id="alfa_start",
        name="Альфа-Старт",
        short="Небольшая сумма на короткий срок",
        desc="Кредитная линия до миллиона рублей с возвратом основного долга в конце транша.",
        icon="flag",
        min_amount=50_000,
        max_amount=1_000_000,
        min_months=1,
        max_months=6,
        rate=109.5,
        daily=0.3,
        rate_label="0,3% в день",
        discount="С подпиской от 0,15% в день, транш до 12 месяцев. Даже небольшая дневная ставка требует расчета в рублях.",
        kind="daily",
        scheme="bullet",
        secured=False,
        min_age=0,
        category="working",
        term="Транш 1–6 мес.",
        source_url="alfastart/",
        features=[
            "От 50 тыс. до 1 млн ₽",
            "Проценты ежемесячно, основной долг в конце",
            "Досрочное погашение без штрафов",
        ],
    ),
    dict(
        id="business_pledge_loan",
        name="Деньги на дело",
        short="Финансирование под имущество",
        desc="Кредит под залог недвижимости или транспорта, в том числе для недавно открытого бизнеса.",
        icon="landmark",
        min_amount=500_000,
        max_amount=150_000_000,
        min_months=12,
        max_months=120,
        rate=21.5,
        rate_label="от 21,5% годовых",
        discount="От 15,5% с Защитой бизнеса при доле недвижимости более 50%. При другой структуре залога ставки выше.",
        kind="loan",
        scheme="diff",
        secured=True,
        min_age=0,
        category="investment",
        term="До 10 лет",
        source_url="lombardnyj_kredit/",
        features=[
            "Нижняя граница калькулятора 500 тыс. ₽ — расчетный ориентир, минимум уточните в банке",
            "До 150 млн ₽ одной суммой / невозобновляемой линией",
            "Для транспорта срок до 5 лет",
            "Финансовые документы по базовому предложению не запрашиваются; дополнительные возможны",
        ],
    ),
    dict(
        id="business_mortgage",
        name="Коммерческая недвижимость",
        short="Свой офис или помещение",
        desc="Покупка коммерческого помещения с передачей приобретаемой недвижимости в залог.",
        icon="building-2",
        min_amount=500_000,
        max_amount=150_000_000,
        min_months=12,
        max_months=120,
        rate=23,
        rate_label="от 23% годовых",
        discount="На странице банка есть расхождение между главным блоком и FAQ по ставке. Для ориентира использован главный блок; финальную ставку нужно подтвердить.",
        kind="loan",
        scheme="annuity",
        secured=True,
        min_age=9,
        category="investment",
        term="До 10 лет",
        source_url="kredit-na-kommercheskuyu-nedvizhimost/",
        features=[
            "Нижняя граница калькулятора 500 тыс. ₽ — расчетный ориентир, минимум уточните в банке",
            "До 150 млн ₽",
            "Взнос от 15%; может заменяться дополнительным залогом",
            "Без комиссии за выдачу и сопровождение",
        ],
    ),
]

SPECIAL_PRODUCTS = [
    {
        "name": "Кредит для селлеров",
        "url": "creditsellers/",
        "desc": "Кредитная линия для бизнеса на маркетплейсах. Условия зависят от оборотов и выбранной подписки.",
    },
    {
        "name": "Кредит с господдержкой",
        "url": "goscredit/",
        "desc": "Программы с отдельными требованиями к деятельности и заемщику. Подходящую программу подтверждает менеджер.",
    },
    {
        "name": "Поручительство РГО",
        "url": "kredit-s-rgo/",
        "desc": "Дополнительная возможность при недостатке обеспечения. Требуется проверка региональных условий.",
    },
]

FEED_SEED: list[dict[str, Any]] = [
    dict(
        id="ed-retail-season",
        icon="package",
        priority=50,
        title="Сезон закупок ближе, чем кажется",
        body="Подготовьте оборотные средства к пику спроса и проверьте запас прочности.",
        cta={"label": "Подобрать продукт", "route": "/app/products"},
        conditions={"profiles": ["retail"]},
    ),
    dict(
        id="ed-production-equipment",
        icon="factory",
        priority=50,
        title="Оборудование без перегрузки",
        body="Сравните стоимость финансирования и ежемесячную нагрузку до расширения производства.",
        cta={"label": "Подобрать продукт", "route": "/app/products"},
        conditions={"profiles": ["production"]},
    ),
    dict(
        id="ed-services-flow",
        icon="briefcase-business",
        priority=50,
        title="Платежи под график поступлений",
        body="Для услуг важна ритмичность выручки. Сравните линию и кредит одной суммой.",
        cta={"label": "Подобрать продукт", "route": "/app/products"},
        conditions={"profiles": ["services"]},
    ),
    dict(
        id="ed-stress",
        icon="chart-no-axes-combined",
        priority=40,
        title="Падение выручки не должно удивить",
        body="Проверьте сценарий −20% в калькуляторе продукта и узнайте, сколько денег останется после платежей.",
        cta={"label": "Проверить сценарий", "route": "/app/products"},
        conditions={},
    ),
    dict(
        id="ed-cash-gap",
        icon="arrow-left-right",
        priority=60,
        title="Кассовый разрыв: короткие деньги",
        body="Если деньги нужны до поступления выручки, посмотрите овердрафт: проценты только за дни использования.",
        cta={"label": "Смотреть овердрафт", "route": "/app/products"},
        conditions={"goals": ["кассов"]},
    ),
    dict(
        id="ed-history",
        icon="calendar-days",
        priority=55,
        title="Добавьте месячные показатели",
        body="Помесячная история покажет динамику и сделает аналитику точнее, чем средние значения из анкеты.",
        cta={"label": "Открыть обзор", "route": "/app"},
        conditions={"no_history": True},
    ),
    dict(
        id="ed-young",
        icon="flag",
        priority=45,
        title="Бизнесу меньше 9 месяцев",
        body="Для молодых компаний подходят «Альфа-Старт» и кредит под залог. Остальным продуктам нужен стаж.",
        cta={"label": "Смотреть продукты", "route": "/app/products"},
        conditions={"max_age": 8},
    ),
    dict(
        id="ed-negative",
        icon="info",
        priority=65,
        title="После платежей остаётся минус",
        body="Расходы и кредиты превышают выручку. Новый кредит усилит нагрузку — начните с пересмотра затрат.",
        cta={"label": "Открыть обзор", "route": "/app"},
        conditions={"negative_cash": True},
    ),
    dict(
        id="ed-first",
        icon="compass",
        priority=35,
        title="Первая заявка — первый шаг",
        body="Выберите продукт, проверьте платёж и отправьте заявку. Статус будет виден прямо в кабинете.",
        cta={"label": "Выбрать продукт", "route": "/app/products"},
        conditions={"no_apps": True},
    ),
]


def product_spec(p: Product) -> ProductSpec:
    return ProductSpec(
        id=p.id, name=p.name, kind=p.kind, scheme=p.scheme, secured=p.secured, category=p.category,
        min_amount=p.min_amount, max_amount=p.max_amount, min_months=p.min_months, max_months=p.max_months,
        min_age=p.min_age, rate=p.rate, daily=p.daily,
    )  # fmt: skip


def spec_from_snapshot(s: dict[str, Any]) -> ProductSpec:
    return ProductSpec(
        id=s["id"], name=s["name"], kind=s["kind"], scheme=s["scheme"], secured=s["secured"],
        category=s["category"], min_amount=s["min_amount"], max_amount=s["max_amount"],
        min_months=s["min_months"], max_months=s["max_months"], min_age=s["min_age"], rate=s["rate"],
        daily=s.get("daily"),
    )  # fmt: skip


def product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id, name=p.name, short=p.short, desc=p.desc, icon=p.icon, kind=p.kind, scheme=p.scheme,
        secured=p.secured, category=p.category, min_amount=p.min_amount, max_amount=p.max_amount,
        min_months=p.min_months, max_months=p.max_months, min_age=p.min_age, rate=p.rate, daily=p.daily,
        rate_label=p.rate_label, discount=p.discount, term=p.term, source_url=p.source_url,
        features=list(p.features or []), calculable=p.calculable, segment=p.segment, family=p.family,
        purpose_tags=list(p.purpose_tags or []), pricing_type=p.pricing_type, collateral_policy=p.collateral_policy,
        new_business_allowed=p.new_business_allowed, marketplace_required=p.marketplace_required,
    )  # fmt: skip


def snapshot(p: Product) -> dict[str, Any]:
    return product_out(p).model_dump()


async def get_product(session: AsyncSession, product_id: str) -> Product:
    p = await session.get(Product, product_id)
    if p is None:
        raise not_found("Продукт")
    return p


async def list_products(session: AsyncSession) -> list[Product]:
    return list((await session.execute(select(Product).order_by(Product.sort_order))).scalars())


META_KEYS = (
    "name", "segment", "family", "purpose_tags", "pricing_type", "collateral_policy",
    "new_business_allowed", "marketplace_required", "effective_at",
)  # fmt: skip


def credit_catalog() -> list[dict[str, Any]]:
    """Кредитные продукты для БД: id, названия и теги — из CSV; ставки и лимиты расчёта — из CATALOG."""
    meta_by_id = {r["id"]: r for r in product_data.credit_rows()}
    rows = []
    for d in CATALOG:
        meta = meta_by_id[d["id"]]
        rows.append({**d, **{k: meta[k] for k in META_KEYS}, "calculable": True})
    calculable = {d["id"] for d in CATALOG}
    for meta in product_data.credit_rows():
        if meta["id"] in calculable:
            continue
        text = product_data.CATALOG_ONLY[meta["id"]]
        months = meta["max_months"]
        rows.append(dict(
            id=meta["id"], short=text["short"], desc=text["desc"], icon="briefcase-business", kind="catalog",
            scheme="annuity", secured=meta["collateral_policy"] == "required", category=text["category"],
            min_amount=meta["min_amount"], max_amount=meta["max_amount"], min_months=meta["min_months"],
            max_months=months, min_age=0, rate=0.0, daily=None, rate_label="Ставка по запросу", discount="",
            term=f"До {months} мес." if months else "По условиям партнёра",
            source_url=product_data.relative_source(meta["source_url"]), features=[], calculable=False,
            **{k: meta[k] for k in META_KEYS},
        ))  # fmt: skip
    return rows


async def migrate_legacy_ids(session: AsyncSession) -> None:
    """Переносит заявки и черновики со старых id продуктов на id из справочника, затем удаляет старые строки."""
    for old, new in product_data.LEGACY_IDS.items():
        row = await session.get(Product, old)
        if row is None or await session.get(Product, new) is None:
            continue
        found = await session.execute(select(Application).where(Application.product_id == old))
        for app in found.scalars():
            app.product_id = new
            app.product_snapshot = {**(app.product_snapshot or {}), "id": new}
        await session.execute(
            update(ApplicationDraft).where(ApplicationDraft.product_id == old).values(product_id=new)
        )
        await session.flush()
        await session.delete(row)
        await session.flush()


async def seed_services(session: AsyncSession) -> None:
    """Некредитные продукты: таблица полностью повторяет CSV (лишние строки удаляются)."""
    rows = product_data.service_rows()
    existing = {p.id: p for p in (await session.execute(select(BankProduct))).scalars()}
    for order, data in enumerate(rows):
        row = existing.pop(data["id"], None)
        if row is None:
            session.add(BankProduct(sort_order=order, **data))
        else:
            for key, value in data.items():
                setattr(row, key, value)
            row.sort_order = order
    for stale in existing.values():
        await session.delete(stale)


async def seed_catalog(session: AsyncSession) -> None:
    existing = {p.id: p for p in await list_products(session)}
    for order, data in enumerate(credit_catalog()):
        row = existing.get(data["id"])
        if row is None:
            session.add(Product(sort_order=order, **data))
        else:
            for key, value in data.items():
                setattr(row, key, value)
            row.sort_order = order
    await session.flush()
    await migrate_legacy_ids(session)
    await seed_services(session)
    have = set((await session.execute(select(FeedItem.id))).scalars())
    for data in FEED_SEED:
        if data["id"] not in have:
            session.add(FeedItem(kind="editorial", **data))
    await session.commit()


RULES_KEY = "scoring_rules"


async def get_rules(session: AsyncSession) -> ScoringRules:
    row = await session.get(Setting, RULES_KEY)
    return ScoringRules(**row.value) if row else ScoringRules()


async def save_rules(session: AsyncSession, rules: ScoringRules) -> ScoringRules:
    current = await get_rules(session)
    rules = rules.model_copy(update={"version": current.version + 1})
    row = await session.get(Setting, RULES_KEY)
    if row is None:
        session.add(Setting(key=RULES_KEY, value=rules.model_dump()))
    else:
        row.value = rules.model_dump()
    await session.commit()
    return rules
