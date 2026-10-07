"""``generate`` step (SPEC §5.1): deterministic blocks from rules/, LLM for
natural-language blocks, templated check items.

Operates on points that already exist under ``content/<lang>/`` -- their
``id``/``target_lang``/``function``/``level``/``prereqs``/``contrasts``/
``error_tags``/``source_refs`` are structural metadata that comes from the
inventory (SPEC §4), not something this step invents. What ``generate``
(re)writes is the point's ``blocks``: the deterministic ``rule_table`` (code,
via ``rules/``), the LLM-authored blocks (``formula``, ``timeline``,
``example``, ``contrast``, ``pitfall``, ``note``), and the ``check`` items
(code, built from the examples the LLM just wrote).

SPEC's "don't overwrite an approved point" rule (§5.1) only applies once a
point has been approved: an unreviewed draft can be regenerated freely, in
place, at the same version. Regenerating an *approved* point requires
``--regenerate-note`` and bumps ``version`` -- SPEC §6's admin "request
regenerate" action.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pypinyin import Style, lazy_pinyin

from grammar_lab.pipeline.content_store import (
    LAB_ROOT,
    load_cast,
    load_functions,
    load_manifest,
    load_point,
    next_draft_version,
    save_point,
)
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.llm_client import LLMClient, LLMError
from grammar_lab.pipeline.seed import apply_seed, check_generation_gate, register_realization
from grammar_lab.pipeline.semantic_repair import (
    TARGETED_REPAIR_ATTEMPTS,
    apply_patch as apply_semantic_patch,
    can_target_repair,
    request_patch as request_semantic_patch,
)
from grammar_lab.pipeline.r5_source import DEFAULT_R5_ROOT, R5SourceError, load_r5, r5_source_text
from grammar_lab.pipeline.validate import (
    _HAN,
    ERROR_TAGS_PATH,
    ILLUSTRATION_FOR_POINT_TYPE,
    QUICK_PRACTICE_BLANK,
    ZH_HANS,
    _PINYIN_SYLLABLE,
    Issue,
    pattern_rule_matches,
    validate_generated_point,
)
from grammar_lab.rules import en_morphology

PROMPT_VERSION = "generate_point.v1"
PROMPT_PATH = LAB_ROOT / "prompts" / "generate_point.md"
PROMPT_VERSION_V04 = "generate_point_v04.v16"
PROMPT_PATH_V04 = LAB_ROOT / "prompts" / "generate_point_v04.md"
V04_SEMANTIC_ATTEMPTS = 3
PERSONAL_PRODUCTION_MAX_SLOTS = 4
PERSONAL_PRODUCTION_MAX_ANY_OF = 8
STORY_PROMPT_VERSION = "generate_story.v2"
# grammar_set.schema.json's story_mode allows "history" too (VOICE.md), but generate.py
# does not offer it yet: a "history" story may only state a fact from a vetted source, and
# no such source exists in this repo yet. Wire it in once one does, rather than letting the
# model invent historical/etymological claims it cannot be checked against.
STORY_MODES = {"everyday"}
STORY_PROMPT_PATH = LAB_ROOT / "prompts" / "generate_story.md"

# point id -> (rule label, vocabulary the rule table is built from)
_EN_RULE_TABLES: dict[str, tuple[str, list[str]]] = {
    "en.present_simple.third_person_s": ("third_person_singular", ["work", "study", "go", "have", "watch"]),
    "en.plural_nouns.regular": ("plural_noun", ["cat", "box", "city", "knife", "bus"]),
    "en.past_simple": ("past_simple", ["work", "study", "stop", "go", "have"]),
    "en.present_continuous.now": ("present_participle", ["work", "make", "run", "study", "write"]),
    "en.comparatives": ("comparative", ["cheap", "big", "nice", "happy", "good"]),
    "en.present_perfect.experience": ("past_participle", ["go", "see", "eat", "do", "visit"]),
}
_RULE_FUNCTIONS = {
    "third_person_singular": en_morphology.third_person_singular,
    "plural_noun": en_morphology.plural_noun,
    "past_simple": en_morphology.past_simple,
    "present_participle": en_morphology.present_participle,
    "comparative": en_morphology.comparative,
    "past_participle": en_morphology.past_participle,
}


def _incremental_result_cost(result: Any) -> float | None:
    """Actual spend in this run: replaying a cached completion costs nothing."""
    if result.cached:
        return 0.0
    return result.usage.cost_usd(result.model)


@dataclass
class GenerateOutcome:
    point_id: str
    status: str  # "written" | "skipped_approved" | "error"
    reason: str = ""
    cost_usd: float | None = None
    cached: bool = False


def build_rule_table(point_id: str, locales: list[str]) -> dict[str, Any] | None:
    """The deterministic ``rule_table`` block for ``point_id``, or ``None`` if this
    point has no mechanical spelling rule (e.g. ``there_is_are``, articles)."""
    entry = _EN_RULE_TABLES.get(point_id)
    if entry is None:
        return None
    rule_name, words = entry
    fn = _RULE_FUNCTIONS[rule_name]
    rows: list[list[Any]] = []
    for word in words:
        derived = fn(word)
        if derived is None:
            continue
        note = {locale: f"{word} -> {derived}" for locale in locales}
        rows.append([word, derived, note])
    return {"type": "rule_table", "rows": rows} if rows else None


def _rule_table_summary(rule_table: dict[str, Any] | None) -> str:
    if rule_table is None:
        return "(none -- no mechanical spelling rule applies to this point)"
    return "; ".join(f"{base} -> {derived}" for base, derived, _ in rule_table["rows"])


def _normalize_seg(seg: list[list[Any]]) -> list[list[Any]]:
    """``example.seg`` items are ``[text]`` or ``[text, label]`` -- the label is
    genuinely optional (SPEC §3), not nullable. A provider with no real schema
    enforcement (DeepSeek's json_object mode; live testing 2026-09-28) reached
    for the more common JSON convention instead and sent ``[text, null]`` for
    an unlabelled segment rather than omitting the second element. Providers
    with real structured-output enforcement (Gemini, OpenAI, Groq, Anthropic
    tool-use) never produce this -- the schema itself forbids it -- so this is
    a no-op for them."""
    return [segment[:1] if len(segment) > 1 and segment[1] is None else segment for segment in seg]


def _locale_map_schema(locales: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(locales),
        "properties": {locale: {"type": "string", "minLength": 1} for locale in locales},
    }


def _generation_schema(*, locales: list[str], l1s: list[str], error_tags: list[str],
                        contrast_with: list[str], num_examples: int) -> dict[str, Any]:
    locale_map = _locale_map_schema(locales)
    example = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "seg", "tr"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "seg": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "array", "minItems": 1, "maxItems": 2,
                    "prefixItems": [{"type": "string", "minLength": 1}, {"type": "string"}],
                },
            },
            "tr": locale_map,
        },
    }
    contrast = {
        "type": "object",
        "additionalProperties": False,
        "required": ["with", "pairs", "explain"],
        "properties": {
            "with": {"enum": contrast_with} if contrast_with else {"type": "string"},
            "pairs": {
                "type": "array", "minItems": 1,
                "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string", "minLength": 1}},
            },
            "explain": locale_map,
        },
    }
    pitfall = {
        "type": "object",
        "additionalProperties": False,
        "required": ["l1", "wrong", "right", "error_tag", "why"],
        "properties": {
            "l1": {"type": "array", "minItems": 1, "items": {"enum": l1s} if l1s else {"type": "string"}},
            "wrong": {"type": "string", "minLength": 1},
            "right": {"type": "string", "minLength": 1},
            "error_tag": {"enum": error_tags} if error_tags else {"type": "string"},
            "why": locale_map,
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula", "timeline", "examples", "contrasts", "pitfalls", "note"],
        "properties": {
            "formula": {
                "type": "object", "additionalProperties": False, "required": ["parts"],
                "properties": {"parts": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}},
            },
            "timeline": {
                "type": ["object", "null"], "additionalProperties": False, "required": ["kind"],
                "properties": {
                    "kind": {"enum": [
                        "point_past", "ongoing_now", "unspecified_past", "habit",
                        "future_condition", "future_plan", "past_ongoing",
                    ]},
                    "relevance": {"type": "string"},
                },
            },
            "examples": {"type": "array", "minItems": num_examples, "maxItems": num_examples, "items": example},
            "contrasts": {"type": "array", "minItems": len(contrast_with), "maxItems": len(contrast_with), "items": contrast},
            "pitfalls": {"type": "array", "minItems": len(error_tags), "maxItems": len(error_tags), "items": pitfall},
            "note": {"type": ["object", "null"], "additionalProperties": False, "required": ["text"],
                      "properties": {"text": locale_map}},
        },
    }


_PATTERN_ROLES = [
    "subject", "verb", "aux", "object", "complement", "classifier", "time", "place", "marker", "particle", "connector",
    "other",
]
_TIMELINE_SHAPES = [
    "point_past", "ongoing_now", "unspecified_past", "habit", "future_condition", "future_plan", "past_ongoing",
]


V04_EXAMPLES = 3
V04_MAX_TOKENS = 8192  # zh output carries per-character pinyin on every string
# Whitespace touching a Han character or the blank (what validate's zh.whitespace reports).
_ZH_SPACE_RUN = re.compile(
    rf"\s+(?={_HAN.pattern}|{QUICK_PRACTICE_BLANK})|(?<={_HAN.pattern})\s+|(?<={QUICK_PRACTICE_BLANK})\s+"
)


def _item_schemas_v04(*, locales: list[str], l1s: list[str], error_tags: list[str], engine_tags: list[str],
                      contrast_with: list[str], zh: bool) -> dict[str, Any]:
    """The model-side schema of each repeated item of a v0.4 point (slot, example, compare item,
    common mistake, quick-practice item). Shared by full generation and by block-level regeneration
    (apply_feedback.py), so both ask for, and assemble, exactly the same shapes."""
    locale_map = {"type": "string", "minLength": 1} if len(locales) == 1 else _locale_map_schema(locales)
    # Pinyin is derived deterministically in code. The model may still provide
    # character/syllable hints for contextual polyphonic readings, but malformed
    # hints must never make an otherwise valid grammar point fail generation.
    pinyin_pairs = {"type": "array", "items": {}}

    def with_pinyin(schema: dict[str, Any], *fields: str) -> dict[str, Any]:
        if zh:
            for name in fields:
                schema["properties"][name] = pinyin_pairs
        return schema

    slot_option = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["text"],
        "properties": {"text": {"type": "string", "minLength": 1}},
    }, "pinyin_pairs")
    slot = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["text", "role", "label", "optional", "options"],
        "properties": {
            "text": {"type": "string", "minLength": 1}, "role": {"enum": _PATTERN_ROLES},
            "label": locale_map, "optional": {"type": "boolean"},
            "options": {"type": "array", "items": slot_option},
        },
    }, "pinyin_pairs")
    span = {
        "type": "object", "additionalProperties": False, "required": ["text", "role"],
        "properties": {"text": {"type": "string", "minLength": 1}, "role": {"enum": _PATTERN_ROLES}},
    }
    example = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["text", "form", "spans", "annotation", "translation"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "form": {"enum": ["affirmative", "negative", "question"]},
            "spans": {"type": "array", "minItems": 1, "items": span},
            "annotation": locale_map,
            "translation": locale_map,
        },
    }, "pinyin_pairs")
    compare_item = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["with", "this_meaning", "this_example", "other_meaning", "other_example"],
        "properties": {
            "with": {"enum": contrast_with} if contrast_with else {"type": "string"},
            "this_meaning": locale_map, "this_example": {"type": "string", "minLength": 1},
            "other_meaning": locale_map, "other_example": {"type": "string", "minLength": 1},
        },
    }, "this_example_pinyin_pairs", "other_example_pinyin_pairs")
    common_mistake = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["wrong", "right", "reason", "error_tag", "l1"],
        "properties": {
            "wrong": {"type": "string", "minLength": 1}, "right": {"type": "string", "minLength": 1},
            "reason": locale_map,
            "error_tag": {"enum": error_tags} if error_tags else {"type": "string"},
            "l1": {"type": "array", "minItems": 1, "items": {"enum": l1s} if l1s else {"type": "string"}},
        },
    }, "wrong_pinyin_pairs", "right_pinyin_pairs")
    option = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["text", "error_tag"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "error_tag": {"enum": [*engine_tags, None]} if engine_tags else {"type": ["string", "null"]},
        },
    }, "pinyin_pairs")
    quick_practice_item = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["q", "options", "answer", "explain"],
        "properties": {
            "q": {"type": "string", "minLength": 1},
            "options": {"type": "array", "minItems": 2, "maxItems": 3, "items": option},
            "answer": {"type": "integer", "minimum": 0, "maximum": 2},
            "explain": locale_map,
        },
    }, "q_pinyin_pairs")
    rule_slot = {
        "type": "object", "additionalProperties": False, "required": ["role", "any_of", "regex"],
        "properties": {
            "role": {"enum": _PATTERN_ROLES},
            # exactly one of the two is filled: the other is an empty list / empty string
            "any_of": {
                "type": "array", "maxItems": PERSONAL_PRODUCTION_MAX_ANY_OF,
                "items": {"type": "string", "minLength": 1},
            },
            "regex": {"type": "string"},
        },
    }
    personal_production = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["prompt", "placeholder", "target_form", "pattern_rule", "sample"],
        "properties": {
            "prompt": locale_map,
            "placeholder": {"type": "string", "minLength": 1},
            "target_form": {"enum": ["affirmative", "negative", "question"]},
            "pattern_rule": {
                "type": "object", "additionalProperties": False, "required": ["ordered", "slots"],
                "properties": {
                    "ordered": {"type": "boolean"},
                    "slots": {
                        "type": "array", "minItems": 1, "maxItems": PERSONAL_PRODUCTION_MAX_SLOTS,
                        "items": rule_slot,
                    },
                },
            },
            "sample": {"type": "string", "minLength": 1},
        },
    }, "placeholder_pinyin_pairs", "sample_pinyin_pairs")
    return {
        "locale_map": locale_map, "pinyin_pairs": pinyin_pairs, "with_pinyin": with_pinyin, "slot": slot,
        "example": example, "compare_item": compare_item, "common_mistake": common_mistake,
        "quick_practice_item": quick_practice_item, "personal_production": personal_production,
    }


def _generation_schema_v04(*, locales: list[str], l1s: list[str], error_tags: list[str], engine_tags: list[str],
                            contrast_with: list[str], point_type: str, zh: bool,
                            r5_ids: list[str] | None = None) -> dict[str, Any]:
    """GRAMMAR_CONTENT_CONTRACT.md: the model's output for a schema_version 0.4 point.

    Built per point, so nothing here needs if/then (not every provider's structured-output
    dialect supports it): the illustration kind is fixed by point_type in code, and only
    the data that kind needs is asked for. Things the model is bad at are moved to code:
    full-generation examples bind exact substrings to formula slot indexes and generate.py
    derives stored span roles/offsets from those bindings; zh pinyin is given as
    [character, syllable] pairs so the alignment is explicit; and with a single
    explanation locale every explanation field is a plain string that generate.py files
    under that locale (live DeepSeek runs kept malforming one-key locale objects inside
    arrays -- `[ "vi": "..." ]`)."""
    items = _item_schemas_v04(
        locales=locales, l1s=l1s, error_tags=error_tags, engine_tags=engine_tags, contrast_with=contrast_with, zh=zh,
    )
    locale_map, pinyin_pairs, with_pinyin = items["locale_map"], items["pinyin_pairs"], items["with_pinyin"]
    slot, example, compare_item = items["slot"], items["example"], items["compare_item"]
    common_mistake, quick_practice_item = items["common_mistake"], items["quick_practice_item"]

    # Full-point generation uses slot-index bindings instead of asking the model
    # to duplicate formula roles inside example spans. The stored v0.4 schema is
    # unchanged: assemble code derives each stored span role from the selected
    # formula slot. Block-level review regeneration keeps the historical span
    # shape through _item_schemas_v04.
    generated_example = copy.deepcopy(example)
    generated_example["required"] = [
        "bindings" if name == "spans" else name
        for name in generated_example["required"]
    ]
    generated_example["properties"].pop("spans", None)
    generated_example["properties"]["bindings"] = {
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["slot_index", "text"],
            "properties": {
                "slot_index": {"type": "integer", "minimum": 0},
                "text": {"type": "string", "minLength": 1},
            },
        },
    }

    generated_production = copy.deepcopy(items["personal_production"])
    generated_rule_slot = (
        generated_production["properties"]["pattern_rule"]["properties"]
        ["slots"]["items"]
    )
    generated_rule_slot["required"] = [
        "slot_index" if name == "role" else name
        for name in generated_rule_slot["required"]
    ]
    generated_rule_slot["properties"].pop("role", None)
    generated_rule_slot["properties"]["slot_index"] = {"type": "integer", "minimum": 0}

    formula = {"type": "array", "minItems": 1, "items": slot}
    mistake_count = max(1, len(error_tags))
    properties: dict[str, Any] = {
        "summary": locale_map,
        "sub": locale_map,
        "when_to_use": {"type": "array", "minItems": 2, "maxItems": 4, "items": locale_map},
        "formula": formula,
        "negative": {"type": "array", "items": slot},
        "question": {"type": "array", "items": slot},
        "examples": {
            "type": "array", "minItems": V04_EXAMPLES, "maxItems": V04_EXAMPLES,
            "items": generated_example,
        },
        "compare": {"type": "array", "minItems": len(contrast_with), "maxItems": len(contrast_with), "items": compare_item},
        "common_mistakes": {"type": "array", "minItems": mistake_count, "maxItems": mistake_count, "items": common_mistake},
        "quick_practice": {"type": "array", "minItems": 3, "maxItems": 3, "items": quick_practice_item},
        "personal_production": generated_production,
    }
    if zh:  # the point's own name is carried over, not generated, but its pinyin still has to be written
        properties["native_title_pinyin_pairs"] = pinyin_pairs
    if point_type == "tense_aspect":
        properties["timeline_shape"] = {"enum": _TIMELINE_SHAPES}
    elif point_type == "morphology":
        properties["morphology"] = {
            "type": "array", "minItems": 1, "maxItems": 4,
            "items": with_pinyin({
                "type": "object", "additionalProperties": False, "required": ["base", "affix", "result"],
                "properties": {
                    "base": {"type": "string", "minLength": 1}, "affix": {"type": "string", "minLength": 1},
                    "result": {"type": "string", "minLength": 1},
                },
            }, "base_pinyin_pairs", "affix_pinyin_pairs", "result_pinyin_pairs"),
        }
    if r5_ids:
        # Conversion mode: the model says what it corrected in the R5 source, so verify can have
        # the other-family model confirm it and the human learns where R5 was wrong.
        properties["r5_corrections"] = {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["r5_id", "issue", "fix"],
                "properties": {
                    "r5_id": {"enum": list(r5_ids)},
                    "issue": {"type": "string", "minLength": 1},
                    "fix": {"type": "string", "minLength": 1},
                },
            },
        }
    required = [
        name for name in properties
        if not (zh and name == "native_title_pinyin_pairs")
    ]
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}


# Conversion mode (human, 2026-09-28): R5 is raw material, not discarded.
_R5_INSTRUCTION = """
## Converting from R5

The user message carries the app's current lesson(s) for this point ("R5"). Use them as raw
material: keep what is right (a good example, a real learner mistake, a clear rule), restructure
it into this schema, **correct** anything wrong (a wrong rule, an ungrammatical example, a
mistake that is not one, a level-inappropriate word) and **add** what is missing (the formula,
the variants, formula-slot bindings for examples, the comparison, the quick check). Do not carry an error over. List every
correction you made to R5's content in `r5_corrections` (which lesson, what was wrong, what you
wrote instead) -- another model checks each one; leave it empty if R5 needed none. Scope stays
this point's: if an R5 lesson covers more than this point, take only this point's part.
"""

_ILLUSTRATION_INSTRUCTIONS = {
    "tense_aspect": (
        "This point is about *when* things happen, so the app draws a timeline: fill `timeline_shape` "
        "with the one shape from the closed list that matches it."
    ),
    "word_order": (
        "This point is about the *order* of the parts, so the app draws the formula slots themselves as "
        "ordered boxes -- make the formula's slot order exactly the order a sentence follows. No extra data."
    ),
    "morphology": (
        "This point is about how a *word changes form*, so the app draws base + affix -> result: fill "
        "`morphology` with 1-4 items (e.g. book + -s -> books, city + -ies -> cities), covering the "
        "spelling cases a learner actually meets. If the formula keeps the base and the affix as "
        "separate slots (`N` + `-s/-es`), bind them separately in every example, in order: the base "
        "(`book`), then the affix alone (`s`). An irregular form with no separable affix (children) "
        "does not fit such a formula -- use regular forms in the examples."
    ),
    "other": "No illustration for this point -- the formula carries it.",
}

_PINYIN_INSTRUCTION = """
## Pinyin (zh-Hans)

