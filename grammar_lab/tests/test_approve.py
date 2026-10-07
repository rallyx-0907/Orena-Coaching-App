"""Human approval gate for reviewed Grammar Lab points."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from grammar_lab.pipeline.approve import ApprovalError, approve_points
from grammar_lab.pipeline.content_store import load_point, save_point
from grammar_lab.pipeline.validate import LAB_ROOT, validate_lang


@pytest.fixture
def lab_copy(tmp_path: Path) -> Path:
    for name in ("content", "schema", "functions", "cast", "inventory"):
        shutil.copytree(LAB_ROOT / name, tmp_path / name)
    return tmp_path


def test_approve_clean_draft_records_human_review(lab_copy: Path) -> None:
    result = approve_points(
        "en",
        ["en.there_is_are"],
        reviewer="Thi",
        seconds=12.5,
        note="Two-pass external review complete",
        reviewed_at="2026-10-07T06:30:00Z",
        root=lab_copy,
    )

    assert result.approved == ["en.there_is_are"]
    assert result.already_approved == []
    point = load_point("en", "en.there_is_are", lab_copy)
    assert point is not None
    assert point["status"] == "approved"
    assert point["review"] == {
        "reviewer": "Thi",
        "reviewed_at": "2026-10-07T06:30:00Z",
        "seconds": 12.5,
        "note": "Two-pass external review complete",
    }
    assert validate_lang("en", lab_copy).ok


def test_approve_checks_rules_that_only_apply_after_status_becomes_approved(lab_copy: Path) -> None:
    point = load_point("en", "en.there_is_are", lab_copy)
    assert point is not None
    point["header"].pop("sub")
    save_point("en", point, lab_copy)
    # header.sub is optional for a draft, so the pre-approval corpus is still valid.
    assert validate_lang("en", lab_copy).ok

    with pytest.raises(ApprovalError) as caught:
        approve_points("en", [point["id"]], reviewer="Thi", root=lab_copy)

    assert any("header.sub_missing" in problem for problem in caught.value.problems)
    unchanged = load_point("en", point["id"], lab_copy)
    assert unchanged is not None
    assert unchanged["status"] == "draft_ai"
    assert unchanged["review"] is None


def test_approve_is_all_or_nothing_for_a_batch(lab_copy: Path) -> None:
    good_id = "en.articles.a_an"
    bad_id = "en.there_is_are"
    bad = load_point("en", bad_id, lab_copy)
    assert bad is not None
    bad.pop("sequence")
    save_point("en", bad, lab_copy)

    with pytest.raises(ApprovalError) as caught:
        approve_points("en", [good_id, bad_id], reviewer="Thi", root=lab_copy)

    assert any("point.sequence_missing" in problem for problem in caught.value.problems)
    good = load_point("en", good_id, lab_copy)
    bad_after = load_point("en", bad_id, lab_copy)
    assert good is not None and bad_after is not None
    assert good["status"] != "approved"
    assert bad_after["status"] != "approved"


def test_approve_does_not_overwrite_an_existing_approval(lab_copy: Path) -> None:
    point = load_point("en", "en.there_is_are", lab_copy)
    assert point is not None
    point["status"] = "approved"
    point["review"] = {
        "reviewer": "Existing reviewer",
        "reviewed_at": "2026-10-06T00:00:00Z",
        "seconds": 42.0,
        "note": "already reviewed",
    }
    save_point("en", point, lab_copy)
    assert validate_lang("en", lab_copy).ok

    result = approve_points("en", [point["id"]], reviewer="Thi", note="new note", root=lab_copy)

    assert result.approved == []
    assert result.already_approved == [point["id"]]
    after = load_point("en", point["id"], lab_copy)
    assert after is not None
    assert after["review"] == point["review"]


def test_approve_rejects_invalid_inputs_before_writing(lab_copy: Path) -> None:
    point = load_point("en", "en.there_is_are", lab_copy)
    assert point is not None
    point["status"] = "rejected"
    save_point("en", point, lab_copy)

    with pytest.raises(ApprovalError) as caught:
        approve_points("en", [point["id"]], reviewer="  ", seconds=-1, root=lab_copy)

    joined = "\n".join(caught.value.problems)
    assert "reviewer" in joined
    assert "seconds" in joined
    assert "status 'rejected'" in joined
    assert load_point("en", point["id"], lab_copy)["status"] == "rejected"
