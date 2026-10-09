"""D-163 `orena.message` enforcement, hermetic (CI, SQLite): the agent's text turn and the text discussion turn.

The quota store is the in-memory TEST DOUBLE of `tests/test_quota_gate.py` (never a runtime store); the model is
the deterministic `FakeAgentTurnProvider`, so "the provider was not called" is asserted, not inferred. The same
behaviour against real PostgreSQL is proved in `tests/test_quota_orena_message_postgres.py`.
"""
from __future__ import annotations

import concurrent.futures
import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_quota_gate import MemorySettings, enforced_runtime  # noqa: E402
from test_text_discussion import _answering, _CountingMeter, _failing, _FakeRepository  # noqa: E402

from writing_coach.agent.api import _message_admission, configure_agent, router  # noqa: E402
from writing_coach.agent.capability_registry import load_capability_registry  # noqa: E402
from writing_coach.agent.errors import ProviderUnavailable  # noqa: E402
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply  # noqa: E402
from writing_coach.agent.limits import AgentLimits  # noqa: E402
from writing_coach.agent.runtime import build_tool_registry  # noqa: E402
from writing_coach.agent.schemas import TurnRequest  # noqa: E402
from writing_coach.agent.session import SessionCache  # noqa: E402
from writing_coach.agent.tools import LearnerScope  # noqa: E402
from writing_coach.agent.turn import AgentRuntime  # noqa: E402
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX  # noqa: E402
from writing_coach.persistence.discussion_repository import MAX_TURNS  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from writing_coach.text_discussion import install_text_discussion  # noqa: E402
import writing_coach.text_discussion as text_discussion  # noqa: E402

