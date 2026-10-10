"""Speech recognition, pronunciation scoring and media translation in the shared AI ledger (cost report, 2026-10-04).

Text model calls were the only priced rows in the `ai.operation` telemetry; a
Groq transcription and an Azure pronunciation assessment cost money too and
left no trace. Each provider call now records one row like a text call does:
the capability, provider and model, the outcome, the latency, the audio
seconds it sent, and the cost from the audio catalog (ai/pricing.py). No audio,
transcript or reference text is recorded. A failing recorder never fails the
learner's request.
"""

from __future__ import annotations

import contextvars
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from writing_coach.ai.pricing import estimate_audio_cost

_log = logging.getLogger(__name__)


# Whose request a recorded provider call belongs to. A learner's call is "learner"; the media pipeline records the calls
# of an operator's shared import with no origin (it is neither a learner's request nor an operator's test).
_ORIGIN: contextvars.ContextVar[str | None] = contextvars.ContextVar("orena_telemetry_origin", default="learner")


@contextmanager
def telemetry_origin(origin: str | None) -> Iterator[None]:
    token = _ORIGIN.set(origin)
    try:
        yield
    finally:
        _ORIGIN.reset(token)


def _error_class(error: BaseException | None) -> str | None:
    if error is None:
        return None
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).casefold()
    return name[:80] if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name) else None


def record_token_operation(
    capability: str,
    *,
    provider: str,
    model: str,
    outcome: str,
    latency_ms: int | None,
    usage: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    """One row for a text-model call made outside the AI platform (the media pre-translation, D-168): capability,
    provider, model, the provider-reported prompt/completion tokens and the cost from the token catalog. No prompt,
    transcript or answer is recorded. Without reported usage the cost is said as unknown, never priced as zero."""
    try:
        from writing_coach.ai.platform import _persist_operation_telemetry
        from writing_coach.ai.pricing import estimate_token_cost

        reported = {key: value for key, value in (usage or {}).items() if key in {"prompt_tokens", "completion_tokens", "total_tokens"}}
        event: dict[str, Any] = {
            "capability": capability,
            "origin": _ORIGIN.get(),
            "provider": provider,
            "model": model,
            "model_redacted": False,
            "outcome": outcome,
            "error_class": _error_class(error),
            "latency_ms": latency_ms,
            "usage": reported if outcome == "success" else {},
            "rate_limit": {},
            "cost": estimate_token_cost(provider, model, reported) if outcome == "success" else
            {"state": "unknown", "currency": None, "amount": None,
             "provenance": {"provider": provider, "model": model, "reason": "request_failed"}},
            "quota_available": "unknown",
        }
        _persist_operation_telemetry(event)
    except Exception:  # telemetry never costs the learner the answer
        _log.warning("token operation telemetry not recorded", exc_info=True)


def record_audio_operation(
    capability: str,
    *,
    provider: str,
    model: str,
    outcome: str,
    latency_ms: int | None,
    audio_seconds: float | None,
    error: BaseException | None = None,
) -> None:
    try:
        from writing_coach.ai.platform import _persist_operation_telemetry

        billed = audio_seconds if outcome == "success" else None
        event: dict[str, Any] = {
            "capability": capability,
            "origin": _ORIGIN.get(),
            "provider": provider,
            "model": model,
            "model_redacted": False,
            "outcome": outcome,
            "error_class": _error_class(error),
            "latency_ms": latency_ms,
            "usage": {"audio_seconds": audio_seconds} if audio_seconds is not None else {},
            "rate_limit": {},
            # A refused or failed request is not charged: it is recorded with no amount, never a guessed one.
            "cost": estimate_audio_cost(provider, model, billed) if outcome == "success" else
            {"state": "unknown", "currency": None, "amount": None,
             "provenance": {"provider": provider, "model": model, "reason": "request_failed"}},
            "quota_available": "unknown",
        }
        _persist_operation_telemetry(event)
    except Exception:  # telemetry never costs the learner the answer
        _log.warning("audio operation telemetry not recorded", exc_info=True)
