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


# --- renewed on use (PRE-005 v2; the owner, 2026-10-18 21:44) -------------------------------------------------------


class Incarnations:
    def resolve(self, account):
        return "inc-1"

    def ensure_active(self, account):
        return "inc-1"


def _with_note(clock):
    from writing_coach.agent.memory_keys import MemoryKeys
    from writing_coach.agent.memory_store import InMemoryMemoryStore

    store = InMemoryMemoryStore(MemoryKeys.parse("v1:" + "k" * 40))
    rt = MemoryRuntime(store=store, incarnations=Incarnations(), clock=clock)
    scope = rt.scope("learner-1")
    item = store.add_explicit(scope, language="zh", kind="goal", text="Phỏng vấn xin việc", slot=None,
                              source="learner_asked", now=T0)  # fmt: skip
    return store, rt, scope, item


class Counting:
    """The store, counting `renew` calls: a note read into many turns is written at most once a day."""

    def __init__(self, store):
        self.store, self.renews = store, []

    def __getattr__(self, name):
        return getattr(self.store, name)

    def renew(self, scope, ids, now):
        self.renews.append((tuple(ids), now))
        return self.store.renew(scope, ids, now)


def test_a_note_read_into_a_turn_is_kept_six_months_from_that_turn_written_at_most_once_a_day():
    from writing_coach.agent.memory_store import EXPLICIT_TTL

    now = {"t": T0 + timedelta(days=170)}
    store, rt, scope, item = _with_note(lambda: now["t"])
    counting = Counting(store)
    rt = MemoryRuntime(store=counting, incarnations=Incarnations(), clock=lambda: now["t"])
    turn = rt.turn("learner-1", version=9, cleared=True)
    assert [n.id for n in rt.notes(turn, "zh")] == [item.id]
    assert [i.expires_at for i in store.items(scope, "zh", now["t"])] == [now["t"] + EXPLICIT_TTL]
    used = now["t"]
    now["t"] = used + timedelta(hours=20)  # many turns the same day: no more writes
    rt.notes(rt.turn("learner-1", version=9, cleared=True), "zh")
    assert len(counting.renews) == 1
    now["t"] = used + timedelta(days=1, minutes=1)  # the next day: renewed again
    rt.notes(rt.turn("learner-1", version=9, cleared=True), "zh")
    assert len(counting.renews) == 2


def test_memory_off_or_a_turn_that_does_not_send_notes_renews_nothing():
    from writing_coach.agent.memory_store import EXPLICIT_TTL

    now = T0 + timedelta(days=170)
    store, rt, scope, _item = _with_note(lambda: now)
    rt.notes(rt.turn("learner-1", version=9, cleared=False), "zh")  # provider not cleared: the notes are not sent
    store.set_enabled(scope, False)
    assert rt.notes(rt.turn("learner-1", version=9, cleared=True), "zh") == ()
    store.set_enabled(scope, True)
    assert [i.expires_at for i in store.items(scope, "zh", now)] == [T0 + EXPLICIT_TTL]


def test_a_renewal_that_fails_never_costs_the_turn():
    now = T0 + timedelta(days=170)
    store, _rt, _scope, item = _with_note(lambda: now)

    class Broken(Counting):
        def renew(self, scope, ids, at):
            raise RuntimeError("store down")

    rt = MemoryRuntime(store=Broken(store), incarnations=Incarnations(), clock=lambda: now)
    assert [n.id for n in rt.notes(rt.turn("learner-1", version=9, cleared=True), "zh")] == [item.id]
