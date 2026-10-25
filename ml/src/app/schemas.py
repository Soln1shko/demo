"""Pydantic-контракты HTTP API и преобразование в доменные типы."""

from __future__ import annotations

from pydantic import Field

from app.model import StrictModel
from cash_cap import CashProfile
from credit_advisor import CreditAdvisorInput
from nba import BusinessProfile
from scoring import ScoringInput


class ApiModel(StrictModel):
    """Базовый HTTP-контракт: неизвестные поля запроса запрещены."""


class ScoringRequest(ApiModel):
    """Тело запроса предварительной оценки риска.

    Attributes:
        product_id: Идентификатор кредитного продукта.
        requested_amount: Запрошенная сумма кредита.
        term_months: Срок кредита в месяцах.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        debt_to_revenue_ratio: Отношение долга к выручке.
        has_overdue_debt: Признак просроченного долга.
        credit_history_score: Оценка кредитной истории.
        has_collateral: Наличие залога.
        legal_form: Организационно-правовая форма.
    """

    product_id: str
    requested_amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    business_age_months: int = Field(ge=0)
    monthly_revenue: int = Field(ge=0)
    net_margin_percent: float = Field(ge=0, le=100)
    debt_to_revenue_ratio: float = Field(ge=0)
    has_overdue_debt: bool
    credit_history_score: int = Field(ge=0, le=1000)
    has_collateral: bool
    legal_form: str

    def to_domain(self) -> ScoringInput:
        """Преобразует JSON-тело в контракт scoring engine.

        Returns:
            ScoringInput: Входные признаки скоринга.
        """
        return ScoringInput(**self.model_dump())


class NbaRequest(ApiModel):
    """Тело запроса next-best-action рекомендаций.

    Attributes:
        legal_form: Организационно-правовая форма.
        business_age_months: Возраст бизнеса в месяцах.
        monthly_turnover: Месячный оборот.
        monthly_payment_count: Число платежей в месяц.
        online_sales_share: Доля онлайн-продаж.
        has_business_account: Наличие расчётного счёта.
        has_website: Наличие сайта.
        has_offline_point: Наличие офлайн-точки.
        sells_on_marketplaces: Признак продаж на маркетплейсах.
        employee_count: Количество сотрудников.
        has_foreign_trade: Наличие внешнеэкономической деятельности.
        needs_tax_reporting: Потребность в налоговой отчётности.
        uses_electronic_documents: Признак электронного документооборота.
        wants_business_registration: Запрос регистрации бизнеса.
        existing_product_ids: Идентификаторы уже подключённых продуктов.
        top_n: Максимальное число вариантов.
    """

    legal_form: str
    business_age_months: int = Field(ge=0)
    monthly_turnover: int = Field(ge=0)
    monthly_payment_count: int = Field(ge=0)
    online_sales_share: float = Field(ge=0, le=1)
    has_business_account: bool
    has_website: bool
    has_offline_point: bool
    sells_on_marketplaces: bool
    employee_count: int = Field(ge=0)
    has_foreign_trade: bool
    needs_tax_reporting: bool
    uses_electronic_documents: bool
    wants_business_registration: bool
    existing_product_ids: tuple[str, ...] = ()
    top_n: int = Field(default=3, ge=1, le=18)

    def to_domain(self) -> BusinessProfile:
        """Преобразует JSON-тело в профиль для NBA engine.

        Returns:
            BusinessProfile: Доменный профиль бизнеса.
        """
        payload = self.model_dump(exclude={"top_n"})
        return BusinessProfile(**payload)


class CreditAdvisorRequest(ApiModel):
    """Тело запроса подбора предварительно подходящих кредитов.

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
        top_n: Максимальное число вариантов.
    """

    requested_amount: int = Field(gt=0)
    term_months: int = Field(gt=0)
    purpose: str = Field(min_length=1)
    business_age_months: int = Field(ge=0)
    monthly_revenue: int = Field(ge=0)
    net_margin_percent: float = Field(ge=0, le=100)
    debt_to_revenue_ratio: float = Field(ge=0)
    has_overdue_debt: bool
    credit_history_score: int = Field(ge=0, le=1000)
    has_collateral: bool
    legal_form: str
    has_marketplace_sales: bool
    has_existing_business_loans: bool
    context_tags: tuple[str, ...] = ()
    top_n: int = Field(default=3, ge=1, le=11)

    def to_domain(self) -> CreditAdvisorInput:
        """Преобразует JSON-тело в доменный контракт подбора.

        Returns:
            CreditAdvisorInput: Доменный профиль для подбора кредитов.
        """
        payload = self.model_dump(exclude={"top_n"})
        return CreditAdvisorInput(**payload)


