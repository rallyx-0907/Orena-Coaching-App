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
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Callable, Iterable

from writing_coach.ai.base import (
    AICapabilityError,
    AIOutputInvalid,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderTimeout,
    AIProviderUnavailable,
    http_status_class,
)
from writing_coach.ai.health_signal import failure_class_of
from writing_coach.ai.pricing import is_free_model

# Consecutive availability failures before a provider is stood down.
FAILURES_BEFORE_COOLDOWN = 3
FIRST_COOLDOWN_SECONDS = 30.0
MAX_COOLDOWN_SECONDS = 300.0
# A chain with a deadline does not start another attempt with less than this left (AI Cost Router, D-195).
MIN_ATTEMPT_SECONDS = 0.2
# The circuit breaker (PR BZ, P0 2026-10-20): the failures nothing recovers from until a person acts, and the policies
# that time the breaker (writing_coach/policies.py, group "health", editable in Admin).
HARD_FAILURES = frozenset({"spend_cap", "auth"})
HARD_COOLDOWN_POLICY = "ai.breaker_hard_cooldown_minutes"
RATE_LIMIT_COOLDOWN_POLICY = "ai.breaker_rate_limit_cooldown_seconds"
RATE_LIMIT_FAILURES_POLICY = "ai.breaker_rate_limit_failures"
DEFAULT_HARD_COOLDOWN_MINUTES = 30
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 120
DEFAULT_RATE_LIMIT_FAILURES = 3


def _breaker_policy(key: str, default: int) -> int:
    """A breaker policy's value now; the default when the policies cannot be read (the breaker never fails open)."""

    try:
        from writing_coach import policies

        value = policies.value(key)
    except Exception:  # noqa: BLE001 - a missing store keeps the built-in timing
        return default
    return value if type(value) is int and value >= 1 else default


class AllProvidersUnavailable(AIProviderUnavailable):
    """Every provider in the chain failed or was skipped.

    Carries `attempts` so the caller can log what was tried. Its message is
    never shown to a learner: the room answers with its own words and a retry.
    """

    def __init__(self, message: str, attempts: list["Attempt"]) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.reason: str | None = None


@dataclass(frozen=True)
class ProviderTarget:
    """One rung of the chain: who to ask, with what, and for how long."""

    provider: str
    model: str
    timeout_seconds: int | None = None


@dataclass
class Attempt:
    """What one rung did. `outcome` is success, failure, skipped_unhealthy or skipped_budget."""

    provider: str
    model: str
    outcome: str
    error_class: str | None = None
    latency_ms: int | None = None
    # Why the chain moved on (router vocabulary, see `fallback_reason`) and the HTTP class of the failure.
    reason: str | None = None
    status_class: str | None = None
    # The provider-health class of a failure (ai/health_signal.py); the provider's message is read, never kept.
    failure_class: str | None = None


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


def fallback_reason(error: BaseException) -> str:
    """The closed, prompt-free reason a rung failed, for telemetry and the router rollup."""

    status = getattr(error, "status_code", None)
    if isinstance(error, AIOutputInvalid):
        return "invalid_output"
    if isinstance(error, (AIProviderTimeout, TimeoutError)):
        return "timeout"
    if status == 429:
        return "rate_limited"
    if status == 402:
        return "payment_required"
    if status in (401, 403):
        return "auth_failed"
    if type(status) is int and status >= 500:
        return "server_error"
    if type(status) is int and status >= 400:
        return "client_error"
    if isinstance(error, AIProviderNotConfigured):
        return "not_configured"
    if isinstance(error, AIProviderResponseInvalid):
        return "malformed_response"
    if isinstance(error, AIProviderUnavailable):
        return "unavailable"
    return "provider_error"


def provider_tier(provider: str, model: str) -> str:
    """`local` (our own machine), `free` (a zero-rate model) or `paid`."""

    if str(provider or "").strip().casefold() == "ollama":
        return "local"
    return "free" if is_free_model(provider, model) else "paid"


