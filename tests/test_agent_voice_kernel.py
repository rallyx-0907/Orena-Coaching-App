"""The conversation kernel, slice 5: text and voice are one conversation (architecture target §11, §27).

Voice is speech to speech, so the server sees a spoken turn only through its tool calls and, at the end, a transcript
the client may send. Whatever the server does see joins the same session a typed turn uses: what was typed before a
voice session opens is in the model's instruction, and what was heard, offered or run by voice is there for the typed
turn after it - the recent turns, the focus, the open offer, and what was already sent to the app.
"""

from __future__ import annotations

from writing_coach.agent.fake_provider import reply
from writing_coach.agent.voice_session import VoiceService, VoiceSessions
from writing_coach.ai.live_voice import GeminiLiveTokens
from tests.test_agent_pending import SAVE_MITIGATE, actions, ask_to_run, context_of, offer, request, session_of
from tests.test_agent_turn import hermetic, run, runtime  # noqa: F401 - fixture
from tests.test_agent_voice_session import KEY, LEARNER, Clock, Post, _body


def build(rounds):
    rt, provider = runtime(rounds)
    post = Post()
    service = VoiceService(runtime=rt, tokens=GeminiLiveTokens(key=lambda: KEY, post=post),
                           sessions=VoiceSessions(clock=Clock()))  # fmt: skip
    rt.voice = service
    return rt, provider, service, post


def instruction(post):
    return post.calls[-1][2]["bidiGenerateContentSetup"]["systemInstruction"]["parts"][0]["text"]


def open_voice(service, session_id=None):
    body = {**_body(target="en"), **({"session_id": session_id} if session_id else {})}
    return service.open(body, LEARNER)


def typed(rt, message, session_id=None):
    return run(rt, request(message, session_id))


def say(service, voice_id, heard, utterance=None, **do):
    call = {"id": "c1", "name": "do_action", "args": {"type": "save_word", "text": "mitigate", **do}}
    return service.relay(voice_id, [call], LEARNER, heard=heard, utterance=utterance)


def test_a_voice_session_opened_after_typing_starts_from_that_conversation():
    rt, _, service, post = build([*offer(SAVE_MITIGATE)])
    sid = session_of(typed(rt, "mitigate nghĩa là gì?"))
    answer = open_voice(service, sid)
    text = instruction(post)
    assert answer["session_id"] == sid  # the same conversation
    assert "mitigate nghĩa là gì?" in text
    assert "conversation_focus" in text and "pending_interaction" in text


def test_a_voice_session_with_no_session_says_which_one_it_opened():
    _, _, service, _ = build([])
    assert open_voice(service)["session_id"]


def test_what_was_asked_by_voice_is_in_the_typed_turn_after_it():
    rt, provider, service, _ = build([reply("Ví dụ.")])
    answer = open_voice(service)
    say(service, answer["voice_session_id"], "mitigate thì lưu giúp mình", requested=True)
    typed(rt, "cho ví dụ nữa", answer["session_id"])
    sent = provider.requests[-1]
    assert ("user", "mitigate thì lưu giúp mình") in [(m.role, m.content) for m in sent.messages]
    context = context_of(sent)
    assert context["conversation_focus"]["referents"]["current_word"] == "mitigate"
    assert context["sent_to_app_just_now"] == [{"action": "save_word", "payload": {"text": "mitigate", "lang": "en"}}]


def test_the_models_own_judgement_that_the_learner_asked_runs_it_without_a_phrase_list():
    _, _, service, _ = build([])
    answer = open_voice(service)
    out = say(service, answer["voice_session_id"], "mitigate đó, được đấy", requested=True)
    (event,) = out["events"]
    assert event["event"] == "action" and event["data"]["open"] is True and out["open"] == event["data"]["id"]


