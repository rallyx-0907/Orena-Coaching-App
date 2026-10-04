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
locale.missing              a locale map lacks vi (always), en (status approved), or a function title lacks vi/en/zh-Hans (contract "Locale")
locale.l1_undeclared        pitfall.l1 names an L1 not declared in the manifest
zh.traditional_char         zh-Hans content contains traditional characters
inventory.duplicate_id      inv_id appears twice in the inventory
story.character_unknown     a story character is not in cast/cast.yaml
error_tag.story_alternative_unlisted  a story alternative's error_tag is not in the point's error_tags
story.length_out_of_range   hook+scene+need+reveal+consequences (vi) is not 150-250 words (STORY_SPEC.md §2, VOICE.md)
story.reveal_short_too_long reveal_short (vi) is more than 20 words
story.short_not_one_line    an alternative's short (or reveal_short) contains a newline
story.forbidden_phrase      vi text uses a phrase VOICE.md bans (fairy-tale opener/vocabulary, etc.)
header.level_mismatch       header.level differs from the point's level (GRAMMAR_CONTENT_CONTRACT.md v0.4)
illustration.kind_mismatch  pattern.illustration.kind does not fit point_type (tense_aspect->timeline, ...) (v0.4)
example.span_invalid        examples[].spans start>=end or end beyond text length (v0.4)
example.form_without_variant  an example's form (negative/question) has no pattern.variants formula (v0.4)
example.formula_role_missing  a required (non-optional) formula role has no span in the example (v0.4)
example.span_role_not_in_formula  a span's role is not a role of the example's formula (v0.4)
zh.pinyin_invalid           zh-Hans pinyin missing, wrong length, untoned/numbered, or set on a non-Han char (v0.4)
common_mistake.same_wrong_right  common_mistakes[].wrong and .right are identical (v0.4)
error_tag.common_mistake_unlisted  common_mistakes[].error_tag is not in the point's error_tags (v0.4)
quick_practice.blank_invalid  q does not contain exactly one ___ (v0.4)
quick_practice.answer_tagged  the correct option carries an error_tag (v0.4)
quick_practice.distractor_untagged  a wrong option names no learner error_tag (v0.4)
quick_practice.distractor_misspelling  a wrong option is only a misspelling (error_tag spelling) (v0.4)
formula.slot_has_joiner     a formula slot's text (or one of its options) contains '+' (the app draws joiners) (v0.4)
formula.option_duplicate    a formula slot lists the same option twice (v0.4)
zh.whitespace               a zh-Hans target string has a space next to a Han character or the ___ blank (v0.4)
zh.pinyin_field_unlisted    a flat string outside the contract's pinyin table carries Han characters (locale maps are never scanned) (v0.4)
header.sub_missing          an approved point has no header.sub (v0.4)
point.sequence_missing      an approved point has no sequence (v0.4)
personal_production.rule_invalid  a pattern_rule slot lacks exactly one of any_of/regex, or its regex does not compile (v0.4)
personal_production.rule_role_not_in_formula  a pattern_rule slot's role is not a role of the target_form formula (v0.4)
personal_production.rule_rejects_sample  the pattern_rule does not match personal_production.sample.text (v0.4)
personal_production.rule_rejects_example  the pattern_rule does not match an example of the target_form (rule too strict) (v0.4)
example.span_slot_mismatch  an example's spans, in text order, do not fit the slots of its formula in order (v0.4)
anchors.missing             a v0.4 point has no source_anchors (status unanchored is fine; absent is not) (v0.4)
contrasts.asymmetric        A lists B in contrasts but B does not list A (both in the set) (v0.4)
aliases.duplicate           an R5 id appears in the aliases of two points (v0.4)
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
CAST_PATH = Path("cast/cast.yaml")
ERROR_TAGS_PATH = Path("schema/error_tags.json")
GRAMMAR_SCHEMA_PATH = Path("schema/grammar_set.schema.json")
INVENTORY_SCHEMA_PATH = Path("schema/inventory.schema.json")

STORY_LENGTH_RANGE = (150, 250)  # words, vi (STORY_SPEC.md §2)
REVEAL_SHORT_MAX_WORDS = 20

# GRAMMAR_CONTENT_CONTRACT.md §2: the illustration a point's type calls for.
ILLUSTRATION_FOR_POINT_TYPE = {
    "tense_aspect": "timeline",
    "word_order": "word_order",
    "morphology": "morphology",
    "other": "none",
}
QUICK_PRACTICE_BLANK = "___"
# GRAMMAR_CONTENT_CONTRACT.md §7: a distractor must be a real learner *grammar* mistake. An
# engine label that only means "misspelled" (boxs, cates) would pass verify -- the engine does
# flag it -- while being exactly the invented form the contract rules out.
NONSENSE_DISTRACTOR_TAGS = frozenset({"spelling"})
REQUIRED_LOCALES = ("vi",)  # every status; "en" joins at approved (contract "Locale")
APPROVED_LOCALES = ("vi", "en")
FUNCTION_LOCALES = ("vi", "en", "zh-Hans")  # a function's label is the Library group header, all three UI languages
_LOCALE_KEYS = frozenset({"vi", "en", "zh-Hans", "ja"})
FORMULA_JOINER = "+"  # the app draws the joiner between slots; a slot never carries it
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
# Chinese is written without spaces; the first zh v0.4 run put one on each side of the blank
# ("他 ___ 吃过越南菜。"), which the learner would see and verify filled in as "他 没 吃过".
_ZH_SPACE = re.compile(rf"(?:{_HAN.pattern}|{QUICK_PRACTICE_BLANK})\s|\s(?:{_HAN.pattern}|{QUICK_PRACTICE_BLANK})")
# A tone-marked (or neutral-tone, unmarked) pinyin syllable; tone numbers like "wo3" are rejected.
_PINYIN_SYLLABLE = re.compile(r"^[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüê]+$")

