"""Сценарный помощник (fallback без LLM). Отвечает только на основе данных заявок и правил."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

STATUS_LABELS = {
    "draft": "Черновик",
    "submitted": "На проверке",
    "checking": "Идёт проверка",
    "review": "Ручной анализ",
    "needs_info": "Нужны документы",
    "approved": "Одобрено",
    "alternative": "Другие условия",
    "rejected": "Отказ",
    "signed": "Договор подписан",
    "funded": "Кредит выдан",
    "withdrawn": "Отозвана",
}


@dataclass
class AssistantContext:
    last_app_id: str | None = None
    last_app_status: str | None = None
    last_app_comment: str | None = None
    last_app_product: str | None = None
    last_app_amount: float | None = None
    last_app_info: str | None = None
    recommended_product: dict[str, Any] | None = None


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def answer(question: str, ctx: AssistantContext) -> tuple[str, dict[str, Any] | None]:
    q = question.strip()
    if _has(r"^(привет|здравствуй(те)?|добрый (день|вечер|утро)|хай)[!.,\s]*$", q):
        text = (
            "Здравствуйте! Я Иришка. Помогу разобраться с заявкой, документами и платежом. Что хотите узнать?"
        )
    elif _has("документ|подготов|выписк", q):
        text = (
            "Подготовьте выписку за последние 6 месяцев и проверьте ИНН, выручку и действующие платежи. "
            "Если банк запросил уточнение, добавьте документ в карточке заявки."
        )
    elif _has("платеж|платёж|уменьш", q):
        text = (
            "Меньшая сумма снизит платёж. Увеличение срока тоже поможет, но повысит переплату. "
            "Раскройте продукт в разделе финансирования: внутри можно менять сумму, срок и проверять падение выручки."
        )
    elif _has("отказ|решени", q):
        text = (
            "Причина решения находится в карточке заявки. При высокой нагрузке можно рассмотреть меньшую сумму. "
            "Если нужны пояснения, передам вопрос оператору."
        )
    elif _has("заявк|статус|дальше", q):
        if ctx.last_app_id and ctx.last_app_status:
            label = STATUS_LABELS.get(ctx.last_app_status, ctx.last_app_status)
            who = f"Заявка {ctx.last_app_id}"
            if ctx.last_app_product:
                who += f" ({ctx.last_app_product})"
            bits = [f"{who}: {label}."]
            if ctx.last_app_amount:
                bits.append(f"Сумма {int(ctx.last_app_amount):,} ₽.".replace(",", " "))
            if ctx.last_app_status == "needs_info" and ctx.last_app_info:
                bits.append(f"Банк ждёт: {ctx.last_app_info}.")
            elif ctx.last_app_comment:
                bits.append(ctx.last_app_comment)
            else:
                bits.append("Следующий шаг указан в карточке заявки.")
            text = " ".join(bits)
        else:
            text = "Заявок пока нет. Начните с подбора продукта: он покажет платёж и запас денег."
    else:
        text = (
            "Могу помочь с документами, статусом заявки и расчётом платежа. "
            "Если вопрос выходит за эти темы, нажмите «Позвать оператора»."
        )

    card = None
    if _has("кассов|оборот|оборудован|продукт|выбрать", q) and ctx.recommended_product:
        card = ctx.recommended_product
    return text, card
