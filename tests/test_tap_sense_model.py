"""The model step of a word tap's sense choice (D-228, PROPOSED). Fake providers only: no network, no key, no live call.

It is asked only when the zero-cost rules tie; free-tier models first for shared content, then the cheapest paid ones;
a learner's own sentence never reaches a free tier; a paid rung is behind the daily cap; any failure keeps the neutral
sense; the answer is an index into the stored senses, never text.
"""

from __future__ import annotations

from typing import Any

import pytest

import writing_coach.ai.platform as platform
from tests.test_ai_router import Repository, http_error
from tests.test_tap_sense import _Catalogue, _Engine, _entry, _tagger
from writing_coach import cost_tier, policies, reading_cache_scope, reading_lookup, tap_sense_model
from writing_coach.ai import routing, spend_gate
from writing_coach.ai.base import AIResult
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.router import router as router_module
from writing_coach.ai.router import tap
from writing_coach.ai.router.contract import get_contract
from writing_coach.ai.router.contracts.word_sense_choice import sentence_digest
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import LookupDefinition, ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService
from writing_coach.tap_sense import catalogue_ties, definition_ties, sentence_around

FREE_OR = "google/gemma-4-31b-it:free"
SENTENCE = "The bank was steep and muddy after the rain."
SENSES = ["ngân hàng", "bờ sông"]


class Fake:
    """A scripted provider: `answers[model]` is a queue of answers or exceptions; the default picks sense 1."""

    def __init__(self, provider_id: str, models: list[str]) -> None:
        self.id, self.name, self.configured = provider_id, provider_id, True
        self.models = models
        self.calls: list[dict[str, Any]] = []
        self.script: dict[str, list[Any]] = {}

    def list_models(self, offline: bool = False) -> list[str]:
        return list(self.models)

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.calls.append(kwargs)
        queue = self.script.get(kwargs["model"])
        item = queue.pop(0) if queue else {"choice": 1}
        if isinstance(item, BaseException):
            raise item
        return AIResult(data=item, provider=self.id, model=kwargs["model"],
                        runtime={"prompt_tokens": 220, "completion_tokens": 8, "total_tokens": 228})

    generate_json = generate_json_once


@pytest.fixture
def env(monkeypatch):
    repository = Repository(CapabilityConfig(enabled=True, provider="openai", model="gpt-4o-mini",
                                             fallback_policy="none"))
    openrouter = Fake("openrouter", [FREE_OR])
    groq = Fake("groq", ["llama-3.3-70b-versatile"])
    openai = Fake("openai", ["gpt-4o-mini"])
    deepseek = Fake("deepseek", ["deepseek-chat"])
    registry = {"openrouter": openrouter, "groq": groq, "openai": openai, "deepseek": deepseek}
    spent = {"usd": 0.0}
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: registry)
    monkeypatch.setattr(repository, "ai_spend_since_for_capability",
                        lambda capability, since, **_: (spent["usd"], 0), raising=False)
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0.25)
    monkeypatch.setattr(cost_tier, "is_free_tier", lambda provider, env=None: provider == "groq")  # the Admin flag
    monkeypatch.setattr(router_module, "CONFIG_TTL_SECONDS", 0.0)
    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda key: "abc")
    routing.provider_health.reset()
    router_module.reset_state()
    spend_gate.reset()
    tap.reset_state()
    yield type("Env", (), {"repo": repository, "spent": spent, **registry, "registry": registry})
    routing.provider_health.reset()
    router_module.reset_state()
    spend_gate.reset()
    tap.reset_state()


def order(env) -> list[str]:
    return [f"{fake.id}:{call['model']}" for fake in env.registry.values() for call in fake.calls]


def asked(env) -> int:
    return sum(len(fake.calls) for fake in env.registry.values())


def choose(*, shared: bool, sentence: str = SENTENCE, senses=None):
    return tap_sense_model.choose_sense("bank", sentence, senses or SENSES, "en", "vi", shared=shared)


