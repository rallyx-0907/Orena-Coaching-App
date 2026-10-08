"""Read and validate one Grammar Lab export package (export profile 1) - GRAMMAR_CONTENT_STORE.md sections 5.1-5.5.

Everything in the upload is untrusted. Reading enforces the byte budgets while decompressing (the sender controls the
zip headers, so `ZipInfo.file_size` is never believed); validation re-derives every hash and runs the closed profile
schema plus the cross checks a schema cannot express. This module touches no database: checks that need the store
(external references, per-point version refusals) live in the importer.
"""
from __future__ import annotations

import io
import json
import stat
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Any

from writing_coach.grammar_store import contract

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 2000
MAX_MEMBER_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = 64
_CHUNK = 64 * 1024


@dataclass(frozen=True)
class Problem:
    code: str
    path: str
    message: str
    point_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "point_id": self.point_id, "path": self.path, "message": self.message[:300]}


class PackageError(Exception):
    """The upload cannot be read as a package at all (budget, zip shape, JSON)."""

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(f"{p.code}: {p.message}" for p in problems))
        self.problems = problems


@dataclass
class Package:
    manifest: dict[str, Any]
    functions: list[Any]
    bodies: dict[str, Any]  # file stem -> parsed body
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def language(self) -> str:
        return str(self.manifest.get("language", "")) if isinstance(self.manifest, dict) else ""


# --- Reading -------------------------------------------------------------------------------------------------------

def _depth_ok(value: Any) -> bool:
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            return False
        if isinstance(node, dict):
            stack.extend((item, depth + 1) for item in node.values())
        elif isinstance(node, list):
            stack.extend((item, depth + 1) for item in node)
    return True


def _parse(name: str, raw: bytes) -> Any:
    try:
        value = json.loads(raw.decode("utf-8"))
    except RecursionError as exc:  # nesting the decoder itself cannot follow
        raise PackageError([Problem("package.json_too_deep", name, f"nesting deeper than {MAX_JSON_DEPTH}")]) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise PackageError([Problem("package.json_invalid", name, f"not UTF-8 JSON: {exc}")]) from exc
    if not _depth_ok(value):
        raise PackageError([Problem("package.json_too_deep", name, f"nesting deeper than {MAX_JSON_DEPTH}")])
    return value


def _allowed_name(name: str) -> bool:
    if name in {"package.json", "functions.json"}:
        return True
    head, _, stem = name.partition("/")
    return head == "points" and stem.endswith(".json") and "/" not in stem and len(stem) > len(".json")


