from __future__ import annotations

import time

from grammar_lab.pipeline.rate_limit import backoff_delay, limiter_for, reset_for_tests


def setup_function() -> None:
    reset_for_tests()


def test_limiter_does_not_delay_the_first_call() -> None:
    limiter = limiter_for("test-a", 0.2)
    started = time.monotonic()
    limiter.wait()
    assert time.monotonic() - started < 0.05


def test_limiter_delays_a_second_call_within_the_interval() -> None:
    limiter = limiter_for("test-b", 0.15)
    limiter.wait()
    started = time.monotonic()
    limiter.wait()
    assert time.monotonic() - started >= 0.1


def test_limiter_for_the_same_key_is_shared() -> None:
    a = limiter_for("shared", 0.1)
    b = limiter_for("shared", 0.1)
    assert a is b


def test_limiter_for_different_keys_is_independent() -> None:
    a = limiter_for("key-1", 0.2)
    b = limiter_for("key-2", 0.2)
    assert a is not b
    a.wait()
    started = time.monotonic()
    b.wait()  # different limiter -- must not inherit key-1's clock
    assert time.monotonic() - started < 0.05


def test_backoff_delay_grows_with_attempt_and_is_capped() -> None:
    small = backoff_delay(0, base=1.0, cap=100.0)
    large = backoff_delay(5, base=1.0, cap=100.0)
    assert 1.0 <= small <= 1.25
    assert large <= 100.0 * 1.25
    capped = backoff_delay(20, base=1.0, cap=10.0)
    assert capped <= 12.5
