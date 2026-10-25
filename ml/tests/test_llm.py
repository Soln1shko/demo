"""Поведение OpenRouter-клиента с коротким лимитом вывода и ошибкой провайдера."""

import json

import httpx
import pytest

from app.config import OpenRouterSettings
from app.llm import LlmUnavailableError, OpenRouterClient


def test_qwen_receives_non_thinking_instruction_and_json_schema() -> None:
    """Короткий JSON-ответ не должен теряться в токенах рассуждения."""
    captured: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen/qwen3-32b",
                "choices": [{"message": {"content": '{"answer":"да"}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            },
        )

    transport = httpx.MockTransport(respond)
    with httpx.Client(transport=transport) as http_client:
        client = OpenRouterClient(OpenRouterSettings(api_key="demo-key", model="qwen/qwen3-32b"), client=http_client)
        schema = {"type": "json_schema", "json_schema": {"name": "answer", "schema": {"type": "object"}}}
        completion = client.complete("Верни JSON.", "Проверь заявку.", 100, response_format=schema)

    assert completion.content == '{"answer":"да"}'
    assert completion.model == "qwen/qwen3-32b"
    assert captured[0]["model"] == "qwen/qwen3-32b"
    assert captured[0]["messages"][0]["content"].endswith("/no_think")
    assert captured[0]["response_format"] == schema
    assert captured[0]["provider"] == {"require_parameters": True}


def test_provider_rate_limit_returns_unavailable_error() -> None:
    """HTTP 429 остаётся явной ошибкой доступности, а не пустым ответом."""
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": "rate limit"}))
    with httpx.Client(transport=transport) as http_client:
        client = OpenRouterClient(OpenRouterSettings(api_key="demo-key"), client=http_client)
        with pytest.raises(LlmUnavailableError, match="временно недоступен"):
            client.complete("Система", "Вопрос", 100)


def test_free_model_uses_json_schema_without_reasoning_tokens() -> None:
    """Для бесплатной модели короткий JSON не должен уходить в скрытое рассуждение."""
    captured: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "nvidia/nemotron-3.5-super-vl:free",
                "choices": [{"message": {"content": '{"answer":"да"}'}}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        client = OpenRouterClient(OpenRouterSettings(api_key="demo-key"), client=http_client)
        schema = {"type": "json_schema", "json_schema": {"name": "answer", "schema": {"type": "object"}}}
        completion = client.complete("Верни JSON.", "Проверь заявку.", 100, response_format=schema)

    assert completion.content == '{"answer":"да"}'
    assert captured[0]["model"] == "nvidia/nemotron-3.5-super-vl:free"
    assert captured[0]["reasoning"] == {"enabled": False}
    assert captured[0]["response_format"] == schema
