from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from writing_coach.ai.base import AIResult
from writing_coach.languages.chinese.profile import (
    ERROR_CATEGORIES as CHINESE_ERROR_CATEGORIES,
    PROFILE as CHINESE_PROFILE,
    RUBRIC_WEIGHTS as CHINESE_RUBRIC_WEIGHTS,
    SYSTEM_PROMPT as CHINESE_SYSTEM_PROMPT,
    score_to_level as chinese_score_to_level,
)
from writing_coach.languages.english.profile import (
    ERROR_CATEGORIES as ENGLISH_ERROR_CATEGORIES,
    PROFILE as ENGLISH_PROFILE,
    RUBRIC_WEIGHTS as ENGLISH_RUBRIC_WEIGHTS,
    SYSTEM_PROMPT as ENGLISH_SYSTEM_PROMPT,
    score_to_level as english_score_to_level,
)
from writing_coach.writing_evaluator_contract import (
    ERROR_FIELDS,
    SHARED_RESULT_FIELDS,
    STRENGTH_EVIDENCE_FIELDS,
    WritingEvaluatorContractInvalid,
    build_writing_evaluator_request,
    build_writing_evaluator_schema,
    validate_writing_evaluator_policy,
)


RUBRIC_KEYS = (
    "grammar",
    "vocabulary",
    "coherence",
    "task_achievement",
    "naturalness",
)


def _english_schema() -> dict[str, Any]:
    return build_writing_evaluator_schema(
        rubric_weights=ENGLISH_RUBRIC_WEIGHTS,
        allowed_levels=ENGLISH_PROFILE.levels,
        score_to_level=english_score_to_level,
        error_categories=ENGLISH_ERROR_CATEGORIES,
    )


def _chinese_schema() -> dict[str, Any]:
    return build_writing_evaluator_schema(
        rubric_weights=CHINESE_RUBRIC_WEIGHTS,
        allowed_levels=CHINESE_PROFILE.levels,
        score_to_level=chinese_score_to_level,
        error_categories=CHINESE_ERROR_CATEGORIES,
    )


def test_english_and_chinese_schemas_contain_every_active_rubric_key() -> None:
    english = _english_schema()
    chinese = _chinese_schema()

    assert tuple(ENGLISH_RUBRIC_WEIGHTS) == RUBRIC_KEYS
    assert tuple(CHINESE_RUBRIC_WEIGHTS) == RUBRIC_KEYS
    assert set(RUBRIC_KEYS) <= set(english["properties"])
    assert set(RUBRIC_KEYS) <= set(chinese["properties"])
    for schema in (english, chinese):
        assert set(schema["properties"]) - set(SHARED_RESULT_FIELDS) == set(RUBRIC_KEYS)
        for key in RUBRIC_KEYS:
            assert schema["properties"][key] == {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
            }


def test_en_zh_shared_result_and_strength_evidence_structure_are_identical() -> None:
    english = _english_schema()
    chinese = _chinese_schema()

    assert english["required"] == chinese["required"] == [*RUBRIC_KEYS, *SHARED_RESULT_FIELDS]
    english_strength = english["properties"]["strength_evidence"]
    chinese_strength = chinese["properties"]["strength_evidence"]
    assert english_strength == chinese_strength
    assert english_strength["items"]["required"] == list(STRENGTH_EVIDENCE_FIELDS)
    assert english_strength["items"]["properties"]["category"]["enum"] == list(RUBRIC_KEYS)


def test_schema_requires_nonempty_actionable_feedback_fields() -> None:
    schema = _english_schema()
    strength = schema["properties"]["strength_evidence"]["items"]["properties"]
    error = schema["properties"]["errors"]["items"]["properties"]

    for field in ("fragment", "explanation_vi"):
        assert strength[field]["minLength"] == 1
    for field in ("fragment", "explanation_vi", "suggestion", "mini_rule_vi"):
        assert error[field]["minLength"] == 1


