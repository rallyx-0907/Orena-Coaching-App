"""The live runner's own logic (scripts/agent_live/run.py), without a sandbox or a provider.

Retries of a refused first round (human direction 2026-09-28: the same model, at most three times, 5 s / 15 s /
45 s, then stop), the cap checked before every send, the notes flow judged from what the device received, and
the time to the first segment.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("agent_live_run", ROOT / "scripts/agent_live/run.py")
run = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("agent_live_run", run)
_SPEC.loader.exec_module(run)


def refused(rounds=None) -> dict:
    """A turn that ended in provider_unavailable; `rounds` are what the sandbox's telemetry recorded for it
    (default: one refused round)."""

    return {"status": 200, "t_first_event": 0.01, "t_first_segment": None, "t_done": 0.4, "events": [
        {"name": "session", "data": {"session_id": "s1"}},
        {"name": "error", "data": {"class": "provider_unavailable", "message": "Orena đang bận", "fallback": "retry"}},
    ], "rounds": rounds if rounds is not None else [failed_round()]}  # fmt: skip


def ok_round(tokens_in=8000, tokens_out=60) -> dict:
    return {"capability": "agent_turn_fast", "outcome": "success",
            "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out}}  # fmt: skip


def failed_round() -> dict:
    return {"capability": "agent_turn_fast", "outcome": "failure", "usage": {"prompt_tokens": None, "completion_tokens": None}}


def answered(text="Được.", memory=(), segment=1.5) -> dict:
    events = [{"name": "session", "data": {"session_id": "s1"}},
              {"name": "segment_delta", "data": {"index": 0, "lang": "vi", "text_delta": text}}]  # fmt: skip
    events += [{"name": "memory_update", "data": m} for m in memory]
    events += [{"name": "segment_end", "data": {"index": 0, "lang": "vi", "text": text, "voice_style": "neutral_explain"}},
               {"name": "done", "data": {"usage": {"input_tokens": 8000, "output_tokens": 60}, "trace_id": "t"}}]  # fmt: skip
    return {"status": 200, "t_first_event": 0.01, "t_first_segment": segment, "t_done": segment + 0.5, "events": events,
            "rounds": [ok_round()]}  # fmt: skip


class FakeClient:
    """The sandbox as the runner sees it: turns, and the telemetry of the rounds each turn made."""

    def __init__(self, results, telemetry=True):
        self.results = list(results)
        self.sent: list[dict] = []
        self.ops: list[dict] = []
        self.telemetry = telemetry

    def call(self, method, path, body=None, timeout=90):
        if path.startswith("/api/admin/ai/operations"):
            return (200, {"recent": list(self.ops)}) if self.telemetry else (403, {"detail": "no"})
        return 200, {}

    def turn(self, body):
        self.sent.append(json.loads(json.dumps(body)))
        result = self.results.pop(0)
        for event in result.get("rounds", []):
            self.ops.append({**event, "created_at": f"t{len(self.ops)}", "latency_ms": len(self.ops)})
        return result


@pytest.fixture()
def slept(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(run.time, "sleep", waits.append)
    run.use_model("gemini-3.8-flash")
    yield waits
    run.use_model("gemini-3.5-flash-lite")


def flow(name, steps, monkeypatch):
    monkeypatch.setitem(run.FLOWS, name, steps)


ONE = [("zh-CN", "only", run.VI, "Chào.", {})]


def test_a_refused_first_round_is_retried_with_growing_waits_then_answers(slept, monkeypatch):
    flow("t", ONE, monkeypatch)
    client = FakeClient([refused(), refused(), answered()])
    rows, spent = run.run_flows(client, 5, ["t"], cap=0.15, gap=0, spent=0.0)
    assert [w for w in slept if w] == [5, 15]  # two retries, the gap between turns is 0 here
    assert len(client.sent) == 3 and rows[0]["attempts"] == 3 and not rows[0]["error"]
    assert spent == pytest.approx(2 * run.ROUND_WORST_USD + run.price(8000, 60))  # refused rounds at their worst


def test_still_refused_after_three_retries_the_run_stops(slept, monkeypatch):
    flow("t", ONE + [("zh-CN", "next", run.VI, "Tiếp.", {})], monkeypatch)
    client = FakeClient([refused(), refused(), refused(), refused(), answered()])
    rows, spent = run.run_flows(client, 5, ["t"], cap=1.0, gap=0, spent=0.0)
    assert [w for w in slept if w] == [5, 15, 45]
    assert len(client.sent) == 4  # the next turn is never sent
    assert rows[-1]["attempts"] == 4 and rows[-1]["error"]["class"] == "provider_unavailable"
    assert spent == pytest.approx(4 * run.ROUND_WORST_USD)


def test_a_turn_that_failed_after_a_billed_round_is_counted_from_the_telemetry(slept, monkeypatch):
    # The review's case: a turn about a note holds its answer; round 1 answered (billed), round 2 (after the nudge)
    # was refused. The client saw only session + error; the telemetry shows both rounds.
    flow("t", ONE, monkeypatch)
    client = FakeClient([refused(rounds=[ok_round(12000, 90), failed_round()]), answered()])
    rows, spent = run.run_flows(client, 5, ["t"], cap=1.0, gap=0, spent=0.0)
    assert spent == pytest.approx(run.price(12000, 90) + run.ROUND_WORST_USD + run.price(8000, 60))


def test_without_the_telemetry_every_turn_counts_its_whole_worst_case(slept, monkeypatch):
    flow("t", ONE, monkeypatch)
    client = FakeClient([refused(), answered()], telemetry=False)
    rows, spent = run.run_flows(client, 5, ["t"], cap=1.0, gap=0, spent=0.0)
    assert spent == pytest.approx(2 * run.WORST_TURN_USD)


def test_a_finished_turn_with_a_round_that_reported_no_usage_counts_that_round_at_its_worst(slept, monkeypatch):
    # review 2026-09-28: done.usage sums only the rounds that reported usage; the telemetry sees every round
    flow("t", ONE, monkeypatch)
    silent = {"capability": "agent_turn_fast", "outcome": "success", "usage": {"prompt_tokens": None, "completion_tokens": None}}
    finished = answered()
    finished["rounds"] = [ok_round(500, 50), silent]
    rows, spent = run.run_flows(FakeClient([finished]), 5, ["t"], cap=1.0, gap=0, spent=0.0)
    assert spent == pytest.approx(run.price(500, 50) + run.ROUND_WORST_USD)


def test_every_send_a_retry_too_fits_the_cap_at_its_worst(slept, monkeypatch):
    flow("t", ONE, monkeypatch)
    cap = run.WORST_TURN_USD + run.ROUND_WORST_USD / 2  # room for the first send, not for a retry after a refusal
    client = FakeClient([refused(), answered()])
    rows, spent = run.run_flows(client, 5, ["t"], cap=cap, gap=0, spent=0.0)
    assert len(client.sent) == 1  # no retry past the cap
    assert len(rows) == 1 and rows[0]["attempts"] == 1 and rows[0]["error"]["class"] == "provider_unavailable"
    assert spent + run.WORST_TURN_USD > cap


def test_the_model_is_one_for_both_agent_keys_and_rates_follow_it(slept, tmp_path):
    assert run.MODEL == "gemini-3.8-flash" and (run.PRICE_IN, run.PRICE_OUT) == (0.75, 3.75)
    assert run.WORST_TURN_USD == pytest.approx(run.WORST_ROUNDS * run.ROUND_WORST_USD)
    out = tmp_path / "result.json"
    run.finish([], 0.0, str(out))
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["model"] == "gemini-3.8-flash"
    assert result["capability_models"] == {"agent_turn_fast": "gemini-3.8-flash", "agent_turn_deep": "gemini-3.8-flash"}


def note(note_id, text="Thích ví dụ thật ngắn"):
    return {"op": "upsert", "note": {"id": note_id, "kind": "preference", "text": text, "weight": 0.6,
                                     "last_reinforced": "2026-09-28T09:00:00+00:00", "expires_at": None}}  # fmt: skip


def notes_rows(correct, forget, after_error=None):
    return [
        {"flow": "notes", "step": "remember", "memory_update": [note("n-1")], "error": None},
        {"flow": "notes", "step": "correct", "memory_update": correct, "error": None},
        {"flow": "notes", "step": "forget", "memory_update": forget, "error": None},
        {"flow": "notes", "step": "after", "memory_update": [], "error": after_error},
    ]


def test_the_notes_flow_passes_only_when_the_same_note_is_replaced_then_removed():
    good = run.notes_verdict(notes_rows([note("n-1", "Ví dụ dài hơn")], [{"op": "remove", "note": {"id": "n-1"}}]))
    assert good["pass"] and good["correct_detail"] == "replaced"
    new = run.notes_verdict(notes_rows([note("n-2", "Ví dụ dài hơn")], [{"op": "remove", "note": {"id": "n-1"}}]))
    assert not new["pass"] and new["correct_detail"] == "new note"
    unchanged = run.notes_verdict(notes_rows([], [{"op": "remove", "note": {"id": "n-1"}}]))
    assert not unchanged["pass"] and unchanged["correct_detail"] == "unchanged"
    kept = run.notes_verdict(notes_rows([note("n-1")], []))
    assert not kept["pass"] and not kept["forget"]
    failed_after = run.notes_verdict(notes_rows([note("n-1")], [{"op": "remove", "note": {"id": "n-1"}}],
                                                after_error={"class": "provider_unavailable"}))  # fmt: skip
    assert not failed_after["pass"] and not failed_after["after"]
    incomplete = run.notes_verdict(notes_rows([note("n-1")], [{"op": "remove", "note": {"id": "n-1"}}])[:2])
    assert not incomplete["pass"] and not incomplete["complete"]


def test_an_address_update_in_a_notes_turn_does_not_count_as_a_note():
    mirrored = {"op": "upsert", "note": {"id": "address-vi", "kind": "address"}}
    verdict = run.notes_verdict(notes_rows([note("n-1", "x"), mirrored], [{"op": "remove", "note": {"id": "n-1"}}]))
    assert verdict["correct"]


def test_the_note_nudges_are_read_per_turn_from_the_server_lines():
    lines = [
        "web-1 | agent notes: the model changed no note of 1; asked again",
        "web-1 | agent notes: changed",
        "web-1 | agent notes: changed",
        "web-1 | agent notes: the model changed no note of 1; asked again",
        "web-1 | agent notes: unchanged after asking again",
    ]
    assert run.notes_log(lines) == [
        {"asked_again": True, "changed": True},
        {"asked_again": False, "changed": True},
        {"asked_again": True, "changed": False},
    ]


def test_a_note_turn_that_failed_after_asking_again_does_not_leak_into_the_next():
    lines = [
        "web-1 | agent notes: the model changed no note of 1; asked again",
        "web-1 | agent notes: failed before a verdict",  # the attempt failed; the runner sends it again
        "web-1 | agent notes: changed",  # the retry changed it on its own
    ]
    assert run.notes_log(lines) == [
        {"asked_again": True, "changed": None, "failed": True},
        {"asked_again": False, "changed": True},
    ]


def test_timing_is_over_the_turns_that_answered():
    rows = [{"t_first_segment": 2.0, "error": None}, {"t_first_segment": 4.0, "error": None},
            {"t_first_segment": None, "error": {"class": "provider_unavailable"}}, {"t_first_segment": 3.0, "error": None}]  # fmt: skip
    assert run.timing(rows) == {"turns": 3, "first_segment_median_s": 3.0, "first_segment_max_s": 4.0}
    assert run.timing([]) == {"turns": 0}


def test_a_kept_address_travels_as_context_address(slept, monkeypatch):
    flow("t", ONE + [("zh-CN", "next", run.VI, "Tiếp.", {})], monkeypatch)
    address = {"op": "upsert", "note": {"id": "address-vi", "kind": "address",
                                        "address": {"self": "chị", "user": "em", "lang": "vi"}}}  # fmt: skip
    client = FakeClient([answered(memory=[address]), answered()])
    run.run_flows(client, 5, ["t"], cap=1.0, gap=0, spent=0.0)
    second = client.sent[1]
    assert second["context"]["address"] == {"self": "chị", "user": "em", "lang": "vi"}
    assert second["coach_notes"] == []
