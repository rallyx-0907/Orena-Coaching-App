from __future__ import annotations

from grammar_lab.pipeline import seed as seed_module
from grammar_lab.pipeline.generate import pinyin_from_pairs
from grammar_lab.pipeline.seed import load_seeds


def test_zh_reviewed_seed_native_titles_have_no_ascii_spaces() -> None:
    offenders = {
        seed["id"]: seed["native_title"]
        for seed in load_seeds("zh")
        if " " in str(seed.get("native_title", ""))
    }
    assert offenders == {}, offenders


def test_apply_seed_realigns_zh_native_title_pinyin(monkeypatch) -> None:
    native_title = "比较句+一点儿/得多"
    record = {
        "id": "zh.test.native_title",
        "level": "1",
        "function": "fn.sequence",
        "point_type": "other",
        "prereqs": [],
        "contrasts": [],
        "error_tags": ["other"],
        "sequence": 1,
        "aliases": [],
        "title": {"vi": "test", "en": "test"},
        "native_title": native_title,
        "anchors": [],
    }
    monkeypatch.setattr(seed_module, "load_catalog", lambda lang, root: [record])
    existing = {
        "header": {
            "native_title": "比较句 + 一点儿/得多",
            "native_title_pinyin": ["stale"] * 12,
        }
    }

    seeded = seed_module.apply_seed(existing, "zh", record["id"])

    assert seeded is not None
    assert seeded["header"]["native_title"] == native_title
    assert seeded["header"]["native_title_pinyin"] == pinyin_from_pairs(native_title)
