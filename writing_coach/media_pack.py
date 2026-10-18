"""Published shared-library media in a content pack (D-234): export and import, one implementation.

The Admin route (`content_pack_api`) and the operator CLI (`scripts/media_content_pack.py`) both call this module.
It never calls a provider, never queues a processing job and never touches a database: it reads and writes the
media library store and its asset store, and nothing else.

Export takes shared-library entries with `status == "published"` and nothing else (personal, held, unpublished,
archived are never read into a pack). Per entry the pack carries every `MediaLibraryEntry` field except `status`
(that travels as the envelope's `exported_status`, advice only) and `processing` (reduced to the final state), plus
the binary assets that belong to it: its stored thumbnail and its prepared model clips, each with sha256 and size.

Import is idempotent by `media_id`: absent -> `new`, identical -> `unchanged`, different -> `conflict` and left
alone unless `overwrite`. An imported item arrives ready, with its stored transcript and translations, and is
published only when its rights are complete (cleared, with a permission note) and its transcript passes the
deterministic checks; otherwise it arrives `unpublished` and the report says why. A dry run decides every item
exactly as a real run would and writes nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import fields, replace
from typing import Any

from writing_coach.book_asset_store import AssetNotFound, InvalidAssetKey, _validate_key
from writing_coach.content_packs import Pack, PackItem, content_hash
from writing_coach.media_library_store import MediaLibraryEntry, validate_entry

KIND = "media_item"
NEW, UNCHANGED, CONFLICT, REFUSED, OVERWRITTEN = "new", "unchanged", "conflict", "refused", "overwritten"
_ENTRY_FIELDS = tuple(f.name for f in fields(MediaLibraryEntry) if f.name not in {"status", "processing"})
# What an exported entry's `source.imported_by` says: an administrator's address never travels.
PACK_ACTOR = "content-pack"
_ALLOWED_PREFIXES = ("media/", "speaking/model-clip/")

ClipKeys = Callable[[MediaLibraryEntry], Sequence[str]]


def rights_complete(source: Mapping[str, Any]) -> bool:
    """Cleared rights with a permission note: the same two facts the Admin rights act requires before it publishes."""
    return source.get("rights") == "cleared" and bool(str(source.get("license") or "").strip())


def default_clip_keys(entry: MediaLibraryEntry) -> list[str]:
    """The asset keys of this entry's speakable lines' model clips (D-140). Computed, never prepared."""
    from writing_coach.speaking_library import entry_clip_lines

    return [line.key for line in entry_clip_lines(entry)]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _asset_keys(entry: MediaLibraryEntry, clip_keys: ClipKeys) -> list[str]:
    keys: list[str] = []
    thumbnail = entry.thumbnail or {}
    if thumbnail.get("kind") == "asset" and thumbnail.get("ref"):
        keys.append(str(thumbnail["ref"]))
    keys.extend(clip_keys(entry))
    return sorted(dict.fromkeys(keys))


def _read_asset(assets: Any, key: str) -> bytes | None:
    try:
        data = assets.get(key)
    except (AssetNotFound, InvalidAssetKey, FileNotFoundError):
        return None
    return data if isinstance(data, bytes) else None


def _entry_data(entry: MediaLibraryEntry, assets: Any, clip_keys: ClipKeys) -> tuple[dict[str, Any], dict[str, bytes]]:
    """The comparable form of an entry (same function for export and for judging a local entry) and its asset bytes."""
    values = {name: _plain(getattr(entry, name)) for name in _ENTRY_FIELDS}
    values["source"] = {**values["source"], "imported_by": PACK_ACTOR}
    described, blobs = [], {}
    for key in _asset_keys(entry, clip_keys):
        blob = _read_asset(assets, key)
        if blob is None:
            continue  # a clip not prepared is simply absent; a thumbnail that is missing is caught by the caller
        described.append({"key": key, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
        blobs[key] = blob
    source = values["source"]
    data = {
        "entry": values,
        "assets": described,
        "rights": {"rights": source.get("rights", ""), "license": source.get("license", ""),
                   "review_status": source.get("review_status", ""), "complete": rights_complete(source)},
        "final_processing": {"state": str((entry.processing or {}).get("state") or "ready"),
                             "origin": str((entry.processing or {}).get("origin") or "")},
    }
    return data, blobs


def _local_comparable(data: Mapping[str, Any]) -> dict[str, Any]:
    """What identity is judged on: the entry and its assets. The rights summary is derived and the processing is
    this environment's own, so neither decides `unchanged`."""
    return {"entry": data["entry"], "assets": data["assets"]}