def test_en_zh_error_structure_differs_only_by_linguistic_category_enum() -> None:
    english = deepcopy(_english_schema()["properties"]["errors"])
    chinese = deepcopy(_chinese_schema()["properties"]["errors"])

    assert english["items"]["required"] == chinese["items"]["required"] == list(ERROR_FIELDS)
    assert english["items"]["properties"]["category"].pop("enum") == list(ENGLISH_ERROR_CATEGORIES)
    assert chinese["items"]["properties"]["category"].pop("enum") == list(CHINESE_ERROR_CATEGORIES)
    assert english == chinese


def test_current_rubric_weights_are_unique_positive_numeric_and_total_one() -> None:
    for weights, levels, mapper, categories in (
        (ENGLISH_RUBRIC_WEIGHTS, ENGLISH_PROFILE.levels, english_score_to_level, ENGLISH_ERROR_CATEGORIES),
        (CHINESE_RUBRIC_WEIGHTS, CHINESE_PROFILE.levels, chinese_score_to_level, CHINESE_ERROR_CATEGORIES),
    ):
        assert len(weights) == len(set(weights))
        assert sum(weights.values()) == pytest.approx(1.0)
        validate_writing_evaluator_policy(
            rubric_weights=weights,
            allowed_levels=levels,
            score_to_level=mapper,
            error_categories=categories,
        )


@pytest.mark.parametrize(
    "weights, message",
    (
        ({"grammar": "1.0"}, "must be numeric"),
        ({"grammar": 0.0, "vocabulary": 1.0}, "must be positive"),
        ({"grammar": 0.7, "vocabulary": 0.4}, "must total 1.0"),
    ),
)
def test_invalid_synthetic_weight_sets_fail(weights: dict[str, Any], message: str) -> None:
    with pytest.raises(WritingEvaluatorContractInvalid, match=message):
        validate_writing_evaluator_policy(
            rubric_weights=weights,
            allowed_levels=("L1",),
            score_to_level=lambda score: "L1",
            error_categories=("other",),
        )


def test_english_score_boundaries_return_declared_levels() -> None:
    cases = ((0, "A1"), (29.9, "A1"), (30, "A2"), (44.9, "A2"), (45, "B1"),
             (59.9, "B1"), (60, "B2"), (74.9, "B2"), (75, "C1"),
             (89.9, "C1"), (90, "C2"), (100, "C2"))
    assert all(english_score_to_level(score) == expected for score, expected in cases)
    assert all(english_score_to_level(score) in ENGLISH_PROFILE.levels for score, _ in cases)


def test_chinese_score_boundaries_return_declared_levels() -> None:
    cases = ((0, "HSK1"), (24.9, "HSK1"), (25, "HSK2"), (39.9, "HSK2"),
             (40, "HSK3"), (54.9, "HSK3"), (55, "HSK4"), (67.9, "HSK4"),
             (68, "HSK5"), (79.9, "HSK5"), (80, "HSK6"), (89.9, "HSK6"),
             (90, "HSK7-9"), (100, "HSK7-9"))
    assert all(chinese_score_to_level(score) == expected for score, expected in cases)
    assert all(chinese_score_to_level(score) in CHINESE_PROFILE.levels for score, _ in cases)


def test_request_contract_is_explicit_about_evidence_and_target_level_semantics() -> None:
    request = build_writing_evaluator_request(
        language_name="English",
        target_level="B2",
        task_prompt="Describe a useful habit.",
        learner_text="Reading every day help me focus.",
        free_writing_context="Free English writing.",
    )

    assert "ORIGINAL learner text" in request
    assert "Never invent learner evidence" in request
    assert "must occur literally in LEARNER_TEXT" in request
    assert "genuine strength visible in its exact fragment" in request
    assert "genuine problem visible in its exact fragment" in request
    assert "suggestion must meaningfully differ" in request
    assert "If uncertain whether something is wrong, omit it" in request
    assert "Fewer high-confidence findings" in request
    assert "confidence >= 0.75" in request
    assert "TARGET LEVEL (LEARNING CONTEXT ONLY)" in request
    assert "actual demonstrated performance" in request
    assert "Do not force the proficiency estimate upward" in request
    assert "inflate scores" in request and "deflate scores" in request


