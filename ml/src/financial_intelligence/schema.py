"""Строгие HTTP-контракты Business Twin и Credit Quest."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.model import StrictModel
from app.schemas import ScoringRequest


class FinancialMonth(StrictModel):
    """Один месяц синтетической финансовой истории.

    Attributes:
        month: Первый день календарного месяца.
        revenue: Денежные поступления.
        operating_expenses: Операционные платежи без налогов и долга.
        taxes: Уплаченные налоги.
        existing_debt_payment: Платёж по действующему долгу.
        cash_balance: Остаток денег на конец месяца.
    """

    month: date
    revenue: int = Field(ge=0)
    operating_expenses: int = Field(ge=0)
    taxes: int = Field(ge=0)
    existing_debt_payment: int = Field(ge=0)
    cash_balance: int


class ForecastRequest(StrictModel):
    """История бизнеса для локального baseline-прогноза.

    Attributes:
        company_id: Заведомо демонстрационный ID компании.
        industry: Отрасль бизнеса.
        business_age_months: Возраст бизнеса.
        history: Последовательные месячные наблюдения.
        horizon_months: Горизонт прогноза.
    """

    company_id: str = Field(pattern=r"^demo_[a-z0-9_-]{1,32}$")
    industry: str = Field(min_length=1, max_length=80)
    business_age_months: int = Field(ge=0)
    history: list[FinancialMonth] = Field(min_length=6, max_length=36)
    horizon_months: int = Field(default=12, ge=1, le=12)

    @model_validator(mode="after")
    def consecutive_months(self) -> ForecastRequest:
        """Запрещает пропуски и перестановку месяцев.

        Returns:
            ForecastRequest: Проверенный временной ряд.

        Raises:
            ValueError: История не образует последовательный ряд.
        """
        for index, item in enumerate(self.history):
            if item.month.day != 1:
                raise ValueError("month должен быть первым днём месяца.")
            if index:
                previous = self.history[index - 1].month
                expected_year = previous.year + (previous.month == 12)
                expected_month = previous.month % 12 + 1
                if (item.month.year, item.month.month) != (expected_year, expected_month):
                    raise ValueError("history должна содержать последовательные месяцы без пропусков.")
        return self


class ForecastMonth(StrictModel):
    """Прогноз денежных поступлений и расходов на месяц.

    Attributes:
        month: Первый день прогнозного месяца.
        revenue: Центральный прогноз поступлений.
        revenue_low: Нижняя граница сценарного интервала.
        revenue_high: Верхняя граница сценарного интервала.
        operating_expenses: Центральный прогноз операционных платежей.
        expenses_low: Нижняя граница сценарного интервала расходов.
        expenses_high: Верхняя граница сценарного интервала расходов.
        taxes: Прогноз налоговых платежей.
        existing_debt_payment: Прогноз старого долгового платежа.
    """

    month: date
    revenue: int = Field(ge=0)
    revenue_low: int = Field(ge=0)
    revenue_high: int = Field(ge=0)
    operating_expenses: int = Field(ge=0)
    expenses_low: int = Field(ge=0)
    expenses_high: int = Field(ge=0)
    taxes: int = Field(ge=0)
    existing_debt_payment: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered_intervals(self) -> ForecastMonth:
        """Проверяет порядок сценарных границ.

        Returns:
            ForecastMonth: Согласованные границы прогноза.

        Raises:
            ValueError: Центральное значение не лежит между границами.
        """
        if not self.revenue_low <= self.revenue <= self.revenue_high:
            raise ValueError("Прогноз выручки должен лежать внутри своего диапазона.")
        if not self.expenses_low <= self.operating_expenses <= self.expenses_high:
            raise ValueError("Прогноз расходов должен лежать внутри своего диапазона.")
        return self


class ForecastResponse(StrictModel):
    """Воспроизводимый baseline с явными ограничениями.

    Attributes:
        company_id: ID компании.
        opening_cash: Последний фактический остаток.
        months: Помесячный прогноз.
        model_version: Версия модели.
        interval_type: Тип интервала, не статистическая гарантия.
        synthetic: Признак демонстрационного результата.
    """

    company_id: str
    opening_cash: int
    months: list[ForecastMonth] = Field(min_length=1, max_length=12)
    model_version: Literal["seasonal_trend_baseline_1"] = "seasonal_trend_baseline_1"
    interval_type: Literal["heuristic_not_calibrated"] = "heuristic_not_calibrated"
    synthetic: bool = True


class LoanScenario(StrictModel):
    """Кредит и явно заданный экономический эффект.

    Attributes:
        amount: Сумма выдачи.
        term_months: Срок кредита.
        annual_rate_percent: Годовая ставка.
        purpose: Цель финансирования.
        investment_amount: Расход из полученных средств в месяц выдачи.
        monthly_revenue_effect: Целевой прирост месячных поступлений.
        monthly_expense_effect: Прирост месячных операционных платежей.
        ramp_months: Срок выхода на целевой эффект.
        old_debt_payoff: Погашение старого долга при рефинансировании.
        old_payment_reduction: Сокращение старого месячного платежа.
    """

    amount: int = Field(gt=0)
    term_months: int = Field(ge=1, le=120)
    annual_rate_percent: float = Field(ge=0, le=100)
    purpose: Literal["development", "working_capital", "refinancing", "cash_gap"]
    investment_amount: int = Field(default=0, ge=0)
    monthly_revenue_effect: int = Field(default=0, ge=0)
    monthly_expense_effect: int = Field(default=0, ge=0)
    ramp_months: int = Field(default=1, ge=1, le=12)
    old_debt_payoff: int = Field(default=0, ge=0)
    old_payment_reduction: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_uses(self) -> LoanScenario:
        """Проверяет расходование средств и смысл рефинансирования.

        Returns:
            LoanScenario: Проверенный кредитный сценарий.

        Raises:
            ValueError: Использование средств противоречиво.
        """
        if self.investment_amount + self.old_debt_payoff > self.amount:
            raise ValueError("Инвестиции и погашение старого долга превышают сумму кредита.")
        if not self.investment_amount and (self.monthly_revenue_effect or self.monthly_expense_effect):
            raise ValueError("Экономический эффект требует положительной суммы инвестиций.")
        if self.purpose != "refinancing" and (self.old_debt_payoff or self.old_payment_reduction):
            raise ValueError("Погашение старого долга допустимо только для рефинансирования.")
        if self.purpose == "refinancing" and (not self.old_debt_payoff or not self.old_payment_reduction):
            raise ValueError("Для рефинансирования нужны сумма погашения и снижение старого платежа.")
        return self


class SimulationRequest(StrictModel):
    """Вход сравнения денежных сценариев без вызова LLM.

    Attributes:
        forecast: Результат прогноза.
        loan: Необязательный новый кредит.
    """

    forecast: ForecastResponse
    loan: LoanScenario | None = None


class CashMonth(StrictModel):
    """Помесячный остаток и обслуживание кредита.

    Attributes:
        month: Месяц сценария.
        revenue: Денежные поступления от операций.
        operating_expenses: Операционные платежи.
        taxes: Налоговые платежи.
        existing_debt_payment: Платёж по старому долгу.
        new_loan_payment: Платёж по новому кредиту.
        remaining_principal: Остаток основного долга нового кредита.
        loan_disbursement: Выдача нового кредита.
        investment_and_payoff: Инвестиции и закрытие старого долга.
        closing_cash: Остаток на конец месяца.
    """

    month: date
    revenue: int
    operating_expenses: int
    taxes: int
    existing_debt_payment: int
    new_loan_payment: int
    remaining_principal: int
    loan_disbursement: int
    investment_and_payoff: int
    closing_cash: int


class ScenarioResult(StrictModel):
    """Одна детерминированная траектория.

    Attributes:
        name: Имя сценария.
        months: Денежный поток по месяцам.
        minimum_cash: Минимальный остаток.
    """

    name: Literal["base", "optimistic", "stress"]
    months: list[CashMonth]
    minimum_cash: int


class SimulationResponse(StrictModel):
    """Помесячные денежные сценарии бизнеса.

    Attributes:
        company_id: ID компании.
        has_loan: Признак сценария с новым кредитом.
        monthly_payment: Аннуитетный платёж нового кредита.
        scenarios: Три траектории.
        guarantees_approval: Признак отсутствия гарантии.
    """

    company_id: str
    has_loan: bool
    monthly_payment: int
    scenarios: list[ScenarioResult]
    guarantees_approval: Literal[False] = False


class QuestRequest(StrictModel):
    """Профиль, заявка и история для поиска допустимых действий.

    Attributes:
        forecast_request: Финансовая история компании.
        scoring: Поля действующего скоринга.
        loan: Кредит с явными сценарными предположениями.
        target_score: Целевой условный балл.
        existing_debt_balance: Подтверждённый остаток старого долга.
        minimum_acceptable_amount: Минимальная полезная сумма кредита.
    """

    forecast_request: ForecastRequest
    scoring: ScoringRequest
    loan: LoanScenario
    target_score: int = Field(default=70, ge=0, le=100)
    existing_debt_balance: int = Field(default=0, ge=0)
    minimum_acceptable_amount: int = Field(gt=0)

    @model_validator(mode="after")
    def compatible_inputs(self) -> QuestRequest:
        """Запрещает несовместимые снимки бизнеса.

        Returns:
            QuestRequest: Согласованные входные данные.

        Raises:
            ValueError: Финансовые и скоринговые поля расходятся.
        """
        if self.minimum_acceptable_amount > self.scoring.requested_amount:
            raise ValueError("Минимально приемлемая сумма больше исходной.")
        if self.loan.amount != self.scoring.requested_amount or self.loan.term_months != self.scoring.term_months:
            raise ValueError("Сумма и срок кредита должны совпадать с заявкой скоринга.")
        if self.scoring.monthly_revenue != self.forecast_request.history[-1].revenue:
            raise ValueError("Выручка скоринга должна совпадать с последним месяцем истории.")
        if self.scoring.business_age_months != self.forecast_request.business_age_months:
            raise ValueError("Возраст бизнеса должен совпадать в скоринге и истории.")
        return self


class QuestAction(StrictModel):
    """Допустимое изменение, требующее подтверждения.

    Attributes:
        type: Вид изменения.
        from_value: Исходное значение.
        to_value: Сценарное значение.
        cost: Прямой расход денег бизнеса.
        months_to_achieve: Оценка срока реализации.
        verification: Что нужно подтвердить.
    """

    type: Literal["reduce_loan_amount", "reduce_monthly_expenses", "repay_existing_debt"]
    from_value: int | float
    to_value: int | float
    cost: int
    months_to_achieve: int
    verification: str


class QuestPlan(StrictModel):
    """Предварительный контрфактический план.

    Attributes:
        actions: Изменения параметров.
        projected_score: Пересчитанный условный балл.
        target_reached: Достижение целевого балла.
        minimum_cash: Минимальный остаток денег по базовому сценарию.
        cost: Прямой расход денег.
        months_to_achieve: Максимальный срок действий.
        requires_verification: Необходимость подтверждения.
        guarantees_approval: Отсутствие гарантии.
    """

    actions: list[QuestAction]
    projected_score: int
    target_reached: bool
    minimum_cash: int
    cost: int
    months_to_achieve: int
    requires_verification: Literal[True] = True
    guarantees_approval: Literal[False] = False


class QuestResponse(StrictModel):
    """Лучшие достижимые варианты без обещания одобрения.

    Attributes:
        company_id: ID компании.
        baseline_score: Условный балл исходной заявки.
        target_score: Целевой условный балл.
        plans: До трёх сценарных планов.
        scoring_model_version: Версия скоринга.
        synthetic: Признак демонстрационного результата.
    """

    company_id: str
    baseline_score: int
    target_score: int
    plans: list[QuestPlan]
    scoring_model_version: str
    synthetic: bool = True


class RecalculateRequest(QuestRequest):
    """Повторный расчёт одного выбранного плана.

    Attributes:
        actions: Сценарные действия, выбранные клиентом.
    """

    actions: list[QuestAction] = Field(min_length=1, max_length=2)


class RecalculateResponse(StrictModel):
    """Результат выбранного сценария.

    Attributes:
        company_id: ID компании.
        plan: Пересчитанный план.
        forecast: Финансовый прогноз после действия.
        simulation: Денежные потоки после действия.
        synthetic: Признак демонстрационного результата.
    """

    company_id: str
    plan: QuestPlan
    forecast: ForecastResponse
    simulation: SimulationResponse
    synthetic: bool = True
