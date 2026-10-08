"""Regressions for the four review findings on PR #92 (conversation kernel): each test fails on the code it was written for.

1. A learner who declines an open offer by voice ends it - it cannot run on a later "yes".
2. A spoken utterance is a turn of the conversation, as a typed one is (offers expire, a run is not blocked forever).
3. The transcript sent at the end of a voice session keeps the order: each reply sits behind the words it answers.
4. The whole assembled prompt - recent turns, summary, pasted text, context - stays inside the turn's input budget.
"""

from __future__ import annotations

from dataclasses import replace

from writing_coach.agent.fake_provider import reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.pending import DEFAULT_TTL_TURNS
from writing_coach.agent.prompts import CARRIED_HEAD
from writing_coach.agent.session import AgentSessionState, ConversationTurn
from tests.test_agent_pending import context_of, request, session_of
from tests.test_agent_turn import VI, hermetic, run, runtime  # noqa: F401 - fixture
from tests.test_agent_voice_kernel import LEARNER, build, open_voice, say, typed


def state_of(rt, sid):
    return rt.sessions.get(sid, LEARNER.user_key)


def relay(service, voice_id, name, args, heard):
    return service.relay(voice_id, [{"id": "c1", "name": name, "args": args}], LEARNER, heard=heard)


# -- 1. declining by voice -------------------------------------------------------------------------------------------


def test_voice_can_decline_an_open_offer_and_it_ends():
    rt, provider, service, post = build([reply("Ok.")])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "mitigate nghĩa là gì")  # a button, not asked for: the offer is open
    pending = state_of(rt, answer["session_id"]).live_pending()
    assert pending is not None
    out = relay(service, voice_id, "resolve_pending", {"id": pending.id, "decision": "cancel"}, "thôi, không lưu")
    assert "accepted" in out["responses"][0]["response"]["result"]
    state = state_of(rt, answer["session_id"])
    assert state.live_pending() is None and (pending.id, "cancelled") in state.settled
    typed(rt, "cảm ơn", answer["session_id"])
    assert "pending_interaction" not in context_of(provider.requests[-1])


def test_a_declined_offer_does_not_run_on_a_later_yes():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "mitigate nghĩa là gì")
    pending = state_of(rt, answer["session_id"]).live_pending()
    relay(service, voice_id, "resolve_pending", {"id": pending.id, "decision": "cancel"}, "không, thôi")
    out = relay(service, voice_id, "resolve_pending", {"id": pending.id, "decision": "confirm"}, "ừ lưu đi")
    assert "refused" in out["responses"][0]["response"]["result"]
    assert not [e for e in out["events"] if e["event"] == "action"]


def test_voice_has_the_tool_to_answer_an_offer():
    from writing_coach.agent.voice_session import VOICE_REPLY_TOOLS

    assert "resolve_pending" in VOICE_REPLY_TOOLS


def test_voice_confirming_by_id_runs_the_offer_once():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "mitigate nghĩa là gì")
    pending = state_of(rt, answer["session_id"]).live_pending()
    out = relay(service, voice_id, "resolve_pending", {"id": pending.id, "decision": "confirm"}, "ừ lưu đi")
    (event,) = [e for e in out["events"] if e["event"] == "action"]
    assert event["data"]["open"] is True and out["open"] == event["data"]["id"]
    assert state_of(rt, answer["session_id"]).live_pending() is None


# -- 2. a spoken utterance is a turn ---------------------------------------------------------------------------------


def test_each_spoken_utterance_is_one_turn_however_many_calls_it_makes():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    before = state_of(rt, answer["session_id"]).turn_count
    relay(service, voice_id, "do_action", {"type": "save_word", "text": "mitigate"}, "mitigate là gì")
    relay(service, voice_id, "do_action", {"type": "save_word", "text": "mitigate"}, "mitigate là gì")  # same utterance
    assert state_of(rt, answer["session_id"]).turn_count == before + 1
    relay(service, voice_id, "do_action", {"type": "save_word", "text": "mitigate"}, "còn từ khác thì sao")
    assert state_of(rt, answer["session_id"]).turn_count == before + 2


def test_an_offer_expires_in_a_voice_only_conversation():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "mitigate nghĩa là gì")
    assert state_of(rt, answer["session_id"]).live_pending() is not None
    for n in range(DEFAULT_TTL_TURNS):
        relay(service, voice_id, "get_current_word_info", {}, f"một câu khác số {n}")
    assert state_of(rt, answer["session_id"]).live_pending() is None


def test_a_run_by_voice_is_not_blocked_for_ever():
    from writing_coach.agent.pending import RUN_WINDOW_TURNS

    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "lưu mitigate đi", requested=True)
    assert state_of(rt, answer["session_id"]).recent_runs()
    for n in range(RUN_WINDOW_TURNS):
        relay(service, voice_id, "get_current_word_info", {}, f"nói chuyện khác {n}")
    assert not state_of(rt, answer["session_id"]).recent_runs()


