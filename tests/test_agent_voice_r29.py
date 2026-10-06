"""R29 (2026-10-06, after the human's phone test): Orena can find a lesson or text and open it by voice - at once when
the learner asked to open it - and the learner chooses Orena's voice among ten (six female, four male), named by
Orena, never by the vendor."""

from __future__ import annotations

import json

import pytest

from tests.test_agent_voice_session import LEARNER, Post, _body
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider
from writing_coach.agent.find_tools import FindArguments, find_tools
from writing_coach.agent.runtime import AppReads, build_tool_registry
from writing_coach.agent.session import SessionCache
from writing_coach.agent.turn import AgentRuntime
from writing_coach.agent.voice_session import (
    DEFAULT_VOICE,
    VOICE_CATALOG,
    VoiceService,
    VoiceSessions,
    voice_catalog,
)
from writing_coach.ai.live_voice import GeminiLiveTokens

LESSONS = [
    {"lesson_id": "zh-market-01", "title": "在市场买水果", "level": "HSK2", "topic": "shopping", "media_type": "video",
     "duration_ms": 95000, "language": "zh"},
    {"lesson_id": "zh-weather-02", "title": "今天天气怎么样", "level": "HSK1", "topic": "weather", "media_type": "audio",
     "duration_ms": 40000, "language": "zh"},
]  # fmt: skip
ARTICLES = [{"id": "a-7", "title": "落花生", "level": "HSK4", "topic": "literature", "reading_time_seconds": 300}]


def _library(language, level, topic):
    return [item for item in LESSONS if item["language"] == language and (not level or item["level"] == level)]


def _articles(language, level, topic, limit):
    return ARTICLES if language == "zh" else []


def _service(post=None):
    tools = build_tool_registry(writing_review=lambda essay_id: None,
                                reads=AppReads(listening_library=_library, reading_articles=_articles))  # fmt: skip
    runtime = AgentRuntime(provider=FakeAgentTurnProvider([]), tools=tools, sessions=SessionCache(),
                           capabilities=load_capability_registry(registered_tools=tools.names()))  # fmt: skip
    service = VoiceService(runtime=runtime, tokens=GeminiLiveTokens(key=lambda: "k", post=post or Post()),
                           sessions=VoiceSessions())  # fmt: skip
    runtime.voice = service
    return service


def _open_body():
    body = _body()
    body["client"]["supported_intents"] = ["listening.workspace", "reading.workspace", "vocabulary.word"]
    return body


# --- find_content -----------------------------------------------------------------------------------------------


def test_find_content_lists_lessons_and_texts_in_the_learners_language_with_their_content_ids():
    (tool,) = find_tools(listening_library=_library, reading_articles=_articles)
    result = tool.handler(LEARNER, FindArguments())
    assert [i["content_id"] for i in result.data["items"]] == ["media:zh-market-01", "media:zh-weather-02", "article:a-7"]
    first = result.data["items"][0]
    assert first == {"content_id": "media:zh-market-01", "kind": "listening", "opens": "listening.workspace",
                     "title": "在市场买水果", "level": "HSK2", "topic": "shopping", "media_type": "video",
                     "duration_s": 95}  # fmt: skip


def test_find_content_filters_by_kind_level_and_title_words():
    (tool,) = find_tools(listening_library=_library, reading_articles=_articles)
    assert [i["content_id"] for i in tool.handler(LEARNER, FindArguments(kind="reading")).data["items"]] == ["article:a-7"]
    assert tool.handler(LEARNER, FindArguments(kind="listening", level="HSK1")).count == 1
    assert tool.handler(LEARNER, FindArguments(query="天气")).data["items"][0]["content_id"] == "media:zh-weather-02"
    nothing = tool.handler(LEARNER, FindArguments(query="no such"))
    assert nothing.count == 0 and nothing.summary.startswith("nothing found")


# --- opening by voice -------------------------------------------------------------------------------------------


def test_asked_to_open_a_video_orena_finds_it_and_the_client_opens_it_at_once():
    service = _service()
    sid = service.open(_open_body(), LEARNER)["voice_session_id"]
    heard = "Mở một video bất kỳ trong Listening để nghe"
    found = service.relay(sid, [{"id": "f", "name": "find_content", "args": {"kind": "listening"}}], LEARNER, heard)
    assert found["responses"][0]["response"]["data"]["items"][0]["content_id"] == "media:zh-market-01"
    offer = {"id": "o", "name": "do_action", "args": {"type": "navigate", "content_id": "media:zh-market-01"}}
    opened = service.relay(sid, [offer], LEARNER, heard)
    (action,) = [e["data"] for e in opened["events"] if e["event"] == "action"]
    assert action["type"] == "navigate"
    assert action["payload"] == {"intent": "listening.workspace", "content_id": "media:zh-market-01"}
    assert opened["open"] == action["id"]  # R29: opened without a tap
    assert "happens now" in opened["responses"][0]["response"]["result"]


