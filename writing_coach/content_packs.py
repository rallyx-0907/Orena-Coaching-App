"""Content packs: approved content moved between environments (docs/project/proposals/CONTENT_PACKS.md, v1).

A pack is a zip (`.orenapack`): `manifest.json` plus one JSON file per item, every file listed in the manifest
with its sha256 and size. v1 carries Reading (sources, published articles, approved comprehension sets) and
vocabulary collections; media and books follow once their stores allow it (UI_BACKEND_GAPS, CP-1/CP-2).

What never travels: learner data of any kind, secrets, local paths, telemetry, review history, database ids
(an item's id rides along only as `origin_id`, for tracing).

Import never bypasses an engine. This module reads and verifies a pack and plans it; the API layer commits each
item through the same engines and rules a fresh Admin import uses (D-111): a Reading text is a Reading job the
worker admits or holds; a vocabulary collection goes through the same normaliser and publication rule as a CSV.
A pack's `exported_status` is advice only - status is always decided here, by this environment's rules.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PACK_FORMAT = "orena-content-pack"
PACK_VERSION = 1
KINDS = ("reading_source", "reading_article", "vocabulary_collection")

MAX_PACK_BYTES = 50 * 1024 * 1024
MAX_FILES = 5001
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_RATIO = 100
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}")
_SAFE_PATH = re.compile(r"(?:manifest\.json|items/(?:reading_source|reading_article|vocabulary_collection)/[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.json)")
# A pack must never carry these: a builder that finds one refuses to build (no learner data, no secrets).
_FORBIDDEN_KEYS = re.compile(r'"(?:user_id|user_key|owner_token|email|password|api_key|secret|token|session)"\s*:')


class PackError(ValueError):
    """A pack that cannot be read or trusted. `code` is stable for the Admin copy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(data: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(data)).hexdigest()


