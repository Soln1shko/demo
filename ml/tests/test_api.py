"""Интеграционная проверка HTTP-контрактов всех inference-сервисов."""

import json

import pytest
from fastapi.testclient import TestClient

from ai_assistant.knowledge import build_knowledge
from ai_assistant.schema import SearchResult
from app.llm import LlmCompletion, LlmResponseError
from app.main import _ranked_products, _structured_answer, _validate_answer_citations, create_app
from document_parser.ocr import OcrPage
from document_parser.schema import CustomerProfile


class FakeAssistant:
    """Лёгкая замена Qdrant для проверки HTTP-контракта API."""

    def __init__(self) -> None:
        self._documents = build_knowledge()

    def retrieve(self, query: str, limit: int) -> tuple[SearchResult, ...]:
        """Возвращает фрагменты, достаточные для сериализации API-ответа."""
        del query
        return tuple(
            SearchResult(document=document, score=1.0 / rank)
            for rank, document in enumerate(self._documents[:limit], start=1)
        )

    def close(self) -> None:
        """Интерфейсно соответствует настоящему ассистенту."""


class FakeLlm:
    """Детерминированная LLM для HTTP-контрактов без внешнего OpenRouter."""

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int, response_format: dict[str, object] | None = None
    ) -> LlmCompletion:
        """Возвращает JSON ранжирования либо ответ ассистента."""
        del max_tokens, response_format
        if "Ты извлекаешь сведения о бизнесе" in system_prompt:
            assert "Выручка за месяц" in user_prompt
            profile = CustomerProfile(monthly_revenue=800000).model_dump()
            content = json.dumps(
                {
                    "profile": profile,
                    "additional_facts": [],
                    "field_evidence": [
                        {
                            "field": "monthly_revenue",
                            "document_id": "doc-1",
                            "page": 1,
                            "source_text": "Выручка за месяц: 800000 руб.",
                        }
                    ],
                    "conflicts": [],
                },
                ensure_ascii=False,
            )
        elif "объяснение отказа в кредите" in system_prompt:
            content = (
                '{"message":"По вашей заявке принято решение об отказе: '
                'текущая долговая нагрузка высока относительно выручки.","risk_indexes":[0]}'
            )
        elif "CRM-помощник сотрудника банка" in system_prompt:
            content = json.dumps(
                {
                    "summary": "Клиент спрашивает о ходе проверки документов.",
                    "summary_evidence": ["history.msg-1.text"],
                    "missing_data": [],
                    "next_actions": [],
                    "reply_draft": "Ваша заявка находится на проверке документов.",
                    "reply_evidence": ["application.status"],
                },
                ensure_ascii=False,
            )
        elif "помощник кредитного аналитика" in system_prompt:
            content = (
                '{"summary":"Долговая нагрузка требует проверки.",'
                '"evidence":["financials.debt_to_revenue_ratio"],'
                '"strengths":[{"text":"Бизнес работает несколько лет.",'
                '"evidence":["business.business_age_months"]}],'
                '"risks":[{"text":"Высокая долговая нагрузка.",'
                '"evidence":["financials.debt_to_revenue_ratio"]}],'
                '"missing_data":[{"text":"Нет данных об обязательствах.",'
                '"evidence":["checks.obligations.status"]}],'
                '"next_actions":[{"text":"Проверить обязательства.",'
                '"evidence":["checks.obligations.status"]}]}'
            )
        elif "кредитный консультант" in system_prompt:
            content = '{"recommendations":[{"product_id":"business_loan","reason":"Подходит по цели и профилю."}]}'
        else:
            content = json.dumps(
                {
                    "answer": "Ответ сформирован только по найденному контексту.",
                    "knowledge_ids": ["credit.business_loan.overview"],
                },
                ensure_ascii=False,
            )
        return LlmCompletion(content=content, model="fake/test", input_tokens=10, output_tokens=10)

    def close(self) -> None:
        """Интерфейсно соответствует настоящему OpenRouter-клиенту."""


