"""Персонализация ленты: условия показа редакционных материалов + динамические подсказки."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PROFILE_LABELS = {"retail": "Торговля", "production": "Производство", "services": "Услуги"}


@dataclass
class FeedContext:
    profile: str = "retail"
    goal: str = ""
    age: int = 0
    revenue: float = 0
    expenses: float = 0
    debt: float = 0
    has_history: bool = False
    app_statuses: dict[str, list[str]] = field(default_factory=dict)  # статус -> id заявок

    @property
    def cash(self) -> float:
        return self.revenue - self.expenses

    @property
    def app_count(self) -> int:
        return sum(len(v) for v in self.app_statuses.values())


def _explain(conditions: dict[str, Any], ctx: FeedContext) -> list[str] | None:
    """Возвращает список причин показа или None, если условия не выполнены."""
    reasons: list[str] = []
    if "profiles" in conditions:
        if ctx.profile not in conditions["profiles"]:
            return None
        reasons.append(f"Отрасль: {PROFILE_LABELS.get(ctx.profile, ctx.profile)}")
    if "goals" in conditions:
        if not any(re.search(g, ctx.goal, re.IGNORECASE) for g in conditions["goals"]):
            return None
        reasons.append(f"Цель: {ctx.goal}")
    if "statuses_any" in conditions:
        if not any(ctx.app_statuses.get(s) for s in conditions["statuses_any"]):
            return None
        reasons.append("Есть заявка в подходящем статусе")
    if conditions.get("no_apps"):
        if ctx.app_count:
            return None
        reasons.append("Заявок пока нет")
    if "max_age" in conditions:
        if ctx.age > conditions["max_age"]:
            return None
        reasons.append(f"Бизнесу {ctx.age} мес.")
    if conditions.get("no_history"):
        if ctx.has_history:
            return None
        reasons.append("Нет помесячной истории показателей")
    if conditions.get("negative_cash"):
        if ctx.cash - ctx.debt >= 0:
            return None
        reasons.append("Остаток после платежей отрицательный")
    return reasons or ["Подходит всем клиентам"]


def dynamic_items(ctx: FeedContext) -> list[dict[str, Any]]:
    """Подсказки, зависящие от текущих заявок клиента."""
    items: list[dict[str, Any]] = []
    s = ctx.app_statuses
    if s.get("needs_info"):
        a = s["needs_info"][0]
        items.append({
            "id": f"dyn:needs_info:{a}", "kind": "action", "icon": "file-clock", "priority": 100,
            "title": "Заявке нужен один документ",
            "body": "Банк запросил сведения. Добавьте документ и отправьте дополнение.",
            "cta": {"label": "Дополнить заявку", "route": f"/app/applications/{a}"},
            "reason": f"Заявка {a} ждёт вашего ответа",
        })  # fmt: skip
    if s.get("approved"):
        a = s["approved"][0]
        items.append({
            "id": f"dyn:approved:{a}", "kind": "action", "icon": "badge-check", "priority": 90,
            "title": "Условия уже одобрены",
            "body": f"Для {a} доступен договор. Можно продолжить без визита в офис.",
            "cta": {"label": "Посмотреть условия", "route": f"/app/applications/{a}"},
            "reason": f"Заявка {a} одобрена",
        })  # fmt: skip
    if s.get("alternative"):
        a = s["alternative"][0]
        items.append({
            "id": f"dyn:alternative:{a}", "kind": "action", "icon": "git-branch", "priority": 85,
            "title": "Банк предложил другие условия",
            "body": "Сравните сумму и платёж. Принять предложение можно в карточке заявки.",
            "cta": {"label": "Сравнить условия", "route": f"/app/applications/{a}"},
            "reason": f"По заявке {a} есть альтернатива",
        })  # fmt: skip
    if s.get("signed"):
        a = s["signed"][0]
        items.append({
            "id": f"dyn:signed:{a}", "kind": "action", "icon": "wallet", "priority": 80,
            "title": "Осталось подтвердить получение",
            "body": "Договор подписан. Подтвердите получение средств в карточке заявки.",
            "cta": {"label": "Открыть заявку", "route": f"/app/applications/{a}"},
            "reason": f"Заявка {a} подписана",
        })  # fmt: skip
    if s.get("rejected"):
        a = s["rejected"][0]
        items.append({
            "id": f"dyn:rejected:{a}", "kind": "action", "icon": "info", "priority": 70,
            "title": "Что делать после отказа",
            "body": "Причина решения в карточке. Можно снизить нагрузку и подать новую заявку.",
            "cta": {"label": "Посмотреть причины", "route": f"/app/applications/{a}"},
            "reason": f"По заявке {a} отказ",
        })  # fmt: skip
    return items


def select_feed(
    editorial: list[dict[str, Any]], ctx: FeedContext, dismissed: set[str], limit: int = 10
) -> list[dict[str, Any]]:
    """Собирает ленту: динамические подсказки + подходящие редакционные материалы."""
    out = [i for i in dynamic_items(ctx) if i["id"] not in dismissed]
    for item in editorial:
        if not item.get("active", True) or item["id"] in dismissed:
            continue
        reasons = _explain(item.get("conditions") or {}, ctx)
        if reasons is None:
            continue
        out.append({**item, "reason": "; ".join(reasons)})
    out.sort(key=lambda i: -int(i.get("priority", 0)))
    return out[:limit]
