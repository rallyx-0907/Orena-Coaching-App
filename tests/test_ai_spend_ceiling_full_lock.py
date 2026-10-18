"""The system ceiling locks every paid AI call, not only the capped backups (owner, 2026-10-18; scope widened by Hermes for
the owner, 2026-10-19). Once it is reached (or the ledger cannot be read), until the next UTC midnight:
- every paid rung of the router is skipped (`system_ceiling`): a routed primary, a backup, a rung of an uncapped
  capability;
- a single paid request (legacy selection, an agent round) is refused before it is sent;
- paid media steps (ASR, media AI) are refused (`SpendCapReached`, scope `system`); caption requests are not AI and
  keep their own daily quota;
- Groq translation, Speaking recognition, pronunciation scoring and new word audio are refused before they are sent.
A local or free rung still runs. Speech, pronunciation and word audio record their priced rows in the same AI ledger, so they count already."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.ai import platform, spend_gate
from writing_coach.ai.routing import ProviderTarget
from writing_coach.media_spend import KIND_AI, KIND_ASR, KIND_SUPADATA, SpendCapReached, SpendLedger

PAID = ProviderTarget("openai", "gpt-4o")
LOCAL = ProviderTarget("ollama", "gemma3")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


class Ledger:
    def __init__(self, usd=0.0, fail=False):
        self.usd, self.fail = usd, fail

    def __call__(self, since):
        if self.fail:
            raise RuntimeError("ledger down")
        return self.usd, 0


@pytest.fixture(autouse=True)
def clean():
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()
    yield
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()


def reached(fail=False):
    spend_gate.configure_ceiling(5.0, read=Ledger(usd=5.0, fail=fail))


def test_every_paid_rung_is_skipped_at_the_ceiling_and_a_local_rung_still_runs():
    gate = platform._funded_gate("writing_evaluator", None, lambda target: 10.0)
    assert gate(PAID) != "system_ceiling"  # no ceiling: the ordinary funding decision
    reached()
    assert gate(PAID) == "system_ceiling"
    assert gate(LOCAL) is None


@pytest.mark.parametrize("fail", [False, True])
def test_a_single_paid_request_is_refused_before_it_is_sent(fail):
    reached(fail=fail)
    with pytest.raises(spend_gate.SpendCeilingReached):
        platform._require_paid_funding("legacy", PAID.provider, PAID.model, 10.0)
    platform._require_paid_funding("legacy", LOCAL.provider, LOCAL.model, 10.0)  # a local model is never gated


def test_media_steps_are_refused_at_the_ceiling(tmp_path):
    ledger = SpendLedger(tmp_path / "spend.json", env={"MEDIA_DAILY_CAP_USD": "100"})
    ledger.check(KIND_ASR, "b1", 0.01)  # no ceiling: the media caps decide
    reached()
    for kind in (KIND_ASR, KIND_AI):
        with pytest.raises(SpendCapReached) as refused:
            ledger.check(kind, "b1", 0.01)
        assert refused.value.scope == "system" and refused.value.code == "spend_cap_day"
    ledger.check_requests(100, KIND_SUPADATA)  # captions are not AI: their own quota decides


@pytest.mark.parametrize("module", ["speech_asr", "speech_pronunciation"])
def test_speech_recognition_and_pronunciation_check_the_ceiling_before_their_funding_backstop(module):
    """Review of #308, P1-2: these paid calls had only the funding backstop. The ceiling check sits right before it.
    (Word audio gives way to the next voice instead: tests/test_word_audio_azure.py.)"""
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"writing_coach.{module}"))
    assert "require_below_ceiling()" in source
    assert source.index("require_below_ceiling()") < source.index("require_paid(capability=")


def test_the_shared_check_refuses_at_the_ceiling():
    spend_gate.require_below_ceiling()  # no ceiling: nothing
    reached()
    with pytest.raises(spend_gate.SpendCeilingReached):
        spend_gate.require_below_ceiling()


def test_groq_translation_for_listening_and_reading_is_refused_at_the_ceiling():
    from writing_coach.media_translation import TranslationProviderError, _below_ceiling

    _below_ceiling()
    reached()
    with pytest.raises(TranslationProviderError) as refused:
        _below_ceiling()
    assert refused.value.reason == "system_ceiling"


def test_an_unanswered_refusal_is_a_plain_429_daily_ai_limit():
    import asyncio
    import json

    import app as app_module

    reached()
    response = asyncio.run(app_module._spend_ceiling_reached(None, spend_gate.SpendCeilingReached()))
    body = json.loads(response.body)
    assert response.status_code == 429 and int(response.headers["retry-after"]) >= 1
    assert body["detail"]["category"] == "daily_ai_limit" and body["detail"]["retryable"] is False