# --- the pool: who is asked, in which order ---------------------------------------------------------------------


def test_shared_pool_is_free_tier_models_first_then_the_cheapest_paid(env) -> None:
    pool = tap_sense_model.build_pool(shared=True)
    # openrouter ':free' (zero-rate model) and groq (provider flagged free tier) come first, in provider order;
    # then gpt-4o-mini (0.15/0.60) before deepseek-chat (0.27/1.10).
    assert [(t.provider, t.model) for t in pool] == [
        ("openrouter", FREE_OR), ("groq", "llama-3.3-70b-versatile"), ("openai", "gpt-4o-mini"),
        ("deepseek", "deepseek-chat"),
    ]


def test_a_learners_own_content_has_no_pool_at_all(env) -> None:
    assert tap_sense_model.build_pool(shared=False) == []
    env.openai.models = ["gpt-4o-mini", "model-without-a-price"]
    assert ("openai", "model-without-a-price") not in [
        (t.provider, t.model) for t in tap_sense_model.build_pool(shared=True)]  # an unpriced paid model is never used


def test_a_free_flag_turned_off_makes_the_provider_an_ordinary_paid_one(env, monkeypatch) -> None:
    monkeypatch.setattr(cost_tier, "is_free_tier", lambda provider, env=None: False)
    pool = [(t.provider, t.model) for t in tap_sense_model.build_pool(shared=True)]
    assert pool == [("openrouter", FREE_OR), ("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")]  # two cheapest paid


# --- the call ---------------------------------------------------------------------------------------------------


def test_a_tie_asks_one_model_once_and_the_answer_is_cached(env) -> None:
    assert choose(shared=True) == 1
    assert choose(shared=True) == 1
    assert order(env) == [f"openrouter:{FREE_OR}"]  # the first free model answered; the second tap is the cache
    assert env.openai.calls == []


def test_the_cache_is_keyed_by_word_sentence_language_and_scope(env) -> None:
    choose(shared=True)
    choose(shared=True, sentence="He went to the bank to pay the bill.")  # another sentence
    assert asked(env) == 2
    env.openrouter.script = {FREE_OR: [{"choice": 0}]}
    zh = tap_sense_model.choose_sense("bank", SENTENCE, ["银行", "河岸"], "en", "zh", shared=True)
    assert asked(env) == 3 and zh == 0  # another support language: a fresh call, its own answer (not the vi one)
    assert choose(shared=True) == 1 and asked(env) == 3  # the first (word, sentence, vi, shared) is still cached
    contract = get_contract("word_sense_choice")
    material = contract.normalize(contract.input_model(
        word="Bank", sentence=SENTENCE, source_language="en", target_language="vi", senses=SENSES, cache_scope="shared"))
    assert material["sentence"] == sentence_digest(SENTENCE) and SENTENCE not in str(material)
    assert material["support_language"] == "vi" and material["scope"] == "shared"


def test_free_tier_first_then_the_cheapest_paid_when_they_fail(env) -> None:
    env.openrouter.script = {FREE_OR: [http_error(429), http_error(429)]}
    env.groq.script = {"llama-3.3-70b-versatile": [http_error(503), http_error(503)]}
    assert choose(shared=True) == 1
    assert order(env)[-1] == "openai:gpt-4o-mini" and env.deepseek.calls == []
    assert order(env)[:2] == [f"openrouter:{FREE_OR}", "groq:llama-3.3-70b-versatile"]


def test_the_paid_call_is_booked_to_the_shared_ledger_under_the_capability(env) -> None:
    env.openrouter.script = {FREE_OR: [http_error(429)]}
    env.groq.script = {"llama-3.3-70b-versatile": [http_error(429)]}
    choose(shared=True)
    booked = [op for op in env.repo.operations if op["provider"] == "openai"]
    assert len(booked) == 1 and booked[0]["capability"] == "word_sense_choice" and booked[0]["tier"] == "paid"
    assert booked[0]["cost"]["amount"] == pytest.approx((220 * 0.15 + 8 * 0.60) / 1_000_000)
    assert tap_sense_model.estimated_call_usd("openai", "gpt-4o-mini") == pytest.approx(booked[0]["cost"]["amount"])


