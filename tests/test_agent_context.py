"""Turn input, Tier 1 context, provider redaction and the decision stub."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.context import TurnInput, build_tier1
from writing_coach.agent.decision import DecisionQuestion, Decisions, DecisionState, StubDecisionProvider
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.schemas import AppContextSnapshot, ClientInfo, CoachNote, TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.runtime import build_tool_registry


def capabilities():
    """The registry as the app loads it: active capabilities need their tools registered."""

    return load_capability_registry(registered_tools=build_tool_registry(writing_review=lambda essay_id: None).names())

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def snapshot(target="zh-CN", surface="speaking.workspace", selected=True):
    body = {
        "surface": surface,
        "activity_type": "pronunciation_practice",
        "locale": {"interface": "en", "support": "vi", "target": target, "content": target},
        "attempt_id": "att-1",
    }
    if selected:
        body["selected_item"] = {"type": "word", "text": "我"}
    return AppContextSnapshot.model_validate(body)


def note(note_id, weight, expires=None):
    return CoachNote(
        id=note_id, kind="preference", text=f"note {note_id}", weight=weight,
        last_reinforced=datetime(2026, 9, 20, tzinfo=UTC), expires_at=expires,
    )  # fmt: skip


def turn(message=None, **kwargs):
    return TurnInput(
        message=message,
        context=kwargs.get("context", snapshot()),
        client=ClientInfo(ui_version="t"),
        coach_notes=kwargs.get("notes", ()),
        version=1,
    )


def test_a_turn_without_a_message_still_has_its_context():
    tier1 = build_tier1(turn(message=None), now=NOW)
    assert tier1.surface == "speaking.workspace"
    assert tier1.locale.target == "zh" and tier1.contract_locale.target == "zh-CN"
    assert tier1.locale.support == "vi" and tier1.locale.interface == "en"
    assert tier1.selection.text == "我"
    assert dict(tier1.ids) == {"attempt_id": "att-1"}


def test_from_request_keeps_everything_the_request_carried():
    request = TurnRequest.model_validate(
        {
            "contract_version": 1,
            "session_id": "s1",
            "message": "Why?",
            "client": {"ui_version": "t"},
            "context": snapshot().model_dump(mode="json"),
        }
    )
    built = TurnInput.from_request(request)
    assert (built.message, built.session_id, built.version) == ("Why?", "s1", 1)


def test_this_word_resolves_from_the_session_when_the_client_sends_no_selection():
    sessions = SessionCache()
    state, _ = sessions.open(None, "u1")
    state = sessions.save(state.with_context(snapshot()))
    tier1 = build_tier1(turn(context=snapshot(selected=False)), state, now=NOW)
    assert tier1.selection.text == "我"


def test_an_unknown_surface_is_no_surface():
    assert build_tier1(turn(context=snapshot(surface="atlas.home")), now=NOW).surface is None


def test_coach_notes_live_heaviest_first():
    notes = (
        note("light", 0.2),
        note("heavy", 0.9),
        note("expired", 1.0, expires=datetime(2026, 9, 1, tzinfo=UTC)),
        note("naive_future", 0.5, expires=datetime(2026, 12, 1)),
    )
    tier1 = build_tier1(turn(notes=notes), now=NOW)
    assert [n.id for n in tier1.coach_notes] == ["heavy", "naive_future", "light"]


def test_redaction_removes_vendor_and_personal_identity_at_any_depth():
    summary = {
        "learningLanguage": "zh",
        "domains": {
            "writing": {"observations": [{"essayId": 3, "producer": "ollama:qwen3:8b", "score": 71}]},
        },
        "email": "someone@example.com",
        "User_ID": "u1",
        "model": "x",
    }
    redacted = redact_for_provider(summary)
    assert redacted == {
        "learningLanguage": "zh",
        "domains": {"writing": {"observations": [{"essayId": 3, "score": 71}]}},
    }
    assert summary["domains"]["writing"]["observations"][0]["producer"] == "ollama:qwen3:8b"  # input untouched


def test_redaction_covers_every_name_a_tool_argument_may_not_use():
    from writing_coach.agent.redaction import REDACTED_KEYS
    from writing_coach.agent.tools import FORBIDDEN_ARGUMENTS

    assert FORBIDDEN_ARGUMENTS <= REDACTED_KEYS
    assert redact_for_provider({"learner_id": "u1", "owner": "u1", "attempts": [{"uid": "u1", "score": 9}]}) == {
        "attempts": [{"score": 9}]
    }


@pytest.mark.parametrize("target, has_tone", [("zh-CN", True), ("en", False)])
def test_the_stub_picks_capabilities_from_surface_and_language(target, has_tone):
    registry = capabilities()
    state = DecisionState(
        turn=turn(context=snapshot(target=target)),
        tier1=build_tier1(turn(context=snapshot(target=target)), now=NOW),
        registry=registry,
    )
    decisions = StubDecisionProvider().decide(state, frozenset({DecisionQuestion.CAPABILITY}))
    assert "speaking.pronunciation.line" in decisions.capability_ids
    assert ("speaking.pronunciation.tone" in decisions.capability_ids) is has_tone
    assert decisions.needs_tools is None and decisions.authorized and not decisions.identity_question


def test_the_stub_answers_only_what_it_is_asked():
    registry = capabilities()
    state = DecisionState(turn=turn(), tier1=build_tier1(turn(), now=NOW), registry=registry)
    assert StubDecisionProvider().decide(state, frozenset()) == Decisions()