# VOICE.md §2: fairy-tale opener/vocabulary and other patterns an adult-voice story may
# never use, in any form (checked as a case-insensitive substring of vi text).
FORBIDDEN_STORY_PHRASES = (
    "ngày xửa ngày xưa",
    "đã từ lâu lắm rồi",
    "vương quốc",
    "nhà vô địch",
    "lão làng",
)

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
        self.cast: set[str] | None = None  # story.characters are only checked against a valid cast file
        self.engine_tags: set[str] | None = None
        self.points: dict[str, tuple[str, dict[str, Any]]] = {}  # id -> (file, point) for schema-valid points
        self.known_ids: set[str] = set()  # IDs with content files; functions.realizations must resolve here
        self.reference_ids: set[str] = set()  # content IDs plus canonical catalog IDs for prereq/contrast refs
        self.catalog_records: dict[str, dict[str, Any]] = {}

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

    def load_cast(self) -> None:
        path = self.root / CAST_PATH
        file = self.rel(path)
        ok, data = self.load(path, read_yaml)
        if not ok or not self.schema_check(file, data, _validator(self.schema, "cast_file")):
            return
        self.cast = {member["name"] for member in data["cast"]}

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

    def load_catalog_references(self) -> None:
        """Load runtime-catalog IDs as valid structural references.

        During resumable corpus generation, a point may legitimately contrast
        with or depend on a canonical point whose content file has not been
        generated yet. functions.realizations still uses known_ids (actual
        files); only prereq/contrast reference checks use this wider set.
        """
        self.reference_ids = set(self.known_ids)
        path = self.root / "inventory" / f"catalog_{self.lang}.yaml"
        if not path.exists():
            return
        try:
            records = read_yaml(path) or []
        except (yaml.YAMLError, UnicodeDecodeError):
            return
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                self.catalog_records[record["id"]] = record
                self.reference_ids.add(record["id"])

    # -- per-point rules -----------------------------------------------------------------
    def check_point(self, file: str, point: dict[str, Any]) -> None:
        self.check_level(file, point)
        self.check_refs(file, point)
        self.check_error_tags(file, point)
        for index, block in enumerate(point.get("blocks", [])):
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
            elif kind == "story":
                self.check_story(file, path, block, point)
        if point.get("schema_version") == "0.4":
            self.check_header_v04(file, point)
            self.check_formula_slots_v04(file, point)
            self.check_illustration_v04(file, point)
            self.check_examples_v04(file, point)
            self.check_compare_v04(file, point)
            self.check_common_mistakes_v04(file, point)
            self.check_quick_practice_v04(file, point)
            if self.target_lang == ZH_HANS:
                self.check_pinyin_v04(file, point)
                self.check_zh_whitespace_v04(file, point)
        required = APPROVED_LOCALES if point["status"] == "approved" else REQUIRED_LOCALES
        for path, mapping in _locale_maps(point):
            self.check_locales(file, path, mapping, required)
        if point["status"] == "approved" and point.get("schema_version") == "0.4":
            if "sub" not in point["header"]:
                self.issue(file, "header.sub", "header.sub_missing", "an approved point needs header.sub")
            if "sequence" not in point:
                self.issue(file, "sequence", "point.sequence_missing", "an approved point needs sequence")
        if point.get("schema_version") == "0.4":
            if "source_anchors" not in point:
                self.issue(file, "source_anchors", "anchors.missing",
                           'add source_anchors ({"status": "unanchored", "items": []} when no source item is found)')
            self.check_personal_production_v04(file, point)
            if self.target_lang == ZH_HANS:
                self.check_pinyin_field_unlisted_v04(file, point)
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
        references = self.reference_ids or self.known_ids
        for index, prereq in enumerate(point["prereqs"]):
            if prereq not in references:
                self.issue(file, f"prereqs[{index}]", "ref.unknown_prereq", f"unknown grammar point {prereq}")
            else:
                prereq_level = None
                if prereq in self.points:
                    prereq_level = self.points[prereq][1]["level"]["value"]
                elif prereq in self.catalog_records:
                    prereq_level = self.catalog_records[prereq]["level"]
                if prereq_level is not None and self.scale.index(prereq_level) > self.scale.index(point["level"]["value"]):
                    self.issue(file, f"prereqs[{index}]", "ref.prereq_level",
                               f"prereq {prereq} is {prereq_level}, above {point['level']['value']}")
        for index, other in enumerate(point["contrasts"]):
            if other not in references:
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
        if other not in (self.reference_ids or self.known_ids):
            self.issue(file, f"{path}.with", "ref.unknown_contrast", f"unknown grammar point {other}")
        if other not in point["contrasts"]:
            self.issue(file, f"{path}.with", "ref.contrast_block_unlisted", f"{other} is not listed in contrasts")

    def check_story(self, file: str, path: str, block: dict[str, Any], point: dict[str, Any]) -> None:
        if self.cast is not None:
            for index, name in enumerate(block["characters"]):
                if name not in self.cast:
                    self.issue(file, f"{path}.characters[{index}]", "story.character_unknown",
                               f"{name!r} is not in cast/cast.yaml")
        for index, alt in enumerate(block["alternatives"]):
            alt_path = f"{path}.alternatives[{index}]"
            for tag_index, tag in enumerate(alt["error_tags"]):
                if tag not in point["error_tags"]:
                    self.issue(file, f"{alt_path}.error_tags[{tag_index}]", "error_tag.story_alternative_unlisted",
                               f"{tag!r} is not in the point's error_tags")
                if self.engine_tags is not None and tag not in self.engine_tags:
                    self.issue(file, f"{alt_path}.error_tags[{tag_index}]", "error_tag.unknown",
                               f"{tag!r} is not an engine error label for {self.target_lang}")
            for locale, text in alt["short"].items():
                if "\n" in text:
                    self.issue(file, f"{alt_path}.short.{locale}", "story.short_not_one_line", "contains a newline")
        for locale, text in block["reveal_short"].items():
            if "\n" in text:
                self.issue(file, f"{path}.reveal_short.{locale}", "story.short_not_one_line", "contains a newline")
        for sub_path, text in _story_forbidden_check_texts(block):
            lowered = text.lower()
            for phrase in FORBIDDEN_STORY_PHRASES:
                if phrase in lowered:
                    self.issue(file, f"{path}.{sub_path}", "story.forbidden_phrase", f"contains banned phrase {phrase!r}")
        if "vi" not in self.locales:
            return
        reveal_short_vi = block["reveal_short"].get("vi", "")
        words = len(reveal_short_vi.split())
        if reveal_short_vi and words > REVEAL_SHORT_MAX_WORDS:
            self.issue(file, f"{path}.reveal_short.vi", "story.reveal_short_too_long",
                       f"{words} words, max {REVEAL_SHORT_MAX_WORDS}")
        total = (
            len(block["hook"]["text"].get("vi", "").split())
            + len(block["scene"].get("vi", "").split())
            + len(block["need"].get("vi", "").split())
            + len(block["reveal"].get("vi", "").split())
            + len(block["teaser"].get("vi", "").split())
            + sum(len(alt["consequence"].get("vi", "").split()) for alt in block["alternatives"])
        )
        low, high = STORY_LENGTH_RANGE
        if not (low <= total <= high):
            self.issue(file, path, "story.length_out_of_range", f"{total} words (vi), expected {low}-{high}")

    def check_header_v04(self, file: str, point: dict[str, Any]) -> None:
        if point["header"]["level"] != point["level"]:
            self.issue(file, "header.level", "header.level_mismatch",
                       f"header says {point['header']['level']}, the point is {point['level']}")

    def check_formula_slots_v04(self, file: str, point: dict[str, Any]) -> None:
        for base, slots in _formulas(point["pattern"]):
            for index, slot in enumerate(slots):
                if FORMULA_JOINER in slot["text"]:
                    self.issue(file, f"{base}[{index}].text", "formula.slot_has_joiner",
                               f"{slot['text']!r}: the app draws '+' between slots; split it into its own slots")
                seen: set[str] = set()
                for option_index, option in enumerate(slot.get("options", [])):
                    path = f"{base}[{index}].options[{option_index}].text"
                    if FORMULA_JOINER in option["text"]:
                        self.issue(file, path, "formula.slot_has_joiner",
                                   f"{option['text']!r}: an option is one form, never a '+' sequence")
                    key = _normalize(option["text"])
                    if key in seen:
                        self.issue(file, path, "formula.option_duplicate", f"{option['text']!r} is listed twice")
                    seen.add(key)

    def check_illustration_v04(self, file: str, point: dict[str, Any]) -> None:
        expected = ILLUSTRATION_FOR_POINT_TYPE[point["point_type"]]
        kind = point["pattern"]["illustration"]["kind"]
        if kind != expected:
            self.issue(file, "pattern.illustration.kind", "illustration.kind_mismatch",
                       f"point_type {point['point_type']} needs {expected!r}, got {kind!r}")

    def check_examples_v04(self, file: str, point: dict[str, Any]) -> None:
        for index, example in enumerate(point["examples"]):
            path = f"examples[{index}]"
            text_len = len(example["text"])
            for span_index, span in enumerate(example["spans"]):
                if span["start"] >= span["end"] or span["end"] > text_len:
                    self.issue(file, f"{path}.spans[{span_index}]", "example.span_invalid",
                               f"start={span['start']} end={span['end']} out of range for text of length {text_len}")
            formula = _formula_for_form(point["pattern"], example["form"])
            if formula is None:
                self.issue(file, f"{path}.form", "example.form_without_variant",
                           f"form {example['form']!r} but pattern.variants has no {example['form']!r} formula")
                continue
            span_roles = {span["role"] for span in example["spans"]}
            required = {slot["role"] for slot in formula if not slot.get("optional")}
            role_problems = 0
            for role in sorted(required - span_roles):
                role_problems += 1
                self.issue(file, f"{path}.spans", "example.formula_role_missing",
                           f"no span with role {role!r}, which the {example['form']} formula requires")
            for role in sorted(span_roles - {slot["role"] for slot in formula}):
                role_problems += 1
                self.issue(file, f"{path}.spans", "example.span_role_not_in_formula",
                           f"span role {role!r} is not a role of the {example['form']} formula")
            if not role_problems:
                roles = [slot["role"] for slot in formula]
                # Stored spans identify a role, not a formula-slot id. When a
                # formula repeats a role (S...S, V...V, alternative markers),
                # assigning one span to one of those same-role slots is
                # inherently ambiguous in schema 0.4. Keep strict slot-order
                # validation only where roles uniquely identify slots.
                if len(roles) == len(set(roles)):
                    self.check_span_slots_v04(file, path, example, formula)

    def check_span_slots_v04(self, file: str, path: str, example: dict[str, Any], formula: list[dict[str, Any]]) -> None:
        """Span by slot, not only by role: walk the spans in text order and give each the first slot of its
        role at or after the previous span's slot. A span with no such slot breaks the formula's order;
        a required slot no span reached is uncovered (roles repeat: S ... S, V ... V)."""
        roles = [slot["role"] for slot in formula]
        position = 0
        reached: set[int] = set()
        for span in sorted(example["spans"], key=lambda item: item["start"]):
            slot_index = next((i for i in range(position, len(roles)) if roles[i] == span["role"]), None)
            if slot_index is None:
                text = example["text"][span["start"]:span["end"]]
                self.issue(file, f"{path}.spans", "example.span_slot_mismatch",
                           f"span {text!r} ({span['role']}) has no slot left in the formula order")
                return
            position = slot_index
            reached.add(slot_index)

    def check_pinyin_v04(self, file: str, point: dict[str, Any]) -> None:
        for path, text, pinyin in _pinyin_targets(point):
            problem = _pinyin_problem(text, pinyin)
            if problem:
                self.issue(file, path, "zh.pinyin_invalid", problem)

    def check_zh_whitespace_v04(self, file: str, point: dict[str, Any]) -> None:
        for path, text in _target_texts(point):
            if _ZH_SPACE.search(text):
                self.issue(file, path, "zh.whitespace", f"space inside Chinese text: {text!r}")

    def check_compare_v04(self, file: str, point: dict[str, Any]) -> None:
        for index, item in enumerate(point["compare"]):
            path = f"compare[{index}]"
            other = item["with"]
            if other not in (self.reference_ids or self.known_ids):
                self.issue(file, f"{path}.with", "ref.unknown_contrast", f"unknown grammar point {other}")
            if other not in point["contrasts"]:
                self.issue(file, f"{path}.with", "ref.contrast_block_unlisted", f"{other} is not listed in contrasts")

    def check_common_mistakes_v04(self, file: str, point: dict[str, Any]) -> None:
        for index, item in enumerate(point["common_mistakes"]):
            path = f"common_mistakes[{index}]"
            if _normalize(item["wrong"]) == _normalize(item["right"]):
                self.issue(file, path, "common_mistake.same_wrong_right", "wrong and right are identical")
            if item["error_tag"] not in point["error_tags"]:
                self.issue(file, f"{path}.error_tag", "error_tag.common_mistake_unlisted",
                           f"{item['error_tag']!r} is not in the point's error_tags")
            if self.engine_tags is not None and item["error_tag"] not in self.engine_tags:
                self.issue(file, f"{path}.error_tag", "error_tag.unknown",
                           f"{item['error_tag']!r} is not an engine error label for {self.target_lang}")
            if self.l1s:
                for l1_index, l1 in enumerate(item["l1"]):
                    if l1 not in self.l1s:
                        self.issue(file, f"{path}.l1[{l1_index}]", "locale.l1_undeclared",
                                   f"L1 {l1!r} is not declared in the set manifest")

    def check_quick_practice_v04(self, file: str, point: dict[str, Any]) -> None:
        for index, item in enumerate(point["quick_practice"]):
            path = f"quick_practice[{index}]"
            blanks = item["q"].count(QUICK_PRACTICE_BLANK)
            if blanks != 1:
                self.issue(file, f"{path}.q", "quick_practice.blank_invalid",
                           f"q must contain exactly one {QUICK_PRACTICE_BLANK}, found {blanks}")
            if item["answer"] >= len(item["options"]):
                self.issue(file, f"{path}.answer", "check.answer_out_of_range",
                           f"answer {item['answer']} but only {len(item['options'])} options")
            seen: dict[str, int] = {}
            for option_index, option in enumerate(item["options"]):
                option_path = f"{path}.options[{option_index}]"
                key = _normalize(option["text"])
                if key in seen:
                    self.issue(file, option_path, "check.duplicate_options",
                               f"{option['text']!r} duplicates option {seen[key]}")
                else:
                    seen[key] = option_index
                tag = option["error_tag"]
                if option_index == item["answer"]:
                    if tag is not None:
                        self.issue(file, f"{option_path}.error_tag", "quick_practice.answer_tagged",
                                   f"the correct option carries error_tag {tag!r}")
                elif tag is None:
                    self.issue(file, f"{option_path}.error_tag", "quick_practice.distractor_untagged",
                               f"wrong option {option['text']!r} names no learner error")
                elif tag in NONSENSE_DISTRACTOR_TAGS:
                    self.issue(file, f"{option_path}.error_tag", "quick_practice.distractor_misspelling",
                               f"wrong option {option['text']!r} is only a misspelling ({tag}), not a grammar "
                               "mistake this point teaches")
                elif self.engine_tags is not None and tag not in self.engine_tags:
                    self.issue(file, f"{option_path}.error_tag", "error_tag.unknown",
                               f"{tag!r} is not an engine error label for {self.target_lang}")

    def check_pinyin_field_unlisted_v04(self, file: str, point: dict[str, Any]) -> None:
        """A flat string outside the contract's pinyin table that carries Han characters is a target-text
        field nobody registered. Locale maps (explanations) are never scanned."""
        listed = {path for path, _, _ in _pinyin_targets(point)}
        listed_texts = {path for path, _ in _target_texts(point)}

        def walk(node: Any, path: str) -> Iterator[tuple[str, str]]:
            if isinstance(node, dict):
                if node and all(key in _LOCALE_KEYS for key in node):
                    return  # a locale map: explanation text, may quote Han characters to teach them
                for key, value in node.items():
                    if key in ("source_refs", "provenance", "review", "flags", "id", "prereqs", "contrasts",
                               "aliases", "error_tags", "error_tag", "l1", "with", "function", "blocks", "pattern_rule"):
                        continue
                    yield from walk(value, f"{path}.{key}" if path else key)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    yield from walk(value, f"{path}[{index}]")
            elif isinstance(node, str) and _HAN.search(node):
                yield path, node

        for path, _text in walk(point, ""):
            if path not in listed_texts and path not in listed:
                self.issue(file, path, "zh.pinyin_field_unlisted",
                           "this field carries Chinese characters but is not in the contract's pinyin table (section 8)")

    def check_personal_production_v04(self, file: str, point: dict[str, Any]) -> None:
        production = point.get("personal_production")
        if not production:
            return
        base = "personal_production"
        formula = _formula_for_form(point["pattern"], production["target_form"])
        if formula is None:
            self.issue(file, f"{base}.target_form", "example.form_without_variant",
                       f"target_form {production['target_form']!r} but pattern.variants has no such formula")
            return
        formula_roles = {slot["role"] for slot in formula}
        rule = production["pattern_rule"]
        matchers = []
        for index, slot in enumerate(rule["slots"]):
            slot_path = f"{base}.pattern_rule.slots[{index}]"
            has_any, has_regex = "any_of" in slot, "regex" in slot
            if has_any == has_regex:
                self.issue(file, slot_path, "personal_production.rule_invalid",
                           "a slot needs exactly one of any_of or regex")
                return
            if slot["role"] not in formula_roles:
                self.issue(file, f"{slot_path}.role", "personal_production.rule_role_not_in_formula",
                           f"role {slot['role']!r} is not in the {production['target_form']} formula")
            if has_regex:
                try:
                    matchers.append(re.compile(slot["regex"], re.IGNORECASE))
                except re.error as exc:
                    self.issue(file, f"{slot_path}.regex", "personal_production.rule_invalid", f"regex: {exc}")
                    return
            else:
                matchers.append(slot["any_of"])
        zh = self.target_lang == ZH_HANS
        sample_text = production["sample"]["text"]
        if not pattern_rule_matches(rule["ordered"], matchers, sample_text, zh):
            self.issue(
                file, f"{base}.sample.text", "personal_production.rule_rejects_sample",
                f"the pattern_rule does not match {sample_text!r}",
            )

        target_examples = [
            (index, example["text"])
            for index, example in enumerate(point["examples"])
            if example["form"] == production["target_form"]
        ]
        if target_examples and not any(
            pattern_rule_matches(rule["ordered"], matchers, text, zh)
            for _, text in target_examples
        ):
            index, text = target_examples[0]
            self.issue(
                file, f"examples[{index}].text", "personal_production.rule_rejects_example",
                "the pattern_rule does not match any example of the target_form "
                f"(first checked: {text!r})",
            )

    def check_locales(
        self, file: str, path: str, mapping: dict[str, str], required: tuple[str, ...] = REQUIRED_LOCALES
    ) -> None:
        missing = [locale for locale in required if locale not in mapping]
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

    def check_contrasts_symmetric(self) -> None:
        for pid, (file, point) in sorted(self.points.items()):
            for index, other in enumerate(point["contrasts"]):
                if other not in self.points:
                    continue
                if self.catalog_records:
                    # In a real corpus the runtime catalog is the structural
                    # authority. Legacy on-disk points outside canonical_v1
                    # remain readable but do not impose reciprocal edges on
                    # the canonical graph.
                    if pid not in self.catalog_records or other not in self.catalog_records:
                        continue
                    counterpart = self.catalog_records[other]
                else:
                    # Tiny validator fixtures have no runtime catalog; retain
                    # the original direct-content symmetry contract.
                    counterpart = self.points[other][1]
                if pid not in counterpart["contrasts"]:
                    self.issue(file, f"contrasts[{index}]", "contrasts.asymmetric",
                               f"{pid} lists {other} but {other} does not list {pid}")

    def check_aliases(self) -> None:
        seen: dict[str, str] = {}
        for pid, (file, point) in sorted(self.points.items()):
            for index, alias in enumerate(point.get("aliases", [])):
                if alias in seen:
                    self.issue(file, f"aliases[{index}]", "aliases.duplicate",
                               f"R5 id {alias} is already an alias of {seen[alias]}")
                else:
                    seen[alias] = pid

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
                self.check_locales(file, f"{fid}.title", function["title"], FUNCTION_LOCALES)
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
        self.load_cast()
        self.load_error_tags()
        self.load_points()
        self.load_catalog_references()
        for file, point in self.points.values():
            self.check_point(file, point)
        self.check_prereq_cycles()
        self.check_contrasts_symmetric()
        self.check_aliases()
        self.check_functions()
        self.check_inventory()
        self.report.issues.sort()
        return self.report


