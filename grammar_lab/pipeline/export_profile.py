"""The production export profile: what Orena's importer accepts, derived from Grammar Lab's own schema.

Grammar Lab's ``schema/grammar_set.schema.json`` is internal and multi-version (v0.2/v0.3/v0.4, ``zh-Hans``,
``en`` only required at ``approved``, provenance/review/flags inside the point). The app boundary is narrower
and is **derived** from it by ``derive_profile_schema`` and committed as ``schema/export_profile.schema.json``:

- one version of the point shape (the v0.4 content blocks; no ``blocks``/``title``/``summary``);
- ``target_lang`` is ``en | zh`` and locale-map keys are ``vi | en | zh``, with ``vi`` **and** ``en`` required in
  every map (Grammar Lab's ``zh-Hans`` <-> the app's ``zh`` is ``to_app_point`` / ``from_app_point``);
- ``status`` is the constant ``approved``;
- the point body is authored content: ``provenance``, ``review``, ``flags``, ``source_anchors`` and
  ``schema_version`` never appear in it (audit data travels in the package manifest).

Committing the derived schema and comparing it with a fresh derivation is the upstream-drift check: when the
internal schema changes the export refuses until the profile is regenerated and reviewed.

Canonical JSON (normative, shared with the Orena importer; ``GRAMMAR_CONTENT_STORE`` section 11): UTF-8 bytes
of the value serialised with object keys sorted by Unicode code point at every level, separators ``","`` and
``":"`` (no whitespace), **no** ASCII escaping, integers as integers (a float anywhere is an error), no
NaN/Infinity, no Unicode normalisation (NFC and NFD text hash differently). ``content_hash`` is the lowercase
hex SHA-256 of those bytes for a point body.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.validate import GRAMMAR_SCHEMA_PATH, LAB_ROOT

PROFILE_ID = "grammar-export-profile/1"
PROFILE_SCHEMA_PATH = Path("schema/export_profile.schema.json")
CONTENT_SCHEMA_VERSION = "0.4"  # the internal point shape this profile is derived from

APP_TARGET_LANG = {"en": "en", "zh-Hans": "zh"}  # Grammar Lab target_lang -> app target_lang
APP_LOCALE_KEY = {"zh-Hans": "zh"}  # Grammar Lab locale key -> app locale key
APP_LOCALES = ("vi", "en", "zh")
APP_REQUIRED_LOCALES = ("vi", "en")
# Internal point fields that never reach a point body (audit/review/routing, or superseded shapes).
BODY_DROPPED = ("schema_version", "title", "summary", "blocks", "provenance", "review", "flags", "source_anchors")
BODY_REQUIRED_EXTRA = ("point_type", "header", "when_to_use", "pattern", "examples", "compare", "common_mistakes",
                       "quick_practice", "sequence", "aliases")
APP_LANG_FRAMEWORK = {"en": ("cefr", ["A1", "A2", "B1", "B2", "C1", "C2"]), "zh": ("hsk3", list("123456789"))}


class CanonicalJSONError(ValueError):
    """The value cannot be put into canonical form (a float, NaN, or a non-JSON type)."""


def _check_canonical(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise CanonicalJSONError(f"{path}: floats are not allowed in canonical JSON (use integers)")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError(f"{path}: object keys must be strings")
            _check_canonical(item, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _check_canonical(item, f"{path}[{index}]")
    elif value is not None and not isinstance(value, str | int | bool):
        raise CanonicalJSONError(f"{path}: {type(value).__name__} is not a JSON value")


def canonical_json(value: Any) -> bytes:
    _check_canonical(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _refs(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, item in node.items():
            if key == "$ref" and isinstance(item, str) and item.startswith("#/$defs/"):
                found.add(item.removeprefix("#/$defs/"))
            else:
                found |= _refs(item)
    elif isinstance(node, list):
        for item in node:
            found |= _refs(item)
    return found


def _app_descriptions(node: Any) -> Any:
    """Prose in the derived schema speaks the app's vocabulary: ``zh-Hans`` -> ``zh``."""
    if isinstance(node, dict):
        return {key: (value.replace("zh-Hans", "zh") if key == "description" and isinstance(value, str)
                      else _app_descriptions(value)) for key, value in node.items()}
    if isinstance(node, list):
        return [_app_descriptions(item) for item in node]
    return node


def _language_rule(internal_rules: list[dict[str, Any]], internal_lang: str, app_lang: str) -> dict[str, Any]:
    rule = next(
        r for r in internal_rules
        if r.get("if", {}).get("properties", {}).get("target_lang", {}).get("const") == internal_lang
    )
    rule = copy.deepcopy(rule)
    rule["if"]["properties"]["target_lang"]["const"] = app_lang
    return rule


