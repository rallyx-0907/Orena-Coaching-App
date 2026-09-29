"""The Writing request minimum: one table, one row per learning language.

A request minimum answers one question: is this an attempt at writing at all?
It is not a grading threshold. A text that is an attempt but too short to judge
is the evaluator's to handle (`band_status: insufficient_evidence`), and it
still costs one review - which is the right price for a learner who wrote
something. What the minimum refuses is the text that is not writing: nothing,
whitespace, punctuation, one stray character.

It used to be a flat `min_length=10` on the request models. That counted code
points, so it meant a different thing in every script: ten characters is a
paragraph in Chinese - `我是学生。` is a complete HSK 1 sentence and is five -
and it is barely a phrase in English. It also counted whitespace, so ten spaces
passed it. The minimum is now a per-learning-language unit and count, defined
once in `writing_coach/writing_limits.py`, and the browser is held to the same
table by `tests/fixtures/writing_minimum_cases.json`, which
`scripts/test_orena_writing_workspace.mjs` reads too.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from writing_coach import writing_limits as limits  # noqa: E402
from writing_coach.core.language_registry import all_languages  # noqa: E402
from writing_coach.languages.grammar_registry import grammar_provider_codes  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "writing_minimum_cases.json").read_text(encoding="utf-8")
)

# A language with no row of its own. Not a language the product teaches: it
# exists to prove the fallback is the stated default rather than an error.
UNLISTED = "xx"

# What a learner would have to write to be exactly n units long, per unit. A
# new unit needs a builder here, so a new row cannot land untested.
SAMPLES = {
    "han": lambda n: ("好" * n + "。") if n else "",
    "words": lambda n: (" ".join(["word"] * n) + ".") if n else "",
}

NOT_AN_ATTEMPT = (
    "",
    " ",
    "          ",
    "\n\n\n\n\n\n\n\n\n\n\n\n",
    "\t \r\n \t \r\n",
    "。。。。。。。。。。。。",
    "...........",
    "?!?!?!?!?!?!",
    "！？，、；：！？，、",
    "😀😀😀😀😀😀😀😀😀😀😀",
    "1234567890123",
    "-_-_-_-_-_-_-_",
    "​​​​​​​​​​​",
)


def _case_id(case: dict[str, Any]) -> str:
    return f"{case['language']}-{case['note']}"[:70]


# --- The table -----------------------------------------------------------


def test_the_table_is_exactly_the_one_the_browser_is_held_to() -> None:
    table = {
        code: {"unit": rule.unit, "minimum": rule.minimum}
        for code, rule in limits.MINIMUM_BY_LANGUAGE.items()
    }
    assert table == FIXTURE["table"]
    assert {
        "unit": limits.DEFAULT_MINIMUM.unit,
        "minimum": limits.DEFAULT_MINIMUM.minimum,
    } == FIXTURE["default"]


def test_every_language_the_product_writes_in_has_a_row_of_its_own() -> None:
    """A new learning language must decide its unit, not inherit one by accident.

    The default exists for a language nobody has looked at yet. Once a language
    is one the product teaches, an unspaced script counted in "words" would
    refuse every sentence, so adding one has to add a row - and this fails until
    it does.
    """
    taught = set(grammar_provider_codes()) | {
        language.code for language in all_languages() if language.enabled
    }
    assert taught, "the product teaches at least one language"
    missing = taught - set(limits.MINIMUM_BY_LANGUAGE)
    assert not missing, f"learning languages without a Writing minimum row: {sorted(missing)}"


def test_chinese_is_counted_in_han_characters_and_english_in_words() -> None:
    assert limits.MINIMUM_BY_LANGUAGE["zh"].unit == "han"
    assert limits.MINIMUM_BY_LANGUAGE["en"].unit == "words"


def test_a_language_with_no_row_gets_the_stated_default() -> None:
    assert UNLISTED not in limits.MINIMUM_BY_LANGUAGE
    for language in (UNLISTED, None, "", "  "):
        assert limits.minimum_rule(language) == limits.DEFAULT_MINIMUM
    assert limits.DEFAULT_MINIMUM.unit == "words"


def test_the_table_cannot_be_changed_by_a_caller() -> None:
    with pytest.raises(TypeError):
        limits.MINIMUM_BY_LANGUAGE["ja"] = limits.DEFAULT_MINIMUM  # type: ignore[index]


# --- The counts, held to the same cases as the browser -------------------


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=_case_id)
def test_the_shared_cases(case: dict[str, Any]) -> None:
    check = limits.check_minimum(case["text"], case["language"])
    assert (check.unit, check.count, check.met) == (case["unit"], case["count"], case["meets"])
    assert check.minimum == limits.minimum_rule(case["language"]).minimum
    assert limits.meets_minimum(case["text"], case["language"]) is case["meets"]


# --- Boundaries, for every language, derived from the table --------------


@pytest.mark.parametrize("language", [*limits.MINIMUM_BY_LANGUAGE, UNLISTED])
def test_each_language_accepts_its_minimum_and_refuses_one_unit_below(language: str) -> None:
    rule = limits.minimum_rule(language)
    sample = SAMPLES[rule.unit]
    assert limits.meets_minimum(sample(rule.minimum), language), (
        f"{language}: exactly {rule.minimum} {rule.unit} is an attempt"
    )
    assert not limits.meets_minimum(sample(rule.minimum - 1), language), (
        f"{language}: one {rule.unit} below the minimum is not"
    )


@pytest.mark.parametrize("language", [*limits.MINIMUM_BY_LANGUAGE, UNLISTED])
@pytest.mark.parametrize("text", NOT_AN_ATTEMPT, ids=repr)
def test_text_that_is_not_writing_is_refused_in_every_language(language: str, text: str) -> None:
    assert not limits.meets_minimum(text, language)
    assert limits.check_minimum(text, language).count == 0


def test_chinese_learning_a_five_character_sentence_is_not_refused() -> None:
    """The report: an HSK 1 sentence is five characters and was refused."""
    assert len("我是学生。") < 10
    assert limits.meets_minimum("我是学生。", "zh")


def test_english_two_word_sentences_are_not_refused() -> None:
    assert len("Hi Bob.") < 10
    assert limits.meets_minimum("Hi Bob.", "en")


def test_the_check_is_pure_and_takes_the_language_it_is_given() -> None:
    """No ambient request language: the caller says which language it means."""
    from writing_coach.core.request_context import LANGUAGE_CODE_CTX

    token = LANGUAGE_CODE_CTX.set("zh")
    try:
        assert limits.check_minimum("Hi Bob.", "en").met
        assert not limits.check_minimum("好", "zh").met
    finally:
        LANGUAGE_CODE_CTX.reset(token)


def test_a_refusal_measurement_carries_no_part_of_the_text() -> None:
    check = limits.check_minimum("Xyzzyplugh", "en")
    context = check.as_context()
    assert context == {"limit": "minimum", "language": "en", "unit": "words", "minimum": 2, "count": 1}
    assert "Xyzzyplugh" not in json.dumps(context)
    assert "2" in limits.minimum_message(check)


# --- The routes -----------------------------------------------------------

@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Any:
    """A client whose review and improvement are counted, and whose store is its own.

    Nothing here grades anything: what is under test is whether the request
    reaches review at all, which is what the minimum decides.
    """
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    client = TestClient(app_module.app)
    client.__enter__()
    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)

    reviewed: list[str] = []
    improved: list[str] = []

    def fake_review(payload: Any, identity: Any, previous: Any, series_id: Any, revision_no: Any) -> dict[str, Any]:
        reviewed.append(payload.text)
        return {"id": 1, "reviewed": True}

    def fake_improve(payload: Any) -> dict[str, Any]:
        improved.append(payload.text)
        return {"corrected_text": payload.text}

    monkeypatch.setattr(app_module, "_run_review", fake_review)
    monkeypatch.setattr(app_module, "improve_with_ai", fake_improve)
    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"}
    )
    app_module._review_in_flight.clear()

    def choose(language: str) -> None:
        # The way the writing evaluation tests choose a language: the route asks
        # `active_grammar_language_code()`. Selecting it through the session
        # would also build that language's per-learner database, which is not
        # what is under test.
        monkeypatch.setattr(app_module, "active_grammar_language_code", lambda: language)

    try:
        yield SimpleNamespace(client=client, reviewed=reviewed, improved=improved, choose=choose)
    finally:
        client.__exit__(None, None, None)


def _evaluate(api: Any, text: str, language: str):
    return api.client.post(
        "/api/evaluate", json={"prompt": "", "text": text, "learning_language": language}
    )


def _improve(api: Any, text: str):
    return api.client.post("/api/improve", json={"text": text})


def _refusal(answer: Any, *, language: str, unit: str, count: int) -> None:
    assert answer.status_code == 422, answer.text
    detail = answer.json()["detail"]
    assert detail["category"] == "writing_too_short"
    assert detail["retryable"] is False
    assert detail["context"] == {
        "limit": "minimum",
        "language": language,
        "unit": unit,
        "minimum": 2,
        "count": count,
    }
    assert detail["message"].strip()


def test_the_request_models_are_not_where_the_floor_lives() -> None:
    """The floor depends on the learning language, which a model field cannot see."""
    assert app_module.EssayIn(text="好").text == "好"
    assert app_module.ImproveIn(text="好").text == "好"


@pytest.mark.parametrize("text", ["我是学生。", "你好。", "你好", "好 好"])
def test_evaluate_reviews_a_short_chinese_attempt(api: Any, text: str) -> None:
    api.choose("zh")
    answer = _evaluate(api, text, "zh")
    assert answer.status_code == 200, answer.text
    assert api.reviewed == [text]


@pytest.mark.parametrize(
    ("text", "count"),
    [("好", 1), ("好。", 1), ("", 0), ("          ", 0), ("。。。。。。。。。。。", 0), ("Hello world, how are you", 0)],
)
def test_evaluate_refuses_chinese_that_is_not_an_attempt(api: Any, text: str, count: int) -> None:
    api.choose("zh")
    answer = _evaluate(api, text, "zh")
    _refusal(answer, language="zh", unit="han", count=count)
    assert api.reviewed == [], "nothing is spent on it"


@pytest.mark.parametrize("text", ["Hi Bob.", "I agree.", "Hello there"])
def test_evaluate_reviews_a_short_english_attempt(api: Any, text: str) -> None:
    answer = _evaluate(api, text, "en")
    assert answer.status_code == 200, answer.text
    assert api.reviewed == [text]


@pytest.mark.parametrize(
    ("text", "count"),
    [("Xyzzyplugh", 1), ("Xyzzyplugh.", 1), ("", 0), ("          ", 0), ("...........", 0), ("😀😀😀😀😀😀😀😀😀😀", 0)],
)
def test_evaluate_refuses_english_that_is_not_an_attempt(api: Any, text: str, count: int) -> None:
    answer = _evaluate(api, text, "en")
    _refusal(answer, language="en", unit="words", count=count)
    assert api.reviewed == [], "nothing is spent on it"
    if "Xyzzy" in text:
        assert "Xyzzy" not in answer.text, "a refusal is a measurement, not a copy of the writing"


def test_a_refusal_names_the_unit_the_learner_writes_in(api: Any) -> None:
    api.choose("zh")
    zh = _evaluate(api, "好", "zh").json()["detail"]["message"]
    api.choose("en")
    en = _evaluate(api, "Hello", "en").json()["detail"]["message"]
    assert "character" in zh.lower()
    assert "word" in en.lower()


@pytest.mark.parametrize("text", ["我是学生。", "你好。"])
def test_improve_accepts_a_short_chinese_attempt(api: Any, text: str) -> None:
    api.choose("zh")
    answer = _improve(api, text)
    assert answer.status_code == 200, answer.text
    assert api.improved == [text]


@pytest.mark.parametrize("text", ["好", "          ", "。。。。。。。。。。。"])
def test_improve_refuses_chinese_that_is_not_an_attempt(api: Any, text: str) -> None:
    api.choose("zh")
    answer = _improve(api, text)
    assert answer.status_code == 422
    assert answer.json()["detail"]["category"] == "writing_too_short"
    assert api.improved == []


def test_improve_accepts_two_english_words_and_refuses_one(api: Any) -> None:
    assert _improve(api, "Hi Bob.").status_code == 200
    assert api.improved == ["Hi Bob."]
    refused = _improve(api, "Hello")
    assert refused.status_code == 422
    assert refused.json()["detail"]["category"] == "writing_too_short"
    assert api.improved == ["Hi Bob."]


def test_the_ceilings_are_unchanged() -> None:
    assert (limits.MAX_CHARACTERS, limits.MAX_BYTES, limits.MAX_LINES) == (12_000, 60_000, 1_000)


@pytest.mark.parametrize(("language", "text"), [("en", "x"), ("zh", "好")])
def test_the_ceiling_is_asked_before_the_minimum(api: Any, language: str, text: str) -> None:
    """A text that is both too short and too big is refused for its size, first.

    The character bound is the request model's and answers before any route
    code runs, so it cannot say which of the two route guards goes first. The
    lines bound is only the route's `_guard_writing_size`: one unit of writing
    followed by a thousand line breaks is well under the minimum and one line
    over the ceiling. If the minimum were asked first this would be a 422
    `writing_too_short` - a learner told to write more about a file they pasted
    by mistake.
    """
    api.choose(language)
    too_many_lines = text + "\n" * limits.MAX_LINES
    assert not limits.check_minimum(too_many_lines, language).met, "below the minimum"
    assert limits.measure_writing(too_many_lines).limit_exceeded == "lines", "over the ceiling"

    answer = _evaluate(api, too_many_lines, language)

    assert answer.status_code == 413, answer.text
    detail = answer.json()["detail"]
    assert detail["category"] == "writing_too_large"
    assert detail["context"]["limit"] == "lines"
    assert api.reviewed == [], "nothing is spent on it"


def test_the_request_models_own_character_bound_still_answers_first(api: Any) -> None:
    """The bound the model states is the model's to enforce, before the route."""
    answer = _evaluate(api, "a" * (limits.MAX_CHARACTERS + 1), "en")
    assert answer.status_code == 422
    assert "writing_too_short" not in answer.text
    assert api.reviewed == []
