"""Admin routes of the grammar content store (`/api/admin/grammar/*`, GRAMMAR_CONTENT_STORE.md rev 3a sections 5, 6, 12).

Import (dry run and commit), batch rights attestation, version review and rights, publish (single and bulk),
unpublish / archive / restore, and the admin reads. Built like `reading_admin_api.py`: the guard is
`require_admin`, every change must come from the console's own origin, every answer is `no-store`, every privileged
change writes an `audit_logs` row (best effort, after the change) on top of the transactional review event.

No route publishes as a side effect: import, review and rights never publish; publish is its own explicit act.
Upload bodies are untrusted data: parsed with budgets, never evaluated, never used as a path.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from writing_coach.core.errors import orena_http_error
from writing_coach.grammar_store.package import MAX_UPLOAD_BYTES, PackageError, read_package, validate_package
from writing_coach.persistence.grammar_store_repository import GrammarStoreRefusal, GrammarStoreRepository

router = APIRouter(prefix="/api/admin/grammar", tags=["admin-grammar"])
_logger = logging.getLogger(__name__)
_UPLOAD_CHUNK = 512 * 1024
UNAVAILABLE = "grammar_store_unavailable"


@dataclass
class _Grammar:
    admin_guard: Callable[[Request], Mapping[str, Any]] | None = None
    store: GrammarStoreRepository | None = None
    audit: Callable[..., None] | None = None


_state = _Grammar()


def configure_grammar_admin(
    *,
    admin_guard: Callable[[Request], Mapping[str, Any]] | None,
    store: GrammarStoreRepository | None = None,
    audit: Callable[..., None] | None = None,
) -> None:
    global _state
    _state = _Grammar(admin_guard=admin_guard, store=store, audit=audit)


# -- plumbing ----------------------------------------------------------------------------------------------------------


def _admin(request: Request) -> Mapping[str, Any]:
    if _state.admin_guard is None:
        raise orena_http_error(503, UNAVAILABLE, "The grammar store is not configured.")
    return _state.admin_guard(request) or {}


def _same_origin(request: Request) -> None:
    """A change must come from the console's own page (the Reading admin's rule)."""
    from urllib.parse import urlsplit

    origin = request.headers.get("origin")
    if not origin:
        raise orena_http_error(403, "admin_origin_required", "Admin changes must be made from the admin console.")
    try:
        origin_host = urlsplit(origin).netloc
    except ValueError:
        origin_host = ""
    if not origin_host or origin_host != request.headers.get("host", ""):
        raise orena_http_error(403, "admin_origin_mismatch", "Admin changes must be made from the admin console.")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _store() -> GrammarStoreRepository:
    if _state.store is None:
        raise orena_http_error(503, UNAVAILABLE, "The grammar store is not active yet.")
    return _state.store


def _actor(admin: Mapping[str, Any]) -> str:
    return str(admin.get("google_sub") or admin.get("email") or "admin")


def _audit(admin: Mapping[str, Any], action: str, *, entity_type: str = "", entity_id: str = "",
           payload: Mapping[str, Any] | None = None) -> None:
    if _state.audit is None:
        return
    try:
        _state.audit(action, actor_key=_actor(admin), entity_type=entity_type, entity_id=entity_id,
                     payload=dict(payload or {}))
    except Exception:  # noqa: BLE001 - never lose the action over its record
        _logger.warning("grammar admin: audit record failed for %s", action, exc_info=True)


def _guarded(call: Callable[[], Any]) -> Any:
    """Domain refusals keep their status; "the schema is not applied yet" is the same 503 as "not configured"."""
    try:
        return call()
    except HTTPException:
        raise
    except GrammarStoreRefusal as refusal:
        raise orena_http_error(refusal.status, refusal.code, refusal.message, context=refusal.context) from refusal
    except SQLAlchemyError as exc:
        _logger.warning("grammar admin: store not ready", exc_info=True)
        raise orena_http_error(503, UNAVAILABLE, "The grammar store is not active yet.") from exc


async def _read_upload(upload: UploadFile | None) -> tuple[bytes, str]:
    if upload is None:
        raise orena_http_error(422, "grammar_package_missing", "Choose an export package (.zip) to upload.")
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_UPLOAD_CHUNK):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise orena_http_error(413, "grammar_package_too_large", "This package is larger than the store accepts.")
        chunks.append(chunk)
    return b"".join(chunks), (upload.filename or "")[:255]


def _package(data: bytes):
    try:
        return validate_package(read_package(data))
    except PackageError as error:
        raise orena_http_error(422, "grammar_package_unreadable", "The upload is not a readable export package.",
                               context={"problems": [p.to_dict() for p in error.problems]}) from error


# -- import ------------------------------------------------------------------------------------------------------------


@router.post("/imports/validate")
async def validate_import(request: Request, response: Response, upload: UploadFile | None = File(None)) -> dict:
    """Dry run: the report and the diff. Writes nothing."""
    _admin(request)
    _same_origin(request)
    _no_store(response)
    data, _ = await _read_upload(upload)
    pkg = _package(data)
    return _guarded(lambda: _store().validate_import(pkg))


@router.post("/imports", status_code=201)
async def commit_import(
    request: Request,
    response: Response,
    upload: UploadFile | None = File(None),
    package_hash: str = Form(""),
    rights_basis: str = Form(""),
    rights_attestation: str = Form(""),
) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    data, filename = await _read_upload(upload)
    rights = None
    if rights_basis or rights_attestation.strip():
        if not rights_basis or not rights_attestation.strip():
            raise orena_http_error(422, "grammar_rights_invalid", "A rights basis needs its attestation text.")
        rights = {"basis": rights_basis, "attestation": rights_attestation.strip()}
    pkg = _package(data)
    outcome = _guarded(lambda: _store().commit_import(pkg, filename=filename, actor=_actor(admin),
                                                      echoed_hash=package_hash, rights=rights))
    batch = outcome.batch or {}
    if outcome.status == "already_imported":
        response.status_code = 200
        return {"already_imported": True, "batch": batch}
    _audit(admin, f"admin.grammar_import_{outcome.status}", entity_type="grammar_import_batch",
           entity_id=batch.get("id", ""), payload={"language": batch.get("language"), "counts": batch.get("counts"),
                                                   "package_hash": batch.get("package_hash")})
    if outcome.status == "rejected":
        raise orena_http_error(422, "grammar_package_rejected", "The package was rejected; nothing was imported.",
                               context={"batch": batch, "report": outcome.report})
    return {"already_imported": False, "batch": batch, "report": outcome.report}


@router.get("/imports")
def list_imports(request: Request, response: Response, limit: int = Query(50, ge=1, le=200)) -> dict:
    _admin(request)
    _no_store(response)
    return {"batches": _guarded(lambda: _store().list_batches(limit=limit))}


@router.get("/imports/{batch_id}")
def get_import(batch_id: str, request: Request, response: Response) -> dict:
    _admin(request)
    _no_store(response)
    return _guarded(lambda: _store().get_batch(batch_id))


class RightsBody(BaseModel):
    basis: str = Field(max_length=40)
    attestation: str = Field(min_length=1, max_length=4000)


@router.post("/imports/{batch_id}/rights")
def attest_import(batch_id: str, body: RightsBody, request: Request, response: Response) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    batch = _guarded(lambda: _store().attest_batch(batch_id, basis=body.basis, attestation=body.attestation,
                                                   actor=_actor(admin)))
    _audit(admin, "admin.grammar_rights_attested", entity_type="grammar_import_batch", entity_id=batch["id"],
           payload={"basis": body.basis})
    return batch


# -- review and rights of one version ------------------------------------------------------------------------------------


class ReviewBody(BaseModel):
    decision: str = Field(max_length=10)
    reason: str = Field("", max_length=4000)


@router.post("/versions/{version_id}/review")
def review_version(version_id: str, body: ReviewBody, request: Request, response: Response) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    version = _guarded(lambda: _store().review_version(version_id, decision=body.decision, actor=_actor(admin),
                                                       reason=body.reason))
    _audit(admin, "admin.grammar_review", entity_type="grammar_point_version", entity_id=version["id"],
           payload={"point_id": version["point_id"], "decision": body.decision})
    return version


class VersionRightsBody(BaseModel):
    status: str = Field(max_length=20)
    reason: str = Field(min_length=1, max_length=4000)


@router.post("/versions/{version_id}/rights")
def set_version_rights(version_id: str, body: VersionRightsBody, request: Request, response: Response) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    version = _guarded(lambda: _store().set_version_rights(version_id, status=body.status, actor=_actor(admin),
                                                           reason=body.reason))
    _audit(admin, "admin.grammar_rights_set", entity_type="grammar_point_version", entity_id=version["id"],
           payload={"point_id": version["point_id"], "status": body.status})
    return version


@router.get("/versions/{version_id}/preview")
def preview_version(version_id: str, request: Request, response: Response) -> dict:
    """The whitelisted body exactly as a learner would receive it; admin-only, any review state."""
    _admin(request)
    _no_store(response)
    return _guarded(lambda: _store().preview(version_id))


# -- points: reads, publish, status --------------------------------------------------------------------------------------


@router.get("/points")
def list_points(
    request: Request,
    response: Response,
    language: str | None = Query(None, max_length=20),
    status: str | None = Query(None, max_length=20),
    review: str | None = Query(None, max_length=20),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    _admin(request)
    _no_store(response)
    return {"points": _guarded(lambda: _store().list_points(language=language, lifecycle=status, review=review,
                                                            limit=limit))}


@router.get("/points/{point_id}")
def get_point(point_id: str, request: Request, response: Response) -> dict:
    _admin(request)
    _no_store(response)
    return _guarded(lambda: _store().admin_point(point_id))


class PublishBody(BaseModel):
    version_id: str = Field(max_length=64)
    attested: bool = False
    override_references: bool = False
    reason: str = Field("", max_length=4000)


def _require_attested(attested: bool) -> None:
    if not attested:
        raise orena_http_error(422, "grammar_publish_unattested",
                               "Publishing is an explicit act: confirm it with attested: true.")


@router.post("/points/{point_id}/publish")
def publish_point(point_id: str, body: PublishBody, request: Request, response: Response) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    _require_attested(body.attested)
    result = _guarded(lambda: _store().publish([(point_id, body.version_id)], actor=_actor(admin),
                                               override_references=body.override_references, reason=body.reason))
    _audit(admin, "admin.grammar_publish", entity_type="grammar_point", entity_id=point_id,
           payload={**result, "override_references": body.override_references})
    return result


class BulkItem(BaseModel):
    point_id: str = Field(max_length=120)
    version_id: str = Field(max_length=64)


class BulkPublishBody(BaseModel):
    items: list[BulkItem] = Field(min_length=1, max_length=1000)
    attested: bool = False
    reason: str = Field("", max_length=4000)


@router.post("/publish")
def publish_bulk(body: BulkPublishBody, request: Request, response: Response) -> dict:
    """All-or-nothing; references are checked against the state the whole publish leaves."""
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    _require_attested(body.attested)
    result = _guarded(lambda: _store().publish([(i.point_id, i.version_id) for i in body.items], actor=_actor(admin),
                                               reason=body.reason))
    _audit(admin, "admin.grammar_publish_bulk", entity_type="grammar_point", entity_id=str(len(body.items)),
           payload={"count": len(result["published"])})
    return result


class StatusBody(BaseModel):
    action: str = Field(max_length=20)
    reason: str = Field("", max_length=4000)


@router.post("/points/{point_id}/status")
def set_point_status(point_id: str, body: StatusBody, request: Request, response: Response) -> dict:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    point = _guarded(lambda: _store().set_point_status(point_id, action=body.action, actor=_actor(admin),
                                                       reason=body.reason))
    _audit(admin, f"admin.grammar_{body.action}", entity_type="grammar_point", entity_id=point_id)
    return point


@router.get("/r5-map")
def r5_map(request: Request, response: Response, language: str = Query(..., max_length=20)) -> dict:
    _admin(request)
    _no_store(response)
    return {"language": language, "rows": _guarded(lambda: _store().r5_rows(language))}


@router.get("/coverage")
def coverage(request: Request, response: Response, language: str = Query(..., max_length=20)) -> dict:
    """R5 ids with neither a published primary nor a dropped row: must be empty before R5 removal (step 9)."""
    _admin(request)
    _no_store(response)
    unresolved = _guarded(lambda: _store().coverage(language))
    return {"language": language, "unresolved": unresolved, "complete": not unresolved}
