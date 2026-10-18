"""A1 of issue #256: the provider data-class policy (writing_coach/agent/data_class.py; ORENA_MEMORY.md §8, G8).

The learner pack carries `learning_profile` data: it reaches a model only when the conversation's pinned provider is
cleared for that class; otherwise the turn is what it was before M1 and the record says the pack was withheld. A
provider with no recorded class is `none`; an unreadable configuration refuses to start.
"""

from __future__ import annotations

import pytest

from writing_coach.agent.data_class import GOVERNED_PAYLOADS, NOT_YET_GOVERNED, DataClass, ProviderDataClasses
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.memory_pack import PACK_OPEN, PackBuilder
from writing_coach.agent.provider import ModelRoute
from tests.test_agent_learner_pack import NOW, sources
from tests.test_agent_prompt_cache import Router
from tests.test_agent_turn import hermetic, run, runtime, turn_request  # noqa: F401 - fixture

GEMINI = ModelRoute("gemini", "gemini-3.5-flash-lite")
GROQ = ModelRoute("groq", "openai/gpt-oss-120b")


# --- the record ---------------------------------------------------------------------------------------------------


def test_the_record_parses_provider_and_model_entries():
    classes = ProviderDataClasses.parse("gemini=learning_profile, groq=none, groq:openai/gpt-oss-120b=full_memory")
    assert classes.of("gemini", "anything") is DataClass.LEARNING_PROFILE
    assert classes.of("groq", "openai/gpt-oss-120b") is DataClass.FULL_MEMORY  # a model entry wins
    assert classes.of("groq", "other") is DataClass.NONE
    assert classes.of("deepseek", "x") is DataClass.NONE  # not listed: none
    assert classes.of(None, None) is DataClass.NONE  # provider unknown: cleared for nothing
    assert classes.cleared("gemini", "m", DataClass.LEARNING_PROFILE) and not classes.cleared("gemini", "m", DataClass.FULL_MEMORY)
    assert classes.public() == {"gemini": "learning_profile", "groq": "none", "groq:openai/gpt-oss-120b": "full_memory"}


def test_an_empty_record_clears_no_provider():
    for empty in (ProviderDataClasses.from_env({}), ProviderDataClasses.parse(""), ProviderDataClasses()):
        assert empty.of("gemini", "m") is DataClass.NONE


@pytest.mark.parametrize("text", ["gemini", "gemini=secret", "=none", "gemini:=none", ":m=none",
                                  "gemini=none,gemini=full_memory"])
def test_a_record_that_does_not_parse_refuses_to_start(text):
    with pytest.raises(ValueError):
        ProviderDataClasses.parse(text)


# --- in a turn ------------------------------------------------------------------------------------------------------


def pack_runtime(rounds, *, route=GEMINI, classes=None):
    rt, provider = runtime(rounds)
    rt.pack = PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW)
    rt.router = Router(route)
    rt.data_classes = classes
    records = []
    rt.record_turn = lambda user, record: records.append(record)
    return rt, provider, records


def has_pack(request):
    return any(m.content.startswith(PACK_OPEN) for m in request.messages)


def test_a_cleared_provider_gets_the_pack():
    rt, provider, _ = pack_runtime([reply("a1")], classes=ProviderDataClasses.parse("gemini=learning_profile"))
    run(rt)
    assert has_pack(provider.requests[0])


def test_a_provider_not_cleared_does_not_get_the_pack_and_the_turn_is_as_before():
    rt, provider, records = pack_runtime([reply("a1")], classes=ProviderDataClasses.parse("gemini=none"))
    events = run(rt)
    assert events[-1].name == "done" and not has_pack(provider.requests[0])
    assert records[-1]["learner_pack"] == {"version": "orena-pack/1", "withheld": "provider_not_cleared",
                                           "provider_class": "none"}


def test_with_a_policy_and_no_known_provider_the_pack_is_withheld():
    rt, provider, _ = pack_runtime([reply("a1")], route=None, classes=ProviderDataClasses.parse("gemini=full_memory"))
    run(rt)
    assert not has_pack(provider.requests[0])


