"""Which provider answers a capability, and what happens when one cannot.

Policy only: no provider client, no FastAPI, no persistence. `platform.py`
supplies the attempt callable and the telemetry; everything here is decidable
from an exception and a clock, which is what makes it testable without a
network.

Three rules the product depends on:

**A failure is not automatically a reason to try someone else.** A provider
that is rate-limited, timing out, unreachable or answering nonsense is an
availability problem, and the next provider may well answer. A request that is
malformed, a capability that is disabled or unconfigured, and anything to do
with who is asking are *not*: trying a second provider would only produce the
same refusal more expensively, and for an authorization failure it would be
wrong. `classify` is the whole of that distinction.

**A provider that keeps failing is skipped, not hammered.** After
`FAILURES_BEFORE_COOLDOWN` consecutive availability failures a provider is put
in cooldown and later requests go straight past it. When the cooldown expires
one request is allowed through as a probe; success clears the record, another
failure starts a longer cooldown, up to `MAX_COOLDOWN_SECONDS`.

**Nothing is invented when everyone fails.** The chain raises the last
availability error. It never fabricates an answer, and it is the caller's job
to keep the learner's own words and offer a retry - `AIFallbackPolicy` remains
the only thing that may substitute a deterministic answer, and only where a
capability opted into it.

The chain is an ordered list, so a third tier costs a config field and no code
here. Today `CapabilityConfig` carries one backup, so a capability makes at
most two attempts.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable, Iterable

from writing_coach.ai.base import (
    AICapabilityError,
    AIProviderError,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
)

# Consecutive availability failures before a provider is stood down.
FAILURES_BEFORE_COOLDOWN = 3
FIRST_COOLDOWN_SECONDS = 30.0
MAX_COOLDOWN_SECONDS = 300.0


class AllProvidersUnavailable(AIProviderUnavailable):
    """Every provider in the chain failed or was skipped.

    Carries `attempts` so the caller can log what was tried. Its message is
    never shown to a learner: the room answers with its own words and a retry.
    """

    def __init__(self, message: str, attempts: list["Attempt"]) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True)
class ProviderTarget:
    """One rung of the chain: who to ask, with what, and for how long."""

    provider: str
    model: str
    timeout_seconds: int | None = None


@dataclass
class Attempt:
    """What one rung did. `outcome` is success, failure or skipped_unhealthy."""

    provider: str
    model: str
    outcome: str
    error_class: str | None = None
    latency_ms: int | None = None


def classify(error: BaseException) -> str:
    """`availability` (try the next provider) or `terminal` (do not).

    A provider answering something that does not satisfy the schema counts as
    availability: the request was fine, this provider was not. A capability
    that is disabled, unconfigured or unsupported is terminal - configuration
    is not fixed by asking someone else.
    """
    if isinstance(error, AICapabilityError):
        return "terminal"
    if isinstance(error, (TimeoutError, AIProviderUnavailable, AIProviderResponseInvalid)):
        return "availability"
    if isinstance(error, AIProviderError):
        return "availability"
    return "terminal"


class ProviderHealth:
    """Consecutive-failure counts and cooldowns, shared by every capability.

    A provider is unwell for everyone at once: it is the provider that is rate
    limited, not one capability's use of it. Guarded by a lock because two
    learner requests can fail at the same moment.
    """

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        with self._lock:
            until = self._open_until.get(provider)
            if until is None:
                return True
            if self._clock() >= until:
                # The cooldown is over: let exactly one request through to
                # probe. The record stays until that probe reports back.
                del self._open_until[provider]
                return True
            return False

    def record_success(self, provider: str) -> None:
        with self._lock:
            self._failures.pop(provider, None)
            self._open_until.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        with self._lock:
            count = self._failures.get(provider, 0) + 1
            self._failures[provider] = count
            if count < FAILURES_BEFORE_COOLDOWN:
                return
            # Each further failure past the threshold doubles the wait.
            steps = count - FAILURES_BEFORE_COOLDOWN
            seconds = min(FIRST_COOLDOWN_SECONDS * (2**steps), MAX_COOLDOWN_SECONDS)
            self._open_until[provider] = self._clock() + seconds

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """For the operator surface. No secrets, no learner data."""
        with self._lock:
            now = self._clock()
            return {
                provider: {
                    "consecutive_failures": self._failures.get(provider, 0),
                    "cooling_down": provider in self._open_until,
                    "seconds_remaining": max(0, int(self._open_until[provider] - now))
                    if provider in self._open_until
                    else 0,
                }
                for provider in set(self._failures) | set(self._open_until)
            }

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._open_until.clear()


provider_health = ProviderHealth()


@dataclass
class RoutingResult:
    value: Any
    target: ProviderTarget
    attempts: list[Attempt] = field(default_factory=list)


def build_chain(
    *,
    provider: str,
    model: str,
    backup_provider: str | None = None,
    backup_model: str | None = None,
    timeout_seconds: int | None = None,
) -> list[ProviderTarget]:
    """The operator's configuration as an ordered chain.

    The backup pair is stored together or not at all (`CapabilityConfig`
    enforces that), so a half-configured backup cannot reach here.
    """
    chain = [ProviderTarget(provider, model, timeout_seconds)]
    if backup_provider and backup_model:
        chain.append(ProviderTarget(backup_provider, backup_model, timeout_seconds))
    return chain


def run_chain(
    chain: Iterable[ProviderTarget],
    attempt: Callable[[ProviderTarget], Any],
    *,
    health: ProviderHealth | None = None,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> RoutingResult:
    """Ask each rung in turn until one answers.

    `attempt` performs one call and must not retry internally - the chain owns
    every retry, so a learner turn cannot be answered twice. A terminal error
    is re-raised immediately and unchanged: the caller still needs to know it
    was a bad request, not a provider outage.
    """
    tracker = health or provider_health
    attempts: list[Attempt] = []
    rungs = list(chain)
    if not rungs:
        raise AllProvidersUnavailable("No provider is configured for this capability.", attempts)

    last_error: BaseException | None = None
    for target in rungs:
        if not tracker.is_available(target.provider):
            record = Attempt(target.provider, target.model, "skipped_unhealthy")
            attempts.append(record)
            if on_attempt:
                on_attempt(record)
            continue
        started = monotonic()
        try:
            value = attempt(target)
        except BaseException as error:  # noqa: BLE001 - classified immediately below
            latency = int((monotonic() - started) * 1000)
            kind = classify(error)
            record = Attempt(
                target.provider, target.model, "failure", type(error).__name__, latency
            )
            attempts.append(record)
            if on_attempt:
                on_attempt(record)
            if kind == "terminal":
                raise
            tracker.record_failure(target.provider)
            last_error = error
            continue
        latency = int((monotonic() - started) * 1000)
        tracker.record_success(target.provider)
        record = Attempt(target.provider, target.model, "success", None, latency)
        attempts.append(record)
        if on_attempt:
            on_attempt(record)
        return RoutingResult(value, target, attempts)

    if last_error is not None:
        # The last provider's own error is the truest description of what went
        # wrong, and callers classify on its type - a wrapper here would retype
        # every single-provider failure as "unavailable". The attempts ride on
        # it instead.
        setattr(last_error, "attempts", attempts)
        raise last_error
    # Nothing was even asked: every rung was cooling down, or there were none.
    raise AllProvidersUnavailable(
        "Every configured provider for this capability is unavailable.", attempts
    )
