"""Поиск реалистичных сценарных изменений с повторным скорингом."""

from __future__ import annotations

from itertools import combinations

from credit_advisor.config import PRODUCT_RULES
from financial_intelligence.config import CONFIG, FinancialConfig
from financial_intelligence.forecast import forecast_financials
from financial_intelligence.schema import (
    ForecastResponse,
    QuestAction,
    QuestPlan,
    QuestRequest,
    QuestResponse,
    RecalculateRequest,
    RecalculateResponse,
    SimulationRequest,
    SimulationResponse,
)
from financial_intelligence.simulation import simulate_finances
from scoring import ScoringEngine
from scoring.schema import ScoringInput


def _actions(request: QuestRequest, config: FinancialConfig) -> list[QuestAction]:
    """Строит допустимые действия только из подтверждённого снимка.

    Args:
        request: Данные бизнеса и заявки.
        config: Доли перебора и требования к резерву.

    Returns:
        list[QuestAction]: Допустимые действия для сценарного расчёта.
    """
    actions = []
    amount = request.scoring.requested_amount
    rule = PRODUCT_RULES.get(request.scoring.product_id)
    minimum = max(request.minimum_acceptable_amount, rule.min_amount if rule else 0)
    for fraction in config.quest_amount_fractions:
        target = round(amount * fraction)
        if target >= minimum and target >= request.loan.old_debt_payoff:
            actions.append(
                QuestAction(
                    type="reduce_loan_amount",
                    from_value=amount,
                    to_value=target,
                    cost=0,
                    months_to_achieve=0,
                    verification="Подтвердить, что меньшая сумма покрывает цель кредита.",
                )
            )
    expense = request.forecast_request.history[-1].operating_expenses
    for fraction in config.quest_expense_fractions:
        if expense:
            actions.append(
                QuestAction(
                    type="reduce_monthly_expenses",
                    from_value=expense,
                    to_value=round(expense * (1 - fraction)),
                    cost=0,
                    months_to_achieve=3,
                    verification="Подтвердить устойчивое снижение расходов выписками за новые месяцы.",
                )
            )
    balance = request.existing_debt_balance
    cash = request.forecast_request.history[-1].cash_balance
    reserve = round(expense * config.minimum_cash_reserve_months)
    for fraction in config.quest_debt_fractions:
        repayment = round(balance * fraction)
        if repayment and repayment <= cash - reserve:
            actions.append(
                QuestAction(
                    type="repay_existing_debt",
                    from_value=balance,
                    to_value=balance - repayment,
                    cost=repayment,
                    months_to_achieve=1,
                    verification="Подтвердить досрочное погашение и новый график платежей.",
                )
            )
    return actions


def _scenario(
    request: QuestRequest,
    actions: list[QuestAction],
    scoring: ScoringEngine,
    config: FinancialConfig,
) -> tuple[QuestPlan, ForecastResponse, SimulationResponse]:
    """Пересчитывает весь сценарий после набора действий.

    Args:
        request: Исходные данные и порог.
        actions: Выбранные допустимые действия.
        scoring: Исходный скоринговый движок.
        config: Финансовые допущения.

    Returns:
        tuple[QuestPlan, ForecastResponse, SimulationResponse]: План, прогноз и денежный путь.
    """
    values = request.scoring.model_dump()
    forecast = forecast_financials(request.forecast_request, config)
    loan = request.loan
    cash_cost = 0
    debt_payment_reduction = 0
    for action in actions:
        if action.type == "reduce_loan_amount":
            old_amount = loan.amount
            new_amount = int(action.to_value)
            investment = min(
                new_amount - loan.old_debt_payoff,
                round(loan.investment_amount * new_amount / old_amount),
            )
            investment_ratio = investment / loan.investment_amount if loan.investment_amount else 0.0
            loan = loan.model_copy(
                update={
                    "amount": new_amount,
                    "investment_amount": investment,
                    "monthly_revenue_effect": round(loan.monthly_revenue_effect * investment_ratio),
                    "monthly_expense_effect": round(loan.monthly_expense_effect * investment_ratio),
                }
            )
            values["requested_amount"] = new_amount
        elif action.type == "reduce_monthly_expenses":
            reduction = int(action.from_value) - int(action.to_value)
            forecast = forecast.model_copy(
                update={
                    "months": [
                        month.model_copy(update={"operating_expenses": max(0, month.operating_expenses - reduction)})
                        if index >= action.months_to_achieve
                        else month
                        for index, month in enumerate(forecast.months)
                    ]
                }
            )
            values["net_margin_percent"] = min(
                100.0, values["net_margin_percent"] + reduction / max(values["monthly_revenue"], 1) * 100
            )
        elif action.type == "repay_existing_debt":
            repayment = action.cost
            cash_cost += repayment
            fraction = repayment / request.existing_debt_balance
            values["debt_to_revenue_ratio"] = max(
                0.0, values["debt_to_revenue_ratio"] - repayment / max(values["monthly_revenue"], 1)
            )
            debt_payment_reduction = round(request.forecast_request.history[-1].existing_debt_payment * fraction)
    if cash_cost:
        forecast = forecast.model_copy(
            update={
                "opening_cash": forecast.opening_cash - cash_cost,
                "months": [
                    month.model_copy(
                        update={"existing_debt_payment": max(0, month.existing_debt_payment - debt_payment_reduction)}
                    )
                    for month in forecast.months
                ],
            }
        )
    result = scoring.score(ScoringInput(**values))
    simulation = simulate_finances(SimulationRequest(forecast=forecast, loan=loan), config)
    projected_score = round((1 - result.risk_probability) * 100)
    plan = QuestPlan(
        actions=actions,
        projected_score=projected_score,
        target_reached=projected_score >= request.target_score,
        minimum_cash=simulation.scenarios[0].minimum_cash,
        cost=cash_cost,
        months_to_achieve=max((action.months_to_achieve for action in actions), default=0),
    )
    return plan, forecast, simulation


