"""Симуляторы внешних систем (ФНС, БКИ, подпись, выдача).

Данные детерминированно генерируются по ИНН и являются синтетическими.
Особые демо-ИНН:
  * начинается с «00»  — ФНС: компания в стадии ликвидации (отказ);
  * заканчивается на «99» — БКИ: действующая просрочка (отказ/ручной разбор);
  * остальные — «чистые» компании.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any, Protocol

OKVED = [
    ("47.19", "Торговля розничная прочая в неспециализированных магазинах"),
    ("46.90", "Торговля оптовая неспециализированная"),
    ("10.71", "Производство хлеба и мучных кондитерских изделий"),
    ("25.62", "Обработка металлических изделий механической обработкой"),
    ("62.01", "Разработка компьютерного программного обеспечения"),
    ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания"),
    ("49.41", "Деятельность автомобильного грузового транспорта"),
    ("43.21", "Производство электромонтажных работ"),
]
HEADS = [
    "Иванов Алексей Петрович",
    "Смирнова Ольга Викторовна",
    "Кузнецов Дмитрий Сергеевич",
    "Попова Мария Андреевна",
]
CITIES = ["г. Москва", "г. Санкт-Петербург", "г. Казань", "г. Екатеринбург", "г. Новосибирск"]


def _h(inn: str, salt: str = "") -> int:
    return int(hashlib.sha256(f"{salt}{inn}".encode()).hexdigest()[:12], 16)


class FnsClient(Protocol):
    async def company(self, inn: str) -> dict[str, Any]: ...


class BkiClient(Protocol):
    async def report(self, inn: str) -> dict[str, Any]: ...


class MockFns:
    async def company(self, inn: str) -> dict[str, Any]:
        n = _h(inn, "fns")
        okved = OKVED[n % len(OKVED)]
        registered = date(2016, 1, 1) + timedelta(days=n % 3000)
        liquidating = inn.startswith("00")
        legal = "ip" if len(inn) == 12 else "ooo"
        return {
            "inn": inn,
            "legal": legal,
            "status": "liquidating" if liquidating else "active",
            "status_text": "В стадии ликвидации" if liquidating else "Действующая организация",
            "name": ("ИП " if legal == "ip" else "ООО «")
            + HEADS[n % len(HEADS)].split()[0]
            + ("" if legal == "ip" else "-Групп»"),
            "registered_at": registered.isoformat(),
            "okved": {"code": okved[0], "title": okved[1]},
            "head": HEADS[(n // 7) % len(HEADS)],
            "founders": [HEADS[(n // 11) % len(HEADS)]],
            "address": f"{CITIES[n % len(CITIES)]}, ул. Примерная, д. {n % 90 + 1}",
            "risk_flags": ["Ликвидация"] if liquidating else [],
            "source": "Симулятор ЕГРЮЛ / «Прозрачный бизнес»",
        }


class MockBki:
    async def report(self, inn: str) -> dict[str, Any]:
        n = _h(inn, "bki")
        overdue = inn.endswith("99")
        loans = n % 4
        return {
            "inn": inn,
            "active_loans": loans,
            "total_obligations": loans * (150_000 + n % 400_000),
            "overdue": overdue,
            "overdue_amount": 180_000 if overdue else 0,
            "max_delay_days": 47 if overdue else 0,
            "discipline": "Есть просрочка" if overdue else "Платежи исполняются в срок",
            "source": "Симулятор БКИ",
        }


class MockEsign:
    async def sign(self, application_id: str, signer: str) -> dict[str, Any]:
        digest = hashlib.sha256(f"{application_id}:{signer}".encode()).hexdigest()[:16].upper()
        return {"signature_id": f"SIG-{digest}", "algorithm": "DEMO-SHA256", "legal_force": False}


class MockPayout:
    async def disburse(self, application_id: str, amount: float) -> dict[str, Any]:
        digest = hashlib.sha256(f"{application_id}:{amount}".encode()).hexdigest()[:12].upper()
        return {
            "payment_id": f"PAY-{digest}",
            "amount": amount,
            "status": "simulated",
            "real_transfer": False,
        }


fns: FnsClient = MockFns()
bki: BkiClient = MockBki()
esign = MockEsign()
payout = MockPayout()
