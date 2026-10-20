# ruff: noqa: F811
"""PR-MON-7B2a: the semantic AI meters `word.assist`, `reading.assist` and `writing.task` at their call sites.

Hermetic (CI, SQLite): the quota store is the in-memory test double of `test_quota_gate.py`. Each meter refuses past
the catalogue's limit without calling the provider; a paid plan is not held to Free's numbers; a cached answer is
never admitted; enforcement off limits nothing. The limits come from the plan catalogue an administrator edits
(Admin > Plans) - the tests lower them there, never in code.
"""
from __future__ import annotations

import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_quota_gate import FakeQuotaRepository, MemorySettings, _isolated, enforced_runtime  # noqa: E402,F401
from writing_coach import media_interaction, reading_cache_scope, reading_translation_api, word_detail  # noqa: E402
from writing_coach.ai.router import router as router_module  # noqa: E402
from writing_coach.ai.router import tap as tap_router  # noqa: E402
from writing_coach.ai.router.router import RouteResult  # noqa: E402
from writing_coach.product import assist_meters, catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store, save_catalog  # noqa: E402
from writing_coach.reading_derived import DerivedCache  # noqa: E402
from writing_coach.reading_summary import ReadingSummaryService  # noqa: E402
from writing_coach.reading_translation import ReadingTranslationService  # noqa: E402

NEW = ("word.assist", "reading.assist", "writing.task")
ON = {quota.FLAG: "on", quota.METERS_FLAG: ",".join(NEW)}
EXPLANATION = {"summary": "went dark", "follow_ups": [], "judgement": "natural", "context_meaning": "went dark",
               "why_here": "the lights", "common_meaning": "to go out"}


def _catalogue(**free_limits: int) -> None:
    """Store an administrator's catalogue whose Free limits for the named meters are `free_limits` (Admin > Plans)."""
    plans = [plan.as_dict() for plan in (catalog.FREE, catalog.PLUS, catalog.PRO)]
    for row in plans:
        for key in ("name", "description", "price_label", "rank"):
            row.pop(key)
        if row["id"] == "free":
            for item in row["entitlements"]:
                wanted = free_limits.get(item["key"].replace(".", "_"))
                if wanted is not None:
                    item["limit"] = wanted
    configure_plan_store(MemorySettings())
    save_catalog({"version": 2, "plans": copy.deepcopy(plans)}, updated_by="admin")


def _runtime(plan_id: str = "free", env: dict | None = None) -> FakeQuotaRepository:
    return enforced_runtime(plan_id=plan_id, env=ON if env is None else env, clock=lambda: datetime.now(UTC))


def _consumed(repository: FakeQuotaRepository, meter: str) -> int:
    return sum(bucket["consumed"] for bucket in repository.buckets.values() if bucket["meter"] == meter)


def _refused(call) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        call()
    return caught.value


@pytest.fixture(autouse=True)
def _one_learner(monkeypatch):
    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda _user_key: "inc-one-learner")
    monkeypatch.setattr(word_detail, "_lookup", None)
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", None)


# ---- the switch --------------------------------------------------------------------------------------------


def test_the_new_meters_are_enforceable_and_listed_by_the_environment():
    _runtime()
    state = quota.switch()
    assert state["state"] == "enforced" and set(NEW) <= set(state["meters"])
    assert quota.validate_switch_setting({"enabled": True, "meters": list(NEW)})["meters"] == list(NEW)


# ---- word.assist: the word sheet ------------------------------------------------------------------------------


def _word(**over: Any) -> word_detail.WordDetailIn:
    body = {"text": "slukket", "context": "Vinduene slukket, en etter en.", "source_language": "en",
            "target_language": "vi", **over}
    return word_detail.WordDetailIn(**body)


def _counting_provider(monkeypatch, answer: dict | None = None) -> list[str]:
    calls: list[str] = []

    def structured(capability_key, *, messages, schema, max_output_tokens):
        calls.append(capability_key)
        return dict(answer if answer is not None else EXPLANATION)

    monkeypatch.setattr(media_interaction, "_run_structured", structured)
    return calls