def test_a_transcript_turn_the_server_never_heard_counts_as_a_turn_too():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    before = state_of(rt, answer["session_id"]).turn_count
    service.end(answer["voice_session_id"], LEARNER, transcript=[
        {"role": "user", "text": "xin chào"}, {"role": "assistant", "text": "Chào bạn."},
        {"role": "user", "text": "hôm nay học gì"}, {"role": "assistant", "text": "Ôn từ vựng nhé."},
    ])
    assert state_of(rt, answer["session_id"]).turn_count == before + 2


# -- 3. transcript order ---------------------------------------------------------------------------------------------


def test_the_transcript_keeps_each_reply_behind_the_words_it_answers():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "scarcity là gì")
    relay(service, voice_id, "get_current_word_info", {}, "cho ví dụ điện")  # both heard through tool relays
    service.end(voice_id, LEARNER, transcript=[
        {"role": "user", "text": "scarcity là gì"}, {"role": "assistant", "text": "Khan hiếm."},
        {"role": "user", "text": "cho ví dụ điện"}, {"role": "assistant", "text": "Điện khan hiếm vào mùa hè."},
    ])
    turns = [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert turns == [("user", "scarcity là gì"), ("assistant", "Khan hiếm."),
                     ("user", "cho ví dụ điện"), ("assistant", "Điện khan hiếm vào mùa hè.")]


def test_a_transcript_mixing_heard_and_unheard_turns_keeps_the_order():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "câu hai")  # only the second was heard through a tool
    service.end(voice_id, LEARNER, transcript=[
        {"role": "user", "text": "câu một"}, {"role": "assistant", "text": "trả lời một"},
        {"role": "user", "text": "câu hai"}, {"role": "assistant", "text": "trả lời hai"},
    ])
    turns = [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert turns == [("user", "câu một"), ("assistant", "trả lời một"), ("user", "câu hai"), ("assistant", "trả lời hai")]


def test_the_same_words_said_twice_match_in_order():
    limits = AgentLimits()
    state = AgentSessionState("s", "u", 0.0, 0.0).with_spoken(
        (ConversationTurn("user", "ừ"), ConversationTurn("user", "ừ")), limits)
    done = state.with_transcript((ConversationTurn("user", "ừ"), ConversationTurn("assistant", "một"),
                                  ConversationTurn("user", "ừ"), ConversationTurn("assistant", "hai")),
                                 frozenset({"ừ"}), limits)
    assert [(t.role, t.text) for t in done.recent_turns] == [("user", "ừ"), ("assistant", "một"), ("user", "ừ"),
                                                             ("assistant", "hai")]


# -- 4. the budget covers the whole prompt ---------------------------------------------------------------------------


def tokens(req):
    return sum((len(m.content) + 3) // 4 for m in req.messages)


PASTE = "Remote work has changed how people live. " * 200  # 8,400 characters


def long_conversation(budget):
    """A pasted text, then several long turns, a summary, and a last question - under `budget` input tokens."""

    limits = AgentLimits(max_input_tokens_per_turn=budget, compact_after_turns=100, compact_after_chars=10**9)
    rt, provider = runtime([reply(f"a{n} " + "x" * 600) for n in range(12)], limits=limits)
    events = run(rt, request(PASTE))
    sid = session_of(events)
    for n in range(5):
        run(rt, request(f"câu hỏi dài số {n} " + "y" * 500, sid))
    rt.sessions.update(sid, VI.user_key, lambda s: replace(s, summary="TÓM TẮT: đã nói về remote work."))
    run(rt, request("đoạn thứ 3 có yếu không?", sid))
    return provider.requests[-1]


def base_tokens():
    rt, provider = runtime([reply("ok")])
    run(rt, request("hi"))
    return tokens(provider.requests[-1])


def test_the_assembled_prompt_stays_inside_the_input_budget():
    budget = base_tokens() + 2_500
    sent = long_conversation(budget)
    assert tokens(sent) <= budget
    assert sent.messages[-1].content == "đoạn thứ 3 có yếu không?"  # the learner's words always stay
    carried = [m.content for m in sent.messages if m.content.startswith(CARRIED_HEAD)]
    assert carried and "TÓM TẮT" in carried[0]  # the summary stays
    assert any(m.role == "assistant" for m in sent.messages[-3:])  # the newest exchange stays, the oldest went


def test_the_pasted_text_is_cut_to_what_fits_not_sent_whole():
    budget = base_tokens() + 1_500
    sent = long_conversation(budget)
    assert tokens(sent) <= budget
    carried = "".join(m.content for m in sent.messages if m.content.startswith(CARRIED_HEAD))
    assert "Remote work has changed" in carried and "left out" in carried


def test_within_the_budget_nothing_is_dropped():
    sent = long_conversation(AgentLimits().max_input_tokens_per_turn)
    users = [m.content for m in sent.messages if m.role == "user"]
    assert PASTE in users or any(PASTE in m.content for m in sent.messages)  # nothing was cut
    assert sum(1 for m in sent.messages if m.content.startswith("câu hỏi dài")) == 5