def test_a_learners_own_sentence_reaches_no_ai_at_all(env) -> None:
    assert choose(shared=False) is None
    assert asked(env) == 0


def test_a_private_sentence_is_not_sent_even_with_a_non_openai_stored_config(env) -> None:
    env.repo.config = CapabilityConfig(enabled=True, provider="groq", model="llama-3.3-70b-versatile",
                                       fallback_policy="none")
    assert choose(shared=False) is None
    assert asked(env) == 0


def test_the_daily_cap_reached_means_no_paid_call_but_free_rungs_still_run(env) -> None:
    env.spent["usd"] = 0.25
    env.openrouter.script = {FREE_OR: [http_error(429)]}
    env.groq.script = {"llama-3.3-70b-versatile": [http_error(429)]}
    assert choose(shared=True) is None  # the free rungs failed; the paid ones are over the cap
    assert env.openai.calls == [] and env.deepseek.calls == []
    spend_gate.reset()
    router_module.reset_state()
    env.openrouter.script = {}
    assert choose(shared=True) == 1 and order(env)[-1] == f"openrouter:{FREE_OR}"


def test_a_zero_cap_and_an_unreadable_ledger_fail_closed(env, monkeypatch) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0)
    env.openrouter.script = {FREE_OR: [http_error(429)]}
    env.groq.script = {"llama-3.3-70b-versatile": [http_error(429)]}
    assert choose(shared=True) is None
    assert env.openai.calls == [] and env.deepseek.calls == []


def test_an_unfunded_learner_is_a_quiet_miss(env, monkeypatch, caplog) -> None:
    from writing_coach.billing.funding_context import FundingRequired

    def refuse(*args, **kwargs):
        raise FundingRequired("no_unpaid_rung", capability="word_sense_choice")

    monkeypatch.setattr(router_module, "route", refuse)
    with caplog.at_level("WARNING", logger="orena.lookup"):
        assert choose(shared=True) is None
    assert caplog.records == []


# --- the pool rule (D-228) ---------------------------------------------------------------------------------------


def test_a_pool_is_refused_for_every_capability_but_word_sense_choice(env) -> None:
    from writing_coach.ai.base import AICapabilityUnsupported
    from writing_coach.ai.routing import ProviderTarget

    pool = [ProviderTarget("openai", "gpt-4o-mini")]
    with pytest.raises(AICapabilityUnsupported):
        router_module.route("word_translation", {"text": "lamp", "source_language": "en", "target_language": "vi"},
                            pool=pool)
    with pytest.raises(AICapabilityUnsupported):
        platform.generate_structured(messages=[], schema={}, capability_key="writing_evaluator",
                                     capability_mode=True, pool=pool)
    assert asked(env) == 0


@pytest.mark.parametrize("pool", [None, []])
def test_word_sense_choice_fails_closed_without_a_pool(env, pool) -> None:
    from writing_coach.ai.base import AICapabilityUnsupported

    raw = {"word": "bank", "sentence": SENTENCE, "source_language": "en", "target_language": "vi",
           "senses": SENSES, "cache_scope": "shared"}
    with pytest.raises(AICapabilityUnsupported):
        router_module.route("word_sense_choice", raw, pool=pool)
    with pytest.raises(AICapabilityUnsupported):
        platform.generate_structured(messages=[], schema={}, capability_key="word_sense_choice",
                                     capability_mode=True, pool=pool)
    assert asked(env) == 0


