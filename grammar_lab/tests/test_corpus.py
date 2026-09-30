from __future__ import annotations

import json

import yaml

from grammar_lab.pipeline.corpus import (
    BLOCKED_METADATA,
    GENERATED,
    GENERATED_UNREVIEWED_METADATA,
    READY,
    normalize_langs,
    plan_corpus,
    ready_items,
)


def _write_catalog(root, lang, records):
    path = root / "inventory" / f"catalog_{lang}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(records, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_point(root, lang, point_id):
    path = root / "content" / lang / f"{point_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": point_id}), encoding="utf-8")


def test_plan_corpus_separates_resume_and_metadata_states(tmp_path):
    records = [
        {"id": "en.ready", "level": "A1", "catalog": {"canonical_level": "A1", "metadata_origin": "reviewed_seed"}},
        {"id": "en.blocked", "level": "A1", "catalog": {"canonical_level": "A1", "metadata_origin": "default_safe"}},
        {"id": "en.done", "level": "A2", "catalog": {"canonical_level": "A2", "metadata_origin": "reviewed_seed"}},
        {"id": "en.draft_unreviewed", "level": "A2", "catalog": {"canonical_level": "A2", "metadata_origin": "default_safe"}},
    ]
    _write_catalog(tmp_path, "en", records)
    _write_point(tmp_path, "en", "en.done")
    _write_point(tmp_path, "en", "en.draft_unreviewed")

    plan = plan_corpus(("en",), tmp_path)

    assert plan["canonical_total"] == 4
    assert plan["counts"] == {
        READY: 1,
        BLOCKED_METADATA: 1,
        GENERATED: 1,
        GENERATED_UNREVIEWED_METADATA: 1,
    }
    assert ready_items(plan) == [("en", "A1", "en.ready")]


def test_normalize_langs_preserves_corpus_order():
    assert normalize_langs("all") == ("en", "zh")
    assert normalize_langs("zh") == ("zh",)
