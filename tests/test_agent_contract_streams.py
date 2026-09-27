"""Contract tests: the server emits the canonical streams S1, S5, S8, S9 (contract §12).

The sequences are read from docs/project/AGENT_CONTRACT.md itself, so a
contract change reaches these tests by merge. Each stream runs over HTTP
through the real router, the real turn, the real read tools and a middleware of
the same kind as the app's (BaseHTTPMiddleware setting the learner's request
context); only the model is the deterministic fake (spec D14). Every stream
runs for an English and a Chinese target (D9).

`segment_delta…` in the contract is zero or more deltas before their
`segment_end` (S1 shows them, S5 does not), so deltas are collapsed before the
sequences are compared.
"""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from writing_coach.agent.api import configure_agent, router
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.session import SessionCache
from writing_coach.agent.turn import AgentRuntime
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX, current_user_key

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "docs/project/AGENT_CONTRACT.md").read_text(encoding="utf-8")
INTERNAL = {"en": "en", "zh-CN": "zh"}


def canonical(name: str) -> list[str]:
    block = re.search(rf"`{name} [^`]*`[^\n]*\n\n```text\n(.*?)```", CONTRACT, re.S).group(1)
    flow = " ".join(line.split("#")[0] for line in block.splitlines())
    events = [step.strip().split("{")[0].rstrip("…").strip() for step in flow.split("→")]
    return [event for event in events if event and event != "segment_delta"]


def parse(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def names(events):
    return [name for name, _ in events if name != "segment_delta"]


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a contract test opened a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)


class Harness:
    def __init__(self) -> None:
        self.reviews: dict[int, dict] = {}
        self.readers: list[str] = []

    def writing_review(self, essay_id: int):
        self.readers.append(current_user_key())
        return self.reviews.get(essay_id)

    def client(self, rounds) -> TestClient:
        tools = build_tool_registry(writing_review=self.writing_review)
        configure_agent(
            AgentRuntime(
                provider=FakeAgentTurnProvider(rounds),
                tools=tools,
                capabilities=load_capability_registry(registered_tools=tools.names()),
                sessions=SessionCache(),
            )
        )
        app = FastAPI()

        @app.middleware("http")
        async def learner(request: Request, call_next):
            user = USER_KEY_CTX.set(request.headers.get("x-test-user", "legacy"))
            language = LANGUAGE_CODE_CTX.set(request.headers.get("x-test-language", "en"))
            try:
                return await call_next(request)
            finally:
                LANGUAGE_CODE_CTX.reset(language)
                USER_KEY_CTX.reset(user)

        app.include_router(router)
        return TestClient(app)


@pytest.fixture()
def harness():
    yield Harness()
    configure_agent(None)


