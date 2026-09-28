from __future__ import annotations

import pytest

from grammar_lab.pipeline.secrets_redact import REDACTED, redact


def test_redacts_a_watched_env_var_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value-123")
    text = redact("error: request failed with key super-secret-value-123 rejected")
    assert "super-secret-value-123" not in text
    assert REDACTED in text


def test_leaves_unrelated_text_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    text = redact("ordinary error message with no secrets")
    assert text == "ordinary error message with no secrets"


def test_does_not_redact_when_env_var_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    text = redact("nothing to see here")
    assert text == "nothing to see here"


def test_redacts_multiple_watched_keys_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key-abc")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key-xyz")
    text = redact("gem-key-abc and groq-key-xyz both appeared")
    assert "gem-key-abc" not in text
    assert "groq-key-xyz" not in text
    assert text.count(REDACTED) == 2
