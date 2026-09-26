from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from grammar_lab.pipeline.jsonio import write_json
from grammar_lab.pipeline.validate import LAB_ROOT, Report, validate_lang

SCHEMA_FILES = ("grammar_set.schema.json", "inventory.schema.json")
PROVENANCE = {"model": "test-model", "prompt_version": "v1", "run_id": "test", "generated_at": "2026-09-26T00:00:00Z"}
ENGINE_TAGS = {"en": {"tags": ["agreement", "tense", "article", "other"]}, "zh-Hans": {"tags": ["aspect", "particle", "other"]}}


def en_point(point_id: str, level: str, rank: int, **overrides: Any) -> dict[str, Any]:
    point = {
        "schema_version": "0.2",
        "id": point_id,
        "version": 1,
        "target_lang": "en",
        "function": "fn.alpha",
        "level": {"framework": "cefr", "value": level, "rank": rank},
        "prereqs": [],
        "contrasts": [],
        "error_tags": ["agreement"],
        "source_refs": {"egp": ["TEST-1"]},
        "title": {"vi": "Tiêu đề", "en": "Title"},
        "summary": {"vi": "Tóm tắt."},
        "blocks": [
            {"type": "formula", "parts": ["He / She / It", "V + s"]},
            {"type": "timeline", "kind": "habit"},
            {"type": "rule_table", "rows": [["work", "works", {"vi": "Thêm -s"}]]},
            {
                "type": "example",
                "text": "She works in a bank.",
                "seg": [["She "], ["works", "target"], [" in a bank."]],
                "tr": {"vi": "Cô ấy làm ở ngân hàng."},
            },
            {
                "type": "pitfall",
                "l1": ["vi"],
                "wrong": "He go to school.",
                "right": "He goes to school.",
                "error_tag": "agreement",
                "why": {"vi": "Ngôi thứ ba số ít."},
            },
            {"type": "note", "text": {"vi": "Ghi chú."}},
            {"type": "check", "items": [{"q": "He ___ to school.", "options": ["go", "goes"], "answer": 1, "explain": {"vi": "Thêm -s."}}]},
        ],
        "status": "draft_ai",
        "provenance": dict(PROVENANCE),
        "review": None,
    }
    point.update(overrides)
    return point


def zh_point() -> dict[str, Any]:
    return {
        "schema_version": "0.2",
        "id": "zh.le_completion",
        "version": 1,
        "target_lang": "zh-Hans",
        "function": "fn.alpha",
        "level": {"framework": "hsk3", "value": "1", "rank": 1},
        "prereqs": [],
        "contrasts": [],
        "error_tags": ["aspect"],
        "source_refs": {"hsk3": ["一级 语法点"]},
        "title": {"vi": "Trợ từ 了", "zh-Hans": "动态助词“了”"},
        "summary": {"vi": "了 sau động từ chỉ hành động đã hoàn thành."},
        "blocks": [
            {"type": "formula", "parts": ["主语", "动词 + 了", "宾语"]},
            {
                "type": "example",
                "text": "我们吃了饭。",
                "seg": [["我们"], ["吃了", "target"], ["饭"], ["。"]],
                "ruby": ["wǒmen", "chī le", "fàn", None],
                "tr": {"vi": "Chúng tôi đã ăn cơm."},
            },
            {
                "type": "pitfall",
                "l1": ["vi"],
                "wrong": "我昨天吃饭。",
                "right": "我昨天吃了饭。",
                "error_tag": "aspect",
                "why": {"vi": "Hành động đã xong cần 了."},
            },
            {"type": "check", "items": [{"q": "我___饭。", "options": ["吃了", "吃着"], "answer": 0, "explain": {"vi": "Đã xong → 了."}}]},
        ],
        "status": "draft_ai",
        "provenance": dict(PROVENANCE),
        "review": None,
    }


class Lab:
    """A throwaway Grammar Lab tree: real schemas, small hand-made content."""

    def __init__(self, root: Path, lang: str = "en") -> None:
        self.root = root
        self.lang = lang
        self.error_tags: dict[str, Any] | None = {"schema_version": "0.2", "languages": copy.deepcopy(ENGINE_TAGS)}
        self.inventory: list[dict[str, Any]] | None = None
        self.file_names: dict[str, str] = {}  # point id -> file name override
        self.raw_files: dict[str, str] = {}  # file name -> raw text in content/<lang>/
        if lang == "en":
            self.manifest: dict[str, Any] | None = {
                "schema_version": "0.2", "set_id": "en.test", "target_lang": "en",
                "explanation_locales": ["vi"], "l1": ["vi"],
            }
            beta = en_point("en.beta", "A2", 2, prereqs=["en.alpha"], contrasts=["en.alpha"], error_tags=["tense"])
            beta["blocks"] = [
                {
                    "type": "example",
                    "text": "Yesterday I went home.",
                    "seg": [["Yesterday I "], ["went", "target"], [" home."]],
                    "tr": {"vi": "Hôm qua tôi về nhà."},
                },
                {
                    "type": "contrast",
                    "with": "en.alpha",
                    "pairs": [["I went home.", "I go home every day."]],
                    "explain": {"vi": "Quá khứ và thói quen."},
                },
                {
                    "type": "pitfall",
                    "l1": ["vi"],
                    "wrong": "Yesterday I go home.",
                    "right": "Yesterday I went home.",
                    "error_tag": "tense",
                    "why": {"vi": "Phải chia quá khứ."},
                },
            ]
            self.points = {"en.alpha": en_point("en.alpha", "A1", 1), "en.beta": beta}
            realizations = {"en": ["en.alpha", "en.beta"]}
        else:
            self.manifest = {
                "schema_version": "0.2", "set_id": "zh.test", "target_lang": "zh-Hans",
                "explanation_locales": ["vi"], "l1": ["vi"],
            }
            self.points = {"zh.le_completion": zh_point()}
            realizations = {"zh-Hans": ["zh.le_completion"]}
        self.functions: dict[str, Any] = {
            "schema_version": "0.2",
            "functions": [{"id": "fn.alpha", "title": {"vi": "Chức năng", "en": "Function"}, "realizations": realizations}],
        }

    @property
    def content_dir(self) -> Path:
        return self.root / "content" / self.lang

    def write(self) -> None:
        schema_dir = self.root / "schema"
        schema_dir.mkdir(parents=True, exist_ok=True)
        for name in SCHEMA_FILES:
            shutil.copy(LAB_ROOT / "schema" / name, schema_dir / name)
        if self.error_tags is not None:
            write_json(schema_dir / "error_tags.json", self.error_tags)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        if self.manifest is not None:
            write_json(self.content_dir / "_set.json", self.manifest)
        for point_id, point in self.points.items():
            write_json(self.content_dir / self.file_names.get(point_id, f"{point_id}.json"), point)
        for name, text in self.raw_files.items():
            (self.content_dir / name).write_text(text, encoding="utf-8")
        functions = self.root / "functions" / "functions.yaml"
        functions.parent.mkdir(parents=True, exist_ok=True)
        functions.write_text(yaml.safe_dump(self.functions, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if self.inventory is not None:
            inventory = self.root / "inventory" / f"{self.lang}.yaml"
            inventory.parent.mkdir(parents=True, exist_ok=True)
            inventory.write_text(yaml.safe_dump(self.inventory, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def validate(self) -> Report:
        self.write()
        return validate_lang(self.lang, self.root)


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return Lab(tmp_path, "en")


@pytest.fixture
def zh_lab(tmp_path: Path) -> Lab:
    return Lab(tmp_path, "zh")
