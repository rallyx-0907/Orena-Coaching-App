"""A capability survives one provider having a bad day - and only that.

These tests hold the three promises of `writing_coach/ai/routing.py`:

1. An availability failure moves to the next provider; a terminal one does not.
   The difference matters because falling back on a malformed request would
   spend a second provider's tokens to earn the same refusal, and falling back
   on an authorization failure would be wrong.
2. A provider is asked exactly once per request, so a learner turn can never be
   answered twice by two providers.
3. A provider that keeps failing is stood down and later probed, rather than
   being asked on every request while it is down.

Nothing here touches the network: an attempt is a callable that raises what a
provider would raise.
"""
from __future__ import annotations

import pytest

from writing_coach.ai.base import (
    AICapabilityDisabled,
    AIProviderError,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
)
from writing_coach.ai.routing import (
    FAILURES_BEFORE_COOLDOWN,
    AllProvidersUnavailable,
    ProviderHealth,
    ProviderTarget,
    build_chain,
    classify,
    run_chain,
)

PRIMARY = ProviderTarget("gemini", "gemini-3.5-flash-lite")
BACKUP = ProviderTarget("ollama", "qwen3:8b")


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _fresh() -> ProviderHealth:
    return ProviderHealth(clock=_Clock())


# --- What counts as a reason to try someone else ------------------------


@pytest.mark.parametrize(
    "error",
    [
        AIProviderUnavailable("rate limited"),
        AIProviderError("upstream 503"),
        AIProviderResponseInvalid("not the schema we asked for"),
        TimeoutError("took too long"),
    ],
)
def test_availability_failures_move_to_the_next_provider(error: BaseException) -> None:
    assert classify(error) == "availability"


@pytest.mark.parametrize(
    "error",
    [
        AICapabilityDisabled("the operator turned it off"),
        ValueError("the request is malformed"),
        PermissionError("not this learner's thread"),
    ],
)
def test_terminal_failures_do_not_fall_back(error: BaseException) -> None:
    assert classify(error) == "terminal"


# --- The chain ----------------------------------------------------------


def test_the_primary_answers_and_the_backup_is_never_asked() -> None:
    asked: list[str] = []

    def attempt(target: ProviderTarget) -> str:
        asked.append(target.provider)
        return "answered"

    result = run_chain([PRIMARY, BACKUP], attempt, health=_fresh())
    assert result.value == "answered"
    assert asked == ["gemini"]
    assert [a.outcome for a in result.attempts] == ["success"]


def test_the_backup_answers_when_the_primary_is_unavailable() -> None:
    asked: list[str] = []

    def attempt(target: ProviderTarget) -> str:
        asked.append(target.provider)
        if target.provider == "gemini":
            raise AIProviderUnavailable("429")
        return "answered by the backup"

    result = run_chain([PRIMARY, BACKUP], attempt, health=_fresh())
    assert result.value == "answered by the backup"
    assert asked == ["gemini", "ollama"]
    assert result.target.provider == "ollama"
    assert [a.outcome for a in result.attempts] == ["failure", "success"]


def test_each_provider_is_asked_exactly_once() -> None:
    """A double-answered learner turn is the failure this prevents."""
    asked: list[str] = []

    def attempt(target: ProviderTarget) -> str:
        asked.append(target.provider)
        raise AIProviderUnavailable("down")

    with pytest.raises(AIProviderUnavailable):
        run_chain([PRIMARY, BACKUP], attempt, health=_fresh())
    assert asked == ["gemini", "ollama"]


def test_the_last_provider_error_is_raised_unretyped() -> None:
    """Callers classify on the exception's type, and the operator surface
    records it: wrapping every failure as "unavailable" would lose which kind
    of failure actually happened."""

    def attempt(target: ProviderTarget) -> str:
        raise AIProviderError("upstream 503")

    with pytest.raises(AIProviderError) as raised:
        run_chain([PRIMARY], attempt, health=_fresh())
    assert type(raised.value) is AIProviderError
    assert [a.provider for a in raised.value.attempts] == ["gemini"]


def test_a_terminal_error_stops_the_chain_and_is_re_raised_unchanged() -> None:
    asked: list[str] = []

    def attempt(target: ProviderTarget) -> str:
        asked.append(target.provider)
        raise AICapabilityDisabled("the operator turned it off")

    with pytest.raises(AICapabilityDisabled):
        run_chain([PRIMARY, BACKUP], attempt, health=_fresh())
    assert asked == ["gemini"]


