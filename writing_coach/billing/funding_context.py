"""FundingContext and the paid-provider backstop (PR-MON-6 §2, §2.1; I-1: no funded admission, no paid-provider call).

A learner `FundingContext` is a pointer - (operation_id, meter, admission digest) - created only after the admission is
durably `funded`. It authorizes nothing by itself: before every paid outbound request `require_paid()` reads the
admission and its backing from the database (the live check) and, on the first paid request, moves it to `dispatched`.
`SystemFunding(reason)` is the other, separate kind: operator tests, configuration checks, catalogue/prefetch work and
media batches, bounded by the existing USD caps. A learner context never satisfies a system check and vice versa.

The backstop is switched by `FUNDING_ENFORCEMENT` (off by default):
- `off`: nothing is checked (today's behaviour);
- `log`: every paid request that would be refused is logged `unfunded_paid_would_skip` and still sent;
- `enforce`: it is refused (`FundingRequired`); a paid rung of a chain is skipped like a budget skip.

Propagation: the context lives in a ContextVar, set by `funded()` / `system_funding()` and reset in `finally`. asyncio
tasks copy it at creation; a thread does not, so work handed to a thread goes through `run_funded(fn)`, and a thread
started any other way sees no context and cannot reach a paid provider once enforcement is on.
"""

from __future__ import annotations

import contextvars
import logging
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger("orena.funding")

MODES = ("off", "log", "enforce")
ENV = "FUNDING_ENFORCEMENT"


@dataclass(frozen=True)
class FundingContext:
    operation_id: str
    meter: str
    admission_digest: str


@dataclass(frozen=True)
class SystemFunding:
    reason: str


class FundingRequired(RuntimeError):
    """A paid-provider request without live funding, refused before it is sent (enforce mode)."""

    def __init__(self, reason: str, *, capability: str = "", provider: str = "") -> None:
        super().__init__(f"funding_required: {reason}")
        self.reason = reason
        self.capability = capability
        self.provider = provider


_CURRENT: contextvars.ContextVar[FundingContext | SystemFunding | None] = contextvars.ContextVar(
    "orena_funding_context", default=None)


class _Runtime:
    def __init__(self) -> None:
        self.mode = "off"
        self.live: Callable[..., str | None] | None = None      # repository.live
        self.dispatch: Callable[[str], str] | None = None       # repository.dispatch


_runtime = _Runtime()


def mode_from(env: Mapping[str, str]) -> str:
    value = str(env.get(ENV, "off") or "off").strip().lower()
    if value not in MODES:
        # An unreadable switch is not "off": the strictest reading that still serves is diagnostic logging.
        _log.error("%s=%r is not one of %s; using 'log'", ENV, value, MODES)
        return "log"
    return value


def configure(*, mode: str | None = None, live: Callable[..., str | None] | None = None,
              dispatch: Callable[[str], str] | None = None, env: Mapping[str, str] | None = None) -> None:
    _runtime.mode = mode if mode is not None else mode_from(env if env is not None else os.environ)
    _runtime.live = live
    _runtime.dispatch = dispatch


def mode() -> str:
    return _runtime.mode


def current() -> FundingContext | SystemFunding | None:
    return _CURRENT.get()


@contextmanager
def funded(context: FundingContext) -> Iterator[FundingContext]:
    """The admitted operation's scope. Reset in `finally`, so the context never outlives the operation."""
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)


@contextmanager
def system_funding(reason: str) -> Iterator[SystemFunding]:
    token = _CURRENT.set(SystemFunding(reason))
    try:
        yield _CURRENT.get()  # type: ignore[misc]
    finally:
        _CURRENT.reset(token)


@contextmanager
def no_funding() -> Iterator[None]:
    """A scope with no funding at all (background work that must not inherit a learner's operation)."""
    token = _CURRENT.set(None)
    try:
        yield None
    finally:
        _CURRENT.reset(token)


def run_funded(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Callable[[], Any]:
    """Bind `fn` to a copy of the current context, for a thread pool or a new thread (§2.1)."""
    snapshot = contextvars.copy_context()

    def call() -> Any:
        return snapshot.run(fn, *args, **kwargs)

    return call


def attribution() -> tuple[str | None, str | None]:
    """(operation_id, meter) for a cost record written now (§8): the learner operation, a system reason, or none."""
    context = _CURRENT.get()
    if isinstance(context, FundingContext):
        return context.operation_id, context.meter
    if isinstance(context, SystemFunding):
        return f"system:{context.reason}"[:200], "system"
    return None, None


def check_paid(*, capability: str = "", provider: str = "", timeout_seconds: float = 0.0) -> str | None:
    """None when a paid request may be sent now; otherwise the reason it may not. Never raises for a store error:
    an unreadable admission is a reason (`live_check_failed`), so it fails closed in enforce mode."""
    context = _CURRENT.get()
    if isinstance(context, SystemFunding):
        return None   # bounded by the existing USD caps, which the callers already check
    if not isinstance(context, FundingContext):
        return "no_funding_context"
    if _runtime.live is None:
        return "funding_unavailable"
    try:
        reason = _runtime.live(context.operation_id, request_digest=context.admission_digest, meter=context.meter,
                               min_hold_seconds=max(0.0, float(timeout_seconds)))  # fmt: skip
    except Exception:
        _log.warning("funding live check failed for %s", context.operation_id, exc_info=True)
        return "live_check_failed"
    if reason is None and _runtime.dispatch is not None:
        try:
            _runtime.dispatch(context.operation_id)
        except Exception:
            _log.warning("funding dispatch failed for %s", context.operation_id, exc_info=True)
            return "dispatch_failed"
    return reason


def _decide(capability: str, provider: str, timeout_seconds: float) -> tuple[bool, str | None]:
    current_mode = _runtime.mode
    if current_mode == "off":
        return True, None
    reason = check_paid(capability=capability, provider=provider, timeout_seconds=timeout_seconds)
    if reason is None:
        return True, None
    if current_mode == "log":
        _log.warning("unfunded_paid_would_skip capability=%s provider=%s reason=%s", capability, provider, reason)
        return True, reason
    _log.warning("unfunded_paid_skipped capability=%s provider=%s reason=%s", capability, provider, reason)
    return False, reason


def paid_allowed(*, capability: str = "", provider: str = "", timeout_seconds: float = 0.0) -> bool:
    """The backstop for a paid rung of a chain: False means skip the rung (enforce mode only)."""
    return _decide(capability, provider, timeout_seconds)[0]


def require_paid(*, capability: str = "", provider: str = "", timeout_seconds: float = 0.0) -> None:
    """The backstop for a paid request with no alternative rung: raises `FundingRequired` in enforce mode."""
    allowed, reason = _decide(capability, provider, timeout_seconds)
    if not allowed:
        raise FundingRequired(reason or "unfunded", capability=capability, provider=provider)