def test_word_sheet_ai_refuses_past_the_limit_without_calling_the_provider(monkeypatch):
    _catalogue(word_assist=2)
    repository = _runtime()
    calls = _counting_provider(monkeypatch)
    assert word_detail.word_detail(_word())["available"] is True                         # why here
    assert word_detail.word_detail(_word(depth="sheet", contextual=True, text="en"))["available"] is True  # meaning
    refused = _refused(lambda: word_detail.word_detail(_word(question="Why not slokket?")))  # the learner's question
    assert refused.status_code == 429 and refused.detail["category"] == "quota_exhausted"
    assert refused.detail["context"]["feature"] == "word.assist" and refused.detail["context"]["limit"] == 2
    assert refused.detail["context"]["upgrade"] == quota.UPGRADE_HREF
    assert len(calls) == 2, "the provider is never called once the plan is spent"
    assert _consumed(repository, "word.assist") == 2


def test_a_plain_tap_is_deterministic_and_never_counted(monkeypatch):
    _catalogue(word_assist=1)
    repository = _runtime()
    calls = _counting_provider(monkeypatch)
    for _ in range(3):
        word_detail.word_detail(_word(depth="sheet"))
    assert calls == [] and repository.calls == []


def test_a_cached_answer_is_never_admitted(monkeypatch):
    _catalogue(word_assist=1)
    repository = _runtime()
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    calls = _counting_provider(monkeypatch)
    first = word_detail.word_detail(_word())
    again = word_detail.word_detail(_word())                 # the limit is spent; the cache still answers
    assert first["contextStatus"] == again["contextStatus"] == "ready"
    assert len(calls) == 1 and _consumed(repository, "word.assist") == 1


def test_an_unanswered_or_failed_ask_costs_nothing(monkeypatch):
    _catalogue(word_assist=1)
    repository = _runtime()
    _counting_provider(monkeypatch, answer={"summary": ""})
    assert word_detail.word_detail(_word())["contextStatus"] == "empty"

    def down(*_a, **_k):
        raise HTTPException(503, "down")

    monkeypatch.setattr(media_interaction, "_run_structured", down)
    assert word_detail.word_detail(_word())["contextStatus"] == "provider_error"
    assert _consumed(repository, "word.assist") == 0
    assert sum(bucket["reserved"] for bucket in repository.buckets.values()) == 0


def test_a_paid_plan_is_not_held_to_free_numbers(monkeypatch):
    _catalogue(word_assist=1, reading_assist=1, writing_task=1)
    repository = _runtime(plan_id="plus")
    calls = _counting_provider(monkeypatch)
    for _ in range(4):
        assert word_detail.word_detail(_word())["available"] is True
    assert len(calls) == 4 and _consumed(repository, "word.assist") == 4


def test_enforcement_off_limits_nothing(monkeypatch):
    _catalogue(word_assist=1)
    repository = _runtime(env={})
    calls = _counting_provider(monkeypatch)
    for _ in range(3):
        assert word_detail.word_detail(_word())["available"] is True
    assert len(calls) == 3 and repository.calls == []


def test_enforcement_without_a_store_refuses_before_the_provider(monkeypatch):
    quota.configure_quota(settings=MemorySettings(), env=ON, reason="no_postgresql")
    calls = _counting_provider(monkeypatch)
    refused = _refused(lambda: word_detail.word_detail(_word()))
    assert refused.status_code == 503 and refused.detail["category"] == "quota_unavailable"
    assert calls == []


def test_the_contextual_dictionary_keeps_the_gates_refusal(monkeypatch):
    _catalogue(word_assist=1)
    _runtime()
    calls = _counting_provider(monkeypatch)
    payload = media_interaction.ContextualDictionaryIn(text="slukket", context="Vinduene slukket.",
                                                       source_language="en", target_language="vi")
    assert media_interaction.contextual_dictionary(payload)["available"] is True
    refused = _refused(lambda: media_interaction.contextual_dictionary(payload))
    assert refused.status_code == 429, "never turned into 'unavailable'"
    assert len(calls) == 1


# ---- word.assist: the tap's last layers (a miss, never an error) --------------------------------------------


def test_the_tap_translation_is_a_miss_past_the_limit_and_free_models_cost_nothing(monkeypatch):
    _catalogue(word_assist=1)
    repository = _runtime()
    tap_router.reset_state()
    asked: list[str] = []
    answer = {"provider": "openai", "model": "gpt-paid"}

    def route(capability, raw, **_kwargs):
        asked.append(raw["text"])
        return RouteResult(output={"meaning": f"vi:{raw['text']}"}, source="model", provenance=dict(answer))

    monkeypatch.setattr(router_module, "peek", lambda *_a, **_k: None)
    monkeypatch.setattr(router_module, "route", route)
    monkeypatch.setattr(assist_meters, "routed_cost", lambda result: result.provenance["model"] == "gpt-paid")
    answer["model"] = "free-model"
    assert tap_router.word_translation_seam("dog", "", [], "en", "vi") == "vi:dog"
    assert _consumed(repository, "word.assist") == 0, "an answer from a model the account gets free is not charged"
    answer["model"] = "gpt-paid"
    assert tap_router.word_translation_seam("cat", "", [], "en", "vi") == "vi:cat"
    assert tap_router.word_translation_seam("cow", "", [], "en", "vi") is None, "the tap keeps its deterministic answer"
    assert asked == ["dog", "cat"] and _consumed(repository, "word.assist") == 1