def test_target_free_guided_request_keeps_length_out_of_level_calibration() -> None:
    request = build_writing_evaluator_request(
        language_name="English",
        target_level=None,
        task_prompt="Describe a place that changed how you think.",
        learner_text="The library near my home changed my habits.",
        free_writing_context="Free English writing.",
        writing_mode="guided",
        writing_context={"topic_id": "places", "length_id": "short"},
    )

    assert "SUBMISSION MODE: guided" in request
    assert "REQUESTED LENGTH (INVITATION ONLY): short" in request
    assert "must not affect scores or the demonstrated band" in request
    assert "TASK ACHIEVEMENT: applicable" in request
    assert "TARGET LEVEL" not in request
    assert "Infer only the band demonstrated by this sample" in request


def test_journal_request_has_no_task_adherence_or_prompt_penalty() -> None:
    request = build_writing_evaluator_request(
        language_name="Chinese",
        target_level=None,
        task_prompt="",
        learner_text="今天我和朋友一起吃饭。",
        free_writing_context="Reflective journal entry.",
        writing_mode="journal",
        writing_context={"journal_context": "A personal reflection"},
    )

    assert "SUBMISSION MODE: journal" in request
    assert "TASK ACHIEVEMENT: not applicable" in request
    assert "Do not score prompt adherence" in request
    assert "<WRITING_TASK>" not in request
    assert "TARGET LEVEL" not in request


def test_journal_schema_omits_task_score_and_allows_insufficient_band() -> None:
    schema = build_writing_evaluator_schema(
        rubric_weights=ENGLISH_RUBRIC_WEIGHTS,
        allowed_levels=ENGLISH_PROFILE.levels,
        score_to_level=english_score_to_level,
        error_categories=ENGLISH_ERROR_CATEGORIES,
        writing_mode="journal",
    )

    assert "task_achievement" not in schema["properties"]
    assert "task_achievement" not in schema["required"]
    assert schema["properties"]["band_status"]["enum"] == ["estimated", "insufficient_evidence"]
    assert "" in schema["properties"]["cefr_estimate"]["enum"]
    assert "band_status" in schema["required"]


@pytest.mark.parametrize(
    "language, target, task, learner, free_context, expected_task",
    (
        ("English", "B2", "", "I write every day.", "Free English writing.", "Free English writing."),
        ("English", "C1", "Explain remote work.", "Remote work is useful.", "Free English writing.", "Explain remote work."),
        ("Chinese", "HSK4", "", "我每天写中文。", "Free Chinese writing.", "Free Chinese writing."),
        ("Chinese", "HSK5", "描述一次旅行。", "我去年去了北京。", "Free Chinese writing.", "描述一次旅行。"),
    ),
)
def test_small_en_zh_request_fixture_set(
    language: str,
    target: str,
    task: str,
    learner: str,
    free_context: str,
    expected_task: str,
) -> None:
    request = build_writing_evaluator_request(
        language_name=language,
        target_level=target,
        task_prompt=task,
        learner_text=learner,
        free_writing_context=free_context,
    )
    assert f"TARGET LANGUAGE: {language}" in request
    assert f"TARGET LEVEL (LEARNING CONTEXT ONLY): {target}" in request
    assert f"<WRITING_TASK>\n{expected_task}\n</WRITING_TASK>" in request
    assert f"<LEARNER_TEXT>\n{learner}\n</LEARNER_TEXT>" in request


