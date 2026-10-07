"""The one generic pending interaction (ORENA_INTELLIGENCE_ARCHITECTURE §7, §15).

An offer Orena has made and the learner has not answered: "save abate?", "open this lesson?". It is data, not a
feature - no `pendingSaveWord`, no `pendingNavigate`; the same record holds any action the contract allows. It lives
in the agent session (this process, for the session's life: a Phase 1 limit, not a design - the record is plain data
so it can move to a store without changing what reads it).

It ends in exactly one way, and nothing else clears it:

    completed  the learner accepted: the runtime ran it, once, under this record's id
    cancelled  the learner declined
    expired    `ttl_turns` learner turns passed without an answer
    replaced   a newer offer took its place

A question asked in between ends nothing. The model reads the learner's words and says what they meant with the
`resolve_pending` reply tool; the runtime does the rest.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

KIND_ACTION_OFFER = "action_offer"
PENDING, COMPLETED, CANCELLED, EXPIRED, REPLACED = "pending", "completed", "cancelled", "expired", "replaced"
CONFIRM, CANCEL = "confirm", "cancel"
DECISIONS = (CONFIRM, CANCEL)
DEFAULT_TTL_TURNS = 6  # learner turns an unanswered offer stays open
SETTLED_KEPT = 10


RUN_WINDOW_TURNS = 3  # an action that ran this recently is not run again by the same words said twice
RUNS_KEPT = 10


def action_key(action: str, payload: Mapping[str, Any]) -> str:
    """What an action is, whoever offered it or asked for it: the same word saved is the same action."""

    return json.dumps([action, dict(payload)], sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class PendingInteraction:
    id: str
    kind: str
    action: str
    payload: Mapping[str, Any]
    label: str
    created_turn: int  # the session's learner-turn count when it was offered
    ttl_turns: int = DEFAULT_TTL_TURNS
    status: str = field(default=PENDING)

    @classmethod
    def offer(cls, action: str, payload: Mapping[str, Any], label: str, *, turn: int,
              ttl_turns: int = DEFAULT_TTL_TURNS) -> PendingInteraction:
        """An offer of `action`, with an id that is the same wherever and however often it is read back."""

        digest = hashlib.sha1((KIND_ACTION_OFFER + action_key(action, payload)).encode("utf-8")).hexdigest()[:10]
        return cls(id=f"p{turn}-{digest}", kind=KIND_ACTION_OFFER, action=action, payload=dict(payload), label=label,
                   created_turn=turn, ttl_turns=ttl_turns)

    def live_at(self, turn: int) -> bool:
        return self.status == PENDING and turn - self.created_turn < self.ttl_turns

    def settled(self, status: str) -> PendingInteraction:
        return replace(self, status=status)