def export_refusal(entry: MediaLibraryEntry, assets: Any, clip_keys: ClipKeys) -> str:
    """Why a published shared entry cannot be packed ("" when it can)."""
    playback = entry.playback or {}
    if str(playback.get("url") or "").startswith("/api/media/files/") or playback.get("provider") == "upload":
        return "local_playback_not_packable"
    thumbnail = entry.thumbnail or {}
    if thumbnail.get("kind") == "asset" and _read_asset(assets, str(thumbnail.get("ref") or "")) is None:
        return "thumbnail_asset_missing"
    return ""


def build_media_items(
    store: Any, assets: Any, *, ids: Iterable[str] = (), languages: Iterable[str] = (),
    exclude_prefixes: Iterable[str] = (), clip_keys: ClipKeys | None = None,
) -> tuple[list[PackItem], dict[str, bytes], list[dict[str, str]]]:
    """Published shared entries as pack items, their asset bytes by key, and the published entries left out (with why).

    `ids` and `languages` narrow what is exported; `exclude_prefixes` leaves out ids an operator knows are not for
    another environment (test or QA fixtures carry no tag in the store, so the id is the only handle). An entry
    whose rights are incomplete still travels: the importing environment holds it unpublished and says so.
    """
    clip_keys = clip_keys or default_clip_keys
    wanted, langs, skip = set(ids), set(languages), tuple(p for p in exclude_prefixes if p)
    items: list[PackItem] = []
    blobs: dict[str, bytes] = {}
    excluded: list[dict[str, str]] = []
    for entry in sorted(store.list(library="shared", status="published"), key=lambda e: e.media_id):
        if (wanted and entry.media_id not in wanted) or (langs and entry.language not in langs):
            continue
        if skip and entry.media_id.startswith(skip):
            excluded.append({"media_id": entry.media_id, "reason": "excluded_by_prefix"})
            continue
        reason = export_refusal(entry, assets, clip_keys)
        if reason:
            excluded.append({"media_id": entry.media_id, "reason": reason})
            continue
        data, entry_blobs = _entry_data(entry, assets, clip_keys)
        blobs.update(entry_blobs)
        items.append(PackItem(kind=KIND, natural_key=entry.media_id, data=data, exported_status="published"))
    return items, blobs, excluded


# ---- import ----------------------------------------------------------------------------------------------


def _entry_from(item: PackItem, *, status: str, processing: Mapping[str, Any], actor: str) -> MediaLibraryEntry:
    raw = dict(item.data["entry"])
    unknown = set(raw) - set(_ENTRY_FIELDS)
    missing = set(_ENTRY_FIELDS) - set(raw)
    if unknown or missing:
        raise ValueError("entry fields do not match")
    raw["source"] = {**raw["source"], "imported_by": actor}
    entry = MediaLibraryEntry(**raw, status=status, processing=dict(processing))
    if entry.library != "shared":
        raise ValueError("library must be shared")
    return validate_entry(entry)


def _asset_problem(item: PackItem, pack_assets: Mapping[str, bytes]) -> str:
    described = item.data["assets"]
    wanted_thumb = ((item.data["entry"].get("thumbnail") or {}).get("ref") or "")
    for asset in described:
        key = asset.get("key") if isinstance(asset, Mapping) else None
        if not isinstance(key, str) or not key.startswith(_ALLOWED_PREFIXES):
            return "asset_key_not_allowed"
        try:
            _validate_key(key)
        except InvalidAssetKey:
            return "asset_key_unsafe"
        blob = pack_assets.get(f"assets/{key}")
        if blob is None:
            return "asset_missing_from_pack"
        if hashlib.sha256(blob).hexdigest() != asset.get("sha256") or len(blob) != asset.get("bytes"):
            return "asset_checksum_mismatch"
    thumbnail = item.data["entry"].get("thumbnail") or {}
    if thumbnail.get("kind") == "asset" and wanted_thumb not in {a["key"] for a in described}:
        return "thumbnail_asset_missing"
    return ""


