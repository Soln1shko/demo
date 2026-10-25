"""Мгновенный локальный перебор суммы и срока с существующими весами скоринга."""

from __future__ import annotations

from dataclasses import replace

from credit_advisor.config import PRODUCT_RULES
from credit_advisor.engine import eligibility_reasons
from offer_recovery.config import CONFIG, RecoveryConfig
from offer_recovery.schema import RecoveredVariant, RecoveryRequest, RecoveryResponse, RejectedProduct, SuggestedTerms
from scoring import ScoringEngine


def recover_offers(
    request: RecoveryRequest, scoring: ScoringEngine, config: RecoveryConfig = CONFIG
) -> RecoveryResponse:
    """Пересчитывает локальную формулу для допустимых условий без сетевых вызовов.

    Args:
        request: Проверенные входные данные.
        scoring: Полученные результаты скоринга.
        config: Типизированные настройки сервиса.

    Returns:
        RecoveryResponse: Подходящие альтернативные условия кредита.

    Raises:
        ValueError: Входные данные нарушают ограничения домена.
    """
    base = request.profile.to_domain()
    declined = {(item.product_id, item.requested_amount, item.term_months) for item in request.declined_offers}
    previous = request.declined_offers[-1]
    baseline = replace(base, requested_amount=previous.requested_amount, term_months=previous.term_months)
    baseline_risk = scoring.score(baseline.scoring_input(previous.product_id)).risk_probability
    variants: list[RecoveredVariant] = []
    unavailable: list[RejectedProduct] = []
    for product_id in request.recommended_product_ids:
        rule = PRODUCT_RULES.get(product_id)
        if rule is None:
            raise ValueError(f"Неизвестный кредитный product_id: {product_id}.")
        candidates: list[RecoveredVariant] = []
        amounts = _candidate_values(
            base.requested_amount,
            request.minimum_acceptable_amount,
            rule.min_amount,
            rule.max_amount,
            config.amount_fractions,
        )
        terms = _candidate_values(
            base.term_months,
            request.minimum_acceptable_term_months,
            rule.min_term_months,
            rule.max_term_months,
            config.term_fractions,
        )
        for amount in amounts:
            for term in terms:
                if (product_id, amount, term) in declined:
                    continue
                candidate = replace(base, requested_amount=amount, term_months=term)
                if eligibility_reasons(candidate, rule):
                    continue
                result = scoring.score(candidate.scoring_input(product_id))
                improvement = baseline_risk - result.risk_probability
                if improvement < config.min_risk_improvement:
                    continue
                changed = []
                if amount < base.requested_amount:
                    changed.append("меньшая сумма")
                if term < base.term_months:
                    changed.append("более короткий срок")
                if not changed:
                    changed.append("другой кредитный продукт")
                candidates.append(
                    RecoveredVariant(
                        product_id=product_id,
                        suggested_terms=SuggestedTerms(amount=amount, term_months=term),
                        risk_probability=round(result.risk_probability, 4),
                        risk_band=result.risk_band,
                        risk_change_vs_original=round(-improvement, 4),
                        model_version=result.model_version,
                        explanation=f"Предварительная оценка риска ниже: {', '.join(changed)}.",
                    )
                )
        candidates.sort(
            key=lambda item: (item.risk_probability, -item.suggested_terms.amount, -item.suggested_terms.term_months)
        )
        if candidates:
            selected = [candidates[0]]
            closest = max(
                candidates,
                key=lambda item: (
                    item.suggested_terms.amount,
                    item.suggested_terms.term_months,
                    -item.risk_probability,
                ),
            )
            if closest != selected[0] and config.max_variants_per_product > 1:
                selected.append(closest)
            variants.extend(selected)
        else:
            reasons = eligibility_reasons(base, rule)
            unavailable.append(
                RejectedProduct(
                    product_id=product_id,
                    reasons=list(reasons) or ["Для допустимых условий оценка риска не улучшилась достаточно."],
                )
            )
    variants.sort(key=lambda item: (item.risk_probability, -item.suggested_terms.amount, item.product_id))
    return RecoveryResponse(
        case_id=request.case_id,
        variants=variants,
        unavailable_products=unavailable,
        declined_reasons=list(dict.fromkeys(reason for item in request.declined_offers for reason in item.reasons)),
    )


def _candidate_values(
    current: int, acceptable_min: int, product_min: int, product_max: int, fractions: tuple[float, ...]
) -> tuple[int, ...]:
    """Строит допустимые суммы и сроки для продукта.

    Args:
        current: Исходное значение.
        acceptable_min: Минимум, приемлемый для клиента.
        product_min: Минимум по правилам продукта.
        product_max: Максимум по правилам продукта.
        fractions: Доли базового значения для перебора.

    Returns:
        tuple[int, ...]: Числовые значения.
    """
    minimum = max(acceptable_min, product_min, 1)
    maximum = min(current, product_max)
    if minimum > maximum:
        return ()
    values = {minimum, maximum}
    values.update(max(minimum, min(maximum, round(current * fraction))) for fraction in fractions)
    return tuple(sorted(values, reverse=True))
