"""Published shared-library media in a content pack (D-234): export and import, one implementation.

The Admin route (`content_pack_api`) and the operator CLI (`scripts/media_content_pack.py`) both call this module.
It never calls a provider, never queues a processing job and never touches a database: it reads and writes the
media library store and its asset store, and nothing else.

Export takes shared-library entries with `status == "published"` and nothing else (personal, held, unpublished,
archived are never read into a pack). Per entry the pack carries every `MediaLibraryEntry` field except `status`
(that travels as the envelope's `exported_status`, advice only) and `processing` (reduced to the final state), plus
the binary assets that belong to it: its stored thumbnail and its prepared model clips, each with sha256 and size.

Translations: a cue's stored meaning lives in the learning cache (`media_translation_cache`, keyed by asset, segment, a
fingerprint of the cue text, language and the translating provider/model), not on the media record, and that cache is
what Listening reads (`listening_api.stored_media_payload` -> `media_meaning.resolve_segment_meanings`). Export reads the
meanings from that same cache for every support language present and carries them with their provenance; import writes
them into the target's cache under the model-independent identity `pack-import`, which its read path checks right after the current provider/model and before any provider
call. They are additive and idempotent: a meaning already held is kept, and replaced only with `overwrite`.

Import is idempotent by `media_id`: absent -> `new`, identical -> `unchanged`, different -> `conflict` and left
alone unless `overwrite`. An imported item arrives ready, with its stored transcript and translations, and is
published only when its rights are complete (cleared, with a permission note) and its transcript passes the
deterministic checks; otherwise it arrives `unpublished` and the report says why. A dry run decides every item
exactly as a real run would and writes nothing.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import fields, replace
from datetime import UTC, datetime
from typing import Any

from writing_coach.book_asset_store import AssetNotFound, InvalidAssetKey, _validate_key
from writing_coach.content_packs import Pack, PackItem, content_hash
from writing_coach.core.support_languages import all_support_languages
from writing_coach.media_meaning import IMPORTED_IDENTITY, cache_key
from writing_coach.media_library_store import MediaLibraryEntry, validate_entry
from writing_coach.thumbnails import has_media_thumbnail, media_cover_key, typographic_record

KIND = "media_item"
NEW, UNCHANGED, CONFLICT, REFUSED, OVERWRITTEN = "new", "unchanged", "conflict", "refused", "overwritten"
_ENTRY_FIELDS = tuple(f.name for f in fields(MediaLibraryEntry) if f.name not in {"status", "processing"})
# What an exported entry's `source.imported_by` says: an administrator's address never travels.
PACK_ACTOR = "content-pack"
_ALLOWED_PREFIXES = ("media/", "speaking/model-clip/")

# Keys that name a learner, an account or this environment's internal bookkeeping never travel: they are dropped from
# `source` and, found anywhere in the lesson, keep the entry out of the pack.
_PRIVATE_KEY = re.compile(r"owner|user|e-?mail|token|session|secret|password|quota|settle|spend|_by$|reviewer|^ip$|_ip$|^name$", re.IGNORECASE)

_LESSON_PRIVATE_KEYS = frozenset({"owner", "owner_token", "user", "user_id", "user_key", "email", "account", "account_id",
                                    "uploaded_by", "reviewed_by", "approved_by", "added_by", "reviewer", "ip"})
_EMAIL = re.compile(r"[^@\s/:]+@[^@\s/:]+\.[^@\s/:]+")  # an address, not a URL that carries an "@"

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


# What a pack without derived text keeps of a lesson's payload: the asset and playback descriptors. The transcript, its
# translations, word timing and every reading derived from the transcript stay behind.
_PAYLOAD_KEPT_WITHOUT_TEXT = ("asset", "playback")


def strip_derived_text(lesson: Any) -> Any:
    if not isinstance(lesson, Mapping):
        return lesson
    payload = lesson.get("payload")
    kept = {k: v for k, v in payload.items() if k in _PAYLOAD_KEPT_WITHOUT_TEXT} if isinstance(payload, Mapping) else payload
    return {**{k: v for k, v in lesson.items() if k != "payload"}, **({"payload": kept} if payload is not None else {})}


def _entry_data(entry: MediaLibraryEntry, assets: Any, clip_keys: ClipKeys, *, derived_text: bool = True,
                ) -> tuple[dict[str, Any], dict[str, bytes]]:
    """The comparable form of an entry (same function for export and for judging a local entry) and its asset bytes."""
    values = {name: _plain(getattr(entry, name)) for name in _ENTRY_FIELDS}
    if not derived_text:
        values["lesson"] = _plain(strip_derived_text(entry.lesson))
    values["source"] = {**_public_source(values["source"]), "imported_by": PACK_ACTOR}
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


def _public_source(source: Mapping[str, Any]) -> dict[str, Any]:
    """`source` without keys that name a person or internal bookkeeping, and without any value that is an address."""
    return {k: v for k, v in source.items()
            if not _PRIVATE_KEY.search(str(k)) and not (isinstance(v, str) and _EMAIL.fullmatch(v.strip()))}


def _private_key_in(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_EMAIL.fullmatch(value.strip()))
    if isinstance(value, Mapping):
        return any(str(k).casefold() in _LESSON_PRIVATE_KEYS or _private_key_in(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_private_key_in(v) for v in value)
    return False


def _local_playback(entry: MediaLibraryEntry) -> bool:
    playback = entry.playback or {}
    return str(playback.get("url") or "").startswith("/api/media/files/") or playback.get("provider") in {"upload", "orena"}


def export_refusal(entry: MediaLibraryEntry, assets: Any, clip_keys: ClipKeys) -> str:
    """Why a published shared entry cannot be packed ("" when it can)."""
    if _local_playback(entry):
        return "local_playback_not_packable"
    if _private_key_in(entry.lesson):
        return "learner_field_in_lesson"
    thumbnail = entry.thumbnail or {}
    if thumbnail.get("kind") == "asset" and _read_asset(assets, str(thumbnail.get("ref") or "")) is None:
        return "thumbnail_asset_missing"
    return ""


KNOWN_IDENTITY_CLASSES = ("GroqTranslationProvider", "PlatformMediaTranslator", "LocalHttpTranslationProvider")

# ---- stored translations ---------------------------------------------------------------------------------

MAX_TRANSLATION_CHARS = 4000


def _lesson_cues(lesson: Mapping[str, Any] | None, media_id: str) -> tuple[str, list[tuple[str, str]]]:
    """The asset id and the (segment_id, text) cues Listening resolves meanings for: the same fields, the same order."""
    payload = lesson.get("payload") if isinstance(lesson, Mapping) else None
    if not isinstance(payload, Mapping):
        return media_id, []
    asset_id = str((payload.get("asset") or {}).get("asset_id") or media_id)
    segments = (payload.get("transcript") or {}).get("segments") or []
    cues = [(str(seg["segment_id"]), str(seg["original_text"])) for seg in segments
            if isinstance(seg, Mapping) and "segment_id" in seg and "original_text" in seg]
    return asset_id, cues


def _support_codes() -> list[str]:
    return [definition.code for definition in all_support_languages()]


def _export_translations(entry: MediaLibraryEntry, cache: Any, provider_models: Sequence[str],
                         ) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    """Every stored meaning of this entry's cues, per target language, read where the learner UI reads it.

    A language appears only when at least one cue has a stored meaning; the summary says how many cues have one."""
    if cache is None:
        return [], {}
    # `<class>:default` is what Listening's identity really is today: the provider classes expose no `.model`
    # (`listening_api._translation_provider_model`), so whatever the model, the key says `default`. Probed always.
    models = list(dict.fromkeys([*provider_models, *(f"{cls}:default" for cls in KNOWN_IDENTITY_CLASSES), IMPORTED_IDENTITY]))
    asset_id, cues = _lesson_cues(entry.lesson, entry.media_id)
    rows: list[dict[str, str]] = []
    summary: dict[str, dict[str, int]] = {}
    for code in _support_codes():
        if code == str(entry.language or "").casefold():
            continue
        found = []
        for segment_id, text in cues:
            best: dict[str, str] | None = None
            for model in models:  # every model that may have translated this cue: the newest meaning wins
                hit = cache.get_media_translation(cache_key(asset_id, segment_id, text, code, model))
                if hit and str(hit.get("translated_text") or "").strip():
                    row = {"segment_id": segment_id, "target_language": code,
                           "translated_text": str(hit["translated_text"]),
                           "provenance": str(hit.get("provenance") or "generated"),
                           "created_at": str(hit.get("generated_at") or ""), "provider_model": model}
                    if best is None or row["created_at"] > best["created_at"]:
                        best = row
            if best is not None:
                found.append(best)
        if found:
            rows += found
            summary[code] = {"have": len(found), "of": len(cues)}
    return rows, summary


def translation_counts(item: PackItem) -> dict[str, int]:
    """Translations a pack item carries, per target language (an item from an older pack carries none)."""
    counts: dict[str, int] = {}
    for row in item.data.get("translations") or []:
        code = str(row.get("target_language") or "") if isinstance(row, Mapping) else ""
        counts[code] = counts.get(code, 0) + 1
    return counts


Put = tuple[str, str, str, str]  # cache key, text, provenance, generated_at


def _plan_translations(item: PackItem, candidate: MediaLibraryEntry, cache: Any, *,
                       overwrite: bool) -> tuple[dict[str, Any], list[Put]]:
    """What import does with an item's translations: the report block and the cache rows to put. Reads, never writes."""
    rows = item.data.get("translations") or []
    block: dict[str, Any] = {"in_pack": len(rows), "languages": translation_counts(item)}
    if not rows:
        return block, []
    if cache is None:
        return {**block, "skipped": "no_translation_store"}, []
    asset_id, cues = _lesson_cues(candidate.lesson, candidate.media_id)
    texts = dict(cues)
    new = same = differs = invalid = 0
    puts: list[Put] = []
    for row in rows:
        try:
            segment_id, code = str(row["segment_id"]), str(row["target_language"]).strip().casefold()
            text = str(row["translated_text"]).strip()
        except (KeyError, TypeError):
            invalid += 1
            continue
        if segment_id not in texts or not text or len(text) > MAX_TRANSLATION_CHARS or code not in _support_codes():
            invalid += 1
            continue
        key = cache_key(asset_id, segment_id, texts[segment_id], code, IMPORTED_IDENTITY)
        held_text = str((cache.get_media_translation(key) or {}).get("translated_text") or "").strip()
        if not held_text:
            new += 1
        elif held_text == text:
            same += 1
            continue
        else:
            differs += 1
            if not overwrite:
                continue
        puts.append((key, text, str(row.get("provenance") or "generated"), str(row.get("created_at") or "")))
    block.update({"new": new, "unchanged": same, "differs": differs, "invalid": invalid})
    if differs and not overwrite:
        block["kept_local"] = differs
    return block, puts