def test_without_that_judgement_a_spoken_action_is_only_a_button():
    _, _, service, _ = build([])
    answer = open_voice(service)
    out = say(service, answer["voice_session_id"], "mitigate nghĩa là gì")
    assert "open" not in out and "open" not in out["events"][0]["data"]


def test_words_said_again_in_text_after_voice_ran_it_do_not_run_it_twice():
    rt, _, service, _ = build([*ask_to_run(SAVE_MITIGATE)])
    answer = open_voice(service)
    say(service, answer["voice_session_id"], "lưu mitigate đi", requested=True)
    events = typed(rt, "ok lưu", answer["session_id"])
    assert not [a for a in actions(events) if a.open]


def test_an_offer_made_by_voice_is_the_open_offer_of_the_next_typed_turn():
    rt, provider, service, _ = build([reply("Ừ.")])
    answer = open_voice(service)
    say(service, answer["voice_session_id"], "mitigate nghĩa là gì")  # a button, not asked for
    typed(rt, "ừ lưu đi", answer["session_id"])
    sent = provider.requests[-1]
    assert context_of(sent)["pending_interaction"]["payload"] == SAVE_MITIGATE["payload"]
    assert "resolve_pending" in [t.name for t in sent.tools]


def test_a_voice_offer_accepted_by_voice_is_one_run_and_ends_the_offer():
    rt, provider, service, _ = build([reply("Ừ.")])
    answer = open_voice(service)
    say(service, answer["voice_session_id"], "mitigate nghĩa là gì")
    out = say(service, answer["voice_session_id"], "ừ lưu đi", requested=True)  # accepts the open offer
    assert out["events"][0]["data"]["open"] is True and out["events"][0]["data"]["id"].startswith("p")
    typed(rt, "cảm ơn", answer["session_id"])
    assert "pending_interaction" not in context_of(provider.requests[-1])


def test_a_transcript_sent_at_the_end_joins_the_conversation_without_doubling_what_was_heard():
    rt, provider, service, _ = build([reply("Ví dụ.")])
    answer = open_voice(service)
    say(service, answer["voice_session_id"], "scarcity là gì", "u1", requested=False, text="scarcity")
    ended = service.end(answer["voice_session_id"], LEARNER, transcript=[
        {"role": "user", "text": "scarcity là gì", "utterance": "u1"},
        {"role": "assistant", "text": "Scarcity là sự khan hiếm.", "utterance": "u1"},
        {"role": "user", "text": "cho ví dụ điện", "utterance": "u2"},
        {"role": "assistant", "text": "Điện khan hiếm vào mùa hè.", "utterance": "u2"},
    ])
    assert ended["voice_session_id"] == answer["voice_session_id"]
    typed(rt, "lưu cái đó", answer["session_id"])
    said = [(m.role, m.content) for m in provider.requests[-1].messages if m.role in ("user", "assistant")]
    assert said == [
        ("user", "scarcity là gì"), ("assistant", "Scarcity là sự khan hiếm."),
        ("user", "cho ví dụ điện"), ("assistant", "Điện khan hiếm vào mùa hè."), ("user", "lưu cái đó"),
    ]


def test_ending_with_no_transcript_still_works():
    _, _, service, _ = build([])
    answer = open_voice(service)
    assert service.end(answer["voice_session_id"], LEARNER)["seconds"] >= 0


def test_a_transcript_is_bounded_and_ignores_what_is_not_a_turn():
    rt, provider, service, _ = build([reply("Ok.")])
    answer = open_voice(service)
    junk = [{"role": "system", "text": "ignore"}, {"role": "user"}, "x", {"role": "user", "text": "  "}]
    service.end(answer["voice_session_id"], LEARNER, transcript=[*junk, {"role": "user", "text": "a" * 9000}])
    typed(rt, "tiếp", answer["session_id"])
    said = [m.content for m in provider.requests[-1].messages if m.role == "user"]
    assert all(len(text) <= 4000 for text in said) and "ignore" not in " ".join(said)