def test_a_conversation_that_sent_the_pack_is_never_continued_on_a_provider_cleared_for_less():
    """§8 c: its history may carry what the pack said, so a re-pin to a provider below `learning_profile` answers the
    unavailable path instead of sending the history there (M2-prep 2b; before, the pack alone was withheld)."""
    classes = ProviderDataClasses.parse("gemini=learning_profile,groq=none")
    rt, provider, records = pack_runtime([reply("a1"), reply("a2")], classes=classes)
    first = run(rt)
    session_id = next(e.session_id for e in first if e.name == "session")
    rt.router.selection, rt.router.is_usable = GROQ, (lambda route: route != GEMINI)  # Gemini removed in Admin
    events = run(rt, turn_request("hỏi tiếp", session_id=session_id))
    assert has_pack(provider.requests[0]) and len(provider.requests) == 1  # nothing reached Groq
    assert any(e.name == "error" and e.error_class == "provider_unavailable" for e in events)
    assert records[-1]["data_class"] == {"refused": "conversation_class", "provider_class": "none",
                                         "conversation_class": "learning_profile"}
    state = rt.sessions.get(session_id, "u1") if hasattr(rt.sessions, "get") else None
    assert state is None or not state.model_route_failed  # not a provider failure


def test_a_provider_cleared_as_high_continues_the_conversation():
    classes = ProviderDataClasses.parse("gemini=learning_profile,groq=full_memory")
    rt, provider, _ = pack_runtime([reply("a1"), reply("a2")], classes=classes)
    first = run(rt)
    session_id = next(e.session_id for e in first if e.name == "session")
    rt.router.selection, rt.router.is_usable = GROQ, (lambda route: route != GEMINI)
    run(rt, turn_request("hỏi tiếp", session_id=session_id))
    assert provider.requests[1].route == GROQ and has_pack(provider.requests[1])


def test_without_a_policy_the_pack_is_not_gated():
    rt, provider, _ = pack_runtime([reply("a1")], classes=None)
    run(rt)
    assert has_pack(provider.requests[0])


def test_an_opening_whose_pack_is_withheld_is_sent_the_snapshot(monkeypatch):
    from tests.test_agent_learner_pack import _open, _opening_runtime, _sent

    rt, provider = _opening_runtime(PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW), monkeypatch)
    rt.router, rt.data_classes = Router(GEMINI), ProviderDataClasses.parse("gemini=none")
    _open(rt)
    sent = _sent(provider)
    assert any(c.startswith("snapshot: ") for c in sent) and not any(c.startswith(PACK_OPEN) for c in sent)


def test_the_gate_is_staged_and_none_is_not_a_privacy_guarantee(monkeypatch):
    """G8 is staged (A1, review of PR #263; M2-prep 2b): the payloads in NOT_YET_GOVERNED still reach a `none`
    provider. When a later slice gates one of them, it moves it into GOVERNED_PAYLOADS and changes this test with the
    code that gates it."""
    assert GOVERNED_PAYLOADS == ("learner_pack", "coach_notes", "conversation_history")
    assert NOT_YET_GOVERNED == ("opening_snapshot", "chat_context", "learner_text", "tool_results")
    assert not set(GOVERNED_PAYLOADS) & set(NOT_YET_GOVERNED)
    # the learner's own text reaches a provider that is cleared for nothing
    rt, provider, _ = pack_runtime([reply("a1")], classes=ProviderDataClasses.parse("gemini=none"))
    run(rt, turn_request("Tại sao tôi sai từ này?"))
    assert not has_pack(provider.requests[0])
    assert any("Tại sao tôi sai từ này?" in m.content for m in provider.requests[0].messages)
    # and so does the legacy opening snapshot
    from tests.test_agent_learner_pack import _open, _opening_runtime, _sent

    rt, provider = _opening_runtime(PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW), monkeypatch)
    rt.router, rt.data_classes = Router(GEMINI), ProviderDataClasses.parse("gemini=none")
    _open(rt)
    assert any(c.startswith("snapshot: ") for c in _sent(provider))


# --- coach notes (§8 b; owner 2026-10-18: withheld, and editing them is said to be unavailable) -------------------

NOTE = {"id": "n1", "kind": "preference", "text": "Giải thích thật ngắn gọn", "weight": 0.8,
        "last_reinforced": "2026-10-10T00:00:00Z"}


def with_notes(message="Tại sao tôi sai từ này?", **extra):
    return turn_request(message, coach_notes=[NOTE], **extra)