ENV = {quota.FLAG: "on", quota.METERS_FLAG: "orena.message"}
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
ASK = "Hôm nay tôi nên học gì?"  # needs the learner's records: the model is asked a second time (gate 3.1)
HELP = "Màn này dùng để làm gì?"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    previous = quota.runtime()
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    yield
    configure_agent(None)
    configure_plan_store(None)
    quota.configure_quota(**{field: getattr(previous, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


class StubVoice:
    def __init__(self):
        self.opened = 0
        self.relayed = 0
        self.utterances = []

    def open(self, body, learner):
        self.opened += 1
        return {"voice_session_id": "v1"}

    def relay(self, voice_session_id, calls, learner, heard, utterance):
        self.relayed += 1
        return {"responses": [], "events": []}

    def utterance_turn(self, voice_session_id, utterance, heard, learner):
        self.utterances.append(utterance)
        return {"turn_ordinal": len(self.utterances)}


class Rig:
    """The real router, turn and tools behind a middleware like the app's; only the model is scripted."""

    def __init__(self, rounds=(), *, voice=None, clock=None):
        self.provider = FakeAgentTurnProvider(list(rounds))
        tools = build_tool_registry(writing_review=lambda essay_id: None)
        self.runtime = AgentRuntime(
            provider=self.provider, tools=tools,
            capabilities=load_capability_registry(registered_tools=tools.names()), sessions=SessionCache(),
            **({"clock": clock} if clock else {}),
        )
        self.runtime.voice = voice
        configure_agent(self.runtime)
        app = FastAPI()

        @app.middleware("http")
        async def learner(request: Request, call_next):
            user = USER_KEY_CTX.set(request.headers.get("x-test-user", "learner-1"))
            language = LANGUAGE_CODE_CTX.set("en")
            try:
                return await call_next(request)
            finally:
                LANGUAGE_CODE_CTX.reset(language)
                USER_KEY_CTX.reset(user)

        app.add_middleware(quota.QuotaRequestMiddleware)
        app.include_router(router)
        self.client = TestClient(app)

    @staticmethod
    def body(message=HELP, *, trigger="message", surface="vocabulary.my_language", **extra):
        payload = {
            "contract_version": 6, "trigger": trigger, "client": {"ui_version": "t"},
            "context": {"surface": surface, "locale": {"interface": "en", "support": "en", "target": "en"}},
            **extra,
        }
        if trigger == "message":
            payload["message"] = message
        return payload

    def turn(self, message=HELP, *, key=None, trigger="message", headers=None, **extra):
        headers = {**(headers or {}), **({"Idempotency-Key": key} if key else {})}
        return self.client.post("/api/agent/turn", json=self.body(message, trigger=trigger, **extra), headers=headers)


def events(response):
    out = []
    for frame in response.text.split("\n\n"):
        if frame.strip():
            lines = dict(line.split(": ", 1) for line in frame.splitlines())
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def names(response):
    return [name for name, _ in events(response)]


def totals(repository):
    consumed = sum(b["consumed"] for b in repository.buckets.values())
    reserved = sum(b["reserved"] for b in repository.buckets.values())
    return consumed, reserved


def spend(n, *, meter="orena.message", user="learner-1"):
    token = USER_KEY_CTX.set(user)
    try:
        for index in range(n):
            with quota.admit(meter, request_digest=f"spend-{index}") as ticket:
                ticket.dispatch("p")
                ticket.settle(1)
    finally:
        USER_KEY_CTX.reset(token)


# ---------------------------------------------------------------- the switch --

def test_switch_off_changes_nothing():
    repository = enforced_runtime(env={})
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")])
    response = rig.turn()
    assert response.status_code == 200 and names(response)[-1] == "done"
    assert len(rig.provider.requests) == 1
    assert repository.calls == [], "no bucket, no reservation, not even a read"


def test_a_meter_not_listed_is_not_enforced():
    repository = enforced_runtime(env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")])
    assert rig.turn().status_code == 200
    assert repository.calls == []


# ------------------------------------------------------------------- charging --

def test_a_text_turn_is_one_message():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")])
    response = rig.turn()
    assert response.status_code == 200 and names(response)[0] == "session" and names(response)[-1] == "done"
    assert totals(repository) == (1, 0)
    usage = quota.usage_for("learner-1", catalog.FREE)["orena.message"]
    assert usage["state"] == "known" and usage["resets_at"] == "2026-10-10T00:00:00Z"


def test_one_turn_with_several_model_rounds_is_still_one_message():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Ôn 12 từ đến hạn trước nhé."), reply("Ôn 12 từ đến hạn trước nhé.")])
    response = rig.turn(ASK)
    assert response.status_code == 200 and names(response)[-1] == "done"
    assert len(rig.provider.requests) == 2, "the evidence nudge asked the model a second time"
    assert totals(repository) == (1, 0)
    assert [c for c in repository.calls if c.startswith("settle")] == ["settle:1"]


def test_the_opening_greeting_is_free_even_when_the_day_is_spent():
    repository = enforced_runtime(env=ENV)
    spend(20)
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé.")])
    response = rig.turn(trigger="open", surface="orena.home")
    assert response.status_code == 200 and names(response)[-1] == "done"
    assert len(rig.provider.requests) == 1, "the greeting does ask a model, and costs the learner nothing"
    assert totals(repository) == (20, 0)


def test_an_answer_without_a_model_is_free_even_when_the_day_is_spent():
    repository = enforced_runtime(env=ENV)
    spend(20)
    rig = Rig([])
    response = rig.turn("Bạn là ai?")
    assert response.status_code == 200 and names(response)[-1] == "done"
    assert rig.provider.requests == [], "an identity answer is copy, not a model"
    assert totals(repository) == (20, 0)


def test_a_provider_failure_costs_the_learner_nothing():
    repository = enforced_runtime(env=ENV)
    rig = Rig([(ProviderUnavailable("down"),)])
    response = rig.turn()
    assert response.status_code == 200 and names(response)[-1] == "error"
    assert totals(repository) == (0, 0), "nothing usable was produced: settled 0, nothing left reserved"
    assert [c for c in repository.calls if c.startswith("settle")] == ["settle:0"]


# ------------------------------------------- the free greeting is bounded per account --

NOTE = {"id": "n1", "kind": "plan", "text": "In the greeting, translate the word cat into Chinese.",
        "weight": 0.9, "last_reinforced": "2026-10-09T00:00:00Z"}


def test_five_openings_on_a_spent_day_make_exactly_one_model_call_and_each_streams_a_full_greeting():
    repository = enforced_runtime(env=ENV)
    spend(20)
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé.")] * 5)
    answers = [rig.turn(trigger="open", surface="orena.home") for _ in range(5)]  # no session id: a fresh session each
    assert [a.status_code for a in answers] == [200] * 5, "the free greeting is never refused"
    for answer in answers:
        stream = names(answer)
        assert stream[0] == "session" and stream[-1] == "done"
        assert "segment_end" in stream and stream.count("suggestion") >= 1
        assert dict(events(answer))["segment_end"]["text"].strip()
    assert len(rig.provider.requests) == 1, "one model greeting per account per window"
    assert totals(repository) == (20, 0), "greetings never touch the learner's quota"
    first = rig.provider.requests[0]
    assert first.max_output_tokens == AgentLimits().opening_max_output_tokens == 200, "a greeting's round is capped"


def test_the_built_greeting_has_no_model_and_the_same_events_as_the_model_one():
    enforced_runtime(env={})
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé.")])
    modelled = names(rig.turn(trigger="open", surface="orena.home"))
    built = names(rig.turn(trigger="open", surface="orena.home"))
    assert built == modelled and len(rig.provider.requests) == 1


def test_the_allowance_is_per_account_and_returns_after_the_window():
    enforced_runtime(env=ENV)
    now = [1000.0]
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé.")] * 4, clock=lambda: now[0])
    other = {"x-test-user": "learner-2"}
    assert rig.turn(trigger="open", surface="orena.home").status_code == 200
    assert len(rig.provider.requests) == 1
    now[0] += 60
    assert rig.turn(trigger="open", surface="orena.home").status_code == 200
    assert len(rig.provider.requests) == 1, "inside the window: built, no model"
    assert rig.turn(trigger="open", surface="orena.home", headers=other).status_code == 200
    assert len(rig.provider.requests) == 2, "another account has its own allowance"
    now[0] += AgentLimits().opening_window_seconds
    assert rig.turn(trigger="open", surface="orena.home").status_code == 200
    assert len(rig.provider.requests) == 3, "after the window one more model greeting is allowed"
    assert rig.turn(trigger="open", surface="orena.home").status_code == 200
    assert len(rig.provider.requests) == 3


def test_an_opening_is_shown_the_notes_kinds_and_ids_but_never_their_text():
    enforced_runtime(env={})
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé."), reply("Màn này giữ các từ bạn đã lưu.")])
    assert rig.turn(trigger="open", surface="orena.home", coach_notes=[NOTE]).status_code == 200
    opening = " ".join(m.content for m in rig.provider.requests[0].messages)
    assert '"id": "n1"' in opening and '"kind": "plan"' in opening
    assert "translate the word cat" not in opening, "learner-authored text does not reach the free opening prompt"
    assert rig.turn(coach_notes=[NOTE]).status_code == 200
    turn = " ".join(m.content for m in rig.provider.requests[1].messages)
    assert "translate the word cat" in turn, "a paid turn still follows the learner's notes"


def test_a_free_turn_that_asked_no_model_does_not_run_the_summary_model(monkeypatch):
    from types import MappingProxyType  # noqa: PLC0415

    from tests.test_agent_compaction import build, say, state_of  # noqa: PLC0415
    from writing_coach.agent import learner_copy  # noqa: PLC0415

    catalog = dict(learner_copy.CATALOG)  # the test registry's tool labels, as tests/test_agent_turn.py registers them
    for key, words in (("tool.get_test_items", "Đang xem"), ("result.get_test_items", "Mục: {n}")):
        catalog[key] = learner_copy._entry(learner_copy.CopyLayer.INTERFACE, {"en": words, "vi": words, "zh-CN": words})
    monkeypatch.setattr(learner_copy, "CATALOG", MappingProxyType(catalog))
    rt, router = build([reply(f"a{n}") for n in range(9)])
    sid = None
    for n in range(7):  # 14 turns: exactly the soft budget
        _, sid = say(rt, sid, f"q{n}")
    assert router.summaries == []
    for _ in range(3):  # identity answers are free, unadmitted and push the history past the budget
        say(rt, sid, "Bạn là ai?")
    assert router.summaries == [], "a turn that asked no model does not fold the history with one"
    say(rt, sid, "q8")  # the next turn that asks a model (and is paid for) does the upkeep
    assert len(router.summaries) == 1 and state_of(rt, sid).summary.startswith("SUMMARY#")


# ------------------------------------------------------------------- refusal --

def test_exhausted_is_a_plain_429_before_anything_streams_and_the_provider_is_not_called():
    repository = enforced_runtime(env=ENV)
    spend(20)
    rig = Rig([reply("never asked")])
    response = rig.turn()
    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/json"), "a refusal is not an SSE frame"
    detail = response.json()["detail"]
    assert detail["category"] == "quota_exhausted" and detail["retryable"] is False
    context = detail["context"]
    assert (context["feature"], context["used"], context["limit"], context["window"], context["plan"]) == (
        "orena.message", 20, 20, "day", "free")
    assert context["resets_at"] == "2026-10-10T00:00:00Z" and context["upgrade"] == "#/plan/pricing"
    assert int(response.headers["Retry-After"]) == int((datetime(2026, 10, 10, tzinfo=UTC) - NOW).total_seconds())
    assert rig.provider.requests == []
    assert totals(repository) == (20, 0)


def test_an_unavailable_store_is_503_before_anything_streams():
    quota.configure_quota(settings=MemorySettings(), env=ENV, reason="no_postgresql")
    rig = Rig([reply("never asked")])
    response = rig.turn()
    assert response.status_code == 503 and response.json()["detail"]["category"] == "quota_unavailable"
    assert rig.provider.requests == []


def test_a_catalogue_failure_is_503_not_defaults():
    enforced_runtime(env=ENV)
    configure_plan_store(MemorySettings(fail=True))
    rig = Rig([reply("never asked")])
    response = rig.turn()
    assert response.status_code == 503 and response.json()["detail"]["context"]["reason"] == "catalogue"
    assert rig.provider.requests == []


def test_a_target_language_mismatch_is_still_409_and_free():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("never asked")])
    body = Rig.body()
    body["context"]["locale"]["target"] = "zh-CN"
    answer = rig.client.post("/api/agent/turn", json=body)
    assert answer.status_code == 409 and answer.json()["detail"] == "target_language_mismatch"
    assert repository.calls == []


# ---------------------------------------------------------------- idempotency --

def test_a_retry_with_the_same_key_is_never_charged_twice():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu."), reply("never asked")])
    assert rig.turn(key="send-1").status_code == 200
    again = rig.turn(key="send-1")
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_finished"
    assert len(rig.provider.requests) == 1
    assert totals(repository) == (1, 0)


def test_a_new_key_is_a_new_message():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu."), reply("Màn này giữ các từ bạn đã lưu.")])
    assert rig.turn(key="send-1").status_code == 200
    assert rig.turn(key="send-2").status_code == 200
    assert totals(repository) == (2, 0)


def test_five_concurrent_turns_on_the_last_message_call_the_provider_once():
    repository = enforced_runtime(env=ENV)
    spend(19)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")] * 5)
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(lambda n: rig.turn(key=f"k{n}"), range(5)))
    assert sorted(a.status_code for a in answers) == [200, 429, 429, 429, 429]
    assert len(rig.provider.requests) == 1
    assert totals(repository) == (20, 0)


# ------------------------------------------------- stream end, error, disconnect --

def _request():
    return TurnRequest.model_validate(Rig.body())


def _scope():
    return LearnerScope(user_key="learner-1", language="en")


def _run(rig, **kwargs):
    request = _request()
    learner = _scope()
    return rig.runtime.run(request, learner, admission=_message_admission(request, learner), **kwargs)


def test_a_client_that_leaves_before_the_model_runs_is_not_charged_and_nothing_stays_reserved():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")])
    stream = _run(rig)
    assert next(stream).name == "session"
    stream.close()  # the learner left right after the stream opened
    assert rig.provider.requests == []
    assert totals(repository) == (0, 0)
    assert [row["state"] for row in repository.reservations.values()] == ["settled"]


def test_a_client_that_leaves_while_the_model_answers_is_charged_the_message_it_used():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu và cho biết từ nào đến hạn ôn.")])
    stream = _run(rig)
    seen = []
    for event in stream:
        seen.append(event.name)
        if event.name == "segment_delta":
            break
    stream.close()
    assert "segment_delta" in seen and len(rig.provider.requests) == 1
    assert totals(repository) == (1, 0), "the provider did the work; walking away does not make it free"
    assert [row["state"] for row in repository.reservations.values()] == ["settled"]


def test_a_stream_that_is_never_read_does_not_leave_a_reservation_after_it_is_dropped():
    repository = enforced_runtime(env=ENV)
    rig = Rig([reply("x")])
    stream = _run(rig)
    next(stream)
    del stream
    import gc

    gc.collect()
    assert totals(repository)[1] == 0


# -------------------------------------------------------------------- voice --

def test_voice_is_refused_while_messages_are_enforced_because_it_cannot_be_metered_yet():
    repository = enforced_runtime(env=ENV)
    voice = StubVoice()
    rig = Rig([], voice=voice)
    response = rig.client.post("/api/agent/voice/session", json={"context": {"locale": {"target": "en"}}})
    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "quota_voice_not_metered"
    assert voice.opened == 0, "no token is minted"
    assert repository.calls == []


def test_voice_tool_and_turn_are_unaffected_by_the_quota_and_its_headers():
    """The contract (v7, section 3 and 9): the quota's Idempotency-Key applies to the message turn only; a spoken
    utterance's own `utterance` token is the identity of /voice/turn and /voice/tool, and the quota never touches them."""

    repository = enforced_runtime(env=ENV)
    spend(20)  # the day is spent: a voice call on a session that exists still answers
    spent_calls = len(repository.calls)
    voice = StubVoice()
    rig = Rig([], voice=voice)
    headers = {"Idempotency-Key": "same-key", "X-Orena-Timezone": "Asia/Ho_Chi_Minh"}
    for _ in range(2):  # the same key twice: neither a 409 nor a charge
        tool = rig.client.post("/api/agent/voice/tool", headers=headers,
                               json={"voice_session_id": "v1", "utterance": "u1", "calls": []})
        turn = rig.client.post("/api/agent/voice/turn", headers=headers,
                               json={"voice_session_id": "v1", "utterance": "u1"})
        assert tool.status_code == 200 and turn.status_code == 200
    assert voice.relayed == 2 and voice.utterances == ["u1", "u1"], "the routes ran as they did before the quota"
    assert totals(repository) == (20, 0) and len(repository.calls) == spent_calls, "the quota store was not touched"


def test_voice_is_refused_when_enforcement_cannot_be_read():
    quota.configure_quota(settings=MemorySettings(), env=ENV, reason="no_postgresql")
    voice = StubVoice()
    rig = Rig([], voice=voice)
    assert rig.client.post("/api/agent/voice/session", json={}).status_code == 503
    assert voice.opened == 0


def test_voice_is_unchanged_when_messages_are_not_enforced():
    enforced_runtime(env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    voice = StubVoice()
    rig = Rig([], voice=voice)
    assert rig.client.post("/api/agent/voice/session", json={}).status_code == 200
    assert voice.opened == 1
    quota.configure_quota(settings=MemorySettings(), env={})
    assert rig.client.post("/api/agent/voice/session", json={}).status_code == 200
    assert voice.opened == 2


# --------------------------------------------------------------- discussion --

@pytest.fixture()
def discussion(monkeypatch):
    repository = _FakeRepository()
    meter = _CountingMeter()
    calls = []

    def build(generate=None):
        inner = generate or _answering()

        def counted(**kwargs):
            calls.append(1)
            return inner(**kwargs)

        app = FastAPI()

        @app.middleware("http")
        async def learner(request: Request, call_next):
            token = USER_KEY_CTX.set("learner-1")
            try:
                return await call_next(request)
            finally:
                USER_KEY_CTX.reset(token)

        app.add_middleware(quota.QuotaRequestMiddleware)
        app.include_router(install_text_discussion(
            repository=repository, generate_structured=counted, product_repository=meter,
            learner_profile=lambda *a, **k: {"support_language": "vi"}))
        return TestClient(app)

    return build, repository, calls


def ask(client, **extra):
    body = {"source_kind": "story", "source_id": "story:borrowed-table", "body": "Why the past perfect?", **extra}
    return client.post("/api/texts/discussion/turns", json=body)


def test_a_discussion_turn_is_one_orena_message(discussion):
    build, _, calls = discussion
    repository = enforced_runtime(env=ENV)
    assert ask(build(), request_id="r1").status_code == 200
    assert calls == [1] and totals(repository) == (1, 0)


def test_discussion_is_unchanged_when_messages_are_not_enforced(discussion):
    build, _, calls = discussion
    repository = enforced_runtime(env={})
    assert ask(build(), request_id="r1").status_code == 200
    assert calls == [1] and repository.calls == []


def test_an_exhausted_discussion_is_429_and_never_asks_the_provider(discussion):
    build, store, calls = discussion
    repository = enforced_runtime(env=ENV)
    spend(20)
    response = ask(build(), request_id="r1")
    assert response.status_code == 429 and response.json()["detail"]["category"] == "quota_exhausted"
    assert calls == [] and store.turns == []
    assert response.json()["detail"]["context"]["feature"] == "orena.message"
    assert totals(repository) == (20, 0)


def test_a_stored_repeat_a_full_thread_and_a_failed_answer_are_free(discussion):
    build, store, calls = discussion
    repository = enforced_runtime(env=ENV)
    client = build()
    assert ask(client, request_id="r1").status_code == 200
    assert ask(client, request_id="r1").json()["reused"] is True, "the same submission: the stored exchange"
    assert totals(repository) == (1, 0)
    store.turn_count = MAX_TURNS
    full = ask(client, request_id="r2")
    assert full.status_code == 409 and "limit" in full.json()["detail"]
    assert totals(repository) == (1, 0)
    store.turn_count = 0
    broken = ask(build(generate=_failing), request_id="r3")
    assert broken.status_code == 503
    assert totals(repository) == (1, 0), "no provider answered: settled 0, nothing left reserved"
    assert len(calls) == 2  # the first answer and the failed attempt; the repeat and the full thread asked nobody


def test_the_discussion_meter_is_a_one_line_switch(discussion, monkeypatch):
    build, _, calls = discussion
    repository = enforced_runtime(env=ENV)
    monkeypatch.setattr(text_discussion, "QUOTA_METER", None)
    assert ask(build(), request_id="r1").status_code == 200
    assert repository.calls == [] and calls == [1]