Pinyin alignment is a code responsibility. You may omit every `*_pinyin_pairs` field.
Only provide a pair when a context-sensitive/polyphonic Han reading should override the
deterministic baseline (for example `["行", "háng"]` in 银行). An override is one Han
character plus one tone-marked syllable. Never provide pinyin pairs for punctuation, Latin
text, spaces, or the `___` blank.
"""


def _header_metadata(existing: dict[str, Any], locales: list[str]) -> dict[str, Any]:
    """Prompt-facing structural metadata, carried over exactly from the catalogue.

    Keep this byte-for-byte stable with the canonical source because it participates in
    the provider cache key. Learner-facing Chinese normalization happens only when the
    assembled point is stored.
    """
    if "header" in existing:
        header = existing["header"]
        return {"title": header["title"], "native_title": header["native_title"], "level": dict(existing["level"])}
    title = existing["title"]
    native = title.get(existing["target_lang"]) or title.get("en") or title["vi"]
    return {
        "title": {locale: title[locale] for locale in locales if locale in title} or {"vi": title["vi"]},
        "native_title": native,
        "level": dict(existing["level"]),
    }


def _stored_header_metadata(header: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Normalize only the learner-facing stored header, never prompt/cache input."""
    out = copy.deepcopy(header)
    out["native_title"] = target_text(str(out["native_title"]), zh)
    return out


def resolve_spans(text: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn model-given span substrings into character offsets. Spans are listed in sentence
    order, so each is looked for first after the previous one (which is what lets a base and
    its affix be spanned separately: `book`, then the `s` right after it), then anywhere it
    does not overlap a span already placed. A substring that is not in the sentence is
    dropped -- validate then flags the formula role it was meant to cover, rather than
    generate inventing an offset."""
    placed: list[dict[str, Any]] = []
    cursor = 0

    def free(start: int, end: int) -> bool:
        return all(end <= other["start"] or start >= other["end"] for other in placed)

    for span in spans:
        needle = span["text"]
        found = None
        for origin in (cursor, 0):
            start = text.find(needle, origin)
            while start != -1 and not free(start, start + len(needle)):
                start = text.find(needle, start + 1)
            if start != -1:
                found = start
                break
        if found is not None:
            placed.append({"start": found, "end": found + len(needle), "role": span["role"]})
            cursor = found + len(needle)
    return sorted(placed, key=lambda s: s["start"])


def pinyin_from_pairs(text: str, pairs: list[Any] | None = None) -> list[str]:
    """Return exactly one pinyin entry per character of text.

    pypinyin supplies the deterministic baseline. Model-provided pairs are only
    accepted as contextual overrides when they align to the same Han character
    and already carry a validator-legal tone-marked syllable. Punctuation,
    Latin text, spaces and blanks always map to an empty string.
    """
    fallback = lazy_pinyin(
        text,
        style=Style.TONE,
        neutral_tone_with_five=False,
        errors=lambda chars: ["" for _ in chars],
        strict=False,
    )
    if len(fallback) != len(text):
        fallback = ["" for _ in text]

    out = [
        syllable if _HAN.fullmatch(char) and _PINYIN_SYLLABLE.fullmatch(str(syllable).casefold()) else ""
        for char, syllable in zip(text, fallback, strict=True)
    ]

    cursor = 0
    for pair in pairs or []:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        char, syllable = str(pair[0]), str(pair[1])
        if len(char) != 1:
            continue
        pos = text.find(char, cursor)
        if pos < 0:
            continue
        cursor = pos + 1
        if _HAN.fullmatch(char):
            if _PINYIN_SYLLABLE.fullmatch(syllable.casefold()):
                out[pos] = syllable
        else:
            out[pos] = ""
    return out


def unspaced_pairs(pairs: list[list[str]]) -> list[list[str]]:
    """The pinyin pairs of a string whose spaces zh_unspaced removes: drop the pairs of the spaces."""
    return [pair for pair in pairs if not pair[0].isspace()]


def zh_unspaced(text: str) -> str:
    """Remove spaces touching Han text or the cloze blank.

    Pinyin is now derived after text normalization, so this is safe for every
    target-language field, not only quick-practice questions.
    """
    return _ZH_SPACE_RUN.sub("", text)


def target_text(text: str, zh: bool) -> str:
    return zh_unspaced(text) if zh else text


def assemble_example(raw: dict[str, Any], zh: bool, loc: Any) -> dict[str, Any]:
    """Model output -> stored example, with target text normalized before offsets/pinyin."""
    text = target_text(raw["text"], zh)
    spans = [
        {**span, "text": target_text(span["text"], zh)}
        for span in raw["spans"]
    ]
    example = {
        "text": text, "form": raw["form"], "spans": resolve_spans(text, spans),
        "annotation": loc(raw["annotation"]), "translation": loc(raw["translation"]),
    }
    if zh:
        example["pinyin"] = pinyin_from_pairs(text, raw.get("pinyin_pairs"))
    return example



def _formula_for_generated_form(pattern: dict[str, Any], form: str) -> list[dict[str, Any]] | None:
    if form == "affirmative":
        return pattern["formula"]
    return pattern.get("variants", {}).get(form)




def _locate_generated_bindings(
    text: str, bindings: list[dict[str, Any]], zh: bool,
) -> dict[int, tuple[int, int, str]] | None:
    """Locate all declared binding substrings without assuming formula order.

    Repeated words are allowed. A small backtracking search chooses the first
    deterministic non-overlapping placement, so one repeated pronoun/article no
    longer disables structural order recovery for the whole example.
    """
    items: list[tuple[int, str, list[tuple[int, int]]]] = []
    seen_slots: set[int] = set()
    for binding in bindings:
        slot_index = binding.get("slot_index")
        if not isinstance(slot_index, int) or slot_index in seen_slots:
            return None
        seen_slots.add(slot_index)
        needle = target_text(str(binding.get("text", "")), zh)
        if not needle:
            return None
        positions: list[tuple[int, int]] = []
        start = text.find(needle)
        while start >= 0:
            positions.append((start, start + len(needle)))
            start = text.find(needle, start + 1)
        if not positions:
            return None
        items.append((slot_index, needle, positions))

    # Most-constrained binding first keeps the search tiny while retaining
    # deterministic leftmost placement within each candidate list.
    items.sort(key=lambda item: (len(item[2]), item[0]))
    placed: dict[int, tuple[int, int, str]] = {}

    def search(index: int) -> bool:
        if index >= len(items):
            return True
        slot_index, needle, positions = items[index]
        for begin, finish in positions:
            if any(
                not (finish <= other_begin or begin >= other_finish)
                for other_begin, other_finish, _ in placed.values()
            ):
                continue
            placed[slot_index] = (begin, finish, needle)
            if search(index + 1):
                return True
            placed.pop(slot_index, None)
        return False

    return dict(placed) if search(0) else None


def normalize_generated_optional_suffix_bindings(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Shorten a proven optional suffix when the next slot realizes that suffix.

    Chinese slots such as ``没(有)`` can surface as either ``没`` or ``没有``.
    When a provider binds the long form ``没有`` to that slot and also binds
    the following verb slot to the overlapping suffix ``有``, assembly cannot
    produce non-overlapping spans. Recover only when the formula itself proves
    the short/long alternation (closed options or one parenthesized suffix),
    and the rewritten bindings have a deterministic ordered surface placement.
    Otherwise leave the candidate unchanged.
    """
    out = copy.deepcopy(data)
    if not zh:
        return out

    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}

    def proven_short_form(slot: dict[str, Any], long_surface: str, suffix: str) -> str | None:
        if not suffix or not long_surface.endswith(suffix) or len(long_surface) <= len(suffix):
            return None
        short = long_surface[:-len(suffix)]
        options = {
            target_text(str(option.get("text", "")), True)
            for option in slot.get("options") or []
            if isinstance(option, dict)
        }
        if short in options and long_surface in options:
            return short

        hint = target_text(str(slot.get("text", "")), True)
        match = re.fullmatch(r"(.+?)[(（]([^()（）]+)[)）]", hint)
        if match and match.group(1) == short and match.group(2) == suffix:
            return short
        return None

    for example in out.get("examples", []):
        key = form_keys.get(example.get("form"))
        formula = out.get(key) if key else None
        if not formula:
            continue

        bindings = example.get("bindings") or []
        indexed: dict[int, dict[str, Any]] = {}
        valid = True
        for binding in bindings:
            slot_index = binding.get("slot_index")
            if (
                type(slot_index) is not int
                or not 0 <= slot_index < len(formula)
                or slot_index in indexed
            ):
                valid = False
                break
            indexed[slot_index] = binding
        if not valid:
            continue

        sentence = target_text(str(example.get("text", "")), True)
        for left_index in sorted(indexed):
            right_index = left_index + 1
            if right_index not in indexed:
                continue

            left_binding = indexed[left_index]
            right_binding = indexed[right_index]
            long_surface = target_text(str(left_binding.get("text", "")), True)
            suffix = target_text(str(right_binding.get("text", "")), True)
            short = proven_short_form(formula[left_index], long_surface, suffix)
            if not short or sentence.count(long_surface) != 1:
                continue

            long_start = sentence.find(long_surface)
            suffix_start = long_start + len(short)
            if sentence[suffix_start:suffix_start + len(suffix)] != suffix:
                continue

            proposed = copy.deepcopy(bindings)
            for binding in proposed:
                if binding.get("slot_index") == left_index:
                    binding["text"] = short
                    break

            located = _locate_generated_bindings(sentence, proposed, True)
            if located is None:
                continue
            ordered = [located[index] for index in sorted(located)]
            if any(ordered[i][1] > ordered[i + 1][0] for i in range(len(ordered) - 1)):
                continue
            if (
                located[left_index][0] != long_start
                or located[left_index][1] != suffix_start
                or located[right_index][0] != suffix_start
            ):
                continue

            left_binding["text"] = short

    return out