def _file_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")[:150] or "item"
    return cleaned if _SAFE_NAME.fullmatch(cleaned) else hashlib.sha256(value.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class PackItem:
    kind: str
    natural_key: str
    data: Mapping[str, Any]
    exported_status: str = "published"

    @property
    def content_hash(self) -> str:
        return content_hash(self.data)

    def envelope(self) -> dict[str, Any]:
        return {"kind": self.kind, "schema_version": 1, "natural_key": self.natural_key,
                "content_hash": self.content_hash, "exported_status": self.exported_status, "data": dict(self.data)}


@dataclass
class Pack:
    manifest: dict[str, Any]
    items: list[PackItem] = field(default_factory=list)


def build_pack(items: Iterable[PackItem], *, created_by: str, environment: str, app_version: str,
               filters: Mapping[str, Any]) -> bytes:
    """The zip for these items. Refuses to build when any item carries a learner or secret field."""

    files: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    for item in items:
        if item.kind not in KINDS:
            raise PackError("pack_kind_unknown", f"unknown kind {item.kind!r}")
        body = _canonical(item.envelope())
        if _FORBIDDEN_KEYS.search(body.decode("utf-8")):
            raise PackError("pack_forbidden_field", f"{item.kind} {item.natural_key} carries a learner or secret field")
        path = f"items/{item.kind}/{_file_name(item.natural_key)}.json"
        if path in files:
            path = f"items/{item.kind}/{_file_name(item.natural_key)}-{hashlib.sha256(body).hexdigest()[:8]}.json"
        files[path] = body
        counts[item.kind] = counts.get(item.kind, 0) + 1
    listed = [{"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for path, data in sorted(files.items())]
    manifest = {
        "format": PACK_FORMAT, "version": PACK_VERSION, "pack_id": str(uuid.uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "source_environment": {"label": environment[:80], "app_version": app_version[:80]},
        "created_by": created_by[:160], "filters": dict(filters), "kinds": sorted(counts), "counts": counts,
        "files": listed,
        "pack_sha256": hashlib.sha256("\n".join(f"{f['path']}:{f['sha256']}" for f in listed).encode()).hexdigest(),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _canonical(manifest))
        for path, data in sorted(files.items()):
            archive.writestr(path, data)
    return buffer.getvalue()


def read_pack(raw: bytes) -> Pack:
    """Open a pack safely and verify every byte of it before anything is planned.

    Refused: an oversize upload, a name that is not one of the pack's own paths (absolute, `..`, backslash,
    drive, link or anything unexpected), duplicate names, a compression ratio of a zip bomb, an unlisted or
    missing file, a hash or size that does not match, a newer format version, or an item that is not shaped
    like its kind. Nothing is extracted to disk.
    """

    if len(raw) > MAX_PACK_BYTES:
        raise PackError("pack_too_large", "the pack is larger than an import accepts")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise PackError("pack_not_zip", "this file is not a content pack") from exc
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        raise PackError("pack_too_many_files", "the pack has more files than an import accepts")
    names = [info.filename for info in infos]
    if len(set(names)) != len(names) or len({name.casefold() for name in names}) != len(names):
        raise PackError("pack_duplicate_name", "the pack lists a file twice")
    total = 0
    contents: dict[str, bytes] = {}
    for info in infos:
        if info.is_dir() or not _SAFE_PATH.fullmatch(info.filename) or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise PackError("pack_unsafe_path", f"unexpected entry {info.filename[:80]!r}")
        if info.file_size > MAX_FILE_BYTES or (info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_RATIO):
            raise PackError("pack_entry_too_large", f"{info.filename} is too large")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise PackError("pack_too_large", "the pack unpacks to more than an import accepts")
        data = archive.read(info.filename)
        if len(data) != info.file_size:
            raise PackError("pack_corrupt", f"{info.filename} is damaged")
        contents[info.filename] = data
    try:
        manifest = json.loads(contents.pop("manifest.json"))
    except (KeyError, ValueError) as exc:
        raise PackError("pack_manifest_missing", "the pack has no readable manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != PACK_FORMAT:
        raise PackError("pack_not_orena", "this file is not an Orena content pack")
    if not isinstance(manifest.get("version"), int) or manifest["version"] > PACK_VERSION:
        raise PackError("pack_version_newer", "this pack was made by a newer Orena; update before importing it")
    listed = {entry.get("path"): entry for entry in manifest.get("files") or [] if isinstance(entry, dict)}
    if set(listed) != set(contents):
        raise PackError("pack_files_mismatch", "the pack's files do not match its manifest")
    for path, data in contents.items():
        entry = listed[path]
        if entry.get("bytes") != len(data) or entry.get("sha256") != hashlib.sha256(data).hexdigest():
            raise PackError("pack_hash_mismatch", f"{path} does not match its manifest")
    items = []
    for path in sorted(contents):
        try:
            envelope = json.loads(contents[path])
        except ValueError as exc:
            raise PackError("pack_item_unreadable", f"{path} is not JSON") from exc
        items.append(_item_from(path, envelope))
    return Pack(manifest=manifest, items=items)


def _item_from(path: str, envelope: Any) -> PackItem:
    if not isinstance(envelope, dict) or envelope.get("kind") not in KINDS or not path.startswith(f"items/{envelope.get('kind')}/"):
        raise PackError("pack_item_shape", f"{path} is not a pack item")
    data = envelope.get("data")
    key = envelope.get("natural_key")
    if not isinstance(data, dict) or not isinstance(key, str) or not key:
        raise PackError("pack_item_shape", f"{path} has no data or key")
    item = PackItem(kind=envelope["kind"], natural_key=key, data=data,
                    exported_status=str(envelope.get("exported_status") or ""))  # fmt: skip
    if envelope.get("content_hash") != item.content_hash:
        raise PackError("pack_item_hash", f"{path} was changed after it was packed")
    _validate(item, path)
    return item


def _text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def _validate(item: PackItem, path: str) -> None:
    data = item.data
    if item.kind == "reading_source":
        ok = _text(data.get("slug"), 120) and _text(data.get("name"), 240) and isinstance(data.get("rights"), dict)
    elif item.kind == "reading_article":
        ok = (_text(data.get("source_slug"), 120) and _text(data.get("body"), 400_000)
              and data.get("language") in {"en", "zh"} and _text(data.get("title"), 500))  # fmt: skip
        sets = data.get("comprehension_sets", [])
        ok = ok and isinstance(sets, list) and all(isinstance(s, dict) and isinstance(s.get("questions"), list) for s in sets)
    else:
        ok = (_text(data.get("id"), 160) and data.get("language_code") in {"en", "zh"}
              and isinstance(data.get("entries"), list) and len(data["entries"]) <= 20_000)  # fmt: skip
    if not ok:
        raise PackError("pack_item_invalid", f"{path} is not a valid {item.kind}")


# ---- planning --------------------------------------------------------------------------------------------


NEW, IDENTICAL, CHANGED, SOURCE_NEEDED = "new", "identical", "changed", "source_needs_approval"


def plan_item(item: PackItem, *, existing_hash: str | None, source_state: str | None = None) -> dict[str, Any]:
    """One item's outcome. `existing_hash` is this environment's hash for the same natural key, if any."""

    if existing_hash is None:
        outcome = NEW
    elif existing_hash == item.content_hash:
        outcome = IDENTICAL
    else:
        outcome = CHANGED
    plan = {"kind": item.kind, "natural_key": item.natural_key, "outcome": outcome}
    if item.kind == "reading_article" and source_state not in (None, "active"):
        plan["note"] = SOURCE_NEEDED  # it will be admitted only once its source is approved here
    return plan
