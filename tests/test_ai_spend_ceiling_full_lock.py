"""The system ceiling locks every paid AI call, not only the capped backups (owner, 2026-10-18; scope widened by Hermes for
the owner, 2026-10-19). Once it is reached (or the ledger cannot be read), until the next UTC midnight:
- every paid rung of the router is skipped (`system_ceiling`): a routed primary, a backup, a rung of an uncapped
  capability;
- a single paid request (legacy selection, an agent round) is refused before it is sent;
- paid media steps (ASR, media AI) are refused (`SpendCapReached`, scope `system`); caption requests are not AI and
  keep their own daily quota.
A local or free rung still runs. Media ASR spend, kept in its own ledger, counts toward the system total."""

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
    assert gate(PAID) is None or gate(PAID) == "unfunded"  # no ceiling: the ordinary funding decision
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


def test_media_asr_spend_counts_toward_the_system_total(tmp_path):
    ledger = SpendLedger(tmp_path / "spend.json")
    ledger.record(KIND_ASR, 1.25, batch_id="b1", media_id="m1")
    ledger.record(KIND_AI, 9.0, batch_id="b1", media_id="m1")  # media AI goes through the AI ledger too: not counted twice
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    assert ledger.asr_spent_since(start) == pytest.approx(1.25)
    assert ledger.asr_spent_since(start + timedelta(days=1)) == 0