def read_package(data: bytes) -> Package:
    """A package from the bytes of a deterministic zip (`package_to_zip` upstream). Raises PackageError."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PackageError([Problem("package.too_large", "$", f"upload exceeds {MAX_UPLOAD_BYTES} bytes")])
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PackageError([Problem("package.not_zip", "$", str(exc))]) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise PackageError([Problem("package.too_many_members", "$", f"more than {MAX_MEMBERS} members")])
        files: dict[str, bytes] = {}
        total = 0
        for info in infos:
            name = info.filename
            if info.is_dir():
                if name.rstrip("/") == "points":
                    continue
                raise PackageError([Problem("package.member_refused", name, "directories other than points/")])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise PackageError([Problem("package.member_refused", name, "symbolic link")])
            if name.startswith("/") or "\\" in name or ".." in name.split("/") or not _allowed_name(name):
                raise PackageError([Problem("package.member_refused", name, "only package.json, functions.json and"
                                                                            " points/<id>.json are allowed")])
            if name in files:
                raise PackageError([Problem("package.member_refused", name, "duplicate member")])
            produced = bytearray()
            with archive.open(info) as stream:  # budgets on bytes actually produced, never on the header
                while chunk := stream.read(_CHUNK):
                    produced += chunk
                    total += len(chunk)
                    if len(produced) > MAX_MEMBER_BYTES:
                        raise PackageError([Problem("package.member_too_large", name, f"over {MAX_MEMBER_BYTES} bytes")])
                    if total > MAX_TOTAL_BYTES:
                        raise PackageError([Problem("package.too_large", "$", f"over {MAX_TOTAL_BYTES} bytes unpacked")])
            files[name] = bytes(produced)
    for required in ("package.json", "functions.json"):
        if required not in files:
            raise PackageError([Problem("package.member_missing", required, "required member missing")])
    manifest = _parse("package.json", files.pop("package.json"))
    functions = _parse("functions.json", files.pop("functions.json"))
    bodies = {name[len("points/"):-len(".json")]: _parse(name, raw) for name, raw in sorted(files.items())}
    return Package(manifest=manifest, functions=functions, bodies=bodies)


# --- Validation ------------------------------------------------------------------------------------------------------

def _locale_maps(node: Any, path: str = "$"):
    if isinstance(node, dict):
        if "vi" in node and set(node) <= {"vi", "en", "zh"} and all(isinstance(v, str) for v in node.values()):
            yield path, node
            return
        for key, value in node.items():
            yield from _locale_maps(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _locale_maps(value, f"{path}[{index}]")


def _vietnamese_letter(char: str) -> bool:
    return not char.isascii() and unicodedata.name(char, "").startswith("LATIN")


def _references(body: dict[str, Any]) -> set[str]:
    return {*body.get("prereqs", []), *body.get("contrasts", []), *(c.get("with") for c in body.get("compare", []))}


def _manifest_problems(pkg: Package) -> list[Problem]:
    m = pkg.manifest
    if not isinstance(m, dict):
        return [Problem("manifest.shape", "package.json", "the manifest is not an object")]
    if set(m) != contract.MANIFEST_KEYS:
        return [Problem("manifest.keys", "package.json",
                        f"missing {sorted(contract.MANIFEST_KEYS - set(m))}, unknown {sorted(set(m) - contract.MANIFEST_KEYS)}")]
    out: list[Problem] = []
    if m["export_profile"] != contract.SUPPORTED_EXPORT_PROFILE:
        out.append(Problem("profile.unsupported", "export_profile", f"{m['export_profile']!r} is not supported"))
    if m["schema_version"] != contract.SUPPORTED_SCHEMA_VERSION:
        out.append(Problem("profile.unsupported", "schema_version", f"{m['schema_version']!r} is not supported"))
    if m["profile_schema_hash"] != contract.PROFILE_SCHEMA_HASH:
        out.append(Problem("profile.unsupported", "profile_schema_hash", "not the vendored export profile"))
    if m["language"] not in contract.APP_LANGUAGES:
        out.append(Problem("language.unsupported", "language", f"{m['language']!r} is not one of en, zh"))
    if m["source_dirty"] is not False:
        out.append(Problem("source.dirty", "source_dirty", "exported from a modified Grammar Lab tree (decision R3-1)"))
    if not isinstance(m["validator"], dict) or m["validator"].get("passed") is not True:
        out.append(Problem("validator.not_passed", "validator", "the exporter's own validation did not pass"))
    for key in ("set_version", "source_commit", "exported_at"):
        if not isinstance(m[key], str) or not m[key]:
            out.append(Problem("manifest.field", key, "must be a non-empty string"))
    for key in ("points", "functions", "r5_map", "external_references"):
        if not isinstance(m[key], list):
            out.append(Problem("manifest.field", key, "must be a list"))
    if out:
        return out
    seen: set[str] = set()
    for index, entry in enumerate(m["points"]):
        path = f"points[{index}]"
        if not isinstance(entry, dict) or set(entry) - contract.POINT_ENTRY_KEYS or \
                {"id", "version", "content_hash", "provenance"} - set(entry):
            out.append(Problem("manifest.point_keys", path, "a point entry has unknown or missing keys"))
            continue
        if not isinstance(entry["provenance"], dict) or set(entry["provenance"]) - contract.POINT_PROVENANCE_KEYS:
            out.append(Problem("manifest.provenance_keys", path, "unknown provenance keys", str(entry["id"])))
        if entry["id"] in seen:
            out.append(Problem("points.duplicate", path, "duplicate point id", str(entry["id"])))
        seen.add(entry["id"])
    if pkg.functions != m["functions"]:
        out.append(Problem("functions.mismatch", "functions.json", "functions.json differs from manifest.functions"))
    if not out:
        try:
            if contract.package_hash_of(m) != m["package_hash"]:
                out.append(Problem("package.hash_mismatch", "package_hash", "does not match the manifest content"))
        except (contract.CanonicalJSONError, KeyError, TypeError) as exc:
            out.append(Problem("package.hash_mismatch", "package_hash", f"cannot be recomputed: {exc}"))
    return out


def _point_problems(point_id: str, body: Any, entry: dict[str, Any], language: str) -> list[Problem]:
    def p(code: str, path: str, message: str) -> Problem:
        return Problem(code, path, message, point_id)

    if not isinstance(body, dict):
        return [p("profile.schema", "$", "a point body must be an object")]
    out: list[Problem] = []
    if body.get("id") != point_id:
        out.append(p("point.id_mismatch", "id", "differs from its file name"))
    try:
        if contract.content_hash(body) != entry["content_hash"]:
            out.append(p("point.hash_mismatch", "$", "content_hash does not match the file"))
    except contract.CanonicalJSONError as exc:
        return out + [p("point.not_canonical", "$", str(exc))]
    if body.get("version") != entry["version"]:
        out.append(p("point.version_mismatch", "version", "differs from the manifest"))
    errors = sorted(contract.profile_validator().iter_errors(body), key=lambda e: list(e.absolute_path))
    out += [p("profile.schema", "$." + ".".join(map(str, e.absolute_path)), e.message[:200]) for e in errors]
    if errors:
        return out  # the cross checks below assume the closed shape
    if not point_id.startswith(f"{language}.") or body["target_lang"] != language:
        out.append(p("point.language", "target_lang", f"not a point of the package language {language!r}"))
    for path, mapping in _locale_maps(body):
        out += [p("locale.missing", path, f"{key} missing") for key in contract.REQUIRED_LOCALES if key not in mapping]
        if mapping.get("en") == mapping.get("vi") and any(_vietnamese_letter(c) for c in mapping.get("vi", "")):
            out.append(p("locale.en_placeholder", path, "en is a copy of vi"))
    if body["header"]["level"] != body["level"]:
        out.append(p("header.level_mismatch", "header.level", "differs from level"))
    for index, example in enumerate(body["examples"]):
        for s_index, span in enumerate(example["spans"]):
            if not 0 <= span["start"] < span["end"] <= len(example["text"]):
                out.append(p("example.span_invalid", f"examples[{index}].spans[{s_index}]", "span outside its sentence"))
    for index, item in enumerate(body["quick_practice"]):
        if item["answer"] >= len(item["options"]):
            out.append(p("quick_practice.answer_out_of_range", f"quick_practice[{index}].answer", "no such option"))
    for index, item in enumerate(body["compare"]):
        if item["with"] not in body["contrasts"]:
            out.append(p("compare.not_in_contrasts", f"compare[{index}].with", f"{item['with']} is not in contrasts"))
    return out


def _structure_problems(bodies: dict[str, dict[str, Any]], external: set[str]) -> list[Problem]:
    out: list[Problem] = []
    for point_id, body in bodies.items():
        for ref in sorted(_references(body)):
            if ref not in bodies and ref not in external:
                out.append(Problem("ref.unresolved", "$", f"{ref} is neither in the package nor external", point_id))
        for other in body["contrasts"]:
            if other in bodies and point_id not in bodies[other]["contrasts"]:
                out.append(Problem("contrasts.asymmetric", "contrasts", f"{other} does not list it back", point_id))
    state: dict[str, int] = {}
    for start in sorted(bodies):
        if start in state:
            continue
        stack = [(start, iter(bodies[start]["prereqs"]))]
        state[start] = 1
        while stack:
            node, children = stack[-1]
            nxt = next((c for c in children if c in bodies), None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                out.append(Problem("prereqs.cycle", "prereqs", f"cycle through {nxt}", node))
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(bodies[nxt]["prereqs"])))
    return out


def _function_problems(functions: list[Any], bodies: dict[str, dict[str, Any]]) -> list[Problem]:
    out: list[Problem] = []
    labels: dict[str, Any] = {}
    for index, function in enumerate(functions):
        if not isinstance(function, dict) or set(function) != {"id", "title"} or not isinstance(function["title"], dict):
            out.append(Problem("function.shape", f"functions[{index}]", "a function is exactly {id, title}"))
            continue
        labels[function["id"]] = function["title"]
        title = function["title"]
        if set(title) - set(contract.FUNCTION_LABEL_LOCALES) or not all(
                isinstance(title.get(k), str) and title.get(k) for k in contract.FUNCTION_LABEL_LOCALES):
            out.append(Problem("function.label_incomplete", f"functions[{index}].title",
                               f"{function['id']} needs vi, en and zh (GCC), and nothing else"))
    for function_id in sorted({body["function"] for body in bodies.values()} - set(labels)):
        out.append(Problem("function.missing", "functions.json", f"{function_id} has no label"))
    return out


def r5_map_problems(rows: list[Any], bodies: dict[str, dict[str, Any]]) -> list[Problem]:
    """Section 9.2, the same rules upstream's `validate_r5_map` runs. Nothing is inferred from aliases."""
    out: list[Problem] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != contract.R5_ROW_KEYS:
            out.append(Problem("r5_map.shape", f"r5_map[{index}]", "keys must be exactly r5_id, point_id, is_primary, disposition"))
            continue
        if row["disposition"] not in contract.DISPOSITIONS or not isinstance(row["is_primary"], bool) \
                or not isinstance(row["r5_id"], str) or not row["r5_id"]:
            out.append(Problem("r5_map.shape", f"r5_map[{index}]", "unknown disposition or bad field types"))
            continue
        if (row["disposition"] == "dropped") != (row["point_id"] is None):
            out.append(Problem("r5_map.dropped", f"r5_map[{index}]", "point_id is null exactly when dropped"))
        if row["is_primary"] != (row["disposition"] in contract.PRIMARY_DISPOSITIONS):
            out.append(Problem("r5_map.primary", f"r5_map[{index}]", "is_primary disagrees with the disposition"))
        if row["point_id"] is not None and row["point_id"] not in bodies:
            out.append(Problem("r5_map.unknown_point", f"r5_map[{index}]", f"{row['point_id']} is not in the package"))
        groups.setdefault(row["r5_id"], []).append(row)
    owners: dict[str, list[str]] = {}
    for point_id, body in bodies.items():
        for alias in body["aliases"]:
            owners.setdefault(alias, []).append(point_id)
    for alias, points in sorted(owners.items()):
        if len(points) > 1:
            out.append(Problem("aliases.duplicate", "aliases", f"{alias} is an alias of {', '.join(sorted(points))}"))
        if alias not in groups:
            out.append(Problem("r5_map.missing", "aliases", f"{alias} has no r5_map row", points[0]))
    for r5_id, group in sorted(groups.items()):
        dropped = [r for r in group if r["disposition"] == "dropped"]
        primaries = [r for r in group if r["is_primary"]]
        secondaries = [r for r in group if r["disposition"] == "split_secondary"]
        if dropped:
            if len(group) > 1:
                out.append(Problem("r5_map.dropped_and_mapped", "r5_map", f"{r5_id} is dropped and also mapped"))
            continue
        if len(primaries) != 1:
            out.append(Problem("r5_map.primary", "r5_map", f"{r5_id} has {len(primaries)} primary rows; one required"))
            continue
        primary = primaries[0]
        if secondaries and primary["disposition"] != "split_primary":
            out.append(Problem("r5_map.split", "r5_map", f"{r5_id} has secondaries but a {primary['disposition']} primary"))
        if primary["disposition"] == "split_primary" and not secondaries:
            out.append(Problem("r5_map.split", "r5_map", f"{r5_id} is split_primary without a secondary"))
        if len({r["point_id"] for r in group}) != len(group):
            out.append(Problem("r5_map.duplicate_row", "r5_map", f"{r5_id} lists a point twice"))
        if primary["point_id"] in bodies and r5_id not in bodies[primary["point_id"]]["aliases"]:
            out.append(Problem("r5_map.alias", "aliases", f"primary does not list {r5_id}", primary["point_id"]))
        for row in secondaries:
            body = bodies.get(row["point_id"])
            if body is None:
                continue
            if r5_id in body["aliases"]:
                out.append(Problem("r5_map.alias", "aliases", f"{r5_id} is on secondary (primary only)", row["point_id"]))
            if r5_id not in body["source_refs"].get("r5_split", []):
                out.append(Problem("r5_map.provenance", "source_refs.r5_split", f"does not record {r5_id}", row["point_id"]))
    return out


