"""D-124: a sense is localized per support language by registered data/offline sources."""

from __future__ import annotations

from writing_coach import vocabulary_localization as loc
from writing_coach.vocabulary_localization import (
    ChineseDictionarySource,
    PivotTranslationSource,
    checked_gloss,
    enabled_pivot_pairs,
    localize_records,
)
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)


def _records(csv: str, language: str, meaning_language: str = "") -> list[dict]:
    source = parse_vocabulary_source("list.csv", csv.encode("utf-8"))
    return normalize_vocabulary_rows(
        source,
        mapping=detect_vocabulary_mapping(source).mapping,
        language_code=language,
        meaning_language=meaning_language,
    )["records"]


class FakeMarian:
    """Stands in for the local service; records what it was asked, answers from a table."""

    def __init__(self, table: dict[str, str]) -> None:
        self.table = table
        self.calls: list[tuple[str, str, list[tuple[str, str]]]] = []

    def __call__(self, source, target, batch):
        self.calls.append((source, target, list(batch)))
        return {key: self.table[text] for key, text in batch if text in self.table}


def _pivot(fake: FakeMarian, pairs) -> PivotTranslationSource:
    return PivotTranslationSource(fake, engine="local_marian", model_version="opus-mt-v1", pairs=pairs)


def test_chinese_senses_gain_an_english_localization_from_cc_cedict() -> None:
    completed, report = localize_records(_records("word\n松树\n竹林\n", "zh"), "zh", [ChineseDictionarySource()])

    assert completed[0]["short_meanings"] == [{"language": "en", "text": "pine; pine tree", "origin": "dictionary"}]
    assert completed[0]["provenance"]["localizations"]["en"]["source"] == "cc-cedict"
    assert report == [{"language": "en", "from_list": 0, "added": {"cc-cedict": 2}, "rejected": 0, "missing": 0}]


def test_an_enabled_pivot_translates_the_dictionary_sense_never_the_bare_headword() -> None:
    fake = FakeMarian({"pine; pine tree": "cây thông", "bamboo forest": "rừng tre"})
    completed, report = localize_records(
        _records("word\n松树\n竹林\n", "zh"), "zh", [ChineseDictionarySource(), _pivot(fake, [("zh", "vi")])]
    )

    vi = [item for item in completed[0]["short_meanings"] if item["language"] == "vi"]
    assert vi == [{"language": "vi", "text": "cây thông", "origin": "pivot_translation"}]
    assert completed[0]["provenance"]["localizations"]["vi"]["source"] == "local_marian"
    asked = [text for _, target, batch in fake.calls if target == "vi" for _, text in batch]
    assert asked == ["pine; pine tree", "bamboo forest"]  # English senses, not 松树/竹林
    assert {row["language"]: row["added"] for row in report} == {"en": {"cc-cedict": 2}, "vi": {"local_marian": 2}}


def test_a_pair_that_is_not_enabled_is_never_sent() -> None:
    fake = FakeMarian({"pine; pine tree": "cây thông"})
    completed, report = localize_records(
        _records("word\n松树\n", "zh"), "zh", [ChineseDictionarySource(), _pivot(fake, [("en", "vi")])]
    )

    assert [item["language"] for item in completed[0]["short_meanings"]] == ["en"]
    assert fake.calls == []


def test_the_list_own_meaning_wins_and_an_unstated_language_is_left_alone() -> None:
    fake = FakeMarian({"pine": "cây thông", "pine; pine tree": "cây thông"})
    stated = _records("word,meaning\n松树,cây thông non\n", "zh", meaning_language="vi")
    completed, report = localize_records(stated, "zh", [ChineseDictionarySource(), _pivot(fake, [("zh", "vi")])])
    assert [item["text"] for item in completed[0]["short_meanings"] if item["language"] == "vi"] == ["cây thông non"]
    assert {row["language"]: row["from_list"] for row in report}["vi"] == 1

    unstated = _records("word,meaning\n松树,pine\n", "zh")
    completed, _ = localize_records(unstated, "zh", [ChineseDictionarySource()])
    assert [item["text"] for item in completed[0]["short_meanings"]] == ["pine"]


def test_invalid_machine_output_is_rejected_by_deterministic_checks() -> None:
    fake = FakeMarian({"pine; pine tree": "松树", "bamboo forest": ""})
    completed, report = localize_records(
        _records("word\n松树\n竹林\n", "zh"), "zh", [ChineseDictionarySource(), _pivot(fake, [("zh", "vi")])]
    )
    vi = next(row for row in report if row["language"] == "vi")
    assert vi["rejected"] == 2 and vi["missing"] == 2 and vi["added"] == {}
    assert checked_gloss("basket", "basket", "vi") == ""
    assert checked_gloss("篮子", "CL:個|个[ge4]", "en") == ""
    assert checked_gloss("篮子", "x" * 161, "vi") == ""
    assert checked_gloss("basket", "篮子", "zh") == "篮子"
    assert checked_gloss("篮子", "basket", "zh") == ""


def test_an_unavailable_offline_engine_leaves_the_gap_and_never_fails() -> None:
    def down(*_args):
        raise RuntimeError("local translator not provisioned")

    completed, report = localize_records(
        _records("word\nbasket\n", "en"), "en", [_pivot(down, [("en", "vi")])]  # type: ignore[arg-type]
    )
    assert completed[0]["short_meanings"] == []
    assert report == []


def test_an_english_headword_without_an_english_gloss_is_translated_as_itself() -> None:
    fake = FakeMarian({"basket": "cái giỏ"})
    completed, _ = localize_records(_records("word\nbasket\n", "en"), "en", [_pivot(fake, [("en", "vi")])])
    assert completed[0]["short_meanings"] == [{"language": "vi", "text": "cái giỏ", "origin": "pivot_translation"}]


def test_pivot_pairs_are_operator_configuration_and_default_off(monkeypatch) -> None:
    assert enabled_pivot_pairs({}) == ()
    assert enabled_pivot_pairs({"VOCABULARY_PIVOT_PAIRS": "zh:vi, en:vi, en:en, xx:zz"}) == (("zh", "vi"), ("en", "vi"))
    monkeypatch.delenv("VOCABULARY_PIVOT_PAIRS", raising=False)
    assert [source.method for source in loc.default_sources()] == ["dictionary"]


def test_localization_never_reaches_an_ai_capability(monkeypatch) -> None:
    from writing_coach.ai import platform as ai_platform

    def boom(*args, **kwargs):
        raise AssertionError("vocabulary localization must not call a model")

    monkeypatch.setattr(ai_platform, "generate_structured", boom)
    completed, _ = localize_records(_records("word\n市场\n", "zh"), "zh", loc.default_sources())
    assert completed[0]["short_meanings"][0]["text"].startswith("marketplace")