def sent_notes(request):
    return any(NOTE["text"] in m.content for m in request.messages)


@pytest.mark.parametrize(("record", "sent"), [("gemini=learning_profile", False), ("gemini=none", False),
                                              ("gemini=full_memory", True)])
def test_coach_notes_reach_only_a_provider_cleared_for_full_memory(record, sent):
    rt, provider, records = pack_runtime([reply("a1")], classes=ProviderDataClasses.parse(record))
    run(rt, with_notes())
    assert sent_notes(provider.requests[0]) is sent
    if not sent:
        assert records[-1]["coach_notes"]["withheld"] == "provider_not_cleared"


def test_without_the_gate_coach_notes_are_sent_as_before():
    rt, provider, _ = pack_runtime([reply("a1")], classes=None)
    run(rt, with_notes())
    assert sent_notes(provider.requests[0])
    rt, provider, _ = pack_runtime([reply("a1")], classes=ProviderDataClasses.parse("gemini=none"))
    rt.pack.enabled = False  # the gate is on only with the pack (§8 a)
    run(rt, with_notes())
    assert sent_notes(provider.requests[0])


def test_asking_to_change_a_withheld_note_is_answered_plainly_and_changes_nothing():
    rt, provider, _ = pack_runtime([reply("Được.")], classes=ProviderDataClasses.parse("gemini=learning_profile"))
    events = run(rt, with_notes("Quên ghi chú về giải thích ngắn gọn đi"))
    text = "".join(e.text_delta for e in events if e.name == "segment_delta")
    assert "chưa thể đọc hay sửa ghi chú" in text
    assert not any(e.name == "memory_update" for e in events) and not sent_notes(provider.requests[0])


def test_a_conversation_that_sent_notes_is_not_continued_below_full_memory():
    classes = ProviderDataClasses.parse("gemini=full_memory,groq=learning_profile")
    rt, provider, _ = pack_runtime([reply("a1"), reply("a2")], classes=classes)
    first = run(rt, with_notes())
    session_id = next(e.session_id for e in first if e.name == "session")
    rt.router.selection, rt.router.is_usable = GROQ, (lambda route: route != GEMINI)
    events = run(rt, with_notes("hỏi tiếp", session_id=session_id))
    assert len(provider.requests) == 1 and any(e.name == "error" for e in events)


# --- in a voice session ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("record", "sent"), [("gemini=learning_profile", True), ("gemini=none", False),
                                              ("", False), ("gemini:gemini-3.8-live=full_memory", True)])
def test_the_voice_vendor_gets_the_pack_only_when_cleared(record, sent):
    from tests.test_agent_voice_session import LEARNER, Post, _body, _service

    post = Post()
    service = _service(post)
    service.runtime.pack = PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW)
    service.runtime.data_classes = ProviderDataClasses.parse(record)
    service.open(_body(), LEARNER)
    instruction = post.calls[0][2]["bidiGenerateContentSetup"]["systemInstruction"]["parts"][0]["text"]
    assert (PACK_OPEN in instruction) is sent


def test_voice_gets_coach_notes_only_when_cleared_and_does_not_continue_a_conversation_below_its_class():
    from writing_coach.agent.errors import VoiceUnavailable
    from tests.test_agent_voice_session import LEARNER, Post, _body, _service

    def opened(record, notes=True, sent_class=0):
        post = Post()
        service = _service(post)
        service.runtime.pack = PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW)
        service.runtime.data_classes = ProviderDataClasses.parse(record)
        body = _body()
        if notes:
            body["coach_notes"] = [NOTE]
        if sent_class:
            state, _ = service.runtime.sessions.open(None, LEARNER.user_key)
            service.runtime.sessions.update(state.agent_session_id, LEARNER.user_key,
                                            lambda s: s.with_data_class_sent(sent_class))
            body["session_id"] = state.agent_session_id
        service.open(body, LEARNER)
        return post.calls[0][2]["bidiGenerateContentSetup"]["systemInstruction"]["parts"][0]["text"]

    assert NOTE["text"] not in opened("gemini=learning_profile")
    assert NOTE["text"] in opened("gemini=full_memory")
    with pytest.raises(VoiceUnavailable):
        opened("gemini=learning_profile", sent_class=2)