def pattern_rule_matches(ordered: bool, matchers: list[Any], text: str, zh: bool) -> bool:
    """GRAMMAR_CONTENT_CONTRACT.md section 7b: does a learner sentence use the pattern?

    ``matchers`` holds, per slot, a compiled regex or a list of literal alternatives. Literals match whole
    words (EN) or substrings (ZH). Ordered rules need the slots to match left to right without overlap."""
    normalized = text.casefold().replace("\u2019", "'")

    # If the rule explicitly models a contraction suffix as its own slot
    # (is + n't, I + 've, she + 'll), expose an internal token boundary
    # before that suffix for matching only. Stored text is never changed.
    contraction_suffixes = {"n't", "'m", "'re", "'s", "'ve", "'ll", "'d"}
    split_suffixes = {
        str(literal).casefold().replace("\u2019", "'")
        for matcher in matchers
        if isinstance(matcher, list)
        for literal in matcher
        if str(literal).casefold().replace("\u2019", "'") in contraction_suffixes
    }
    if not zh:
        for suffix in sorted(split_suffixes, key=len, reverse=True):
            normalized = normalized.replace(suffix, " " + suffix)

    position = 0
    for matcher in matchers:
        best = None
        if isinstance(matcher, list):
            candidates = []
            for literal in matcher:
                literal = literal.casefold()
                if zh:
                    pattern = re.escape(literal)
                elif literal.replace("\u2019", "'") in {"n't", "'m", "'re", "'s", "'ve", "'ll", "'d"}:
                    # Contraction suffixes are grammar-bearing literals inside a
                    # larger orthographic token (isn't, I've, she'll...). They
                    # cannot satisfy the normal left whole-word boundary.
                    pattern = rf"{re.escape(literal)}(?![\w])"
                else:
                    pattern = rf"(?<![\w']){re.escape(literal)}(?![\w])"
                candidates.append(re.compile(pattern))
        else:
            candidates = [matcher]
        for pattern in candidates:
            found = pattern.search(normalized, position if ordered else 0)
            if found and (best is None or found.start() < best.start()):
                best = found
        if best is None:
            return False
        if ordered:
            position = best.end()
    return True


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _formula_for_form(pattern: dict[str, Any], form: str) -> list[dict[str, Any]] | None:
    if form == "affirmative":
        return pattern["formula"]
    return pattern.get("variants", {}).get(form)