def build_media_items(
    store: Any, assets: Any, *, ids: Iterable[str] = (), languages: Iterable[str] = (),
    exclude_prefixes: Iterable[str] = (), clip_keys: ClipKeys | None = None,
    translations: Any = None, provider_models: Sequence[str] = (), include_derived_text: bool = False,
) -> tuple[list[PackItem], dict[str, bytes], list[dict[str, str]]]:
    """Published shared entries as pack items, their asset bytes by key, and the published entries left out (with why).

    `ids` and `languages` narrow what is exported; `exclude_prefixes` leaves out ids an operator knows are not for
    another environment (test or QA fixtures carry no tag in the store, so the id is the only handle). An entry
    whose rights are incomplete still travels: the importing environment holds it unpublished and says so.

    `translations` is the learning cache Listening reads and `provider_models` the identities its meanings may have
    been stored under (the cache key carries the translating provider/model); without both, none is exported.

    `include_derived_text` (default off) is the explicit switch for the transcript cues, their word timing and the
    translations: off, a pack carries the media metadata, rights, level, playback and assets only, and no cache is read.
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
        data, entry_blobs = _entry_data(entry, assets, clip_keys, derived_text=include_derived_text)
        blobs.update(entry_blobs)
        data["derived_text"] = include_derived_text
        data["translations"], data["translation_summary"] = (
            _export_translations(entry, translations, tuple(provider_models)) if include_derived_text else ([], {}))
        items.append(PackItem(kind=KIND, natural_key=entry.media_id, data=data, exported_status="published"))
    return items, blobs, excluded


# ---- import ----------------------------------------------------------------------------------------------


def _entry_from(item: PackItem, *, status: str, processing: Mapping[str, Any], actor: str) -> MediaLibraryEntry:
    raw = dict(item.data["entry"])
    unknown = set(raw) - set(_ENTRY_FIELDS)
    missing = set(_ENTRY_FIELDS) - set(raw)
    if unknown or missing:
        raise ValueError("entry fields do not match")
    raw["source"] = {**_public_source(raw["source"]), "imported_by": actor}
    entry = MediaLibraryEntry(**raw, status=status, processing=dict(processing))
    if entry.library != "shared":
        raise ValueError("library must be shared")
    return validate_entry(entry)


def _own_key(key: str, entry: MediaLibraryEntry, clip_keys: ClipKeys) -> bool:
    """A key is the item's own when it is its thumbnail, one of its computed model clips, or under its own directory."""
    thumbnail = entry.thumbnail or {}
    if thumbnail.get("kind") == "asset" and key == thumbnail.get("ref"):
        return True
    if key in set(clip_keys(entry)):
        return True
    return any(key.startswith(f"media/{name}/") for name in {entry.media_id, entry.provider_media_id})


