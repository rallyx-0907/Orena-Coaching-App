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


def test_private_pool_has_no_free_tier_and_no_prompt_logging_provider(env) -> None:
    pool = tap_sense_model.build_pool(shared=False)
    assert [(t.provider, t.model) for t in pool] == [("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")]
    env.openai.models = ["gpt-4o-mini", "model-without-a-price"]
    assert ("openai", "model-without-a-price") not in [(t.provider, t.model) for t in tap_sense_model.build_pool(shared=True)]


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
    choose(shared=False)  # the same sentence as private content: its own entry, and it never reuses the shared one
    assert asked(env) == 3
    assert tap_sense_model.choose_sense("bank", SENTENCE, SENSES, "en", "zh", shared=True) in (0, 1, None)
    assert asked(env) == 4
    contract = get_contract("word_sense_choice")
    material = contract.normalize(contract.input_model(
        word="Bank", sentence=SENTENCE, source_language="en", target_language="vi", senses=SENSES, cache_scope="shared"))
    assert material["sentence"] == sentence_digest(SENTENCE) and SENTENCE not in str(material)


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


def test_a_learners_own_sentence_never_reaches_a_free_tier(env) -> None:
    assert choose(shared=False) == 1
    assert order(env) == ["openai:gpt-4o-mini"]
    assert env.openrouter.calls == [] and env.groq.calls == []


def test_a_private_sentence_with_no_eligible_model_keeps_the_neutral_sense(env) -> None:
    env.openai.models, env.deepseek.models = [], []
    assert choose(shared=False) is None
    assert asked(env) == 0


def test_the_daily_cap_reached_means_no_paid_call(env) -> None:
    env.spent["usd"] = 0.25
    assert choose(shared=False) is None
    assert asked(env) == 0
    # the free rungs of shared content are not gated by the paid cap
    spend_gate.reset()
    assert choose(shared=True) == 1 and order(env) == [f"openrouter:{FREE_OR}"]


def test_a_zero_cap_and_an_unreadable_ledger_fail_closed(env, monkeypatch) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0)
    assert choose(shared=False) is None
    assert asked(env) == 0


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


def test_a_tie_asks_the_seam_once_and_shows_the_stored_sense_it_names(monkeypatch) -> None:
    _tagger(monkeypatch, pos="noun")
    calls: list = []
    result = _service(_bank(), calls, 1).lookup("bank", SENTENCE, "en", "vi").to_dict()
    assert result["meanings"] == [{"text": "bờ sông", "source": "collection"}]
    assert calls == [("bank", SENTENCE, ["ngân hàng", "bờ sông"], "en", "vi", False)]  # unverified content: private


@pytest.mark.parametrize("answer", [None, 0, 5, -1, "1", True])
def test_no_answer_or_an_unusable_one_keeps_the_neutral_sense(monkeypatch, answer) -> None:
    _tagger(monkeypatch, pos="noun")
    result = _service(_bank(), [], answer).lookup("bank", SENTENCE, "en", "vi").to_dict()
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


def test_a_seam_that_raises_is_a_miss_and_the_sheet_is_not_blocked(monkeypatch) -> None:
    _tagger(monkeypatch, pos="noun")

    def boom(*args):
        raise RuntimeError("provider down")

    service = ReadingLookupService(_bank(), lambda word: None, ReadingTranslationService(_Engine(), cache=DerivedCache()),
                                   sense_choice=boom)
    assert service.lookup("bank", SENTENCE, "en", "vi").to_dict()["meanings"][0]["text"] == "ngân hàng"


def test_english_support_language_reorders_the_tied_dictionary_definitions(monkeypatch) -> None:
    _tagger(monkeypatch, pos="noun")
    dictionary = lambda word: {"definitions": [  # noqa: E731
        {"part_of_speech": "noun", "definition": "a financial firm"},
        {"part_of_speech": "noun", "definition": "the side of a river"},
    ], "phonetic": ""}
    calls: list = []
    result = _service(None, calls, 1, dictionary=dictionary).lookup("bank", SENTENCE, "en", "en").to_dict()
    assert calls == [("bank", SENTENCE, ["a financial firm", "the side of a river"], "en", "en", False)]
    assert [d["definition"] for d in result["definitions"]] == ["the side of a river", "a financial firm"]
    reading_lookup.reset_seam_gate()
    kept = _service(None, [], None, dictionary=dictionary).lookup("bank", SENTENCE, "en", "en").to_dict()
    assert kept["definitions"][0]["definition"] == "a financial firm"  # no answer: the dictionary's first stays


def test_a_localised_meaning_in_hand_is_not_replaced_by_definitions(monkeypatch) -> None:
    _tagger(monkeypatch, pos="noun")
    single = _Catalogue({("en", "bank"): [_entry("bank", "noun", vi="ngân hàng")]})
    dictionary = lambda word: {"definitions": [  # noqa: E731
        {"part_of_speech": "noun", "definition": "a financial firm"},
        {"part_of_speech": "noun", "definition": "the side of a river"},
    ], "phonetic": ""}
    calls: list = []
    _service(single, calls, 1, dictionary=dictionary).lookup("bank", SENTENCE, "en", "vi")
    assert calls == []  # one stored sense in the support language: nothing ties, the dictionary does not drive it


def test_the_shared_scope_needs_a_published_article_that_holds_the_sentence(monkeypatch) -> None:
    _tagger(monkeypatch, pos="noun")
    monkeypatch.setattr(reading_cache_scope, "_published_article",
                        lambda article_id: {"title": "River", "body": SENTENCE} if article_id == "a1" else None)
    calls: list = []
    service = _service(_bank(), calls, 1)
    service.lookup("bank", SENTENCE, "en", "vi", content_id="article:a1")
    service.lookup("bank", SENTENCE + " It rained.", "en", "vi", content_id="article:a1")  # not all in the article
    service.lookup("bank", SENTENCE, "en", "vi", content_id="article:nope")
    service.lookup("bank", SENTENCE, "en", "vi")
    reading_lookup.reset_seam_gate()
    assert [call[5] for call in calls] == [True, False, False, False]


def test_the_lookup_route_forwards_content_id() -> None:
    from writing_coach.reading_translation_api import ReadingLookupIn

    assert ReadingLookupIn(text="bank", context="bank", source_language="en", target_language="vi",
                           content_id="article:a1").content_id == "article:a1"
    assert ReadingLookupIn(text="bank", context="bank", source_language="en", target_language="vi").content_id is None
