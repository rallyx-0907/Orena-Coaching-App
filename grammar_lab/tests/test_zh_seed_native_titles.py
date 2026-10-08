from __future__ import annotations

from grammar_lab.pipeline.seed import load_seeds


def test_zh_reviewed_seed_native_titles_have_no_ascii_spaces() -> None:
    offenders = {
        seed["id"]: seed["native_title"]
        for seed in load_seeds("zh")
        if " " in str(seed.get("native_title", ""))
    }
    assert offenders == {}, offenders
