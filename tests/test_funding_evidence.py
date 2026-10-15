# ruff: noqa: F811
"""Formal review of `7f28ef05` (PR-MON-6), hermetic: billable provider calls are cost evidence (P1-1), and the live
hold check gets each paid client's real request timeout (P1-2). Fake providers and fake transports only."""

from __future__ import annotations

import contextlib
from decimal import Decimal
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from tests.test_ai_router import GEMMA, config, env, http_error  # noqa: F401 - `env` is a fixture
from writing_coach import policies
from writing_coach.ai import account_costs, spend_gate
from writing_coach.ai.base import AIProviderError, AIResult
from writing_coach.ai.router import route, tap
from writing_coach.ai.routing import provider_tier
from writing_coach.billing import funding_context as fc
from writing_coach.billing.cost_model import OperationCost, meter_stats

PAID = "llama-3.3-70b-versatile"
CONTEXT = fc.FundingContext(operation_id="q1:evidence", meter="writing.review", admission_digest="a" * 64)
LAMP = {"text": "lamp", "source_language": "en", "target_language": "vi"}


class Paid:
    """A paid provider (Groq) scripted per call: an answer dict, or an exception (a request that was sent)."""

    id = "groq"
    name = "Groq"
    configured = True
    timeout = 180

    def __init__(self, script: list[Any]) -> None:
        self.script, self.calls = list(script), 0

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return AIResult(data=dict(item), provider="groq", model=kwargs["model"],
                        runtime={"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100})

    generate_json = generate_json_once


class Costs:
    """The account-cost repository: every row the recorder would write."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record_ai_cost(self, user_key: str, event: dict[str, Any]) -> bool:
        self.rows.append(event)
        return True


@pytest.fixture
def paid_world(env, monkeypatch):
    costs = Costs()
    account_costs.install(costs)
    monkeypatch.setattr("writing_coach.core.request_context.current_user_key", lambda: "learner-1")
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 5.0)   # the word_translation paid cap: open
    monkeypatch.setattr(env.repo, "ai_spend_since_for_capability", lambda capability, since: (0.0, 0), raising=False)
    spend_gate.reset()
    tap.reset_state()
    previous = (fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch)
    fc.configure(mode="enforce", live=lambda *a, **k: None, dispatch=lambda op: "dispatched")
    yield costs
    fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch = previous
    account_costs.install(None)
    spend_gate.reset()
    tap.reset_state()


def wire(env, monkeypatch, script):
    """word_translation needs a free primary: the free rung fails (429), the paid Groq standby runs `script`."""
    provider = Paid(script)
    monkeypatch.setattr(platform, "providers", lambda: {"openrouter": env.fake, "groq": provider})
    env.repo.config = config(backup_provider="groq", backup_model=PAID)
    env.fake.script = {GEMMA: [http_error(429)]}
    return provider


def paid_rows(costs):
    return [row for row in costs.rows if row.get("funding_operation_id") == CONTEXT.operation_id
            and row["provider"] == "groq"]


def operation(rows):
    calls = tuple((row["cost"]["state"], provider_tier(row["provider"], row["model"]),
                   None if row["cost"].get("amount") is None else Decimal(str(row["cost"]["amount"])))
                  for row in rows if row.get("funding_operation_id") == CONTEXT.operation_id)
    return meter_stats([OperationCost(CONTEXT.operation_id, CONTEXT.meter, 1, calls)])[CONTEXT.meter]


# ---- P1-1: every request that was sent is evidence; nothing that was not sent is ------------------------------------

def test_an_invalid_paid_answer_and_its_paid_retry_both_count(env, paid_world, monkeypatch):
    provider = wire(env, monkeypatch, [{"meaning": ""}, {"meaning": "cái đèn"}])   # A: invalid output, B: valid
    with fc.funded(CONTEXT):
        assert route("word_translation", LAMP).output == {"meaning": "cái đèn"}
    assert provider.calls == 2
    rows = paid_rows(paid_world)
    assert [(row["outcome"], row["cost"]["state"]) for row in rows] == [("failure", "estimated"), ("success", "estimated")]
    each = Decimal(str(rows[0]["cost"]["amount"]))
    stats = operation(paid_world.rows)
    assert stats.complete_paid == 1 and stats.max_paid == each * 2   # operation cost = A + B


def test_a_sent_paid_call_with_unknown_cost_makes_the_operation_incomplete(env, paid_world, monkeypatch):
    error = AIProviderError("upstream 503")
    error.status_code = 503
    wire(env, monkeypatch, [error])
    with fc.funded(CONTEXT), pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    rows = paid_rows(paid_world)
    assert len(rows) == 1 and rows[0]["billable_attempt"] is True and rows[0]["cost"]["state"] == "unknown"
    stats = operation(paid_world.rows)
    assert (stats.complete, stats.incomplete) == (0, 1)   # never USD 0


def test_an_unfunded_paid_rung_is_skipped_and_is_no_cost_row(env, paid_world, monkeypatch):
    provider = wire(env, monkeypatch, [{"meaning": "cái đèn"}])
    with pytest.raises(AIProviderError):   # no FundingContext: the free rung fails, the paid standby is unfunded
        route("word_translation", LAMP)
    assert provider.calls == 0
    assert [row for row in paid_world.rows if row["provider"] == "groq"] == []
    skipped = [op for op in env.repo.operations if op.get("provider") == "groq"]
    assert skipped and all(not op.get("billable_attempt") for op in skipped)


def test_a_budget_skipped_rung_is_no_cost_row(env, paid_world, monkeypatch):
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0)   # the paid cap closed
    provider = wire(env, monkeypatch, [{"meaning": "cái đèn"}])
    with fc.funded(CONTEXT), pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert provider.calls == 0 and paid_rows(paid_world) == []


# ---- P1-2: the hold must outlive the request's own timeout ---------------------------------------------------------

class Session:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []

    def post(self, url, **kwargs):
        self.posts.append(kwargs)
        raise RuntimeError("fake transport: the request was sent")


def hold_with(seconds_left: float):
    """A live check over a credit hold with `seconds_left`: like the repository's, it refuses a shorter hold."""
    def live(operation_id, *, request_digest, meter, min_hold_seconds):
        return None if seconds_left >= min_hold_seconds else "hold_expiring"
    return live


@pytest.fixture
def enforce():
    previous = (fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch)
    yield lambda seconds: fc.configure(mode="enforce", live=hold_with(seconds), dispatch=lambda op: "dispatched")
    fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch = previous


def asr(session):
    from writing_coach.speech_asr import GroqSpeechAsrProvider

    return GroqSpeechAsrProvider("key", timeout_seconds=120, session=session)


def pronunciation(session):
    from writing_coach.speech_pronunciation import AzureSpeechPronunciationProvider

    return AzureSpeechPronunciationProvider("key", "eastus", timeout_seconds=30, session=session,
                                            normalizer=lambda audio, **_: b"RIFFwav")


def call_asr(provider):
    provider.transcribe_bytes(b"audio", filename="a.webm", content_type="audio/webm", language="en")


def call_pronunciation(provider):
    provider.assess_bytes(b"audio", filename="a.webm", content_type="audio/webm", language="en", reference_text="hello")


@pytest.mark.parametrize(("make", "call"), [(asr, call_asr), (pronunciation, call_pronunciation)],
                         ids=["asr_120s", "pronunciation_30s"])
def test_a_hold_shorter_than_the_request_timeout_sends_nothing(enforce, make, call):
    enforce(10)   # the hold has 10 seconds left
    session = Session()
    with fc.funded(CONTEXT), pytest.raises(fc.FundingRequired) as refused:
        call(make(session))
    assert refused.value.reason == "hold_expiring" and session.posts == []


@pytest.mark.parametrize(("make", "call", "timeout"), [(asr, call_asr, 120), (pronunciation, call_pronunciation, 30)],
                         ids=["asr_120s", "pronunciation_30s"])
def test_a_hold_that_outlives_the_request_timeout_sends_exactly_once(enforce, make, call, timeout):
    enforce(600)
    session = Session()
    with fc.funded(CONTEXT), contextlib.suppress(Exception):   # the fake transport fails after the request left
        call(make(session))
    assert len(session.posts) == 1 and session.posts[0]["timeout"] == timeout


def test_an_unknown_timeout_is_refused_never_treated_as_zero(enforce):
    enforce(600)
    with fc.funded(CONTEXT):
        assert fc.check_paid(capability="c", provider="groq", timeout_seconds=0) == "timeout_unknown"
        assert fc.check_paid(capability="c", provider="groq", timeout_seconds=30) is None


def test_the_platform_backstop_uses_the_clients_own_timeout_when_the_call_names_none(monkeypatch):
    seen = []
    previous = (fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch)
    fc.configure(mode="enforce", live=lambda op, **k: seen.append(k["min_hold_seconds"]) or None,
                 dispatch=lambda op: "dispatched")
    try:
        monkeypatch.setattr(platform, "providers", lambda: {"groq": Paid([])})
        gate = platform._funded_gate("c", None, lambda target: platform._effective_timeout(
            None, platform._provider_timeout(target.provider)))
        from writing_coach.ai.routing import ProviderTarget

        with fc.funded(CONTEXT):
            assert gate(ProviderTarget("groq", PAID)) is None
        assert seen == [180.0]   # Paid.timeout, the client's default
    finally:
        fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch = previous
