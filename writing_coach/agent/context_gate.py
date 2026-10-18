"""The chat context's learner-derived session state, for G8 (ORENA_MEMORY.md §8; review of PR #268).

A turn's context holds the request's own content - the languages, the screen, what is in view, the selection the
request carries, this turn's address, Orena's own open offer - and state carried from earlier in the session:

- `earlier_in_session`: summaries of what tools read for the learner;
- `conversation_focus`: the topic and referents of earlier turns (a word a tool read, an earlier sentence or
  selection) and the head of a text the learner pasted, which is also carried whole into later turns;
- a selection from an earlier request, reused when this request names none.

That carried state is learning data (`CONTEXT_EVIDENCE_CLASS`): it goes only to a provider cleared for it, and when it
is sent it raises the conversation's class.
"""

from __future__ import annotations

from dataclasses import replace

from writing_coach.agent.focus import Focus


def carried_state(turn, tier1, session) -> bool:
    """The context this request would send holds state from earlier in the session."""

    if session is None:
        return False
    reused_selection = turn.context.selected_item is None and tier1.selection is not None
    return bool(session.recent_tool_results or session.focus.to_context() is not None or session.focus.pasted
                or reused_selection)  # fmt: skip


def without_carried_state(turn, tier1, session):
    """The tier-1 context and session with only the request's own content."""

    if session is not None:
        session = replace(session, recent_tool_results=(), focus=Focus(), last_selected_entity=None)
    if turn.context.selected_item is None and tier1.selection is not None:
        tier1 = replace(tier1, selection=None)
    return tier1, session
