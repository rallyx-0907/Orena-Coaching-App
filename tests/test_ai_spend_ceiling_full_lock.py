"""D-250 (owner, 2026-10-21): the system's daily spend never locks anything. With the whole ledger past the monitor's
threshold - and with a ledger that cannot be read - every path the old ceiling stopped still runs:
- every paid rung of the router (a routed primary, a backup, a rung of an uncapped capability);
- a single paid request (legacy selection, an agent round);
- paid media steps (ASR, media AI), which keep only their own media caps;
- Groq translation, Speaking recognition, pronunciation scoring and new word audio.
Each still ticks the monitor, so the alert is raised; only a learner's own plan cap (ai/learner_cost.py) limits them."""

from __future__ import annotations

import importlib
import inspect

import pytest

from writing_coach.ai import platform, spend_gate
from writing_coach.ai.routing import ProviderTarget
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendLedger

PAID = ProviderTarget("openai", "gpt-4o")
LOCAL = ProviderTarget("ollama", "gemma3")


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


@pytest.fixture(params=[False, True], ids=["reached", "unreadable"])
def heavy_day(request):
    spend_gate.configure_ceiling(5.0, read=Ledger(usd=50.0, fail=request.param))
    return request.param


def test_no_paid_rung_is_skipped_for_the_system_total(heavy_day):
    gate = platform._funded_gate("writing_evaluator", None, lambda target: 10.0)
    assert gate(PAID) != spend_gate.CEILING_REASON and gate(LOCAL) is None


def test_a_single_paid_request_is_still_sent(heavy_day):
    platform._require_paid_funding("legacy", PAID.provider, PAID.model, 10.0)   # funding is off here: nothing raises


def test_media_steps_keep_only_their_own_caps(heavy_day, tmp_path):
    ledger = SpendLedger(tmp_path / "spend.json", env={"MEDIA_DAILY_CAP_USD": "100"})
    for kind in (KIND_ASR, KIND_AI):
        ledger.check(kind, "b1", 0.01)


def test_groq_translation_is_still_sent(heavy_day):
    from writing_coach.media_translation import _below_ceiling

    _below_ceiling()


@pytest.mark.parametrize("module", ["speech_asr", "speech_pronunciation", "word_audio_azure", "media_spend",
                                    "media_translation", "ai.platform"])
def test_every_former_ceiling_check_is_a_monitor_tick(module):
    source = inspect.getsource(importlib.import_module(f"writing_coach.{module}"))
    assert "observe()" in source
    for gone in ("ceiling_reached(", "require_below_ceiling(", "SpendCeilingReached()"):
        assert gone not in source, (module, gone)


def test_the_paused_header_is_gone():
    assert not hasattr(spend_gate, "install_paused_header")
