"""Grammar export package v1: build and validate the approved package Orena Admin imports (D-105).

Grammar Lab -> **approved export package** -> Orena Admin import -> immutable DB versions -> accept / rights /
publish -> ``/api/grammar/v1/*`` -> the ``/next`` renderer. This module is the first arrow. It never calls a
provider, never writes into ``content/`` and never sets ``approved``.

Package layout (``GRAMMAR_CONTENT_STORE`` section 5.2)::

    package.json      manifest: profile, hashes, per-point audit provenance, r5_map, validator verdict, rights
    functions.json    [{id, title: {vi, en, zh?}}]
    points/<id>.json  one approved point body, authored content only (export profile 1)

``export_package`` fails closed: it collects every problem and writes nothing unless there are none. The same
checks run again over the written files by ``validate_package``, which reads nothing from ``content/``.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from grammar_lab.pipeline.canonical import catalog_is_current
from grammar_lab.pipeline.content_store import load_functions, load_point
from grammar_lab.pipeline.export_profile import (
    APP_LOCALE_KEY, APP_REQUIRED_LOCALES, CONTENT_SCHEMA_VERSION, PROFILE_ID, content_hash, load_profile_schema,
    locale_problems, profile_drift, profile_schema_hash, to_app_point,
)
from grammar_lab.pipeline.jsonio import read_json, write_json
from grammar_lab.pipeline.r5_map import build_r5_map, validate_r5_map
from grammar_lab.pipeline.seed import apply_seed, load_catalog
from grammar_lab.pipeline.validate import LAB_ROOT, LANGS, validate_lang

APP_LANGS = ("en", "zh")
TOOL = "grammar_lab.export_package"
TOOL_VERSION = "1"
MANIFEST_KEYS = {
    "export_profile", "profile_schema_hash", "schema_version", "language", "set_version", "source_commit",
    "source_dirty", "exported_at", "package_hash", "external_references", "functions", "points", "r5_map",
    "validator", "rights",
}
POINT_PROVENANCE_KEYS = {
    "reviewer", "reviewed_at", "review_seconds", "run_id", "model", "prompt_version", "generated_at",
    "source_refs", "source_anchors",
}
RIGHTS = {
    "source_text_policy": "catalogue_codes_only",
    "external_text_included": False,
    "attestation_required_at_import": True,
    "note": "Grammar Lab records catalogue codes, never source text; the rights basis and attestation are the "
            "human statement made in Admin at import (GRAMMAR_CONTENT_STORE section 6), not made here.",
}


class ExportError(Exception):
    """The package cannot be built or is invalid; ``problems`` lists every reason, nothing was written."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class ExportResult:
    out_dir: Path
    package_hash: str
    manifest: dict[str, Any]
    points: list[str] = field(default_factory=list)


