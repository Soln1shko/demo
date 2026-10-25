"""Предварительный выбор кредитных продуктов на основе правил и скоринга."""

from credit_advisor.engine import CreditAdvisor
from credit_advisor.schema import CreditAdvice, CreditAdvisorInput, CreditRecommendation

__all__ = ["CreditAdvice", "CreditAdvisor", "CreditAdvisorInput", "CreditRecommendation"]