def normalize_generated_formula_order(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Reorder v13 formula slots only from complete, unambiguous consensus evidence.

    Partial examples must never be merged into one synthetic ordering graph. A matching
    example can vote only when it provides an exact binding for every formula slot and
    every valid non-overlapping placement yields the same complete permutation. All
    usable examples for the form must then agree on that permutation. Ambiguity,
    conflicts, malformed complete bindings, or search exhaustion leave the candidate
    unchanged.
    """
    out = copy.deepcopy(data)
    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}

    def complete_surface_order(
        example: dict[str, Any], formula_len: int,
    ) -> tuple[str, tuple[int, ...] | None]:
        bindings = example.get("bindings") or []
        if len(bindings) < formula_len:
            return "incomplete", None
        if len(bindings) != formula_len:
            return "unsafe", None

        indexes = [binding.get("slot_index") for binding in bindings]
        if (
            any(type(index) is not int or not 0 <= index < formula_len for index in indexes)
            or len(set(indexes)) != formula_len
            or set(indexes) != set(range(formula_len))
        ):
            return "unsafe", None

        text = target_text(str(example.get("text", "")), zh)
        items: list[tuple[int, str, list[tuple[int, int]]]] = []
        for binding in bindings:
            slot_index = binding["slot_index"]
            needle = target_text(str(binding.get("text", "")), zh)
            if not needle:
                return "unsafe", None
            positions: list[tuple[int, int]] = []
            begin = text.find(needle)
            while begin >= 0:
                positions.append((begin, begin + len(needle)))
                begin = text.find(needle, begin + 1)
            if not positions:
                return "unsafe", None
            items.append((slot_index, needle, positions))

        items.sort(key=lambda item: (len(item[2]), item[0]))
        placed: dict[int, tuple[int, int, str]] = {}
        orders: set[tuple[int, ...]] = set()
        steps = 0
        exhausted = False

        def search(index: int) -> None:
            nonlocal steps, exhausted
            if exhausted or len(orders) > 1:
                return
            steps += 1
            if steps > 4096:
                exhausted = True
                return
            if index >= len(items):
                orders.add(tuple(
                    slot_index
                    for slot_index, _position in sorted(
                        placed.items(),
                        key=lambda item: (item[1][0], item[1][1], item[0]),
                    )
                ))
                return

            slot_index, needle, positions = items[index]
            for begin, finish in positions:
                if any(
                    not (finish <= other_begin or begin >= other_finish)
                    for other_begin, other_finish, _other_needle in placed.values()
                ):
                    continue
                placed[slot_index] = (begin, finish, needle)
                search(index + 1)
                placed.pop(slot_index, None)
                if exhausted or len(orders) > 1:
                    return

        search(0)
        if exhausted or len(orders) != 1:
            return "unsafe", None
        return "usable", next(iter(orders))

    for form, key in form_keys.items():
        formula = out.get(key) or []
        if len(formula) < 2:
            continue

        consensus: tuple[int, ...] | None = None
        unsafe = False
        used_example = False
        for example in out.get("examples", []):
            if example.get("form") != form:
                continue
            status, order = complete_surface_order(example, len(formula))
            if status == "incomplete":
                continue
            if status != "usable" or order is None:
                unsafe = True
                break
            used_example = True
            if consensus is None:
                consensus = order
            elif consensus != order:
                unsafe = True
                break

        if unsafe or not used_example or consensus is None:
            continue

        order = list(consensus)
        if len(order) != len(formula) or order == list(range(len(formula))):
            continue

        remap = {old: new for new, old in enumerate(order)}
        out[key] = [formula[old] for old in order]

        for example in out.get("examples", []):
            if example.get("form") != form:
                continue
            for binding in example.get("bindings") or []:
                slot_index = binding.get("slot_index")
                if slot_index in remap:
                    binding["slot_index"] = remap[slot_index]

        production = out.get("personal_production") or {}
        if production.get("target_form") == form:
            rule = production.get("pattern_rule") or {}
            for rule_slot in rule.get("slots") or []:
                slot_index = rule_slot.get("slot_index")
                if slot_index in remap:
                    rule_slot["slot_index"] = remap[slot_index]
            if rule.get("ordered"):
                rule["slots"] = sorted(
                    rule.get("slots") or [],
                    key=lambda slot: slot.get("slot_index", len(formula)),
                )

    return out



def _safe_generated_gap_candidate(slot: dict[str, Any], candidate: str, zh: bool) -> bool:
    """Accept only surface shapes that the slot label itself makes unambiguous."""
    slot_hint = str(slot.get("text", "")).casefold()
    if zh:
        phrase_like = any(
            hint in slot_hint
            for hint in ("np", "noun phrase", "clause", "complement", "constituent", "短语", "从句")
        )
        return (
            phrase_like
            and sum(1 for char in candidate if _HAN.fullmatch(char)) >= 2
        )

    tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", candidate)
    phrase_like = any(
        hint in slot_hint
        for hint in (
            "np", "noun phrase", "clause", "complement", "constituent",
            "reported content", "content clause", "object phrase",
        )
    )
    if phrase_like:
        return len(tokens) >= 2

    v3_like = bool(re.search(r"(?:^|[^a-z0-9])v3(?:$|[^a-z0-9])", slot_hint)) or "past participle" in slot_hint
    if v3_like and len(tokens) == 1:
        token = tokens[0].casefold()
        irregular_participles = {
            form.casefold()
            for _past, participle in en_morphology.IRREGULAR_VERBS.values()
            for form in participle.split("/")
        }
        return token in irregular_participles or token.endswith(("ed", "ied"))

    return False


def complete_generated_single_gap_bindings(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Recover exactly one missing required slot from one bounded surface gap.

    No POS/role is guessed. Existing exact bindings determine the only possible
    text interval for the missing formula position, and the slot label must make
    that interval's surface shape safe to accept (for example a phrase/clause,
    or one recognisable English V3 token).
    """
    out = copy.deepcopy(data)
    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}
    trim_chars = " \t\r\n,.;:!?—–()[]{}\"“”"

    for example in out.get("examples", []):
        form = example.get("form")
        key = form_keys.get(form)
        formula = out.get(key) if key else None
        if not formula:
            continue

        bindings = example.get("bindings") or []
        bound_indexes = {
            binding.get("slot_index")
            for binding in bindings
            if isinstance(binding.get("slot_index"), int)
        }
        required = {i for i, slot in enumerate(formula) if not slot.get("optional")}
        missing = sorted(required - bound_indexes)
        if len(missing) != 1:
            continue
        missing_index = missing[0]

        # Any second unbound optional slot makes the uncovered interval
        # structurally ambiguous, so leave it to fail-closed repair.
        if any(
            i not in bound_indexes and i != missing_index and slot.get("optional")
            for i, slot in enumerate(formula)
        ):
            continue

        text = target_text(str(example.get("text", "")), zh)
        located = _locate_generated_bindings(text, bindings, zh)
        if not located and bindings:
            continue

        # Formula order must already agree with the located surface order.
        ordered_bound = sorted(located.items())
        if any(
            ordered_bound[i][1][0] > ordered_bound[i + 1][1][0]
            for i in range(len(ordered_bound) - 1)
        ):
            continue

        left = [
            (slot_index, finish)
            for slot_index, (_begin, finish, _needle) in located.items()
            if slot_index < missing_index
        ]
        right = [
            (slot_index, begin)
            for slot_index, (begin, _finish, _needle) in located.items()
            if slot_index > missing_index
        ]
        start = max(left, default=(-1, 0), key=lambda item: item[0])[1]
        finish = min(right, default=(len(formula), len(text)), key=lambda item: item[0])[1]
        if finish <= start:
            continue

        candidate = text[start:finish].strip(trim_chars)
        if not candidate or not _safe_generated_gap_candidate(
            formula[missing_index], candidate, zh
        ):
            continue

        bindings.append({"slot_index": missing_index, "text": candidate})
        example["bindings"] = bindings

    return out