def _decide(item: PackItem, pack: Pack, store: Any, assets: Any, clip_keys: ClipKeys, *, overwrite: bool,
            actor: str, pack_id: str) -> tuple[dict[str, Any], MediaLibraryEntry | None]:
    """One item's report row and, when it is to be written, the entry to write. Writes nothing."""
    row: dict[str, Any] = {"kind": KIND, "natural_key": item.natural_key}
    if _asset_problem(item, pack.assets):
        return {**row, "outcome": REFUSED, "reason": _asset_problem(item, pack.assets)}, None
    ready = {"state": "ready", "stage": "ready", "reason": "", "origin": "content-pack", "pack_id": pack_id}
    try:
        candidate = _entry_from(item, status="unpublished", processing=ready, actor=actor)
    except (ValueError, TypeError, KeyError) as exc:
        return {**row, "outcome": REFUSED, "reason": "entry_invalid", "detail": str(exc)[:160]}, None
    # Published only if the rights are complete and the stored transcript passes the same checks Publish uses.
    hold = ""
    if not rights_complete(candidate.source):
        hold = "rights_incomplete"
    else:
        from writing_coach.media_transcript_pipeline import usable_transcript

        usable, why = usable_transcript(candidate)
        if not usable:
            hold = f"transcript_{why or 'unusable'}"
    final = replace(candidate, status="unpublished" if hold else "published")
    if hold:
        row["held"] = hold
    existing = store.get(item.natural_key)
    if existing is None:
        return {**row, "outcome": NEW, "status": final.status}, final
    if existing.library != "shared":
        return {**row, "outcome": REFUSED, "reason": "id_in_use_by_personal_entry"}, None
    local, _ = _entry_data(existing, assets, clip_keys)
    if content_hash(_local_comparable(local)) == content_hash(_local_comparable(item.data)):
        return {**row, "outcome": UNCHANGED}, None
    differs = "assets_differ" if local["entry"] == item.data["entry"] else "fields_differ"
    if not overwrite:
        return {**row, "outcome": CONFLICT, "reason": differs}, None
    return {**row, "outcome": OVERWRITTEN, "reason": differs, "status": final.status}, final


def apply_media_items(pack: Pack, store: Any, assets: Any, *, overwrite: bool = False, dry_run: bool = True,
                      actor: str = PACK_ACTOR, clip_keys: ClipKeys | None = None) -> list[dict[str, Any]]:
    """Judge every `media_item` of a pack, and when `dry_run` is false write what the judgement allows.

    The asset bytes are put first and the entry last, so an entry never points at a file that was not written.
    A failure of one item is that item's `refused` row; it never stops the others.
    """
    clip_keys = clip_keys or default_clip_keys
    pack_id = str(pack.manifest.get("pack_id") or "")
    rows = []
    for item in pack.items:
        if item.kind != KIND:
            continue
        row, final = _decide(item, pack, store, assets, clip_keys, overwrite=overwrite, actor=actor, pack_id=pack_id)
        if final is not None and not dry_run:
            try:
                for asset in item.data["assets"]:
                    assets.put(asset["key"], pack.assets[f"assets/{asset['key']}"])
                store.upsert(final)
                row["written"] = True
            except Exception as exc:  # noqa: BLE001 - one item never fails the pack; its failure is reported
                row = {**row, "outcome": REFUSED, "reason": "write_failed", "detail": type(exc).__name__}
        rows.append(row)
    return rows


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["outcome"]] = summary.get(row["outcome"], 0) + 1
    return summary


__all__ = ["KIND", "apply_media_items", "build_media_items", "rights_complete", "summarize"]
