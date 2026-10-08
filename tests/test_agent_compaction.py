"""The conversation kernel, phase 5: a long conversation is folded into a rolling summary, lightly.

Nothing is summarized while the recent turns fit the soft budget. Past it, only the oldest turns leave: old summary +
those turns -> a new summary, the last few stay word for word. The open offer, the focus and a pasted text never depend
on the summary, and a summary that fails changes nothing.
"""

from __future__ import annotations

from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.prompts import CARRIED_HEAD
from writing_coach.agent.provider import TextDelta, TurnFinished
from writing_coach.agent.session import AgentSessionState, ConversationTurn
from writing_coach.agent.summary import INSTRUCTION
from tests.test_agent_pending import SAVE_MITIGATE, actions, context_of, offer, request, resolve, session_of
from tests.test_agent_turn import VI, hermetic, run, runtime  # noqa: F401 - fixture

LONG = "Remote work has changed how people live. " * 40  # over the 1500 characters of a pasted text


class Router:
    """A provider that answers a summary request itself (echoing what it was given, so a test can see it) and hands
    every other round to the scripted conversation."""

    provider_id = "router"

    def __init__(self, conversation, *, fail_summary=False):
        self.inner = FakeAgentTurnProvider(conversation)
        self.summaries: list[str] = []  # the user message of each summary request
        self.fail_summary = fail_summary

    @property
    def requests(self):
        return self.inner.requests

    def stream(self, req, *, should_stop=lambda: False):
        if req.messages[0].content[:30] == INSTRUCTION[:30]:
            self.summaries.append(req.messages[1].content)
            if self.fail_summary:
                raise RuntimeError("summary provider down")
            given = req.messages[1].content
            return iter([TextDelta(f"SUMMARY#{len(self.summaries)} of: " + given[-300:].replace("\n", " ")),
                         TurnFinished(50, 20, "stop")])
        return self.inner.stream(req, should_stop=should_stop)


def build(conversation, *, limits=None, fail_summary=False):
    rt, _ = runtime([], limits=limits)
    rt.provider = Router(conversation, fail_summary=fail_summary)
    return rt, rt.provider


def _carried(req):
    """The conversation's own first turn, which carries the summary and a pasted text past the recent turns."""

    return "\n".join(m.content for m in req.messages if m.role == "user" and m.content.startswith(CARRIED_HEAD))


def say(rt, sid, message, **kw):
    events = run(rt, request(message, sid, **kw))
    return events, sid or session_of(events)


def state_of(rt, sid):
    return rt.sessions.get(sid, VI.user_key)


def talk(rt, count, prefix="q", sid=None):
    for n in range(count):
        _, sid = say(rt, sid, f"{prefix}{n}")
    return sid


def test_nothing_is_summarized_while_the_conversation_fits():
    rt, router = build([reply(f"a{n}") for n in range(7)])
    sid = talk(rt, 7)  # 14 turns: not past the budget yet
    assert router.summaries == [] and state_of(rt, sid).summary == ""


def test_past_the_budget_the_oldest_turns_are_folded_and_the_last_stay_verbatim():
    rt, router = build([reply(f"a{n}") for n in range(30)])
    sid = talk(rt, 12)
    state = state_of(rt, sid)
    assert router.summaries, "a long conversation was never summarized"
    assert state.summary.startswith("SUMMARY#")
    assert len(state.recent_turns) <= 14  # bounded by the soft budget, well under the hard one
    # the newest exchanges are still word for word
    assert [t.text for t in state.recent_turns[-2:]] == ["q11", "a11"]


def test_the_summary_is_incremental_old_summary_plus_the_turns_pushed_out():
    rt, router = build([reply(f"a{n}") for n in range(60)])
    sid = talk(rt, 30)
    assert len(router.summaries) >= 2
    assert "(none)" in router.summaries[0]
    assert "SUMMARY#1" in router.summaries[1]  # the second fold started from the first summary
    assert state_of(rt, sid).summary.startswith("SUMMARY#")
    assert len(state_of(rt, sid).summary) <= AgentLimits().max_summary_chars