def _owned_by_another(key: str, media_id: str, store: Any) -> bool:
    for library in ("shared", "personal"):
        for other in store.list(library=library, status=None):
            if other.media_id != media_id and _own_key(key, other, lambda _e: []):
                return True
    return False


def _asset_problem(item: PackItem, pack_assets: Mapping[str, bytes], entry: MediaLibraryEntry, assets: Any,
                   store: Any, clip_keys: ClipKeys) -> str:
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
        if not _own_key(key, entry, clip_keys):
            return "asset_key_not_this_items"
        blob = pack_assets.get(f"assets/{key}")
        if blob is None:
            return "asset_missing_from_pack"
        if hashlib.sha256(blob).hexdigest() != asset.get("sha256") or len(blob) != asset.get("bytes"):
            return "asset_checksum_mismatch"
        held = _read_asset(assets, key)
        if held is not None and held != blob and _owned_by_another(key, entry.media_id, store):
            return "asset_belongs_to_another_entry"
    thumbnail = item.data["entry"].get("thumbnail") or {}
    if thumbnail.get("kind") == "asset" and wanted_thumb not in {a["key"] for a in described}:
        return "thumbnail_asset_missing"
    return ""


def _decide(item: PackItem, pack: Pack, store: Any, assets: Any, clip_keys: ClipKeys, *, overwrite: bool,
            actor: str, pack_id: str) -> tuple[dict[str, Any], MediaLibraryEntry | None]:
    """One item's report row and, when it is to be written, the entry to write. Writes nothing."""
    row: dict[str, Any] = {"kind": KIND, "natural_key": item.natural_key}
    ready = {"state": "ready", "stage": "ready", "reason": "", "origin": "content-pack", "pack_id": pack_id}
    try:
        candidate = _entry_from(item, status="unpublished", processing=ready, actor=actor)
    except (ValueError, TypeError, KeyError) as exc:
        return {**row, "outcome": REFUSED, "reason": "entry_invalid", "detail": str(exc)[:160]}, None
    if _local_playback(candidate):
        return {**row, "outcome": REFUSED, "reason": "local_playback_not_packable"}, None
    if _private_key_in(candidate.lesson):
        return {**row, "outcome": REFUSED, "reason": "learner_field_in_lesson"}, None
    problem = _asset_problem(item, pack.assets, candidate, assets, store, clip_keys)
    if problem:
        return {**row, "outcome": REFUSED, "reason": problem}, None
    # D-240: an item arrives with a thumbnail. One that carries none (a pack from before the rule) gets the deterministic
    # typographic cover, whose bytes `apply_media_items` writes with the entry; a provider-hosted one stays provider-served.
    if not has_media_thumbnail(candidate.thumbnail):
        record = typographic_record(candidate.title, language=candidate.language, topic=_lesson_topic(candidate), kind="media")
        candidate = replace(
            candidate, thumbnail={"kind": "asset", "ref": media_cover_key(candidate.media_id, record)},
            source={**dict(candidate.source), "thumbnail_kind": "typographic", "thumbnail_source_url": "",
                    "thumbnail_author": "", "thumbnail_licence": "", "thumbnail_licence_url": ""})
        row["thumbnail"] = "typographic"
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
    derived = bool(item.data.get("derived_text", True))
    local, _ = _entry_data(existing, assets, clip_keys, derived_text=derived)
    if content_hash(_local_comparable(local)) == content_hash(_local_comparable(item.data)):
        return {**row, "outcome": UNCHANGED}, None
    differs = "assets_differ" if local["entry"] == item.data["entry"] else "fields_differ"
    if not overwrite:
        return {**row, "outcome": CONFLICT, "reason": differs}, None
    if not derived:
        final = replace(final, lesson=existing.lesson)  # a pack without text never takes a local transcript away
        row["kept_local_text"] = True
    if existing.status != "published" and final.status != existing.status:
        # An overwrite replaces content, never a local decision to take an item off the shelf.
        final = replace(final, status=existing.status)
        row["kept_status"] = existing.status
    return {**row, "outcome": OVERWRITTEN, "reason": differs, "status": final.status}, final