def complete_generated_terminal_bindings(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Recover one missing edge slot from the only remaining sentence surface.

    This deliberately handles only the first/last required formula slot and only
    when every other required slot is already bound. It does not infer POS or
    grammar roles; it maps the sole uncovered edge phrase to the sole missing
    edge slot. Ambiguous middle gaps remain fail-closed for structural repair.
    """
    out = copy.deepcopy(data)
    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}
    trim_chars = " \t\r\n,.;:!?—–()[]{}\"“”"

    for example in out.get("examples", []):
        form = example.get("form")
        key = form_keys.get(form)
        formula = out.get(key) if key else None
        if not formula:
            continue

        bindings = example.get("bindings") or []
        bound_indexes = {
            binding.get("slot_index")
            for binding in bindings
            if isinstance(binding.get("slot_index"), int)
        }
        required = {i for i, slot in enumerate(formula) if not slot.get("optional")}
        missing = sorted(required - bound_indexes)
        if len(missing) != 1:
            continue
        missing_index = missing[0]
        if missing_index not in {0, len(formula) - 1}:
            continue

        # Do not absorb a distinct unbound optional edge slot into the recovered
        # phrase; that surface would be structurally ambiguous.
        if any(
            i not in bound_indexes and i != missing_index and slot.get("optional")
            for i, slot in enumerate(formula)
        ):
            continue

        text = target_text(str(example.get("text", "")), zh)
        located = _locate_generated_bindings(text, bindings, zh)
        if not located and bindings:
            continue

        if missing_index == 0:
            edge = min((begin for begin, _end, _ in (located or {}).values()), default=len(text))
            candidate = text[:edge].strip(trim_chars)
        else:
            edge = max((_end for _begin, _end, _ in (located or {}).values()), default=0)
            candidate = text[edge:].strip(trim_chars)

        if not candidate or not any(char.isalnum() or _HAN.fullmatch(char) for char in candidate):
            continue

        slot_hint = str(formula[missing_index].get("text", "")).casefold()
        phrase_like = any(
            hint in slot_hint
            for hint in (
                "np", "noun phrase", "clause", "complement", "constituent",
                "reported content", "content clause", "object phrase",
            )
        )
        if not phrase_like:
            continue
        if zh:
            if sum(1 for char in candidate if _HAN.fullmatch(char)) < 2:
                continue
        elif len(re.findall(r"\b\w+\b", candidate)) < 2:
            continue

        bindings.append({"slot_index": missing_index, "text": candidate})
        example["bindings"] = bindings

    return out



def normalize_generated_safe_joiner_slots(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Split only closed, unambiguous generated '+' sequences.

    The stored UI draws '+' between slots, so a provider slot such as
    ``aux + not`` is structurally invalid. For English ``X + not`` only, split
    the slot when every affected surface binding also has the exact form
    ``<X surface> not``. A closed negative-auxiliary option list instead permits
    an atomic ``aux not`` slot, preserving contracted surfaces. Indexes in
    examples and personal production are remapped together. Anything ambiguous
    remains untouched and fails closed.
    """
    if zh:
        return copy.deepcopy(data)

    out = copy.deepcopy(data)
    form_keys = {"affirmative": "formula", "negative": "negative", "question": "question"}

    def negative_auxiliary(surface: Any) -> bool:
        if not isinstance(surface, str):
            return False
        return re.fullmatch(
            r"(?:(?:am|is|are|was|were|be|do|does|did|have|has|had|"
            r"can|could|will|would|shall|should|may|might|must|need|dare)\s+not"
            r"|cannot|(?:is|are|was|were|do|does|did|have|has|had|ca|could|"
            r"wo|would|sha|should|might|must|need|dare)n['’]t)",
            surface.strip(), flags=re.IGNORECASE,
        ) is not None

    for form, key in form_keys.items():
        formula = out.get(key) or []
        if not formula:
            continue

        # A contracted negative auxiliary is one surface unit. If a closed
        # option list and every consumer prove that interpretation, keep it
        # atomic rather than inventing separate spans for e.g. "didn't".
        for old_index, slot in enumerate(formula):
            parts = [part.strip() for part in str(slot.get("text", "")).split("+")]
            options = slot.get("options") or []
            if (
                len(parts) != 2 or parts[0].casefold() not in {"aux", "auxiliary"}
                or parts[1].casefold() != "not" or slot.get("role") != "aux"
                or not options
                or not all(negative_auxiliary(option.get("text")) for option in options)
            ):
                continue
            surfaces = [
                binding.get("text")
                for example in out.get("examples", []) if example.get("form") == form
                for binding in example.get("bindings") or []
                if binding.get("slot_index") == old_index
            ]
            production = out.get("personal_production") or {}
            if production.get("target_form") == form:
                rules = (production.get("pattern_rule") or {}).get("slots") or []
                affected = [rule for rule in rules if rule.get("slot_index") == old_index]
                if any(rule.get("regex") or not rule.get("any_of") for rule in affected):
                    continue
                surfaces.extend(literal for rule in affected for literal in rule["any_of"])
            if surfaces and all(negative_auxiliary(surface) for surface in surfaces):
                slot["text"] = " ".join(parts)

        split_old: dict[int, tuple[str, dict[str, Any], dict[str, Any]]] = {}
        for old_index, slot in enumerate(formula):
            text = str(slot.get("text", ""))
            parts = [part.strip() for part in text.split("+")]
            if (
                len(parts) == 2
                and parts[0]
                and parts[1].casefold() == "not"
                and not slot.get("options")
            ):
                first = copy.deepcopy(slot)
                first["text"] = parts[0]
                second = {
                    "text": "not",
                    "role": "marker",
                    "label": "not",
                    "optional": bool(slot.get("optional", False)),
                    "options": [],
                }
                split_old[old_index] = (parts[0], first, second)

        if not split_old:
            continue

        split_bindings: dict[tuple[int, int], tuple[str, str]] = {}
        safe = True
        for example_index, example in enumerate(out.get("examples", [])):
            if example.get("form") != form:
                continue
            for binding_index, binding in enumerate(example.get("bindings") or []):
                old_index = binding.get("slot_index")
                if old_index not in split_old:
                    continue
                surface = target_text(str(binding.get("text", "")), False)
                match = re.fullmatch(r"(.+?)\s+(not)", surface, flags=re.IGNORECASE)
                if match is None:
                    safe = False
                    break
                split_bindings[(example_index, binding_index)] = (
                    match.group(1),
                    match.group(2),
                )
            if not safe:
                break
        if not safe:
            continue

        production = out.get("personal_production") or {}
        production_rule = production.get("pattern_rule") or {}
        production_split: dict[int, tuple[list[str], list[str]]] = {}
        if production.get("target_form") == form:
            slots = production_rule.get("slots") or []
            for rule_index, rule_slot in enumerate(slots):
                old_index = rule_slot.get("slot_index")
                if old_index not in split_old:
                    continue
                if rule_slot.get("regex"):
                    safe = False
                    break
                any_of = rule_slot.get("any_of") or []
                left_values: list[str] = []
                right_values: list[str] = []
                for literal in any_of:
                    match = re.fullmatch(
                        r"(.+?)\s+(not)",
                        str(literal).strip(),
                        flags=re.IGNORECASE,
                    )
                    if match is None:
                        safe = False
                        break
                    left_values.append(match.group(1))
                    right_values.append(match.group(2))
                if not safe or not left_values:
                    safe = False
                    break
                production_split[rule_index] = (left_values, right_values)
            if not safe or len(slots) + len(production_split) > PERSONAL_PRODUCTION_MAX_SLOTS:
                continue

        new_formula: list[dict[str, Any]] = []
        remap: dict[int, int] = {}
        split_new: dict[int, tuple[int, int]] = {}
        for old_index, slot in enumerate(formula):
            remap[old_index] = len(new_formula)
            if old_index in split_old:
                _left_text, first, second = split_old[old_index]
                first_index = len(new_formula)
                new_formula.extend([first, second])
                split_new[old_index] = (first_index, first_index + 1)
            else:
                new_formula.append(copy.deepcopy(slot))

        out[key] = new_formula

        for example_index, example in enumerate(out.get("examples", [])):
            if example.get("form") != form:
                continue
            rewritten: list[dict[str, Any]] = []
            for binding_index, binding in enumerate(example.get("bindings") or []):
                old_index = binding.get("slot_index")
                if old_index in split_new:
                    left_index, right_index = split_new[old_index]
                    left_text, right_text = split_bindings[(example_index, binding_index)]
                    rewritten.extend([
                        {"slot_index": left_index, "text": left_text},
                        {"slot_index": right_index, "text": right_text},
                    ])
                elif old_index in remap:
                    rewritten.append({
                        **binding,
                        "slot_index": remap[old_index],
                    })
                else:
                    rewritten.append(copy.deepcopy(binding))
            example["bindings"] = rewritten

        if production.get("target_form") == form:
            rewritten_rule: list[dict[str, Any]] = []
            for rule_index, rule_slot in enumerate(production_rule.get("slots") or []):
                old_index = rule_slot.get("slot_index")
                if rule_index in production_split:
                    left_values, right_values = production_split[rule_index]
                    left_index, right_index = split_new[old_index]
                    rewritten_rule.extend([
                        {
                            "slot_index": left_index,
                            "any_of": left_values,
                            "regex": "",
                        },
                        {
                            "slot_index": right_index,
                            "any_of": right_values,
                            "regex": "",
                        },
                    ])
                elif old_index in remap:
                    rewritten_rule.append({
                        **rule_slot,
                        "slot_index": remap[old_index],
                    })
                else:
                    rewritten_rule.append(copy.deepcopy(rule_slot))
            production_rule["slots"] = rewritten_rule

    return out


def normalize_generated_nested_context_slots(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Drop proven discourse context, never a second grammar realization.

    Numbered sentence/clause placeholders with no options denote context;
    explicit substitute/ellipsis slots denote the highlight. Require unique
    exact spans, at least one strict nesting witness, and valid non-overlapping
    surviving bindings in every example. A production rule constraining the
    context cannot be translated mechanically, so it vetoes removal. Unknown
    language realizations and richer context contracts remain fail-closed.
    """
    out = copy.deepcopy(data)
    if zh:
        return out
    realizations = {
        "one", "ones", "do so", "does so", "did so", "done so", "doing so",
        "so", "not", "to", "not to", "neither", "former", "latter", "this", "that",
    }
    for form, key in {"affirmative": "formula", "negative": "negative", "question": "question"}.items():
        formula = out.get(key) or []
        examples = [ex for ex in out.get("examples", []) if ex.get("form") == form]
        for index in reversed(range(len(formula))):
            slot = formula[index]
            if (slot.get("role") not in {"subject", "other"} or slot.get("options")
                    or re.fullmatch(r"(?:S\d+|sentence(?:\s+\d+)?|clause(?:\s+\d+)?)",
                                    str(slot.get("text", "")), re.IGNORECASE) is None):
                continue
            production = out.get("personal_production") or {}
            rules = (production.get("pattern_rule") or {}).get("slots") or []
            if production.get("target_form") == form and any(
                type(rule.get("slot_index")) is not int
                or not 0 <= rule["slot_index"] < len(formula)
                or rule["slot_index"] == index for rule in rules
            ):
                continue
            witnessed = False
            safe = bool(examples)
            for example in examples:
                text = target_text(str(example.get("text", "")), False)
                bindings = example.get("bindings") or []
                indexes = [b.get("slot_index") for b in bindings]
                if (any(type(i) is not int or not 0 <= i < len(formula) for i in indexes)
                        or len(set(indexes)) != len(indexes) or index not in indexes):
                    safe = False
                    break
                context = next(b for b in bindings if b["slot_index"] == index)
                outer = target_text(str(context.get("text", "")), False)
                if not outer or text.count(outer) != 1:
                    safe = False
                    break
                for binding in bindings:
                    inner_index = binding["slot_index"]
                    if inner_index == index:
                        continue
                    inner = target_text(str(binding.get("text", "")), False)
                    if inner and inner != outer and inner in outer:
                        taught = formula[inner_index]
                        hint = str(taught.get("text", "")).casefold()
                        if (hint not in {"substitute", "substitution", "ellipsis"}
                                or inner.casefold() not in realizations
                                or outer.count(inner) != 1 or text.count(inner) != 1
                                or re.search(r"(?<!\w)" + re.escape(inner) + r"(?!\w)", outer) is None):
                            safe = False
                            break
                        witnessed = True
                surviving = [b for b in bindings if b["slot_index"] != index]
                if not safe or not _locate_generated_bindings(text, surviving, False):
                    safe = False
                    break
            if not safe or not witnessed:
                continue
            formula.pop(index)
            for example in examples:
                example["bindings"] = [b for b in example["bindings"] if b["slot_index"] != index]
                for binding in example["bindings"]:
                    if binding["slot_index"] > index:
                        binding["slot_index"] -= 1
            if production.get("target_form") == form:
                for rule in rules:
                    if rule["slot_index"] > index:
                        rule["slot_index"] -= 1
    return out


def normalize_generated_common_prefix_options(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Factor a literal prefix only when all routes and consumers prove it.

    Mixed arities, variable prefixes, unsupported grammatical forms and opaque
    production regexes are deliberately left for validation to reject.
    """
    out = copy.deepcopy(data)
    if zh:
        return out
    for form, key in {"affirmative": "formula", "negative": "negative", "question": "question"}.items():
        # Work backwards so each successful expansion preserves earlier indexes.
        for index in reversed(range(len(out.get(key) or []))):
            slot = out[key][index]
            options = slot.get("options") or []
            routes = [str(option.get("text", "")).split("+") for option in options]
            routes = [[part.strip() for part in route] for route in routes]
            if not routes or any(len(route) < 2 for route in routes):
                continue
            prefix = routes[0][:-1]
            if (any(route[:-1] != prefix for route in routes)
                    or any(re.fullmatch(r"[a-z]+", part) is None for part in prefix)
                    or any(route[-1] not in {"V-ing", "to-infinitive", "that-clause"} for route in routes)):
                continue
            tails = list(dict.fromkeys(route[-1] for route in routes))
            shapes = {"V-ing": r"[A-Za-z]+ing\b.*", "to-infinitive": r"to\s+[A-Za-z]+\b.*",
                      "that-clause": r"that\s+.+"}

            def split(surface: Any) -> list[str] | None:
                if not isinstance(surface, str):
                    return None
                match = re.fullmatch(
                    r"\s*" + r"\s+".join("(" + re.escape(part) + ")" for part in prefix)
                    + r"\s+(.+?)\s*", surface, flags=re.IGNORECASE)
                if match is None:
                    return None
                tail = match.group(len(prefix) + 1)
                if sum(re.fullmatch(shapes[kind], tail, re.IGNORECASE) is not None for kind in tails) != 1:
                    return None
                return list(match.groups())

            examples = [example for example in out.get("examples", []) if example.get("form") == form]
            affected = [binding for example in examples for binding in example.get("bindings", [])
                        if binding.get("slot_index") == index]
            if not examples or len(affected) != len(examples) or any(split(binding.get("text")) is None for binding in affected):
                continue
            if any(not any(re.fullmatch(shapes[kind], split(binding["text"])[-1], re.IGNORECASE)
                           for binding in affected) for kind in tails):
                continue
            # Require exact, uniquely located, non-overlapping evidence in sentence text.
            if any(target_text(example["text"], False).count(binding["text"]) != 1
                   for example in examples for binding in example.get("bindings", [])
                   if binding.get("slot_index") == index):
                continue
            if any(_locate_generated_bindings(target_text(example["text"], False), example.get("bindings", []), False) is None
                   for example in examples):
                continue
            production = out.get("personal_production") or {}
            rules = ((production.get("pattern_rule") or {}).get("slots") or []) if production.get("target_form") == form else []
            selected = [rule for rule in rules if rule.get("slot_index") == index]
            if any(rule.get("regex") or not rule.get("any_of") or any(split(value) is None for value in rule["any_of"])
                   for rule in selected):
                continue
            if len(rules) + len(prefix) * len(selected) > PERSONAL_PRODUCTION_MAX_SLOTS:
                continue
            expanded = [{"text": part, "role": "marker", "label": part,
                         "optional": bool(slot.get("optional")), "options": []} for part in prefix]
            expanded.append({**copy.deepcopy(slot), "options": [{"text": tail} for tail in tails]})
            out[key][index:index + 1] = expanded
            for example in examples:
                rewritten = []
                for binding in example.get("bindings", []):
                    old = binding.get("slot_index")
                    if old == index:
                        rewritten.extend({**binding, "slot_index": index + offset, "text": value}
                                         for offset, value in enumerate(split(binding["text"])))
                    else:
                        rewritten.append({**binding, "slot_index": old + len(prefix) if isinstance(old, int) and old > index else old})
                example["bindings"] = rewritten
            if rules:
                rewritten = []
                for rule in rules:
                    old = rule.get("slot_index")
                    if old == index:
                        values = [split(value) for value in rule["any_of"]]
                        rewritten.extend({**rule, "slot_index": index + offset,
                                          "any_of": list(dict.fromkeys(parts[offset] for parts in values))}
                                         for offset in range(len(prefix) + 1))
                    else:
                        rewritten.append({**rule, "slot_index": old + len(prefix) if isinstance(old, int) and old > index else old})
                production["pattern_rule"]["slots"] = rewritten
    return out



_ZH_QUESTION_WORD_SURFACES = frozenset({
    "谁", "什么", "哪", "哪儿", "哪里", "几", "多少", "怎么", "怎么样", "为什么",
    "什么时候", "多久", "多长时间", "多大", "多高", "多远", "哪天", "哪年", "几点",
})


def _question_frame_label(example: Any, kind: str) -> Any:
    labels = {
        "before": {
            "vi": "phần đứng trước từ để hỏi",
            "en": "context before the question word",
            "zh-Hans": "疑问词前的成分",
        },
        "question": {
            "vi": "từ để hỏi ở đúng vị trí của phần cần hỏi",
            "en": "question word in the missing information's original position",
            "zh-Hans": "疑问词保留在原来的位置",
        },
        "after": {
            "vi": "phần đứng sau từ để hỏi",
            "en": "context after the question word",
            "zh-Hans": "疑问词后的成分",
        },
    }
    if isinstance(example, dict):
        return {locale: labels[kind].get(locale, labels[kind]["en"]) for locale in example}
    if isinstance(example, str):
        return labels[kind]["vi"]
    return labels[kind]["vi"]


def normalize_generated_question_word_frame(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Repair zh.question_words into an in-place question-word position frame.

    Chinese interrogative pronouns stay where the missing information belongs. A
    cached candidate may instead force every question into S-V-O; locatives such
    as ``你在哪儿工作？`` then bind ``哪儿`` inside ``在哪儿工作``. Reordering cannot
    make that analysis truthful, so this point-specific normalizer represents the
    actual invariant directly: context before + question word + context after.

    The repair remains fail-closed unless every question example contains exactly
    one recognised interrogative binding, at least one example proves a strict
    overlap with another binding, and question-form production rules constrain only
    recognised interrogative literals.
    """
    out = copy.deepcopy(data)
    if not zh:
        return out

    formula = out.get("question") or []
    examples = [example for example in out.get("examples", []) if example.get("form") == "question"]
    if not formula or not examples:
        return out

    production = out.get("personal_production") or {}
    production_rule = production.get("pattern_rule") or {}
    production_slots = (
        production_rule.get("slots") or []
        if production.get("target_form") == "question"
        else []
    )
    if production.get("target_form") == "question":
        for rule in production_slots:
            values = rule.get("any_of") or []
            if (
                rule.get("regex")
                or not values
                or any(target_text(str(value), True) not in _ZH_QUESTION_WORD_SURFACES for value in values)
            ):
                return out

    records: list[tuple[dict[str, Any], str, str, str]] = []
    overlap_witness = False
    question_values: list[str] = []

    for example in examples:
        text = target_text(str(example.get("text", "")), True)
        bindings = example.get("bindings") or []
        question_bindings = [
            binding
            for binding in bindings
            if target_text(str(binding.get("text", "")), True) in _ZH_QUESTION_WORD_SURFACES
        ]
        if len(question_bindings) != 1:
            return out

        question_binding = question_bindings[0]
        q_surface = target_text(str(question_binding.get("text", "")), True)
        positions: list[int] = []
        start = text.find(q_surface)
        while start >= 0:
            positions.append(start)
            start = text.find(q_surface, start + 1)
        if len(positions) != 1:
            return out
        q_start = positions[0]
        q_end = q_start + len(q_surface)

        for binding in bindings:
            if binding is question_binding:
                continue
            surface = target_text(str(binding.get("text", "")), True)
            if not surface:
                continue
            starts: list[int] = []
            begin = text.find(surface)
            while begin >= 0:
                starts.append(begin)
                begin = text.find(surface, begin + 1)
            if len(starts) != 1:
                continue
            begin = starts[0]
            finish = begin + len(surface)
            if begin <= q_start and q_end <= finish and (begin < q_start or q_end < finish):
                overlap_witness = True

        prefix = text[:q_start].strip()
        suffix = text[q_end:].strip().rstrip("？?。.!！").strip()
        if not prefix and not suffix:
            return out
        records.append((example, prefix, q_surface, suffix))
        if q_surface not in question_values:
            question_values.append(q_surface)

    if not overlap_witness:
        return out

    sample_label = formula[0].get("label") if formula else ""
    out["question"] = [
        {
            "text": "…",
            "role": "other",
            "label": _question_frame_label(sample_label, "before"),
            "optional": True,
            "options": [],
        },
        {
            "text": "疑问词",
            "role": "other",
            "label": _question_frame_label(sample_label, "question"),
            "optional": False,
            "options": [{"text": value} for value in question_values],
        },
        {
            "text": "…",
            "role": "other",
            "label": _question_frame_label(sample_label, "after"),
            "optional": True,
            "options": [],
        },
    ]

    for example, prefix, q_surface, suffix in records:
        rewritten: list[dict[str, Any]] = []
        if prefix:
            rewritten.append({"slot_index": 0, "text": prefix})
        rewritten.append({"slot_index": 1, "text": q_surface})
        if suffix:
            rewritten.append({"slot_index": 2, "text": suffix})
        example["bindings"] = rewritten

    if production.get("target_form") == "question":
        for rule in production_slots:
            rule["slot_index"] = 1
        production_rule["ordered"] = True

    return out

def normalize_generated_missing_question_variant(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Reuse the proven base pattern when a Chinese question variant is omitted.

    Some lexical/word-order points use the same taught pattern inside statements and
    questions. DeepSeek can label an example as ``question`` while omitting the
    structurally identical ``question`` formula, which makes assembly emit no spans.

    Recover only for Chinese, only when the question variant is absent, at least one
    affirmative example proves the base formula, and every question example already
    binds that same base formula completely and in order. No bindings or learner-facing
    text are invented. English stays fail-closed because question formation can reorder
    or add auxiliaries.
    """
    out = copy.deepcopy(data)
    if not zh or out.get("question"):
        return out

    formula = out.get("formula") or []
    if not formula:
        return out

    indexed_examples = list(enumerate(out.get("examples") or []))
    affirmative = [(index, example) for index, example in indexed_examples if example.get("form") == "affirmative"]
    questions = [(index, example) for index, example in indexed_examples if example.get("form") == "question"]
    if not affirmative or not questions or not any(example.get("bindings") for _index, example in questions):
        return out

    proof_pattern = {"formula": formula, "variants": {"question": formula}}

    affirmative_proven = False
    for index, example in affirmative:
        _assembled, problems = assemble_generated_example(
            example, proof_pattern, True, lambda value: value, index
        )
        if not problems:
            affirmative_proven = True
            break
    if not affirmative_proven:
        return out

    for index, example in questions:
        _assembled, problems = assemble_generated_example(
            example, proof_pattern, True, lambda value: value, index
        )
        if problems:
            return out

    production = out.get("personal_production") or {}
    if production.get("target_form") == "question":
        rules = (production.get("pattern_rule") or {}).get("slots") or []
        if any(
            type(rule.get("slot_index")) is not int
            or not 0 <= rule["slot_index"] < len(formula)
            for rule in rules
        ):
            return out

    out["question"] = copy.deepcopy(formula)
    return out


def normalize_generated_structure(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Return the exact structural candidate that full assembly validates."""
    out = normalize_generated_optional_suffix_bindings(data, zh)
    out = normalize_generated_common_prefix_options(out, zh)
    out = normalize_generated_safe_joiner_slots(out, zh)
    out = normalize_generated_nested_context_slots(out, zh)
    out = normalize_generated_missing_question_variant(out, zh)
    out = normalize_generated_formula_order(out, zh)
    out = complete_generated_single_gap_bindings(out, zh)
    out = complete_generated_terminal_bindings(out, zh)
    return normalize_generated_formula_order(out, zh)


def assemble_generated_example(
    raw: dict[str, Any], pattern: dict[str, Any], zh: bool, loc: Any, index: int,
) -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    """Assemble a full-generation example from formula-slot bindings.

    The provider never assigns a role. It identifies the selected formula slot
    by zero-based index and quotes the exact surface substring. Code derives the
    stored role from that slot and requires every non-optional slot exactly once.
    """
    text = target_text(raw["text"], zh)
    form = raw["form"]
    formula = _formula_for_generated_form(pattern, form)
    example: dict[str, Any] = {
        "text": text,
        "form": form,
        "spans": [],
        "annotation": loc(raw["annotation"]),
        "translation": loc(raw["translation"]),
    }
    if zh:
        example["pinyin"] = pinyin_from_pairs(text, raw.get("pinyin_pairs"))

    # The normal validator owns the form-without-variant error.
    if formula is None:
        return example, []

    problems: list[tuple[str, str, str]] = []
    by_index: dict[int, str] = {}
    for binding_index, binding in enumerate(raw.get("bindings") or []):
        slot_index = binding.get("slot_index")
        path = f"examples[{index}].bindings[{binding_index}]"
        if not isinstance(slot_index, int) or not 0 <= slot_index < len(formula):
            problems.append((
                path + ".slot_index",
                "generation.binding_slot_invalid",
                f"slot_index {slot_index!r} is outside the {form} formula of {len(formula)} slot(s)",
            ))
            continue
        if slot_index in by_index:
            problems.append((
                path + ".slot_index",
                "generation.binding_slot_duplicate",
                f"formula slot {slot_index} is bound more than once",
            ))
            continue
        by_index[slot_index] = target_text(str(binding["text"]), zh)

    required = {i for i, slot in enumerate(formula) if not slot.get("optional")}
    missing = sorted(required - set(by_index))
    for slot_index in missing:
        problems.append((
            f"examples[{index}].bindings",
            "generation.binding_required_slot_missing",
            f"required {form} formula slot {slot_index} ({formula[slot_index]['text']!r}) has no binding",
        ))

    cursor = 0
    spans: list[dict[str, Any]] = []
    for slot_index in sorted(by_index):
        needle = by_index[slot_index]
        start = text.find(needle, cursor)
        if start < 0:
            problems.append((
                f"examples[{index}].bindings",
                "generation.binding_text_order",
                f"slot {slot_index} binding {needle!r} is not an exact substring after the previous bound slot",
            ))
            continue
        end = start + len(needle)
        spans.append({"start": start, "end": end, "role": formula[slot_index]["role"]})
        cursor = end

    example["spans"] = spans
    return example, problems



V04_STRUCTURE_REPAIR_MAX_TOKENS = 1600

_GENERATION_STRUCTURE_DERIVATIVE_CODES = {
    "example.formula_role_missing",
    "example.span_role_not_in_formula",
    "example.span_slot_mismatch",
    "personal_production.rule_invalid",
    "personal_production.rule_role_not_in_formula",
    "personal_production.rule_rejects_sample",
    "personal_production.rule_rejects_example",
    "formula.slot_has_joiner",
}


def can_repair_generation_structure(issues: list[Any]) -> bool:
    """Route raw binding failures and invalid in-slot joiners to structure repair."""
    return any(
        str(getattr(issue, "code", "")).startswith("generation.")
        or str(getattr(issue, "code", "")) == "formula.slot_has_joiner"
        for issue in issues
    )


def generation_structure_repair_issues(issues: list[Any]) -> list[Any]:
    """Only the issues a structure-only patch is allowed to act on."""
    return [
        issue
        for issue in issues
        if (
            str(getattr(issue, "code", "")).startswith("generation.")
            or str(getattr(issue, "code", "")) in _GENERATION_STRUCTURE_DERIVATIVE_CODES
        )
    ]


def _generation_structure_patch_schema(full_schema: dict[str, Any]) -> dict[str, Any]:
    props = full_schema["properties"]
    binding = copy.deepcopy(
        props["examples"]["items"]["properties"]["bindings"]["items"]
    )
    rule = copy.deepcopy(
        props["personal_production"]["properties"]["pattern_rule"]
    )
    example_patch = {
        "type": "object",
        "additionalProperties": False,
        "required": ["index", "bindings"],
        "properties": {
            "index": {"type": "integer", "minimum": 0, "maximum": V04_EXAMPLES - 1},
            "bindings": {"type": "array", "minItems": 1, "items": binding},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula", "negative", "question", "examples", "personal_production_pattern_rule"],
        "properties": {
            "formula": copy.deepcopy(props["formula"]),
            "negative": copy.deepcopy(props["negative"]),
            "question": copy.deepcopy(props["question"]),
            "examples": {
                "type": "array",
                "minItems": V04_EXAMPLES,
                "maxItems": V04_EXAMPLES,
                "items": example_patch,
            },
            "personal_production_pattern_rule": rule,
        },
    }


def _generation_structure_context(
    point_id: str, title: str, data: dict[str, Any], issues: list[Any],
) -> dict[str, Any]:
    return {
        "point_id": point_id,
        "title": title,
        "summary": data["summary"],
        "sub": data["sub"],
        "when_to_use": data["when_to_use"],
        "issues": [
            {"code": issue.code, "path": issue.path, "message": issue.message}
            for issue in issues[:12]
        ],
        "formula": data["formula"],
        "negative": data["negative"],
        "question": data["question"],
        "examples": [
            {
                "index": index,
                "text": example["text"],
                "form": example["form"],
                "bindings": example["bindings"],
            }
            for index, example in enumerate(data["examples"])
        ],
        "personal_production": {
            "target_form": data["personal_production"]["target_form"],
            "sample": data["personal_production"]["sample"],
            "pattern_rule": data["personal_production"]["pattern_rule"],
        },
    }


def request_generation_structure_patch(
    llm: LLMClient,
    *,
    point_id: str,
    title: str,
    target_lang: str,
    data: dict[str, Any],
    issues: list[Any],
    full_schema: dict[str, Any],
) -> Any:
    """Repair only the v13 structural projection; learner-facing prose stays immutable."""
    patch_schema = _generation_structure_patch_schema(full_schema)
    if llm.provider == "deepseek":
        rule_props = (
            patch_schema["properties"]["personal_production_pattern_rule"]["properties"]
            ["slots"]["items"]["properties"]
        )
        rule_props["any_of"].pop("maxItems", None)
    system = """You repair ONLY the structural grammar projection of an already-written lesson.
The lesson's prose and example sentences are immutable. Return a corrected structural object
matching the schema.

Rules:
- Every formula list is ONE realizable left-to-right sentence path, never several mutually
  exclusive paths concatenated together.
- Surface alternatives that occupy the same grammatical position belong in ONE slot's options.
  Example: a/an are options of one article slot, not two sequential slots.
- If a grammatical element can be absent, use ONE optional=true slot. Absence itself is not
  a token: never create a required slot such as zero article, no article, O-slash or empty-set
  in addition to another article route. Represent zero article by omitting an optional
  article/determiner slot.
- Keep a slot abstract where the examples vary lexically (S, V, N, NP, clause, etc.).
- Never put `+` inside a slot text or option. The UI draws `+` between slots. If the current
  label encodes sequential pieces such as quantity+noun or 得+complement, represent those as
  truthful separate slots and bind each exact surface constituent in sentence order.
- English contractions are surface units when splitting them would overlap or reorder bindings.
  For a question-tag surface such as "isn't it", prefer one auxiliary slot for "isn't" followed
  by the pronoun slot; never place the pronoun before a later separate "n't" slot.
- Each unchanged example must bind every non-optional slot of its selected form exactly once,
  using an exact substring, in slot order. Optional slots may be omitted.
- Do not fake coverage by marking a genuinely required grammar-bearing slot optional.
- If the current same-form examples expose several surface realizations, factor their shared
  order into options/optional slots when that is grammatically truthful.
- personal_production_pattern_rule uses zero-based slot_index values from the REPAIRED
  target-form formula. It must match the unchanged sample and at least one unchanged example
  of that form. Use only grammar-bearing evidence, never enumerate open-class vocabulary.
- Do not change, paraphrase, or replace any example text, translation, explanation, practice
  item, title, summary, mistake, or other lesson content."""
    user = (
        f"Repair the structural projection for {point_id} ({target_lang}).\n"
        + json.dumps(
            _generation_structure_context(point_id, title, data, issues),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return llm.complete(
        system=system,
        user=user,
        json_schema=patch_schema,
        schema_name="grammar_point_v04_structure_patch",
        max_tokens=V04_STRUCTURE_REPAIR_MAX_TOKENS,
    )


def apply_generation_structure_patch(
    data: dict[str, Any], patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a structure-only patch while proving learner-facing content is unchanged."""
    out = copy.deepcopy(data)
    out["formula"] = patch["formula"]
    out["negative"] = patch["negative"]
    out["question"] = patch["question"]

    seen: set[int] = set()
    for item in patch["examples"]:
        index = item["index"]
        if index in seen or not 0 <= index < len(out["examples"]):
            raise ValueError("structure patch example indexes must be unique and in range")
        seen.add(index)
        out["examples"][index]["bindings"] = item["bindings"]
    if seen != set(range(len(out["examples"]))):
        raise ValueError("structure patch must return bindings for every unchanged example")

    out["personal_production"]["pattern_rule"] = patch["personal_production_pattern_rule"]
    return out


def assemble_generated_personal_production(
    raw: dict[str, Any], pattern: dict[str, Any], zh: bool, loc: Any,
) -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    """Map generation-only pattern-rule slot indexes to stored formula roles."""
    target_form = raw["target_form"]
    formula = _formula_for_generated_form(pattern, target_form)
    problems: list[tuple[str, str, str]] = []
    slots: list[dict[str, Any]] = []
    seen: set[int] = set()

    for index, raw_slot in enumerate(raw["pattern_rule"]["slots"]):
        slot_index = raw_slot.get("slot_index")
        path = f"personal_production.pattern_rule.slots[{index}].slot_index"
        if formula is None or not isinstance(slot_index, int) or not 0 <= slot_index < len(formula):
            problems.append((
                path,
                "generation.rule_slot_invalid",
                f"slot_index {slot_index!r} does not name a slot in the {target_form} formula",
            ))
            continue
        if slot_index in seen:
            problems.append((
                path,
                "generation.rule_slot_duplicate",
                f"formula slot {slot_index} is used more than once in pattern_rule",
            ))
            continue
        seen.add(slot_index)
        stored = {
            key: value
            for key, value in raw_slot.items()
            if key != "slot_index" and value not in (None, "", [])
        }
        stored["role"] = formula[slot_index]["role"]
        slots.append(stored)

    block: dict[str, Any] = {
        "prompt": loc(raw["prompt"]),
        "placeholder": target_text(raw["placeholder"], zh),
        "target_form": target_form,
        "pattern_rule": {"ordered": raw["pattern_rule"]["ordered"], "slots": slots},
        "sample": {"text": target_text(raw["sample"], zh)},
    }
    if zh:
        block["placeholder_pinyin"] = pinyin_from_pairs(block["placeholder"], raw.get("placeholder_pinyin_pairs"))
        block["sample"]["pinyin"] = pinyin_from_pairs(block["sample"]["text"], raw.get("sample_pinyin_pairs"))
    return block, problems


def assemble_compare_item(item: dict[str, Any], zh: bool, loc: Any) -> dict[str, Any]:
    entry = {
        "with": item["with"],
        "this_example": target_text(item["this_example"], zh),
        "other_example": target_text(item["other_example"], zh),
        "this_meaning": loc(item["this_meaning"]), "other_meaning": loc(item["other_meaning"]),
    }
    if zh:
        entry["this_example_pinyin"] = pinyin_from_pairs(entry["this_example"], item.get("this_example_pinyin_pairs"))
        entry["other_example_pinyin"] = pinyin_from_pairs(entry["other_example"], item.get("other_example_pinyin_pairs"))
    return entry


def assemble_quick_practice_item(item: dict[str, Any], zh: bool, loc: Any) -> dict[str, Any]:
    entry = {
        "q": zh_unspaced(item["q"]) if zh else item["q"],
        "options": [
            {"text": target_text(option["text"], zh), "error_tag": option["error_tag"],
             **({"pinyin": pinyin_from_pairs(target_text(option["text"], zh), option.get("pinyin_pairs"))} if zh else {})}
            for option in item["options"]
        ],
        "answer": item["answer"], "explain": loc(item["explain"]),
    }
    if zh:
        entry["q_pinyin"] = pinyin_from_pairs(entry["q"], unspaced_pairs(item.get("q_pinyin_pairs") or []))
    return entry


def assemble_common_mistake(raw: dict[str, Any], zh: bool, loc: Any) -> dict[str, Any]:
    mistake = {key: raw[key] for key in ("reason", "error_tag", "l1")}
    mistake["wrong"] = target_text(raw["wrong"], zh)
    mistake["right"] = target_text(raw["right"], zh)
    mistake["reason"] = loc(mistake["reason"])
    if zh:
        mistake["wrong_pinyin"] = pinyin_from_pairs(mistake["wrong"], raw.get("wrong_pinyin_pairs"))
        mistake["right_pinyin"] = pinyin_from_pairs(mistake["right"], raw.get("right_pinyin_pairs"))
    return mistake


def assemble_personal_production(raw: dict[str, Any], zh: bool, loc: Any) -> dict[str, Any]:
    """Model output -> the stored "Try it yourself" block. A rule slot names its matcher with exactly one of
    ``any_of`` / ``regex``; the model fills the other with an empty value, which is dropped here."""
    slots = []
    for slot in raw["pattern_rule"]["slots"]:
        slots.append({key: value for key, value in slot.items() if value not in (None, "", [])})
    block: dict[str, Any] = {
        "prompt": loc(raw["prompt"]), "placeholder": target_text(raw["placeholder"], zh), "target_form": raw["target_form"],
        "pattern_rule": {"ordered": raw["pattern_rule"]["ordered"], "slots": slots},
        "sample": {"text": target_text(raw["sample"], zh)},
    }
    if zh:
        block["placeholder_pinyin"] = pinyin_from_pairs(block["placeholder"], raw.get("placeholder_pinyin_pairs"))
        block["sample"]["pinyin"] = pinyin_from_pairs(block["sample"]["text"], raw.get("sample_pinyin_pairs"))
    return block


def assemble_morphology_row(raw: dict[str, Any], zh: bool) -> dict[str, Any]:
    row = {key: target_text(raw[key], zh) for key in ("base", "affix", "result")}
    if zh:
        for key in ("base", "affix", "result"):
            row[f"{key}_pinyin"] = pinyin_from_pairs(row[key], raw.get(f"{key}_pinyin_pairs"))
    return row


def _as_locale_map(value: Any, locales: list[str]) -> Any:
    """A provider with no schema enforcement (DeepSeek's json_object mode, live 2026-09-28)
    sometimes returns a locale field as a bare string. With a single declared locale that
    string can only mean that locale; with several it is left as-is for validate to flag."""
    if isinstance(value, str) and len(locales) == 1:
        return {locales[0]: value}
    return value


def _slots(raw: list[dict[str, Any]], zh: bool, locales: list[str]) -> list[dict[str, Any]]:
    out = []
    for slot in raw:
        item: dict[str, Any] = {"text": target_text(slot["text"], zh), "role": slot["role"], "label": _as_locale_map(slot["label"], locales)}
        if slot.get("optional"):
            item["optional"] = True
        options = [
            {"text": target_text(option["text"], zh), **({"pinyin": pinyin_from_pairs(target_text(option["text"], zh), option.get("pinyin_pairs"))} if zh else {})}
            for option in slot.get("options") or []
        ]
        if len(options) >= 2:  # one "option" is not a choice; the slot text already says it
            item["options"] = options
        if zh:
            item["pinyin"] = pinyin_from_pairs(item["text"], slot.get("pinyin_pairs"))
        out.append(item)
    return out



_ABSTRACT_SLOT_TEXT = {
    "s", "s1", "s2", "subject", "v", "v1", "v2", "v3", "verb", "n", "np", "noun",
    "adj", "adjective", "adv", "adverb", "o", "object", "do", "io", "complement",
    "time", "place", "clause", "clause 1", "clause 2", "main clause", "subordinate clause",
    "head noun", "summary noun", "heavy np/clause", "parenthetical", "result",
    "主语", "小主语", "谓语", "动词", "名词", "形容词", "宾语", "宾语1", "宾语2",
    "代词", "数词", "结果", "分句", "分句1", "分句2", "句子一", "句子二", "复句",
    "形容词/动词短语", "名词/形容词",
}


def _literal_slot_candidates(slot: dict[str, Any]) -> list[str]:
    """Surface forms safe to recover from an example without linguistic guessing."""
    raw = [option["text"] for option in slot.get("options", [])]
    text = str(slot.get("text", "")).strip()
    if text and text.casefold() not in _ABSTRACT_SLOT_TEXT:
        raw.append(text)
    out: list[str] = []
    for value in raw:
        # Formula cards often write alternatives with / or Chinese enumeration punctuation.
        for part in re.split(r"\s*(?:/|｜|、)\s*", value):
            part = part.strip()
            if not part or part.casefold() in _ABSTRACT_SLOT_TEXT:
                continue
            # Meta variables embedded in a form are not literal surface candidates.
            if re.search(r"\b(?:S\d*|V\d*|N|NP|Adj|Adv|Clause\d*)\b", part):
                continue
            if part not in out:
                out.append(part)
    return sorted(out, key=len, reverse=True)


def complete_literal_example_spans(examples: list[dict[str, Any]], pattern: dict[str, Any]) -> None:
    """Recover a missing role only when the formula itself supplies a literal surface form.

    Example: formula aux 'have/has' + sentence 'She has finished.' can safely recover
    'has'. Abstract S/V/N slots are never guessed.
    """
    variants = pattern.get("variants", {})
    for example in examples:
        formula = pattern["formula"] if example["form"] == "affirmative" else variants.get(example["form"])
        if not formula:
            continue
        present_roles = {span["role"] for span in example["spans"]}
        occupied = [(span["start"], span["end"]) for span in example["spans"]]
        for slot in formula:
            role = slot["role"]
            if slot.get("optional") or role in present_roles:
                continue
            for candidate in _literal_slot_candidates(slot):
                if re.search(r"[A-Za-z]", candidate):
                    # Contraction suffixes are grammar-bearing literals but are
                    # intentionally inside a larger token: "n't" in "didn't",
                    # "'ve" in "I've", etc. Ordinary Latin literals still use
                    # word boundaries so "be" never matches "because".
                    if candidate.casefold().replace("\u2019", "'") in {"n't", "'m", "'re", "'s", "'ve", "'ll", "'d"}:
                        matches = list(re.finditer(re.escape(candidate), example["text"], re.IGNORECASE))
                    else:
                        matches = list(re.finditer(r"(?<!\w)" + re.escape(candidate) + r"(?!\w)", example["text"], re.IGNORECASE))
                    starts = [match.start() for match in matches]
                else:
                    starts = []
                    start = example["text"].find(candidate)
                    while start >= 0:
                        starts.append(start)
                        start = example["text"].find(candidate, start + 1)
                for start in starts:
                    end = start + len(candidate)
                    if all(end <= a or start >= b for a, b in occupied):
                        example["spans"].append({"start": start, "end": end, "role": role})
                        occupied.append((start, end))
                        present_roles.add(role)
                        break
                if role in present_roles:
                    break
        example["spans"].sort(key=lambda item: item["start"])


def sanitize_example_spans(examples: list[dict[str, Any]], pattern: dict[str, Any]) -> None:
    """Drop visual spans whose role is not part of the selected formula.

    Such spans are harmless model over-highlighting, not a grammar error. Missing
    required roles still fail validation and trigger semantic repair.
    """
    variants = pattern.get("variants", {})
    for example in examples:
        formula = pattern["formula"] if example["form"] == "affirmative" else variants.get(example["form"])
        if not formula:
            continue
        allowed = {slot["role"] for slot in formula}
        example["spans"] = [span for span in example["spans"] if span["role"] in allowed]




def align_formula_order_from_examples(examples: list[dict[str, Any]], pattern: dict[str, Any]) -> None:
    """Repair only an unambiguous presentation-order mismatch.

    For a form whose formula roles are unique, if every example of that form
    contains every formula role exactly once and they all agree on one span
    order, reorder the formula slots to that order. This does not invent roles,
    spans or surface forms; it only makes the formula card agree with the
    examples the same candidate already supplied.
    """
    formulas: dict[str, list[dict[str, Any]]] = {"affirmative": pattern["formula"]}
    formulas.update(pattern.get("variants", {}))
    for form, formula in formulas.items():
        roles = [slot["role"] for slot in formula]
        if len(roles) != len(set(roles)):
            continue
        candidates: list[list[str]] = []
        for example in examples:
            if example["form"] != form:
                continue
            ordered = [span["role"] for span in sorted(example["spans"], key=lambda item: item["start"])]
            if len(ordered) != len(set(ordered)) or set(ordered) != set(roles):
                candidates = []
                break
            candidates.append(ordered)
        if not candidates or any(order != candidates[0] for order in candidates[1:]):
            continue
        if candidates[0] == roles:
            continue
        by_role = {slot["role"]: slot for slot in formula}
        formula[:] = [by_role[role] for role in candidates[0]]


_EN_CONTRACTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "am": re.compile(r"\b[\w]+['’]m\b", re.IGNORECASE),
    "are": re.compile(r"\b[\w]+['’]re\b", re.IGNORECASE),
    "is": re.compile(r"\b[\w]+['’]s\b", re.IGNORECASE),
    "has": re.compile(r"\b[\w]+['’]s\b", re.IGNORECASE),
    "have": re.compile(r"\b[\w]+['’]ve\b", re.IGNORECASE),
    "will": re.compile(r"\b[\w]+['’]ll\b", re.IGNORECASE),
    "would": re.compile(r"\b[\w]+['’]d\b", re.IGNORECASE),
    "had": re.compile(r"\b[\w]+['’]d\b", re.IGNORECASE),
}


def _stored_rule_matcher(slot: dict[str, Any]) -> Any | None:
    if "regex" in slot:
        try:
            return re.compile(slot["regex"], re.IGNORECASE)
        except re.error:
            return None
    values = slot.get("any_of")
    return values if isinstance(values, list) and values else None


def _slot_matches_text(slot: dict[str, Any], text: str, zh: bool) -> bool:
    matcher = _stored_rule_matcher(slot)
    return matcher is not None and pattern_rule_matches(False, [matcher], text, zh)



def _compact_observed_any_of(slot: dict[str, Any], texts: list[str], zh: bool) -> dict[str, Any]:
    """Keep only literals that the candidate actually demonstrates.

    Weak-schema providers sometimes enumerate an open vocabulary set despite
    the prompt. For generation repair, an any_of only needs surface forms
    observed in the model's own sample/examples. Preserve order, deduplicate,
    and cap the stored matcher to the contract bound.
    """
    values = slot.get("any_of")
    if not isinstance(values, list) or not values:
        return slot
    observed: list[str] = []
    seen: set[str] = set()
    for value in values:
        probe = {"role": slot.get("role"), "any_of": [value]}
        if not any(_slot_matches_text(probe, text, zh) for text in texts):
            continue
        key = str(value).casefold().replace("\u2019", "'")
        if key in seen:
            continue
        observed.append(value)
        seen.add(key)
        if len(observed) >= PERSONAL_PRODUCTION_MAX_ANY_OF:
            break
    return {**slot, "any_of": observed}


def _expand_observed_contractions(slot: dict[str, Any], texts: list[str], zh: bool) -> dict[str, Any]:
    """Add only contraction tokens actually present in this candidate's sample/examples."""
    if zh or "any_of" not in slot:
        return slot
    values = list(slot.get("any_of") or [])
    seen = {value.casefold().replace("\u2019", "'") for value in values}
    for literal in list(values):
        pattern = _EN_CONTRACTION_PATTERNS.get(literal.casefold())
        if pattern is None:
            continue
        for text in texts:
            for match in pattern.finditer(text):
                token = match.group(0).replace("\u2019", "'")
                key = token.casefold()
                if key not in seen and len(values) < PERSONAL_PRODUCTION_MAX_ANY_OF:
                    values.append(token)
                    seen.add(key)
    return {**slot, "any_of": values}


def repair_personal_production_rule(
    production: dict[str, Any], pattern: dict[str, Any], examples: list[dict[str, Any]], zh: bool,
) -> None:
    """Make a model-authored production rule self-consistent without inventing grammar.

    The model remains responsible for the rule. Code may add contraction spellings
    observed in its own sample/examples, drop constraints that match neither the
    sample nor one representative target-form example, or fall back to literal
    grammar slots already present in the formula. If no safe anchor exists the
    rule is left to fail deterministic validation.
    """
    formula = pattern["formula"] if production["target_form"] == "affirmative" else (
        pattern.get("variants", {}).get(production["target_form"])
    )
    if not formula:
        return
    formula_roles = {slot["role"] for slot in formula}
    sample = production["sample"]["text"]
    target_examples = [
        example["text"] for example in examples if example["form"] == production["target_form"]
    ]
    if not target_examples:
        return
    texts = [sample, *target_examples]

    raw_slots = [
        _expand_observed_contractions(_compact_observed_any_of(slot, texts, zh), texts, zh)
        for slot in production["pattern_rule"]["slots"]
        if slot.get("role") in formula_roles and _stored_rule_matcher(slot) is not None
    ]
    ordered = production["pattern_rule"]["ordered"]

    def rule_matches(slots: list[dict[str, Any]]) -> bool:
        matchers = [_stored_rule_matcher(slot) for slot in slots]
        if not slots or any(matcher is None for matcher in matchers):
            return False
        return pattern_rule_matches(ordered, matchers, sample, zh) and any(
            pattern_rule_matches(ordered, matchers, text, zh) for text in target_examples
        )

    if rule_matches(raw_slots):
        production["pattern_rule"]["slots"] = raw_slots
        return

    # Pick one representative example, then retain only constraints supported
    # by both it and the sample. Subject/time/place anchors are not grammar
    # evidence by themselves and are never the sole repair fallback.
    best: list[dict[str, Any]] = []
    for example_text in target_examples:
        supported = [
            slot for slot in raw_slots
            if _slot_matches_text(slot, sample, zh) and _slot_matches_text(slot, example_text, zh)
        ]
        if len(supported) > len(best):
            best = supported
    informative = [slot for slot in best if slot["role"] not in {"subject", "time", "place"}]
    if rule_matches(informative):
        production["pattern_rule"]["slots"] = informative
        return

    # Last safe fallback: literal forms already encoded in the selected
    # formula (auxiliaries, markers, particles, fixed connectors, etc.).
    for example_text in target_examples:
        derived: list[dict[str, Any]] = []
        for formula_slot in formula:
            if formula_slot["role"] in {"subject", "time", "place"}:
                continue
            candidates = _literal_slot_candidates(formula_slot)[:PERSONAL_PRODUCTION_MAX_ANY_OF]
            if not candidates:
                continue
            candidate_slot = _expand_observed_contractions(
                {"role": formula_slot["role"], "any_of": candidates},
                [sample, example_text],
                zh,
            )
            if _slot_matches_text(candidate_slot, sample, zh) and _slot_matches_text(candidate_slot, example_text, zh):
                derived.append(candidate_slot)
            if len(derived) >= PERSONAL_PRODUCTION_MAX_SLOTS:
                break
        if rule_matches(derived):
            production["pattern_rule"]["slots"] = derived
            return

def _story_generation_schema(*, locales: list[str], error_tags: list[str], cast_names: list[str]) -> dict[str, Any]:
    """STORY_SPEC.md §2: the LLM writes everything except ``type``/``theme`` (code sets
    those). One alternative per error_tag, same bounded-count pattern as pitfalls."""
    locale_map = _locale_map_schema(locales)
    slot = {
        "type": "object", "additionalProperties": False,
        "required": ["role", "value", "constraint"],
        "properties": {
            "role": {"enum": ["person", "place", "action", "object"]},
            "value": {"type": "string", "minLength": 1},
            "constraint": {"type": "string", "minLength": 1},
        },
    }
    beat = {
        "type": "object", "additionalProperties": False,
        "required": ["sentences", "slots"],
        "properties": {
            "sentences": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            "slots": {"type": "array", "items": slot},
        },
    }
    alternative = {
        "type": "object", "additionalProperties": False,
        "required": ["sentence", "error_tags", "consequence", "short", "slots"],
        "properties": {
            "sentence": {"type": "string", "minLength": 1},
            "error_tags": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"enum": error_tags} if error_tags else {"type": "string"},
            },
            "consequence": locale_map,
            "short": locale_map,
            "slots": {"type": "array", "items": slot},
        },
    }
    hook = {
        "type": "object", "additionalProperties": False,
        "required": ["hook_type", "text"],
        "properties": {
            "hook_type": {"enum": ["stakes", "insider", "myth-bust"]},
            "text": locale_map,
        },
    }
    alternative_count = max(1, len(error_tags))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "characters", "hook", "scene", "need", "form_in_action", "alternatives", "reveal", "reveal_short", "teaser"
        ],
        "properties": {
            "characters": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"enum": cast_names} if cast_names else {"type": "string"},
            },
            "hook": hook,
            "scene": locale_map,
            "need": locale_map,
            "form_in_action": beat,
            "alternatives": {"type": "array", "minItems": alternative_count, "maxItems": alternative_count, "items": alternative},
            "reveal": locale_map,
            "reveal_short": locale_map,
            "teaser": locale_map,
        },
    }


