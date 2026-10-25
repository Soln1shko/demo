"""Профиль на подтверждение и отдельные дополнительные факты с источниками."""

import json
import sys
from types import SimpleNamespace

import pytest

from app.llm import LlmCompletion, LlmResponseError
from document_parser.ocr import OcrPage, PaddleDocumentOcr, _ocr_rows
from document_parser.service import SourceDocument, parse_documents


class FakeOcr:
    def extract(self, content: bytes, suffix: str) -> list[OcrPage]:
        assert content.startswith(b"%PDF")
        assert suffix == ".pdf"
        return [OcrPage(page=1, text="Выручка за месяц: 800000 руб. Продажи через маркетплейсы.")]


class FakeLlm:
    def __init__(self, source_text: str = "Выручка за месяц: 800000 руб.") -> None:
        self.source_text = source_text

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int, response_format: dict[str, object] | None = None
    ) -> LlmCompletion:
        del system_prompt, max_tokens
        assert response_format is not None
        assert "Продажи через маркетплейсы" in user_prompt
        profile = dict.fromkeys(
            (
                "legal_form",
                "tax_regime",
                "tax_id",
                "registration_number",
                "industry",
                "business_age_months",
                "monthly_revenue",
                "monthly_expenses",
                "net_margin_percent",
                "existing_debt_balance",
                "monthly_debt_payment",
            )
        )
        profile["monthly_revenue"] = 800000
        payload = {
            "profile": profile,
            "additional_facts": [
                {
                    "name": "sales_channel",
                    "value": "маркетплейсы",
                    "document_id": "doc-1",
                    "page": 1,
                    "source_text": "Продажи через маркетплейсы.",
                }
            ],
            "field_evidence": [
                {
                    "field": "monthly_revenue",
                    "document_id": "doc-1",
                    "page": 1,
                    "source_text": self.source_text,
                }
            ],
            "conflicts": [],
        }
        return LlmCompletion(
            content=json.dumps(payload, ensure_ascii=False), model="fake/test", input_tokens=1, output_tokens=1
        )


def test_standard_profile_and_additional_facts_are_separate() -> None:
    result = parse_documents("DEMO-001", [SourceDocument("doc-1", "statement.pdf", b"%PDF fake")], FakeOcr(), FakeLlm())
    assert result.profile.monthly_revenue == 800000
    assert "sales_channel" not in result.profile.model_dump()
    assert result.additional_facts[0].name == "sales_channel"
    assert result.field_evidence[0].document_id == "doc-1"
    assert "monthly_expenses" in result.missing_fields


def test_unknown_source_text_is_rejected() -> None:
    with pytest.raises(LlmResponseError, match="вне загруженных документов"):
        parse_documents(
            "DEMO-001",
            [SourceDocument("doc-1", "statement.pdf", b"%PDF fake")],
            FakeOcr(),
            FakeLlm("Поддельная выручка"),
        )


def test_invalid_first_llm_profile_is_retried_without_repeating_ocr() -> None:
    class CountingOcr(FakeOcr):
        calls = 0

        def extract(self, content: bytes, suffix: str) -> list[OcrPage]:
            self.calls += 1
            return super().extract(content, suffix)

    class RetryLlm(FakeLlm):
        calls = 0

        def complete(
            self,
            system_prompt: str,
            user_prompt: str,
            max_tokens: int,
            response_format: dict[str, object] | None = None,
        ) -> LlmCompletion:
            self.calls += 1
            if self.calls == 1:
                return LlmCompletion(content='{"profile": {}}', model="fake/test", input_tokens=1, output_tokens=1)
            return super().complete(system_prompt, user_prompt, max_tokens, response_format)

    ocr, llm = CountingOcr(), RetryLlm()
    result = parse_documents("DEMO-001", [SourceDocument("doc-1", "statement.pdf", b"%PDF fake")], ocr, llm)
    assert result.profile.monthly_revenue == 800000
    assert ocr.calls == 1
    assert llm.calls == 2


def test_ocr_cells_keep_table_rows_together() -> None:
    rows = _ocr_rows(
        {
            "rec_texts": ["Показатель", "Сумма", "Расходы", "600000"],
            "rec_boxes": [[50, 100, 200, 140], [500, 102, 650, 142], [50, 200, 200, 240], [500, 202, 650, 242]],
        }
    )
    assert rows == "Показатель | Сумма\nРасходы | 600000"


def test_text_ocr_does_not_load_heavy_structure_models(monkeypatch: pytest.MonkeyPatch) -> None:
    class TextPipeline:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["device"] == "cpu"

        def predict(self, path: str) -> list[SimpleNamespace]:
            assert path.endswith(".png")
            return [
                SimpleNamespace(
                    json={
                        "res": {
                            "rec_texts": ["Выручка за месяц", "800000 руб."],
                            "rec_boxes": [[10, 10, 400, 40], [410, 10, 700, 40]],
                        }
                    }
                )
            ]

    def heavy_pipeline(**kwargs: object) -> None:
        del kwargs
        raise AssertionError("Структурные модели не нужны для обычного текста")

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=TextPipeline, PPStructureV3=heavy_pipeline))
    pages = PaddleDocumentOcr().extract(b"\x89PNG test", ".png")
    assert pages == [OcrPage(page=1, text="Выручка за месяц | 800000 руб.")]