class ProviderHealth:
    """Consecutive-failure counts and cooldowns, shared by every capability.

    A provider is unwell for everyone at once: it is the provider that is rate
    limited, not one capability's use of it. Guarded by a lock because two
    learner requests can fail at the same moment.
    """

    def __init__(self, clock: Callable[[], float] = monotonic, *,
                 policy: Callable[[str, int], int] | None = None) -> None:
        self._clock = clock
        self._policy = policy or _breaker_policy
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        # The circuit breaker (PR BZ): why a provider is down, since when (UTC), and its run of rate limits.
        self._reason: dict[str, str] = {}
        self._since: dict[str, datetime] = {}
        self._rate_limits: dict[str, int] = {}
        # A spending cap is held per model (PR BZ): a project cap (Gemini) stands every model down at its first
        # failure each, while a credit balance (OpenRouter 402) leaves the same provider's free models answering.
        self._model_open: dict[tuple[str, str], float] = {}
        self._model_reason: dict[tuple[str, str], str] = {}
        self._model_since: dict[tuple[str, str], datetime] = {}

    def is_available(self, provider: str, model: str | None = None) -> bool:
        with self._lock:
            now = self._clock()
            if model is not None:
                until = self._model_open.get((provider, model))
                if until is not None:
                    if now < until:
                        return False
                    del self._model_open[(provider, model)]  # half open: this request probes
            until = self._open_until.get(provider)
            if until is None:
                return True
            if now >= until:
                # The cooldown is over: let exactly one request through to
                # probe (half open). The record stays until that probe reports back.
                del self._open_until[provider]
                return True
            return False

    def record_success(self, provider: str, model: str | None = None) -> None:
        with self._lock:
            self._failures.pop(provider, None)
            self._open_until.pop(provider, None)
            self._reason.pop(provider, None)
            self._since.pop(provider, None)
            self._rate_limits.pop(provider, None)
            if model is not None:
                for store in (self._model_open, self._model_reason, self._model_since):
                    store.pop((provider, model), None)

    def _open(self, provider: str, seconds: float, reason: str) -> None:
        self._open_until[provider] = self._clock() + seconds
        self._reason[provider] = reason
        self._since.setdefault(provider, datetime.now(UTC))

    def record_failure(self, provider: str, failure_class: str | None = None, model: str | None = None) -> None:
        """One availability failure. A spending cap or a rejected key (`failure_class` spend_cap / auth) opens the
        breaker at once for `ai.breaker_hard_cooldown_minutes`: nothing recovers until a person acts, and asking again
        only adds latency. A run of rate limits opens it for `ai.breaker_rate_limit_cooldown_seconds`. Anything else
        keeps the doubling cooldown after FAILURES_BEFORE_COOLDOWN failures in a row. When the cooldown ends one
        request probes (half open); its failure opens the breaker again. A spending cap with a `model` is held for
        that model only (see `_model_open`); a rejected key always stands the whole provider down."""

        with self._lock:
            if failure_class == "spend_cap" and model is not None:
                minutes = self._policy(HARD_COOLDOWN_POLICY, DEFAULT_HARD_COOLDOWN_MINUTES)
                key = (provider, model)
                self._model_open[key] = self._clock() + float(minutes) * 60
                self._model_reason[key] = failure_class
                self._model_since.setdefault(key, datetime.now(UTC))
                return
            count = self._failures.get(provider, 0) + 1
            self._failures[provider] = count
            if failure_class in HARD_FAILURES:
                minutes = self._policy(HARD_COOLDOWN_POLICY, DEFAULT_HARD_COOLDOWN_MINUTES)
                self._open(provider, float(minutes) * 60, failure_class)
                return
            if failure_class == "rate_limit":
                run = self._rate_limits.get(provider, 0) + 1
                self._rate_limits[provider] = run
                if run >= self._policy(RATE_LIMIT_FAILURES_POLICY, DEFAULT_RATE_LIMIT_FAILURES):
                    seconds = self._policy(RATE_LIMIT_COOLDOWN_POLICY, DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS)
                    self._open(provider, float(seconds), "rate_limit")
                    return
            else:
                self._rate_limits.pop(provider, None)
            if count < FAILURES_BEFORE_COOLDOWN:
                return
            # Each further failure past the threshold doubles the wait.
            steps = count - FAILURES_BEFORE_COOLDOWN
            seconds = min(FIRST_COOLDOWN_SECONDS * (2**steps), MAX_COOLDOWN_SECONDS)
            self._open(provider, seconds, failure_class or "other")

    def down_reason(self, provider: str, model: str | None = None) -> str | None:
        """Why the breaker last opened for `provider` (or this model of it), while it has not answered since."""
        with self._lock:
            return (self._model_reason.get((provider, model)) if model is not None else None) or self._reason.get(provider)

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
                    "reason": self._reason.get(provider),
                    "down_since": self._since[provider].strftime("%Y-%m-%dT%H:%M:%SZ")
                    if provider in self._since else None,
                }
                for provider in set(self._failures) | set(self._open_until)
            } | {
                f"{provider}:{model}": {
                    "provider": provider,
                    "model": model,
                    "consecutive_failures": 1,
                    "cooling_down": (provider, model) in self._model_open,
                    "seconds_remaining": max(0, int(self._model_open[(provider, model)] - now))
                    if (provider, model) in self._model_open else 0,
                    "reason": reason,
                    "down_since": self._model_since[(provider, model)].strftime("%Y-%m-%dT%H:%M:%SZ")
                    if (provider, model) in self._model_since else None,
                }
                for (provider, model), reason in self._model_reason.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._open_until.clear()
            self._reason.clear()
            self._since.clear()
            self._rate_limits.clear()
            self._model_open.clear()
            self._model_reason.clear()
            self._model_since.clear()


provider_health = ProviderHealth()


def _down_reason(tracker: Any, provider: str, model: str) -> str | None:
    reader = getattr(tracker, "down_reason", None)
    return reader(provider, model) if callable(reader) else None



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
    deadline: float | None = None,
    admit: Callable[[ProviderTarget], str | None] | None = None,
) -> RoutingResult:
    """Ask each rung in turn until one answers.

    `attempt` performs one call and must not retry internally - the chain owns
    every retry, so a learner turn cannot be answered twice. A terminal error
    is re-raised immediately and unchanged: the caller still needs to know it
    was a bad request, not a provider outage.

    `deadline` is an absolute `monotonic()` time: once less than `MIN_ATTEMPT_SECONDS`
    remains, no further rung is started.

    `admit(target)` is asked before a rung is called and returns None to allow it or a closed reason (`"budget"`) to skip
    it: a paid rung whose capability has spent its daily cap is never asked (AI Cost Router, D-195 amendment). A skipped
    rung is recorded, never counted as a provider failure.
    """
    tracker = health or provider_health
    attempts: list[Attempt] = []
    rungs = list(chain)
    if not rungs:
        raise AllProvidersUnavailable("No provider is configured for this capability.", attempts)

    last_error: BaseException | None = None
    for target in rungs:
        if deadline is not None and deadline - monotonic() < MIN_ATTEMPT_SECONDS:
            if last_error is not None:
                last_error.attempts = attempts  # type: ignore[attr-defined]
                raise last_error
            error = AllProvidersUnavailable("The time allowed for this capability has run out.", attempts)
            error.reason = "deadline"
            raise error
        if not tracker.is_available(target.provider, target.model):
            record = Attempt(target.provider, target.model, "skipped_unhealthy", reason="cooling_down",
                             failure_class=_down_reason(tracker, target.provider, target.model))
            attempts.append(record)
            if on_attempt:
                on_attempt(record)
            continue
        if admit is not None:
            refused = admit(target)
            if refused is not None:
                record = Attempt(target.provider, target.model, "skipped_budget", reason=refused)
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
                target.provider, target.model, "failure", type(error).__name__, latency,
                reason=fallback_reason(error), status_class=http_status_class(getattr(error, "status_code", None)),
                failure_class=failure_class_of(error),
            )
            attempts.append(record)
            if on_attempt:
                on_attempt(record)
            if kind == "terminal":
                raise
            if not isinstance(error, AIOutputInvalid):
                # A validator rejecting one answer says nothing about the provider's health (a bad word, not a bad
                # provider); cooldown is for availability failures.
                tracker.record_failure(target.provider, record.failure_class, target.model)
            last_error = error
            continue
        latency = int((monotonic() - started) * 1000)
        tracker.record_success(target.provider, target.model)
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
    # Nothing was even asked: every rung was cooling down or over budget, or there were none.
    raise AllProvidersUnavailable(
        "Every configured provider for this capability is unavailable.", attempts
    )
