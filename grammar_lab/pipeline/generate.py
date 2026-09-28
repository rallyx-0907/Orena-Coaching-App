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

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import (
    LAB_ROOT,
    load_cast,
    load_functions,
    load_manifest,
    load_point,
    next_draft_version,
    save_point,
)
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.rules import en_morphology

PROMPT_VERSION = "generate_point.v1"
PROMPT_PATH = LAB_ROOT / "prompts" / "generate_point.md"
PROMPT_VERSION_V04 = "generate_point_v04.v1"
PROMPT_PATH_V04 = LAB_ROOT / "prompts" / "generate_point_v04.md"
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
    "subject", "verb", "aux", "object", "complement", "time", "place", "marker", "particle", "connector", "other",
]
_TIMELINE_SHAPES = [
    "point_past", "ongoing_now", "unspecified_past", "habit", "future_condition", "future_plan", "past_ongoing",
]


def _generation_schema_v04(*, locales: list[str], l1s: list[str], error_tags: list[str],
                            contrast_with: list[str], num_examples: int) -> dict[str, Any]:
    """GRAMMAR_CONTENT_CONTRACT.md: replaces _generation_schema for schema_version 0.4 points.

    illustration_kind/timeline_shape are two flat, always-required fields rather than the
    content schema's conditional {kind, timeline?} -- structured-output dialects vary in
    how well they support if/then (Gemini's in particular does not), so the model always
    fills timeline_shape and generate.py drops it when the kind isn't "timeline"."""
    locale_map = _locale_map_schema(locales)
    part = {
        "type": "object", "additionalProperties": False, "required": ["text", "role"],
        "properties": {"text": {"type": "string", "minLength": 1}, "role": {"enum": _PATTERN_ROLES}},
    }
    span = {
        "type": "object", "additionalProperties": False, "required": ["start", "end", "role"],
        "properties": {
            "start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 0},
            "role": {"enum": _PATTERN_ROLES},
        },
    }
    example = {
        "type": "object", "additionalProperties": False, "required": ["text", "spans", "annotation", "translation"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "spans": {"type": "array", "items": span},
            "annotation": locale_map,
            "translation": locale_map,
        },
    }
    compare_item = {
        "type": "object", "additionalProperties": False,
        "required": ["with", "this_meaning", "this_example", "other_meaning", "other_example"],
        "properties": {
            "with": {"enum": contrast_with} if contrast_with else {"type": "string"},
            "this_meaning": locale_map, "this_example": {"type": "string", "minLength": 1},
            "other_meaning": locale_map, "other_example": {"type": "string", "minLength": 1},
        },
    }
    common_mistake = {
        "type": "object", "additionalProperties": False,
        "required": ["wrong", "right", "reason", "error_tag", "l1"],
        "properties": {
            "wrong": {"type": "string", "minLength": 1}, "right": {"type": "string", "minLength": 1},
            "reason": locale_map,
            "error_tag": {"enum": error_tags} if error_tags else {"type": "string"},
            "l1": {"type": "array", "minItems": 1, "items": {"enum": l1s} if l1s else {"type": "string"}},
        },
    }
    quick_practice_item = {
        "type": "object", "additionalProperties": False, "required": ["q", "options", "answer", "explain"],
        "properties": {
            "q": {"type": "string", "minLength": 1},
            "options": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string", "minLength": 1}},
            "answer": {"type": "integer", "minimum": 0},
            "explain": locale_map,
        },
    }
    mistake_count = max(1, len(error_tags))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["when_to_use", "pattern", "examples", "compare", "common_mistakes", "quick_practice"],
        "properties": {
            "when_to_use": {"type": "array", "minItems": 2, "maxItems": 4, "items": locale_map},
            "pattern": {
                "type": "object", "additionalProperties": False,
                "required": ["parts", "illustration_kind", "timeline_shape"],
                "properties": {
                    "parts": {"type": "array", "minItems": 1, "items": part},
                    "illustration_kind": {"enum": ["timeline", "word_order", "none"]},
                    "timeline_shape": {"enum": _TIMELINE_SHAPES},
                },
            },
            "examples": {"type": "array", "minItems": num_examples, "maxItems": num_examples, "items": example},
            "compare": {
                "type": "array", "minItems": len(contrast_with), "maxItems": len(contrast_with), "items": compare_item
            },
            "common_mistakes": {
                "type": "array", "minItems": mistake_count, "maxItems": mistake_count, "items": common_mistake
            },
            "quick_practice": {"type": "array", "minItems": 3, "maxItems": 3, "items": quick_practice_item},
        },
    }


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


