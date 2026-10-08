from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

import pytest

from writing_coach.languages.chinese.profile import ERROR_CATEGORIES as CHINESE_ERROR_CATEGORIES
from writing_coach.languages.english.profile import ERROR_CATEGORIES as ENGLISH_ERROR_CATEGORIES
from writing_coach.writing_evaluation import normalize_writing_evaluation


RUBRIC_WEIGHTS = {"grammar": 0.6, "vocabulary": 0.4}
LEARNER_TEXT = "I has a dog."


def _en_level(score: float) -> str:
    return "B2" if score >= 60 else "A1"


def _zh_level(score: float) -> str:
    return "HSK4" if score >= 60 else "HSK1"


def _normalize(
    raw: dict[str, Any],
    *,
    allowed_levels: tuple[str, ...] = ("A1", "B2"),
    score_to_level: Callable[[float], str] = _en_level,
    error_categories: tuple[str, ...] = ENGLISH_ERROR_CATEGORIES,
    allow_cjk: bool = False,
    learner_text: str = LEARNER_TEXT,
    applicable_dimensions: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return normalize_writing_evaluation(
        raw,
        rubric_weights=RUBRIC_WEIGHTS,
        allowed_levels=allowed_levels,
        score_to_level=score_to_level,
        error_categories=error_categories,
        allow_cjk=allow_cjk,
        learner_text=learner_text,
        applicable_dimensions=applicable_dimensions,
    )


def _strength(**overrides: Any) -> dict[str, Any]:
    item = {
        "category": "grammar",
        "fragment": "I has a dog.",
        "explanation_vi": "Cau nay the hien y ro rang.",
        "confidence": 0.8,
    }
    item.update(overrides)
    return item


def _error(**overrides: Any) -> dict[str, Any]:
    item = {
        "category": "agreement",
        "fragment": "I has a dog.",
        "explanation_vi": "Dong tu can phu hop voi chu ngu.",
        "suggestion": "I have a dog.",
        "mini_rule_vi": "I di voi have.",
        "confidence": 0.8,
    }
    item.update(overrides)
    return item


def test_valid_scores_and_weighted_overall_are_preserved_deterministically() -> None:
    result = _normalize({"grammar": 80, "vocabulary": 50, "cefr_estimate": "B2"})

    assert result["grammar"] == 80.0
    assert result["vocabulary"] == 50.0
    assert result["cefr_estimate"] == "B2"
    assert result["grammar"] * 0.6 + result["vocabulary"] * 0.4 == 68.0


def test_numeric_strings_clamp_and_malformed_scores_normalize_safely() -> None:
    result = _normalize({"grammar": "100.06", "vocabulary": "not-a-number"})
    assert result["grammar"] == 100.0
    assert result["vocabulary"] == 0.0

    clamped = _normalize({"grammar": -2, "vocabulary": 150})
    assert clamped["grammar"] == 0.0
    assert clamped["vocabulary"] == 100.0

    malformed = _normalize({"grammar": True, "vocabulary": None})
    assert malformed["grammar"] == 0.0
    assert malformed["vocabulary"] == 0.0


def test_valid_and_invalid_english_levels_use_the_supplied_policy() -> None:
    assert _normalize({"grammar": 70, "vocabulary": 70, "cefr_estimate": "A1"})["cefr_estimate"] == "A1"
    assert _normalize({"grammar": 70, "vocabulary": 70, "cefr_estimate": "not-a-level"})["cefr_estimate"] == "B2"


def test_valid_and_invalid_chinese_levels_use_the_same_shared_implementation() -> None:
    options = {"allowed_levels": ("HSK1", "HSK4"), "score_to_level": _zh_level, "allow_cjk": True}
    assert _normalize({"grammar": 70, "vocabulary": 70, "cefr_estimate": "HSK1"}, **options)["cefr_estimate"] == "HSK1"
    assert _normalize({"grammar": 70, "vocabulary": 70, "cefr_estimate": "invalid"}, **options)["cefr_estimate"] == "HSK4"


def test_strength_evidence_requires_exact_fragment_category_and_confidence() -> None:
    accepted = _normalize({"strength_evidence": [_strength()]})
    assert accepted["strength_evidence"][0]["category"] == "grammar"
    assert accepted["strength_evidence"][0]["fragment"] == LEARNER_TEXT
    assert accepted["strength_evidence"][0]["span"] == {"start": 0, "end": len(LEARNER_TEXT)}

    rejected = _normalize(
        {
            "strength_evidence": [
                _strength(fragment="invented fragment"),
                _strength(confidence=0.74),
                _strength(confidence=0.749),
                _strength(category="unknown"),
                "not-an-object",
            ]
        }
    )
    assert rejected["strength_evidence"] == []


def test_learner_facing_text_fields_reject_non_string_provider_values() -> None:
    result = _normalize(
        {
            "summary_vi": {"message": "not learner copy"},
            "strengths_vi": [{"message": "not learner copy"}, None, 7],
            "priorities_vi": [{"message": "not learner copy"}, False],
            "strength_evidence": [_strength(explanation_vi={"message": "not learner copy"})],
            "errors": [_error(explanation_vi={"message": "not learner copy"}, mini_rule_vi=["not learner copy"])],
        }
    )

    assert result["summary_vi"] == ""
    assert result["strengths_vi"] == []
    assert result["priorities_vi"] == []
    assert result["strength_evidence"] == []
    assert result["errors"] == []
    assert "not learner copy" not in repr(result)


def test_feedback_items_require_actionable_explanation_and_rule() -> None:
    result = _normalize(
        {
            "strength_evidence": [
                _strength(explanation_vi=""),
                _strength(category="vocabulary", explanation_vi="   "),
            ],
            "errors": [
                _error(explanation_vi=""),
                _error(category="article", mini_rule_vi="   "),
            ],
        }
    )

    assert result["strength_evidence"] == []
    assert result["errors"] == []


def test_english_feedback_rejects_a_cjk_correction() -> None:
    result = _normalize({"errors": [_error(suggestion="我有一只狗。")]})

    assert result["errors"] == []


def test_strength_evidence_is_bounded() -> None:
    fragments = [f"good {index}" for index in range(8)]
    result = _normalize(
        {"strength_evidence": [_strength(fragment=fragment) for fragment in fragments]},
        learner_text=" ".join(fragments),
    )
    assert len(result["strength_evidence"]) == 6


def test_errors_require_a_meaningful_suggestion_and_confidence() -> None:
    accepted = _normalize({"errors": [_error()]})
    assert accepted["errors"][0]["category"] == "agreement"
    assert accepted["errors"][0]["span"] == {"start": 0, "end": len(LEARNER_TEXT)}
    assert accepted["errors"][0]["anchored"] is True
    assert accepted["issues"][0]["id"] == accepted["errors"][0]["id"]

    rejected = _normalize(
        {
            "errors": [
                _error(confidence=0.74),
                _error(confidence=0.749),
                _error(suggestion=""),
                _error(suggestion="  i   has a dog.  "),
                "not-an-object",
            ]
        }
    )
    assert rejected["errors"] == []


def test_a_finding_that_cannot_be_quoted_is_kept_but_cannot_be_pointed_at() -> None:
    """Exact evidence decides where a finding can be shown, not whether it exists.

    A fragment that is not verbatim in the learner's text used to be thrown
    away with the finding attached to it, so an evaluator that retyped its own
    quote - a straight apostrophe for a curly one - silently cost the learner a
    real correction. The span is what requires an exact occurrence: without one
    there is nothing honest to highlight, and the surface offers no way to look
    for it. The finding itself is still worth reading.
    """
    result = _normalize({"errors": [_error(fragment="invented fragment")]})
    (finding,) = result["errors"]
    assert finding["fragment"] == "invented fragment"
    assert finding["anchored"] is False
    assert finding["span"] == {"start": 0, "end": 0}, "no span is claimed that cannot be shown"


def test_error_categories_follow_exact_active_language_taxonomy() -> None:
    english = _normalize(
        {
            "errors": [
                _error(category="article"),
                _error(category="word_order"),
                _error(category="unknown"),
                _error(category=""),
                _error(category=" article "),
                _error(category="other"),
                _error(category="Article"),
                _error(category=["article"]),
                {key: value for key, value in _error().items() if key != "category"},
            ]
        }
    )
    assert [item["category"] for item in english["errors"]] == ["article", "other"]

    chinese = _normalize(
        {"errors": [_error(category="word_order"), _error(category="article"), _error(category="other")]},
        error_categories=CHINESE_ERROR_CATEGORIES,
        allow_cjk=True,
    )
    assert [item["category"] for item in chinese["errors"]] == ["word_order", "other"]


def test_error_duplicates_collapse_by_exact_category_and_fragment_in_first_valid_order() -> None:
    first = _error(category="agreement", explanation_vi="first")
    result = _normalize(
        {
            "errors": [
                first,
                _error(category="agreement", explanation_vi="duplicate"),
                _error(category="article", explanation_vi="different category"),
            ]
        }
    )
    assert [(item["category"], item["fragment"], item["explanation_vi"]) for item in result["errors"]] == [
        ("agreement", LEARNER_TEXT, "first"),
        ("article", LEARNER_TEXT, "different category"),
    ]


def test_errors_are_prioritized_by_confidence_with_stable_ties() -> None:
    result = _normalize(
        {
            "errors": [
                _error(category="agreement", fragment="I has", confidence=0.8),
                _error(category="article", fragment="a dog", confidence=0.95),
                # `sentence_structure`, not `word_order`: the English profile's
                # ERROR_CATEGORIES allowlist drops anything it does not name, so an
                # invalid category here would test the allowlist, not the tie order.
                _error(category="sentence_structure", fragment="I has a dog.", confidence=0.95),
            ]
        },
        learner_text=LEARNER_TEXT,
    )

    assert [(item["category"], item["confidence"]) for item in result["errors"]] == [
        ("article", 0.95),
        ("sentence_structure", 0.95),
        ("agreement", 0.8),
    ]


def test_strength_duplicates_collapse_by_exact_category_and_fragment_in_first_valid_order() -> None:
    first = _strength(explanation_vi="first")
    result = _normalize(
        {
            "strength_evidence": [
                first,
                _strength(explanation_vi="duplicate"),
                _strength(category="vocabulary", explanation_vi="different category"),
            ]
        }
    )
    assert [(item["category"], item["fragment"], item["explanation_vi"]) for item in result["strength_evidence"]] == [
        ("grammar", LEARNER_TEXT, "first"),
        ("vocabulary", LEARNER_TEXT, "different category"),
    ]


def test_errors_are_bounded_to_schema_limit_and_confidence_is_clamped_and_rounded() -> None:
    fragments = [f"error {index}" for index in range(32)]
    items = [
        _error(fragment=fragment, suggestion=f"fix {index}", confidence=1.6)
        for index, fragment in enumerate(fragments)
    ]
    result = _normalize({"errors": items}, learner_text=" ".join(fragments))
    assert len(result["errors"]) == 20
    assert result["errors"][0]["confidence"] == 1.0


def test_english_language_safety_rejects_unexpected_cjk_learner_explanations() -> None:
    result = _normalize(
        {
            "summary_vi": "\u4e2d\u6587",
            "strengths_vi": ["\u4e2d\u6587"],
            "priorities_vi": ["\u4e2d\u6587"],
            "strength_evidence": [_strength(explanation_vi="\u4e2d\u6587")],
            "errors": [_error(explanation_vi="\u4e2d\u6587")],
        }
    )
    assert result["summary_vi"] == ""
    assert result["strengths_vi"] == []
    assert result["priorities_vi"] == []
    assert result["strength_evidence"] == []
    assert result["errors"] == []


def test_chinese_policy_allows_cjk_learner_facing_content() -> None:
    result = _normalize(
        {
            "summary_vi": "\u4e2d\u6587",
            "strengths_vi": ["\u4e2d\u6587"],
            "priorities_vi": ["\u4e2d\u6587"],
            "strength_evidence": [_strength(explanation_vi="\u4e2d\u6587")],
            "errors": [_error(explanation_vi="\u4e2d\u6587", mini_rule_vi="\u4e2d\u6587")],
        },
        allow_cjk=True,
    )
    assert result["summary_vi"] == "\u4e2d\u6587"
    assert result["strengths_vi"] == ["\u4e2d\u6587"]
    assert result["priorities_vi"] == ["\u4e2d\u6587"]
    assert len(result["strength_evidence"]) == 1
    assert len(result["errors"]) == 1


def test_support_language_script_policy_is_independent_from_target_language() -> None:
    result = normalize_writing_evaluation(
        {
            "grammar": 70,
            "vocabulary": 70,
            "summary_vi": "この文章は明確です。",
            "strengths_vi": ["この表現は自然です。"],
            "priorities_vi": ["次は時制を確認しましょう。"],
            "strength_evidence": [
                _strength(explanation_vi="この強みは本文に表れています。"),
            ],
            "errors": [
                _error(
                    explanation_vi="主語に合わせて動詞を変えます。",
                    mini_rule_vi="I には have を使います。",
                ),
            ],
        },
        rubric_weights=RUBRIC_WEIGHTS,
        allowed_levels=("A1", "B2"),
        score_to_level=_en_level,
        error_categories=ENGLISH_ERROR_CATEGORIES,
        allow_cjk=False,
        allow_explanation_cjk=True,
        learner_text=LEARNER_TEXT,
    )

    assert result["summary_vi"] == "この文章は明確です。"
    assert result["strengths_vi"] == ["この表現は自然です。"]
    assert result["errors"][0]["suggestion"] == "I have a dog."


def test_insufficient_evidence_has_no_band_but_keeps_grounded_feedback() -> None:
    result = _normalize(
        {
            "band_status": "insufficient_evidence",
            "cefr_estimate": "",
            "errors": [_error(fragment="I has", suggestion="I have")],
        },
        learner_text="I has a dog.",
    )

    assert result["band_status"] == "insufficient_evidence"
    assert result["cefr_estimate"] == ""
    assert result["issues"][0]["quote"] == "I has"


def test_journal_normalization_omits_task_achievement_dimension() -> None:
    result = _normalize(
        {"grammar": 70, "vocabulary": 68, "coherence": 72, "naturalness": 66},
        applicable_dimensions=("grammar", "vocabulary", "coherence", "naturalness"),
    )

    assert "task_achievement" not in result
    assert "task_achievement" not in result["dimensions"]


def test_canonical_writing_input_does_not_require_a_target() -> None:
    import app

    payload = app.EssayIn(
        text="I wrote enough words for the evaluator to inspect this sample.",
        writing_mode="journal",
        writing_context={"journal_context": "A personal reflection"},
    )

    assert payload.target_cefr is None
    assert payload.writing_mode == "journal"
    assert payload.writing_context.journal_context == "A personal reflection"


def test_response_shape_is_backward_compatible_and_excludes_internal_learner_text() -> None:
    result = _normalize({"__learner_text": "must not appear"})
    assert set(result) >= {
        "grammar",
        "vocabulary",
        "cefr_estimate",
        "summary_vi",
        "strengths_vi",
        "priorities_vi",
        "strength_evidence",
        "errors",
        "schema_version",
        "text_hash",
        "summary",
        "dimensions",
        "issues",
        "strengths",
        "next_actions",
    }
    assert "__learner_text" not in result


def test_app_validate_result_delegates_to_the_extracted_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import app

    expected = {"grammar": 1.0}
    captured: dict[str, Any] = {}

    def normalize(raw: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["raw"] = raw
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(app, "normalize_writing_evaluation", normalize)
    monkeypatch.setattr(app, "active_rubric_weights", lambda: {"grammar": 1.0})
    monkeypatch.setattr(app, "active_levels", lambda: ("A1",))
    monkeypatch.setattr(app, "active_score_to_level", lambda score: "A1")
    monkeypatch.setattr(app, "active_error_categories", lambda: ("agreement", "other"))
    monkeypatch.setattr(app, "is_chinese", lambda: False)

    raw = {"grammar": 1, "__learner_text": LEARNER_TEXT}
    assert app.validate_result(raw) is expected
    assert captured["raw"] is raw
    assert captured["learner_text"] == LEARNER_TEXT
    assert captured["allow_cjk"] is False
    assert captured["error_categories"] == ("agreement", "other")


def test_app_writing_evaluator_path_keeps_its_capability_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    import app
    from writing_coach.ai.base import AIResult

    captured: dict[str, Any] = {}

    def generate_structured(**kwargs: Any) -> AIResult:
        captured.update(kwargs)
        return AIResult(
            data={"grammar": 80, "vocabulary": 50, "cefr_estimate": "B2"},
            provider="test-provider",
            model="test-model",
            runtime={"mode": "test"},
        )

    monkeypatch.setattr(app, "generate_structured", generate_structured)
    result = app.evaluate_with_ai(app.EssayIn(text=LEARNER_TEXT, prompt="Test prompt"))

    assert captured["capability_key"] == "writing_evaluator"
    assert result["grammar"] == 80.0
    assert result["strength_evidence"] == []
    assert result["errors"] == []
    assert result["_ai_provider"] == "test-provider"


def test_invalid_provider_response_uses_the_same_explicit_demo_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import app
    from writing_coach.ai.base import AIProviderResponseInvalid

    def invalid_provider(_payload: Any) -> dict[str, Any]:
        raise AIProviderResponseInvalid("provider returned incomplete JSON")

    monkeypatch.setattr(app, "evaluate_with_ai", invalid_provider)
    monkeypatch.setattr(app, "ALLOW_FALLBACK", True)
    monkeypatch.setattr(app, "get_learner_profile", lambda: {"support_language": "en"})

    result, evaluator = app.evaluate(app.EssayIn(text=LEARNER_TEXT, prompt="Test prompt"))

    assert evaluator == "fallback-demo"
    assert result["schema_version"] == "writing-evaluation-v2"
    assert result["errors"][0]["fragment"] == "I has"
    assert "Kết nối AI Coach" not in result["priorities_vi"][0]
    # The degraded notice must say the evaluation is provisional. The priority
    # line carries the re-run cue; the "chưa tạo được" phrasing lives in the summary.
    assert "run again when AI Coach is available" in result["priorities_vi"][0]
    assert "could not produce a full evaluation" in result["summary_vi"]


@pytest.mark.parametrize(
    ("support_language", "support_label", "summary"),
    (
        ("en", "English", "The writing is clear."),
        ("ja", "Japanese", "この文章は明確です。"),
        ("zh", "Simplified Chinese", "这篇文章很清楚。"),
    ),
)
def test_writing_evaluator_uses_profile_support_language_for_prompt_and_output(
    monkeypatch: pytest.MonkeyPatch,
    support_language: str,
    support_label: str,
    summary: str,
) -> None:
    import app
    from writing_coach.ai.base import AIResult
    from writing_coach.languages.english.profile import (
        ERROR_CATEGORIES,
        PROFILE,
        RUBRIC_WEIGHTS,
        score_to_level,
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(app, "get_learner_profile", lambda: {"support_language": support_language})
    monkeypatch.setattr(app, "active_profile", lambda: PROFILE)
    monkeypatch.setattr(app, "active_levels", lambda: PROFILE.levels)
    monkeypatch.setattr(app, "active_rubric_weights", lambda: RUBRIC_WEIGHTS)
    monkeypatch.setattr(app, "active_score_to_level", score_to_level)
    monkeypatch.setattr(app, "active_error_categories", lambda: ERROR_CATEGORIES)
    monkeypatch.setattr(app, "active_system_prompt", lambda: "fixture system prompt")
    monkeypatch.setattr(app, "is_chinese", lambda: False)

    def generate_structured(**kwargs: Any) -> AIResult:
        captured.update(kwargs)
        return AIResult(
            data={
                **{key: 70 for key in RUBRIC_WEIGHTS},
                "cefr_estimate": "B2",
                "summary_vi": summary,
                "strengths_vi": [],
                "strength_evidence": [],
                "priorities_vi": [],
                "errors": [],
            },
            provider="fixture",
            model="test",
            runtime={},
        )

    monkeypatch.setattr(app, "generate_structured", generate_structured)
    result = app.evaluate_with_ai(
        app.EssayIn(
            text="I write every day.",
            prompt="Describe a useful habit.",
            target_cefr="B2",
        )
    )

    user_prompt = captured["messages"][1]["content"]
    assert f"SUPPORT LANGUAGE: {support_label}" in user_prompt
    assert result["summary_vi"] == summary


@pytest.mark.parametrize(
    (
        "language",
        "target_level",
        "learner_text",
        "error_category",
        "error_fragment",
        "error_suggestion",
        "strength_fragment",
        "grammar_id",
    ),
    [
        (
            "en",
            "B1",
            "I has a dog.",
            "agreement",
            "I has",
            "I have",
            "dog",
            "a1-agreement",
        ),
        (
            "zh",
            "HSK2",
            "\u6211\u6bcf\u5929\u90fd\u8ba4\u771f\u5b66\u4e60\u6c49\u8bed\u3002",
            "word_order",
            "\u5b66\u4e60\u6c49\u8bed",
            "\u6c49\u8bed\u5b66\u4e60",
            "\u6211\u6bcf\u5929",
            "hsk2-word-order",
        ),
    ],
)
def test_api_evaluate_end_to_end_preserves_en_zh_evidence_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    target_level: str,
    learner_text: str,
    error_category: str,
    error_fragment: str,
    error_suggestion: str,
    strength_fragment: str,
    grammar_id: str,
) -> None:
    """The Write response must carry the evidence that Review and Journey consume."""
    import app
    from writing_coach.ai.base import AIResult
    from writing_coach.languages.chinese.profile import (
        ERROR_CATEGORIES as ZH_CATEGORIES,
        PROFILE as ZH_PROFILE,
        RUBRIC_WEIGHTS as ZH_WEIGHTS,
        score_to_level as zh_score_to_level,
    )
    from writing_coach.languages.english.profile import (
        ERROR_CATEGORIES as EN_CATEGORIES,
        PROFILE as EN_PROFILE,
        RUBRIC_WEIGHTS as EN_WEIGHTS,
        score_to_level as en_score_to_level,
    )

    class FakeLearningRepository:
        def __init__(self) -> None:
            self.created: dict[str, Any] | None = None

        def create_essay(self, values: dict[str, Any]) -> dict[str, int]:
            self.created = values
            return {"id": 41, "series_id": 41, "revision_no": 1}

        def list_essays(self, limit: int = 200, *, ascending: bool = False) -> list[dict[str, Any]]:
            # Part of the repository protocol, and asked before every review so
            # an evaluation already earned for this exact request is reused
            # rather than bought again. Nothing is stored here, so this double
            # always answers "no such review yet" and the evaluator runs.
            return []

    repository = FakeLearningRepository()
    monkeypatch.setattr(app, "_learning_repository", repository)
    monkeypatch.setattr(app, "active_grammar_language_code", lambda: language)
    monkeypatch.setattr(app, "is_chinese", lambda: language == "zh")

    if language == "zh":
        profile, weights, levels, score_to_level, categories = (
            ZH_PROFILE,
            ZH_WEIGHTS,
            ZH_PROFILE.levels,
            zh_score_to_level,
            ZH_CATEGORIES,
        )
    else:
        profile, weights, levels, score_to_level, categories = (
            EN_PROFILE,
            EN_WEIGHTS,
            EN_PROFILE.levels,
            en_score_to_level,
            EN_CATEGORIES,
        )
    monkeypatch.setattr(app, "active_profile", lambda: profile)
    monkeypatch.setattr(app, "active_rubric_weights", lambda: weights)
    monkeypatch.setattr(app, "active_levels", lambda: levels)
    monkeypatch.setattr(app, "active_score_to_level", score_to_level)
    monkeypatch.setattr(app, "active_error_categories", lambda: categories)
    monkeypatch.setattr(app, "active_system_prompt", lambda: "fixture system prompt")
    monkeypatch.setattr(
        app,
        "active_grammar_knowledge_by_id",
        lambda: {
            grammar_id: {
                "title": "Subject verb agreement" if language == "en" else "Word order",
                "level": target_level,
                "quick_reference": {"lookup_tags": [error_category.replace("_", " ")]},
            }
        },
    )

    raw_result = {
        **{key: 70 for key in weights},
        "cefr_estimate": target_level,
        "summary_vi": "Bai viet co bang chung ro rang.",
        "strengths_vi": ["Nguoi hoc trinh bay y ro rang."],
        "strength_evidence": [
            {
                "category": "grammar",
                "fragment": strength_fragment,
                "explanation_vi": "Diem manh nay xuat hien ro trong cau.",
                "confidence": 0.9,
            }
        ],
        "priorities_vi": ["Sua mau loi nay trong lan viet tiep theo."],
        "errors": [
            {
                "category": error_category,
                "fragment": error_fragment,
                "explanation_vi": "Cau truc nay can duoc dieu chinh.",
                "suggestion": error_suggestion,
                "mini_rule_vi": "Chon cau truc phu hop voi ngu canh.",
                "confidence": 0.95,
            }
        ],
    }

    captured: dict[str, Any] = {}

    def generate_structured(**kwargs: Any) -> AIResult:
        captured.update(kwargs)
        return AIResult(
            data=raw_result,
            provider=f"fixture-{language}",
            model="v1",
            runtime={"mode": "fixture"},
        )

    monkeypatch.setattr(app, "generate_structured", generate_structured)
    response = app.api_evaluate(
        app.EssayIn(
            text=learner_text,
            prompt="Write one short practice response.",
            target_cefr=target_level,
            learning_language=language,
        )
    )

    assert captured["capability_key"] == "writing_evaluator"
    assert response["id"] == 41
    assert response["evaluator"] == f"fixture-{language}:v1"
    assert response["schema_version"] == "writing-evaluation-v2"
    assert response["errors"][0]["fragment"] == error_fragment
    assert response["issues"][0]["quote"] == error_fragment
    assert response["strength_evidence"][0]["fragment"] == strength_fragment
    assert response["grammar_links"][0]["grammar_id"] == grammar_id
    assert repository.created is not None
    assert repository.created["evaluator"] == response["evaluator"]
    assert json.loads(repository.created["errors_json"])[0]["fragment"] == error_fragment
    assert json.loads(repository.created["strength_evidence_json"])[0]["fragment"] == strength_fragment


def test_heuristic_fallback_keeps_high_confidence_feedback_and_v2_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    import app

    monkeypatch.setattr(app, "is_chinese", lambda: False)
    result = app.heuristic_fallback(app.EssayIn(text="I has a dog."))

    assert result["schema_version"] == "writing-evaluation-v2"
    assert result["errors"][0]["fragment"] == "I has"
    assert result["errors"][0]["suggestion"] == "I have"
    assert result["issues"][0]["span"] == {"start": 0, "end": 5}


@pytest.mark.parametrize(
    ("support_language", "expected_marker"),
    (("ja", "AI Coach が完全な評価を作成できなかった"), ("zh", "由于 AI Coach 尚未生成完整评估")),
)
def test_heuristic_fallback_uses_the_resolved_support_language(
    monkeypatch: pytest.MonkeyPatch,
    support_language: str,
    expected_marker: str,
) -> None:
    import app

    monkeypatch.setattr(app, "get_learner_profile", lambda: {"support_language": support_language})
    monkeypatch.setattr(app, "is_chinese", lambda: False)

    result = app.heuristic_fallback(app.EssayIn(text="I has a dog."))

    assert expected_marker in result["summary_vi"]


@pytest.mark.parametrize(
    ("provider_error", "status_code", "category", "retryable"),
    (
        ("unavailable", 503, "evaluation_unavailable", True),
        ("invalid-response", 502, "evaluation_provider_failure", False),
    ),
)
def test_provider_failures_use_canonical_learner_safe_evaluation_envelope(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: str,
    status_code: int,
    category: str,
    retryable: bool,
) -> None:
    import app
    from fastapi import HTTPException
    from writing_coach.ai.base import AIProviderError, AIProviderUnavailable

    exception_type = AIProviderUnavailable if provider_error == "unavailable" else AIProviderError

    def fail(_payload: Any) -> Any:
        raise exception_type(f"raw provider detail: {provider_error}")

    monkeypatch.setattr(app, "evaluate_with_ai", fail)
    monkeypatch.setattr(app, "ALLOW_FALLBACK", False)

    with pytest.raises(HTTPException) as raised:
        app.evaluate(app.EssayIn(text="I write a short sentence."))

    assert raised.value.status_code == status_code
    detail = raised.value.detail
    assert detail == {
        "category": category,
        "message": (
            "AI evaluation is temporarily unavailable. Please try again."
            if provider_error == "unavailable"
            else "AI evaluation could not produce a usable result."
        ),
        "retryable": retryable,
        "context": {},
    }
    # Assert the raw provider text does not leak. A bare `provider_error not in
    # message` check cannot work here: "unavailable" is legitimately part of the
    # canonical learner-facing copy, so it would fail on the truthful message.
    assert f"raw provider detail: {provider_error}" not in str(detail)
    assert "raw provider detail" not in str(detail)


def test_language_scope_mismatch_uses_canonical_evaluation_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app
    from fastapi import HTTPException

    monkeypatch.setattr(app, "active_grammar_language_code", lambda: "en")

    with pytest.raises(HTTPException) as raised:
        app.api_evaluate(
            app.EssayIn(
                text="I write a short sentence.",
                learning_language="zh",
            )
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "category": "language_scope_mismatch",
        "message": "Writing language does not match the selected learning language.",
        "retryable": False,
        "context": {"requested_language": "zh", "active_language": "en"},
    }
