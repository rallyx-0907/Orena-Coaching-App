from __future__ import annotations

import re

from grammar_lab.pipeline.content_store import load_point
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
