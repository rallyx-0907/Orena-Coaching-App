"""``validate`` step (SPEC §5.2): deterministic checks, no LLM.

Every problem is an :class:`Issue` whose ``reason`` (``validate:<code>``) is
what a failing grammar point is flagged with. Codes:

schema.invalid              file does not match its JSON Schema
file.invalid_json           file is not parseable JSON/YAML
file.missing_manifest       content/<lang>/_set.json is missing
file.id_mismatch            point file name is not <id>.json
file.lang_mismatch          content does not belong to the language being validated
level.rank_mismatch         level.rank is not the position of level.value in level_scales
example.seg_text_mismatch   concatenated seg differs from text
example.no_target           no seg labelled "target"
example.ruby_length         ruby length differs from seg length
check.answer_out_of_range   answer is not an index into options
check.duplicate_options     two options are the same (ignoring case and spacing)
pitfall.same_wrong_right    wrong and right sentences are identical
ref.unknown_function        function ID does not exist
ref.unknown_prereq          prereq ID does not exist
ref.unknown_contrast        contrasts[] or contrast.with ID does not exist
ref.contrast_block_unlisted contrast.with is not listed in contrasts
ref.prereq_cycle            prereq graph has a cycle
ref.prereq_level            a prereq sits higher in the level scale than the point
ref.realization_missing     the point's function does not list it in realizations
ref.unknown_realization     a function realization ID does not exist
error_tag.list_missing      schema/error_tags.json has no tag list for the language
error_tag.unknown           tag is not an engine error label
error_tag.pitfall_unlisted  pitfall.error_tag is not in the point's error_tags
locale.missing              a localized field lacks a locale declared in the manifest
locale.l1_undeclared        pitfall.l1 names an L1 not declared in the manifest
zh.traditional_char         zh-Hans content contains traditional characters
inventory.duplicate_id      inv_id appears twice in the inventory
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from grammar_lab.pipeline.jsonio import read_json, read_yaml, write_json
from grammar_lab.pipeline.zh_script import traditional_chars

LAB_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "_set.json"
FUNCTIONS_PATH = Path("functions/functions.yaml")
ERROR_TAGS_PATH = Path("schema/error_tags.json")
GRAMMAR_SCHEMA_PATH = Path("schema/grammar_set.schema.json")
INVENTORY_SCHEMA_PATH = Path("schema/inventory.schema.json")

# Short code (content dir, ID prefix, CLI --lang) -> BCP-47 target_lang.
LANGS = {"en": "en", "zh": "zh-Hans", "ja": "ja"}
ZH_HANS = "zh-Hans"
FLAG_PREFIX = "validate:"


@dataclass(frozen=True, order=True)
class Issue:
    file: str
    path: str
    code: str
    message: str

    @property
    def reason(self) -> str:
        return FLAG_PREFIX + self.code

    def to_dict(self) -> dict[str, str]:
        return {"file": self.file, "path": self.path, "code": self.code, "reason": self.reason, "message": self.message}


@dataclass
class Report:
    lang: str
    points: int = 0
    issues: list[Issue] = field(default_factory=list)
    point_files: dict[str, str] = field(default_factory=dict)  # relative file -> point id

    @property
    def ok(self) -> bool:
        return not self.issues

    def codes(self) -> set[str]:
        return {issue.code for issue in self.issues}

    def issues_for(self, file: str) -> list[Issue]:
        return [issue for issue in self.issues if issue.file == file]


@cache
def _load_schema(path: Path) -> dict[str, Any]:
    return read_json(path)


def _validator(schema: dict[str, Any], definition: str | None = None) -> Draft202012Validator:
    if definition is None:
        return Draft202012Validator(schema)
    return Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}
    )


def _json_path(parts: Any) -> str:
    out = ""
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "$"


class _Validation:
    def __init__(self, lang: str, root: Path) -> None:
        if lang not in LANGS:
            raise ValueError(f"unknown lang {lang!r}; expected one of {sorted(LANGS)}")
        self.lang = lang
        self.target_lang = LANGS[lang]
        self.root = root
        self.report = Report(lang=lang)
        self.schema = _load_schema(root / GRAMMAR_SCHEMA_PATH)
        scale = self.schema["level_scales"][self.target_lang]
        self.framework: str = scale["framework"]
        self.scale: list[str] = scale["values"]
        self.locales: list[str] = []
        self.l1s: list[str] = []
        self.functions: dict[str, dict[str, Any]] = {}
        self.functions_loaded = False  # function references are only checked against a valid functions file
        self.engine_tags: set[str] | None = None
        self.points: dict[str, tuple[str, dict[str, Any]]] = {}  # id -> (file, point) for schema-valid points
        self.known_ids: set[str] = set()  # every ID seen, even in schema-invalid files

    # -- helpers -------------------------------------------------------------------------
    def issue(self, file: str, path: str, code: str, message: str) -> None:
        self.report.issues.append(Issue(file, path, code, message))

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def load(self, path: Path, loader) -> tuple[bool, Any]:
        try:
            return True, loader(path)
        except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
            self.issue(self.rel(path), "$", "file.invalid_json", f"cannot parse: {exc}")
            return False, None

    def schema_check(self, file: str, data: Any, validator: Draft202012Validator) -> bool:
        errors = sorted(validator.iter_errors(data), key=lambda e: (list(e.absolute_path), e.message))
        for error in errors:
            self.issue(file, _json_path(error.absolute_path), "schema.invalid", error.message)
        return not errors

    # -- inputs --------------------------------------------------------------------------
    def load_manifest(self) -> None:
        path = self.root / "content" / self.lang / MANIFEST_NAME
        file = self.rel(path)
        if not path.exists():
            self.issue(file, "$", "file.missing_manifest", "set manifest is missing")
            return
        ok, manifest = self.load(path, read_json)
        if not ok or not self.schema_check(file, manifest, _validator(self.schema, "set_manifest")):
            return
        if manifest["target_lang"] != self.target_lang:
            self.issue(file, "target_lang", "file.lang_mismatch",
                       f"manifest target_lang {manifest['target_lang']!r} in content/{self.lang}/")
            return
        self.locales = manifest["explanation_locales"]
        self.l1s = manifest["l1"]

    def load_functions(self) -> None:
        path = self.root / FUNCTIONS_PATH
        file = self.rel(path)
        ok, data = self.load(path, read_yaml)
        if not ok or not self.schema_check(file, data, _validator(self.schema, "functions_file")):
            return
        for index, function in enumerate(data["functions"]):
            if function["id"] in self.functions:
                self.issue(file, f"functions[{index}].id", "schema.invalid", f"duplicate function id {function['id']}")
            self.functions[function["id"]] = function
        self.functions_loaded = True

    def load_error_tags(self) -> None:
        path = self.root / ERROR_TAGS_PATH
        file = self.rel(path)
        if not path.exists():
            self.issue(file, "$", "error_tag.list_missing", "error tag list is missing")
            return
        ok, data = self.load(path, read_json)
        if not ok:
            return
        entry = (data.get("languages") or {}).get(self.target_lang) if isinstance(data, dict) else None
        if not isinstance(entry, dict) or not isinstance(entry.get("tags"), list):
            self.issue(file, f"languages.{self.target_lang}", "error_tag.list_missing",
                       f"no engine error tags for {self.target_lang}")
            return
        self.engine_tags = set(entry["tags"])

    def load_points(self) -> None:
        validator = _validator(self.schema)
        directory = self.root / "content" / self.lang
        for path in sorted(directory.glob("*.json")) if directory.exists() else []:
            if path.name.startswith("_"):
                continue
            file = self.rel(path)
            self.report.points += 1
            ok, point = self.load(path, read_json)
            if not ok:
                continue
            point_id = point.get("id") if isinstance(point, dict) else None
            if isinstance(point_id, str):
                self.known_ids.add(point_id)
                self.report.point_files[file] = point_id
            if not self.schema_check(file, point, validator):
                continue
            if path.stem != point_id:
                self.issue(file, "id", "file.id_mismatch", f"file name must be {point_id}.json")
            if point["target_lang"] != self.target_lang:
                self.issue(file, "target_lang", "file.lang_mismatch",
                           f"target_lang {point['target_lang']!r} in content/{self.lang}/")
                continue
            self.points[point_id] = (file, point)

    # -- per-point rules -----------------------------------------------------------------
    def check_point(self, file: str, point: dict[str, Any]) -> None:
        self.check_level(file, point)
        self.check_refs(file, point)
        self.check_error_tags(file, point)
        for index, block in enumerate(point["blocks"]):
            path = f"blocks[{index}]"
            kind = block["type"]
            if kind == "example":
                self.check_example(file, path, block)
            elif kind == "check":
                self.check_check(file, path, block)
            elif kind == "pitfall":
                self.check_pitfall(file, path, block, point)
            elif kind == "contrast":
                self.check_contrast(file, path, block, point)
        for path, mapping in _locale_maps(point):
            self.check_locales(file, path, mapping)
        self.check_script(file, point)

    def check_level(self, file: str, point: dict[str, Any]) -> None:
        level = point["level"]
        expected = self.scale.index(level["value"]) + 1
        if level["rank"] != expected:
            self.issue(file, "level.rank", "level.rank_mismatch",
                       f"{self.framework} {level['value']} has rank {expected}, got {level['rank']}")

    def check_refs(self, file: str, point: dict[str, Any]) -> None:
        if self.functions_loaded:
            function = self.functions.get(point["function"])
            if function is None:
                self.issue(file, "function", "ref.unknown_function", f"unknown function {point['function']}")
            elif point["id"] not in function["realizations"].get(self.target_lang, []):
                self.issue(file, "function", "ref.realization_missing",
                           f"{point['function']} does not list {point['id']} in realizations.{self.target_lang}")
        for index, prereq in enumerate(point["prereqs"]):
            if prereq not in self.known_ids:
                self.issue(file, f"prereqs[{index}]", "ref.unknown_prereq", f"unknown grammar point {prereq}")
            elif prereq in self.points:
                prereq_level = self.points[prereq][1]["level"]["value"]
                if self.scale.index(prereq_level) > self.scale.index(point["level"]["value"]):
                    self.issue(file, f"prereqs[{index}]", "ref.prereq_level",
                               f"prereq {prereq} is {prereq_level}, above {point['level']['value']}")
        for index, other in enumerate(point["contrasts"]):
            if other not in self.known_ids:
                self.issue(file, f"contrasts[{index}]", "ref.unknown_contrast", f"unknown grammar point {other}")

    def check_error_tags(self, file: str, point: dict[str, Any]) -> None:
        if self.engine_tags is None:
            return
        for index, tag in enumerate(point["error_tags"]):
            if tag not in self.engine_tags:
                self.issue(file, f"error_tags[{index}]", "error_tag.unknown",
                           f"{tag!r} is not an engine error label for {self.target_lang}")

    def check_example(self, file: str, path: str, block: dict[str, Any]) -> None:
        joined = "".join(segment[0] for segment in block["seg"])
        if joined != block["text"]:
            self.issue(file, f"{path}.seg", "example.seg_text_mismatch",
                       f"seg joins to {joined!r}, text is {block['text']!r}")
        if not any(len(segment) > 1 and segment[1] == "target" for segment in block["seg"]):
            self.issue(file, f"{path}.seg", "example.no_target", "no segment labelled 'target'")
        if "ruby" in block and len(block["ruby"]) != len(block["seg"]):
            self.issue(file, f"{path}.ruby", "example.ruby_length",
                       f"ruby has {len(block['ruby'])} items, seg has {len(block['seg'])}")

    def check_check(self, file: str, path: str, block: dict[str, Any]) -> None:
        for index, item in enumerate(block["items"]):
            item_path = f"{path}.items[{index}]"
            if item["answer"] >= len(item["options"]):
                self.issue(file, f"{item_path}.answer", "check.answer_out_of_range",
                           f"answer {item['answer']} but only {len(item['options'])} options")
            seen: dict[str, int] = {}
            for option_index, option in enumerate(item["options"]):
                key = _normalize(option)
                if key in seen:
                    self.issue(file, f"{item_path}.options[{option_index}]", "check.duplicate_options",
                               f"{option!r} duplicates option {seen[key]}")
                else:
                    seen[key] = option_index

    def check_pitfall(self, file: str, path: str, block: dict[str, Any], point: dict[str, Any]) -> None:
        if _normalize(block["wrong"]) == _normalize(block["right"]):
            self.issue(file, path, "pitfall.same_wrong_right", "wrong and right are identical")
        if block["error_tag"] not in point["error_tags"]:
            self.issue(file, f"{path}.error_tag", "error_tag.pitfall_unlisted",
                       f"{block['error_tag']!r} is not in the point's error_tags")
        if self.engine_tags is not None and block["error_tag"] not in self.engine_tags:
            self.issue(file, f"{path}.error_tag", "error_tag.unknown",
                       f"{block['error_tag']!r} is not an engine error label for {self.target_lang}")
        if self.l1s:
            for index, l1 in enumerate(block["l1"]):
                if l1 not in self.l1s:
                    self.issue(file, f"{path}.l1[{index}]", "locale.l1_undeclared",
                               f"L1 {l1!r} is not declared in the set manifest")

    def check_contrast(self, file: str, path: str, block: dict[str, Any], point: dict[str, Any]) -> None:
        other = block["with"]
        if other not in self.known_ids:
            self.issue(file, f"{path}.with", "ref.unknown_contrast", f"unknown grammar point {other}")
        if other not in point["contrasts"]:
            self.issue(file, f"{path}.with", "ref.contrast_block_unlisted", f"{other} is not listed in contrasts")

    def check_locales(self, file: str, path: str, mapping: dict[str, str]) -> None:
        missing = [locale for locale in self.locales if locale not in mapping]
        if missing:
            self.issue(file, path, "locale.missing", f"missing locale(s): {', '.join(missing)}")

    def check_script(self, file: str, point: dict[str, Any]) -> None:
        texts = list(_zh_hans_texts(point, self.target_lang == ZH_HANS))
        for path, text in texts:
            found = traditional_chars(text)
            if found:
                self.issue(file, path, "zh.traditional_char", f"traditional character(s): {''.join(found)}")

    # -- cross-file rules ----------------------------------------------------------------
    def check_prereq_cycles(self) -> None:
        graph = {pid: [p for p in point["prereqs"] if p in self.points] for pid, (_, point) in self.points.items()}
        reported: set[tuple[str, ...]] = set()
        state: dict[str, int] = {}  # 1 = on stack, 2 = done
        stack: list[str] = []

        def visit(node: str) -> None:
            state[node] = 1
            stack.append(node)
            for nxt in graph[node]:
                if state.get(nxt) == 1:
                    cycle = stack[stack.index(nxt):]
                    start = cycle.index(min(cycle))
                    canonical = tuple(cycle[start:] + cycle[:start])
                    if canonical not in reported:
                        reported.add(canonical)
                        self.issue(self.points[canonical[0]][0], "prereqs", "ref.prereq_cycle",
                                   "prereq cycle: " + " -> ".join((*canonical, canonical[0])))
                elif nxt not in state:
                    visit(nxt)
            stack.pop()
            state[node] = 2

        for node in sorted(graph):
            if node not in state:
                visit(node)

    def check_functions(self) -> None:
        file = FUNCTIONS_PATH.as_posix()
        used = {point["function"] for _, point in self.points.values()}
        for function in self.functions.values():
            fid = function["id"]
            for index, realization in enumerate(function["realizations"].get(self.target_lang, [])):
                if realization not in self.known_ids:
                    self.issue(file, f"{fid}.realizations.{self.target_lang}[{index}]", "ref.unknown_realization",
                               f"unknown grammar point {realization}")
            if fid in used:
                self.check_locales(file, f"{fid}.title", function["title"])
            zh_title = function["title"].get(ZH_HANS)
            if zh_title and traditional_chars(zh_title):
                self.issue(file, f"{fid}.title.{ZH_HANS}", "zh.traditional_char",
                           f"traditional character(s): {''.join(traditional_chars(zh_title))}")

    def check_inventory(self) -> None:
        path = self.root / "inventory" / f"{self.lang}.yaml"
        if not path.exists():
            return
        file = self.rel(path)
        ok, items = self.load(path, read_yaml)
        if not ok:
            return
        schema = _load_schema(self.root / INVENTORY_SCHEMA_PATH)
        if not self.schema_check(file, items or [], _validator(schema)):
            return
        seen: set[str] = set()
        for index, item in enumerate(items or []):
            if item["inv_id"] in seen:
                self.issue(file, f"[{index}].inv_id", "inventory.duplicate_id", f"duplicate inv_id {item['inv_id']}")
            seen.add(item["inv_id"])
            if not item["inv_id"].startswith(self.lang + "."):
                self.issue(file, f"[{index}].inv_id", "file.lang_mismatch", f"{item['inv_id']} in inventory/{self.lang}.yaml")
            if self.functions_loaded and item["function"] not in self.functions:
                self.issue(file, f"[{index}].function", "ref.unknown_function", f"unknown function {item['function']}")

    def run(self) -> Report:
        self.load_manifest()
        self.load_functions()
        self.load_error_tags()
        self.load_points()
        for file, point in self.points.values():
            self.check_point(file, point)
        self.check_prereq_cycles()
        self.check_functions()
        self.check_inventory()
        self.report.issues.sort()
        return self.report


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _locale_maps(point: dict[str, Any]) -> Iterator[tuple[str, dict[str, str]]]:
    yield "title", point["title"]
    yield "summary", point["summary"]
    for index, block in enumerate(point["blocks"]):
        path = f"blocks[{index}]"
        kind = block["type"]
        if kind == "rule_table":
            for row_index, row in enumerate(block["rows"]):
                yield f"{path}.rows[{row_index}][2]", row[2]
        elif kind == "example":
            yield f"{path}.tr", block["tr"]
        elif kind == "contrast":
            yield f"{path}.explain", block["explain"]
        elif kind == "pitfall":
            yield f"{path}.why", block["why"]
        elif kind == "note":
            yield f"{path}.text", block["text"]
        elif kind == "check":
            for item_index, item in enumerate(block["items"]):
                yield f"{path}.items[{item_index}].explain", item["explain"]


def _target_texts(point: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Strings written in the target language (as opposed to explanation locales)."""
    for index, block in enumerate(point["blocks"]):
        path = f"blocks[{index}]"
        kind = block["type"]
        if kind == "formula":
            for part_index, part in enumerate(block["parts"]):
                yield f"{path}.parts[{part_index}]", part
        elif kind == "rule_table":
            for row_index, row in enumerate(block["rows"]):
                yield f"{path}.rows[{row_index}][0]", row[0]
                yield f"{path}.rows[{row_index}][1]", row[1]
        elif kind == "example":
            yield f"{path}.text", block["text"]
            for seg_index, segment in enumerate(block["seg"]):
                yield f"{path}.seg[{seg_index}]", segment[0]
        elif kind == "contrast":
            for pair_index, pair in enumerate(block["pairs"]):
                for side, sentence in enumerate(pair):
                    yield f"{path}.pairs[{pair_index}][{side}]", sentence
        elif kind == "pitfall":
            yield f"{path}.wrong", block["wrong"]
            yield f"{path}.right", block["right"]
        elif kind == "check":
            for item_index, item in enumerate(block["items"]):
                yield f"{path}.items[{item_index}].q", item["q"]
                for option_index, option in enumerate(item["options"]):
                    yield f"{path}.items[{item_index}].options[{option_index}]", option


