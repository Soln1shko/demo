"""Подбор продуктов под задачу бизнеса (объяснимые правила, не одобрение)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.finance import ProductSpec


@dataclass
class MatchProfile:
    goal: str = ""
    amount: float = 1_000_000
    months: int = 24
    frequency: str = "once"
    collateral: str = "no"
    age: int = 0
    late: bool = False


@dataclass
class MatchResult:
    score: int
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def match_product(p: ProductSpec, o: MatchProfile) -> MatchResult:
    score = 40
    reasons: list[str] = []
    warnings: list[str] = []
    goal = o.goal or ""

    if _has("кассов", goal) and p.kind == "overdraft":
        score += 45
        reasons.append("Короткий разрыв до поступления выручки")
    if o.frequency == "regular" and p.kind == "line":
        score += 35
        reasons.append("Лимит восстанавливается после погашения")
    if _has("оборуд|развит|рефинанс", goal) and p.kind == "loan":
        score += 25
        reasons.append("Подходит для единовременного вложения")
    if _has("товар", goal) and p.id in ("business_loan", "credit_line", "alfa_start"):
        score += 25
        reasons.append("Для закупки товара и оборотных расходов")
    if _has("недвиж", goal) and p.id == "business_mortgage":
        score += 65
        reasons.append("Покупаемое помещение становится залогом")
    if p.id == "business_mortgage" and not _has("недвиж", goal):
        score -= 50
    if p.secured and (o.collateral == "no" or not o.collateral):
        score -= 65
        warnings.append("Нужно залоговое обеспечение")
    if o.collateral == "transport" and p.id == "business_pledge_loan":
        warnings.append("При залоге транспорта срок до 5 лет; базовая ставка 25,5%")
        score += 10
    if p.min_age > o.age:
        score -= 45
        warnings.append(f"Бизнес должен работать от {p.min_age} месяцев")
    if o.amount > p.max_amount:
        score -= 40
        warnings.append("Запрошенная сумма выше лимита продукта")
    if o.amount < p.min_amount:
        score -= 25
        warnings.append("Сумма ниже минимума продукта")
    if o.months > p.max_months and p.kind != "overdraft":
        score -= 15
        warnings.append("Нужно сократить срок или уточнить специальные условия")
    if o.late:
        warnings.append("Текущая просрочка требует отдельного рассмотрения")
        score -= 15
    if p.kind == "daily":
        score -= 15
    if not reasons:
        reasons.append(
            "Можно рассмотреть при наличии обеспечения"
            if p.secured
            else "Один из вариантов финансирования бизнеса"
        )
    return MatchResult(score, reasons, warnings)
