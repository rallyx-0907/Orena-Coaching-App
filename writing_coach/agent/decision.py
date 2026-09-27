"""Where the turn's decisions are made (spec §7, §20; D16).

Before tools run, a turn asks a few questions: which capability applies here,
whether tools are needed, whether the learner is asking who Orena is, whether
the request is one the learner may make. A `DecisionProvider` answers only the
questions asked. V1 answers with rules and the model; a decision model may
replace it after V1 (D16) without touching the turn.

`RuleDecisionProvider` answers two questions by rule. The capability
question comes from the surface and target language and needs no message. The
identity question (spec §35) comes from the message alone, by the strict rules
in `identity.py`; a turn that is one is answered from copy before any model is
asked. The rest stays neutral: the model decides whether to call tools, and
the tool gateway enforces whose data is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from writing_coach.agent.capability_registry import CapabilityRegistry
from writing_coach.agent.context import Tier1Context, TurnInput
from writing_coach.agent.identity import IdentityQuestion, identity_question


class DecisionQuestion(StrEnum):
    CAPABILITY = "capability"
    NEEDS_TOOLS = "needs_tools"
    IDENTITY_QUESTION = "identity_question"
    AUTHORIZATION = "authorization"


@dataclass(frozen=True)
class Decisions:
    capability_ids: tuple[str, ...] = ()
    needs_tools: bool | None = None  # None: let the model decide
    identity: IdentityQuestion | None = None  # the learner asked who, or which model, Orena is
    authorized: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class DecisionState:
    turn: TurnInput
    tier1: Tier1Context
    registry: CapabilityRegistry


class DecisionProvider(Protocol):
    def decide(self, state: DecisionState, questions: frozenset[DecisionQuestion]) -> Decisions: ...


class RuleDecisionProvider:
    def decide(self, state: DecisionState, questions: frozenset[DecisionQuestion]) -> Decisions:
        capability_ids: tuple[str, ...] = ()
        if DecisionQuestion.CAPABILITY in questions:
            target = state.tier1.contract_locale.target
            capability_ids = tuple(entry.id for entry in state.registry.for_surface(state.tier1.surface, target))
        identity = None
        if DecisionQuestion.IDENTITY_QUESTION in questions:
            identity = identity_question(state.turn.message)
        return Decisions(capability_ids=capability_ids, identity=identity)
