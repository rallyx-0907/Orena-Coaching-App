"""How a Dictation write changes the stored evidence (D-103.2, D-104 H-14; D4 I18).

Pure and storage-free, so the rule is proved in CI without PostgreSQL and the repository applies
exactly this under its row lock. The score is the SERVER's: the browser's `best_*` fields are ignored.

  * A checked write with an answer carries a `score` the route computed with the Python port of the
    browser evaluator. A stored row whose score came from the client (or no row) is SUPERSEDED by it
    (never kept by `max`: an unverifiable number cannot hold a verified one down or up); afterwards
    the best is `max(stored, computed)` and `best_exact` is `stored or computed`.
  * `checked_attempt_count = max(stored, min(client, stored + 1))`: never lowered, at most +1 a write.
    It is activity, not evidence, and it is not idempotent under a lost-response retry (ADA section 4).
  * A `revealed` or `prompt` write (or a checked write with no answer) changes no score, count or
    source; what the client sent for them is ignored.
"""
from __future__ import annotations

from typing import Any
from collections.abc import Mapping

SCORE_SOURCE_CLIENT = "client"
SCORE_SOURCE_SERVER = "server"


def merge_progress(stored: Mapping[str, Any] | None, values: Mapping[str, Any], score: Mapping[str, Any] | None) -> dict[str, Any]:
    """The evidence fields to store for this write. `stored` is None for a new row."""
    stored = stored or {}
    stored_best = stored.get("best_accuracy_percent")
    stored_count = int(stored.get("checked_attempt_count") or 0)
    stored_source = stored.get("score_source") or SCORE_SOURCE_CLIENT
    merged = {
        "best_accuracy_percent": stored_best,
        "best_exact": bool(stored.get("best_exact", False)),
        "checked_attempt_count": stored_count,
        "score_source": stored_source,
    }
    if score is None:
        return merged
    computed = int(score["accuracy_percent"])
    exact = bool(score["exact"])
    if stored_source == SCORE_SOURCE_SERVER and stored_best is not None:
        merged["best_accuracy_percent"] = max(int(stored_best), computed)
        merged["best_exact"] = bool(stored.get("best_exact", False)) or exact
    else:
        merged["best_accuracy_percent"] = computed
        merged["best_exact"] = exact
    claimed = int(values.get("checked_attempt_count") or 0)
    merged["checked_attempt_count"] = max(stored_count, min(claimed, stored_count + 1))
    merged["score_source"] = SCORE_SOURCE_SERVER
    return merged
