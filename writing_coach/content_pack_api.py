"""Admin content packs: export, plan, import (docs/project/proposals/CONTENT_PACKS.md, v1).

`POST /api/admin/content-packs/export`  filters in, an `.orenapack` out (synchronous; v1 packs are small).
`POST /api/admin/content-packs/plan`    a pack in, the per-item plan out - read-only, nothing is written.
`POST /api/admin/content-packs/import`  a pack in, each item committed through its engine, results out.

Plan and import each read and verify the whole pack again (v1 keeps no uploaded pack on the server). An item
already here is kept (`skip`, the default and only v1 policy): a pack never overwrites local content. Every
route is admin-only, same-origin and audited, like the rest of the console.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, File, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from writing_coach import reading_admin_api as reading
from writing_coach.content_packs import (
    IDENTICAL,
    MAX_PACK_BYTES,
    PackError,
    PackItem,
    build_pack,
    plan_item,
    read_pack,
)
from writing_coach.core.errors import orena_http_error

router = APIRouter(prefix="/api/admin/content-packs", tags=["admin-content-packs"])


@dataclass
class _Packs:
    vocabulary_ids: Callable[[tuple[str, ...], str], list[str]] | None = None
    vocabulary_export: Callable[[str], dict[str, Any] | None] | None = None
    vocabulary_import: Callable[..., dict[str, Any]] | None = None
    environment: str = "local"
    app_version: str = ""


_state = _Packs()


def configure_content_packs(**kwargs: Any) -> None:
    global _state
    _state = _Packs(**kwargs)


class ExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kinds: list[str] = Field(default_factory=lambda: ["reading", "vocabulary"], max_length=4)
    languages: list[str] = Field(default_factory=list, max_length=4)
    source_slug_prefix: str = Field(default="", max_length=120)
    collection_prefix: str = Field(default="", max_length=160)


def _items_for(body: ExportBody) -> list[PackItem]:
    items: list[PackItem] = []
    languages = tuple(code for code in body.languages if code in {"en", "zh"})
    if "reading" in body.kinds:
        items += reading.pack_reading_items(source_slug_prefix=body.source_slug_prefix.strip(), languages=languages)
    if "vocabulary" in body.kinds and _state.vocabulary_ids and _state.vocabulary_export:
        for collection_id in _state.vocabulary_ids(languages, body.collection_prefix.strip()):
            data = _state.vocabulary_export(collection_id)
            if data is not None:
                items.append(PackItem(kind="vocabulary_collection", natural_key=collection_id, data=data))
    return items


@router.post("/export")
def export_pack(request: Request, body: ExportBody) -> Response:
    admin = reading._admin(request)
    reading._same_origin(request)
    items = reading._guarded(lambda: _items_for(body))
    if not items:
        raise orena_http_error(404, "pack_nothing_to_export", "Nothing published matches these filters.")
    try:
        raw = build_pack(items, created_by=str(admin.get("email") or "admin"), environment=_state.environment,
                         app_version=_state.app_version, filters=body.model_dump())  # fmt: skip
    except PackError as exc:
        raise orena_http_error(422, exc.code, str(exc)) from exc
    counts: dict[str, int] = {}
    for item in items:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    reading._audit(admin, "admin.content_pack_export", entity_type="content_pack", entity_id="", payload={"counts": counts})
    return Response(raw, media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="orena-content.orenapack"', "Cache-Control": "no-store"})


async def _read_upload(upload: UploadFile | None) -> bytes:
    """The pack, read within its budget. Optional in the signature so that the administrator check runs first:
    a learner is refused (403) before anything about the request's shape is said."""

    if upload is None:
        raise orena_http_error(422, "pack_file_missing", "Choose a content pack file.")
    chunks, total = [], 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_PACK_BYTES:
            raise orena_http_error(413, "pack_too_large", "This pack is larger than an import accepts.")
        chunks.append(chunk)
    return b"".join(chunks)


def _verified(raw: bytes) -> Any:
    try:
        return read_pack(raw)
    except PackError as exc:
        raise orena_http_error(422, exc.code, str(exc)) from exc


def _existing(item: PackItem) -> tuple[str | None, str | None]:
    if item.kind in {"reading_source", "reading_article"}:
        return reading.pack_reading_existing(item)
    if _state.vocabulary_export is None:
        return None, None
    local = _state.vocabulary_export(item.natural_key)
    if local is None:
        return None, None
    wanted = {entry.get("identity_key") for entry in item.data.get("entries", [])}
    have = {entry.get("identity_key") for entry in local.get("entries", [])}
    # The collection is here with every sense the pack names: nothing to add.
    return (item.content_hash if wanted <= have else "local-differs"), None


def _plan(pack: Any) -> dict[str, Any]:
    rows = []
    for item in pack.items:
        existing, state = _existing(item)
        rows.append(plan_item(item, existing_hash=existing, source_state=state))
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["outcome"]] = summary.get(row["outcome"], 0) + 1
    manifest = pack.manifest
    return {"pack_id": manifest.get("pack_id"), "created_at": manifest.get("created_at"),
            "source_environment": manifest.get("source_environment"), "counts": manifest.get("counts"),
            "summary": summary, "items": rows, "policy": "skip"}  # fmt: skip


@router.post("/plan")
async def plan_pack(request: Request, file: UploadFile | None = File(default=None)) -> dict[str, Any]:
    reading._admin(request)
    reading._same_origin(request)
    pack = _verified(await _read_upload(file))
    return reading._guarded(lambda: _plan(pack))


@router.post("/import")
async def import_pack(request: Request, file: UploadFile | None = File(default=None)) -> dict[str, Any]:
    admin = reading._admin(request)
    reading._same_origin(request)
    pack = _verified(await _read_upload(file))
    pack_id = str(pack.manifest.get("pack_id") or "")
    order = {"reading_source": 0, "reading_article": 1, "vocabulary_collection": 2}
    results = []
    for item in sorted(pack.items, key=lambda entry: order[entry.kind]):
        existing, _state_of_source = _existing(item)
        outcome = plan_item(item, existing_hash=existing)["outcome"]
        try:
            if item.kind == "vocabulary_collection":
                if existing is not None:
                    result = {"result": "kept_local" if outcome != IDENTICAL else "identical"}
                elif _state.vocabulary_import is None:
                    result = {"result": "failed", "category": "vocabulary_unavailable"}
                else:
                    result = {"result": "imported", **_state.vocabulary_import(
                        dict(item.data), imported_by=reading._actor(admin), pack_id=pack_id)}
            else:
                result = reading._guarded(lambda item=item: reading.pack_import_reading(item, admin, pack_id=pack_id))
        except Exception as exc:  # noqa: BLE001 - one item never fails the pack; its failure is reported
            result = {"result": "failed", "category": getattr(exc, "code", type(exc).__name__)}
        results.append({"kind": item.kind, "natural_key": item.natural_key, "outcome": outcome, **result})
    summary: dict[str, int] = {}
    for row in results:
        summary[row["result"]] = summary.get(row["result"], 0) + 1
    reading._audit(admin, "admin.content_pack_import", entity_type="content_pack", entity_id=pack_id,
                   payload={"summary": summary})  # fmt: skip
    return {"pack_id": pack_id, "summary": summary, "items": results}