def test_every_provider_failing_raises_and_invents_nothing() -> None:
    def attempt(target: ProviderTarget) -> str:
        raise AIProviderUnavailable("down")

    with pytest.raises(AIProviderUnavailable) as raised:
        run_chain([PRIMARY, BACKUP], attempt, health=_fresh())
    assert [a.provider for a in raised.value.attempts] == ["gemini", "ollama"]


def test_every_provider_cooling_down_is_its_own_failure() -> None:
    """Nothing was asked, so there is no provider error to re-raise."""
    health = ProviderHealth(clock=_Clock())
    for provider in ("gemini", "ollama"):
        for _ in range(FAILURES_BEFORE_COOLDOWN):
            health.record_failure(provider)

    with pytest.raises(AllProvidersUnavailable) as raised:
        run_chain([PRIMARY, BACKUP], lambda target: "never asked", health=health)
    assert [a.outcome for a in raised.value.attempts] == [
        "skipped_unhealthy",
        "skipped_unhealthy",
    ]


def test_an_empty_chain_is_a_configuration_failure_not_a_silent_answer() -> None:
    with pytest.raises(AllProvidersUnavailable):
        run_chain([], lambda target: "never", health=_fresh())


# --- Building the chain from the operator's configuration ---------------


def test_a_capability_with_no_backup_makes_one_attempt() -> None:
    chain = build_chain(provider="gemini", model="gemini-3.5-flash-lite")
    assert [t.provider for t in chain] == ["gemini"]


def test_a_configured_backup_becomes_the_second_rung() -> None:
    chain = build_chain(
        provider="gemini",
        model="gemini-3.5-flash-lite",
        backup_provider="ollama",
        backup_model="qwen3:8b",
        timeout_seconds=20,
    )
    assert [(t.provider, t.model) for t in chain] == [
        ("gemini", "gemini-3.5-flash-lite"),
        ("ollama", "qwen3:8b"),
    ]
    assert all(t.timeout_seconds == 20 for t in chain)


# --- Standing a provider down -------------------------------------------


def test_a_provider_is_stood_down_after_repeated_failures() -> None:
    health = ProviderHealth(clock=_Clock())
    for _ in range(FAILURES_BEFORE_COOLDOWN):
        health.record_failure("gemini")
    assert health.is_available("gemini") is False


def test_a_healthy_provider_is_available() -> None:
    health = ProviderHealth(clock=_Clock())
    health.record_failure("gemini")
    assert health.is_available("gemini") is True


def test_success_clears_the_record() -> None:
    health = ProviderHealth(clock=_Clock())
    for _ in range(FAILURES_BEFORE_COOLDOWN):
        health.record_failure("gemini")
    health.record_success("gemini")
    assert health.is_available("gemini") is True
    assert health.snapshot() == {}


def test_a_cooling_provider_is_skipped_and_the_next_one_answers() -> None:
    health = ProviderHealth(clock=_Clock())
    for _ in range(FAILURES_BEFORE_COOLDOWN):
        health.record_failure("gemini")

    asked: list[str] = []

    def attempt(target: ProviderTarget) -> str:
        asked.append(target.provider)
        return "answered"

    result = run_chain([PRIMARY, BACKUP], attempt, health=health)
    assert asked == ["ollama"]
    assert result.attempts[0].outcome == "skipped_unhealthy"


def test_the_cooldown_expires_and_one_probe_is_allowed_through() -> None:
    clock = _Clock()
    health = ProviderHealth(clock=clock)
    for _ in range(FAILURES_BEFORE_COOLDOWN):
        health.record_failure("gemini")
    assert health.is_available("gemini") is False

    clock.now += 31.0
    assert health.is_available("gemini") is True


def test_the_wait_grows_while_a_provider_stays_down() -> None:
    clock = _Clock()
    health = ProviderHealth(clock=clock)
    for _ in range(FAILURES_BEFORE_COOLDOWN + 2):
        health.record_failure("gemini")
    clock.now += 31.0
    assert health.is_available("gemini") is False


def test_the_snapshot_reports_cooldown_without_leaking_anything() -> None:
    health = ProviderHealth(clock=_Clock())
    for _ in range(FAILURES_BEFORE_COOLDOWN):
        health.record_failure("gemini")
    snapshot = health.snapshot()
    assert snapshot["gemini"]["cooling_down"] is True
    assert snapshot["gemini"]["consecutive_failures"] == FAILURES_BEFORE_COOLDOWN
    assert snapshot["gemini"]["seconds_remaining"] > 0