def test_the_stored_config_is_ignored_even_when_it_is_a_prompt_logging_free_tier(env) -> None:
    from writing_coach.ai.routing import ProviderTarget

    env.repo.config = CapabilityConfig(enabled=True, provider="openrouter", model=FREE_OR, fallback_policy="none")
    raw = {"word": "bank", "sentence": SENTENCE, "source_language": "en", "target_language": "vi",
           "senses": SENSES, "cache_scope": "shared"}
    result = router_module.route("word_sense_choice", raw, pool=[ProviderTarget("openai", "gpt-4o-mini")])
    assert result.output == {"choice": 1}
    assert order(env) == ["openai:gpt-4o-mini"] and env.openrouter.calls == []


def test_a_long_sense_is_sent_cut_and_the_index_still_maps_to_the_stored_one(env) -> None:
    long = "x" * 200
    assert tap_sense_model.choose_sense("bank", SENTENCE, [long + "a", long + "b"], "en", "vi", shared=True) is None
    # cut to the limit the two collide: not distinct, so nothing is asked and the neutral sense stays
    assert asked(env) == 0
    senses = ["a" * 150 + " đầu", "b" * 200]
    assert tap_sense_model.choose_sense("bank", SENTENCE, senses, "en", "vi", shared=True) == 1
    user = env.openrouter.calls[0]["messages"][1]["content"]
    assert "b" * 160 in user and "b" * 161 not in user


@pytest.mark.parametrize("answer", [{"choice": 7}, {"choice": -1}, {"choice": "1"}, {"choice": True},
                                    {"choice": 1.0}, {"meaning": "bờ sông"}, {"choice": 1, "text": "x"}, {}])
def test_a_malformed_answer_keeps_the_neutral_sense(env, answer) -> None:
    for fake in env.registry.values():
        fake.script = {model: [answer] * 4 for model in fake.models}
    assert choose(shared=True) is None


def test_every_model_failing_keeps_the_neutral_sense(env) -> None:
    for fake in env.registry.values():
        fake.script = {model: [http_error(500)] * 4 for model in fake.models}
    assert choose(shared=True) is None


def test_a_disabled_capability_asks_nobody(env) -> None:
    env.repo.config = CapabilityConfig(enabled=False, provider="openai", model="gpt-4o-mini", fallback_policy="none")
    assert choose(shared=True) is None
    assert asked(env) == 0


def test_the_prompt_carries_the_sentence_and_numbered_senses_but_never_the_scope(env) -> None:
    choose(shared=True)
    system, user = env.openrouter.calls[0]["messages"]
    assert "never write a meaning yourself" in system["content"]
    assert SENTENCE in user["content"] and "ngân hàng" in user["content"] and "shared" not in user["content"]


# --- the tie, and the lookup around it --------------------------------------------------------------------------


def test_catalogue_ties_only_when_class_and_language_leave_two_distinct_senses() -> None:
    noun_a, noun_b = _entry("bank", "noun", vi="ngân hàng"), _entry("bank", "noun", vi="bờ sông")
    verb = _entry("bank", "verb", vi="nghiêng")
    assert catalogue_ties([noun_a, verb, noun_b], "noun", "vi") == [noun_a, noun_b]
    assert catalogue_ties([noun_a, verb, noun_b], "verb", "vi") == []  # the class decided
    assert catalogue_ties([noun_a, noun_b], "", "vi") == [noun_a, noun_b]  # no class: nothing decides
    assert catalogue_ties([noun_a, _entry("bank", "noun", vi="Ngân hàng")], "noun", "vi") == []  # the same meaning
    assert catalogue_ties([noun_a, _entry("bank", "noun", en="shore")], "noun", "vi") == []  # one with no vi text
    assert catalogue_ties([_entry("bank", "noun", en="x"), noun_b, _entry("bank", "noun", vi="khác")], "verb", "vi") == [
        noun_b, _entry("bank", "noun", vi="khác")]


