"""Expired Orena Memory is deleted by a daily sweep (review of #292, P1-2). The pilot keeps learner data up to 6 months
(owner, PRE-005, 2026-10-18): a kept note expires `EXPLICIT_TTL` after it was last asked for, is invisible from then
on, and this sweep removes the rows. Automatic deletion is a destructive lifecycle change, so it is off until
`AGENT_MEMORY_RETENTION_SWEEP` is switched on, like the agent.turn sweep (agent/retention.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.agent.memory_runtime import MEMORY_SWEEP_SWITCH, ExpiredMemorySweep, MemoryRuntime

T0 = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)
KEYS = {"AGENT_MEMORY_HMAC_KEYS": "v1:" + "k" * 40}


class Backbone:
    is_active = True
    incarnations = None


class Store:
    def __init__(self, backlog=0, fail=False):
        self.backlog, self.fail, self.calls = backlog, fail, []

    def sweep_expired(self, now, batch=500):
        self.calls.append((now, batch))
        if self.fail:
            raise RuntimeError("database down")
        gone = min(batch, self.backlog)
        self.backlog -= gone
        return gone


def runtime(env, store):
    return MemoryRuntime.from_env({**KEYS, **env}, Backbone(), lambda keys: store)


def test_off_by_default_and_an_unclear_switch_refuses_to_start():
    assert runtime({}, Store()).sweep is None
    assert runtime({MEMORY_SWEEP_SWITCH: "off"}, Store()).sweep is None
    with pytest.raises(ValueError):
        runtime({MEMORY_SWEEP_SWITCH: "maybe"}, Store())


def test_on_it_sweeps_in_bounded_batches_at_most_once_a_day():
    clock = [T0]
    store = Store(backlog=1200)
    sweep = ExpiredMemorySweep(store.sweep_expired, clock=lambda: clock[0], run=lambda work: work())
    assert sweep.maybe_sweep() == 1200 and [b for _, b in store.calls] == [500, 500, 500]
    assert all(now == T0 for now, _ in store.calls)
    assert sweep.maybe_sweep() is None  # the same day: not again
    clock[0] = T0 + timedelta(days=1)
    store.backlog = 10_000_000
    assert sweep.maybe_sweep() == ExpiredMemorySweep.MAX_BATCHES * 500  # a large backlog goes over the next days


def test_a_turn_starts_the_sweep_and_a_failing_sweep_never_costs_the_turn():
    store = Store(fail=True)
    rt = runtime({MEMORY_SWEEP_SWITCH: "on"}, store)
    rt.sweep._run = lambda work: work()
    turn = rt.turn("learner-1", version=9, cleared=True)  # no incarnation here: memory is simply not used
    assert turn.scope is None and len(store.calls) == 1


def test_a_store_that_cannot_sweep_refuses_to_start_with_the_switch_on():
    with pytest.raises(ValueError):
        runtime({MEMORY_SWEEP_SWITCH: "on"}, object())