def _build_check_items(examples: list[dict[str, Any]], rule_table: dict[str, Any] | None,
                        pitfalls: list[dict[str, Any]], locales: list[str], max_items: int = 3) -> list[dict[str, Any]]:
    """Cloze questions built from the examples the LLM just wrote (SPEC §5.1 step 3):
    blank out the ``target`` segment, offer the base form and a pitfall's wrong form
    as distractors. Deterministic -- no LLM call."""
    rows_by_derived = {row[1]: row[0] for row in (rule_table or {}).get("rows", [])}
    pitfalls_by_tag = {p["error_tag"]: p for p in pitfalls}
    generic_explain = {locale: "See the rule and examples above." for locale in locales}

    items: list[dict[str, Any]] = []
    for example in examples:
        target_segments = [seg for seg in example["seg"] if len(seg) > 1 and seg[1] == "target"]
        if len(target_segments) != 1:
            continue  # a clean single-blank cloze needs exactly one target segment
        target_text = target_segments[0][0]
        blanked = "".join(seg[0] if not (len(seg) > 1 and seg[1] == "target") else "___" for seg in example["seg"])
        options = [target_text]
        base = rows_by_derived.get(target_text.strip())
        if base and base not in options:
            options.append(base)
        for pitfall in pitfalls:
            wrong_words = set(pitfall["wrong"].split())
            candidate = next((w for w in wrong_words if w not in target_text and len(options) < max_items), None)
            if candidate and candidate not in options:
                options.append(candidate)
                break
        if len(options) < 2:
            continue
        explain = next(
            (p["why"] for p in pitfalls_by_tag.values() if p["right"].strip() == target_text.strip()),
            generic_explain,
        )
        items.append({"q": blanked, "options": options, "answer": 0, "explain": explain})
        if len(items) >= max_items:
            break
    return items