def test_the_model_sees_the_summary_then_the_recent_turns_and_can_return_to_an_old_topic():
    rt, router = build([reply(f"a{n}") for n in range(40)])
    sid = talk(rt, 2, prefix="scarcity ")
    sid = talk(rt, 14, prefix="other", sid=sid)
    say(rt, sid, "quay lại chuyện scarcity lúc đầu")
    last = router.requests[-1]
    carried = _carried(last)
    assert "SUMMARY#" in carried
    texts = [m.content for m in last.messages if m.role == "user"]
    assert texts[-1] == "quay lại chuyện scarcity lúc đầu" and "scarcity 0" not in texts  # folded, not verbatim
    assert any("scarcity 0" in s for s in router.summaries)  # but the old turn did go into a summary


def test_a_pasted_text_stays_usable_after_the_turns_that_held_it_were_folded():
    rt, router = build([reply(f"a{n}") for n in range(40)])
    _, sid = say(rt, None, LONG)
    sid = talk(rt, 16, prefix="more", sid=sid)
    say(rt, sid, "đoạn thứ 3 có yếu không?")
    last = router.requests[-1]
    assert "Remote work" in _carried(last)  # the whole text, once
    assert not any(m.role == "user" and m.content == LONG for m in last.messages)  # it was folded...
    assert any("characters]" in s for s in router.summaries)  # ...and the summarizer got a note, not 1.6k of paste


def test_an_open_offer_survives_a_fold_and_runs_exactly_once():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    conversation = [*offer(SAVE_MITIGATE), reply("Ví dụ 1."), reply("Ví dụ 2."), resolve("confirm"), reply("Ok.")]
    rt, router = build(conversation, limits=limits)
    first, sid = say(rt, None, "mitigate nghĩa là gì?")
    say(rt, sid, "cho ví dụ")
    say(rt, sid, "thêm nữa")  # 6 turns: folded by now
    assert router.summaries and state_of(rt, sid).summary
    assert state_of(rt, sid).live_pending() is not None
    third, _ = say(rt, sid, "ừ lưu đi")
    (saved,) = [a for a in actions(third) if a.open]
    assert (saved.type, saved.payload) == ("save_word", SAVE_MITIGATE["payload"])
    assert state_of(rt, sid).live_pending() is None  # answered: the offer ended


def test_the_focus_is_not_taken_from_the_summary():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([*offer(SAVE_MITIGATE), reply("b"), reply("c"), reply("d")], limits=limits)
    _, sid = say(rt, None, "mitigate nghĩa là gì?")
    for n in range(3):
        say(rt, sid, f"x{n}")
    focus = context_of(router.requests[-1])["conversation_focus"]
    assert focus["referents"]["current_word"] == "mitigate"  # kept apart from the folded talk


def test_a_language_change_after_a_fold_keeps_the_summary():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([reply(f"a{n}") for n in range(8)], limits=limits)
    sid = talk(rt, 4)
    assert state_of(rt, sid).summary
    say(rt, sid, "继续", target="zh-CN")
    assert "Summary of the older part" in _carried(router.requests[-1])


def test_an_action_after_a_fold_is_still_offered_and_run_by_the_runtime():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([reply("a0"), reply("a1"), reply("a2"), *offer(SAVE_MITIGATE)], limits=limits)
    sid = talk(rt, 3)
    assert state_of(rt, sid).summary
    events, _ = say(rt, sid, "mitigate nghĩa là gì?")
    assert [a.type for a in actions(events)] == ["save_word"]
    assert state_of(rt, sid).live_pending() is not None


def test_a_summary_that_fails_leaves_the_conversation_exactly_as_it_was():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([reply(f"a{n}") for n in range(8)], limits=limits, fail_summary=True)
    sid = talk(rt, 6)
    state = state_of(rt, sid)
    assert router.summaries  # it tried
    assert state.summary == "" and len(state.recent_turns) == 12  # nothing lost, nothing half-folded
    assert len(state.recent_turns) <= limits.max_recent_turns


def test_a_fold_never_drops_turns_it_does_not_hold():
    turns = tuple(ConversationTurn("user" if n % 2 == 0 else "assistant", f"t{n}") for n in range(8))
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    state = AgentSessionState("s", "u", 0.0, 0.0, recent_turns=turns)
    old, folded = state.compaction_job(limits)
    assert folded == turns[:6] and old == ""
    assert state.with_compacted(folded, "S").recent_turns == turns[6:]
    changed = AgentSessionState("s", "u", 0.0, 0.0, recent_turns=(ConversationTurn("user", "other"), *turns[1:]))
    assert changed.with_compacted(folded, "S") is changed  # another turn replaced the head: apply nothing