def _formulas(pattern: dict[str, Any]) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    yield "pattern.formula", pattern["formula"]
    for name, slots in pattern.get("variants", {}).items():
        yield f"pattern.variants.{name}", slots


def _pinyin_targets(point: dict[str, Any]) -> Iterator[tuple[str, str, list[str] | None]]:
    """(path, text, pinyin) for every zh-Hans string that must carry per-character pinyin
    (the table of GRAMMAR_CONTENT_CONTRACT.md section 8, and nothing else)."""
    if "header" in point:
        yield "header.native_title_pinyin", point["header"]["native_title"], point["header"].get("native_title_pinyin")
    for base, slots in _formulas(point["pattern"]):
        for index, slot in enumerate(slots):
            yield f"{base}[{index}].pinyin", slot["text"], slot.get("pinyin")
            for option_index, option in enumerate(slot.get("options", [])):
                yield f"{base}[{index}].options[{option_index}].pinyin", option["text"], option.get("pinyin")
    for index, example in enumerate(point["examples"]):
        yield f"examples[{index}].pinyin", example["text"], example.get("pinyin")
    for index, item in enumerate(point["common_mistakes"]):
        yield f"common_mistakes[{index}].wrong_pinyin", item["wrong"], item.get("wrong_pinyin")
        yield f"common_mistakes[{index}].right_pinyin", item["right"], item.get("right_pinyin")
    for index, item in enumerate(point.get("compare", [])):
        for side in ("this", "other"):
            yield f"compare[{index}].{side}_example_pinyin", item[f"{side}_example"], item.get(f"{side}_example_pinyin")
    for index, item in enumerate(point.get("quick_practice", [])):
        yield f"quick_practice[{index}].q_pinyin", item["q"], item.get("q_pinyin")
        for option_index, option in enumerate(item["options"]):
            yield (f"quick_practice[{index}].options[{option_index}].pinyin", option["text"], option.get("pinyin"))
    for index, item in enumerate(point["pattern"]["illustration"].get("morphology", [])):
        for key in ("base", "affix", "result"):
            yield f"pattern.illustration.morphology[{index}].{key}_pinyin", item[key], item.get(f"{key}_pinyin")
    production = point.get("personal_production")
    if production:
        yield "personal_production.placeholder_pinyin", production["placeholder"], production.get("placeholder_pinyin")
        yield "personal_production.sample.pinyin", production["sample"]["text"], production["sample"].get("pinyin")