@pytest.mark.parametrize("late", ["", "   ", None])
def test_an_empty_transcript_keeps_the_learners_request(late):
    """The phone test: the client sent heard "" when the transcript came after the tool call."""

    service = _service()
    sid = service.open(_open_body(), LEARNER)["voice_session_id"]
    service.relay(sid, [{"id": "f", "name": "find_content", "args": {"kind": "listening"}}], LEARNER,
                  "Mở một video bất kỳ trong Listening")  # fmt: skip
    offer = {"id": "o", "name": "do_action", "args": {"type": "navigate", "content_id": "media:zh-market-01"}}
    assert "open" in service.relay(sid, [offer], LEARNER, late)


@pytest.mark.parametrize("asked", ["Open any video in Listening", "Mở một video bất kỳ trong Listening",
                                   "我想看一个视频"])  # fmt: skip
def test_asked_for_a_video_a_review_button_is_refused(asked):
    """The phone test: a review button for "open a video" opened an empty Review page."""

    service = _service()
    sid = service.open(_open_body(), LEARNER)["voice_session_id"]
    review = {"id": "r", "name": "do_action", "args": {"type": "start_review"}}
    answer = service.relay(sid, [review], LEARNER, asked)
    assert answer["responses"][0]["response"]["result"].startswith("refused: the learner asked for a lesson")
    assert answer["events"] == []


def test_asked_for_a_review_a_review_button_is_given():
    service = _service()
    body = _open_body()
    body["client"]["supported_actions"].append("start_review")
    sid = service.open(body, LEARNER)["voice_session_id"]
    review = {"id": "r", "name": "do_action", "args": {"type": "start_review"}}
    answer = service.relay(sid, [review], LEARNER, "Ôn từ đến hạn giúp mình")
    assert [e["event"] for e in answer["events"]] == ["action"]


def test_offered_without_being_asked_to_open_it_is_a_button_only():
    service = _service()
    sid = service.open(_open_body(), LEARNER)["voice_session_id"]
    heard = "Có bài nghe nào về thời tiết không?"
    service.relay(sid, [{"id": "f", "name": "find_content", "args": {"query": "天气"}}], LEARNER, heard)
    offer = {"id": "o", "name": "do_action", "args": {"type": "navigate", "content_id": "media:zh-weather-02"}}
    answer = service.relay(sid, [offer], LEARNER, heard)
    assert [e["event"] for e in answer["events"]] == ["action"] and "open" not in answer


def test_a_content_id_no_tool_returned_is_refused():
    service = _service()
    sid = service.open(_open_body(), LEARNER)["voice_session_id"]
    offer = {"id": "o", "name": "do_action", "args": {"type": "navigate", "content_id": "media:made-up"}}
    answer = service.relay(sid, [offer], LEARNER, "Mở bài nghe đó")
    assert answer["responses"][0]["response"]["result"].startswith("refused") and answer["events"] == []
    assert "open" not in answer


def test_find_content_is_offered_to_the_voice_model():
    post = Post()
    _service(post).open(_open_body(), LEARNER)
    names = {d["name"] for d in post.calls[0][2]["bidiGenerateContentSetup"]["tools"][0]["functionDeclarations"]}
    assert {"find_content", "do_action"} <= names


# --- choosing the voice -------------------------------------------------------------------------------------------


def test_ten_voices_six_female_and_four_male_named_by_orena():
    assert len(VOICE_CATALOG) == 10
    assert sum(c.gender == "female" for c in VOICE_CATALOG) == 6 and sum(c.gender == "male" for c in VOICE_CATALOG) == 4
    catalog = voice_catalog("vi")
    assert catalog["default"] == DEFAULT_VOICE and len(catalog["voices"]) == 10
    shown = json.dumps(catalog, ensure_ascii=False)
    assert not any(c.vendor_voice in shown for c in VOICE_CATALOG)  # never the vendor's names
    assert {"id", "gender", "label"} == set(catalog["voices"][0])
    assert voice_catalog("zh-CN")["voices"][0]["label"] != voice_catalog("en")["voices"][0]["label"]


@pytest.mark.parametrize(("choice", "vendor"), [("m-calm", "Charon"), ("f-warm", "Sulafat"), ("nonsense", "Kore"),
                                                (None, "Kore")])  # fmt: skip
def test_the_chosen_voice_is_locked_into_the_session(choice, vendor):
    post = Post()
    body = _open_body()
    if choice:
        body["voice"] = choice
    _service(post).open(body, LEARNER)
    setup = post.calls[0][2]["bidiGenerateContentSetup"]
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == vendor