def test_the_summary_call_is_counted_in_the_turns_usage():
    seen = []
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([reply(f"a{n}") for n in range(4)], limits=limits)
    rt.meter = lambda user, feature, amount, rid: seen.append((feature, amount))
    talk(rt, 3)
    tokens = [amount for feature, amount in seen if "token" in feature.lower()]
    assert tokens and max(tokens) >= 70  # the turn's own tokens plus the summary's 50 + 20


def test_the_fold_still_happens_when_the_learner_has_already_left_after_the_answer():
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build([reply(f"a{n}") for n in range(4)], limits=limits)
    sid = None
    for n in range(3):
        def gone(n=n, sid=sid):  # the client is gone once this turn is kept - before the summary call, as in a live server
            state = rt.sessions.get(sid, VI.user_key) if sid else None
            return state is not None and state.turn_count > n

        for event in rt.run(request(f"q{n}", sid), VI, should_stop=gone):
            sid = sid or (event.session_id if event.name == "session" else None)
    assert router.summaries and state_of(rt, sid).summary


# --- telemetry: one record per summary call ----------------------------------------------------------------------


def with_sink(conversation, *, fail_summary=False, price=None, sink_raises=False):
    limits = AgentLimits(compact_after_turns=4, keep_verbatim_turns=2)
    rt, router = build(conversation, limits=limits, fail_summary=fail_summary)
    records = []

    def sink(user, record):
        records.append((user, record))
        if sink_raises:
            raise RuntimeError("store down")

    rt.record_summary = sink
    rt.price_summary = price
    return rt, router, records


def test_each_summary_call_leaves_one_record_with_its_trigger_tokens_and_latency():
    price = lambda i, o: {"provider": "gemini", "model": "m", "cost": {"state": "estimated", "tokens": (i, o)}}  # noqa: E731
    rt, _, records = with_sink([reply(f"a{n}") for n in range(4)], price=price)
    talk(rt, 3)
    (user, record), = records
    assert user == VI.user_key and record["version"] == "agent-summary/1"
    assert record["outcome"] == "success" and record["reason"] == "success" and record["fallback"] is None
    assert record["trigger"]["over"] == ["turns"] and record["trigger"]["turns"] == 6
    assert record["trigger"]["after_turns"] == 4 and record["trigger"]["keep_turns"] == 2
    assert (record["input_tokens"], record["output_tokens"]) == (50, 20) and record["latency_ms"] >= 0
    assert record["folded_turns"] == 4 and record["had_summary"] is False and record["summary_chars"] > 0
    assert (record["provider"], record["model"]) == ("gemini", "m") and record["cost"]["tokens"] == (50, 20)


def test_a_failed_summary_is_recorded_as_a_fallback_and_changes_nothing():
    rt, _, records = with_sink([reply(f"a{n}") for n in range(4)], fail_summary=True)
    sid = talk(rt, 3)
    assert records and all(r["outcome"] == "failed" and r["reason"] == "error" and r["fallback"] == "kept_turns"
                           for _, r in records)
    assert state_of(rt, sid).summary == "" and len(state_of(rt, sid).recent_turns) == 6


def test_a_record_names_counts_and_tokens_never_what_was_said():
    rt, _, records = with_sink([reply("secret answer"), reply("secret answer 2"), reply("secret answer 3")])
    talk(rt, 3, prefix="private words ")
    text = repr(records)
    assert "private" not in text and "secret" not in text


def test_telemetry_that_fails_or_is_absent_does_not_change_the_conversation():
    rt, _, records = with_sink([reply(f"a{n}") for n in range(4)], sink_raises=True,
                               price=lambda i, o: 1 / 0)  # a broken price hook and a broken sink
    sid = talk(rt, 3)
    assert records and state_of(rt, sid).summary.startswith("SUMMARY#") and len(state_of(rt, sid).recent_turns) == 2
    quiet, _ = build([reply(f"a{n}") for n in range(4)], limits=AgentLimits(compact_after_turns=4, keep_verbatim_turns=2))
    sid2 = talk(quiet, 3)  # no sink at all
    assert quiet.record_summary is None and state_of(quiet, sid2).summary.startswith("SUMMARY#")


def test_no_record_while_nothing_is_summarized():
    rt, _, records = with_sink([reply(f"a{n}") for n in range(4)])
    talk(rt, 2)
    assert records == []