def generate_quest(request: QuestRequest, scoring: ScoringEngine, config: FinancialConfig = CONFIG) -> QuestResponse:
    """Ищет до трёх полезных достижимых сценариев из одного или двух действий.

    Args:
        request: Финансовая история, заявка и цель.
        scoring: Тот же скоринг, что и в кредитном конвейере.
        config: Конфигурация перебора.

    Returns:
        QuestResponse: Ранжированные сценарии без обещания одобрения.
    """
    baseline = scoring.score(request.scoring.to_domain())
    baseline_score = round((1 - baseline.risk_probability) * 100)
    if baseline_score >= request.target_score:
        return QuestResponse(
            company_id=request.forecast_request.company_id,
            baseline_score=baseline_score,
            target_score=request.target_score,
            plans=[],
            scoring_model_version=baseline.model_version,
        )
    baseline_forecast = forecast_financials(request.forecast_request, config)
    baseline_cash = simulate_finances(SimulationRequest(forecast=baseline_forecast, loan=request.loan), config)
    baseline_minimum_cash = baseline_cash.scenarios[0].minimum_cash
    available = _actions(request, config)
    plans: list[QuestPlan] = []
    for size in (1, 2):
        for selected in combinations(available, size):
            if len({action.type for action in selected}) != size:
                continue
            plan, _, _ = _scenario(request, list(selected), scoring, config)
            if plan.projected_score > baseline_score and (
                plan.minimum_cash >= 0 or plan.minimum_cash >= baseline_minimum_cash
            ):
                plans.append(plan)
    plans.sort(
        key=lambda item: (
            not item.target_reached,
            item.minimum_cash < 0,
            max(0, request.target_score - item.projected_score),
            item.cost,
            item.months_to_achieve,
            sum(abs(action.to_value - action.from_value) / max(action.from_value, 1) for action in item.actions),
            -item.minimum_cash,
            -item.projected_score,
        )
    )
    return QuestResponse(
        company_id=request.forecast_request.company_id,
        baseline_score=baseline_score,
        target_score=request.target_score,
        plans=plans[:3],
        scoring_model_version=baseline.model_version,
    )


def recalculate_quest(
    request: RecalculateRequest, scoring: ScoringEngine, config: FinancialConfig = CONFIG
) -> RecalculateResponse:
    """Пересчитывает выбранный план, не доверяя произвольным новым значениям.

    Args:
        request: Исходные данные и выбранные действия.
        scoring: Действующий скоринг.
        config: Финансовые допущения.

    Returns:
        RecalculateResponse: Новый прогноз, путь денег и оценка.

    Raises:
        ValueError: Действие не входит в допустимый набор.
    """
    base = QuestRequest.model_validate(request.model_dump(exclude={"actions"}))
    plans = generate_quest(base, scoring, config).plans
    if not any(plan.actions == request.actions for plan in plans):
        raise ValueError("Выбранное действие не входит в допустимые сценарии для этой заявки.")
    plan, forecast, simulation = _scenario(base, request.actions, scoring, config)
    return RecalculateResponse(
        company_id=base.forecast_request.company_id,
        plan=plan,
        forecast=forecast,
        simulation=simulation,
    )