def test_definition_ties_and_the_sentence_cut() -> None:
    a, b, v = LookupDefinition("noun", "a bank of a river"), LookupDefinition("noun", "a financial firm"), \
        LookupDefinition("verb", "to tilt")
    assert definition_ties([a, v, b], "noun") == [a, b]
    assert definition_ties([a, v], "noun") == []
    assert sentence_around("First one. The bank was steep! Third.", "bank") == "The bank was steep!"
    assert sentence_around("no word here", "bank") == ""
    long = "word " * 200 + "bank " + "word " * 200
    cut = sentence_around(long, "bank")
    assert "bank" in cut and len(cut) <= 300


def _service(catalogue, calls, answer, *, dictionary=lambda word: None):
    def seam(word, sentence, senses, source, target, shared):
        calls.append((word, sentence, list(senses), source, target, shared))
        return answer

    return ReadingLookupService(
        catalogue, dictionary, ReadingTranslationService(_Engine(), cache=DerivedCache()), sense_choice=seam,
    )


@pytest.fixture(autouse=True)
def _gate():
    reading_lookup.reset_seam_gate()
    yield
    reading_lookup.reset_seam_gate()


def _bank():
    return _Catalogue({("en", "bank"): [_entry("bank", "noun", vi="ngân hàng"), _entry("bank", "noun", vi="bờ sông")]})


@pytest.fixture
def published(monkeypatch):
    monkeypatch.setattr(reading_cache_scope, "_published_article",
                        lambda article_id: {"title": "River", "body": SENTENCE} if article_id == "a1" else None)