V04_LEARNING_BLOCK_REPAIR_MAX_TOKENS = 1800
_GENERATION_LEARNING_BLOCK_CODES = {
    "common_mistake.same_wrong_right",
    "error_tag.common_mistake_unlisted",
    "quick_practice.blank_invalid",
    "quick_practice.answer_tagged",
    "quick_practice.distractor_untagged",
    "quick_practice.distractor_misspelling",
}


def generation_learning_block_repair_issues(issues: list[Any]) -> list[Any]:
    """Return only bounded learner-exercise defects safe for block-only repair."""
    return [
        issue for issue in issues
        if str(getattr(issue, "code", "")) in _GENERATION_LEARNING_BLOCK_CODES
    ]


def can_repair_generation_learning_blocks(issues: list[Any]) -> bool:
    """True when at least one common-mistake or quick-practice block needs repair."""
    return bool(generation_learning_block_repair_issues(issues))


def _generation_learning_patch_schema(
    full_schema: dict[str, Any], issues: list[Any],
) -> dict[str, Any]:
    codes = {str(getattr(issue, "code", "")) for issue in issues}
    properties: dict[str, Any] = {}
    if any(code.startswith("common_mistake.") or code.startswith("error_tag.common_mistake") for code in codes):
        properties["common_mistakes"] = copy.deepcopy(full_schema["properties"]["common_mistakes"])
    if any(code.startswith("quick_practice.") for code in codes):
        properties["quick_practice"] = copy.deepcopy(full_schema["properties"]["quick_practice"])
    if not properties:
        raise ValueError("learning-block patch requested without a repairable block")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _generation_learning_context(data: dict[str, Any], issues: list[Any]) -> dict[str, Any]:
    selected = generation_learning_block_repair_issues(issues)
    codes = {str(getattr(issue, "code", "")) for issue in selected}
    context: dict[str, Any] = {
        "issues": [
            {"code": issue.code, "path": issue.path, "message": issue.message}
            for issue in selected[:12]
        ],
        "summary": data.get("summary"),
        "when_to_use": data.get("when_to_use"),
        "formula": data.get("formula"),
        "negative": data.get("negative"),
        "question": data.get("question"),
        "examples": [
            {"text": example.get("text"), "form": example.get("form")}
            for example in data.get("examples") or []
        ],
    }
    if any(code.startswith("common_mistake.") or code.startswith("error_tag.common_mistake") for code in codes):
        context["common_mistakes"] = data.get("common_mistakes")
    if any(code.startswith("quick_practice.") for code in codes):
        context["quick_practice"] = data.get("quick_practice")
    return context


