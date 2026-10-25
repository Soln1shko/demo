"""Конфигурация конечного поиска условий, а не банковские пороги одобрения."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    """Настройки подбора альтернативного кредита.

    Attributes:
        amount_fractions: Доли исходной суммы для перебора.
        term_fractions: Доли исходного срока для перебора.
        max_variants_per_product: Максимальное число вариантов на продукт.
        min_risk_improvement: Минимальное снижение модельного риска.
    """

    amount_fractions: tuple[float, ...] = (1.0, 0.9, 0.75, 0.5)
    term_fractions: tuple[float, ...] = (1.0, 0.75, 0.5)
    max_variants_per_product: int = 2
    min_risk_improvement: float = 0.01


CONFIG = RecoveryConfig()
