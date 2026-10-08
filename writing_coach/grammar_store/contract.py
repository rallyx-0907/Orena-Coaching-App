"""The boundary with Grammar Lab: export profile 1, canonical JSON, hashes (GRAMMAR_CONTENT_STORE.md sections 5 and 11).

One accepted boundary, held here and nowhere else: the profile id, the content schema version it derives from, and
the hash of the vendored profile schema. A package naming anything else is rejected; a new profile is a reviewed
change of these constants and a new vendored file, never a widening.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_EXPORT_PROFILE = "grammar-export-profile/1"
SUPPORTED_SCHEMA_VERSION = "0.4"
PROFILE_SCHEMA_PATH = Path(__file__).parent / "schema" / "export_profile.schema.json"
PROFILE_SCHEMA_HASH = "0671ac912967a230d6073a454f82d6e66e20af67a6adfe3bde95c03c9f06541f"

APP_LANGUAGES = ("en", "zh")
REQUIRED_LOCALES = ("vi", "en")
FUNCTION_LABEL_LOCALES = ("vi", "en", "zh")  # GCC: a function label carries all three (stricter than the exporter)
MANIFEST_KEYS = frozenset({
    "export_profile", "profile_schema_hash", "schema_version", "language", "set_version", "source_commit",
    "source_dirty", "exported_at", "package_hash", "external_references", "functions", "points", "r5_map",
    "validator", "rights",
})
POINT_ENTRY_KEYS = frozenset({"id", "version", "content_hash", "level", "provenance"})
POINT_PROVENANCE_KEYS = frozenset({
    "reviewer", "reviewed_at", "review_seconds", "run_id", "model", "prompt_version", "generated_at", "source_refs",
    "source_anchors", "r5_source",
})
R5_ROW_KEYS = frozenset({"r5_id", "point_id", "is_primary", "disposition"})
DISPOSITIONS = ("replaced", "merged", "split_primary", "split_secondary", "dropped")
PRIMARY_DISPOSITIONS = frozenset({"replaced", "merged", "split_primary"})
# What a learner is ever served of a point body: the profile's top-level keys minus `source_refs` (catalogue codes and
# `r5_split` are provenance; no screen reads them). Decision R3-2.
SERVED_KEYS = frozenset({
    "id", "version", "status", "target_lang", "function", "level", "prereqs", "contrasts", "error_tags", "point_type",
    "header", "when_to_use", "pattern", "examples", "compare", "common_mistakes", "quick_practice", "sequence",
    "aliases", "personal_production",
})


class CanonicalJSONError(ValueError):
    """The value has no canonical form (a float, NaN, a non-string key, a non-JSON type)."""


def _check(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        raise CanonicalJSONError(f"{path}: floats are not allowed in canonical JSON")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError(f"{path}: object keys must be strings")
            _check(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check(item, f"{path}[{index}]")
        return
    raise CanonicalJSONError(f"{path}: {type(value).__name__} is not a JSON value")


def canonical_json(value: Any) -> bytes:
    """Keys sorted by code point at every level, `,`/`:`, UTF-8 unescaped, integers only, no normalisation (section 11)."""
    _check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def package_hash_of(manifest: dict[str, Any]) -> str:
    """The semantic package hash: profile, schema version, language, functions, each point's (id, version, hash) and
    the r5_map. Audit metadata (commit, time, set_version, provenance, validator) is outside it."""
    return content_hash({
        "export_profile": manifest["export_profile"],
        "schema_version": manifest["schema_version"],
        "language": manifest["language"],
        "functions": manifest["functions"],
        "points": [{"id": p["id"], "version": p["version"], "content_hash": p["content_hash"]} for p in manifest["points"]],
        "r5_map": manifest["r5_map"],
    })


@lru_cache(maxsize=1)
def profile_schema() -> dict[str, Any]:
    schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
    if content_hash(schema) != PROFILE_SCHEMA_HASH:
        raise RuntimeError("the vendored export profile does not match PROFILE_SCHEMA_HASH")
    return schema


@lru_cache(maxsize=1)
def profile_validator():
    from jsonschema import Draft202012Validator

    return Draft202012Validator(profile_schema())


def served_point(content: dict[str, Any]) -> dict[str, Any]:
    """The whitelisted body a learner receives (belt and braces over the closed-schema import check)."""
    return {key: value for key, value in content.items() if key in SERVED_KEYS}