def _lesson_topic(entry: Any) -> str:
    return str(entry.lesson.get("topic") or "") if isinstance(entry.lesson, Mapping) else ""


def apply_media_items(pack: Pack, store: Any, assets: Any, *, overwrite: bool = False, dry_run: bool = True,
                      actor: str = PACK_ACTOR, clip_keys: ClipKeys | None = None,
                      translations: Any = None) -> list[dict[str, Any]]:
    """Judge every `media_item` of a pack, and when `dry_run` is false write what the judgement allows.

    The asset bytes are put first and the entry last, so an entry never points at a file that was not written.
    A failure of one item is that item's `refused` row; it never stops the others.

    `translations` is the learning cache this environment's Listening reads. The pack's meanings are put under the
    model-independent identity `media_meaning.IMPORTED_IDENTITY`, which the read path checks after the current
    provider/model and before any provider call, so a later change of translating model re-translates nothing. A held
    meaning is kept unless `overwrite`. Every row reports its counts, so a dry run says what a real run would write.
    """
    clip_keys = clip_keys or default_clip_keys
    pack_id = str(pack.manifest.get("pack_id") or "")
    rows = []
    for item in pack.items:
        if item.kind != KIND:
            continue
        row, final = _decide(item, pack, store, assets, clip_keys, overwrite=overwrite, actor=actor, pack_id=pack_id)
        puts: list[Put] = []
        if row["outcome"] != REFUSED:
            try:
                candidate = _entry_from(item, status="unpublished", processing={}, actor=actor)
                row["translations"], puts = _plan_translations(item, candidate, translations, overwrite=overwrite)
            except (ValueError, TypeError, KeyError):
                row["translations"], puts = {"in_pack": 0}, []
            if row["outcome"] == CONFLICT:
                puts = []  # a conflicting item is left alone, translations included
        if not dry_run and (final is not None or puts):
            try:
                if final is not None:
                    for asset in item.data["assets"]:
                        assets.put(asset["key"], pack.assets[f"assets/{asset['key']}"])
                    if row.get("thumbnail") == "typographic":
                        cover = typographic_record(final.title, language=final.language, topic=_lesson_topic(final), kind="media")
                        assets.put(final.thumbnail["ref"], cover["data"])
                    store.upsert(final)
                    row["written"] = True
                stamp = datetime.now(UTC).isoformat()
                for key, text, provenance, created_at in puts:
                    translations.put_media_translation(key, text, provenance, created_at or stamp)
                if puts:
                    row["translations"]["written"] = len(puts)
            except Exception as exc:  # noqa: BLE001 - one item never fails the pack; its failure is reported
                row = {**row, "outcome": REFUSED, "reason": "write_failed", "detail": type(exc).__name__}
        rows.append(row)
    return rows


