"""Live voice, mode A (contract §9; R28, 2026-10-06): the server mints a one-use Gemini Live token with the whole
setup locked in, runs the model's tool calls for the learner, judges its buttons and notes like a text turn, and
bills the session's time into the shared AI ledger. The key never reaches the client."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from writing_coach.agent.api import configure_agent, router, voice_enabled
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime
from writing_coach.agent.voice_session import (
    SESSION_SECONDS,
    VOICE_MODEL,
    VOICE_RULES,
    VoiceService,
    VoiceSessions,
    gemini_schema,
)
from writing_coach.ai.live_voice import LIVE_SOCKET, TOKEN_URL, GeminiLiveTokens, VoiceUnavailable
from writing_coach.ai.pricing import estimate_audio_cost
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX

KEY = "test-key-not-real"
LEARNER = LearnerScope(user_key="learner-1", language="zh", interface="vi")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Post:
    def __init__(self, status=200, answer=None):
        self.status, self.answer, self.calls = status, answer or {"name": "auth_tokens/one-use"}, []

    def __call__(self, url, headers, body):
        self.calls.append((url, dict(headers), json.loads(body)))
        return self.status, json.dumps(self.answer).encode()


def _service(post=None, key=KEY, clock=None, billed=None):
    tools = build_tool_registry(writing_review=lambda essay_id: None)
    runtime = AgentRuntime(provider=FakeAgentTurnProvider([]), tools=tools, sessions=SessionCache(),
                           capabilities=load_capability_registry(registered_tools=tools.names()))  # fmt: skip
    record = (lambda *a, **k: billed.append((a, k))) if billed is not None else None
    service = VoiceService(runtime=runtime, tokens=GeminiLiveTokens(key=lambda: key, post=post or Post()),
                           record_audio=record, sessions=VoiceSessions(clock=clock or Clock()))  # fmt: skip
    runtime.voice = service
    return service


def _body(selected=None, target="zh-CN"):
    context = {"surface": "reading.workspace", "locale": {"interface": "vi", "support": "vi", "target": target}}
    if selected:
        context["selected_item"] = selected
    return {"contract_version": 5, "client": {"ui_version": "t", "supported_actions": ["save_word", "navigate"],
                                              "supported_intents": ["vocabulary.word"]}, "context": context}  # fmt: skip


# --- the token and its locked setup -------------------------------------------------------------------------------


def test_a_session_mints_a_one_use_token_with_the_setup_locked_in():
    post = Post()
    answer = _service(post).open(_body(), LEARNER)
    (url, headers, sent), = post.calls
    assert url == TOKEN_URL and headers["x-goog-api-key"] == KEY and sent["uses"] == 1
    setup = sent["bidiGenerateContentSetup"]
    assert setup["model"] == f"models/{VOICE_MODEL}" and setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    instruction = setup["systemInstruction"]["parts"][0]["text"]
    assert instruction.startswith(INSTRUCTION) and VOICE_RULES in instruction and "context: " in instruction
    names = {d["name"] for d in setup["tools"][0]["functionDeclarations"]}
    assert {"get_word_detail", "do_action", "remember_note"} <= names
    assert not names & {"propose_action", "cite_evidence", "set_voice_style", "add_reference", "suggest_next"}
    assert "inputAudioTranscription" in setup and "outputAudioTranscription" in setup
    assert answer["mode"] == "s2s" and answer["transport"] == "websocket"
    assert answer["connect"]["url"] == LIVE_SOCKET and answer["connect"]["ephemeral_token"] == "auth_tokens/one-use"
    assert answer["connect"]["setup"] == {"setup": {"model": f"models/{VOICE_MODEL}"}}
    assert answer["max_seconds"] == SESSION_SECONDS == 900
    assert KEY not in json.dumps(answer)  # the key never reaches the client


def test_a_selection_and_its_sentence_reach_the_locked_instruction():
    post = Post()
    word = {"type": "word", "text": "花生", "lang": "zh-CN", "sentence": "你们那么爱吃花生"}
    _service(post).open(_body(word), LEARNER)
    instruction = post.calls[0][2]["bidiGenerateContentSetup"]["systemInstruction"]["parts"][0]["text"]
    assert "The learner has selected the word \"花生\"" in instruction and "你们那么爱吃花生" in instruction


def test_no_key_or_a_refused_token_is_voice_unavailable_and_says_nothing_of_the_answer():
    with pytest.raises(VoiceUnavailable):
        _service(key="").open(_body(), LEARNER)
    with pytest.raises(VoiceUnavailable) as refused:
        _service(Post(status=400, answer={"error": {"message": f"bad {KEY}"}})).open(_body(), LEARNER)
    assert KEY not in str(refused.value)


def test_a_json_schema_becomes_a_gemini_function_schema():
    schema = {"type": "object", "additionalProperties": False, "required": ["text"],
              "properties": {"text": {"type": "string", "description": "a word"},
                             "kind": {"type": ["string", "null"], "enum": ["a", "b"]},
                             "ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1}}}  # fmt: skip
    assert gemini_schema(schema) == {
        "type": "OBJECT", "required": ["text"],
        "properties": {"text": {"type": "STRING", "description": "a word"},
                       "kind": {"type": "STRING", "nullable": True, "enum": ["a", "b"]},
                       "ids": {"type": "ARRAY", "items": {"type": "INTEGER"}}},
    }  # fmt: skip


# --- tool calls ------------------------------------------------------------------------------------------------


def test_a_spoken_button_is_filled_from_the_selection_and_judged_like_in_text():
    service = _service()
    sid = service.open(_body({"type": "word", "text": "花生", "lang": "zh-CN"}), LEARNER)["voice_session_id"]
    save = {"id": "c1", "name": "do_action", "args": {"type": "save_word"}}
    answer = service.relay(sid, [save], LEARNER, heard="Lưu từ này giúp mình nhé")
    assert answer["responses"][0]["id"] == "c1" and answer["responses"][0]["response"]["result"].startswith("accepted")
    assert [e["event"] for e in answer["events"]] == ["action"]
    assert answer["events"][0]["data"]["type"] == "save_word"
    assert answer["events"][0]["data"]["payload"] == {"text": "花生", "lang": "zh-CN"}
    # D-135: My Library about a word not read as saved is refused, as in text
    library = {"id": "c2", "name": "do_action", "args": {"type": "navigate", "intent": "vocabulary.word"}}
    refused = service.relay(sid, [library], LEARNER, heard="Mở từ này trong thư viện")
    assert refused["responses"][0]["response"]["result"].startswith("refused") and refused["events"] == []


def test_each_utterance_counts_its_buttons_afresh():
    service = _service()
    sid = service.open(_body({"type": "word", "text": "花生", "lang": "zh-CN"}), LEARNER)["voice_session_id"]
    save = {"id": "c", "name": "do_action", "args": {"type": "save_word"}}
    for said in ("Lưu từ này", "Lưu lại giúp mình", "Lưu từ này lần nữa"):
        answer = service.relay(sid, [save], LEARNER, heard=said)
        assert answer["responses"][0]["response"]["result"].startswith("accepted"), said


def test_a_note_needs_the_learners_own_words_heard_in_this_session():
    service = _service()
    sid = service.open(_body(), LEARNER)["voice_session_id"]
    note = {"id": "n", "name": "remember_note", "args": {"kind": "preference", "text": "Ví dụ ngắn"}}
    assert service.relay(sid, [note], LEARNER)["responses"][0]["response"]["result"].startswith("refused")
    kept = service.relay(sid, [note], LEARNER, heard="Nhớ giúp mình là mình thích ví dụ ngắn nhé")
    assert [e["event"] for e in kept["events"]] == ["memory_update"]


def test_a_read_for_another_learner_is_refused_and_an_unknown_tool_is_unavailable():
    service = _service()
    sid = service.open(_body(), LEARNER)["voice_session_id"]
    other = {"id": "r", "name": "get_due_review_summary", "args": {"user_id": "someone-else"}}
    assert service.relay(sid, [other], LEARNER)["responses"][0]["response"]["result"].startswith("refused")
    unknown = {"id": "u", "name": "drop_tables", "args": {}}
    assert service.relay(sid, [unknown], LEARNER)["responses"][0]["response"]["result"].startswith("unavailable")


def test_a_session_is_only_its_learners_and_only_for_fifteen_minutes():
    clock = Clock()
    service = _service(clock=clock)
    sid = service.open(_body(), LEARNER)["voice_session_id"]
    other = LearnerScope(user_key="learner-2", language="zh", interface="vi")
    assert service.relay(sid, [], other) is None
    clock.t += SESSION_SECONDS + 1
    assert service.relay(sid, [], LEARNER) is None


# --- billing ---------------------------------------------------------------------------------------------------


def test_ending_a_session_bills_its_time_into_the_shared_ledger():
    clock, billed = Clock(), []
    service = _service(clock=clock, billed=billed)
    sid = service.open(_body(), LEARNER)["voice_session_id"]
    clock.t += 125.0
    assert service.end(sid, LEARNER) == {"voice_session_id": sid, "seconds": 125.0}
    (args, kwargs), = billed
    assert args == ("agent_voice",) and kwargs["provider"] == "gemini" and kwargs["model"] == VOICE_MODEL
    assert kwargs["audio_seconds"] == 125.0 and kwargs["outcome"] == "success"
    assert service.end(sid, LEARNER) is None  # billed once


def test_a_session_never_ended_is_billed_at_its_cap_when_the_next_one_opens():
    clock, billed = Clock(), []
    service = _service(clock=clock, billed=billed)
    service.open(_body(), LEARNER)
    clock.t += SESSION_SECONDS + 300
    service.open(_body(), LEARNER)
    assert [k["audio_seconds"] for _, k in billed] == [SESSION_SECONDS]


def test_gemini_live_time_is_priced_from_the_audio_catalog():
    cost = estimate_audio_cost("gemini", VOICE_MODEL, 60)
    assert cost["state"] == "estimated" and cost["amount"] == pytest.approx(0.036)


# --- the routes ------------------------------------------------------------------------------------------------


def test_voice_is_off_unless_switched_on():
    assert not voice_enabled({}) and not voice_enabled({"AGENT_VOICE_ENABLED": "false"})
    assert voice_enabled({"AGENT_VOICE_ENABLED": "true"})


@pytest.fixture()
def client():
    app = FastAPI()

    @app.middleware("http")
    async def learner(request: Request, call_next):
        user = USER_KEY_CTX.set("learner-1")
        language = LANGUAGE_CODE_CTX.set("zh")
        try:
            return await call_next(request)
        finally:
            LANGUAGE_CODE_CTX.reset(language)
            USER_KEY_CTX.reset(user)

    app.include_router(router)
    yield TestClient(app)
    configure_agent(None)


def test_the_routes_are_404_without_voice(client):
    service = _service()
    service.runtime.voice = None
    configure_agent(service.runtime)
    assert client.post("/api/agent/voice/session", json=_body()).status_code == 404


def test_the_routes_open_relay_and_end_a_session(client):
    service = _service()
    configure_agent(service.runtime)
    opened = client.post("/api/agent/voice/session", json=_body())
    assert opened.status_code == 200 and KEY not in opened.text
    sid = opened.json()["voice_session_id"]
    relayed = client.post("/api/agent/voice/tool", json={"voice_session_id": sid, "calls": []})
    assert relayed.status_code == 200 and relayed.json() == {"responses": [], "events": []}
    assert client.post("/api/agent/voice/end", json={"voice_session_id": sid}).status_code == 200
    assert client.post("/api/agent/voice/end", json={"voice_session_id": sid}).status_code == 404


def test_a_mismatched_target_is_409_and_a_refused_token_503(client):
    configure_agent(_service().runtime)
    assert client.post("/api/agent/voice/session", json=_body(target="en")).status_code == 409
    configure_agent(_service(Post(status=403)).runtime)
    refused = client.post("/api/agent/voice/session", json=_body())
    assert refused.status_code == 503 and refused.json()["detail"] == "voice_unavailable"
