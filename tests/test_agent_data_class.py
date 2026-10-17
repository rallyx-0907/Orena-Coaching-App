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


def test_a_pack_built_for_a_cleared_provider_is_not_sent_after_a_repin_to_one_that_is_not():
    classes = ProviderDataClasses.parse("gemini=learning_profile,groq=none")
    rt, provider, _ = pack_runtime([reply("a1"), reply("a2")], classes=classes)
    first = run(rt)
    session_id = next(e.session_id for e in first if e.name == "session")
    rt.router.selection, rt.router.is_usable = GROQ, (lambda route: route != GEMINI)  # Gemini removed in Admin
    run(rt, turn_request("hỏi tiếp", session_id=session_id))
    assert has_pack(provider.requests[0]) and provider.requests[1].route == GROQ and not has_pack(provider.requests[1])


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


def test_the_gate_is_learner_pack_clearance_only_and_none_is_not_a_privacy_guarantee(monkeypatch):
    """A1 is a staged, partial G8 (review of PR #263). `none` means "not cleared for the M1 learner pack": the payloads
    in NOT_YET_GOVERNED still reach a `none` provider. When a later slice gates one of them, it moves it into
    GOVERNED_PAYLOADS and changes this test with the code that gates it."""
    assert GOVERNED_PAYLOADS == ("learner_pack",)
    assert NOT_YET_GOVERNED == ("opening_snapshot", "chat_context", "coach_notes", "learner_text", "tool_results")
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