def test_routed_cost_charges_only_a_model_answer_from_a_paid_model():
    assert assist_meters.routed_cost(None) is False
    assert assist_meters.routed_cost(RouteResult(output={}, source="cache")) is False
    assert assist_meters.routed_cost(RouteResult(output={}, source="deterministic")) is False
    assert assist_meters.routed_cost(RouteResult(output={}, source="model", provenance={})) is True
    free = RouteResult(output={}, source="model", provenance={"provider": "openrouter", "model": "x/y:free"})
    assert assist_meters.routed_cost(free) is False


# ---- reading.assist -----------------------------------------------------------------------------------------


class PaidEngine:
    engine_id = "ai"
    model_version = "fake-ai-1"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def translate_batch(self, source_language, target_language, segments):
        self.calls.append([item.original_text for item in segments])
        return {item.segment_id: f"{target_language}|{item.original_text}" for item in segments}


@pytest.fixture
def reading(monkeypatch):
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    engine = PaidEngine()
    summaries: list[str] = []

    def generate(**_kwargs):
        summaries.append("summary")
        return {"bullets": ["One.", "Two."]}

    reading_translation_api.configure_reading_translation(ReadingTranslationService(engine, cache=DerivedCache()))
    reading_translation_api.configure_reading_summary(ReadingSummaryService(DerivedCache(), generate))
    app = FastAPI()
    app.include_router(reading_translation_api.router)
    try:
        yield TestClient(app), engine, summaries
    finally:
        reading_translation_api.configure_reading_translation(None)
        reading_translation_api.configure_reading_summary(None)


def _translate(http, text):
    return http.post("/api/reading/translate", json={"source_language": "en", "target_language": "vi",
                                                     "segments": [{"segment_id": "s1", "text": text}]})


def test_reading_assist_refuses_past_the_limit_and_a_held_meaning_is_free(reading):
    http, engine, summaries = reading
    _catalogue(reading_assist=2)
    repository = _runtime()
    assert _translate(http, "It rained.").status_code == 200
    assert _translate(http, "It rained.").status_code == 200            # held: never admitted
    summary = {"source_language": "en", "target_language": "vi", "text": "It rained all day."}
    assert http.post("/api/reading/summary", json=summary).status_code == 200
    refused = _translate(http, "We stayed in.")
    assert refused.status_code == 429 and refused.json()["detail"]["category"] == "quota_exhausted"
    assert refused.json()["detail"]["context"]["feature"] == "reading.assist"
    assert int(refused.headers["Retry-After"]) > 0
    assert http.post("/api/reading/summary", json={**summary, "text": "Another text."}).status_code == 429
    assert http.post("/api/reading/summary", json=summary).status_code == 200, "a held summary costs nothing"
    assert engine.calls == [["It rained."]] and summaries == ["summary"]
    assert _consumed(repository, "reading.assist") == 2


def test_reading_assist_on_a_paid_plan_and_with_enforcement_off(reading):
    http, engine, _summaries = reading
    _catalogue(reading_assist=1)
    _runtime(plan_id="pro")
    for index in range(3):
        assert _translate(http, f"Sentence {index}.").status_code == 200
    _runtime(env={})
    for index in range(3, 6):
        assert _translate(http, f"Sentence {index}.").status_code == 200
    assert len(engine.calls) == 6


def test_the_media_explain_route_is_reading_assist(monkeypatch):
    _catalogue(reading_assist=1)
    repository = _runtime()
    calls = _counting_provider(monkeypatch)
    payload = media_interaction.MediaExplainIn(text="slukket", context="Vinduene slukket.", source_language="en",
                                               target_language="vi")
    media_interaction.explain_media_text_route(payload)
    assert _refused(lambda: media_interaction.explain_media_text_route(payload)).status_code == 429
    assert len(calls) == 1 and _consumed(repository, "reading.assist") == 1


