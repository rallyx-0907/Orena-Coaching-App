"""The per-learner sliding window behind `/api/agent/*` (spec §22)."""

from __future__ import annotations

import threading

import pytest

from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.ratelimit import SlidingWindowLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_limit_holds_in_any_window_and_says_how_long_to_wait():
    clock = Clock()
    limiter = SlidingWindowLimiter(3, 60, clock=clock)
    for second in (0, 10, 20):
        clock.now = 1000 + second
        assert limiter.check("learner-1") is None
    clock.now = 1030
    assert limiter.check("learner-1") == pytest.approx(30)  # the first request leaves at 1060
    clock.now = 1060
    assert limiter.check("learner-1") is None
    assert limiter.check("learner-1") == pytest.approx(10)


def test_a_refused_request_is_not_counted():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock=clock)
    assert limiter.check("learner-1") is None
    for _ in range(50):
        assert limiter.check("learner-1") is not None
    clock.now += 60
    assert limiter.check("learner-1") is None


def test_learners_are_counted_apart_and_the_oldest_is_forgotten_first():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, max_keys=2, clock=clock)
    assert limiter.check("a") is None and limiter.check("b") is None
    assert limiter.check("a") is not None  # "a" is now the most recently seen
    assert limiter.check("c") is None
    assert len(limiter) == 2
    assert limiter.check("a") is not None  # "b" was forgotten, "a" was not
    assert limiter.check("b") is None


def test_concurrent_requests_never_exceed_the_limit():
    limiter = SlidingWindowLimiter(25, 60)
    allowed = []
    barrier = threading.Barrier(8)

    def hammer():
        barrier.wait()
        allowed.extend(1 for _ in range(20) if limiter.check("learner-1") is None)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(allowed) == 25


@pytest.mark.parametrize("args", [(0, 60), (1, 0), (1, -1)])
def test_nonsense_limits_are_refused(args):
    with pytest.raises(ValueError):
        SlidingWindowLimiter(*args)
    with pytest.raises(ValueError):
        SlidingWindowLimiter(1, 60, max_keys=0)


def test_the_defaults_are_configuration():
    limits = AgentLimits()
    assert (limits.rate_window_seconds, limits.turns_per_window, limits.capability_reads_per_window) == (60.0, 12, 60)
    with pytest.raises(ValueError):
        AgentLimits(turns_per_window=0)
