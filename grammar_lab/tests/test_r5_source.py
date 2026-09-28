from __future__ import annotations

import json
from pathlib import Path

import pytest

from grammar_lab.pipeline.r5_source import R5SourceError, load_r5, r5_source_text


def write_fake_r5(root: Path) -> Path:
    """Minimal R5 files in the app's layout: languages/english/grammar_{curriculum,knowledge}.json."""
    lang_dir = root / "english"
    lang_dir.mkdir(parents=True)
    curriculum = [
        {"id": "a1-alpha", "kind": "lesson", "level": "A1", "title": "Alpha", "content_version": 2,
         "objective_vi": "Mục tiêu.", "scope": ["Scope."], "contrasts": [], "restrictions": [], "common_traps": ["Bẫy."]},
        {"id": "a1-review-1", "kind": "review", "level": "A1", "title": "Review", "content_version": 2},
    ]
    knowledge = [
        {"id": "a1-alpha", "kind": "lesson", "content_version": 2, "title": "Alpha",
         "quick_reference": {"summary_vi": "Tóm tắt."},
         "lesson": {"explanation_vi": "Giải thích.", "rules": ["Rule."], "contrasts": [], "exceptions": [],
                    "examples": [{"target": "He goes to school.", "meaning_vi": "Anh ấy đi học."}],
                    "mistakes": [{"incorrect": "He go.", "correct": "He goes.", "why": "-s"}],
                    "guided_practice": [], "production_task_vi": "", "writing_tip_vi": ""}},
    ]
    (lang_dir / "grammar_curriculum.json").write_text(json.dumps(curriculum), encoding="utf-8")
    (lang_dir / "grammar_knowledge.json").write_text(json.dumps(knowledge), encoding="utf-8")
    return root


def test_load_r5_merges_curriculum_and_knowledge_for_lessons_only(tmp_path: Path) -> None:
    records = load_r5("en", write_fake_r5(tmp_path))
    assert set(records) == {"a1-alpha"}  # review/checkpoint items are practice sessions, not points
    record = records["a1-alpha"]
    assert record["level"] == "A1"
    assert record["content_version"] == 2
    assert record["summary_vi"] == "Tóm tắt."
    assert record["examples"][0]["target"] == "He goes to school."


def test_r5_source_text_carries_the_lesson_content_the_model_restructures(tmp_path: Path) -> None:
    records = load_r5("en", write_fake_r5(tmp_path))
    text = r5_source_text([records["a1-alpha"]])
    for expected in ("a1-alpha", "Giải thích.", "He goes to school.", "He go.", "Bẫy."):
        assert expected in text


def test_missing_r5_files_are_an_explicit_error(tmp_path: Path) -> None:
    with pytest.raises(R5SourceError, match="grammar_curriculum.json"):
        load_r5("en", tmp_path)
