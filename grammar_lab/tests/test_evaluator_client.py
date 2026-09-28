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
    evaluate_calls = [r for r in captured if r.url.path == "/api/evaluate"]
    sent = json.loads(evaluate_calls[0].content)
    assert sent["writing_mode"] == "journal"
    assert sent["text"] == "He goes to school."
    assert sent["target_cefr"] == "A1"
    assert sent["learning_language"] == "en"
    assert "journal_context" in sent["writing_context"]


def test_learning_language_selects_the_session_language_once_and_keeps_its_cookie() -> None:
    """The app grades in the session's language, so a zh check must select zh first --
    a session-scoped change the client's own cookie jar carries, not a stored profile change."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/api/platform/language":
            return httpx.Response(200, json={"active": "zh"}, headers={"set-cookie": "session=zh-scope; Path=/"})
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", learning_language="zh", transport=httpx.MockTransport(handler))
    client.evaluate("我们昨天晚上吃了饭。")
    client.evaluate("他昨天下午去学校了。")
    paths = [r.url.path for r in captured]
    assert paths == ["/api/platform/language", "/api/evaluate", "/api/evaluate"]
    assert json.loads(captured[0].content) == {"language": "zh"}
    assert "session=zh-scope" in captured[1].headers.get("cookie", "")


def test_no_learning_language_selects_nothing() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"errors": []})

    EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler)).evaluate("He goes to school.")
    assert [r.url.path for r in captured] == ["/api/evaluate"]


def test_non_2xx_raises_evaluator_client_error() -> None:
    client = EvaluatorClient("http://sandbox.test", transport=transport(422, "text too short"))
    with pytest.raises(EvaluatorClientError, match="422"):
        client.evaluate("He goes to school.")


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


def test_429_is_retried_and_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("grammar_lab.pipeline.evaluator_client.time.sleep", lambda _seconds: None)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, text="quota exceeded")
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    result = client.evaluate("He goes to school.")
    assert result.errors == []
    assert len(calls) == 3


def test_503_is_retried_like_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("grammar_lab.pipeline.evaluator_client.time.sleep", lambda _seconds: None)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 2:
            return httpx.Response(503, text="provider unavailable")
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    client.evaluate("He goes to school.")
    assert len(calls) == 2


def test_gives_up_after_max_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("grammar_lab.pipeline.evaluator_client.time.sleep", lambda _seconds: None)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, text="quota exceeded")

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    with pytest.raises(EvaluatorClientError, match="429"):
        client.evaluate("He goes to school.")
    assert len(calls) == 5


def test_a_400_is_not_retried() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, text="bad request")

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    with pytest.raises(EvaluatorClientError, match="400"):
        client.evaluate("He goes to school.")
    assert len(calls) == 1


def test_error_message_redacts_a_watched_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "leaked-value-danger")
    client = EvaluatorClient(
        "http://sandbox.test",
        transport=transport(500, "upstream provider rejected key leaked-value-danger"),
    )
    with pytest.raises(EvaluatorClientError) as excinfo:
        client.evaluate("He goes to school.")
    assert "leaked-value-danger" not in str(excinfo.value)


def test_rate_limiting_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No rate_limit_key given -> no artificial delay between calls."""
    import time

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    started = time.monotonic()
    client.evaluate("Sentence number one.")
    client.evaluate("Sentence number two.")
    assert time.monotonic() - started < 0.5


def test_rate_limiting_can_be_enabled_and_is_shared_by_key() -> None:
    import time

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient(
        "http://sandbox.test", transport=httpx.MockTransport(handler),
        rate_limit_key="test-shared", min_interval_seconds=0.15,
    )
    client.evaluate("Sentence number one.")
    started = time.monotonic()
    client.evaluate("Sentence number two.")
    assert time.monotonic() - started >= 0.1


def test_text_under_the_engines_minimum_is_refused_without_a_call() -> None:
    # The app's /api/evaluate rejects text under 10 characters (422 string_too_short);
    # short, natural HSK 1 sentences hit it ("我们吃了饭。" is 6).
    from grammar_lab.pipeline.evaluator_client import EvaluatorInputTooShort

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"errors": []})

    client = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    with pytest.raises(EvaluatorInputTooShort):
        client.evaluate("我们吃了饭。")
    assert calls == []


def test_a_string_too_short_422_is_the_same_refusal() -> None:
    from grammar_lab.pipeline.evaluator_client import EvaluatorInputTooShort

    body = {"detail": [{"type": "string_too_short", "loc": ["body", "text"], "ctx": {"min_length": 12}}]}
    client = EvaluatorClient("http://sandbox.test", transport=transport(422, body))
    with pytest.raises(EvaluatorInputTooShort):
        client.evaluate("He goes to it.")