def test_the_sentence_sheet_is_reading_assist(monkeypatch):
    _catalogue(reading_assist=1)
    repository = _runtime()
    calls = _counting_provider(monkeypatch, answer={**EXPLANATION, "structure": []})
    sheet = word_detail.SentenceSheetIn(text="Vinduene slukket.", source_language="en", target_language="vi")
    assert word_detail.sentence_sheet(sheet)["available"] is True
    assert _refused(lambda: word_detail.sentence_sheet(
        word_detail.SentenceSheetIn(text="Hun kom.", source_language="en", target_language="vi"))).status_code == 429
    assert len(calls) == 1 and _consumed(repository, "reading.assist") == 1


# ---- writing.task -------------------------------------------------------------------------------------------


def test_writing_task_refuses_past_the_limit_and_the_built_in_task_is_free(monkeypatch):
    import app as app_module

    _catalogue(writing_task=1)
    repository = _runtime()
    calls: list[str] = []
    state = {"fail": True}

    def generate(**kwargs):
        calls.append(kwargs["capability_key"])
        if state["fail"]:
            raise ValueError("malformed")
        return SimpleNamespace(data={"title": "Email", "instruction": "Write to Anna.", "topic": "work",
                                     "checklist": ["Greet her", "Ask a question"]}, label="fake")

    monkeypatch.setattr(app_module, "generate_structured", generate)
    task = app_module.TaskGenerateIn(task_type="email", topic="work", target_cefr="B1", word_target=120)
    assert app_module.generate_practice_task(task)["source"] == "built-in", "the fallback answers"
    assert _consumed(repository, "writing.task") == 0, "the built-in task costs nothing"
    state["fail"] = False
    assert app_module.generate_practice_task(task)["source"] == "fake"
    refused = _refused(lambda: app_module.generate_practice_task(task))
    assert refused.status_code == 429 and refused.detail["context"]["feature"] == "writing.task"
    assert calls == ["writing_task_generator", "writing_task_generator"]
    assert _consumed(repository, "writing.task") == 1


# ---- word.assist and the word tap's own caches (#423) ----------------------------------------------------------

from tests.test_ai_router import env  # noqa: E402,F401 - the router's fixture: a fake free-tier pool, a fresh cache


def test_a_router_cache_hit_and_a_free_model_answer_cost_no_word_assist(env, monkeypatch):
    """The shared in-process `word_translation` cache (#423) is asked before the gate: a word any learner already
    tapped is answered without an admission; the free-tier model that answered the first tap settles 0."""
    _catalogue(word_assist=1)
    repository = _runtime()
    tap_router.reset_state()
    assert tap_router.word_translation_seam("lamp", "The lamp went out.", [], "en", "vi") == "đèn"
    assert len(env.fake.calls) == 1 and _consumed(repository, "word.assist") == 0, "a free model costs nothing"
    monkeypatch.setattr(assist_meters, "routed_cost", lambda _result: True)    # as if a paid model had answered
    before = list(repository.calls)
    for _ in range(3):
        assert tap_router.word_translation_seam("lamp", "Another lamp.", [], "en", "vi") == "đèn"
    assert len(env.fake.calls) == 1, "a cache hit asks no provider"
    assert repository.calls == before, "a cache hit is never admitted"


def test_catalogue_pack_and_local_answers_never_reach_the_meter():
    """Lookup order (#423): catalogue -> bilingual pack -> local MT -> `word_translation`. Only the last can be charged."""
    from writing_coach import bilingual_dictionary, reading_lookup
    from writing_coach.reading_lookup import ReadingLookupService

    _catalogue(word_assist=1)
    repository = _runtime()
    reading_lookup.reset_seam_gate()
    bilingual_dictionary.reset_packs()
    asked: list[tuple] = []

    def seam(*args):
        asked.append(args)
        return assist_meters.quiet(assist_meters.WORD_ASSIST, digest=args, ref="t", call=lambda: "x")

    class _Paid:
        engine_id = "ai"
        model_version = "x"

        def translate_batch(self, *_a, **_k):
            raise AssertionError("a tap never uses the paid reading engine")

    service = ReadingLookupService(
        None, lambda _w: {"phonetic": ""}, ReadingTranslationService(_Paid(), cache=DerivedCache()),
        word_translation=seam, bilingual_dictionary=lambda word, _s, _t, **_k: {"shield": "tấm chắn"}.get(word),
    )
    result = service.lookup("shield", "Its heat shield held.", "en", "vi").to_dict()
    assert result["meanings"][0]["source"] == "bilingual_dictionary"
    assert asked == [] and repository.calls == [], "the pack's answer is free and admits nothing"
    bilingual_dictionary.reset_packs()