def request_generation_learning_patch(
    llm: LLMClient,
    *,
    point_id: str,
    target_lang: str,
    data: dict[str, Any],
    issues: list[Any],
    full_schema: dict[str, Any],
) -> Any:
    """Repair only learner mistake/practice blocks; grammar lesson prose stays immutable."""
    selected = generation_learning_block_repair_issues(issues)
    patch_schema = _generation_learning_patch_schema(full_schema, selected)
    system = """You repair ONLY the bounded learner-exercise blocks of an already-written grammar lesson.
The grammar formula, explanations, examples, translations, title, summary, comparisons and personal-production task are immutable.
Return only the block(s) requested by the JSON schema.

Rules:
- common_mistakes: wrong and right must be genuinely different. The wrong sentence must demonstrate a real learner grammar error matching its error_tag; the right sentence must be grammatical and teach the same intended point. Do not invent a spelling-only error.
- quick_practice: every q contains exactly one literal ___ blank. Keep exactly three items. The answer index points to the genuinely correct option; that correct option has error_tag null. Every wrong option must be a plausible grammar error and carry the matching non-null error_tag.
- Preserve the lesson's grammar scope and difficulty. Use the unchanged examples/formula as evidence; do not broaden the lesson or rewrite unrelated content.
- For Chinese, write natural unspaced Chinese around the blank; pinyin hints may be omitted because code derives pinyin deterministically.
"""
    user = (
        f"Repair learner blocks for {point_id} ({target_lang}).\n"
        + json.dumps(
            _generation_learning_context(data, selected),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return llm.complete(
        system=system,
        user=user,
        json_schema=patch_schema,
        schema_name="grammar_point_v04_learning_patch",
        max_tokens=V04_LEARNING_BLOCK_REPAIR_MAX_TOKENS,
    )


def apply_generation_learning_patch(
    data: dict[str, Any], patch: dict[str, Any],
) -> dict[str, Any]:
    """Replace only explicitly returned common-mistake/quick-practice blocks."""
    allowed = {"common_mistakes", "quick_practice"}
    if not patch or any(key not in allowed for key in patch):
        raise ValueError("learning patch contains unsupported keys")
    out = copy.deepcopy(data)
    for key, value in patch.items():
        out[key] = copy.deepcopy(value)
    return out

def semantic_repair_hints(issues: list[Any]) -> str:
    """Focused instructions for recurrent deterministic failure families.

    The validator remains authoritative; these hints only stop the provider
    from re-creating the same structural mistake on all three attempts.
    """
    codes = {issue.code for issue in issues}
    hints: list[str] = []
    if codes & {
        "example.formula_role_missing", "example.span_slot_mismatch",
        "example.span_role_not_in_formula", "example.form_without_variant",
    }:
        hints.append(
            "Formula/examples: keep one concrete skeleton per form. Collapse alternative surface forms "
            "into one slot's options instead of sequential required slots; mark a slot optional only when "
            "a valid sentence can omit it. Rewrite spans as exact substrings using only roles present in "
            "that selected formula. Before returning, walk each example left-to-right against its selected "
            "formula and make the role order agree exactly. Do not highlight extra time/place/complement "
            "material unless the formula names it."
        )
    if codes & {"formula.slot_has_joiner", "formula.option_duplicate"}:
        hints.append(
            "Formula slots: never put '+' inside a slot. Split sequential parts into slots; put true alternatives "
            "in distinct options of one slot and remove duplicate options."
        )
    if any(code.startswith("personal_production.") for code in codes):
        hints.append(
            f"Personal production: teach one representative route only. Use at most {PERSONAL_PRODUCTION_MAX_SLOTS} "
            f"rule slots and at most {PERSONAL_PRODUCTION_MAX_ANY_OF} literals in any any_of list. Never enumerate "
            "open-class vocabulary (ordinary verbs, nouns, adjectives, topics) in any_of. Match only the "
            "grammar-bearing form: use a short closed any_of for markers/auxiliaries/particles, or a focused regex "
            "for a productive form. Make pattern_rule match the sample and at least one target-form example; "
            "each rule slot must end with exactly one non-empty matcher."
        )
    if codes & {"zh.pinyin_invalid", "zh.whitespace"}:
        hints.append(
            "Chinese formatting: write normal unspaced Chinese. Omit pinyin-pair fields unless a polyphonic Han "
            "character truly needs a contextual override; code supplies routine pinyin and alignment."
        )
    if any(code.startswith("quick_practice.") for code in codes):
        hints.append(
            "Quick practice: each q has exactly one ___; the indexed correct option is grammatical and untagged; "
            "every distractor is a real grammar error with a valid evaluator tag, never a spelling invention."
        )
    if any(code.startswith("common_mistake.") or code.startswith("error_tag.common_mistake") for code in codes):
        hints.append(
            "Common mistakes: wrong and right must differ by the named grammar mechanism, with an error_tag listed "
            "for this point; do not use a typo as the mistake."
        )
    return "\n".join(f"REPAIR RULE: {hint}" for hint in hints)



@dataclass
class Generator:
    lang: str
    l1: str
    llm: LLMClient
    root: Path = LAB_ROOT
    num_examples: int = 2
    r5_root: Path | None = None  # the app's grammar data (r5_source.DEFAULT_R5_ROOT when None)
    allow_default_safe: bool = False  # explicit override for points whose metadata was never reviewed
    max_full_attempts: int = V04_SEMANTIC_ATTEMPTS
    paid_repairs: bool = True
    require_initial_cache: bool = False

    def generate(
        self, point_id: str, *, regenerate_note: str | None = None, with_story: bool = False, story_mode: str = "everyday"
    ) -> GenerateOutcome:
        if self.max_full_attempts < 1 or self.max_full_attempts > V04_SEMANTIC_ATTEMPTS:
            raise ValueError(
                f"max_full_attempts must be between 1 and {V04_SEMANTIC_ATTEMPTS}, got {self.max_full_attempts}"
            )
        if story_mode not in STORY_MODES:
            raise ValueError(f"story_mode must be one of {sorted(STORY_MODES)}, got {story_mode!r}")
        # Fail closed before any provider call: stale catalogue or unreviewed (default_safe) metadata.
        check_generation_gate(self.lang, [point_id], self.root, allow_default_safe=self.allow_default_safe)
        # The catalogue decides structure: a point not on disk starts from its seed, and one that is takes
        # the seed's metadata (level, function, contrasts, R5 sources, anchors) over its own.
        existing = apply_seed(load_point(self.lang, point_id, self.root), self.lang, point_id, self.root)
        if existing is None:
            return GenerateOutcome(point_id, "error", reason="no such point on disk and no seed in inventory/seeds_<lang>.yaml")
        if existing["status"] == "approved" and not regenerate_note:
            return GenerateOutcome(point_id, "skipped_approved", reason="pass --regenerate-note to regenerate an approved point")

        manifest = load_manifest(self.lang, self.root)
        locales: list[str] = manifest["explanation_locales"]
        l1s: list[str] = manifest["l1"]
        functions = load_functions(self.root)["functions"]
        function = next(f for f in functions if f["id"] == existing["function"])

        if existing.get("schema_version") == "0.4":
            if with_story:
                raise ValueError("--with-story is not wired into schema_version 0.4 generation yet (story is paused this round)")
            return self._generate_v04(
                existing, locales=locales, l1s=l1s, function=function, regenerate_note=regenerate_note,
            )

        rule_table = build_rule_table(point_id, locales)
        schema = _generation_schema(
            locales=locales, l1s=l1s, error_tags=existing["error_tags"],
            contrast_with=existing["contrasts"], num_examples=self.num_examples,
        )
        system = PROMPT_PATH.read_text(encoding="utf-8").format(
            point_id=point_id, target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            function_title=function["title"].get("en", function["title"].get("vi", "")),
            function_id=function["id"], locales=", ".join(locales), l1s=", ".join(l1s),
            contrast_with_ids=", ".join(existing["contrasts"]) or "(none)",
            error_tags=", ".join(existing["error_tags"]) or "(none)",
            rule_table_summary=_rule_table_summary(rule_table),
        )
        user = f"Write the grammar point {point_id} now, matching the structured output schema."
        note_suffix = f" Admin regenerate note: {regenerate_note}" if regenerate_note else ""
        result = self.llm.complete(
            system=system, user=user + note_suffix, json_schema=schema, schema_name="grammar_point_blocks",
            check_schema=False,  # legacy v0.2/0.3 path
            require_cache=self.require_initial_cache,
        )
        for example in result.data["examples"]:
            example["seg"] = _normalize_seg(example["seg"])

        blocks: list[dict[str, Any]] = [{"type": "formula", **result.data["formula"]}]
        if result.data.get("timeline"):
            blocks.append({"type": "timeline", **result.data["timeline"]})
        if rule_table is not None:
            blocks.append(rule_table)
        examples = [{"type": "example", **example} for example in result.data["examples"]]
        blocks.extend(examples)
        blocks.extend({"type": "contrast", **contrast} for contrast in result.data["contrasts"])
        pitfalls = [{"type": "pitfall", **pitfall} for pitfall in result.data["pitfalls"]]
        blocks.extend(pitfalls)
        if result.data.get("note"):
            blocks.append({"type": "note", **result.data["note"]})
        check_items = _build_check_items(result.data["examples"], rule_table, result.data["pitfalls"], locales)
        if check_items:
            blocks.append({"type": "check", "items": check_items})

        cost = _incremental_result_cost(result) or 0.0
        cached = result.cached
        prompt_version = PROMPT_VERSION
        schema_version = existing.get("schema_version", "0.2")
        if with_story:
            story_result, story_block = self._generate_story(existing, locales, mode=story_mode)
            blocks.append(story_block)
            story_cost = _incremental_result_cost(story_result)
            cost = (cost + story_cost) if story_cost is not None else cost
            cached = cached and story_result.cached
            prompt_version = f"{PROMPT_VERSION}+{STORY_PROMPT_VERSION}"
            schema_version = "0.3"

        version = next_draft_version(existing) if regenerate_note and existing["status"] == "approved" else existing["version"]
        point = {
            **existing,
            "schema_version": schema_version,
            "version": version,
            "blocks": blocks,
            "status": "draft_ai",
            "flags": [],
            "provenance": {
                "model": f"{result.provider}:{result.model}",
                "prompt_version": prompt_version,
                "run_id": f"generate.{int(time.time())}",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "review": None,
        }
        save_point(self.lang, point, self.root)
        return GenerateOutcome(point_id, "written", cost_usd=cost or None, cached=cached)

    def _generate_v04(
        self, existing: dict[str, Any], *, locales: list[str], l1s: list[str], function: dict[str, Any],
        regenerate_note: str | None = None,
    ) -> GenerateOutcome:
        """GRAMMAR_CONTENT_CONTRACT.md: header + the fixed content blocks, generated fresh.

        Structural metadata (id, level, point_type, error_tags, contrasts, the title and its
        target-language name) comes from the existing point, as with every generate step;
        everything a learner reads under the header is written by the model."""
        point_id = existing["id"]
        point_type = existing.get("point_type")
        if point_type not in ILLUSTRATION_FOR_POINT_TYPE:
            return GenerateOutcome(point_id, "error", reason="schema_version 0.4 point needs point_type metadata first")
        zh = existing["target_lang"] == ZH_HANS
        r5_ids: list[str] = list((existing.get("source_refs") or {}).get("r5", []))
        r5_records: list[dict[str, Any]] = []
        if r5_ids:
            try:
                available = load_r5(self.lang, self.r5_root or DEFAULT_R5_ROOT)
            except R5SourceError as exc:
                return GenerateOutcome(point_id, "error", reason=str(exc))
            unknown = [r5_id for r5_id in r5_ids if r5_id not in available]
            if unknown:
                return GenerateOutcome(point_id, "error", reason=f"source_refs.r5 names unknown R5 lesson(s): {unknown}")
            r5_records = [available[r5_id] for r5_id in r5_ids]
        header = _header_metadata(existing, locales)
        engine_tags = read_json(self.root / ERROR_TAGS_PATH)["languages"][existing["target_lang"]]["tags"]
        schema = _generation_schema_v04(
            locales=locales, l1s=l1s, error_tags=existing["error_tags"], engine_tags=engine_tags,
            contrast_with=existing["contrasts"], point_type=point_type, zh=zh, r5_ids=r5_ids,
        )
        provider_schema = schema
        if self.llm.provider == "deepseek":
            # DeepSeek json_object mode does not enforce JSON Schema. Let an
            # oversized any_of reach deterministic repair instead of billing a
            # whole fresh response just because it exceeded maxItems. Strong
            # structured-output providers keep the strict schema.
            provider_schema = copy.deepcopy(schema)
            rule_props = (
                provider_schema["properties"]["personal_production"]["properties"]
                ["pattern_rule"]["properties"]["slots"]["items"]["properties"]
            )
            rule_props["any_of"].pop("maxItems", None)
        system = PROMPT_PATH_V04.read_text(encoding="utf-8").format(
            point_id=point_id, target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            title=header["title"].get("vi", header["native_title"]), native_title=header["native_title"],
            function_title=function["title"].get("en", function["title"].get("vi", "")),
            function_id=function["id"], locales=", ".join(locales), l1s=", ".join(l1s),
            contrast_with_ids=", ".join(existing["contrasts"]) or "(none)",
            error_tags=", ".join(existing["error_tags"]) or "(none)",
            engine_tags=", ".join(engine_tags),
            illustration_instruction=_ILLUSTRATION_INSTRUCTIONS[point_type],
            locale_format=(
                f"a plain string written in `{locales[0]}` (not an object)."
                if len(locales) == 1 else
                "an object keyed by locale, with every one of these locales: " + ", ".join(locales) + "."
            ),
            pinyin_instruction=_PINYIN_INSTRUCTION if zh else "",
            r5_instruction=_R5_INSTRUCTION if r5_records else "",
            num_examples=V04_EXAMPLES,
        )
        user = f"Write the grammar point {point_id} now, matching the structured output schema."
        if regenerate_note:
            user += f" Admin regenerate note: {regenerate_note}"
        if r5_records:
            user += "\n\nR5 source lesson(s) for this point (restructure, correct, complete):\n" + r5_source_text(r5_records)
        def assemble(result: Any) -> dict[str, Any]:
            candidate_data = normalize_generated_question_word_frame(result.data, zh) if point_id == "zh.question_words" else result.data
            data = normalize_generated_structure(candidate_data, zh)

            illustration: dict[str, Any] = {"kind": ILLUSTRATION_FOR_POINT_TYPE[point_type]}
            if point_type == "tense_aspect":
                illustration["timeline"] = {"shape": data["timeline_shape"]}
            elif point_type == "morphology":
                illustration["morphology"] = [assemble_morphology_row(raw, zh) for raw in data["morphology"]]

            def loc(value: Any) -> Any:
                return _as_locale_map(value, locales)

            pattern: dict[str, Any] = {"formula": _slots(data["formula"], zh, locales)}
            variants = {name: _slots(data[name], zh, locales) for name in ("negative", "question") if data.get(name)}
            if variants:
                pattern["variants"] = variants
            pattern["illustration"] = illustration

            generation_problems: list[tuple[str, str, str]] = []
            examples: list[dict[str, Any]] = []
            for example_index, raw in enumerate(data["examples"]):
                example, problems = assemble_generated_example(raw, pattern, zh, loc, example_index)
                examples.append(example)
                generation_problems.extend(problems)

            compare = [assemble_compare_item(item, zh, loc) for item in data["compare"]]
            quick_practice = [assemble_quick_practice_item(item, zh, loc) for item in data["quick_practice"]]
            mistakes = [assemble_common_mistake(raw, zh, loc) for raw in data["common_mistakes"]]
            personal_production, production_problems = assemble_generated_personal_production(
                data["personal_production"], pattern, zh, loc
            )
            generation_problems.extend(production_problems)
            repair_personal_production_rule(personal_production, pattern, examples, zh)
            stored_header = _stored_header_metadata(header, zh)

            point = {
                **{key: existing[key] for key in (
                    "id", "version", "target_lang", "function", "level", "prereqs", "contrasts", "error_tags", "source_refs",
                )},
                "schema_version": "0.4",
                "point_type": point_type,
                **{key: existing[key] for key in ("sequence", "aliases") if key in existing},
                "source_anchors": existing.get("source_anchors") or {"status": "unanchored", "items": []},
                "header": {
                    **stored_header, "summary": loc(data["summary"]),
                    "sub": loc(data["sub"]),
                    **({"native_title_pinyin": pinyin_from_pairs(stored_header["native_title"], data.get("native_title_pinyin_pairs"))} if zh else {}),
                },
                "when_to_use": [loc(item) for item in data["when_to_use"]],
                "pattern": pattern,
                "examples": examples,
                "compare": compare,
                "common_mistakes": mistakes,
                "quick_practice": quick_practice,
                "personal_production": personal_production,
                "status": "draft_ai",
                "flags": [],
                "provenance": {
                    "model": f"{result.provider}:{result.model}",
                    "prompt_version": PROMPT_VERSION_V04,
                    "run_id": f"generate.{int(time.time())}",
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                "review": None,
            }
            if r5_records:
                point["provenance"]["r5_source"] = {
                    "ids": r5_ids,
                    "content_version": max(record["content_version"] for record in r5_records),
                    "content_hash": hashlib.sha256(r5_source_text(r5_records).encode("utf-8")).hexdigest(),
                    "corrections": data.get("r5_corrections", []),
                }
            if existing.get("blocks"):
                point["blocks"] = existing["blocks"]
            assembled = {"schema_version": point.pop("schema_version"), **point}
            file = f"content/{self.lang}/{point_id}.json"
            contract_issues = [
                Issue(file=file, path=path, code=code, message=message)
                for path, code, message in generation_problems
            ]
            return assembled, contract_issues

        total_cost = 0.0
        cost_known = True
        all_cached = True
        repair_context = ""
        last_problem = ""

        for attempt in range(1, self.max_full_attempts + 1):
            attempt_user = user
            if repair_context:
                attempt_user += (
                    f"\n\nRepair attempt {attempt}/{self.max_full_attempts}. "
                    "The previous full JSON candidate failed deterministic validation. "
                    "Return a fresh complete JSON object that fixes every issue below without changing the requested grammar scope:\n"
                    + repair_context
                )
            try:
                result = self.llm.complete(
                    system=system, user=attempt_user, json_schema=provider_schema,
                    schema_name="grammar_point_v04", max_tokens=V04_MAX_TOKENS,
                    require_cache=self.require_initial_cache,
                )
            except LLMError as exc:
                if exc.usage is None or attempt >= self.max_full_attempts:
                    raise
                attempt_cost = exc.usage.cost_usd(self.llm.model)
                if attempt_cost is None:
                    cost_known = False
                else:
                    total_cost += attempt_cost
                all_cached = False
                last_problem = str(exc)
                repair_context = "Provider/schema failure: " + str(exc)[:1200]
                continue

            attempt_cost = _incremental_result_cost(result)
            if attempt_cost is None:
                cost_known = False
            else:
                total_cost += attempt_cost
            all_cached = all_cached and result.cached

            point, contract_issues = assemble(result)
            issues = [*contract_issues, *validate_generated_point(self.lang, point, self.root)]
            targeted_repair_used = False
            learning_repair_used = False
            structure_repair_exhausted = False
            if not issues:
                save_point(self.lang, point, self.root)
                register_realization(point, self.root)
                return GenerateOutcome(
                    point_id, "written",
                    cost_usd=(total_cost if cost_known and total_cost else None),
                    cached=all_cached,
                )

            if not self.paid_repairs:
                last_problem = "; ".join(
                    f"{issue.code} at {issue.path}: {issue.message}" for issue in issues[:8]
                )
                break

            # The provider/JSON schema accepted this response, so complete()
            # cached it. Keep that paid candidate while deterministic/targeted
            # repair is attempted: a later code fix can then re-evaluate the same
            # lesson without buying the full generation again. We invalidate only
            # immediately before intentionally requesting a fresh full candidate.

            # v13 binding failures are projection failures, not a reason to
            # buy the whole lesson again. Keep the accepted lesson prose and make
            # at most two small structure-only repair calls.
            if can_repair_generation_structure(issues):
                candidate_structure_data = normalize_generated_question_word_frame(result.data, zh) if point_id == "zh.question_words" else result.data
                structure_data = normalize_generated_structure(candidate_structure_data, zh)
                structure_issues = issues
                for _structure_attempt in range(2):
                    try:
                        structure_patch = request_generation_structure_patch(
                            self.llm,
                            point_id=point_id,
                            title=header["native_title"],
                            target_lang=existing["target_lang"],
                            data=structure_data,
                            issues=generation_structure_repair_issues(structure_issues),
                            full_schema=schema,
                        )
                    except LLMError as exc:
                        if exc.usage is not None:
                            patch_cost = exc.usage.cost_usd(self.llm.model)
                            if patch_cost is None:
                                cost_known = False
                            else:
                                total_cost += patch_cost
                        all_cached = False
                        break

                    patch_cost = _incremental_result_cost(structure_patch)
                    if patch_cost is None:
                        cost_known = False
                    else:
                        total_cost += patch_cost
                    all_cached = all_cached and structure_patch.cached
                    try:
                        structure_data = apply_generation_structure_patch(
                            structure_data, structure_patch.data
                        )
                    except ValueError:
                        break

                    result = replace(result, data=structure_data)
                    point, contract_issues = assemble(result)
                    structure_issues = [
                        *contract_issues,
                        *validate_generated_point(self.lang, point, self.root),
                    ]
                    if not structure_issues:
                        save_point(self.lang, point, self.root)
                        register_realization(point, self.root)
                        return GenerateOutcome(
                            point_id, "written",
                            cost_usd=(total_cost if cost_known and total_cost else None),
                            cached=all_cached,
                        )
                    if not can_repair_generation_structure(structure_issues):
                        break

                issues = structure_issues
                structure_repair_exhausted = any(
                    issue.code.startswith("generation.") for issue in issues
                )

            # Mistake/practice defects are learner-content bugs, but they do not justify
            # buying a fresh full lesson. Repair only the implicated small block(s).
            if can_repair_generation_learning_blocks(issues):
                learning_repair_used = True
                learning_issues = generation_learning_block_repair_issues(issues)
                try:
                    learning_patch = request_generation_learning_patch(
                        self.llm,
                        point_id=point_id,
                        target_lang=existing["target_lang"],
                        data=result.data,
                        issues=learning_issues,
                        full_schema=schema,
                    )
                except LLMError as exc:
                    if exc.usage is not None:
                        patch_cost = exc.usage.cost_usd(self.llm.model)
                        if patch_cost is None:
                            cost_known = False
                        else:
                            total_cost += patch_cost
                    all_cached = False
                else:
                    patch_cost = _incremental_result_cost(learning_patch)
                    if patch_cost is None:
                        cost_known = False
                    else:
                        total_cost += patch_cost
                    all_cached = all_cached and learning_patch.cached
                    try:
                        learning_data = apply_generation_learning_patch(
                            result.data, learning_patch.data
                        )
                    except ValueError:
                        pass
                    else:
                        result = replace(result, data=learning_data)
                        point, contract_issues = assemble(result)
                        issues = [
                            *contract_issues,
                            *validate_generated_point(self.lang, point, self.root),
                        ]
                        if not issues:
                            save_point(self.lang, point, self.root)
                            register_realization(point, self.root)
                            return GenerateOutcome(
                                point_id, "written",
                                cost_usd=(total_cost if cost_known and total_cost else None),
                                cached=all_cached,
                            )

            # Remaining semantic failures can still be confined to formula ordering,
            # stored example spans and the deterministic production rule. Repair that
            # small surface before paying for a fresh full lesson.
            if can_target_repair(issues):
                targeted_repair_used = True
                repair_point = point
                repair_issues = issues
                rule_only_repair = all(
                    issue.code.startswith("personal_production.")
                    for issue in repair_issues
                )
                repair_attempts = max(
                    TARGETED_REPAIR_ATTEMPTS,
                    2 if rule_only_repair else 1,
                )
                for _repair_attempt in range(repair_attempts):
                    try:
                        patch_result = request_semantic_patch(
                            self.llm,
                            point_id=point_id,
                            target_lang=existing["target_lang"],
                            point=repair_point,
                            issues=repair_issues,
                        )
                    except LLMError as exc:
                        if exc.usage is not None:
                            patch_cost = exc.usage.cost_usd(self.llm.model)
                            if patch_cost is None:
                                cost_known = False
                            else:
                                total_cost += patch_cost
                        all_cached = False
                        break

                    patch_cost = _incremental_result_cost(patch_result)
                    if patch_cost is None:
                        cost_known = False
                    else:
                        total_cost += patch_cost
                    all_cached = all_cached and patch_result.cached

                    try:
                        repair_point = apply_semantic_patch(
                            repair_point, patch_result.data, repair_issues
                        )
                    except ValueError:
                        break

                    repair_issues = validate_generated_point(self.lang, repair_point, self.root)
                    if not repair_issues:
                        save_point(self.lang, repair_point, self.root)
                        register_realization(repair_point, self.root)
                        return GenerateOutcome(
                            point_id, "written",
                            cost_usd=(total_cost if cost_known and total_cost else None),
                            cached=all_cached,
                        )

                issues = repair_issues

            last_problem = "; ".join(
                f"{issue.code} at {issue.path}: {issue.message}" for issue in issues[:8]
            )
            focused_hints = semantic_repair_hints(issues)
            # A targeted repair already spent on the exact failing
            # structure, so do not buy more full generations after it fails.
            # Pure generation-structure failures are handled above by cached
            # deterministic/structure-only repair and fail closed without a
            # second full lesson. Mixed failures retain one bounded full retry.
            contract_failure = any(issue.code.startswith("generation.") for issue in issues)
            if targeted_repair_used or learning_repair_used or structure_repair_exhausted or (contract_failure and attempt >= 2):
                break

            # A full semantic retry already has a different user prompt
            # (repair context + attempt number), hence a different cache key.
            # Keep every paid candidate: future deterministic fixes may make an
            # earlier candidate valid without another provider call.
            repair_context = (
                "\n".join(
                    f"- {issue.code} at {issue.path}: {issue.message}" for issue in issues[:8]
                )
                + (("\n\n" + focused_hints) if focused_hints else "")
                + "\n\nPrevious candidate JSON (repair this candidate; preserve the parts not implicated by the errors):\n"
                + json.dumps(result.data, ensure_ascii=False, separators=(",", ":"))
            )

        attempts_used = attempt
        return GenerateOutcome(
            point_id, "error",
            reason=(
                f"semantic validation failed after {attempts_used} full attempt(s)"
                + (" plus learning-block repair" if learning_repair_used else "")
                + (" plus targeted repair" if targeted_repair_used else "")
                + f": {last_problem}"
            ),
            cost_usd=(total_cost if cost_known and total_cost else None),
            cached=all_cached,
        )

    def _generate_story(self, existing: dict[str, Any], locales: list[str], *, mode: str = "everyday") -> tuple[Any, dict[str, Any]]:
        """STORY_SPEC.md + VOICE.md: a dedicated call for the point's daily-theme story block."""
        cast = load_cast(self.root)
        cast_names = [member["name"] for member in cast]
        cast_list = "\n".join(f"- {member['name']}: {member['personality'].get('vi', '')}" for member in cast)
        schema = _story_generation_schema(locales=locales, error_tags=existing["error_tags"], cast_names=cast_names)
        system = STORY_PROMPT_PATH.read_text(encoding="utf-8").format(
            point_id=existing["id"], target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            locales=", ".join(locales), error_tags=", ".join(existing["error_tags"]) or "(none)",
            cast_list=cast_list,
        )
        user = f"Write the daily-theme story for {existing['id']} now, matching the structured output schema."
        result = self.llm.complete(system=system, user=user, json_schema=schema, schema_name="story", check_schema=False)
        return result, {"type": "story", "theme": "daily", "mode": mode, **result.data}