class FakeOcr:
    def extract(self, content: bytes, suffix: str) -> list[OcrPage]:
        assert content.startswith(b"%PDF")
        assert suffix == ".pdf"
        return [OcrPage(page=1, text="Выручка за месяц: 800000 руб.")]


def test_all_inference_services_are_available_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет основной API-сценарий без внешних банковских систем."""
    monkeypatch.setattr("app.main.create_assistant", lambda settings: FakeAssistant())
    app = create_app(llm_client=FakeLlm(), ocr_client=FakeOcr())
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

        invalid_scoring = client.post(
            "/v1/scoring",
            json={
                "product_id": "unknown_product",
                "requested_amount": 2_000_000,
                "term_months": 36,
                "business_age_months": 28,
                "monthly_revenue": 1_500_000,
                "net_margin_percent": 18,
                "debt_to_revenue_ratio": 0.8,
                "has_overdue_debt": False,
                "credit_history_score": 720,
                "has_collateral": False,
                "legal_form": "ip",
            },
        )
        assert invalid_scoring.status_code == 422

        scoring = client.post(
            "/v1/scoring",
            json={
                "product_id": "business_loan",
                "requested_amount": 2_000_000,
                "term_months": 36,
                "business_age_months": 28,
                "monthly_revenue": 1_500_000,
                "net_margin_percent": 18,
                "debt_to_revenue_ratio": 0.8,
                "has_overdue_debt": False,
                "credit_history_score": 720,
                "has_collateral": False,
                "legal_form": "ip",
            },
        )
        assert scoring.status_code == 200
        assert 0 <= scoring.json()["risk_probability"] <= 1

        underwriting = client.post(
            "/v1/underwriting/summary",
            json={
                "case_id": "DEMO-001",
                "business": {"segment": "micro", "legal_form": "ip", "business_age_months": 48, "industry": "торговля"},
                "application": {
                    "product_id": "business_loan",
                    "requested_amount": 2_000_000,
                    "term_months": 36,
                    "purpose": "оборотные средства",
                },
                "financials": {
                    "monthly_revenue": 800_000,
                    "net_margin_percent": 12,
                    "debt_to_revenue_ratio": 0.8,
                },
                "scoring": {
                    "risk_probability": 0.72,
                    "risk_band": "high",
                    "model_version": "backend-v1",
                    "factors": [{"feature": "debt_to_revenue_ratio", "contribution": 0.8}],
                },
                "checks": [
                    {
                        "check_id": "tax_status",
                        "label": "Налоговый статус",
                        "status": "clear",
                        "details": "Нет сигналов",
                        "source": "demo_tax",
                    },
                    {
                        "check_id": "obligations",
                        "label": "Обязательства",
                        "status": "missing",
                        "details": "Нет данных",
                        "source": "demo_bank",
                    },
                ],
                "additional_facts": [{"fact_id": "seasonality", "value": "высокая", "source": "demo_backend"}],
            },
        )
        assert underwriting.status_code == 200
        result = underwriting.json()
        assert result["overall_assessment"]["level"] == "insufficient_data"
        assert result["decision_complexity"]["level"] == "high"
        assert result["analyst_priority"]["level"] == "high"
        assert result["analyst_priority"]["exposure_months"] == 2.5
        assert result["model"] == "fake/test"

        refusal = client.post(
            "/v1/decision-explainer/refusal",
            json={
                "decision": "declined",
                "underwriting": result,
                "scoring": {
                    "risk_probability": 0.72,
                    "risk_band": "high",
                    "model_version": "backend-v1",
                    "factors": [{"feature": "debt_to_revenue_ratio", "contribution": 0.8}],
                },
            },
        )
        assert refusal.status_code == 200
        expected_message = (
            "По вашей заявке принято решение об отказе: текущая долговая нагрузка высока относительно выручки."
        )
        assert refusal.json() == {"message": expected_message}

        wrong_decision = client.post(
            "/v1/decision-explainer/refusal", json={"decision": "approved", "underwriting": result}
        )
        assert wrong_decision.status_code == 422

        copilot = client.post(
            "/v1/crm-copilot/reply",
            json={
                "case_id": "DEMO-001",
                "customer_question": "Когда будет решение по кредиту?",
                "history": [{"message_id": "msg-1", "author": "customer", "text": "Когда будет решение?"}],
                "application": {"status": "document_review", "decision": "pending"},
                "required_fields": [
                    {
                        "path": "verified_facts.decision_deadline.text",
                        "label": "Подтверждённый срок решения",
                        "reason": "Без срока нельзя назвать дату клиенту.",
                        "obtain_from": "backend",
                    }
                ],
            },
        )
        assert copilot.status_code == 200
        assert copilot.json()["answerability"] == "needs_data"
        assert copilot.json()["missing_data"][0]["path"] == "verified_facts.decision_deadline.text"
        assert copilot.json()["reply_evidence"] == []
        assert "срок решения" in copilot.json()["reply_draft"]

        documents = client.post(
            "/v1/documents/parse",
            data={"case_id": "DEMO-001"},
            files=[("files", ("statement.pdf", b"%PDF fake", "application/pdf"))],
        )
        assert documents.status_code == 200
        assert documents.json()["profile"]["monthly_revenue"] == 800000
        assert documents.json()["additional_facts"] == []

        recovered = client.post(
            "/v1/offer-recovery/recommendations",
            json={
                "case_id": "DEMO-001",
                "profile": {
                    "requested_amount": 2000000,
                    "term_months": 36,
                    "purpose": "working_capital",
                    "business_age_months": 24,
                    "monthly_revenue": 800000,
                    "net_margin_percent": 12,
                    "debt_to_revenue_ratio": 0.8,
                    "has_overdue_debt": False,
                    "credit_history_score": 700,
                    "has_collateral": False,
                    "legal_form": "ip",
                    "has_marketplace_sales": False,
                    "has_existing_business_loans": False,
                },
                "declined_offers": [
                    {
                        "product_id": "business_loan",
                        "requested_amount": 2000000,
                        "term_months": 36,
                        "reasons": ["Высокая долговая нагрузка."],
                    }
                ],
                "recommended_product_ids": ["business_loan"],
                "minimum_acceptable_amount": 800000,
                "minimum_acceptable_term_months": 12,
            },
        )
        assert recovered.status_code == 200
        assert recovered.json()["variants"]
        assert recovered.json()["estimate_type"] == "synthetic_risk_probability"

        nba = client.post(
            "/v1/nba/recommendations",
            json={
                "legal_form": "ip",
                "business_age_months": 12,
                "monthly_turnover": 1_200_000,
                "monthly_payment_count": 60,
                "online_sales_share": 0.7,
                "has_business_account": True,
                "has_website": True,
                "has_offline_point": False,
                "sells_on_marketplaces": True,
                "employee_count": 2,
                "has_foreign_trade": False,
                "needs_tax_reporting": True,
                "uses_electronic_documents": False,
                "wants_business_registration": False,
            },
        )
        assert nba.status_code == 200
        assert len(nba.json()) == 3

        advisor = client.post(
            "/v1/credit-advisor/recommendations",
            json={
                "requested_amount": 500_000,
                "term_months": 12,
                "purpose": "working_capital",
                "business_age_months": 12,
                "monthly_revenue": 1_500_000,
                "net_margin_percent": 18,
                "debt_to_revenue_ratio": 0.8,
                "has_overdue_debt": False,
                "credit_history_score": 720,
                "has_collateral": False,
                "legal_form": "ip",
                "has_marketplace_sales": False,
                "has_existing_business_loans": False,
            },
        )
        assert advisor.status_code == 200
        assert advisor.json()["recommendations"]
        assert advisor.json()["recommendations"][0]["rank"] == 1
        assert advisor.json()["model"] == "fake/test"

        no_credit = client.post(
            "/v1/credit-advisor/recommendations",
            json={
                "requested_amount": 200_000_000,
                "term_months": 12,
                "purpose": "working_capital",
                "business_age_months": 12,
                "monthly_revenue": 1_500_000,
                "net_margin_percent": 18,
                "debt_to_revenue_ratio": 0.8,
                "has_overdue_debt": False,
                "credit_history_score": 720,
                "has_collateral": False,
                "legal_form": "ip",
                "has_marketplace_sales": False,
                "has_existing_business_loans": False,
            },
        )
        assert no_credit.status_code == 200
        assert no_credit.json()["recommendations"] == []
        assert no_credit.json()["model"] is None

        cash_gap = client.post(
            "/v1/cash-gap/forecast",
            json={
                "monthly_revenue": 1_500_000,
                "net_margin_percent": 15,
                "opening_balance": 200_000,
                "monthly_fixed_costs": 400_000,
                "sales_volatility": 0.3,
                "payment_delay_days": 14,
                "upcoming_expenses": 250_000,
            },
        )
        assert cash_gap.status_code == 200
        assert 0 <= cash_gap.json()["cash_gap_probability"] <= 1

        search = client.post(
            "/v1/assistant/search",
            json={"query": "кредит продавцу маркетплейса на закупку товара", "limit": 3},
        )
        assert search.status_code == 200
        assert len(search.json()) == 3
        assert all(item["document"]["source_url"].startswith("https://") for item in search.json())

        answer = client.post(
            "/v1/assistant/answer",
            json={"query": "Какие документы нужны для кредита?", "limit": 3},
        )
        assert answer.status_code == 200
        assert answer.json()["answer"].startswith("Ответ сформирован")
        assert len(answer.json()["sources"]) == 3


def test_llm_product_ranking_accepts_markdown_json_and_rejects_invalid_ids() -> None:
    """LLM не может вывести продукт вне предварительно отобранных кандидатов."""
    eligible = [
        {
            "product_id": "business_loan",
            "preliminary_approval_probability": 0.8,
            "risk_probability": 0.2,
            "context_relevance": 0.9,
            "combined_score": 0.85,
            "reasons": ["Подходит по сумме"],
        }
    ]
    ranked = _ranked_products(
        '```json\n{"recommendations":[{"product_id":"business_loan","reason":"Подходит по цели."}]}\n```',
        eligible,
        top_n=1,
    )
    assert ranked[0]["product_id"] == "business_loan"

    with pytest.raises(LlmResponseError, match="вне списка"):
        _ranked_products(
            '{"recommendations":[{"product_id":"unknown","reason":"Неважно"}]}',
            eligible,
            top_n=1,
        )


def test_assistant_answer_must_cite_a_retrieved_knowledge_id() -> None:
    """Публичный ответ нельзя вернуть без проверяемой ссылки на RAG-контекст."""
    document = build_knowledge()[0]
    source = SearchResult(document=document, score=1.0)
    _validate_answer_citations(f"Ответ по источнику [{document.knowledge_id}]", (source,))

    with pytest.raises(LlmResponseError, match="не указала knowledge_id"):
        _validate_answer_citations("Ответ без ссылки.", (source,))
    with pytest.raises(LlmResponseError, match="вне переданного"):
        _validate_answer_citations("Ответ [unknown.source].", (source,))

    structured = _structured_answer(
        json.dumps({"answer": "Ответ по источнику.", "knowledge_ids": [document.knowledge_id]}), (source,)
    )
    assert structured == f"Ответ по источнику. [{document.knowledge_id}]"
    with pytest.raises(LlmResponseError, match="вне переданного"):
        _structured_answer('{"answer":"Текст","knowledge_ids":["unknown.source"]}', (source,))
