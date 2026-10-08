from __future__ import annotations

import re

from grammar_lab.pipeline.content_store import load_point, load_points
from grammar_lab.pipeline.seed import apply_seed, load_seeds
from grammar_lab.pipeline.validate import LAB_ROOT, validate_generated_point

_CJK = re.compile(r"[\u3400-\u9fff]")


def test_reviewed_zh_seed_native_titles_have_no_ascii_spaces() -> None:
    bad = {
        seed["id"]: seed["native_title"]
        for seed in load_seeds("zh", LAB_ROOT)
        if _CJK.search(seed["native_title"]) and " " in seed["native_title"]
    }
    assert bad == {}


def test_serial_verbs_reviewed_seed_stays_export_valid_after_apply_seed() -> None:
    point = load_point("zh", "zh.serial_verbs.qu_lai", LAB_ROOT)
    assert point is not None

    resolved = apply_seed(point, "zh", "zh.serial_verbs.qu_lai", LAB_ROOT)
    assert resolved is not None

    issues = validate_generated_point("zh", resolved, LAB_ROOT)
    bad = [issue for issue in issues if issue.code in {"zh.whitespace", "zh.pinyin_invalid"}]
    assert bad == []


def test_apply_seed_keeps_all_zh_native_title_pinyin_in_lockstep() -> None:
    failures: dict[str, list[str]] = {}
    for point_id, point in load_points("zh", LAB_ROOT).items():
        resolved = apply_seed(point, "zh", point_id, LAB_ROOT)
        if resolved is None:
            continue
        issues = validate_generated_point("zh", resolved, LAB_ROOT)
        bad = [
            f"{issue.path}: {issue.message}"
            for issue in issues
            if issue.path == "header.native_title_pinyin" and issue.code == "zh.pinyin_invalid"
        ]
        if bad:
            failures[point_id] = bad
    assert failures == {}
