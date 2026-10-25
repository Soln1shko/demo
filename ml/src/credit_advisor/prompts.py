"""Промпт для безопасного LLM-ранжирования уже проверенных кредитов."""

from __future__ import annotations

import json

PRODUCT_RANKING_SYSTEM_PROMPT = """Ты кредитный консультант в демонстрационном прототипе.
Ранжируй ТОЛЬКО product_id из списка eligible_products. Не добавляй другие ID и не выдавай одобрение.
Учитывай полный профиль, обязательные условия, предварительный риск, контекст и назначение продукта.
Верни только валидный JSON без Markdown: {"recommendations":[{"product_id":"...","reason":"..."}]}.
reason — короткая причина на русском, основанная на входных данных."""


def product_ranking_prompt(profile: dict[str, object], eligible_products: dict[str, object], top_n: int) -> str:
    """Передаёт LLM профиль и допустимых кандидатов, прошедших правила.

    Args:
        profile: Профиль клиента или бизнеса.
        eligible_products: Продукты, прошедшие проверку правил.
        top_n: Максимальное число вариантов.

    Returns:
        str: Сформированный текст.
    """
    return (
        f"Профиль и параметры запроса:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"eligible_products (только эти ID разрешены):\n{json.dumps(eligible_products, ensure_ascii=False)}\n\n"
        f"Верни ровно до {top_n} рекомендаций в порядке убывания релевантности."
    )