def _zh_hans_texts(point: dict[str, Any], target_is_zh: bool) -> Iterator[tuple[str, str]]:
    if target_is_zh:
        yield from _target_texts(point)
        for key, refs in point["source_refs"].items():
            for index, ref in enumerate(refs):
                yield f"source_refs.{key}[{index}]", ref
    for path, mapping in _locale_maps(point):
        if ZH_HANS in mapping:
            yield f"{path}.{ZH_HANS}", mapping[ZH_HANS]


def validate_lang(lang: str, root: Path = LAB_ROOT) -> Report:
    return _Validation(lang, root).run()


def apply_flags(report: Report, root: Path = LAB_ROOT) -> list[str]:
    """Flag failing points (status=flagged, flags += validate:<code>); clear stale validate flags.

    Passing points keep their status: routing them is the job of ``route``.
    Returns the relative paths of files that changed.
    """
    changed = []
    for file in sorted(report.point_files):
        path = root / file
        try:
            point = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(point, dict):
            continue
        kept = [flag for flag in point.get("flags", []) if not flag.startswith(FLAG_PREFIX)]
        reasons = sorted({issue.reason for issue in report.issues_for(file)})
        updated = dict(point)
        if reasons:
            updated["status"] = "flagged"
        flags = kept + reasons
        if flags:
            updated["flags"] = flags
        else:
            updated.pop("flags", None)
        if updated != point:
            write_json(path, updated)
            changed.append(file)
    return changed