def test_language_specific_error_categories_and_explanation_policies_are_preserved() -> None:
    assert {"article", "tense", "agreement", "sentence_structure"} <= set(ENGLISH_ERROR_CATEGORIES)
    assert {"word_order", "particle", "aspect", "measure_word", "ba_sentence", "bei_sentence"} <= set(
        CHINESE_ERROR_CATEGORIES
    )
    assert "other" in ENGLISH_ERROR_CATEGORIES
    assert "other" in CHINESE_ERROR_CATEGORIES
    assert "Vietnamese using the Latin alphabet" in ENGLISH_SYSTEM_PROMPT
    assert "primarily in Vietnamese" in CHINESE_SYSTEM_PROMPT
    assert "INTERNAL learning estimate" in CHINESE_SYSTEM_PROMPT
    assert "not an official HSK exam score" in CHINESE_SYSTEM_PROMPT


def test_app_uses_shared_builders_once_and_preserves_normalizer_and_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app

    calls = {"request": 0, "schema": 0, "generation": 0, "normalizer": 0}
    request_builder = app.build_writing_evaluator_request
    schema_builder = app.build_writing_evaluator_schema
    normalizer = app.validate_result
    captured: dict[str, Any] = {}

    def request_spy(**kwargs: Any) -> str:
        calls["request"] += 1
        captured["request_inputs"] = kwargs
        return request_builder(**kwargs)

    def schema_spy(**kwargs: Any) -> dict[str, Any]:
        calls["schema"] += 1
        captured["schema_inputs"] = kwargs
        return schema_builder(**kwargs)

    def generation_spy(**kwargs: Any) -> AIResult:
        calls["generation"] += 1
        captured["generation"] = kwargs
        return AIResult(
            data={
                **{key: 70 for key in RUBRIC_KEYS},
                "cefr_estimate": "B2",
                "summary_vi": "Tom tat.",
                "strengths_vi": [],
                "strength_evidence": [],
                "priorities_vi": [],
                "errors": [],
            },
            provider="test-provider",
            model="test-model",
            runtime={"mode": "test"},
        )

    def normalizer_spy(raw: dict[str, Any]) -> dict[str, Any]:
        calls["normalizer"] += 1
        return normalizer(raw)

    monkeypatch.setattr(app, "build_writing_evaluator_request", request_spy)
    monkeypatch.setattr(app, "build_writing_evaluator_schema", schema_spy)
    monkeypatch.setattr(app, "generate_structured", generation_spy)
    monkeypatch.setattr(app, "validate_result", normalizer_spy)
    monkeypatch.setattr(app, "active_profile", lambda: SimpleNamespace(name="English"))
    monkeypatch.setattr(app, "active_levels", lambda: ENGLISH_PROFILE.levels)
    monkeypatch.setattr(app, "active_rubric_weights", lambda: ENGLISH_RUBRIC_WEIGHTS)
    monkeypatch.setattr(app, "active_error_categories", lambda: ENGLISH_ERROR_CATEGORIES)
    monkeypatch.setattr(app, "active_score_to_level", english_score_to_level)
    monkeypatch.setattr(app, "active_system_prompt", lambda: ENGLISH_SYSTEM_PROMPT)
    monkeypatch.setattr(app, "is_chinese", lambda: False)

    result = app.evaluate_with_ai(
        app.EssayIn(text="I write a short essay every day.", prompt="Describe a useful habit.", target_cefr="B2")
    )

    assert calls == {"request": 1, "schema": 1, "generation": 1, "normalizer": 1}
    assert captured["generation"]["capability_key"] == "writing_evaluator"
    assert captured["generation"]["temperature"] == 0.0
    assert captured["generation"]["seed"] == 42
    assert captured["generation"]["max_output_tokens"] == 2200
    assert captured["generation"]["schema"] == _english_schema()
    assert [message["role"] for message in captured["generation"]["messages"]] == ["system", "user"]
    assert "<LEARNER_TEXT>" in captured["generation"]["messages"][1]["content"]
    assert set(result) >= {
        *RUBRIC_KEYS,
        *SHARED_RESULT_FIELDS,
        "schema_version",
        "text_hash",
        "summary",
        "dimensions",
        "issues",
        "strengths",
        "next_actions",
        "_runtime",
        "_ai_provider",
        "_ai_model",
    }
    assert result["_ai_provider"] == "test-provider"
