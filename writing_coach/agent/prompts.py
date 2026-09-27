"""What the model is told: one stable instruction, then this turn's context.

The instruction never changes between learners or turns, so a provider can
cache it (spec §10). Everything that varies - languages, where the learner is,
what is selected, their coach notes, what the last turns read - goes in a
second message as JSON, redacted before it leaves (spec §36). Nothing here
depends on the learner having typed something.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from writing_coach.agent.capability_registry import CapabilityEntry
from writing_coach.agent.context import Tier1Context, TurnInput
from writing_coach.agent.locale import to_internal
from writing_coach.agent.provider import ProviderMessage
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.session import AgentSessionState
from writing_coach.core.language_registry import language as learning_language
from writing_coach.core.support_languages import support_language

INSTRUCTION = """You are Orena, the assistant and learning coach inside the Orena language-learning app.

Who you are: Orena. Never name or describe the model, company or provider behind you; if asked, you are Orena.

How you answer:
- Write in the learner's support language (context.languages.support). Material being learned may appear in the
  target language. Keep it short: two to four sentences unless the learner asks for more. No slogans, no filler
  encouragement, no repeating the question.
- The context says where the learner is and what they selected. Use it; never ask them to repeat what is on screen.

Evidence before claims:
- Say the learner made an error only when a tool result shows it, and then call cite_evidence with those ids.
- A lower score the provider did not flag is not an error: say it scored lower, and do not guess why.
- With no evidence, say you do not have it and how to get it (try again, submit the piece).

Data and actions:
- Tools read only the signed-in learner's own data. You cannot see other learners' data; if asked, say so plainly.
  Never pass a learner, user or account id to a tool.
- Never mention routes, URLs or internal screen names. To offer something the app can do, call propose_action;
  if it is refused, say it in words instead.
- Use suggest_next, set_voice_style and add_reference only when they help this answer."""


def _language_name(contract_code: str | None, *, target: bool) -> str | None:
    if contract_code is None:
        return None
    internal = to_internal(contract_code)
    if target:
        profile = learning_language(internal)
        return profile.name if profile else contract_code
    definition = support_language(internal)
    return definition.translation_label if definition else contract_code


def context_document(
    turn: TurnInput,
    tier1: Tier1Context,
    capabilities: Sequence[CapabilityEntry],
    session: AgentSessionState | None,
) -> dict:
    locale = tier1.contract_locale
    document = {
        "languages": {
            "support": {"code": locale.support, "name": _language_name(locale.support, target=False)},
            "target": {"code": locale.target, "name": _language_name(locale.target, target=True)},
            "interface": locale.interface,
            "content": locale.content,
        },
        "surface": tier1.surface,
        "activity": tier1.activity_type,
        "in_view": dict(tier1.ids),
        "selection": tier1.selection.model_dump(exclude_none=True) if tier1.selection else None,
        "capabilities_here": [{"id": entry.id, "title": entry.title["en"]} for entry in capabilities],
        "coach_notes": [{"kind": note.kind, "text": note.text} for note in tier1.coach_notes],
        "earlier_in_session": [
            {"tool": record.tool, "summary": record.summary} for record in (session.recent_tool_results if session else ())
        ],
    }
    return redact_for_provider(document)


def opening_messages(
    turn: TurnInput,
    tier1: Tier1Context,
    capabilities: Sequence[CapabilityEntry],
    session: AgentSessionState | None,
) -> list[ProviderMessage]:
    context = json.dumps(context_document(turn, tier1, capabilities, session), ensure_ascii=False)
    messages = [
        ProviderMessage(role="system", content=INSTRUCTION),
        ProviderMessage(role="system", content=f"context: {context}"),
    ]
    if turn.message is not None:
        messages.append(ProviderMessage(role="user", content=turn.message))
    return messages
