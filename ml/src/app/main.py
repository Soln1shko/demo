"""FastAPI-приложение, объединяющее все inference-сервисы прототипа."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated, cast

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ai_assistant import KnowledgeAssistant, create_assistant
from ai_assistant.config import QdrantSettings
from ai_assistant.prompts import (
    ASSISTANT_SYSTEM_PROMPT,
    assistant_prompt,
    assistant_response_format,
    cited_knowledge_ids,
)
from ai_assistant.schema import SearchResult
from app.llm import ChatCompletionClient, LlmResponseError, LlmUnavailableError, OpenRouterClient
from app.llm_json import json_payload
from app.schemas import (
    AssistantAnswerRequest,
    AssistantAnswerResponse,
    AssistantSearchRequest,
    CashGapRequest,
    CashGapResponse,
    CreditAdvisorRequest,
    CreditAdvisorResponse,
    HealthResponse,
    NbaRecommendationResponse,
    NbaRequest,
    ScoringRequest,
    ScoringResponse,
    SearchResultResponse,
)
from cash_cap import CashGapEngine
from credit_advisor import CreditAdvisor
from credit_advisor.config import PRODUCT_RULES
from credit_advisor.prompts import PRODUCT_RANKING_SYSTEM_PROMPT, product_ranking_prompt
from credit_advisor.schema import LlmCandidate
from crm_copilot import prepare_reply
from crm_copilot.schema import CopilotRequest, CopilotResponse
from decision_explainer import explain_refusal
from decision_explainer.schema import RefusalExplanationRequest, RefusalExplanationResponse
from document_parser import parse_documents
from document_parser.config import CONFIG as PARSER_CONFIG
from document_parser.ocr import DocumentOcr, PaddleDocumentOcr
from document_parser.schema import DocumentParseResponse
from document_parser.service import SourceDocument
from financial_intelligence.demo import DemoKind, demo_case
from financial_intelligence.forecast import forecast_financials
from financial_intelligence.quest import generate_quest, recalculate_quest
from financial_intelligence.schema import (
    ForecastRequest,
    ForecastResponse,
    QuestRequest,
    QuestResponse,
    RecalculateRequest,
    RecalculateResponse,
    SimulationRequest,
    SimulationResponse,
)
from financial_intelligence.simulation import simulate_finances
from nba import NbaEngine
from offer_recovery import recover_offers
from offer_recovery.schema import RecoveryRequest, RecoveryResponse
from scoring import ScoringEngine
from underwriting import analyze_case
from underwriting.schema import UnderwritingRequest, UnderwritingResponse


class ApplicationServices:
    """Подготовленные singleton-зависимости HTTP-приложения.

    OCR и RAG поднимаются при первом запросе: скоринг, баннеры и подбор кредита
    не тянут модели Paddle и эмбеддинги.
    """

    def __init__(
        self,
        scoring: ScoringEngine,
        nba: NbaEngine,
        credit_advisor: CreditAdvisor,
        cash_gap: CashGapEngine,
        llm: ChatCompletionClient,
        qdrant_settings: QdrantSettings | None,
        ocr_client: DocumentOcr | None,
    ) -> None:
        self.scoring = scoring
        self.nba = nba
        self.credit_advisor = credit_advisor
        self.cash_gap = cash_gap
        self.llm = llm
        self._qdrant_settings = qdrant_settings
        self._ocr_client = ocr_client
        self._assistant: KnowledgeAssistant | None = None

    @property
    def assistant(self) -> KnowledgeAssistant:
        if self._assistant is None:
            self._assistant = create_assistant(self._qdrant_settings)
        return self._assistant

    @property
    def document_ocr(self) -> DocumentOcr:
        if self._ocr_client is None:
            self._ocr_client = PaddleDocumentOcr()
        return self._ocr_client

    def close(self) -> None:
        """Освобождает ресурсы, принадлежащие приложению."""
        if self._assistant is not None:
            self._assistant.close()
        self.llm.close()


def _create_services(
    qdrant_settings: QdrantSettings | None = None,
    llm_client: ChatCompletionClient | None = None,
    ocr_client: DocumentOcr | None = None,
) -> ApplicationServices:
    """Создаёт зависимости один раз при старте приложения.

    Args:
        qdrant_settings: Настройки Qdrant.
        llm_client: Клиент языковой модели.
        ocr_client: OCR-клиент.

    Returns:
        ApplicationServices: Созданные зависимости приложения.
    """
    scoring = ScoringEngine.from_json()
    return ApplicationServices(
        scoring=scoring,
        nba=NbaEngine.from_json(),
        credit_advisor=CreditAdvisor(scoring),
        cash_gap=CashGapEngine.from_json(),
        llm=llm_client or OpenRouterClient.from_environment(),
        qdrant_settings=qdrant_settings,
        ocr_client=ocr_client,
    )


def create_app(
    qdrant_settings: QdrantSettings | None = None,
    llm_client: ChatCompletionClient | None = None,
    ocr_client: DocumentOcr | None = None,
) -> FastAPI:
    """Создаёт приложение; явные Qdrant-настройки используются в интеграционных тестах.

    Args:
        qdrant_settings: Настройки Qdrant.
        llm_client: Клиент языковой модели.
        ocr_client: OCR-клиент.

    Returns:
        FastAPI: Приложение с настроенными маршрутами и зависимостями.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Управляет ресурсами приложения при запуске и остановке.

        Args:
            app: Экземпляр FastAPI.

        Returns:
            AsyncIterator[None]: Жизненный цикл приложения.
        """
        services = _create_services(qdrant_settings, llm_client, ocr_client)
        app.state.services = services
        try:
            yield
        finally:
            services.close()

    app = FastAPI(
        title="Alfa Smart Credit Cabinet API",
        version="0.1.0",
        description="Локальный демонстрационный API для inference-сервисов кабинета предпринимателя.",
        lifespan=lifespan,
    )

    @app.exception_handler(ValueError)
    def invalid_domain_input(_: Request, error: ValueError) -> JSONResponse:
        """Преобразует ошибки доменной валидации в HTTP 422.

        Args:
            _: Неиспользуемый объект запроса.
            error: Перехваченная ошибка.

        Returns:
            JSONResponse: HTTP-ответ с ошибкой.
        """
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(LlmUnavailableError)
    def unavailable_llm(_: Request, error: LlmUnavailableError) -> JSONResponse:
        """Возвращает 503, если OpenRouter не настроен или недоступен.

        Args:
            _: Неиспользуемый объект запроса.
            error: Перехваченная ошибка.

        Returns:
            JSONResponse: HTTP-ответ с ошибкой.
        """
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.exception_handler(LlmResponseError)
    def invalid_llm_response(_: Request, error: LlmResponseError) -> JSONResponse:
        """Возвращает 502 для невалидного ответа провайдера или модели.

        Args:
            _: Неиспользуемый объект запроса.
            error: Перехваченная ошибка.

        Returns:
            JSONResponse: HTTP-ответ с ошибкой.
        """
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.get("/health", tags=["system"], response_model=HealthResponse)
    def health() -> dict[str, str]:
        """Возвращает готовность HTTP-сервиса после выполнения startup.

        Returns:
            dict[str, str]: Строковые атрибуты по имени.
        """
        return {"status": "ok"}

    @app.post("/v1/scoring", tags=["scoring"], response_model=ScoringResponse)
    def score(payload: ScoringRequest, request: Request) -> dict[str, object]:
        """Рассчитывает предварительную вероятность риска для одного product_id.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        return asdict(_services(request).scoring.score(payload.to_domain()))

    @app.get("/v1/scoring/weights", tags=["scoring"])
    def scoring_weights(request: Request) -> dict[str, object]:
        """Отдаёт те же веса для мгновенного расчёта при перемещении ползунка."""
        return _services(request).scoring.browser_payload()

    @app.post("/ml/forecast", tags=["financial_intelligence"], response_model=ForecastResponse)
    def financial_forecast(payload: ForecastRequest) -> ForecastResponse:
        """Прогнозирует синтетические денежные показатели без кредита.

        Args:
            payload: Последовательная финансовая история.

        Returns:
            ForecastResponse: Центральный прогноз и сценарные границы.
        """
        return forecast_financials(payload)

    @app.get("/ml/demo/{kind}", tags=["financial_intelligence"], response_model=QuestRequest)
    def financial_demo_case(kind: DemoKind) -> QuestRequest:
        """Возвращает один воспроизводимый синтетический профиль.

        Args:
            kind: Вид демонстрационного бизнеса.

        Returns:
            QuestRequest: История и заявка для интерактивного сценария.
        """
        return demo_case(kind)

    @app.post("/ml/simulate", tags=["financial_intelligence"], response_model=SimulationResponse)
    def financial_simulation(payload: SimulationRequest) -> SimulationResponse:
        """Считает денежные потоки бизнеса с кредитом или без него.

        Args:
            payload: Прогноз и параметры кредита.

        Returns:
            SimulationResponse: Базовый, оптимистичный и стрессовый пути.
        """
        return simulate_finances(payload)

    @app.post("/ml/quest/generate", tags=["financial_intelligence"], response_model=QuestResponse)
    def quest_generate(payload: QuestRequest, request: Request) -> QuestResponse:
        """Ищет допустимые предварительные улучшения заявки.

        Args:
            payload: Финансовая история и заявка.
            request: HTTP-запрос с сервисом скоринга.

        Returns:
            QuestResponse: До трёх контрфактических планов.
        """
        return generate_quest(payload, _services(request).scoring)

    @app.post("/ml/quest/recalculate", tags=["financial_intelligence"], response_model=RecalculateResponse)
    def quest_recalculate(payload: RecalculateRequest, request: Request) -> RecalculateResponse:
        """Повторно считает проверенный набор выбранных действий.

        Args:
            payload: Исходные данные и выбранный план.
            request: HTTP-запрос с сервисом скоринга.

        Returns:
            RecalculateResponse: Финансовый и скоринговый результаты плана.
        """
        return recalculate_quest(payload, _services(request).scoring)

    @app.post("/v1/underwriting/summary", tags=["underwriting"], response_model=UnderwritingResponse)
    def underwriting_summary(payload: UnderwritingRequest, request: Request) -> UnderwritingResponse:
        """Объясняет готовый снимок заявки через OpenRouter без пересчёта скоринга.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            UnderwritingResponse: Резюме с выводами, сложностью и приоритетом.
        """
        return analyze_case(payload, _services(request).llm)

    @app.post("/v1/decision-explainer/refusal", tags=["decision_explainer"], response_model=RefusalExplanationResponse)
    def refusal_explanation(payload: RefusalExplanationRequest, request: Request) -> RefusalExplanationResponse:
        """Пишет причину отказа после выбора сотрудника в CRM.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            RefusalExplanationResponse: Сообщение с причиной отказа.
        """
        return explain_refusal(payload, _services(request).llm)

    @app.post("/v1/crm-copilot/reply", tags=["crm_copilot"], response_model=CopilotResponse)
    def crm_copilot_reply(payload: CopilotRequest, request: Request) -> CopilotResponse:
        """Собирает историю, выявляет недостающие данные и пишет черновик сотруднику.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            CopilotResponse: Черновик ответа и список недостающих сведений.
        """
        return prepare_reply(payload, _services(request).llm)

    @app.post("/v1/offer-recovery/recommendations", tags=["offer_recovery"], response_model=RecoveryResponse)
    def offer_recovery(payload: RecoveryRequest, request: Request) -> RecoveryResponse:
        """Перебирает кредитные условия локально по формуле скоринга.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            RecoveryResponse: Подходящие альтернативные условия кредита.
        """
        return recover_offers(payload, _services(request).scoring)

    @app.post("/v1/documents/parse", tags=["document_parser"], response_model=DocumentParseResponse)
    def parse_uploaded_documents(
        request: Request,
        case_id: Annotated[str, Form(pattern=r"^DEMO-[A-Z0-9-]{1,24}$")],
        files: Annotated[list[UploadFile], File()],
    ) -> DocumentParseResponse:
        """Распознаёт таблицы и текст, затем извлекает профиль через OpenRouter.

        Args:
            request: Проверенные входные данные.
            case_id: Демонстрационный идентификатор заявки.
            files: Загруженные документы.

        Returns:
            DocumentParseResponse: Профиль с источниками, конфликтами и пробелами.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if not 1 <= len(files) <= PARSER_CONFIG.max_documents:
            raise ValueError("Нужно загрузить от 1 до 8 документов.")
        documents = [
            SourceDocument(
                document_id=f"doc-{index}",
                filename=file.filename or "",
                content=file.file.read(PARSER_CONFIG.max_document_bytes + 1),
            )
            for index, file in enumerate(files, start=1)
        ]
        services = _services(request)
        return parse_documents(case_id, documents, services.document_ocr, services.llm)

    @app.post("/v1/nba/recommendations", tags=["nba"], response_model=list[NbaRecommendationResponse])
    def nba_recommendations(payload: NbaRequest, request: Request) -> list[dict[str, object]]:
        """Возвращает top-N некредитных продуктов для баннеров профиля.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            list[dict[str, object]]: Структурированные элементы.
        """
        return [asdict(item) for item in _services(request).nba.recommend(payload.to_domain(), payload.top_n)]

    @app.post("/v1/credit-advisor/recommendations", tags=["credit_advisor"], response_model=CreditAdvisorResponse)
    def credit_recommendations(payload: CreditAdvisorRequest, request: Request) -> dict[str, object]:
        """Ранжирует кредиты LLM по профилю, правилам и предварительному скорингу.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        services = _services(request)
        advice = services.credit_advisor.recommend(payload.to_domain(), top_n=len(PRODUCT_RULES))
        eligible = advice.llm_candidates()
        if not eligible:
            return {
                "recommendations": [],
                "excluded_product_ids": list(advice.excluded_product_ids),
                "model": None,
            }
        llm_candidates = _candidates_with_rules(eligible)
        completion = services.llm.complete(
            PRODUCT_RANKING_SYSTEM_PROMPT,
            product_ranking_prompt(
                payload.model_dump(exclude={"top_n"}), {"recommendations": llm_candidates}, payload.top_n
            ),
            max_tokens=500,
        )
        recommendations = _ranked_products(completion.content, eligible, payload.top_n)
        return {
            "recommendations": recommendations,
            "excluded_product_ids": list(advice.excluded_product_ids),
            "model": completion.model,
        }

    @app.post("/v1/cash-gap/forecast", tags=["cash_gap"], response_model=CashGapResponse)
    def cash_gap_forecast(payload: CashGapRequest, request: Request) -> dict[str, object]:
        """Прогнозирует кассовый разрыв по локально сгенерированной истории операций.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        return asdict(_services(request).cash_gap.predict(payload.to_domain(), payload.forecast_days))

    @app.post("/v1/assistant/search", tags=["assistant"], response_model=list[SearchResultResponse])
    def assistant_search(payload: AssistantSearchRequest, request: Request) -> list[dict[str, object]]:
        """Возвращает найденные источники для будущего LLM-ответа.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            list[dict[str, object]]: Структурированные элементы.
        """
        return [asdict(item) for item in _services(request).assistant.retrieve(payload.query, payload.limit)]

    @app.post("/v1/assistant/answer", tags=["assistant"], response_model=AssistantAnswerResponse)
    def assistant_answer(payload: AssistantAnswerRequest, request: Request) -> dict[str, object]:
        """Отвечает LLM только по RAG-контексту и возвращает использованные источники.

        Args:
            payload: Тело запроса или ответа.
            request: Проверенные входные данные.

        Returns:
            dict[str, object]: Структурированные данные для API или LLM.
        """
        services = _services(request)
        sources = services.assistant.retrieve(payload.query, payload.limit)
        completion = services.llm.complete(
            ASSISTANT_SYSTEM_PROMPT,
            assistant_prompt(payload.query, sources),
            max_tokens=600,
            response_format=assistant_response_format(sources),
        )
        answer = _structured_answer(completion.content, sources)
        return {
            "answer": answer,
            "sources": [asdict(item) for item in sources],
            "model": completion.model,
            "usage": {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens},
        }

    return app


def _services(request: Request) -> ApplicationServices:
    """Возвращает зависимости приложения, подготовленные в lifespan.

    Args:
        request: Проверенные входные данные.

    Returns:
        ApplicationServices: Созданные зависимости приложения.
    """
    return cast(ApplicationServices, request.app.state.services)


def _ranked_products(content: str, eligible: list[LlmCandidate], top_n: int) -> list[dict[str, object]]:
    """Проверяет JSON LLM и возвращает только допустимые product_id в её порядке.

    Args:
        content: Содержимое файла или ответа.
        eligible: Продукты, прошедшие локальные правила.
        top_n: Максимальное число вариантов.

    Returns:
        list[dict[str, object]]: Структурированные элементы.

    Raises:
        LlmResponseError: Ответ LLM нарушает формат или ссылается на неподтверждённые данные.
    """
    try:
        payload = json.loads(json_payload(content))
    except json.JSONDecodeError as error:
        raise LlmResponseError("LLM вернула невалидный JSON для списка продуктов.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("recommendations"), list):
        raise LlmResponseError("LLM не вернула поле recommendations.")
    candidates = {item["product_id"]: item for item in eligible}
    ranked: list[dict[str, object]] = []
    selected_ids: set[str] = set()
    for item in payload["recommendations"]:
        if not isinstance(item, dict):
            raise LlmResponseError("LLM вернула рекомендацию в неверном формате.")
        product_id = item.get("product_id")
        reason = item.get("reason")
        if not isinstance(product_id, str) or product_id not in candidates:
            raise LlmResponseError("LLM вернула product_id вне списка допустимых кандидатов.")
        if not isinstance(reason, str) or not reason.strip():
            raise LlmResponseError("LLM не указала причину рекомендации.")
        if product_id in selected_ids:
            raise LlmResponseError("LLM вернула повторный product_id.")
        selected_ids.add(product_id)
        ranked.append({"rank": len(ranked) + 1, **candidates[product_id], "reason": reason.strip()})
        if len(ranked) == top_n:
            break
    if not ranked:
        raise LlmResponseError("LLM не выбрала ни одного допустимого продукта.")
    return ranked


def _validate_answer_citations(answer: str, sources: tuple[SearchResult, ...]) -> None:
    """Не выпускает RAG-ответ без ссылки на фактически переданный фрагмент.

    Args:
        answer: Ответ.
        sources: Найденные источники для ответа.

    Raises:
        LlmResponseError: Невозможно обработать ответ внешнего сервиса.
    """
    if not answer.strip():
        raise LlmResponseError("LLM вернула пустой ответ ассистента.")
    source_ids = {item.document.knowledge_id for item in sources}
    cited_ids = cited_knowledge_ids(answer)
    if not cited_ids:
        raise LlmResponseError("LLM не указала knowledge_id использованного источника.")
    if not cited_ids <= source_ids:
        raise LlmResponseError("LLM сослалась на knowledge_id вне переданного RAG-контекста.")


def _structured_answer(content: str, sources: tuple[SearchResult, ...]) -> str:
    """Добавляет к тексту только проверенные ссылки на найденные знания.

    Args:
        content: JSON-ответ языковой модели.
        sources: Найденные источники ответа.

    Returns:
        str: Ответ с проверенными ссылками.

    Raises:
        LlmResponseError: Ответ не содержит текст или допустимые источники.
    """
    try:
        payload = json.loads(json_payload(content))
    except json.JSONDecodeError as error:
        raise LlmResponseError("LLM вернула невалидный JSON ответа ассистента.") from error
    if not isinstance(payload, dict):
        raise LlmResponseError("LLM вернула ответ ассистента в неверном формате.")
    answer = payload.get("answer")
    knowledge_ids = payload.get("knowledge_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise LlmResponseError("LLM вернула пустой ответ ассистента.")
    if (
        not isinstance(knowledge_ids, list)
        or not knowledge_ids
        or any(not isinstance(item, str) for item in knowledge_ids)
    ):
        raise LlmResponseError("LLM не указала knowledge_id использованного источника.")
    if len(knowledge_ids) != len(set(knowledge_ids)):
        raise LlmResponseError("LLM повторила knowledge_id использованного источника.")
    if not set(knowledge_ids) <= {item.document.knowledge_id for item in sources}:
        raise LlmResponseError("LLM сослалась на knowledge_id вне переданного RAG-контекста.")
    result = f"{answer.strip()} {' '.join(f'[{item}]' for item in knowledge_ids)}"
    _validate_answer_citations(result, sources)
    return result


def _candidates_with_rules(eligible: list[LlmCandidate]) -> list[dict[str, object]]:
    """Добавляет в LLM-контекст все условия продукта, не раскрывая их в ответе API.

    Args:
        eligible: Продукты, прошедшие локальные правила.

    Returns:
        list[dict[str, object]]: Структурированные элементы.
    """
    candidates: list[dict[str, object]] = []
    for item in eligible:
        product_id = item["product_id"]
        candidates.append({**item, "product_rule": asdict(PRODUCT_RULES[product_id])})
    return candidates


app = create_app()
