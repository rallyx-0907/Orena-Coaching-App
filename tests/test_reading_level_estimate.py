"""D-199: the coverage-based automatic level estimate (reading-level/3).

Every gold label under tests/fixtures/level_gold is PROVISIONAL (author or VOA-tier judgement, none owner
approved), so the accuracy floors below guard against regression and collapse - they do not certify
accuracy. The reviewer override (D-196) is covered by test_reading_content_repository.py and is untouched:
the estimator never sees `reviewed_level`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from writing_coach import reading_level
from writing_coach.reading_processing import EN_LEVEL_BANDS, LEVEL_VERSION, LOW_CONFIDENCE, analyze_article

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "tests" / "fixtures" / "level_gold"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evaluation = _load_script("eval_reading_level")
builder = _load_script("build_reading_level_tables")


def _predictions(language: str) -> list[tuple[dict, str]]:
    if language == "zh":
        pytest.importorskip("jieba")
    rows = [i for i in evaluation.load_gold() if i["language"] == language]
    return [(i, analyze_article(i["text"], language).estimated_level) for i in rows]


# ---- the tables --------------------------------------------------------------

def test_the_committed_tables_are_valid_and_carry_their_licences():
    assert builder.validate_committed() == []
    octanove = json.loads(builder.OCTANOVE_OUT.read_text(encoding="utf-8"))
    cefrj = json.loads(builder.CEFRJ_OUT.read_text(encoding="utf-8"))
    assert "CC BY-SA 4.0" in octanove["licence"] and "ShareAlike" in octanove["licence"]
    assert "citation" in cefrj and "Tono" in cefrj["citation"]
    assert set(octanove["levels"]) == {"C1", "C2"} and set(cefrj["levels"]) == {"A1", "A2", "B1", "B2"}


def test_every_licence_is_named_in_the_third_party_notices():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for needle in ("level_words_cefrj.json", "level_words_octanove_c1c2.json", "level_words_hsk30.json", "ShareAlike"):
        assert needle in notices


# ---- exclusions and lookup ---------------------------------------------------

def test_names_acronyms_numbers_and_hyphen_halves_leave_the_signals():
    words = [w for w, _ in reading_level.en_tokens("Yesterday Johnson and NASA flew 10km in a nuclear-powered craft.")]
    assert words == ["yesterday", "and", "flew", "in", "a", "nuclear", "powered", "craft"]


def test_contractions_keep_their_stem_and_drop_one_and_two_letter_fragments():
    words = [w for w, _ in reading_level.en_tokens("It's what they're doing, isn't it? The boy's kite.")]
    assert words == ["what", "they", "doing", "isn", "it", "the", "boy", "kite"]


def test_inflected_and_irregular_forms_find_their_headword():
    rank = reading_level._en_rank
    assert rank("walked") == rank("walk") and rank("went") == rank("go") and rank("children") == rank("child")
    assert rank("studies") is not None and rank("running") is not None
    assert rank("zxqvw") is None


def test_an_unlisted_capitalised_word_opening_a_sentence_is_read_as_a_name():
    counts, _ = reading_level._rank_counts_en("Zxqvwton arrived. He sat down.")
    assert counts[6] == 0


# ---- the estimate ------------------------------------------------------------

def test_simple_text_is_a1_and_dense_academic_text_is_c2():
    simple = analyze_article("I am Mia. I am ten. I have a dog. The dog is big. I like my dog. " * 4, "en")
    dense = analyze_article(
        "The epistemic status of testimony remains contentious precisely because it resists assimilation to either "
        "perception or inference. Reductionists maintain that a hearer is warranted in accepting an assertion only "
        "insofar as she possesses independent, non-circular grounds for deeming the speaker reliable; anti-reductionists, "
        "conversely, contend that such a demand misconstrues the very practices through which competence is acquired.",
        "en",
    )
    assert simple.estimated_level == "A1" and dense.estimated_level in {"C1", "C2"}


def test_the_estimate_carries_a_version_confidence_and_evidence_without_the_text():
    analysis = analyze_article(
        (GOLD / "en" / next(p.name for p in (GOLD / "en").iterdir())).read_text(encoding="utf-8"), "en"
    )
    assert analysis.level_version == LEVEL_VERSION == "reading-level/3"
    assert 0.0 <= analysis.confidence <= 1.0
    evidence = analysis.evidence
    assert set(evidence["coverage"]) == set(EN_LEVEL_BANDS)
    assert list(evidence["coverage"].values()) == sorted(evidence["coverage"].values())
    assert len(evidence["top_above_band"]) <= 8 and evidence["scored_tokens"] > 0
    assert len(json.dumps(evidence)) < 1500  # a summary, never the article


def test_a_text_too_short_to_judge_is_capped_below_the_top_of_the_scale():
    dense = analyze_article("Notwithstanding preliminary determinations, epistemological considerations persist.", "en")
    assert dense.confidence < LOW_CONFIDENCE and dense.estimated_level != "C2"


# ---- calibration set and spread (the owner's acceptance) ---------------------

def test_gold_set_labels_are_all_provisional_and_none_claims_owner_approval():
    for name in ("voa_en.json", "samples_en.json", "samples_zh.json", "real_articles.json"):
        for entry in json.loads((GOLD / name).read_text(encoding="utf-8")):
            assert entry["status"] in {"PROVISIONAL", "UNLABELLED"}, entry["id"]


def test_english_levels_do_not_collapse_into_one_band():
    results = _predictions("en")
    used = {band for _, band in results}
    assert len(used) >= 5, used
    real = {band for item, band in results if item["id"].startswith("voa-") or item["id"] in {"nasa-news-release", "global-voices-calypso"}}
    assert len(real) >= 3, real
    nasa = next(band for item, band in results if item["id"] == "nasa-news-release")
    assert nasa in {"B2", "C1", "C2"} and nasa != "A1"


def test_chinese_levels_do_not_collapse_into_one_band():
    results = _predictions("zh")
    assert len({band for _, band in results}) >= 5
    by_id = {item["id"]: band for item, band in results}
    assert by_id["orena-zh-hsk1-a"] in {"HSK1", "HSK2"} and by_id["orena-zh-hsk6-a"] in {"HSK5", "HSK6"}
    assert by_id["orena-zh-hsk2-a"] != by_id["orena-zh-hsk6-a"]


@pytest.mark.parametrize(("language", "exact", "within1"), [("en", 0.65, 0.9), ("zh", 0.8, 0.9)])
def test_agreement_with_the_provisional_gold_labels_does_not_regress(language, exact, within1):
    if language == "zh":
        pytest.importorskip("jieba")
    items = evaluation.load_gold()
    result = evaluation.score(
        items, lambda i: evaluation.bands(i["language"]).index(analyze_article(i["text"], i["language"]).estimated_level)
    )[language]
    assert result["exact"] >= exact and result["within1"] >= within1, result


def test_en_zh_parity_each_language_stays_on_its_own_scale():
    pytest.importorskip("jieba")
    en = analyze_article("The cat sat on the mat. " * 40, "en")
    zh = analyze_article("今天天气很好，我们去公园散步。" * 40, "zh")
    assert en.estimated_level in EN_LEVEL_BANDS and zh.estimated_level.startswith("HSK")
    assert en.level_version == zh.level_version == LEVEL_VERSION
    assert set(zh.evidence["coverage"]) == {"HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"}
