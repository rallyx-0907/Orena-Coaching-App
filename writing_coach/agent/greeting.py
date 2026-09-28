"""The opening greeting states one fact from the snapshot, or is built from it (human direction 2026-09-28).

The model writes the greeting (S13) from the snapshot it is given. The live run
showed a greeting with no fact at all ("Hôm nay chúng ta cùng học nhé!"), so the
server checks it: a number the snapshot holds must be in it, and no number the
snapshot does not hold. Otherwise the greeting is built here, from the snapshot:
the words due, else the busiest skill's activity, else that nothing was recorded,
else - the snapshot unread - that progress could not be read. Never a generic line.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from writing_coach.agent import learner_copy

WINDOW_DAYS = 30
_WORDS = {
    **{w: n for n, w in enumerate("zero one two three four five six seven eight nine ten".split())},
    **{w: n for n, w in enumerate("không một hai ba bốn năm sáu bảy tám chín mười".split())},
}
_ZH = {c: n for n, c in enumerate("零一二三四五六七八九十")} | {"两": 2}


def _counts(snapshot: Mapping[str, Any]) -> list[tuple[int, Mapping[str, Any]]]:
    out = []
    for entry in (snapshot.get("skill_summary") or {}).values():
        activity = entry.get("activity") if isinstance(entry, Mapping) else None
        if isinstance(activity, Mapping) and isinstance(activity.get("count"), int) and activity["count"] > 0:
            out.append((activity["count"], entry))
    return out


def facts(snapshot: Mapping[str, Any] | None) -> set[int]:
    """The numbers a greeting may state."""

    if not snapshot:
        return set()
    found = {count for count, _ in _counts(snapshot)}
    due = snapshot.get("review_due")
    if isinstance(due, int) and due > 0:
        found.add(due)
    return found


def numbers_in(text: str) -> set[int]:
    found = {int(d) for d in re.findall(r"\d+", text)}
    found |= {_WORDS[w] for w in re.findall(r"[^\W\d_]+", text.casefold()) if w in _WORDS and _WORDS[w] > 0}
    found |= {_ZH[c] for c in re.findall(r"([一二两三四五六七八九十])\s*[个次篇天词條条]", text)}
    return found


def states_a_fact(text: str, snapshot: Mapping[str, Any] | None) -> bool:
    allowed = facts(snapshot)
    said = numbers_in(text)
    return bool(said & allowed) and said <= allowed | {WINDOW_DAYS}


def built(
    snapshot: Mapping[str, Any] | None,
    *,
    interface: str,
    support: str,
    address: object = None,
) -> str:
    """The greeting built from the snapshot, in the support layer and the learner's address pair."""

    if not snapshot or (snapshot.get("review_due") is None and not _readable(snapshot)):
        key, params = "opening.unread", {}
    elif isinstance(snapshot.get("review_due"), int) and snapshot["review_due"] > 0:
        key, params = "opening.due", {"n": snapshot["review_due"]}
    elif exact := [(c, e) for c, e in _counts(snapshot) if not e["activity"].get("at_least")]:
        count, entry = max(exact, key=lambda item: item[0])
        key, params = "opening.activity", {"n": count, "what": entry["activity"].get("what") or "", "skill": entry["name"]}
    else:
        key, params = "opening.empty", {}
    return learner_copy.text(key, interface=interface, support=support, address=address, **params)[1]


def _readable(snapshot: Mapping[str, Any]) -> bool:
    return any(
        isinstance(entry, Mapping) and entry.get("activity") is not None
        for entry in (snapshot.get("skill_summary") or {}).values()
    )
