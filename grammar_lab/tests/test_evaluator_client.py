from __future__ import annotations

import json

import httpx
import pytest

from grammar_lab.pipeline.evaluator_client import EvaluatorClient, EvaluatorClientError


def transport(status: int, body: dict | str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(body, dict):
            return httpx.Response(status, json=body)
        return httpx.Response(status, text=body)
    return httpx.MockTransport(handler)


def test_base_url_is_required() -> None:
    with pytest.raises(ValueError, match="base_url"):
        EvaluatorClient("")


def test_evaluate_parses_errors() -> None:
    body = {"errors": [{"category": "agreement", "fragment": "He go", "confidence": 0.9}]}
    client = EvaluatorClient("http://sandbox.test", transport=transport(200, body))
    result = client.evaluate("He go to school.")
    assert result.categories() == {"agreement"}
    assert result.errors[0].fragment == "He go"


def test_evaluate_with_no_errors() -> None:
    client = EvaluatorClient("http://sandbox.test", transport=transport(200, {"errors": []}))
    result = client.evaluate("He goes to school.")
    assert result.errors == []
    assert result.categories() == set()


def test_request_shape_is_journal_mode_grammar_check() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", learning_language="en", transport=httpx.MockTransport(handler))
    client.evaluate("He goes to school.", target_cefr="A1")
    sent = json.loads(captured[0].content)
    assert sent["writing_mode"] == "journal"
    assert sent["text"] == "He goes to school."
    assert sent["target_cefr"] == "A1"
    assert sent["learning_language"] == "en"
    assert "journal_context" in sent["writing_context"]


def test_non_2xx_raises_evaluator_client_error() -> None:
    client = EvaluatorClient("http://sandbox.test", transport=transport(422, "text too short"))
    with pytest.raises(EvaluatorClientError, match="422"):
        client.evaluate("short")


def test_connection_failure_raises_evaluator_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    with pytest.raises(EvaluatorClientError, match="failed"):
        client.evaluate("He goes to school.")


def test_response_without_errors_list_raises() -> None:
    client = EvaluatorClient("http://sandbox.test", transport=transport(200, {"band_status": "estimated"}))
    with pytest.raises(EvaluatorClientError, match="errors"):
        client.evaluate("He goes to school.")
