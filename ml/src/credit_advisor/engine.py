"""Оркестрация проверки условий и risk scoring для выбора кредита."""

from __future__ import annotations

from credit_advisor.config import PRODUCT_RULES, RANKING, ProductRule
from credit_advisor.schema import CreditAdvice, CreditAdvisorInput, CreditRecommendation
from scoring import ScoringEngine


class CreditAdvisor:
    """Возвращает ранжированные подходящие продукты, не кредитное решение.

    Attributes:
        _scoring_engine:  скоринг движок.
    """

    def __init__(self, scoring_engine: ScoringEngine) -> None:
        """Инициализирует объект и его зависимости.

        Args:
            scoring_engine: Скоринг движок.
        """
        self._scoring_engine = scoring_engine

    @classmethod
    def default(cls) -> CreditAdvisor:
        """Создаёт советник со стандартными JSON-весами скоринга.

        Returns:
            CreditAdvisor: Сервис со скоринговым движком.
        """
        return cls(ScoringEngine.from_json())

    def recommend(self, request: CreditAdvisorInput, top_n: int = 3) -> CreditAdvice:
        """Проверяет все продукты и возвращает top-N подходящих вариантов.

        Args:
            request: Проверенные входные данные.
            top_n: Максимальное число вариантов.

        Returns:
            CreditAdvice: Предварительно подходящие кредитные продукты.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if top_n < 1:
            raise ValueError("top_n должен быть не меньше 1.")
        candidates: list[CreditRecommendation] = []
        excluded: list[str] = []
        for product_id, rule in PRODUCT_RULES.items():
            reasons = eligibility_reasons(request, rule)
            if reasons:
                excluded.append(product_id)
                continue
            risk = self._scoring_engine.score(request.scoring_input(product_id)).risk_probability
            approval_probability = 1.0 - risk
            context_relevance = _context_relevance(request, rule)
            candidates.append(
                CreditRecommendation(
                    product_id=product_id,
                    preliminary_approval_probability=round(approval_probability, 4),
                    risk_probability=round(risk, 4),
                    context_relevance=round(context_relevance, 4),
                    combined_score=round(
                        RANKING.approval_probability_weight * approval_probability
                        + RANKING.context_relevance_weight * context_relevance,
                        4,
                    ),
                    reasons=_recommendation_reasons(request, product_id, rule),
                )
            )
        ranked = sorted(candidates, key=lambda item: (-item.combined_score, item.product_id))
        return CreditAdvice(recommendations=tuple(ranked[:top_n]), excluded_product_ids=tuple(excluded))


def eligibility_reasons(request: CreditAdvisorInput, rule: ProductRule) -> tuple[str, ...]:
    """Возвращает причины несоответствия условиям продукта.

    Args:
        request: Проверенные входные данные.
        rule: Правила кредитного продукта.

    Returns:
        tuple[str, ...]: Строковые значения.
    """
    reasons: list[str] = []
    if not rule.min_amount <= request.requested_amount <= rule.max_amount:
        reasons.append("Сумма не входит в предварительный диапазон продукта.")
    if not rule.min_term_months <= request.term_months <= rule.max_term_months:
        reasons.append("Срок не входит в предварительный диапазон продукта.")
    if request.business_age_months < rule.min_business_age_months:
        reasons.append("Бизнес ещё не достиг минимального срока работы для продукта.")
    if rule.requires_collateral and not request.has_collateral:
        reasons.append("Для продукта требуется обеспечение.")
    if rule.requires_marketplace_sales and not request.has_marketplace_sales:
        reasons.append("Продукт доступен продавцам маркетплейсов.")
    if rule.requires_existing_loans and not request.has_existing_business_loans:
        reasons.append("Для рефинансирования нужен действующий бизнес-кредит.")
    if rule.requires_purpose is not None and request.purpose != rule.requires_purpose:
        reasons.append("Цель заявки не соответствует назначению продукта.")
    return tuple(reasons)


def _context_relevance(request: CreditAdvisorInput, rule: ProductRule) -> float:
    """Оценивает соответствие продукта контексту бизнеса.

    Args:
        request: Проверенные входные данные.
        rule: Правила кредитного продукта.

    Returns:
        float: Вычисленное числовое значение.
    """
    tags = set(request.context_tags) | {request.purpose}
    score = 0.65 if tags & set(rule.context_tags) else 0.0
    if rule.requires_marketplace_sales and request.has_marketplace_sales:
        score += 0.2
    if rule.requires_collateral and request.has_collateral:
        score += 0.1
    if rule.requires_existing_loans and request.has_existing_business_loans:
        score += 0.1
    return min(score, 1.0)


def _recommendation_reasons(request: CreditAdvisorInput, product_id: str, rule: ProductRule) -> tuple[str, ...]:
    """Объясняет предварительный выбор продукта.

    Args:
        request: Проверенные входные данные.
        product_id: Идентификатор кредитного продукта.
        rule: Правила кредитного продукта.

    Returns:
        tuple[str, ...]: Строковые значения.
    """
    reasons = ["Сумма, срок и базовые условия подходят предварительно."]
    if (set(request.context_tags) | {request.purpose}) & set(rule.context_tags):
        reasons.append("Цель и контекст бизнеса совпадают с назначением продукта.")
    if product_id == "seller_credit" and request.has_marketplace_sales:
        reasons.append("Есть продажи на маркетплейсах.")
    if product_id == "overdraft" and request.purpose == "cash_gap":
        reasons.append("Целью указан кассовый разрыв.")
    if product_id == "business_refinancing" and request.has_existing_business_loans:
        reasons.append("Есть действующий бизнес-кредит для рефинансирования.")
    return tuple(reasons)