@dataclass
class Generator:
    lang: str
    l1: str
    llm: LLMClient
    root: Path = LAB_ROOT
    num_examples: int = 2

    def generate(
        self, point_id: str, *, regenerate_note: str | None = None, with_story: bool = False, story_mode: str = "everyday"
    ) -> GenerateOutcome:
        if story_mode not in STORY_MODES:
            raise ValueError(f"story_mode must be one of {sorted(STORY_MODES)}, got {story_mode!r}")
        existing = load_point(self.lang, point_id, self.root)
        if existing is None:
            return GenerateOutcome(point_id, "error", reason="point metadata does not exist yet; seed it from the inventory first")
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
            return self._generate_v04(existing, locales=locales, l1s=l1s, function=function)

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
        result = self.llm.complete(system=system, user=user + note_suffix, json_schema=schema, schema_name="grammar_point_blocks")
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

        cost = result.usage.cost_usd(result.model) or 0.0
        cached = result.cached
        prompt_version = PROMPT_VERSION
        schema_version = existing.get("schema_version", "0.2")
        if with_story:
            story_result, story_block = self._generate_story(existing, locales, mode=story_mode)
            blocks.append(story_block)
            story_cost = story_result.usage.cost_usd(story_result.model)
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
        self, existing: dict[str, Any], *, locales: list[str], l1s: list[str], function: dict[str, Any]
    ) -> GenerateOutcome:
        """GRAMMAR_CONTENT_CONTRACT.md: the six fixed content blocks, replacing generate()'s
        free-form blocks[] path for points already on schema_version 0.4."""
        point_id = existing["id"]
        schema = _generation_schema_v04(
            locales=locales, l1s=l1s, error_tags=existing["error_tags"],
            contrast_with=existing["contrasts"], num_examples=self.num_examples,
        )
        system = PROMPT_PATH_V04.read_text(encoding="utf-8").format(
            point_id=point_id, target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            function_title=function["title"].get("en", function["title"].get("vi", "")),
            function_id=function["id"], locales=", ".join(locales), l1s=", ".join(l1s),
            contrast_with_ids=", ".join(existing["contrasts"]) or "(none)",
            error_tags=", ".join(existing["error_tags"]) or "(none)",
            num_examples=self.num_examples,
        )
        user = f"Write the grammar point {point_id} now, matching the structured output schema."
        result = self.llm.complete(system=system, user=user, json_schema=schema, schema_name="grammar_point_v04")
        data = result.data

        illustration: dict[str, Any] = {"kind": data["pattern"]["illustration_kind"]}
        if illustration["kind"] == "timeline":
            illustration["timeline"] = {"shape": data["pattern"]["timeline_shape"]}
        pattern = {"parts": data["pattern"]["parts"], "illustration": illustration}

        point = {
            **existing,
            "schema_version": "0.4",
            "when_to_use": data["when_to_use"],
            "pattern": pattern,
            "examples": data["examples"],
            "compare": data["compare"],
            "common_mistakes": data["common_mistakes"],
            "quick_practice": data["quick_practice"],
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
        save_point(self.lang, point, self.root)
        return GenerateOutcome(point_id, "written", cost_usd=result.usage.cost_usd(result.model) or None, cached=result.cached)

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
        result = self.llm.complete(system=system, user=user, json_schema=schema, schema_name="story")
        return result, {"type": "story", "theme": "daily", "mode": mode, **result.data}