def derive_profile_schema(internal: dict[str, Any]) -> dict[str, Any]:
    """The closed, single-version export-profile schema for one point body, derived from ``internal``."""
    defs = copy.deepcopy(internal["$defs"])
    point = defs["grammar_point"]
    for name in BODY_DROPPED:
        point["properties"].pop(name, None)
    point["required"] = [
        name for name in point["required"] if name not in BODY_DROPPED
    ] + [name for name in BODY_REQUIRED_EXTRA if name not in point["required"]]
    point["properties"]["status"] = {"const": "approved"}
    point["allOf"] = [
        _language_rule(internal["$defs"]["grammar_point"]["allOf"], internal_lang, app_lang)
        for internal_lang, app_lang in APP_TARGET_LANG.items()
    ]
    point["properties"]["aliases"]["description"] = (
        "R5 ids this point is the PRIMARY replacement of (an R5 id is an alias of exactly one point; other pieces "
        "of a split record the relationship in source_refs.r5_split, never here)."
    )
    point.pop("not", None)

    defs["target_lang"] = {"description": "App target language.", "enum": list(APP_TARGET_LANG.values())}
    defs["locale"] = {"description": "App explanation locale key.", "enum": list(APP_LOCALES)}
    defs["locale_map"] = {
        "description": "vi and en are both required in every locale map; zh is optional.",
        "type": "object", "minProperties": 2, "required": list(APP_REQUIRED_LOCALES),
        "propertyNames": {"$ref": "#/$defs/locale"},
        "additionalProperties": {"type": "string", "minLength": 1},
    }
    defs["point_id"] = {
        "description": "<lang>.<slug>; lang is en | zh. Immutable after publish.",
        "type": "string", "pattern": "^(en|zh)\\.[a-z0-9_]+(\\.[a-z0-9_]+)*$",
    }
    defs["level"]["properties"]["framework"] = {"enum": [framework for framework, _ in APP_LANG_FRAMEWORK.values()]}
    root: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:orena:grammar_lab:export_profile:1",
        "title": "Orena grammar export profile 1: one approved point body",
        "description": (
            "Derived from grammar_set.schema.json by pipeline/export_profile.py; do not edit by hand. Closed at every "
            "object. Audit data (provenance, review, flags, source anchors) lives in the package manifest."
        ),
        "$ref": "#/$defs/grammar_point",
    }
    reachable: set[str] = set()
    frontier = {"grammar_point"}
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        frontier |= _refs(defs[name]) - reachable
    root["$defs"] = {name: defs[name] for name in sorted(reachable)}
    return _app_descriptions(root)


def load_internal_schema(root: Path = LAB_ROOT) -> dict[str, Any]:
    return read_json(root / GRAMMAR_SCHEMA_PATH)


def load_profile_schema(root: Path = LAB_ROOT) -> dict[str, Any]:
    return read_json(root / PROFILE_SCHEMA_PATH)


def profile_drift(root: Path = LAB_ROOT) -> str | None:
    """None when the committed profile schema is exactly what the internal schema derives to now."""
    path = root / PROFILE_SCHEMA_PATH
    if not path.exists():
        return f"{PROFILE_SCHEMA_PATH} is missing; run `export-profile --write`"
    if load_profile_schema(root) != derive_profile_schema(load_internal_schema(root)):
        return f"{PROFILE_SCHEMA_PATH} differs from what grammar_set.schema.json derives to; regenerate and review it"
    return None


def profile_schema_hash(root: Path = LAB_ROOT) -> str:
    return content_hash(load_profile_schema(root))


def iter_locale_maps(point: dict[str, Any]) -> Any:
    """Every locale map of a point body, in either key vocabulary (shares validate's traversal)."""
    from grammar_lab.pipeline.validate import _locale_maps

    return _locale_maps(point)


def to_app_point(point: dict[str, Any]) -> dict[str, Any]:
    """Grammar Lab point -> app body shape: drop audit fields, ``zh-Hans`` -> ``zh``. Never adds text."""
    body = copy.deepcopy({key: value for key, value in point.items() if key not in BODY_DROPPED})
    for _, mapping in iter_locale_maps(body):
        for internal, app in APP_LOCALE_KEY.items():
            if internal in mapping:
                mapping[app] = mapping.pop(internal)
    body["target_lang"] = APP_TARGET_LANG[body["target_lang"]]
    return body


def from_app_point(body: dict[str, Any]) -> dict[str, Any]:
    """Inverse of ``to_app_point`` on what it touches (locale keys and ``target_lang``); audit fields stay dropped."""
    out = copy.deepcopy(body)
    back = {app: internal for internal, app in APP_LOCALE_KEY.items()}
    for _, mapping in iter_locale_maps(out):
        for app, internal in back.items():
            if app in mapping:
                mapping[internal] = mapping.pop(app)
    out["target_lang"] = {app: internal for internal, app in APP_TARGET_LANG.items()}[out["target_lang"]]
    return out


def _vietnamese_letter(char: str) -> bool:
    """A Latin letter outside ASCII (an accented Vietnamese vowel): text that cannot be English as written."""
    return not char.isascii() and unicodedata.name(char, "").startswith("LATIN")


def locale_problems(body: dict[str, Any]) -> list[str]:
    """Missing required locales, and ``en`` that is a copy of ``vi`` (a placeholder, never real English)."""
    problems: list[str] = []
    for path, mapping in iter_locale_maps(body):
        for key in APP_REQUIRED_LOCALES:
            if key not in mapping:
                problems.append(f"{path}: locale.missing {key}")
        if "vi" in mapping and mapping.get("en") == mapping["vi"] and any(_vietnamese_letter(c) for c in mapping["vi"]):
            problems.append(f"{path}: locale.en_placeholder (en is a copy of vi)")
    return problems