def _pinyin_problem(text: str, pinyin: list[str] | None) -> str | None:
    if pinyin is None:
        return "missing (zh-Hans needs one entry per character)"
    if len(pinyin) != len(text):
        return f"{len(pinyin)} entries for {len(text)} characters"
    for char, syllable in zip(text, pinyin, strict=True):
        if _HAN.match(char):
            if not _PINYIN_SYLLABLE.match(syllable.casefold()):
                return f"{char!r} needs a tone-marked syllable, got {syllable!r}"
        elif syllable:
            return f"non-Han character {char!r} must map to '', got {syllable!r}"
    return None


def _story_forbidden_check_texts(block: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Every vi-locale string in a story block, for the VOICE.md banned-phrase check."""
    yield "hook.text.vi", block["hook"]["text"].get("vi", "")
    yield "scene.vi", block["scene"].get("vi", "")
    yield "need.vi", block["need"].get("vi", "")
    yield "reveal.vi", block["reveal"].get("vi", "")
    yield "reveal_short.vi", block["reveal_short"].get("vi", "")
    yield "teaser.vi", block["teaser"].get("vi", "")
    for index, alt in enumerate(block["alternatives"]):
        yield f"alternatives[{index}].consequence.vi", alt["consequence"].get("vi", "")
        yield f"alternatives[{index}].short.vi", alt["short"].get("vi", "")


def _locale_maps(point: dict[str, Any]) -> Iterator[tuple[str, dict[str, str]]]:
    if "header" in point:
        yield "header.title", point["header"]["title"]
        yield "header.summary", point["header"]["summary"]
        if "sub" in point["header"]:
            yield "header.sub", point["header"]["sub"]
    else:
        yield "title", point["title"]
        yield "summary", point["summary"]
    if "pattern" in point:
        for base, slots in _formulas(point["pattern"]):
            for index, slot in enumerate(slots):
                yield f"{base}[{index}].label", slot["label"]
        illustration = point["pattern"]["illustration"]
        if "relevance" in illustration.get("timeline", {}):
            yield "pattern.illustration.timeline.relevance", illustration["timeline"]["relevance"]
        for index, item in enumerate(illustration.get("morphology", [])):
            for key in ("affix_note", "note"):
                if key in item:
                    yield f"pattern.illustration.morphology[{index}].{key}", item[key]
    production = point.get("personal_production")
    if production:
        yield "personal_production.prompt", production["prompt"]
        if "placeholder_note" in production:
            yield "personal_production.placeholder_note", production["placeholder_note"]
    for index, item in enumerate(point.get("when_to_use", [])):
        yield f"when_to_use[{index}]", item
    for index, example in enumerate(point.get("examples", [])):
        yield f"examples[{index}].annotation", example["annotation"]
        yield f"examples[{index}].translation", example["translation"]
    for index, item in enumerate(point.get("compare", [])):
        yield f"compare[{index}].this_meaning", item["this_meaning"]
        yield f"compare[{index}].other_meaning", item["other_meaning"]
    for index, item in enumerate(point.get("common_mistakes", [])):
        yield f"common_mistakes[{index}].reason", item["reason"]
    for index, item in enumerate(point.get("quick_practice", [])):
        yield f"quick_practice[{index}].explain", item["explain"]
    for index, block in enumerate(point.get("blocks", [])):
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
        elif kind == "story":
            yield f"{path}.hook.text", block["hook"]["text"]
            yield f"{path}.scene", block["scene"]
            yield f"{path}.need", block["need"]
            yield f"{path}.reveal", block["reveal"]
            yield f"{path}.reveal_short", block["reveal_short"]
            yield f"{path}.teaser", block["teaser"]
            for alt_index, alt in enumerate(block["alternatives"]):
                yield f"{path}.alternatives[{alt_index}].consequence", alt["consequence"]
                yield f"{path}.alternatives[{alt_index}].short", alt["short"]


def _target_texts(point: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Strings written in the target language (as opposed to explanation locales)."""
    if "header" in point:
        yield "header.native_title", point["header"]["native_title"]
    if "pattern" in point:
        for base, slots in _formulas(point["pattern"]):
            for index, slot in enumerate(slots):
                yield f"{base}[{index}].text", slot["text"]
                for option_index, option in enumerate(slot.get("options", [])):
                    yield f"{base}[{index}].options[{option_index}].text", option["text"]
        for index, item in enumerate(point["pattern"]["illustration"].get("morphology", [])):
            for key in ("base", "affix", "result"):
                yield f"pattern.illustration.morphology[{index}].{key}", item[key]
    production = point.get("personal_production")
    if production:
        yield "personal_production.placeholder", production["placeholder"]
        yield "personal_production.sample.text", production["sample"]["text"]
    for index, example in enumerate(point.get("examples", [])):
        yield f"examples[{index}].text", example["text"]
    for index, item in enumerate(point.get("compare", [])):
        yield f"compare[{index}].this_example", item["this_example"]
        yield f"compare[{index}].other_example", item["other_example"]
    for index, item in enumerate(point.get("common_mistakes", [])):
        yield f"common_mistakes[{index}].wrong", item["wrong"]
        yield f"common_mistakes[{index}].right", item["right"]
    for index, item in enumerate(point.get("quick_practice", [])):
        yield f"quick_practice[{index}].q", item["q"]
        for option_index, option in enumerate(item["options"]):
            yield f"quick_practice[{index}].options[{option_index}].text", option["text"]
    for index, block in enumerate(point.get("blocks", [])):
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
        elif kind == "story":
            for sentence_index, sentence in enumerate(block["form_in_action"]["sentences"]):
                yield f"{path}.form_in_action.sentences[{sentence_index}]", sentence
            for alt_index, alt in enumerate(block["alternatives"]):
                yield f"{path}.alternatives[{alt_index}].sentence", alt["sentence"]


def _zh_hans_texts(point: dict[str, Any], target_is_zh: bool) -> Iterator[tuple[str, str]]:
    if target_is_zh:
        yield from _target_texts(point)
        for key, refs in point["source_refs"].items():
            for index, ref in enumerate(refs):
                yield f"source_refs.{key}[{index}]", ref
    for path, mapping in _locale_maps(point):
        if ZH_HANS in mapping:
            yield f"{path}.{ZH_HANS}", mapping[ZH_HANS]


def validate_generated_point(
    lang: str, point: dict[str, Any], root: Path = LAB_ROOT,
) -> list[Issue]:
    """Validate one generated candidate before it is written to the corpus.

    This runs the same per-point semantic rules as validate_lang but treats
    every canonical catalog id as a known reference, because a resumable corpus
    may legitimately point at a canonical contrast/prerequisite whose content
    file has not been generated yet. Cross-point/global checks (contrast
    symmetry, cycles, function-registry completeness) remain the responsibility
    of the full-corpus validator.

    ref.realization_missing is intentionally ignored here: a brand-new
    candidate is moved from planned to realizations only after this local gate
    passes.
    """
    validation = _Validation(lang, root)
    validation.load_manifest()
    # Deliberately do not load functions or the other point files here. Corpus
    # workers run concurrently and functions.yaml/content files are being
    # advanced by sibling workers. Structural function/prerequisite/contrast
    # integrity is already gated by the frozen catalog; this local gate is for
    # the candidate's own schema and semantic content.
    validation.load_cast()
    validation.load_error_tags()

    file = f"content/{lang}/{point['id']}.json"

    catalog_path = root / "inventory" / f"catalog_{lang}.yaml"
    if catalog_path.exists():
        try:
            catalog = read_yaml(catalog_path) or []
        except (yaml.YAMLError, UnicodeDecodeError):
            catalog = []
        for record in catalog:
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                validation.known_ids.add(record["id"])
                validation.reference_ids.add(record["id"])

    # Legacy on-disk points outside canonical_v1 are still valid references.
    content_dir = root / "content" / lang
    if content_dir.exists():
        disk_ids = {
            path.stem for path in content_dir.glob("*.json") if not path.name.startswith("_")
        }
        validation.known_ids.update(disk_ids)
        validation.reference_ids.update(disk_ids)

    validation.known_ids.add(point["id"])
    validation.reference_ids.add(point["id"])
    validation.points[point["id"]] = (file, point)
    if validation.schema_check(file, point, _validator(validation.schema)):
        validation.check_point(file, point)

    return [
        issue
        for issue in validation.report.issues_for(file)
        if issue.code != "ref.realization_missing"
    ]

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
