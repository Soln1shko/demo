import csv
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import session_factory
from app.models import Application, ApplicationDraft, BankProduct, Organization, Product
from app.services import product_data
from app.services.catalog import seed_catalog

ROOT_DATA = Path(__file__).resolve().parents[3] / "data"


async def _headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": "client@demo.ru", "password": "Demo2026!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _csv_ids(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r["product_id"] for r in csv.DictReader(f)]


def test_backend_csv_copies_match_repo_data():
    """Копии в backend/app/data не должны расходиться со справочниками в data/."""
    for src, copy in (
        (ROOT_DATA / "Кредитные_продукты_Альфа_Банка_МСБ.csv", product_data.CREDIT_CSV),
        (ROOT_DATA / "Продукты_Альфа_Банка_вне_кредитов_МСБ.csv", product_data.SERVICE_CSV),
    ):
        if src.exists():
            assert src.read_bytes() == copy.read_bytes(), f"{copy.name} отличается от {src.name}"


async def test_db_ids_equal_reference_ids(client: AsyncClient):
    async with session_factory()() as session:
        credit = set((await session.execute(select(Product.id))).scalars())
        services = set((await session.execute(select(BankProduct.id))).scalars())
    assert credit == set(_csv_ids(product_data.CREDIT_CSV)) and len(credit) == 11
    assert services == set(_csv_ids(product_data.SERVICE_CSV)) and len(services) == 21


async def test_catalog_only_products_are_hidden_and_not_calculable(client: AsyncClient):
    h = await _headers(client)
    default = (await client.get("/api/v1/products", headers=h)).json()
    assert {p["id"] for p in default} == {
        "business_loan",
        "credit_line",
        "overdraft",
        "alfa_start",
        "business_pledge_loan",
        "business_mortgage",
    }
    assert all(p["calculable"] for p in default)
    everything = (await client.get("/api/v1/products?include_all=true", headers=h)).json()
    assert len(everything) == 11
    seller = next(p for p in everything if p["id"] == "seller_credit")
    assert seller["calculable"] is False and seller["marketplace_required"] is True and seller["rate"] == 0

    quote = await client.post(
        "/api/v1/products/seller_credit/quote", json={"amount": 100000, "months": 6}, headers=h
    )
    assert quote.status_code == 422 and quote.json()["code"] == "product_not_calculable"

    org = (await client.get("/api/v1/organizations", headers=h)).json()[0]
    draft = await client.put(
        f"/api/v1/organizations/{org['id']}/draft",
        json={"product_id": "seller_credit", "replace": True},
        headers=h,
    )
    assert draft.status_code == 422


async def test_services_endpoint(client: AsyncClient):
    h = await _headers(client)
    all_rows = (await client.get("/api/v1/products/services", headers=h)).json()
    assert len(all_rows) == 21 and all_rows[0]["id"] == "business_account"
    assert "payments" in all_rows[0]["purpose_tags"]
    corporate = (await client.get("/api/v1/products/services?segment=corporate", headers=h)).json()
    assert [r["id"] for r in corporate] == ["cash_management", "collection", "corporate_letter_of_credit"]


async def test_legacy_ids_are_migrated(client: AsyncClient):
    """Старая БД с id вида `working` переезжает на id справочника вместе с заявками и черновиками."""
    async with session_factory()() as session:
        new = await session.get(Product, "business_loan")
        legacy = Product(
            **{c.name: getattr(new, c.name) for c in Product.__table__.columns} | {"id": "working"}
        )
        session.add(legacy)
        await session.flush()
        app = (await session.execute(select(Application).limit(1))).scalars().one()
        app.product_id = "working"
        app.product_snapshot = {**app.product_snapshot, "id": "working"}
        org = (
            (
                await session.execute(
                    select(Organization).where(Organization.id != app.organization_id).limit(1)
                )
            )
            .scalars()
            .one()
        )
        session.add(ApplicationDraft(organization_id=org.id, product_id="equipment", step=1, data={}))
        session.add(
            Product(**{c.name: getattr(new, c.name) for c in Product.__table__.columns} | {"id": "equipment"})
        )
        await session.commit()
        app_id, org_id = app.id, org.id

        await seed_catalog(session)

    async with session_factory()() as session:
        migrated = await session.get(Application, app_id)
        assert migrated.product_id == "business_loan" and migrated.product_snapshot["id"] == "business_loan"
        draft = (
            (
                await session.execute(
                    select(ApplicationDraft).where(ApplicationDraft.organization_id == org_id)
                )
            )
            .scalars()
            .one()
        )
        assert draft.product_id == "business_loan"
        assert (
            await session.get(Product, "working") is None and await session.get(Product, "equipment") is None
        )
