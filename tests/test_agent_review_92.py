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


def relay(service, voice_id, name, args, heard, utterance=None):
    return service.relay(voice_id, [{"id": "c1", "name": name, "args": args}], LEARNER, heard=heard, utterance=utterance)


def end_with(service, voice_id, items):
    return service.end(voice_id, LEARNER, transcript=items)


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


# -- 2. a spoken utterance is a turn, by its identity -----------------------------------------------------------------


def turns_of(rt, answer):
    return state_of(rt, answer["session_id"]).turn_count


def test_an_utterance_is_one_turn_whatever_tools_it_called():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id, before = answer["voice_session_id"], turns_of(rt, answer)
    relay(service, voice_id, "get_current_word_info", {}, "mitigate là gì", "u1")  # one tool...
    relay(service, voice_id, "get_current_word_info", {}, "mitigate là gì", "u1")  # ...and another, same utterance
    assert turns_of(rt, answer) == before + 1
    service.utterance_turn(voice_id, "u1", "mitigate là gì", LEARNER)  # its boundary: already counted
    assert turns_of(rt, answer) == before + 1
    service.utterance_turn(voice_id, "u2", "chào bạn", LEARNER)  # no tool at all
    assert turns_of(rt, answer) == before + 2


def test_a_tool_first_next_utterance_does_not_take_the_words_of_the_one_before():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "mitigate là gì", "u1")
    service.utterance_turn(voice_id, "u1", "mitigate là gì", LEARNER)  # u1 closes
    relay(service, voice_id, "get_current_word_info", {}, None, "u2")  # u2's tool call, before its transcript
    assert turns_of(rt, answer) == 2
    assert [(t.text, t.ref.rsplit(":", 1)[1]) for t in state_of(rt, answer["session_id"]).recent_turns] == [("mitigate là gì", "u1")]
    service.utterance_turn(voice_id, "u2", "cho ví dụ", LEARNER)  # its words arrive with its boundary
    texts = [(t.text, t.ref.rsplit(":", 1)[1]) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert texts == [("mitigate là gì", "u1"), ("cho ví dụ", "u2")] and turns_of(rt, answer) == 2


def test_the_same_words_said_twice_are_two_turns_and_the_words_are_not_the_identity():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id, before = answer["voice_session_id"], turns_of(rt, answer)
    service.utterance_turn(voice_id, "u1", "ừ", LEARNER)
    service.utterance_turn(voice_id, "u2", "ừ", LEARNER)
    assert turns_of(rt, answer) == before + 2
    assert [t.text for t in state_of(rt, answer["session_id"]).recent_turns] == ["ừ", "ừ"]
    service.utterance_turn(voice_id, "u2", "ừ", LEARNER)  # the client's retry of a boundary
    assert turns_of(rt, answer) == before + 2


def test_the_words_of_an_utterance_are_put_in_once():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "scarcity là gì", "u1")
    service.utterance_turn(voice_id, "u1", "scarcity là gì", LEARNER)
    assert [t.text for t in state_of(rt, answer["session_id"]).recent_turns] == ["scarcity là gì"]


def test_a_boundary_with_no_identity_counts_nothing():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    before = turns_of(rt, answer)
    assert service.utterance_turn(answer["voice_session_id"], None, "xin chào", LEARNER)["counted"] is False
    assert turns_of(rt, answer) == before


def test_an_offer_expires_in_a_voice_only_conversation_even_with_no_tool_calls():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "mitigate nghĩa là gì", "u0")
    assert state_of(rt, answer["session_id"]).live_pending() is not None
    for n in range(1, DEFAULT_TTL_TURNS + 1):
        service.utterance_turn(voice_id, f"u{n}", "một câu khác", LEARNER)
    assert state_of(rt, answer["session_id"]).live_pending() is None


def test_a_run_by_voice_is_not_blocked_for_ever():
    from writing_coach.agent.pending import RUN_WINDOW_TURNS

    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    say(service, voice_id, "lưu mitigate đi", "u0", requested=True)
    assert state_of(rt, answer["session_id"]).recent_runs()
    for n in range(1, RUN_WINDOW_TURNS + 1):
        service.utterance_turn(voice_id, f"u{n}", "nói chuyện khác", LEARNER)
    assert not state_of(rt, answer["session_id"]).recent_runs()


def test_a_transcript_turn_the_server_never_heard_counts_as_a_turn_too():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    before = turns_of(rt, answer)
    end_with(service, answer["voice_session_id"], [
        {"role": "user", "text": "xin chào", "utterance": "u1"}, {"role": "assistant", "text": "Chào bạn.", "utterance": "u1"},
        {"role": "user", "text": "hôm nay học gì", "utterance": "u2"},
        {"role": "assistant", "text": "Ôn từ vựng nhé.", "utterance": "u2"},
    ])
    assert turns_of(rt, answer) == before + 2