def translation_totals(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Pack-wide translation counts of an import report (what a dry run would write, or did)."""
    totals = {"in_pack": 0, "new": 0, "unchanged": 0, "differs": 0, "invalid": 0, "written": 0}
    for row in rows:
        for name, value in (row.get("translations") or {}).items():
            if name in totals and isinstance(value, int):
                totals[name] += value
    return totals


# The translating identities a cache key may carry, read from the AI ledger (`audit_logs` `ai.operation`, capability
# `media_translation`, distinct provider/model). The ledger is the one place that records every model that ever
# translated, whatever the current configuration says; the cache itself holds only hashed keys and cannot be listed.
_IDENTITY_CLASS = {"groq": "GroqTranslationProvider", "local_marian": "LocalHttpTranslationProvider"}


def models_from_ledger_rows(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Cache identities (`<Provider class>:<model>`) of the distinct media_translation provider/model pairs in ledger rows."""
    found: list[str] = []
    for row in rows:
        if str(row.get("capability") or "") != "media_translation":
            continue
        cls, model = _IDENTITY_CLASS.get(str(row.get("provider") or "")), str(row.get("model") or "").strip()
        if cls and model:
            found.append(f"{cls}:{model}")
    return sorted(dict.fromkeys(found))


def discover_provider_models(platform_repository: Any, extra: Iterable[str] = ()) -> list[str]:
    """Every identity worth probing: the ledger's (when it can be read) and the ones given; `extra` first."""
    models = [m for m in extra if m]
    loader = getattr(platform_repository, "ai_cost_rows", None)
    if loader is not None:
        try:
            models += models_from_ledger_rows(loader(datetime(2020, 1, 1, tzinfo=UTC)))
        except Exception:  # noqa: BLE001 - an unreadable ledger leaves the given identities; coverage then says what is missing
            pass
    return list(dict.fromkeys(models))


def translation_coverage(items: Iterable[PackItem]) -> dict[str, Any]:
    """Cue translations present against expected, per item and in total.

    Expected for an item is every cue in every target language any exported item carries (the item's own source language
    excepted): an item with none is 0%, and an item missing a language the others have is partial."""
    items = [item for item in items if item.data.get("derived_text", True)]  # a pack without text has none to cover
    langs = {code for item in items for code in (item.data.get("translation_summary") or {})}
    per_item: dict[str, dict[str, Any]] = {}
    have_total = expected_total = 0
    for item in items:
        _asset, cues = _lesson_cues(item.data["entry"].get("lesson"), item.natural_key)
        own = str(item.data["entry"].get("language") or "").casefold()
        # An item with a transcript is expected to carry at least one language: nothing stored is a failure, not "0/0".
        expected = len(cues) * max(1, len([c for c in langs if c != own]))
        have = sum(v.get("have", 0) for v in (item.data.get("translation_summary") or {}).values())
        per_item[item.natural_key] = {"have": have, "expected": expected,
                                      "percent": round(100.0 * have / expected, 1) if expected else 0.0}
        have_total += have
        expected_total += expected
    complete = all(row["expected"] > 0 and row["have"] >= row["expected"] for row in per_item.values())
    return {"items": per_item, "total": {"have": have_total, "expected": expected_total,
                                         "percent": round(100.0 * have_total / expected_total, 1) if expected_total else 0.0},
            "languages": sorted(langs), "complete": complete,
            "incomplete": [key for key, row in per_item.items() if row["expected"] == 0 or row["have"] < row["expected"]]}


def export_preview(items: Iterable[PackItem], blobs: Mapping[str, bytes], excluded: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """A read-only summary of what an export would pack, per item and in total. Writes nothing."""
    rows = []
    items_list = list(items)
    for item in items_list:
        counts = translation_counts(item)
        rows.append({"media_id": item.natural_key, "assets": len(item.data.get("assets") or []),
                     "translations": counts, "translation_total": sum(counts.values()),
                     "translation_coverage": item.data.get("translation_summary") or {}})
    return {"dry_run": True, "include_derived_text": all(i.data.get("derived_text", True) for i in items_list) and bool(items_list),
            "items": len(rows), "assets": len(blobs), "asset_bytes": sum(len(b) for b in blobs.values()),
            "translations": sum(row["translation_total"] for row in rows),
            "coverage": translation_coverage(items_list),
            "without_translations": [row["media_id"] for row in rows if not row["translation_total"]],
            "excluded": list(excluded), "per_item": rows}


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["outcome"]] = summary.get(row["outcome"], 0) + 1
    return summary


__all__ = ["KIND", "apply_media_items", "build_media_items", "export_preview", "rights_complete", "summarize",
           "translation_counts", "translation_totals", "translation_coverage", "discover_provider_models",
           "models_from_ledger_rows"]
