"""Task C: the Daily Vocabulary Feed candidate/selection foundation.

The Feed is a filtered, day-seeded *view* over Task B's static catalog
(``writing_coach.vocabulary_library.all_vocabulary_entries``) — it is not a
second content set and it does not create a second card projection.
``vocabulary_card_from_feed_candidate`` is a direct, undecorated call into
``vocabulary_cards.vocabulary_card_from_catalog_entry``.

**Determinism, not randomness.** Ordering is derived from a stable SHA-256
hash of ``(learner_key, language_code, target_level, framework, iso_date)``
per candidate word — never Python's process-randomized ``hash()`` and never
wall-clock time beyond the ``on_date`` default. The same
``(learner_context, language_code, on_date)`` tuple always returns the same
ordered candidates; a different ``learner_key`` is free to (and, over a real
catalog, will in practice) return a different order, so the Feed does not
force every learner of a language onto one shared, permanent ordering.

**Declared vs. measured, per `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`.**
``LearnerFeedContext.target_level``/``framework`` are explicit, caller-
supplied, *declared* values (a goal the learner or an explicit request
parameter states) — this module never infers a level from saves, review
outcomes, or Feed keeps, and never writes one back as measured fact. There is
no "proficiency score" anywhere in this contract; do not add one here.

**Known limitation, stated rather than worked around.** This codebase has no
per-request account/session identity threaded into any vocabulary route
today (see
``docs/superpowers/plans/2026-09-14-vocabulary-experience.md`` §5). A caller
must supply an explicit, stable ``learner_key`` describing the request's
identity (a sandbox constant, a real account id once one exists, or any other
caller-owned stable string) — this module does not fabricate one, does not
default it, and does not read any session/cookie/account state itself.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any

from writing_coach import vocabulary_cards
from writing_coach.vocabulary_library import all_vocabulary_entries, normalize_vocabulary_word


@dataclass(frozen=True)
class LearnerFeedContext:
    """Request-scoped Feed selection context. Never persisted.

    ``learner_key`` is an opaque, caller-supplied stable identity string
    (see module docstring's "known limitation") — never fabricated here.
    ``target_level``/``framework`` are explicit *declared* values, distinct
    from any measured proficiency; ``None`` means "no declared narrowing,"
    not "measured as unrestricted."
    """

    learner_key: str
    target_level: str | None = None
    framework: str | None = None


def _narrowed_pool(
    pool: list[dict[str, Any]], learner_context: LearnerFeedContext
) -> list[dict[str, Any]]:
    if learner_context.target_level is None and learner_context.framework is None:
        return pool
    narrowed = [
        entry
        for entry in pool
        if (
            learner_context.target_level is None
            or entry.get("level") == learner_context.target_level
        )
        and (
            learner_context.framework is None
            or entry.get("framework") == learner_context.framework
        )
    ]
    # A declared level/framework narrows the pool; it must never starve the
    # feed down to nothing when no entry currently matches it.
    return narrowed if narrowed else pool


def _sort_key(
    entry: dict[str, Any],
    *,
    learner_context: LearnerFeedContext,
    language_code: str,
    iso_date: str,
) -> str:
    payload = "|".join(
        [
            learner_context.learner_key,
            language_code,
            learner_context.target_level or "",
            learner_context.framework or "",
            iso_date,
            entry.get("normalized_word") or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def daily_feed_candidates(
    language_code: str,
    *,
    learner_context: LearnerFeedContext,
    exclude_normalized: set[str],
    count: int = 5,
    on_date: date | None = None,
) -> list[dict[str, Any]]:
    """Up to ``count`` catalog entries for ``language_code``, deterministically
    ordered per ``(learner_context, language_code, on_date)``.

    Filters to ``learner_context.target_level``/``framework`` when supplied,
    falling back to the full per-language pool rather than returning an empty
    feed when the declared narrowing matches nothing. Excludes any entry whose
    normalized word is in ``exclude_normalized``.
    """

    language = str(language_code or "").strip().casefold()
    pool = _narrowed_pool(all_vocabulary_entries(language), learner_context)

    excluded = {normalize_vocabulary_word(word) for word in exclude_normalized}
    pool = [entry for entry in pool if entry.get("normalized_word") not in excluded]

    iso_date = (on_date or date.today()).isoformat()
    ordered = sorted(
        pool,
        key=lambda entry: _sort_key(
            entry, learner_context=learner_context, language_code=language, iso_date=iso_date
        ),
    )
    return [dict(entry) for entry in ordered[:count]]


def vocabulary_card_from_feed_candidate(entry: dict[str, Any]) -> dict[str, Any]:
    """Project one Feed candidate into the same Vocabulary Card shape a
    curated-catalog browse would produce — a direct call, no duplicated
    card-shaping logic. Kept as its own name so Feed call sites read
    distinctly from generic catalog browsing."""

    return vocabulary_cards.vocabulary_card_from_catalog_entry(entry)