class CashGapRequest(ApiModel):
    """Тело запроса прогноза кассового разрыва.

    Attributes:
        monthly_revenue: Месячная выручка.
        net_margin_percent: Чистая маржа в процентах.
        opening_balance: Начальный остаток средств.
        monthly_fixed_costs: Месячные постоянные расходы.
        sales_volatility: Волатильность продаж.
        payment_delay_days: Задержка платежей в днях.
        upcoming_expenses: Предстоящие расходы.
        simulation_seed: Seed воспроизводимой симуляции.
        forecast_days: Горизонт прогноза.
    """

    monthly_revenue: int = Field(ge=0)
    net_margin_percent: float = Field(ge=0, le=100)
    opening_balance: int = Field(ge=0)
    monthly_fixed_costs: int = Field(ge=0)
    sales_volatility: float = Field(ge=0)
    payment_delay_days: int = Field(ge=0)
    upcoming_expenses: int = Field(default=0, ge=0)
    simulation_seed: int = 20261022
    forecast_days: int = Field(default=30, ge=1, le=365)

    def to_domain(self) -> CashProfile:
        """Преобразует JSON-тело в профиль cash-gap engine.

        Returns:
            CashProfile: Доменный финансовый профиль.
        """
        payload = self.model_dump(exclude={"forecast_days"})
        return CashProfile(**payload)


class AssistantSearchRequest(ApiModel):
    """Тело запроса поиска контекста для будущего LLM-ответа.

    Attributes:
        query: Поисковый запрос.
        limit: Ограничение числа результатов.
    """

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class AssistantAnswerRequest(AssistantSearchRequest):
    """Тело запроса ответа ассистента с RAG-контекстом и LLM-генерацией."""


class HealthResponse(ApiModel):
    """Статус готовности API после startup.

    Attributes:
        status: Статус проверки или заявки.
    """

    status: str


class FactorContributionResponse(ApiModel):
    """Вклад одного признака в риск-оценку.

    Attributes:
        feature: Название признака модели.
        contribution: Вклад фактора в логит риска.
    """

    feature: str
    contribution: float


class ScoringResponse(ApiModel):
    """Структура данных `ScoringResponse`.

    Attributes:
        risk_probability: Предварительная вероятность риска.
        risk_band: Категория риска.
        factors: Вклады факторов модели.
        model_version: Версия модели скоринга.
    """

    risk_probability: float = Field(ge=0, le=1)
    risk_band: str
    factors: list[FactorContributionResponse]
    model_version: str


class NbaRecommendationResponse(ApiModel):
    """Одна рекомендация некредитного продукта.

    Attributes:
        product_id: Идентификатор некредитного продукта.
        score: Оценка релевантности или риска.
        reason: Обоснование оценки или действия.
    """

    product_id: str
    score: float = Field(ge=0, le=1)
    reason: str


class CreditRecommendationResponse(ApiModel):
    """Результат LLM-ранжирования одного допустимого кредита.

    Attributes:
        rank: Место рекомендации.
        product_id: Идентификатор кредитного продукта.
        preliminary_approval_probability: Предварительная оценка вероятности одобрения.
        risk_probability: Предварительная вероятность риска.
        context_relevance: Соответствие продукта контексту бизнеса.
        combined_score: Общая оценка кандидата.
        reasons: Причины выбора или отказа.
        reason: Обоснование оценки или действия.
    """

    rank: int = Field(ge=1)
    product_id: str
    preliminary_approval_probability: float = Field(ge=0, le=1)
    risk_probability: float = Field(ge=0, le=1)
    context_relevance: float = Field(ge=0, le=1)
    combined_score: float = Field(ge=0, le=1)
    reasons: list[str]
    reason: str


class CreditAdvisorResponse(ApiModel):
    """Структура данных `CreditAdvisorResponse`.

    Attributes:
        recommendations: Ранжированные рекомендации.
        excluded_product_ids: Идентификаторы исключённых продуктов.
        model: Название использованной LLM.
    """

    recommendations: list[CreditRecommendationResponse]
    excluded_product_ids: list[str]
    model: str | None


class CashGapResponse(ApiModel):
    """Структура данных `CashGapResponse`.

    Attributes:
        cash_gap_probability: Вероятность кассового разрыва.
        risk_band: Категория риска.
        estimated_shortfall: Оценка дефицита средств.
        forecast_days: Горизонт прогноза.
        factors: Вклады факторов модели.
    """

    cash_gap_probability: float = Field(ge=0, le=1)
    risk_band: str
    estimated_shortfall: int = Field(ge=0)
    forecast_days: int = Field(ge=1)
    factors: list[str]


class KnowledgeDocumentResponse(ApiModel):
    """Фрагмент базы знаний, который использовал RAG.

    Attributes:
        knowledge_id: Идентификатор знания.
        title: Название знания.
        text: Текст сообщения или факта.
        category: Категория документа.
        source_url: Ссылка на первоисточник.
        effective_at: Дата актуальности знания.
    """

    knowledge_id: str
    title: str
    text: str
    category: str
    source_url: str
    effective_at: str


class SearchResultResponse(ApiModel):
    """RAG-результат с документом и fusion-score.

    Attributes:
        document: Документ базы знаний.
        score: Оценка релевантности или риска.
    """

    document: KnowledgeDocumentResponse
    score: float


class UsageResponse(ApiModel):
    """Счётчики токенов, которые вернул OpenRouter.

    Attributes:
        input_tokens: Число входных токенов.
        output_tokens: Число выходных токенов.
    """

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AssistantAnswerResponse(ApiModel):
    """Ответ LLM и источники, ограничившие его контекст.

    Attributes:
        answer: Готовый ответ клиенту.
        sources: Найденные источники ответа.
        model: Название использованной LLM.
        usage: Число токенов запроса и ответа.
    """

    answer: str
    sources: list[SearchResultResponse]
    model: str
    usage: UsageResponse