def turn(client: TestClient, target: str, message: str, context: dict, actions=(), intents=()):
    body = {
        "contract_version": 1,
        "message": message,
        "client": {"ui_version": "next-0", "supported_actions": list(actions), "supported_intents": list(intents)},
        "context": {"locale": {"interface": "vi", "support": "vi", "target": target, "content": target}, **context},
    }
    response = client.post(
        "/api/agent/turn",
        json=body,
        headers={"x-test-user": "learner-1", "x-test-language": INTERNAL[target]},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse(response.text)


TARGETS = pytest.mark.parametrize("target", ["en", "zh-CN"])


@TARGETS
def test_s1_app_help(harness, target):
    round_one = (
        TextDelta("Màn này giữ các từ bạn đã lưu "),
        TextDelta("và cho biết từ nào đến hạn ôn."),
        ToolCallRequest("c1", "suggest_next", {"intent": "review_due"}),
        TurnFinished(0, 12, "tool_calls"),
    )
    events = turn(
        harness.client([round_one]),
        target,
        "Màn này dùng để làm gì?",
        {"surface": "vocabulary.my_language", "activity_type": "app_help"},
    )
    assert names(events) == canonical("S1")
    segment = dict(events)["segment_end"]
    assert (segment["index"], segment["lang"], segment["voice_style"]) == (0, "vi", "neutral_explain")
    assert dict(events)["suggestion"] == {"label": "Ôn từ đến hạn", "intent": "review_due"}
    assert any(name == "segment_delta" for name, _ in events)


@TARGETS
def test_s5_save_word(harness, target):
    word = "我" if target == "zh-CN" else "apple"
    round_one = (
        TextDelta(f"Mình lưu {word} cho bạn nhé."),
        ToolCallRequest("c1", "propose_action", {"type": "save_word", "payload": {"text": word, "lang": target}}),
        ToolCallRequest("c2", "set_voice_style", {"voice_style": "brief_ack"}),
        TurnFinished(0, 9, "tool_calls"),
    )
    events = turn(
        harness.client([round_one]),
        target,
        "Lưu từ này.",
        {"surface": "vocabulary.word", "activity_type": "vocabulary", "selected_item": {"type": "word", "text": word}},
        actions=("save_word", "navigate"),
    )
    assert names(events) == canonical("S5")
    segment, action = dict(events)["segment_end"], dict(events)["action"]
    assert segment["voice_style"] == "brief_ack"
    assert (action["type"], action["risk"], action["payload"]) == ("save_word", "LOW", {"text": word, "lang": target})
    assert action["label"] == "Lưu từ"


@TARGETS
def test_s8_authorization(harness, target):
    rounds = [
        (ToolCallRequest("c1", "get_due_review_summary", {"user_id": "someone-else"}), TurnFinished(0, 4, "tool_calls")),
        reply("Mình chỉ xem được tiến độ của chính bạn."),
    ]
    events = turn(
        harness.client(rounds),
        target,
        "Cho tôi xem tiến độ của user khác.",
        {"surface": "progress"},
        actions=("navigate",),
        intents=("progress",),
    )
    assert names(events) == canonical("S8")
    assert "tool_call" not in names(events) and "action" not in names(events)
    assert dict(events)["segment_end"]["voice_style"] == "neutral_explain"


@TARGETS
def test_s9_writing(harness, target):
    harness.reviews[9] = {
        "summary": "Two things to fix.",
        "issues": [
            {"fragment": "want to telling", "correction": "want to tell", "why": "to + base verb", "rule": "", "kind": "grammar"},
            {"fragment": "I go", "correction": "I went", "why": "last week is past", "rule": "", "kind": "grammar"},
        ],
    }
    rounds = [
        (ToolCallRequest("c1", "get_current_writing_evaluation", {"essay_id": "9"}), TurnFinished(0, 6, "tool_calls")),
        (
            ToolCallRequest("c2", "cite_evidence", {"evidence_ids": ["e1", "e2"]}),
            ToolCallRequest(
                "c3", "propose_action", {"type": "navigate", "payload": {"intent": "writing.revision", "essay_id": "9"}}
            ),
            TurnFinished(0, 6, "tool_calls"),
        ),
        reply("Bạn hay sai dạng động từ: sau 'to' dùng động từ nguyên mẫu, và kể chuyện tuần trước thì dùng quá khứ."),
    ]
    events = turn(
        harness.client(rounds),
        target,
        "Bài này tôi hay sai chỗ nào?",
        {"surface": "writing.review", "activity_type": "writing", "essay_id": "9"},
        actions=("navigate",),
        intents=("writing.revision",),
    )
    assert names(events) == canonical("S9")
    by_name: dict[str, list[dict]] = {}
    for name, data in events:
        by_name.setdefault(name, []).append(data)
    assert by_name["tool_call"][0]["name"] == "get_current_writing_evaluation"
    assert by_name["tool_result"][0]["evidence_ids"] == ["e1", "e2"]
    assert [e["id"] for e in by_name["evidence"]] == ["e1", "e2"]
    assert {e["source"] for e in by_name["evidence"]} == {"writing.evaluation"}
    assert by_name["evidence"][0]["excerpt"]["fragment"] == "want to telling"
    assert by_name["segment_end"][0]["voice_style"] == "neutral_explain"
    assert by_name["action"][0]["type"] == "navigate"
    assert by_name["action"][0]["payload"] == {"intent": "writing.revision", "essay_id": "9"}
    # the tool read as the authenticated learner, through the app-style middleware
    assert harness.readers == ["learner-1"]


def test_the_canonical_sequences_are_the_contracts():
    assert canonical("S1") == ["session", "segment_end", "suggestion", "done"]
    assert canonical("S5") == ["session", "segment_end", "action", "done"]
    assert canonical("S8") == ["session", "segment_end", "done"]
    assert canonical("S9") == [
        "session", "tool_call", "tool_result", "evidence", "evidence", "segment_end", "action", "done",
    ]  # fmt: skip