def test_a_tie_asks_the_seam_once_and_shows_the_stored_sense_it_names(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    result = _service(_bank(), calls, 1).lookup("bank", SENTENCE, "en", "vi", content_id="article:a1").to_dict()
    assert result["meanings"] == [{"text": "bờ sông", "source": "collection"}]
    assert calls == [("bank", SENTENCE, ["ngân hàng", "bờ sông"], "en", "vi", True)]  # verified shared content


def test_a_learners_own_content_never_asks_the_seam(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    service = _service(_bank(), calls, 1)
    for content_id in (None, "", "article:nope", "article:a1"):
        text = SENTENCE if content_id != "article:a1" else SENTENCE + " It rained."  # not all in the article
        result = service.lookup("bank", text, "en", "vi", content_id=content_id).to_dict()
        assert result["meanings"][0]["text"] == "ngân hàng"
    assert calls == []


def test_a_disabled_capability_short_circuits_before_any_article_is_read(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    reads: list = []
    monkeypatch.setattr(reading_lookup, "scope_for", lambda *a, **k: reads.append(a))
    calls: list = []

    def seam(*args):
        calls.append(args)
        return 1

    service = ReadingLookupService(_bank(), lambda w: None, ReadingTranslationService(_Engine(), cache=DerivedCache()),
                                   sense_choice=seam, sense_choice_enabled=lambda: False)
    service.lookup("bank", SENTENCE, "en", "vi", content_id="article:a1")
    assert reads == [] and calls == []


@pytest.mark.parametrize("answer", [None, 0, 5, -1, "1", True])
def test_no_answer_or_an_unusable_one_keeps_the_neutral_sense(monkeypatch, published, answer) -> None:
    _tagger(monkeypatch, pos="noun")
    result = _service(_bank(), [], answer).lookup("bank", SENTENCE, "en", "vi", content_id="article:a1").to_dict()
    assert result["meanings"] == [{"text": "ngân hàng", "source": "collection"}]


def test_a_decided_sense_never_asks(monkeypatch) -> None:
    _tagger(monkeypatch, pos="verb")
    catalogue = _Catalogue({("en", "plan"): [_entry("plan", "noun", vi="bản vẽ"), _entry("plan", "verb", vi="lên kế hoạch")]})
    calls: list = []
    result = _service(catalogue, calls, 1).lookup("plan", "We plan to leave.", "en", "vi").to_dict()
    assert result["meanings"][0]["text"] == "lên kế hoạch" and calls == []
    single = _Catalogue({("en", "lamp"): [_entry("lamp", "noun", vi="đèn")]})
    _service(single, calls, 1).lookup("lamp", "A lamp.", "en", "vi")
    assert calls == []


def test_a_seam_that_raises_is_a_miss_and_the_sheet_is_not_blocked(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")

    def boom(*args):
        raise RuntimeError("provider down")

    service = ReadingLookupService(_bank(), lambda word: None, ReadingTranslationService(_Engine(), cache=DerivedCache()),
                                   sense_choice=boom)
    assert service.lookup("bank", SENTENCE, "en", "vi", content_id="article:a1").to_dict()["meanings"][0]["text"] == "ngân hàng"


def test_english_support_language_reorders_the_tied_dictionary_definitions(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    dictionary = lambda word: {"definitions": [  # noqa: E731
        {"part_of_speech": "noun", "definition": "a financial firm"},
        {"part_of_speech": "noun", "definition": "the side of a river"},
    ], "phonetic": ""}
    calls: list = []
    result = _service(None, calls, 1, dictionary=dictionary).lookup("bank", SENTENCE, "en", "en", content_id="article:a1").to_dict()
    assert calls == [("bank", SENTENCE, ["a financial firm", "the side of a river"], "en", "en", True)]
    assert [d["definition"] for d in result["definitions"]] == ["the side of a river", "a financial firm"]
    reading_lookup.reset_seam_gate()
    kept = _service(None, [], None, dictionary=dictionary).lookup("bank", SENTENCE, "en", "en", content_id="article:a1").to_dict()
    assert kept["definitions"][0]["definition"] == "a financial firm"  # no answer: the dictionary's first stays


def test_a_localised_meaning_in_hand_is_not_replaced_by_definitions(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    single = _Catalogue({("en", "bank"): [_entry("bank", "noun", vi="ngân hàng")]})
    dictionary = lambda word: {"definitions": [  # noqa: E731
        {"part_of_speech": "noun", "definition": "a financial firm"},
        {"part_of_speech": "noun", "definition": "the side of a river"},
    ], "phonetic": ""}
    calls: list = []
    _service(single, calls, 1, dictionary=dictionary).lookup("bank", SENTENCE, "en", "vi", content_id="article:a1")
    assert calls == []  # one stored sense in the support language: nothing ties, the dictionary does not drive it


def test_the_shared_scope_needs_a_published_article_that_holds_the_sentence(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    service = _service(_bank(), calls, 1)
    service.lookup("bank", SENTENCE, "en", "vi", content_id="article:a1")
    service.lookup("bank", SENTENCE + " It rained.", "en", "vi", content_id="article:a1")  # not all in the article
    service.lookup("bank", SENTENCE, "en", "vi", content_id="article:nope")
    service.lookup("bank", SENTENCE, "en", "vi")
    assert [call[5] for call in calls] == [True]


def test_sentence_around_uses_word_boundaries_and_refuses_an_ambiguous_tap() -> None:
    assert sentence_around("The banking sector grew. She sat on the bank.", "bank") == "She sat on the bank."
    assert sentence_around("Banks closed. Nothing else.", "bank") == ""  # only inside another word
    assert sentence_around("I went to the bank. The bank was closed.", "bank") == ""  # two sentences: which was tapped?
    assert sentence_around("I went to the bank. The bank was closed.", "bank", at=24) == "The bank was closed."
    assert sentence_around("The bank, the bank.", "bank") == "The bank, the bank."  # one sentence either way
    assert sentence_around("他去了银行。她读书。", "银行") == "他去了银行。"  # Chinese has no boundaries to respect


def test_the_lookup_route_forwards_content_id() -> None:
    from writing_coach.reading_translation_api import ReadingLookupIn

    assert ReadingLookupIn(text="bank", context="bank", source_language="en", target_language="vi",
                           content_id="article:a1").content_id == "article:a1"
    assert ReadingLookupIn(text="bank", context="bank", source_language="en", target_language="vi").content_id is None


def _sheet(monkeypatch, service, content_id):
    from writing_coach import word_detail

    monkeypatch.setattr(word_detail, "_lookup", service.lookup)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    extra = {} if content_id is None else {"content_id": content_id}
    return word_detail.word_detail(word_detail.WordDetailIn(
        text="bank", context=SENTENCE, source_language="en", target_language="vi", depth="sheet", contextual=False,
        **extra,
    ))


def test_the_word_detail_tap_forwards_content_id_to_the_sense_choice(monkeypatch, published) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    _sheet(monkeypatch, _service(_bank(), calls, 1), "article:a1")
    assert [call[5] for call in calls] == [True]  # verified shared content reaches the seam as shared


@pytest.mark.parametrize("content_id", [None, "text:imp-1", "article:nope", "media:m-9"])
def test_the_word_detail_tap_stays_private_without_a_verified_id(monkeypatch, published, content_id) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    _sheet(monkeypatch, _service(_bank(), calls, 1), content_id)
    assert calls == []  # private: no seam, no AI


# --- a keyed provider with no named models still has its priced catalogue models (issue #312) ---------------------------

GEMINI = "gemini-3.5-flash-lite"


class Unlisted(Fake):
    """A keyed provider the operator named no models for: the offline read has nothing (a real Gemini without GEMINI_MODELS)."""

    def list_models(self, offline: bool = False) -> list[str]:
        return []


@pytest.fixture
def keyed(env, monkeypatch):
    gemini = Unlisted("gemini", [])
    registry = {"openrouter": env.openrouter, "groq": env.groq, "gemini": gemini}
    monkeypatch.setattr(platform, "providers", lambda: registry)
    return type("Keyed", (), {"gemini": gemini, "openrouter": env.openrouter, "groq": env.groq, "registry": registry,
                              "spent": env.spent})


def test_a_keyed_gemini_with_no_model_list_is_a_paid_rung_after_the_free_ones(keyed) -> None:
    pool = [(t.provider, t.model) for t in tap_sense_model.build_pool(shared=True)]
    assert pool[0] == ("openrouter", FREE_OR) and ("gemini", GEMINI) in pool
    assert pool.index(("openrouter", FREE_OR)) < pool.index(("gemini", GEMINI))


def test_free_rungs_failing_calls_gemini_flash_lite(keyed) -> None:
    keyed.openrouter.script = {FREE_OR: [http_error(429)]}
    keyed.groq.script = {"llama-3.3-70b-versatile": [http_error(503), http_error(503)]}
    assert choose(shared=True) == 1
    assert [c["model"] for c in keyed.gemini.calls] == ["gemini-3.1-flash-lite"]  # the cheaper of the two flash-lites


def test_the_cap_reached_means_no_gemini_call(keyed) -> None:
    keyed.spent["usd"] = 0.25
    keyed.openrouter.script = {FREE_OR: [http_error(429)]}
    keyed.groq.script = {"llama-3.3-70b-versatile": [http_error(429)]}
    assert choose(shared=True) is None
    assert keyed.gemini.calls == []


def test_private_content_never_reaches_gemini(keyed) -> None:
    assert choose(shared=False) is None
    assert keyed.gemini.calls == [] and keyed.openrouter.calls == [] and keyed.groq.calls == []


def test_shut_down_and_free_plan_models_are_not_a_fallback_list() -> None:
    from writing_coach.ai.pricing import priced_catalogue_models

    assert priced_catalogue_models("gemini") == [GEMINI, "gemini-3.1-flash-lite"]
    groq = priced_catalogue_models("groq")
    assert "llama-3.3-70b-versatile" not in groq and "openai/gpt-oss-120b" in groq
    assert priced_catalogue_models("openrouter") == []