def test_an_utterance_counted_at_its_boundary_is_not_counted_again_by_the_transcript():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    service.utterance_turn(voice_id, "u1", None, LEARNER)  # counted; its words had not arrived
    before = turns_of(rt, answer)
    end_with(service, voice_id, [{"role": "user", "text": "xin chào", "utterance": "u1"},
                                 {"role": "assistant", "text": "Chào.", "utterance": "u1"}])
    assert turns_of(rt, answer) == before
    assert [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns] == [
        ("user", "xin chào"), ("assistant", "Chào.")]


# -- 3. transcript reconciliation: occurrences of this voice session only ----------------------------------------------


def test_a_typed_yes_before_voice_is_not_taken_for_the_spoken_yes():
    rt, _, service, _ = build([reply("Ok.")])
    sid = session_of(typed(rt, "yes"))  # typed "yes" first
    answer = open_voice(service, sid)
    voice_id = answer["voice_session_id"]
    service.utterance_turn(voice_id, "u1", "yes", LEARNER)  # then spoken "yes"
    end_with(service, voice_id, [{"role": "user", "text": "yes", "utterance": "u1"},
                                 {"role": "assistant", "text": "Right.", "utterance": "u1"}])
    turns = [(t.role, t.text) for t in state_of(rt, sid).recent_turns]
    assert turns == [("user", "yes"), ("assistant", "Ok."), ("user", "yes"), ("assistant", "Right.")]


def test_a_spoken_yes_never_heard_by_the_server_is_added_not_matched_to_a_typed_one():
    rt, _, service, _ = build([reply("Ok.")])
    sid = session_of(typed(rt, "yes"))
    answer = open_voice(service, sid)
    end_with(service, answer["voice_session_id"], [{"role": "user", "text": "yes", "utterance": "u1"},
                                                   {"role": "assistant", "text": "Right.", "utterance": "u1"}])
    turns = [(t.role, t.text) for t in state_of(rt, sid).recent_turns]
    assert turns == [("user", "yes"), ("assistant", "Ok."), ("user", "yes"), ("assistant", "Right.")]


