"""Synthetic export-profile-1 packages for the grammar store tests. No Grammar Lab corpus is read or copied: every body
here is generated, validates against the vendored profile, and passes the importer's cross checks."""
from __future__ import annotations

import copy
import io
import json
import zipfile
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event

from writing_coach.grammar_store import contract
from writing_coach.persistence.models import Base

VI = "Ví dụ tổng hợp có dấu tiếng Việt"


def lm(en: str, zh: str | None = None) -> dict[str, str]:
    return {"vi": f"{VI} ({en})", "en": en, **({"zh": zh} if zh else {})}


def body(point_id: str, *, version: int = 1, function: str = "fn.talk_past", sequence: int = 1, level: int = 1,
         aliases: list[str] | None = None, r5_split: list[str] | None = None, prereqs: list[str] | None = None,
         contrasts: list[str] | None = None, tags: tuple[str, str] = ("tense_choice", "word_order"),
         title: str = "Point") -> dict[str, Any]:
    lang = point_id.split(".")[0]
    level_obj = ({"framework": "cefr", "value": ["A1", "A2", "B1", "B2", "C1", "C2"][level - 1], "rank": level}
                 if lang == "en" else {"framework": "hsk3", "value": str(level), "rank": level})
    if lang == "en":
        example = {"text": "Learners finished it yesterday.", "form": "affirmative",
                   "spans": [{"start": 0, "end": 8, "role": "subject"}, {"start": 9, "end": 17, "role": "verb"}],
                   "annotation": lm("Annotation"), "translation": lm("Translation")}
        native = f"{title} {sequence}"
        sample = {"text": "I finished it."}
    else:
        example = {"text": "我昨天买了一本书。", "form": "affirmative",
                   "pinyin": ["wǒ", "zuó", "tiān", "mǎi", "le", "yī", "běn", "shū", ""],
                   "spans": [{"start": 0, "end": 1, "role": "subject"}, {"start": 3, "end": 4, "role": "verb"}],
                   "annotation": lm("Annotation", "注释"), "translation": lm("Translation", "翻译")}
        native = f"语法点{sequence}"
        sample = {"text": "我昨天买了一本书。"}
    return {
        "id": point_id, "version": version, "status": "approved", "target_lang": lang, "function": function,
        "level": level_obj, "prereqs": list(prereqs or []), "contrasts": list(contrasts or []), "error_tags": list(tags),
        "source_refs": {"egp": [f"egp_{sequence}"], **({"r5_split": r5_split} if r5_split else {})},
        "point_type": "tense_aspect", "sequence": sequence, "aliases": list(aliases or []),
        "header": {"title": lm(title), "native_title": native, "sub": lm("Subtitle"), "level": dict(level_obj),
                   "summary": lm("Summary")},
        "when_to_use": [lm("When one"), lm("When two")],
        "pattern": {"formula": [{"text": "S", "role": "subject", "label": lm("Subject")},
                                {"text": "V", "role": "verb", "label": lm("Verb")}],
                    "illustration": {"kind": "timeline", "timeline": {"shape": "point_past", "relevance": lm("Rel")}}},
        "examples": [copy.deepcopy(example) for _ in range(2)],
        "compare": [],
        "common_mistakes": [{"wrong": "x", "right": "y", "reason": lm("Reason"), "error_tag": tags[0], "l1": ["vi"]}],
        "quick_practice": [{"q": f"Q{k}", "options": [{"text": "a", "error_tag": None}, {"text": "b", "error_tag": tags[0]}],
                            "answer": k % 2, "explain": lm("Because")} for k in range(3)],
        "personal_production": {"prompt": lm("Write one."), "placeholder": "...", "target_form": "affirmative",
                                "pattern_rule": {"ordered": True, "slots": [{"role": "subject"}, {"role": "verb"}]},
                                "sample": sample},
    }


FUNCTIONS = [{"id": "fn.talk_past", "title": {"vi": f"{VI} quá khứ", "en": "Talking about the past", "zh": "谈论过去"}},
             {"id": "fn.describe", "title": {"vi": f"{VI} miêu tả", "en": "Describing", "zh": "描述"}}]


def manifest(bodies: list[dict[str, Any]], *, language: str = "en", r5_map: list[dict[str, Any]] | None = None,
             external: list[str] | None = None, functions: list[dict[str, Any]] | None = None,
             set_version: str = "test.1", **overrides: Any) -> dict[str, Any]:
    used = {b["function"] for b in bodies}
    fns = [f for f in (functions if functions is not None else FUNCTIONS) if f["id"] in used]
    m = {
        "export_profile": contract.SUPPORTED_EXPORT_PROFILE, "profile_schema_hash": contract.PROFILE_SCHEMA_HASH,
        "schema_version": contract.SUPPORTED_SCHEMA_VERSION, "language": language, "set_version": set_version,
        "source_commit": "a" * 40, "source_dirty": False, "exported_at": "2026-10-08T00:00:00Z",
        "package_hash": "", "external_references": sorted(external or []), "functions": fns,
        "points": [{"id": b["id"], "version": b["version"], "content_hash": contract.content_hash(b),
                    "level": b["level"], "provenance": {"reviewer": "human", "reviewed_at": "2026-10-01T00:00:00Z",
                                                        "review_seconds": 30, "run_id": "r", "model": "m",
                                                        "prompt_version": "p", "generated_at": "2026-09-30T00:00:00Z",
                                                        "source_refs": {}, "source_anchors": None}}
                   for b in sorted(bodies, key=lambda b: b["id"])],
        "r5_map": list(r5_map or []),
        "validator": {"tool": "grammar_lab.export_package", "version": "1", "passed": True, "codes": []},
        "rights": {"source_text_policy": "catalogue_codes_only", "external_text_included": False,
                   "attestation_required_at_import": True, "note": "policy"},
    }
    m.update(overrides)
    if not m["package_hash"]:
        m["package_hash"] = contract.package_hash_of(m)
    return m


def zip_package(m: dict[str, Any], bodies: list[dict[str, Any]], *, functions: Any = None,
                extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("package.json", json.dumps(m, ensure_ascii=False))
        archive.writestr("functions.json", json.dumps(m["functions"] if functions is None else functions,
                                                      ensure_ascii=False))
        for b in bodies:
            archive.writestr(f"points/{b['id']}.json", json.dumps(b, ensure_ascii=False))
        for name, raw in (extra or {}).items():
            archive.writestr(name, raw)
    return buffer.getvalue()


def package(bodies: list[dict[str, Any]], **kw: Any) -> bytes:
    m = manifest(bodies, **kw)
    return zip_package(m, bodies)


def sqlite_engine(tmp_path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'grammar.db'}", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine
