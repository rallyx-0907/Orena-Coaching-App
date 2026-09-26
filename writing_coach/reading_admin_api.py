"""HTTP boundary of the Reading Content Engine's admin side.

`/api/admin/reading/*` - submitting content, watching the queue, reviewing a
candidate, publishing it, and managing sources. It keeps the rules the rest of
the console already keeps, because they are the console's rules and not this
feature's:

* every route is administrator-only, through the guard the app installs;
* every change must come from the console's own page (the `Origin` a browser
  attaches), so a sibling site cannot ride the session cookie;
* every privileged change writes an `audit_logs` row - one audit system, the
  one that already exists;
* nothing here answers with a body a list did not need: the queue is metadata,
  the preview is where a body and a source snapshot are fetched.

And two that belong to this engine:

* **no route publishes as a side effect.** Publication is its own explicit
  call, with an actor recorded on it.
* **nothing does the work in the request.** Submitting returns `202` and a job
  id; the worker does the fetching and the analysis.

Until the reviewed migration is applied, every route here answers
`503 reading_engine_unavailable` - the same shape Vocabulary import already
uses, so an operator sees one truthful "not active yet" rather than a
traceback.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.reading_content_repository import (
    CONTENT_KINDS,
    MAX_ARTICLE_PAGE,
    ReadingContentRepository,
    TargetInput,
)
from writing_coach.persistence.reading_evidence_repository import (
    ReadingEvidenceError,
    ReadingEvidenceRepository,
    body_sha256,
    question_inputs,
)
from writing_coach.reading_comprehension import GENERATOR_VERSION, process_article
from writing_coach.persistence.reading_job_repository import (
    MAX_JOB_PAGE,
    InvalidCursor,
    ReadingJobRepository,
)
from writing_coach.reading_content_engine import ReadingContentEngine
from writing_coach.reading_source_import import (
    MAX_FILE_BYTES,
    ReadingSourceError,
    SubmittedInput,
)
# The reaper's window, from the worker that owns it. Operations reads liveness
# against the same threshold the recovery path uses, so "stale" on the screen
# and "stale" in the database are one number rather than two that can drift.
from writing_coach.reading_worker import DEFAULT_STALE_AFTER

router = APIRouter(prefix="/api/admin/reading", tags=["admin-reading"])
_logger = logging.getLogger(__name__)

ARTICLE_ACTIONS = frozenset({"published", "unpublished", "rejected", "archived", "ready", "needs_review"})
SOURCE_STATES = frozenset({"needs_review", "approved", "active", "paused", "blocked", "rejected", "archived"})
_UPLOAD_CHUNK = 512 * 1024


@dataclass
class _Reading:
    admin_guard: Callable[[Request], Mapping[str, Any]] | None = None
    content: ReadingContentRepository | None = None
    jobs: ReadingJobRepository | None = None
    engine: ReadingContentEngine | None = None
    audit: Callable[..., None] | None = None
    evidence: ReadingEvidenceRepository | None = None
    generate: Callable[..., Any] | None = None


_state = _Reading()


def configure_reading_admin(
    *,
    admin_guard: Callable[[Request], Mapping[str, Any]] | None,
    content: ReadingContentRepository | None = None,
    jobs: ReadingJobRepository | None = None,
    engine: ReadingContentEngine | None = None,
    audit: Callable[..., None] | None = None,
    evidence: ReadingEvidenceRepository | None = None,
    generate: Callable[..., Any] | None = None,
) -> None:
    global _state
    _state = _Reading(
        admin_guard=admin_guard, content=content, jobs=jobs, engine=engine, audit=audit,
        evidence=evidence, generate=generate,
    )


# -- plumbing ------------------------------------------------------------------


def _admin(request: Request) -> Mapping[str, Any]:
    if _state.admin_guard is None:
        raise orena_http_error(503, "reading_engine_unavailable", "The Reading engine is not configured.")
    return _state.admin_guard(request) or {}


def _same_origin(request: Request) -> None:
    """A change must come from the console's own page.

    The session cookie is SameSite=Lax, which stops a cross-site form post but
    not a same-site one from a sibling subdomain. A browser attaches `Origin`
    to every request that changes something, so a change whose origin is
    absent or names another host is refused - the check the rest of the
    console already makes.
    """
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


def _engine() -> ReadingContentEngine:
    if _state.engine is None:
        raise orena_http_error(503, "reading_engine_unavailable", "The Reading engine is not active yet.")
    return _state.engine


def _content() -> ReadingContentRepository:
    if _state.content is None:
        raise orena_http_error(503, "reading_engine_unavailable", "The Reading engine is not active yet.")
    return _state.content


def _jobs() -> ReadingJobRepository:
    if _state.jobs is None:
        raise orena_http_error(503, "reading_engine_unavailable", "The Reading engine is not active yet.")
    return _state.jobs


def _evidence() -> ReadingEvidenceRepository:
    if _state.evidence is None:
        raise orena_http_error(503, "reading_engine_unavailable", "The Reading engine is not active yet.")
    return _state.evidence


def _evidence_call(call: Callable[[], Any]) -> Any:
    """A comprehension-set refusal is the administrator's to read, with its
    reason code; anything the schema cannot yet answer is the usual 503."""
    try:
        return _guarded(call)
    except ReadingEvidenceError as exc:
        status = 409 if exc.code in {"reading_set_frozen", "reading_set_transition_refused",
                                     "reading_set_undeletable", "reading_set_stale",
                                     "reading_article_not_published", "reading_article_changed"} else 422
        if exc.code in {"reading_processor_unavailable", "reading_processor_failed"}:
            status = 503
        raise orena_http_error(status, exc.code, str(exc)) from exc


def _category(exc: HTTPException) -> str:
    detail = exc.detail if isinstance(exc.detail, Mapping) else {}
    return str(detail.get("category") or "")


def publication_warnings(article: Mapping[str, Any]) -> list[dict[str, str]]:
    """Rights advice for publishing a Reading article, in the vocabulary
    console's weights. None of it stops anything (D-082): the administrator
    decides, and the decision is audited beside the warnings that were showing.

    Read from the snapshot's rights answers - the evidence captured at
    ingestion, and what the review pane already shows.
    """
    source = article.get("source") or {}
    state = source.get("rights_state") or {}
    warnings: list[dict[str, str]] = []
    republish = state.get("can_republish", "unknown")
    if republish == "denied":
        warnings.append({"code": "rights_not_cleared", "level": "strong"})
    elif republish != "allowed":
        warnings.append({"code": "rights_unknown", "level": "warning"})
    if article.get("is_adapted"):
        adapt = state.get("can_adapt", "unknown")
        if adapt == "denied":
            warnings.append({"code": "adaptation_not_cleared", "level": "strong"})
        elif adapt != "allowed":
            warnings.append({"code": "adaptation_unknown", "level": "warning"})
    if state.get("attribution_required", "unknown") == "unknown":
        warnings.append({"code": "attribution_unknown", "level": "warning"})
    return warnings


def _actor(admin: Mapping[str, Any]) -> str:
    return str(admin.get("google_sub") or admin.get("email") or "admin")


def _audit(
    admin: Mapping[str, Any],
    action: str,
    *,
    entity_type: str = "",
    entity_id: str = "",
    payload: Mapping[str, Any] | None = None,
) -> None:
    """Record what an administrator did, in `audit_logs`.

    Best-effort by design: the action has already happened by the time this
    runs, so a failed record is logged rather than undoing a publish. The
    review trail in `reading_review_events` is written inside the same
    transaction as the change itself and is not best-effort.
    """
    if _state.audit is None:
        return
    try:
        _state.audit(
            action,
            actor_key=_actor(admin),
            entity_type=entity_type,
            entity_id=entity_id,
            payload=dict(payload or {}),
        )
    except Exception:  # noqa: BLE001 - never lose the action over its record
        _logger.warning("reading admin: audit record failed for %s", action, exc_info=True)


def _guarded(call: Callable[[], Any]) -> Any:
    """Turn "the schema is not applied yet" into the same 503 as "not configured".

    An operator opening Reading before the migration is authorised sees one
    truthful message, never a raw database error naming a missing table.
    """
    try:
        return call()
    except HTTPException:
        raise
    except InvalidCursor as exc:
        raise orena_http_error(422, "reading_invalid_cursor", "That page cursor is not valid.") from exc
    except SQLAlchemyError as exc:
        _logger.warning("reading admin: schema not ready", exc_info=True)
        raise orena_http_error(
            503, "reading_engine_unavailable", "The Reading engine is not active yet."
        ) from exc


def _limit(raw: int | None, ceiling: int) -> int:
    return max(1, min(int(raw or ceiling), ceiling))


# -- models --------------------------------------------------------------------


class SourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    source_type: str = Field(min_length=1, max_length=20)
    base_url: str = Field(default="", max_length=600)
    languages: list[str] = Field(default_factory=list)
    automation_allowed: bool = False
    can_republish: bool = False
    can_adapt: bool = False
    attribution_required: bool = True
    license_note: str = Field(default="", max_length=2000)


class SourceStateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    polling_enabled: bool | None = None


class ArticleEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    body: str | None = None
    excerpt: str | None = Field(default=None, max_length=400)
    topic: str | None = Field(default=None, max_length=120)
    subtopic: str | None = Field(default=None, max_length=120)
    # `""` clears the admin override and returns the article to the machine's
    # estimate; omitting the field leaves it untouched. They are different
    # requests, so they have different spellings.
    reviewed_level: str | None = None
    # The learner-facing content type (`article`, `news`) - never the source's
    # feed mechanism or an editorial category of the publisher (D-083).
    content_kind: str | None = Field(default=None, max_length=20)
    reason: str = Field(default="", max_length=2000)


class ArticleStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reason: str = Field(default="", max_length=2000)


class ComprehensionSetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The language the explanations are written in; the learner meets the set
    # written in their own support language.
    support_language: str = Field(min_length=2, max_length=20)


class ComprehensionStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=20)
    reason: str = Field(default="", max_length=2000)


class QuestionDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1, max_length=20)


class TargetDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


class TargetOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The whole order, not a move. Bounded because the list is the article's
    # own targets and an unbounded array is an unbounded write.
    order: list[str] = Field(default_factory=list, max_length=200)


class TargetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    canonical_form: str = Field(default="", max_length=300)
    target_type: str = Field(default="word", max_length=30)
    context: str = Field(default="", max_length=2000)
    meaning: str = Field(default="", max_length=2000)


# -- sources -------------------------------------------------------------------


@router.get("/sources")
def list_sources(request: Request, response: Response) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    return {"items": _guarded(lambda: _content().list_sources())}


@router.post("/sources", status_code=201)
def create_source(request: Request, response: Response, payload: SourceBody) -> dict[str, Any]:
    """Register where content may come from. It starts unapproved, always.

    Nothing an admin types here begins fetching: `state` is `needs_review` and
    polling is off until a separate, deliberate approval - which is also what
    the schema's CHECK constraint enforces.
    """
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    source = _guarded(
        lambda: _content().create_source(
            slug=payload.slug.strip(),
            name=payload.name.strip(),
            source_type=payload.source_type.strip(),
            base_url=payload.base_url.strip(),
            languages=[language.strip().casefold() for language in payload.languages if language.strip()],
            rights={
                "automation_allowed": payload.automation_allowed,
                "can_republish": payload.can_republish,
                "can_adapt": payload.can_adapt,
                "attribution_required": payload.attribution_required,
                "license_note": payload.license_note,
            },
            created_by=_actor(admin),
        )
    )
    _audit(admin, "admin.reading_source_created", entity_type="reading_source", entity_id=source["id"],
           payload={"slug": source["slug"], "source_type": source["source_type"]})
    return source


@router.post("/sources/{source_id}")
def update_source(
    request: Request, response: Response, source_id: str, payload: SourceStateBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    state = payload.state.strip().casefold()
    if state not in SOURCE_STATES:
        raise orena_http_error(422, "reading_invalid_state", "That is not a source state.")
    source = _guarded(lambda: _content().set_source_state(source_id, state, actor=_actor(admin)))
    if source is None:
        raise orena_http_error(404, "reading_source_not_found", "That source is not in the registry.")
    _audit(admin, "admin.reading_source_state", entity_type="reading_source", entity_id=source_id,
           payload={"state": state})
    if payload.polling_enabled is not None:
        updated = _guarded(
            lambda: _content().set_polling(
                source_id, enabled=payload.polling_enabled, actor=_actor(admin)
            )
        )
        if updated is None:
            # Refused rather than failed: polling needs both an approved source
            # and a rights answer that allows automation.
            raise orena_http_error(
                422,
                "reading_polling_not_allowed",
                "Polling needs an active source whose rights allow automation.",
            )
        _audit(admin, "admin.reading_source_polling", entity_type="reading_source", entity_id=source_id,
               payload={"polling_enabled": payload.polling_enabled})
        source = updated
    return source


# -- submission ----------------------------------------------------------------


@router.post("/jobs", status_code=202)
async def submit_content(
    request: Request,
    response: Response,
    kind: str = Form(...),
    text: str = Form(""),
    url: str = Form(""),
    title: str = Form(""),
    author: str = Form(""),
    language: str = Form(""),
    published_at: str = Form(""),
    source_name: str = Form(""),
    # No default answer. A rights question the submitter did not answer stays
    # unanswered in the snapshot: a `False` default would record a refusal
    # nobody made, and a reviewer would then be deciding against evidence that
    # was invented by a form.
    can_republish: bool | None = Form(None),
    can_adapt: bool | None = Form(None),
    attribution_required: bool | None = Form(None),
    license_note: str = Form(""),
    upload: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Accept one submission and return its job. 202, not 200.

    The status code is the contract: this did not happen yet. Nothing is
    fetched, parsed or analysed here - an admin pasting from a slow site waits
    for a job id, not for that site.
    """
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    payload = b""
    filename = ""
    if upload is not None:
        filename = upload.filename or ""
        payload = await _read_upload(upload)
    submitted = SubmittedInput(
        kind=kind.strip().casefold(),
        text=text,
        url=url.strip(),
        filename=filename,
        payload=payload,
        title=title.strip(),
        author=author.strip(),
        language=language.strip().casefold(),
        published_at=published_at.strip(),
        source_name=source_name.strip(),
        rights={
            key: value
            for key, value in (
                ("can_republish", can_republish),
                ("can_adapt", can_adapt),
                ("attribution_required", attribution_required),
                ("license_note", license_note.strip() or None),
            )
            if value is not None
        },
    )
    try:
        job = _guarded(lambda: _engine().submit(submitted, actor=_actor(admin)))
    except ReadingSourceError as refusal:
        raise orena_http_error(422, refusal.code, refusal.message) from refusal
    _audit(admin, "admin.reading_ingestion_submitted", entity_type="reading_job", entity_id=job["id"],
           payload={"kind": submitted.kind, "duplicate": job["duplicate"]})
    return {
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "duplicate": job["duplicate"],
        "job_type": job["job_type"],
    }


async def _read_upload(upload: UploadFile) -> bytes:
    """Read an upload within its budget, never past it.

    Reading first and checking after is how an oversized file costs exactly
    the memory the limit exists to protect - the fix `vocabulary_source_import`
    already made.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise orena_http_error(413, "source_too_large", "This file is larger than the engine accepts.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/jobs")
def list_jobs(
    request: Request,
    response: Response,
    status: str = "",
    cursor: str = "",
    limit: int = MAX_JOB_PAGE,
) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    return _guarded(
        lambda: _jobs().list_jobs(
            status=status.strip() or None, cursor=cursor or None, limit=_limit(limit, MAX_JOB_PAGE)
        )
    )


@router.get("/jobs/{job_id}")
def get_job(request: Request, response: Response, job_id: str) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    job = _guarded(lambda: _jobs().get_job(job_id))
    if job is None:
        raise orena_http_error(404, "reading_job_not_found", "That import is not in the queue.")
    # The submitted payload can be a whole article; an admin watching a job
    # needs its state, not its contents.
    job.pop("input_json", None)
    return job


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(request: Request, response: Response, job_id: str) -> dict[str, Any]:
    """Re-submit a finished job's input as a new job.

    The failed row keeps its error and its attempts: an admin looking at
    Imports is there to read what went wrong, and a mutated row would have
    erased it.
    """
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    job = _guarded(lambda: _jobs().retry(job_id, actor=_actor(admin)))
    if job is None:
        raise orena_http_error(
            409, "reading_job_not_retryable", "Only a finished import can be submitted again."
        )
    _audit(admin, "admin.reading_ingestion_retried", entity_type="reading_job", entity_id=job["id"],
           payload={"from_job": job_id, "duplicate": job["duplicate"]})
    return {"id": job["id"], "status": job["status"], "duplicate": job["duplicate"]}


# -- review --------------------------------------------------------------------


@router.get("/queue")
def review_queue(
    request: Request,
    response: Response,
    status: str = "",
    cursor: str = "",
    limit: int = MAX_ARTICLE_PAGE,
) -> dict[str, Any]:
    """Candidates waiting for a decision. Metadata only - Preview fetches the
    article, the snapshot and the evidence."""
    _admin(request)
    _no_store(response)
    statuses = tuple(part.strip() for part in status.split(",") if part.strip())
    return _guarded(
        lambda: _content().list_queue(
            **({"statuses": statuses} if statuses else {}),
            cursor=cursor or None,
            limit=_limit(limit, MAX_ARTICLE_PAGE),
        )
    )


@router.get("/articles/{article_id}")
def preview_article(request: Request, response: Response, article_id: str) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    article = _guarded(lambda: _content().get_article(article_id))
    if article is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    article["events"] = _guarded(lambda: _content().list_review_events(article_id))
    if article.get("source"):
        article["duplicates"] = _guarded(
            lambda: _content().find_duplicate_content(
                article["source"]["content_hash"], exclude_source_id=article["source"]["source_id"]
            )
        )
    _audit(admin, "admin.reading_article_previewed", entity_type="reading_article", entity_id=article_id)
    return article


@router.post("/articles/{article_id}")
def edit_article(
    request: Request, response: Response, article_id: str, payload: ArticleEditBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    content_kind = payload.content_kind.strip().casefold() if payload.content_kind is not None else None
    if content_kind is not None and content_kind not in CONTENT_KINDS:
        raise orena_http_error(422, "reading_invalid_content_kind", "That is not a Reading content type.")
    article = _guarded(
        lambda: _content().update_article(
            article_id,
            actor=_actor(admin),
            title=payload.title,
            body=payload.body,
            excerpt=payload.excerpt,
            topic=payload.topic,
            subtopic=payload.subtopic,
            # The model's `None` means "not supplied"; the repository's "" means
            # that, and its `None` means "clear the override". Translating here
            # keeps the two vocabularies from leaking into each other.
            reviewed_level=(
                "" if payload.reviewed_level is None else (payload.reviewed_level.strip() or None)
            ),
            content_kind=content_kind,
            reason=payload.reason,
        )
    )
    if article is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    _audit(
        admin,
        "admin.reading_level_override" if payload.reviewed_level is not None else "admin.reading_article_edited",
        entity_type="reading_article",
        entity_id=article_id,
        payload={"reviewed_level": article["reviewed_level"], "effective_level": article["effective_level"]},
    )
    return article


@router.post("/articles/{article_id}/status")
def set_article_status(
    request: Request, response: Response, article_id: str, payload: ArticleStatusBody
) -> dict[str, Any]:
    """Publish, unpublish, reject or archive - always an admin's own act.

    Nothing in the pipeline reaches this route, which is what "no auto-publish"
    means in code rather than in a policy document.
    """
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    status = payload.status.strip().casefold()
    if status not in ARTICLE_ACTIONS:
        raise orena_http_error(422, "reading_invalid_status", "That is not an article status.")
    if status == "rejected" and not payload.reason.strip():
        raise orena_http_error(
            422, "reading_reason_required", "A rejection keeps its reason - say why."
        )
    warnings: list[dict[str, str]] = []
    if status == "published":
        current = _guarded(lambda: _content().get_article(article_id))
        if current is None:
            raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
        warnings = publication_warnings(current)
    article = _guarded(
        lambda: _content().set_status(
            article_id, status, actor=_actor(admin), reason=payload.reason.strip(), warnings=warnings
        )
    )
    if article is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    audit_payload: dict[str, Any] = {"status": status, "reason": payload.reason.strip()}
    if status == "published":
        # An override is only meaningful beside what it overrode.
        audit_payload |= {"warnings": warnings, "override": bool(warnings)}
    _audit(admin, f"admin.reading_article_{status}", entity_type="reading_article", entity_id=article_id,
           payload=audit_payload)
    if status == "published":
        return {**article, "publication_warnings": warnings}
    return article


# -- comprehension sets ------------------------------------------------------------
# For a published article only (D-082: import, review, publish, then the set).
# The processor writes a draft; an administrator decides every question and the
# set. Nothing here is visible to a learner until the set is approved, and an
# approval re-checks that every question is grounded in the article's body as
# it is now.

SET_STATUSES = frozenset({"draft", "needs_review", "approved", "rejected", "archived"})


@router.get("/articles/{article_id}/comprehension-sets")
def list_comprehension_sets(request: Request, response: Response, article_id: str) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    return {"items": _evidence_call(lambda: _evidence().list_sets(article_id))}


@router.post("/articles/{article_id}/comprehension-sets", status_code=201)
def generate_comprehension_set(
    request: Request, response: Response, article_id: str, payload: ComprehensionSetBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    article = _guarded(lambda: _content().get_article(article_id))
    if article is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    # Published first (D-082): refused here before the provider is asked, and
    # again under the article's lock when the draft is written.
    if article.get("status") != "published":
        raise orena_http_error(409, "reading_article_not_published",
                               "Publish the article first: a comprehension set is built for a published article only.")
    support = payload.support_language.strip().casefold()
    # The body the model is shown is the body the set is anchored to: its hash
    # is taken before the AI call and required again under the article's lock.
    # An edit in between refuses the draft and the questions are written again
    # for the new text - once; a second change in a row is the admin's to retry.
    try:
        created, model = _written_set(admin, article_id, article, support)
    except HTTPException as exc:
        if _category(exc) != "reading_article_changed":
            raise
        article = _guarded(lambda: _content().get_article(article_id))
        if article is None:
            raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.") from exc
        created, model = _written_set(admin, article_id, article, support)
    _audit(admin, "admin.reading_comprehension_set_created", entity_type="reading_comprehension_set",
           entity_id=created["id"], payload={"article_id": article_id, "questions": len(created["questions"]),
                                             "support_language": support, "model": model})
    return created


def _written_set(admin: Mapping[str, Any], article_id: str, article: Mapping[str, Any],
                 support: str) -> tuple[dict[str, Any], str]:
    """One pass: hash the body, ask the processor about exactly that body, and
    write the draft only if the body under the lock still has that hash."""
    anchor = body_sha256(str(article.get("body") or ""))
    processed = _evidence_call(lambda: process_article(article, support_code=support, generate=_state.generate))
    created = _evidence_call(lambda: _evidence().create_set(
        article_id, support_language=support, generator_version=GENERATOR_VERSION, model=processed.model,
        questions=question_inputs(processed.questions), validation=processed.validation,
        actor=_actor(admin), expected_body_sha256=anchor,
    ))
    return created, processed.model


@router.get("/comprehension-sets/{set_id}")
def get_comprehension_set(request: Request, response: Response, set_id: str) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    found = _evidence_call(lambda: _evidence().get_set(set_id))
    if found is None:
        raise orena_http_error(404, "reading_set_not_found", "That comprehension set does not exist.")
    return found


@router.post("/comprehension-sets/{set_id}/questions/{question_id}")
def decide_comprehension_question(
    request: Request, response: Response, set_id: str, question_id: str, payload: QuestionDecisionBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    decision = payload.decision.strip().casefold()
    found = _evidence_call(lambda: _evidence().decide_question(
        set_id, question_id, decision=decision, actor=_actor(admin)))
    if found is None:
        raise orena_http_error(404, "reading_question_not_found", "That question is not in this set.")
    _audit(admin, f"admin.reading_comprehension_question_{decision}", entity_type="reading_comprehension_set",
           entity_id=set_id, payload={"question_id": question_id})
    return found


@router.post("/comprehension-sets/{set_id}/status")
def set_comprehension_status(
    request: Request, response: Response, set_id: str, payload: ComprehensionStatusBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    status = payload.status.strip().casefold()
    if status not in SET_STATUSES:
        raise orena_http_error(422, "reading_invalid_status", "That is not a comprehension-set status.")
    if status == "rejected" and not payload.reason.strip():
        raise orena_http_error(422, "reading_reason_required", "A rejection keeps its reason - say why.")
    found = _evidence_call(lambda: _evidence().transition(
        set_id, status, actor=_actor(admin), reason=payload.reason.strip()))
    if found is None:
        raise orena_http_error(404, "reading_set_not_found", "That comprehension set does not exist.")
    _audit(admin, f"admin.reading_comprehension_set_{status}", entity_type="reading_comprehension_set",
           entity_id=set_id, payload={"status": status, "reason": payload.reason.strip()})
    return found


@router.post("/comprehension-sets/{set_id}/discard")
def discard_comprehension_set(request: Request, response: Response, set_id: str) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    if not _evidence_call(lambda: _evidence().discard_set(set_id, actor=_actor(admin))):
        raise orena_http_error(404, "reading_set_not_found", "That comprehension set does not exist.")
    _audit(admin, "admin.reading_comprehension_set_discarded", entity_type="reading_comprehension_set",
           entity_id=set_id)
    return {"discarded": True, "id": set_id}


@router.post("/articles/{article_id}/targets")
def add_target(
    request: Request, response: Response, article_id: str, payload: TargetBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    existing = _guarded(lambda: _content().get_article(article_id))
    if existing is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    target = _guarded(
        lambda: _content().add_target(
            article_id,
            target=TargetInput(
                text=payload.text.strip(),
                canonical_form=(payload.canonical_form.strip() or payload.text.strip().casefold()),
                target_type=payload.target_type.strip(),
                context=payload.context.strip(),
                meaning=payload.meaning.strip(),
                estimated_level="",
                rank=len(existing["targets"]),
                machine_suggested=False,
            ),
            actor=_actor(admin),
        )
    )
    _audit(admin, "admin.reading_target_added", entity_type="reading_article", entity_id=article_id,
           payload={"text": payload.text.strip()})
    return target


@router.post("/articles/{article_id}/target-order")
def reorder_targets(
    request: Request, response: Response, article_id: str, payload: TargetOrderBody
) -> dict[str, Any]:
    """The order a learner meets the targets in, as the reviewer arranged it.

    Its own path rather than `/targets/order`, which would sit in the same
    shape as `/targets/{target_id}` and be one route-ordering accident away
    from being read as a target whose id is the word "order".
    """
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    if _guarded(lambda: _content().get_article(article_id)) is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not in the catalog.")
    targets = _guarded(
        lambda: _content().reorder_targets(article_id, order=payload.order, actor=_actor(admin))
    )
    if targets is None:
        raise orena_http_error(
            400,
            "reading_target_order_mismatch",
            "An order must list this article's learning targets exactly once each.",
        )
    _audit(admin, "admin.reading_targets_reordered", entity_type="reading_article",
           entity_id=article_id, payload={"count": len(targets)})
    return {"targets": targets}


@router.post("/articles/{article_id}/targets/{target_id}")
def decide_target(
    request: Request, response: Response, article_id: str, target_id: str, payload: TargetDecisionBody
) -> dict[str, Any]:
    admin = _admin(request)
    _same_origin(request)
    _no_store(response)
    target = _guarded(
        lambda: _content().decide_target(
            target_id, article_id=article_id, approved=payload.approved, actor=_actor(admin)
        )
    )
    if target is None:
        raise orena_http_error(404, "reading_target_not_found", "That learning target is not on this article.")
    _audit(
        admin,
        "admin.reading_target_approved" if payload.approved else "admin.reading_target_rejected",
        entity_type="reading_article",
        entity_id=article_id,
        payload={"target": target["text"]},
    )
    return target


# -- operations ----------------------------------------------------------------


def _worker_health() -> dict[str, Any]:
    """Who is processing, derived from the claims the queue already holds.

    `derived_from_claims` is not decoration: the console renders a different
    sentence for it. A worker that has never taken a job cannot appear here,
    so "two workers" means "two workers were seen holding work", not "two
    processes exist". Saying which of those two the number is keeps the panel
    honest without a registry table, which is a schema decision this lane may
    not make on its own.
    """
    items = _jobs().workers(stale_after=DEFAULT_STALE_AFTER)
    return {
        "items": items,
        "running": sum(entry["running"] for entry in items),
        "stale_after_seconds": int(DEFAULT_STALE_AFTER.total_seconds()),
        "derived_from_claims": True,
    }


@router.get("/operations")
def operations(request: Request, response: Response) -> dict[str, Any]:
    """Queue depth, article states and worker health, counted in the database."""
    _admin(request)
    _no_store(response)
    return _guarded(
        lambda: {
            "queue": _jobs().counts_by_status(),
            "articles": _content().counts_by_status(),
            "published": _content().published_count(),
            "recent": _jobs().list_jobs(limit=5)["items"],
            "workers": _worker_health(),
        }
    )
