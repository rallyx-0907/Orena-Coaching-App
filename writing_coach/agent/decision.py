"""Where the turn's decisions are made (spec §7, §20; D16).

Before tools run, a turn asks a few questions: which capability applies here,
whether tools are needed, whether the learner is asking who Orena is, whether
the request is one the learner may make. A `DecisionProvider` answers only the
questions asked. V1 answers with rules and the model; a decision model may
replace it after V1 (D16) without touching the turn.

The stub below answers the capability question deterministically from the
surface and target language - it needs no message - and leaves the rest
neutral: the model decides whether to call tools, the tool gateway enforces
whose data is read, and identity answers arrive with Slice 1b.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from writing_coach.agent.capability_registry import CapabilityRegistry
from writing_coach.agent.context import Tier1Context, TurnInput


class DecisionQuestion(StrEnum):
    CAPABILITY = "capability"
    NEEDS_TOOLS = "needs_tools"
    IDENTITY_QUESTION = "identity_question"
    AUTHORIZATION = "authorization"


@dataclass(frozen=True)
class Decisions:
    capability_ids: tuple[str, ...] = ()
    needs_tools: bool | None = None  # None: let the model decide
    identity_question: bool = False
    authorized: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class DecisionState:
    turn: TurnInput
    tier1: Tier1Context
    registry: CapabilityRegistry


class DecisionProvider(Protocol):
    def decide(self, state: DecisionState, questions: frozenset[DecisionQuestion]) -> Decisions: ...


class StubDecisionProvider:
    def decide(self, state: DecisionState, questions: frozenset[DecisionQuestion]) -> Decisions:
        capability_ids: tuple[str, ...] = ()
        if DecisionQuestion.CAPABILITY in questions:
            target = state.tier1.contract_locale.target
            capability_ids = tuple(entry.id for entry in state.registry.for_surface(state.tier1.surface, target))
        return Decisions(capability_ids=capability_ids)
