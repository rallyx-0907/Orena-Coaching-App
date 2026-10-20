"""The Reading rights gate (D-250, amends D-190): an article is published only when its rights are clear.

D-190 let an administrator publish over unclear rights or attribution with `acknowledge_warnings` and a reason. That
override is gone (Hermes for the owner, 2026-10-21, PRE-203): every former warning is now a refusal, like Media's
`cleared`-only gate (D-105's hard gate, restored).

- **Rights**, from the article's own snapshot with the administrator's recorded answers folded over it (#410's
  `publication_rights`; an article with no rights of its own reads its source's policy):
  - the republish right must be `allowed` (`rights_not_cleared` when denied, `rights_unknown` when never answered);
  - for an adapted text, the adapt right too (`adaptation_not_cleared`, `adaptation_unknown`).
- **Credit** (D-189 §4): where the terms require attribution, an incomplete credit refuses (`provenance_missing`), and
  whether attribution is required must be answered (`attribution_unknown`).

The repository refuses (`RightsRefused`), so a script that publishes directly is stopped too; the admin route translates
it into 409 `reading_rights_not_cleared` with the blockers. Nothing already published is taken down by this gate: the
read-only checker lists the published articles it would refuse (`scripts/check_published_reading_rights_gate.py`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from writing_coach.reading_provenance import provenance_blockers


class RightsRefused(Exception):
    """Publishing an article whose rights are not clear (D-250). There is no override."""

    def __init__(self, blockers: Sequence[Mapping[str, str]]) -> None:
        self.blockers = [dict(item) for item in blockers]
        super().__init__(", ".join(item["code"] for item in self.blockers))


def publication_rights(article: Mapping[str, Any]) -> Mapping[str, Any]:
    """The rights the gate reads: `{basis, state}` from the article projection (#410)."""

    source = article.get("source") or {}
    found = source.get("publication_rights")
    if isinstance(found, Mapping):
        return found
    return {"basis": "snapshot", "state": source.get("rights_state") or {}}


def rights_blockers(article: Mapping[str, Any]) -> list[dict[str, str]]:
    """Everything that stops this article being published, in a stable order; empty when its rights are clear."""

    state = publication_rights(article).get("state") or {}
    blockers: list[dict[str, str]] = []
    republish = state.get("can_republish", "unknown")
    if republish == "denied":
        blockers.append({"code": "rights_not_cleared", "question": "can_republish"})
    elif republish != "allowed":
        blockers.append({"code": "rights_unknown", "question": "can_republish"})
    if article.get("is_adapted"):
        adapt = state.get("can_adapt", "unknown")
        if adapt == "denied":
            blockers.append({"code": "adaptation_not_cleared", "question": "can_adapt"})
        elif adapt != "allowed":
            blockers.append({"code": "adaptation_unknown", "question": "can_adapt"})
    blockers.extend(provenance_blockers(article.get("provenance") or {}))
    if state.get("attribution_required", "unknown") == "unknown":
        blockers.append({"code": "attribution_unknown", "question": "attribution_required"})
    return blockers