def validate_package(pkg: Package) -> Package:
    """Fill `pkg.problems` with every hard failure of section 5.3 that needs no database. Returns `pkg`."""
    pkg.problems = _manifest_problems(pkg)
    if pkg.problems:
        return pkg
    manifest = pkg.manifest
    listed = {entry["id"]: entry for entry in manifest["points"]}
    for missing in sorted(set(listed) - set(pkg.bodies)):
        pkg.problems.append(Problem("points.missing_file", f"points/{missing}.json", "listed, file missing", missing))
    for extra in sorted(set(pkg.bodies) - set(listed)):
        pkg.problems.append(Problem("points.unlisted_file", f"points/{extra}.json", "file present, not listed", extra))
    language = manifest["language"]
    for point_id in sorted(set(listed) & set(pkg.bodies)):
        pkg.problems += _point_problems(point_id, pkg.bodies[point_id], listed[point_id], language)
    if pkg.problems:
        return pkg
    bodies = {pid: pkg.bodies[pid] for pid in listed}
    external = {ref for ref in manifest["external_references"] if isinstance(ref, str)}
    pkg.problems += _structure_problems(bodies, external)
    pkg.problems += _function_problems(pkg.functions, bodies)
    pkg.problems += r5_map_problems(manifest["r5_map"], bodies)
    return pkg