def test_repeated_identical_spoken_turns_keep_their_own_replies():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    for n in (1, 2, 3):
        service.utterance_turn(voice_id, f"u{n}", "ừ", LEARNER)
    items = []
    for n in (1, 2, 3):
        items += [{"role": "user", "text": "ừ", "utterance": f"u{n}"},
                  {"role": "assistant", "text": f"trả lời {n}", "utterance": f"u{n}"}]
    end_with(service, voice_id, items)
    turns = [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert turns == [("user", "ừ"), ("assistant", "trả lời 1"), ("user", "ừ"), ("assistant", "trả lời 2"),
                     ("user", "ừ"), ("assistant", "trả lời 3")]


def test_the_transcript_keeps_each_reply_behind_the_words_it_answers():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "scarcity là gì", "u1")
    relay(service, voice_id, "get_current_word_info", {}, "cho ví dụ điện", "u2")  # both heard through tool relays
    end_with(service, voice_id, [
        {"role": "user", "text": "scarcity là gì", "utterance": "u1"}, {"role": "assistant", "text": "Khan hiếm.", "utterance": "u1"},
        {"role": "user", "text": "cho ví dụ điện", "utterance": "u2"},
        {"role": "assistant", "text": "Điện khan hiếm vào mùa hè.", "utterance": "u2"},
    ])
    turns = [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert turns == [("user", "scarcity là gì"), ("assistant", "Khan hiếm."),
                     ("user", "cho ví dụ điện"), ("assistant", "Điện khan hiếm vào mùa hè.")]


def test_a_transcript_mixing_heard_and_unheard_turns_keeps_the_order():
    rt, _, service, _ = build([])
    answer = open_voice(service)
    voice_id = answer["voice_session_id"]
    relay(service, voice_id, "get_current_word_info", {}, "câu hai", "u2")  # only the second reached the server
    end_with(service, voice_id, [
        {"role": "user", "text": "câu một", "utterance": "u1"}, {"role": "assistant", "text": "trả lời một", "utterance": "u1"},
        {"role": "user", "text": "câu hai", "utterance": "u2"}, {"role": "assistant", "text": "trả lời hai", "utterance": "u2"},
    ])
    turns = [(t.role, t.text) for t in state_of(rt, answer["session_id"]).recent_turns]
    assert turns == [("user", "câu một"), ("assistant", "trả lời một"), ("user", "câu hai"), ("assistant", "trả lời hai")]


def test_the_voice_sessions_identity_is_part_of_the_turns_identity():
    limits = AgentLimits()
    state = AgentSessionState("s", "u", 0.0, 0.0).with_spoken((ConversationTurn("user", "ừ", "voiceA:u1"),), limits)
    done = state.with_transcript((ConversationTurn("user", "ừ", "voiceB:u1"), ConversationTurn("assistant", "r", "voiceB:u1")), limits)
    assert [(t.role, t.ref) for t in done.recent_turns] == [("user", "voiceA:u1"), ("user", "voiceB:u1"), ("assistant", "voiceB:u1")]


# -- 4. the budget covers the whole prompt ---------------------------------------------------------------------------


def tokens(req):
    """The worst case any tokenizer can reach: one token per UTF-8 byte (the shipped instruction counted as prose)."""

    from writing_coach.agent.prompts import INSTRUCTION
    from writing_coach.agent.tokens import FRAME_TOKENS, RESERVE_TOKENS, PROSE_CHARS_PER_TOKEN

    return RESERVE_TOKENS + sum(
        FRAME_TOKENS + (-(-len(m.content) // PROSE_CHARS_PER_TOKEN) if m.content == INSTRUCTION else len(m.content.encode()))
        for m in req.messages)


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
    budget = base_tokens() + 6_000
    sent = long_conversation(budget)
    assert tokens(sent) <= budget
    carried = "".join(m.content for m in sent.messages if m.content.startswith(CARRIED_HEAD))
    assert "Remote work has changed" in carried and "left out" in carried


def test_within_the_budget_nothing_is_dropped():
    sent = long_conversation(60_000)
    users = [m.content for m in sent.messages if m.role == "user"]
    assert PASTE in users or any(PASTE in m.content for m in sent.messages)  # nothing was cut
    assert sum(1 for m in sent.messages if m.content.startswith("câu hỏi dài")) == 5


def real_tokens(text):
    """An independent, still conservative count: a Han character is at least 1.5 tokens, other text 1 per 4 characters."""

    cjk = sum(1 for c in text if "⺀" <= c <= "鿿" or "가" <= c <= "힯" or "＀" <= c <= "￯")
    return cjk * 1.5 + (len(text) - cjk) / 4


PASTE_ZH = "远程办公改变了人们的生活方式，也改变了公司管理团队的方法。" * 100  # about 3,000 characters


def test_a_long_chinese_paste_stays_inside_the_budget_under_a_conservative_count():
    budget = base_tokens() + 2_500
    limits = AgentLimits(max_input_tokens_per_turn=budget, compact_after_turns=100, compact_after_chars=10**9)
    rt, provider = runtime([reply("好的。" + "答" * 300) for n in range(10)], limits=limits)
    sid = session_of(run(rt, request(PASTE_ZH)))
    for n in range(4):
        run(rt, request(f"第{n}个问题：" + "问" * 400, sid))
    run(rt, request("第三段是不是太弱了？", sid))
    sent = provider.requests[-1]
    assert sent.messages[-1].content == "第三段是不是太弱了？"
    total = sum(real_tokens(m.content) for m in sent.messages)
    assert total <= budget, (total, budget)  # len/4 would call this about a third of what it is
    assert tokens(sent) <= budget


def test_the_estimate_never_undercounts_chinese():
    from writing_coach.agent.tokens import estimate_tokens, fit_chars

    text = "远程办公" * 500
    assert estimate_tokens(text) >= len(text)  # a Han character is at least one token
    assert estimate_tokens("hello world " * 100) >= len("hello world " * 100)  # the bound, not a guess at prose
    kept = fit_chars(text, 1_000)
    assert estimate_tokens(text[:kept]) <= 1_000 < estimate_tokens(text[: kept + 1]) + 2


ADVERSARIAL = {
    "digits and punctuation": "1a!2b?3c;" * 700,
    "emoji": "😀🎉" * 900,
    "vietnamese": "Tiếng Việt có nhiều dấu: ắ ằ ẳ ẵ ặ. " * 120,
    "arabic": "مرحبا بالعالم " * 400,
    "mixed": "abc 远程办公 ñandú 😀 123 " * 250,
}


def test_the_bound_holds_for_adversarial_ascii_and_unicode_whatever_the_tokenizer():
    from writing_coach.agent.tokens import estimate_tokens

    for name, text in ADVERSARIAL.items():
        assert estimate_tokens(text) >= len(text.encode("utf-8")), name  # a token is at least one byte
        budget = base_tokens() + 2_500
        limits = AgentLimits(max_input_tokens_per_turn=budget, compact_after_turns=100, compact_after_chars=10**9)
        rt, provider = runtime([reply(text[:300]) for _ in range(8)], limits=limits)
        sid = session_of(run(rt, request(text[:2400])))
        for _ in range(3):
            run(rt, request(text[:900], sid))
        run(rt, request(text[:150], sid))
        sent = provider.requests[-1]
        assert sent.messages[-1].content == text[:150], name  # the learner's words stay
        assert tokens(sent) <= budget, (name, tokens(sent), budget)


def test_a_tool_result_is_left_out_when_the_bound_says_it_would_not_fit():
    from writing_coach.agent.tokens import estimate_tokens

    assert estimate_tokens("😀" * 100) == 400 and estimate_tokens("1" * 100) == 100
