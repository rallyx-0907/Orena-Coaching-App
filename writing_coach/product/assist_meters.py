"""The semantic AI meters at their call sites (PR-MON-7B2a, H7-3, D-MON-025): `word.assist`, `reading.assist`,
`writing.task` - one fresh remote AI operation is one request, per day, in the learner's timezone.

Every call site goes through the one gate (`quota.admit` / `quota.begin`), exactly like the existing meters: checked
before any provider call, dispatched immediately before it, settled 1 when the learner got an answer and 0 when the
provider gave nothing usable or a deterministic fallback answered. A stored, cached or deterministic answer is decided
by the caller BEFORE it reaches these helpers, so it is never admitted and never charged. The numbers are the plan
catalogue's (Admin > Plans); nothing here knows a limit.

    with assist_meters.fresh(WORD_ASSIST, digest=..., ref="word-detail:gloss") as ticket:
        answer = provider_call()
        ticket.settle(1 if answer else 0, "word-detail:gloss")

A route's refusal is the gate's own: 429 `quota_exhausted`, 403 `feature_not_in_plan`, 503 `quota_unavailable`. A
seam whose contract is "never an error" (the word tap's last layers, D-195 / D-228) uses `quiet()`: a refusal is a
miss, and the tap keeps its deterministic answer.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from fastapi import HTTPException

from writing_coach.product import quota

WORD_ASSIST = "word.assist"        # word sheet AI: contextual meaning, why here, the learner's question, sense, translation
READING_ASSIST = "reading.assist"  # Reading / Listening AI: sentence meaning, summary, sentence sheet, explain
WRITING_TASK = "writing.task"      # Writing task generation

T = TypeVar("T")


def require_feature(meter: str) -> None:
    """Feature access before any stored answer (PR-MON-6 section 4 step 1). A no-op while the meter is not enforced."""
    quota.require_feature(meter)


@contextmanager
def fresh(meter: str, *, digest: object, ref: str) -> Iterator[Any]:
    """Admit one fresh remote AI operation of `meter` and dispatch it; the caller settles 1 or 0.

    Raises the gate's 429 / 403 / 409 / 503 before anything is sent. An exception inside the block settles 0 (the
    learner got nothing); leaving it without a settle settles the admitted unit, as `quota.admit` does."""
    with quota.admit(meter, units=1, request_digest=quota.request_digest(digest)) as ticket:
        ticket.dispatch(ref)
        yield ticket


def quiet(meter: str, *, digest: object, ref: str, call: Callable[[], T],
          charged: Callable[[T], bool] = lambda result: result is not None) -> T | None:
    """`call()` admitted as one `meter` operation, for a seam that answers a miss (None) instead of an error.

    Over the limit, or enforcement unreadable: None and nothing is sent. Otherwise the call runs; it is settled 1
    when `charged(result)` (an answer that cost a remote AI call), 0 otherwise, and 0 when it raises."""
    try:
        ticket = quota.begin(meter, units=1, request_digest=quota.request_digest(digest))
    except HTTPException:
        return None
    try:
        ticket.dispatch(ref)
    except HTTPException:
        return None   # dispatch released the reservation itself
    try:
        result = call()
    except BaseException:
        ticket.settle(0, f"{ref}:failed")
        raise
    ticket.settle(1 if charged(result) else 0, ref)
    return result


def routed_cost(result: Any) -> bool:
    """Whether a routed answer (`RouteResult`) cost a remote AI call: a model answered, and it is not a model the
    account gets free (a zero-rate catalogue model, or a provider flagged on a free plan) - the word-audio rule that
    free voices are never charged (PR-MON-7D2). A cached or deterministic answer costs nothing."""
    if result is None or getattr(result, "source", "") != "model":
        return False
    provenance = getattr(result, "provenance", None) or {}
    provider, model = str(provenance.get("provider") or ""), str(provenance.get("model") or "")
    if not provider:
        return True   # an answer with no named model is never assumed free
    from writing_coach import cost_tier
    from writing_coach.ai.pricing import is_free_model

    return not (is_free_model(provider, model) or cost_tier.is_free_tier(provider))