def package_hash_of(manifest: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the semantic package: profile, language, functions, every point's
    ``(id, version, content_hash)`` and the r5_map. Audit metadata (commit, time, set_version, provenance, validator
    verdict) is deliberately outside it, so re-exporting the same content gives the same hash."""
    return content_hash({
        "export_profile": manifest["export_profile"],
        "schema_version": manifest["schema_version"],
        "language": manifest["language"],
        "functions": manifest["functions"],
        "points": [{"id": p["id"], "version": p["version"], "content_hash": p["content_hash"]} for p in manifest["points"]],
        "r5_map": manifest["r5_map"],
    })


def _app_function(function: dict[str, Any]) -> dict[str, Any]:
    title = {APP_LOCALE_KEY.get(key, key): value for key, value in function["title"].items()}
    return {"id": function["id"], "title": title}


def _function_problems(function: dict[str, Any]) -> list[str]:
    problems = [f"function {function['id']}: title.{key} missing" for key in APP_REQUIRED_LOCALES if key not in function["title"]]
    title = function["title"]
    if title.get("en") and title.get("en") == title.get("vi") and any(not c.isascii() for c in title["vi"]):
        problems.append(f"function {function['id']}: locale.en_placeholder (en is a copy of vi)")
    return problems


def _references(body: dict[str, Any]) -> list[str]:
    return sorted({*body.get("prereqs", []), *body.get("contrasts", []), *(c["with"] for c in body.get("compare", []))})


def _structure_problems(bodies: dict[str, dict[str, Any]], external: set[str], language: str) -> list[str]:
    problems: list[str] = []
    for point_id, body in bodies.items():
        if not point_id.startswith(f"{language}."):
            problems.append(f"{point_id}: id does not start with the package language {language}.")
        if body["target_lang"] != language:
            problems.append(f"{point_id}: target_lang {body['target_lang']!r} != package language {language!r}")
        for ref in _references(body):
            if ref not in bodies and ref not in external:
                problems.append(f"{point_id}: ref.unresolved {ref} (not in the package and not declared external)")
        for other in body.get("contrasts", []):
            if other in bodies and point_id not in bodies[other].get("contrasts", []):
                problems.append(f"{point_id}: contrasts.asymmetric with {other}")
        for item in body.get("compare", []):
            if item["with"] not in body.get("contrasts", []):
                problems.append(f"{point_id}: compare.with {item['with']} is not in contrasts")
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        state[node] = 1
        for prereq in bodies[node].get("prereqs", []):
            if prereq not in bodies:
                continue
            if state.get(prereq) == 1:
                problems.append(f"{node}: prereqs cycle through {prereq}")
            elif prereq not in state:
                visit(prereq)
        state[node] = 2

    for point_id in bodies:
        if point_id not in state:
            visit(point_id)
    return problems


def _schema_problems(bodies: dict[str, dict[str, Any]], root: Path) -> list[str]:
    validator = Draft202012Validator(load_profile_schema(root))
    return [
        f"{point_id}: profile.schema {'.'.join(str(p) for p in error.path) or '$'}: {error.message[:200]}"
        for point_id, body in bodies.items()
        for error in sorted(validator.iter_errors(body), key=lambda e: list(e.path))
    ]


def _validate_selected(lang: str, root: Path, resolved: dict[str, dict[str, Any]]) -> list[str]:
    """validate_lang over the language's content with the selected points replaced by their catalogue-resolved form."""
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        for name in ("schema", "functions", "cast"):
            if (root / name).exists():
                shutil.copytree(root / name, work / name)
        shutil.copytree(root / "content" / lang, work / "content" / lang)
        for point_id, point in resolved.items():
            write_json(work / "content" / lang / f"{point_id}.json", point)
        report = validate_lang(lang, work)
    wanted = {f"content/{lang}/{point_id}.json" for point_id in resolved}
    return [f"{issue.file.split('/')[-1][:-5]}: validate:{issue.code} {issue.path} {issue.message}"
            for issue in report.issues if issue.file in wanted or issue.file.replace("\\", "/") in wanted]


def export_package(
    lang: str, ids: list[str], root: Path = LAB_ROOT, out_dir: Path | None = None, *, set_version: str,
    source_commit: str, source_dirty: bool = False, exported_at: str | None = None, dropped: list[str] | None = None,
) -> ExportResult:
    """Build ``out_dir`` from the approved points ``ids``; raise ``ExportError`` (nothing written) on any problem."""
    if lang not in LANGS:
        raise ExportError([f"lang {lang!r} is not one of {', '.join(LANGS)}"])
    language = "en" if lang == "en" else "zh"
    ids = sorted(set(ids))
    problems: list[str] = []
    if not ids:
        raise ExportError(["no points selected"])
    if not set_version or not source_commit:
        problems.append("set_version and source_commit are required")
    drift = profile_drift(root)
    if drift:
        problems.append(f"profile.drift: {drift}")
    if not catalog_is_current(lang, root):
        problems.append(f"catalog.stale: inventory/catalog_{lang}.yaml is missing or stale against canonical_v1; run import-canonical")
    records = load_catalog(lang, root)
    by_id = {record["id"]: record for record in records}

    resolved: dict[str, dict[str, Any]] = {}
    for point_id in ids:
        record = by_id.get(point_id)
        point = load_point(lang, point_id, root)
        if record is None:
            problems.append(f"{point_id}: point.not_in_catalog")
        elif record.get("catalog", {}).get("metadata_origin") == "default_safe":
            problems.append(f"{point_id}: metadata.default_safe (metadata never reviewed)")
        if point is None:
            problems.append(f"{point_id}: point.no_content")
        elif point.get("status") != "approved":
            problems.append(f"{point_id}: point.not_approved (status {point.get('status')!r})")
        elif point.get("flags"):
            problems.append(f"{point_id}: point.flagged {point['flags']}")
        elif not point.get("review"):
            problems.append(f"{point_id}: point.no_review")
        elif record is not None and record.get("catalog", {}).get("metadata_origin") != "default_safe":
            resolved[point_id] = apply_seed(point, lang, point_id, root)  # type: ignore[assignment]
    if problems:
        raise ExportError(problems)  # nothing below is meaningful for points that are not exportable

    problems += _validate_selected(lang, root, resolved)
    bodies: dict[str, dict[str, Any]] = {}
    for point_id, point in resolved.items():
        body = to_app_point(point)
        aliases = set(body.get("aliases", []))
        r5_ids = by_id[point_id].get("r5", [])
        refs = {key: value for key, value in body.get("source_refs", {}).items() if key != "r5"}
        if [r5 for r5 in r5_ids if r5 in aliases]:
            refs["r5"] = [r5 for r5 in r5_ids if r5 in aliases]
        if [r5 for r5 in r5_ids if r5 not in aliases]:
            refs["r5_split"] = [r5 for r5 in r5_ids if r5 not in aliases]
        body["source_refs"] = refs
        bodies[point_id] = body
        problems += [f"{point_id}: {problem}" for problem in locale_problems(body)]
    problems += _schema_problems(bodies, root)

    on_disk_approved = {
        point_id for point_id in by_id
        if point_id not in bodies and (other := load_point(lang, point_id, root)) and other.get("status") == "approved"
    }
    external = {ref for body in bodies.values() for ref in _references(body) if ref not in bodies and ref in on_disk_approved}
    problems += _structure_problems(bodies, external, language)

    functions_all = {f["id"]: f for f in load_functions(root)["functions"]}
    used = sorted({body["function"] for body in bodies.values()})
    functions: list[dict[str, Any]] = []
    for function_id in used:
        if function_id not in functions_all:
            problems.append(f"function {function_id}: unknown")
            continue
        problems += _function_problems(_app_function(functions_all[function_id]))
        functions.append(_app_function(functions_all[function_id]))

    rows, r5_problems = build_r5_map(records, ids, dropped)
    problems += r5_problems + validate_r5_map(rows, bodies)
    if problems:
        raise ExportError(problems)

    entries = []
    for point_id in sorted(bodies):
        point = resolved[point_id]
        entries.append({
            "id": point_id, "version": point["version"], "content_hash": content_hash(bodies[point_id]),
            "level": point["level"],
            "provenance": {
                "reviewer": point["review"]["reviewer"], "reviewed_at": point["review"]["reviewed_at"],
                "review_seconds": point["review"]["seconds"], "run_id": point["provenance"]["run_id"],
                "model": point["provenance"]["model"], "prompt_version": point["provenance"]["prompt_version"],
                "generated_at": point["provenance"]["generated_at"],
                "source_refs": point.get("source_refs", {}), "source_anchors": point.get("source_anchors"),
                **({"r5_source": point["provenance"]["r5_source"]} if "r5_source" in point["provenance"] else {}),
            },
        })
    manifest: dict[str, Any] = {
        "export_profile": PROFILE_ID, "profile_schema_hash": profile_schema_hash(root),
        "schema_version": CONTENT_SCHEMA_VERSION, "language": language, "set_version": set_version,
        "source_commit": source_commit, "source_dirty": source_dirty,
        "exported_at": exported_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "external_references": sorted(external), "functions": functions, "points": entries, "r5_map": rows,
        "validator": {"tool": TOOL, "version": TOOL_VERSION, "passed": True, "codes": []},
        "rights": dict(RIGHTS),
    }
    manifest["package_hash"] = package_hash_of(manifest)

    target = out_dir or (root / "export" / lang)
    if target.exists() and any(target.iterdir()):
        raise ExportError([f"{target} is not empty; choose a new directory"])
    for point_id, body in bodies.items():
        write_json(target / "points" / f"{point_id}.json", body)
    write_json(target / "functions.json", functions)
    write_json(target / "package.json", manifest)
    after = validate_package(target, root)
    if after:
        shutil.rmtree(target)
        raise ExportError([f"written package failed its own validation: {p}" for p in after])
    return ExportResult(target, manifest["package_hash"], manifest, sorted(bodies))


def validate_package(path: Path, root: Path = LAB_ROOT) -> list[str]:
    """Problems of a package directory, read from its files alone (empty = valid). Mirrors the importer's hard checks."""
    problems: list[str] = []
    try:
        manifest = read_json(path / "package.json")
        functions = read_json(path / "functions.json")
    except (OSError, ValueError) as exc:
        return [f"package unreadable: {exc}"]
    if set(manifest) != MANIFEST_KEYS:
        return [f"manifest keys differ: missing {sorted(MANIFEST_KEYS - set(manifest))}, extra {sorted(set(manifest) - MANIFEST_KEYS)}"]
    if manifest["export_profile"] != PROFILE_ID:
        problems.append(f"export_profile {manifest['export_profile']!r} != {PROFILE_ID!r}")
    if manifest["schema_version"] != CONTENT_SCHEMA_VERSION:
        problems.append(f"schema_version {manifest['schema_version']!r} != {CONTENT_SCHEMA_VERSION!r}")
    drift = profile_drift(root)
    if drift:
        problems.append(f"profile.drift: {drift}")
    elif manifest["profile_schema_hash"] != profile_schema_hash(root):
        problems.append("profile_schema_hash does not match the profile schema in use")
    language = manifest["language"]
    if language not in APP_LANGS:
        problems.append(f"language {language!r} is not one of {', '.join(APP_LANGS)}")
    if manifest["validator"].get("passed") is not True:
        problems.append("validator.passed is not true")
    if manifest["functions"] != functions:
        problems.append("functions.json differs from manifest.functions")

    listed = {entry["id"]: entry for entry in manifest["points"]}
    if len(listed) != len(manifest["points"]):
        problems.append("duplicate point ids in the manifest")
    files = {p.name[:-5] for p in (path / "points").glob("*.json")} if (path / "points").exists() else set()
    for missing in sorted(set(listed) - files):
        problems.append(f"{missing}: listed in the manifest, file missing")
    for extra in sorted(files - set(listed)):
        problems.append(f"{extra}: file present, not listed in the manifest")
    bodies: dict[str, dict[str, Any]] = {}
    for point_id in sorted(set(listed) & files):
        body = read_json(path / "points" / f"{point_id}.json")
        bodies[point_id] = body
        if body.get("id") != point_id:
            problems.append(f"{point_id}: id differs from its filename")
        try:
            digest = content_hash(body)
        except ValueError as exc:
            problems.append(f"{point_id}: not canonical JSON: {exc}")
            continue
        if digest != listed[point_id]["content_hash"]:
            problems.append(f"{point_id}: content_hash does not match the file")
        if body.get("version") != listed[point_id]["version"]:
            problems.append(f"{point_id}: manifest version differs from the point")
        if body.get("status") != "approved":
            problems.append(f"{point_id}: point.not_approved (status {body.get('status')!r})")
        if set(listed[point_id]["provenance"]) - POINT_PROVENANCE_KEYS - {"r5_source"}:
            problems.append(f"{point_id}: unknown provenance keys")
        problems += [f"{point_id}: {problem}" for problem in locale_problems(body)]
    problems += _schema_problems(bodies, root)
    for function in functions:
        problems += _function_problems(function)
    used = {body.get("function") for body in bodies.values()}
    for missing_function in sorted(used - {f["id"] for f in functions}):
        problems.append(f"function {missing_function}: no label in functions.json")
    external = set(manifest["external_references"])
    problems += _structure_problems(bodies, external, language)
    problems += validate_r5_map(manifest["r5_map"], bodies)
    if manifest["package_hash"] != package_hash_of(manifest):
        problems.append("package_hash does not match the manifest content")
    return problems


def package_to_zip(directory: Path, zip_path: Path) -> Path:
    """A deterministic zip of a package directory (sorted members, fixed timestamps) for the Admin upload."""
    members = sorted(p for p in directory.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            info = zipfile.ZipInfo(member.relative_to(directory).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, member.read_bytes())
    return zip_path

