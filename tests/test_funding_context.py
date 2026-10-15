"""PR-MON-6 §2/§2.1: the FundingContext pointer and the paid-provider backstop (hermetic; no database).

The live check is injected here as a fake of `PostgresFundingRepository.live`; its PostgreSQL behaviour is proved in
`tests/test_funding_postgres.py`."""

from __future__ import annotations

import asyncio
import logging
import threading

import pytest

from writing_coach.billing import funding_context as fc

CONTEXT = fc.FundingContext(operation_id="q1:abc", meter="writing.review", admission_digest="d" * 64)


@pytest.fixture(autouse=True)
def _restore():
    previous = (fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch)
    yield
    fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch = previous


class Live:
    def __init__(self, answer=None, *, raises=False):
        self.answer, self.raises, self.calls, self.dispatched = answer, raises, [], []

    def live(self, operation_id, *, request_digest, meter, min_hold_seconds):
        self.calls.append((operation_id, request_digest, meter, min_hold_seconds))
        if self.raises:
            raise RuntimeError("store down")
        return self.answer

    def dispatch(self, operation_id):
        self.dispatched.append(operation_id)
        return "dispatched"


def configure(mode, live=None):
    fc.configure(mode=mode, live=live.live if live else None, dispatch=live.dispatch if live else None)


def test_the_switch_is_off_by_default_and_an_unknown_value_is_diagnostic_not_off():
    assert fc.mode_from({}) == "off"
    assert fc.mode_from({fc.ENV: "enforce"}) == "enforce"
    assert fc.mode_from({fc.ENV: "maybe"}) == "log"


def test_off_checks_nothing():
    configure("off")
    assert fc.paid_allowed(capability="x", provider="openai") is True
    fc.require_paid(capability="x", provider="openai")


def test_a_paid_call_without_funding_context_is_blocked_in_enforce_and_only_logged_in_log(caplog):
    configure("enforce", Live())
    assert fc.paid_allowed(capability="writing_evaluator", provider="openai") is False
    with pytest.raises(fc.FundingRequired) as refused:
        fc.require_paid(capability="writing_evaluator", provider="openai")
    assert refused.value.reason == "no_funding_context"
    configure("log", Live())
    with caplog.at_level(logging.WARNING, logger="orena.funding"):
        assert fc.paid_allowed(capability="writing_evaluator", provider="openai") is True
    assert "unfunded_paid_would_skip" in caplog.text


def test_a_context_is_a_pointer_the_live_check_decides_and_the_first_paid_request_dispatches():
    live = Live(None)
    configure("enforce", live)
    with fc.funded(CONTEXT):
        assert fc.paid_allowed(capability="c", provider="p", timeout_seconds=45) is True
    assert live.calls == [("q1:abc", "d" * 64, "writing.review", 45.0)]
    assert live.dispatched == ["q1:abc"]
    for answer in ("hold_expiring", "hold_closed", "admission_settled", "digest_mismatch"):
        configure("enforce", Live(answer))
        with fc.funded(CONTEXT), pytest.raises(fc.FundingRequired) as refused:
            fc.require_paid(capability="c", provider="p", timeout_seconds=45)
        assert refused.value.reason == answer


def test_an_unreadable_live_check_fails_closed():
    configure("enforce", Live(raises=True))
    with fc.funded(CONTEXT):
        assert fc.check_paid(capability="c", provider="p") == "live_check_failed"
        assert fc.paid_allowed(capability="c", provider="p") is False


def test_system_funding_is_separate_and_passes_without_a_learner_admission():
    live = Live("no_admission")
    configure("enforce", live)
    with fc.system_funding("operator_test"):
        assert fc.paid_allowed(capability="c", provider="p") is True
        assert fc.attribution() == ("system:operator_test", "system")
    assert live.calls == []
    with fc.funded(CONTEXT):
        assert fc.attribution() == ("q1:abc", "writing.review")
    assert fc.attribution() == (None, None)


def test_the_context_is_reset_on_exceptions_and_never_leaks_into_another_thread():
    with pytest.raises(ValueError):
        with fc.funded(CONTEXT):
            raise ValueError("boom")
    assert fc.current() is None
    seen = {}
    with fc.funded(CONTEXT):
        plain = threading.Thread(target=lambda: seen.setdefault("plain", fc.current()))
        plain.start()
        plain.join()
        bound = threading.Thread(target=fc.run_funded(lambda: seen.setdefault("bound", fc.current())))
        bound.start()
        bound.join()
    assert seen == {"plain": None, "bound": CONTEXT}


def test_async_tasks_copy_their_context_and_do_not_share_it():
    other = fc.FundingContext(operation_id="q1:other", meter="orena.message", admission_digest="e" * 64)

    async def run(context):
        with fc.funded(context):
            await asyncio.sleep(0.01)
            return fc.current()

    async def both():
        return await asyncio.gather(run(CONTEXT), run(other))

    assert asyncio.run(both()) == [CONTEXT, other]
    assert fc.current() is None


def test_the_platform_gate_skips_only_an_unfunded_paid_rung():
    from writing_coach.ai.platform import _funded_gate
    from writing_coach.ai.routing import ProviderTarget

    configure("enforce", Live())
    gate = _funded_gate("writing_evaluator", None, lambda target: 30.0)
    assert gate(ProviderTarget("openai", "gpt-4.1")) == "unfunded"
    assert gate(ProviderTarget("ollama", "llama3")) is None   # a local rung needs no paid funding
    budget = _funded_gate("writing_evaluator", lambda target: "budget", lambda target: 30.0)
    assert budget(ProviderTarget("openai", "gpt-4.1")) == "budget"
    with fc.funded(CONTEXT):
        configure("enforce", Live(None))
        assert gate(ProviderTarget("openai", "gpt-4.1")) is None
