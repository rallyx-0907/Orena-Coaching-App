"""What a turn starts from, and the context every turn carries (spec §10 Tier 1).

A turn is built from the request, but nothing downstream assumes the learner
typed something: `TurnInput.message` may be None, and Tier 1 is assembled from
where the learner is and what they have in view. That keeps a turn the client
opens without a message (proposed for contract v2) a small addition, not a
rewrite. Contract v1 requests always carry a message.

Tier 1 is small and always sent: locale in the backend's own codes, the known
surface, the activity, the selection (or the session's last one, so "this
word" still resolves), the ids in view and the live coach notes, heaviest
first. Tiers 2 and 3 are tool reads, not context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from writing_coach.agent.locale import InternalLocale
from writing_coach.agent.schemas import AppContextSnapshot, ClientInfo, CoachNote, ContractLocale, SelectedItem, TurnRequest
from writing_coach.agent.session import AgentSessionState

CONTEXT_IDS = ("lesson_id", "content_id", "attempt_id", "take_ref", "essay_id")


@dataclass(frozen=True)
class TurnInput:
    message: str | None
    context: AppContextSnapshot
    client: ClientInfo
    coach_notes: tuple[CoachNote, ...]
    version: int
    session_id: str | None = None

    @classmethod
    def from_request(cls, request: TurnRequest) -> TurnInput:
        return cls(
            message=request.message,
            context=request.context,
            client=request.client,
            coach_notes=tuple(request.coach_notes),
            version=request.version,
            session_id=request.session_id,
        )


@dataclass(frozen=True)
class Tier1Context:
    locale: InternalLocale
    contract_locale: ContractLocale
    surface: str | None
    activity_type: str | None
    selection: SelectedItem | None
    ids: Mapping[str, str]
    coach_notes: tuple[CoachNote, ...]


def live_coach_notes(notes: tuple[CoachNote, ...], *, now: datetime) -> tuple[CoachNote, ...]:
    def aware(moment: datetime) -> datetime:
        return moment if moment.tzinfo else moment.replace(tzinfo=UTC)

    live = [note for note in notes if note.expires_at is None or aware(note.expires_at) > now]
    return tuple(sorted(live, key=lambda note: (-note.weight, note.id)))


def build_tier1(
    turn: TurnInput, session: AgentSessionState | None = None, *, now: datetime | None = None
) -> Tier1Context:
    context = turn.context
    moment = now or datetime.now(UTC)
    selection = context.selected_item or (session.last_selected_entity if session else None)
    ids = {name: getattr(context, name) for name in CONTEXT_IDS if getattr(context, name)}
    return Tier1Context(
        locale=context.locale.internal(),
        contract_locale=context.locale,
        surface=context.known_surface,
        activity_type=context.activity_type,
        selection=selection,
        ids=MappingProxyType(ids),
        coach_notes=live_coach_notes(turn.coach_notes, now=moment),
    )
