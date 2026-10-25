"""Контракт входа, результата и LLM-контекста кредитного советника."""

from dataclasses import dataclass
from typing import TypedDict

from scoring.schema import ScoringInput


class LlmCandidate(TypedDict):
    """Вычисленный продукт для ранжирования языковой моделью.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        preliminary_approval_probability: Предварительная оценка вероятности одобрения.
        risk_probability: Оценка скорингового риска.
        context_relevance: Соответствие продукта контексту клиента.
        combined_score: Общая оценка кандидата.
        reasons: Основания предварительного выбора.
    """

    product_id: str
    preliminary_approval_probability: float
    risk_probability: float
    context_relevance: float
    combined_score: float
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class CreditAdvisorInput:
    """Данные для проверки вариантов кредита до создания заявки.

    Attributes:
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        purpose: Цель кредита.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        debt_to_revenue_ratio: Отношение долга к выручке.
        has_overdue_debt: Признак просроченного долга.
        credit_history_score: Оценка кредитной истории.
        has_collateral: Наличие залога.
        legal_form: Организационно-правовая форма.
        has_marketplace_sales: Наличие продаж на маркетплейсах.
        has_existing_business_loans: Наличие действующих кредитов.
        context_tags: Метки потребностей бизнеса.
    """

    requested_amount: int
    term_months: int
    purpose: str
    business_age_months: int
    monthly_revenue: int
    net_margin_percent: float
    debt_to_revenue_ratio: float
    has_overdue_debt: bool
    credit_history_score: int
    has_collateral: bool
    legal_form: str
    has_marketplace_sales: bool
    has_existing_business_loans: bool
    context_tags: tuple[str, ...] = ()

    def scoring_input(self, product_id: str) -> ScoringInput:
        """Создаёт вход существующего scoring engine для кандидата.

        Args:
            product_id: Идентификатор кредитного продукта.

        Returns:
            ScoringInput: Входные признаки скоринга.
        """
        return ScoringInput(
            product_id=product_id,
            requested_amount=self.requested_amount,
            term_months=self.term_months,
            business_age_months=self.business_age_months,
            monthly_revenue=self.monthly_revenue,
            net_margin_percent=self.net_margin_percent,
            debt_to_revenue_ratio=self.debt_to_revenue_ratio,
            has_overdue_debt=self.has_overdue_debt,
            credit_history_score=self.credit_history_score,
            has_collateral=self.has_collateral,
            legal_form=self.legal_form,
        )


@dataclass(frozen=True, slots=True)
class CreditRecommendation:
    """Подходящий кредитный продукт с синтетической предварительной оценкой.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        preliminary_approval_probability: Предварительная оценка вероятности одобрения.
        risk_probability: Предварительная вероятность риска.
        context_relevance: Соответствие продукта контексту бизнеса.
        combined_score: Общая оценка кандидата.
        reasons: Причины выбора или отказа.
    """

    product_id: str
    preliminary_approval_probability: float
    risk_probability: float
    context_relevance: float
    combined_score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CreditAdvice:
    """Результат для интерфейса и безопасный структурированный контекст для LLM.

    Attributes:
        recommendations: Ранжированные рекомендации.
        excluded_product_ids: Идентификаторы исключённых продуктов.
    """

    recommendations: tuple[CreditRecommendation, ...]
    excluded_product_ids: tuple[str, ...]

    def llm_context(self) -> dict[str, object]:
        """Передаёт LLM только вычисленные варианты, без права менять product_id.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        return {
            "recommendations": self.llm_candidates(),
            "excluded_product_ids": list(self.excluded_product_ids),
        }

    def llm_candidates(self) -> list[LlmCandidate]:
        """Возвращает структурированные варианты для ранжирования LLM.

        Returns:
            Кандидаты с оценками и причинами выбора.
        """
        return [
            {
                "product_id": item.product_id,
                "preliminary_approval_probability": item.preliminary_approval_probability,
                "risk_probability": item.risk_probability,
                "context_relevance": item.context_relevance,
                "combined_score": item.combined_score,
                "reasons": list(item.reasons),
            }
            for item in self.recommendations
        ]
