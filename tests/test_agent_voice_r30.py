"""R30 (2026-10-06, after the phone tests): voice Orena does anything the app can do on request - one do_action tool for
every §7 action the client lists, run at once when the learner's own words asked for it (a CONFIRM action through
the app's confirmation), a button otherwise - follows the learner across the app with a context update, and is
told which languages to hear."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.test_agent_voice_r29 import _service
from tests.test_agent_voice_session import LEARNER, Post, client  # noqa: F401  (the routes fixture)
from writing_coach.agent.api import configure_agent
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.voice_session import VOICE_RULES, recognition_languages

ALL_ACTIONS = ["navigate", "play_model", "say_again", "save_word", "unsave_word", "start_review", "start_targeted_drill"]
ALL_INTENTS = ["home", "orena.home", "progress", "preferences", "listening.library", "listening.workspace",
               "listening.dictation", "reading.workspace", "speaking.free_talk", "vocabulary.review_due",
               "vocabulary.word", "writing.workspace"]  # fmt: skip


def _body(context=None, support="vi", target="zh-CN"):
    ctx = {"surface": "orena.home", "locale": {"interface": "vi", "support": support, "target": target}}
    ctx.update(context or {})
    return {"contract_version": 5, "client": {"ui_version": "t", "supported_actions": ALL_ACTIONS,
                                              "supported_intents": ALL_INTENTS}, "context": ctx}  # fmt: skip


def _do(service, sid, heard, **args):
    return service.relay(sid, [{"id": "d", "name": "do_action", "args": args}], LEARNER, heard)


def _session(context=None, post=None):
    service = _service(post)
    return service, service.open(_body(context), LEARNER)["voice_session_id"]


# --- the tool and the languages ------------------------------------------------------------------------------------


def test_do_action_offers_exactly_the_clients_actions_and_places_and_the_recognition_languages():
    post = Post()
    _session(post=post)
    setup = post.calls[0][2]["bidiGenerateContentSetup"]
    (do,) = [d for d in setup["tools"][0]["functionDeclarations"] if d["name"] == "do_action"]
    assert sorted(do["parameters"]["properties"]["type"]["enum"]) == sorted(ALL_ACTIONS)
    assert sorted(do["parameters"]["properties"]["intent"]["enum"]) == sorted(ALL_INTENTS)
    assert setup["inputAudioTranscription"] == {"languageCodes": ["vi-VN", "cmn-CN"]}


def test_recognition_languages_are_support_then_target_without_repeats():
    assert recognition_languages("en", "en") == ["en-US"]
    assert recognition_languages("vi", "en") == ["vi-VN", "en-US"]
    assert recognition_languages("xx", None) == []


def test_the_voice_rules_ask_again_rather_than_act_on_what_was_not_heard():
    assert "did\n  not catch it" in VOICE_RULES or "did not catch it" in " ".join(VOICE_RULES.split())
    assert "[context]" in VOICE_RULES


# --- doing it, at once when asked ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("heard", "intent"), [("Mở phần tiến độ của mình", "progress"), ("Go to my progress", "progress"),
                                               ("Mở cài đặt", "preferences"), ("打开设置", "preferences")])  # fmt: skip
def test_a_place_the_learner_asks_for_opens_at_once(heard, intent):
    service, sid = _session()
    answer = _do(service, sid, heard, type="navigate", intent=intent)
    (action,) = [e["data"] for e in answer["events"]]
    assert action["payload"] == {"intent": intent} and answer["open"] == action["id"]


@pytest.mark.parametrize("heard", ["Bắt đầu ôn tập đi", "Start a review", "开始复习"])
def test_a_low_risk_action_the_learner_asks_for_runs_at_once(heard):
    service, sid = _session()
    answer = _do(service, sid, heard, type="start_review")
    (action,) = [e["data"] for e in answer["events"]]
    assert action["type"] == "start_review" and answer["open"] == action["id"]


def test_a_confirm_action_asked_for_goes_through_the_apps_confirmation():
    service, sid = _session({"selected_item": {"type": "word", "text": "花生", "lang": "zh-CN"}})
    answer = _do(service, sid, "Bỏ lưu từ này", type="unsave_word")
    (action,) = [e["data"] for e in answer["events"]]
    assert action["risk"] == "CONFIRM" and answer["open"] == action["id"]  # the client confirms before it runs


def test_not_asked_it_is_a_button_only():
    service, sid = _session()
    answer = _do(service, sid, "Hôm nay mình học gì nhỉ", type="start_review")
    assert [e["event"] for e in answer["events"]] == ["action"] and "open" not in answer


def test_a_place_the_client_did_not_list_is_refused():
    service, sid = _session()
    answer = _do(service, sid, "Mở ngữ pháp", type="navigate", intent="grammar.catalog")
    assert answer["responses"][0]["response"]["result"].startswith("refused") and answer["events"] == []


def test_what_is_in_view_fills_the_action():
    service, sid = _session({"surface": "listening.workspace", "content_id": "media:zh-market-01",
                             "selected_item": {"type": "sentence", "id": "s3", "text": "我想买苹果。"}})  # fmt: skip
    answer = _do(service, sid, "Phát mẫu câu này", type="play_model")
    (action,) = [e["data"] for e in answer["events"]]
    assert action["payload"] == {"content_id": "media:zh-market-01", "item_id": "s3"} and "open" in answer
    dictation = _do(service, sid, "Mở chép chính tả bài này", type="navigate", intent="listening.dictation")
    assert dictation["events"][0]["data"]["payload"] == {"intent": "listening.dictation", "content_id": "media:zh-market-01"}


# --- following the learner -----------------------------------------------------------------------------------------


def test_a_context_update_moves_what_this_means():
    service, sid = _session()
    moved = service.update_context(sid, {"surface": "listening.workspace", "content_id": "media:zh-weather-02",
                                         "selected_item": {"type": "sentence", "id": "s1", "text": "今天天气怎么样"}},
                                   LEARNER)  # fmt: skip
    assert moved["note"].startswith("[context]") and "media:zh-weather-02" in moved["note"]
    answer = _do(service, sid, "Phát mẫu câu này", type="play_model")
    assert answer["events"][0]["data"]["payload"] == {"content_id": "media:zh-weather-02", "item_id": "s1"}


def test_a_context_update_keeps_the_sessions_languages_and_is_only_the_learners():
    service, sid = _session()
    service.update_context(sid, {"surface": "progress", "locale": {"interface": "en", "support": "en", "target": "en"}},
                           LEARNER)  # fmt: skip
    session = service.sessions.get(sid, LEARNER.user_key)
    assert session.request.context.locale.support == "vi" and session.request.context.locale.target == "zh-CN"
    other = LearnerScope(user_key="learner-2", language="zh", interface="vi")
    assert service.update_context(sid, {"surface": "home"}, other) is None


def test_the_context_route(client: TestClient):  # noqa: F811
    service, sid = _session()
    configure_agent(service.runtime)
    ok = client.post("/api/agent/voice/context", json={"voice_session_id": sid, "context": {"surface": "progress"}})
    assert ok.status_code == 200 and ok.json()["note"].startswith("[context]")
    assert client.post("/api/agent/voice/context", json={"voice_session_id": "vs-none", "context": {}}).status_code == 404
    assert client.post("/api/agent/voice/context", json={"voice_session_id": sid, "context": "x"}).status_code == 422
