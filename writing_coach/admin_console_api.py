"""HTTP boundary of the Platform Admin control center (`/api/admin/console`).

The console composes contracts that already exist rather than growing new
ones: the AI control plane (capability registry, saved routes, operation
telemetry, provider credentials), the reading/media/vocabulary catalogs and
their importers, and the learner-evidence tables every capability writes.
What it adds is read-only aggregation over those facts, the admin list of
accounts the human product owner authorised on 2026-09-18, and audit rows in
the existing `audit_logs` table for every account read, content action and
import attempt.

Rules this boundary keeps:

* every route is administrator-only, through the guard the app installs;
* a number is either computed from stored rows or reported as unavailable or
  insufficient - never estimated, never filled in;
* nothing learner-authored leaves the server (no essay, passage, transcript of
  a learner, saved word or conversation); account identity is masked in lists
  and shown whole only in an audited detail read;
* no secret value is ever returned; credential state is a word, not a value;
* learner runtime activation stays a deployment decision - this reports it.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from writing_coach import media_library_api, reading_library_api
from writing_coach.admin_content import (
    book_error_stage,
    book_record,
    content_counts,
    curated_media_record,
    filter_history,
    filter_records,
    history_rows,
    media_record,
    paginate,
    recent_failures,
    status_counts,
    transcript_attention_count,
    vocabulary_record,
)
from writing_coach.admin_metrics import (
    activity_days,
    daily_series,
    day_keys,
    learner_segments,
    needs_attention,
    retention_windows,
)
from writing_coach.core.errors import orena_http_error

router = APIRouter(prefix="/api/admin/console", tags=["admin-console"])
_logger = logging.getLogger(__name__)

ACTIVITY_DOMAINS = ("writing", "reading", "listening", "speaking", "vocabulary", "grammar")
TREND_DAYS = 30
RETENTION_COHORT_DAYS = 90
PUBLISHABLE_RIGHTS = frozenset({"public_domain", "licensed", "creator_authorized", "internal_curated"})
TRANSCRIPT_PREVIEW_SEGMENTS = 12
VOCABULARY_PREVIEW_ENTRIES = 25


@dataclass
class _Console:
    admin_guard: Callable[[Request], Mapping[str, Any]] | None = None
    backend: str = ""
    repository: Any = None
    platform_repository: Any = None
    vocabulary_repository: Any = None
    media_store: Any = None
    reading_repository: Any = None
    runtime_services: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_facts: Callable[[], Mapping[str, Any]] | None = None
    app_version: str = ""


_state = _Console()


def configure_admin_console(
    *,
    admin_guard: Callable[[Request], Mapping[str, Any]] | None,
    backend: str = "",
    repository: Any = None,
    platform_repository: Any = None,
    vocabulary_repository: Any = None,
    media_store: Any = None,
    reading_repository: Any = None,
    runtime_services: Mapping[str, Mapping[str, Any]] | None = None,
    runtime_facts: Callable[[], Mapping[str, Any]] | None = None,
    app_version: str = "",
) -> None:
    global _state
    _state = _Console(
        admin_guard=admin_guard,
        backend=backend,
        repository=repository,
        platform_repository=platform_repository,
        vocabulary_repository=vocabulary_repository,
        media_store=media_store,
        reading_repository=reading_repository,
        runtime_services={key: dict(value) for key, value in (runtime_services or {}).items()},
        runtime_facts=runtime_facts,
        app_version=app_version,
    )


def describe_runtime_services(
    *,
    media_translation: tuple[str, Any],
    reading_translation: tuple[str, Any],
    speech_recognition: Any,
    pronunciation: Any,
    transcript_fallback: str,
) -> dict[str, dict[str, str]]:
    """The deployment-configured engines outside the capability registry.

    Media and reading translation, speech recognition, pronunciation scoring
    and the transcript fallback are chosen from environment configuration at
    startup (app.py) rather than routed through capability configuration, so
    the console reports them as they are and never offers to change them.
    Only names are read - never a key, token or endpoint.

    `configured` means a credentialed engine has its credential; `selected`
    means a local engine was chosen that needs none (its reachability is not
    probed here); `demo` is the synthetic development scorer.
    """
    from writing_coach.ai.control_plane import safe_model_display

    def engine(provider_id: str, provider: Any) -> dict[str, str]:
        credentialed = hasattr(provider, "configured")
        state = ("configured" if getattr(provider, "configured", False) else "not_configured") if credentialed else "selected"
        return {
            "provider": str(provider_id or ""),
            "engine": str(getattr(provider, "engine_id", "") or provider_id or ""),
            "model": safe_model_display(getattr(provider, "model_version", "") or "")[0],
            "state": state,
        }

    def attached(provider: Any, *, demo: str = "") -> dict[str, str]:
        if provider is None:
            return {"provider": "", "engine": "", "model": "", "state": "not_configured"}
        identifier = str(getattr(provider, "provider_id", "") or "")
        return {
            "provider": identifier,
            "engine": identifier,
            "model": safe_model_display(getattr(provider, "model", "") or "")[0],
            "state": "demo" if demo and identifier == demo else "configured",
        }

    fallback = str(transcript_fallback or "none")
    return {
        "media_translation": engine(*media_translation),
        "reading_translation": engine(*reading_translation),
        "speech_recognition": attached(speech_recognition),
        "pronunciation": attached(pronunciation, demo="demo-synthetic"),
        "transcript_fallback": {
            "provider": fallback, "engine": fallback, "model": "",
            "state": "not_configured" if fallback == "none" else "configured",
        },
    }


def schema_facts(engine: Any) -> dict[str, Any]:
    """The runtime schema revision against the one this build expects."""
    if engine is None:
        return {"state": "not_applicable", "current": None, "expected": None}
    try:
        from alembic.runtime.migration import MigrationContext

        from writing_coach.persistence.runtime import runtime_head

        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        expected = runtime_head()
    except Exception:  # noqa: BLE001 - unreadable is a state to report
        return {"state": "unreadable", "current": None, "expected": None}
    return {"state": "ready" if current == expected else "mismatch", "current": current, "expected": expected}


# -- plumbing -------------------------------------------------------------------


def _admin(request: Request) -> Mapping[str, Any]:
    if _state.admin_guard is None:
        raise orena_http_error(503, "admin_console_unavailable", "The admin console is not configured.")
    return _state.admin_guard(request) or {}


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _now() -> datetime:
    return datetime.now(UTC)


def _day_start(day) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _actor(admin: Mapping[str, Any]) -> str:
    return str(admin.get("google_sub") or admin.get("email") or "admin")


def _audit(admin: Mapping[str, Any], action: str, *, entity_type: str = "", entity_id: str = "",
           payload: Mapping[str, Any] | None = None, required: bool = False) -> None:
    """Record what an administrator did or read.

    Reading account data is refused when it cannot be recorded (`required`):
    admin access to accounts is conditional on the record existing. An import
    or content action has already happened by the time it is recorded, so a
    failed record there is logged rather than undoing the action.
    """
    repository = _state.repository
    if repository is None:
        if required:
            raise orena_http_error(503, "admin_audit_unavailable", "Account reads need the audit log, which is unavailable.")
        return
    try:
        repository.record_event(action, actor_key=_actor(admin), entity_type=entity_type, entity_id=entity_id,
                                payload=dict(payload or {}))
    except Exception as exc:  # noqa: BLE001 - reported below, never swallowed for required reads
        _logger.warning("admin console: audit record failed for %s", action, exc_info=True)
        if required:
            raise orena_http_error(503, "admin_audit_unavailable", "Account reads need the audit log, which is unavailable.") from exc


def _vocabulary_available() -> bool:
    repository = _state.vocabulary_repository
    try:
        return bool(repository is not None and repository.available())
    except Exception:  # noqa: BLE001 - an unreadable schema is unavailable, not a crash
        return False


def _shared_media() -> tuple[list[Any], str]:
    store = _state.media_store
    if store is None:
        return [], "unavailable"
    try:
        entries = store.list(language=None, library="shared")
    except Exception:  # noqa: BLE001 - a broken index is reported, not raised
        return [], "index_unreadable"
    return list(entries), str(getattr(store, "last_read_issue", "") or "")


def _curated_lessons() -> tuple[Any, ...]:
    from writing_coach.listening_catalog import CATALOG

    return CATALOG


# -- AI facts --------------------------------------------------------------------


def _runtime_mode() -> str:
    from writing_coach.ai.platform import runtime_mode

    try:
        return runtime_mode().value
    except Exception:  # noqa: BLE001 - an invalid AI_RUNTIME_MODE is itself a fact
        return "invalid"


def _provider_state() -> dict[str, dict[str, Any]]:
    """Configured or not, per provider - from env and the encrypted store.

    Builds provider objects exactly as the platform does, which reads
    configuration and never contacts a provider. A stored credential that can
    no longer be decrypted is reported, because the platform silently skips it.
    """
    from writing_coach.ai.credentials import ProviderCredentialStoreError, decrypt_credentials
    from writing_coach.ai.providers import build_providers, provider_definitions

    stored: dict[str, dict[str, Any]] = {}
    unreadable: set[str] = set()
    repository = _state.platform_repository
    for definition in provider_definitions():
        try:
            envelope = repository.get_provider_credential(definition.id) if repository is not None else None
        except Exception:  # noqa: BLE001
            envelope = None
        if not envelope:
            continue
        try:
            stored[definition.id] = decrypt_credentials(definition.id, envelope)
        except ProviderCredentialStoreError:
            unreadable.add(definition.id)
    runtimes = build_providers(stored)
    return {
        definition.id: {
            "configured": bool(getattr(runtimes.get(definition.id), "configured", False)),
            "credential_unreadable": definition.id in unreadable,
        }
        for definition in provider_definitions()
    }


def _ai_facts() -> dict[str, Any]:
    from writing_coach.ai.control_plane import AIControlPlane

    repository = _state.platform_repository
    inspected: dict[str, Any] = {"capabilities": [], "providers": []}
    operations: dict[str, Any] = {"available": False, "by_capability": [], "recent": []}
    if repository is not None:
        plane = AIControlPlane(repository)
        try:
            inspected = plane.inspect()
        except Exception:  # noqa: BLE001
            _logger.warning("admin console: capability inspection failed", exc_info=True)
        try:
            operations = plane.operations(limit=500)
        except Exception:  # noqa: BLE001
            _logger.warning("admin console: operation telemetry unreadable", exc_info=True)
    return {
        "capabilities": inspected.get("capabilities") or [],
        "operations": operations,
        "providers": _provider_state(),
        "runtime_mode": _runtime_mode(),
    }


def _ai_summary(facts: Mapping[str, Any]) -> dict[str, Any]:
    from writing_coach.ai.providers import provider_definitions

    capabilities = facts["capabilities"]
    configurable = [c for c in capabilities if c.get("implemented") and c.get("provider_backed") and c.get("configurable")]
    configured = [c for c in configurable if c.get("explicit_config_exists")]
    enabled = [c for c in configured if (c.get("config") or {}).get("enabled") is not False]
    health: dict[str, int] = defaultdict(int)
    seen = set()
    for row in facts["operations"].get("by_capability") or []:
        health[str(row.get("health_state") or "no_data")] += 1
        seen.add(row.get("capability"))
    health["no_data"] += sum(1 for c in configurable if c.get("key") not in seen)
    providers = facts["providers"]
    return {
        "runtime_mode": facts["runtime_mode"],
        "capabilities": {
            "total": len(capabilities),
            "configurable": len(configurable),
            "configured": len(configured),
            "enabled": len(enabled),
            "deterministic": sum(1 for c in capabilities if c.get("implemented") and not c.get("provider_backed")),
            "reserved": sum(1 for c in capabilities if not c.get("implemented")),
        },
        "providers": {
            "total": len(providers),
            "configured": sum(1 for state in providers.values() if state.get("configured")),
        },
        "health": dict(health),
        "operations_available": bool(facts["operations"].get("available")),
        "provider_names": {definition.id: definition.name for definition in provider_definitions()},
    }


def _learner_impact_failures(operations: Mapping[str, Any]) -> int:
    from writing_coach.product_activity import aggregate_learner_impact_failures

    try:
        impact = aggregate_learner_impact_failures(operations, window_days=7)
    except Exception:  # noqa: BLE001
        return 0
    return sum(int(row.get("failure_count") or 0) for row in impact.get("by_capability") or [])


# -- accounts and activity ---------------------------------------------------------


def _accounts_block(now: datetime, days: int) -> dict[str, Any]:
    repository = _state.repository
    if repository is None:
        return {"available": False}
    totals = repository.account_totals(now=now)
    start = _day_start(now.date() - timedelta(days=days - 1))
    return {
        "available": True,
        **totals,
        "window_days": days,
        "registrations": daily_series(repository.registrations_by_day(start), days, now=now),
    }


def _activity_block(now: datetime, days: int = TREND_DAYS) -> dict[str, Any]:
    repository = _state.repository
    if repository is None:
        return {"available": False}
    today = now.date()
    start = _day_start(today - timedelta(days=days - 1))
    week_start = _day_start(today - timedelta(days=6))
    rows = repository.activity_rows(start)
    first = repository.first_activity_by_user()
    daily_learners: dict[str, set[str]] = defaultdict(set)
    daily_events: dict[str, int] = defaultdict(int)
    domain_events: dict[str, int] = defaultdict(int)
    domain_learners: dict[str, set[str]] = defaultdict(set)
    language_learners: dict[str, set[str]] = defaultdict(set)
    active: set[str] = set()
    active_week: set[str] = set()
    week_key = week_start.date().isoformat()
    for row in rows:
        learner, day = row["user_id"], row["day"]
        daily_learners[day].add(learner)
        daily_events[day] += row["events"]
        domain_events[row["domain"]] += row["events"]
        domain_learners[row["domain"]].add(learner)
        if row.get("language"):
            language_learners[row["language"]].add(learner)
        active.add(learner)
        if day >= week_key:
            active_week.add(learner)
    week = learner_segments(first, active_week, week_start)
    window = learner_segments(first, active, start)
    return {
        "available": True,
        "window_days": days,
        "timezone": "UTC",
        "active_7d": len(active_week),
        "active_30d": len(active),
        "new_7d": week["new"],
        "returning_7d": week["returning"],
        "segments": window,
        "events": sum(daily_events.values()),
        "daily": [
            {"date": key, "learners": len(daily_learners.get(key, ())), "events": daily_events.get(key, 0)}
            for key in day_keys(days, now=now)
        ],
        "domains": [
            {"domain": name, "events": domain_events.get(name, 0), "learners": len(domain_learners.get(name, ()))}
            for name in ACTIVITY_DOMAINS
        ],
        "languages": sorted(
            ({"language": code, "learners": len(learners)} for code, learners in language_learners.items()),
            key=lambda item: (-item["learners"], item["language"]),
        ),
    }


# -- content and imports -------------------------------------------------------------


def _content_records() -> tuple[list[dict[str, Any]], dict[str, str]]:
    records: list[dict[str, Any]] = []
    sources: dict[str, str] = {}
    repository = _state.repository
    books = repository.list_books() if repository is not None else None
    sources["book"] = "ok" if books is not None else "unavailable"
    records.extend(book_record(book) for book in books or [])

    entries, issue = _shared_media()
    sources["media"] = "ok" if issue in {"", "index_missing"} else issue
    records.extend(media_record(entry) for entry in entries)
    records.extend(curated_media_record(lesson) for lesson in _curated_lessons())

    if repository is not None and _vocabulary_available():
        sources["vocabulary"] = "ok"
        records.extend(vocabulary_record(collection) for collection in repository.list_vocabulary_collections())
    else:
        sources["vocabulary"] = "unavailable"
    return records, sources


def _content_summary(records: list[dict[str, Any]], sources: Mapping[str, str]) -> dict[str, Any]:
    def count(kind: str, **where: Any) -> int:
        return sum(1 for r in records if r["kind"] == kind and all(r.get(k) == v for k, v in where.items()))

    return {
        "sources": dict(sources),
        "published": sum(1 for record in records if record["status"] == "published"),
        "book": {"published": count("book", status="published"), "archived": count("book", status="archived")},
        "media": {
            "published": count("media", status="published"),
            "curated": count("media", origin="curated"),
            "imported": count("media", origin="imported"),
            "transcript_missing": transcript_attention_count(records),
        },
        "vocabulary": {"published": count("vocabulary", status="published"), "draft": count("vocabulary", status="draft")},
    }


def _history() -> list[dict[str, Any]] | None:
    repository = _state.repository
    if repository is None:
        return None
    receipts = repository.list_events(("admin.import",), limit=2000)
    vocabulary = repository.list_vocabulary_imports() if _vocabulary_available() else []
    books = repository.list_books() or []
    entries, _issue = _shared_media()
    return history_rows(receipts=receipts, vocabulary_imports=vocabulary, books=books, media_entries=entries)


def _receipt(admin: Mapping[str, Any], kind: str, payload: Mapping[str, Any], *, content_id: str = "") -> None:
    _audit(admin, "admin.import", entity_type=kind, entity_id=content_id, payload={"kind": kind, **payload})


def _media_receipt(admin: Mapping[str, Any], row: dict[str, Any], language: str) -> None:
    """Record one media import attempt, and answer the row with what was stored.

    A provider preview can know a transcript exists without having counted it,
    so the stored entry is read once here and its transcript facts go to both
    the receipt and the live row - the queue and the history cannot disagree.
    """
    content_id = str(row.get("media_id") or "")
    entry = _state.media_store.get(content_id) if content_id and _state.media_store is not None else None
    lesson = entry.lesson if entry is not None and isinstance(entry.lesson, Mapping) else {}
    segments = ((lesson.get("payload") or {}).get("transcript") or {}).get("segments") or []
    stored = row.get("status") == "ok" and entry is not None
    if stored:
        row.update({"has_transcript": bool(segments), "segment_count": len(segments)})
    _receipt(admin, "media", {
        "source": str(row.get("url") or ""),
        "language": language,
        "status": "ok" if row.get("status") == "ok" else "error",
        "detail": "" if row.get("status") == "ok" else str(row.get("detail") or ""),
        "title": entry.title if entry is not None else "",
        "has_transcript": bool(segments),
        "segment_count": len(segments),
    }, content_id=content_id)


def _error_category(exc: HTTPException, fallback: str) -> str:
    detail = exc.detail if isinstance(exc.detail, Mapping) else {}
    return str(detail.get("category") or fallback)


# -- read routes --------------------------------------------------------------------


@router.get("/overview")
def overview(request: Request, response: Response) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    now = _now()
    accounts = _accounts_block(now, TREND_DAYS)
    activity = _activity_block(now)
    repository = _state.repository
    languages = (
        {"available": True, "profiles": repository.language_profiles(), "active_30d": activity.get("languages", [])}
        if repository is not None else {"available": False}
    )
    records, sources = _content_records()
    content = _content_summary(records, sources)
    history = _history()
    week_ago = (now - timedelta(days=7)).isoformat()
    imports = (
        {
            "available": True,
            "failed_7d": recent_failures(history, since=week_ago),
            "last_import_at": max((str(row.get("created_at") or "") for row in history), default="") or None,
            "total": len(history),
        }
        if history is not None else {"available": False}
    )
    facts = _ai_facts()
    _entries, media_issue = _shared_media()
    runtime = dict(_state.runtime_facts() if callable(_state.runtime_facts) else {})
    attention = needs_attention(
        capabilities=facts["capabilities"],
        provider_state=facts["providers"],
        operations=facts["operations"],
        runtime_mode=facts["runtime_mode"],
        import_failures=imports.get("failed_7d", 0) if imports.get("available") else 0,
        transcript_missing=content["media"]["transcript_missing"],
        content_waiting=content["vocabulary"]["draft"],
        runtime={
            "persistence_backend": _state.backend,
            "account_backbone": runtime.get("account_backbone"),
            "media_index_issue": media_issue,
            "reading_library": sources.get("book"),
            "vocabulary": sources.get("vocabulary"),
            "learner_impact_failures": _learner_impact_failures(facts["operations"]),
        },
        legacy_route=_legacy_selection(facts["providers"]),
    )
    return {
        "generated_at": now.isoformat(),
        "accounts": accounts,
        "activity": activity,
        "languages": languages,
        "content": content,
        "imports": imports,
        "ai": _ai_summary(facts),
        "attention": attention,
    }


@router.get("/users/summary")
def users_summary(request: Request, response: Response, days: int = TREND_DAYS) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    repository = _state.repository
    if repository is None:
        return {"available": False}
    now = _now()
    window = max(7, min(int(days or TREND_DAYS), 90))
    activity = _activity_block(now, window)
    floor = _day_start(now.date() - timedelta(days=RETENTION_COHORT_DAYS))
    first = repository.first_activity_by_user()
    _first_seen, active_days = activity_days((row["user_id"], row["day"]) for row in repository.activity_rows(floor))
    first_days = {learner: stamp.date() for learner, stamp in first.items()}
    return {
        "available": True,
        "window_days": window,
        "accounts": _accounts_block(now, window),
        "activity": activity,
        "segments_30d": activity["segments"] if window == TREND_DAYS else learner_segments(
            first, {row["user_id"] for row in repository.activity_rows(_day_start(now.date() - timedelta(days=TREND_DAYS - 1)))},
            _day_start(now.date() - timedelta(days=TREND_DAYS - 1)),
        ),
        "retention": retention_windows(first_days, active_days, today=now.date(), cohort_days=RETENTION_COHORT_DAYS),
        "retention_cohort_days": RETENTION_COHORT_DAYS,
        # A declared level has no stored field (account_profile.py, `stored=False`),
        # and measured proficiency is not a claim the product makes.
        "level": {"state": "not_recorded"},
        "languages": {"profiles": repository.language_profiles(), "active": activity.get("languages", [])},
    }


@router.get("/users")
def users(
    request: Request,
    response: Response,
    q: str = "",
    language: str = "",
    role: str = "",
    activity: str = "",
    sort: str = "joined",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    repository = _state.repository
    if repository is None:
        return {"available": False, "items": [], "total": 0}
    page = repository.list_accounts(
        now=_now(), query=q[:120], language=language[:12], role=role, activity=activity, sort=sort,
        limit=limit, offset=offset,
    )
    # The search text itself may be an address, so the record keeps only that a
    # search ran, never what was typed.
    _audit(admin, "admin.accounts.list", entity_type="account", required=True, payload={
        "filters": {"query": bool(q.strip()), "language": language or None, "role": role or None,
                    "activity": activity or None, "sort": sort},
        "results": page["total"],
    })
    return {"available": True, **page}


@router.get("/users/{user_id}")
def user_detail(user_id: str, request: Request, response: Response) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    repository = _state.repository
    if repository is None:
        raise orena_http_error(503, "admin_accounts_unavailable", "Accounts are not readable on this deployment.")
    detail = repository.account_detail(user_id, now=_now())
    if detail is None:
        raise orena_http_error(404, "account_not_found", "No account has this identifier.")
    _audit(admin, "admin.account.view", entity_type="account", entity_id=detail["id"], required=True,
           payload={"fields": "operational"})
    # No account action has a backend contract yet (no suspension or
    # reactivation state exists; deletion is gated by D-055), so none is offered.
    return {"available": True, **detail, "actions": []}


@router.get("/content")
def content(
    request: Request,
    response: Response,
    kind: str = "",
    q: str = "",
    language: str = "",
    status: str = "",
    sort: str = "updated",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    records, sources = _content_records()
    scoped = filter_records(records, kind=kind)
    selected = filter_records(scoped, query=q[:120], language=language, status=status, sort=sort)
    items, total = paginate(selected, offset=offset, limit=limit)
    return {
        "items": items,
        "total": total,
        "limit": max(1, min(int(limit or 25), 100)),
        "offset": max(0, int(offset or 0)),
        "counts": content_counts(records),
        "status_counts": status_counts(scoped),
        "sources": sources,
    }


def _learner_link(content_id: str, intent: str) -> str:
    return "#/encounter?" + urlencode({"id": content_id, "intent": intent})


def _first_text(values: Any) -> str:
    for item in values if isinstance(values, list) else []:
        text = item.get("text") if isinstance(item, Mapping) else item
        if str(text or "").strip():
            return str(text).strip()
    return ""


@router.get("/content/{kind}/{content_id}")
def content_detail(kind: str, content_id: str, request: Request, response: Response) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    if kind == "book":
        book = _state.repository.get_book(content_id) if _state.repository is not None else None
        if book is None:
            raise orena_http_error(404, "content_not_found", "This book is not in the catalog.")
        record = book_record(book)
        first = (book.get("chapters") or [None])[0]
        return {
            "record": record,
            "book": {"description": book.get("description", ""), "chapters": book.get("chapters", []),
                     "imported_by": book.get("imported_by", "")},
            "learner_link": _learner_link(f"book:{record['id']}/{first['id']}", "reading")
            if first and record["status"] == "published" else None,
        }
    if kind == "media":
        entry = _state.media_store.get(content_id) if _state.media_store is not None else None
        if entry is not None and entry.library == "shared":
            lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
            payload = lesson.get("payload") if isinstance(lesson.get("payload"), Mapping) else {}
            segments = ((payload.get("transcript") or {}).get("segments")) or []
            return {
                "record": media_record(entry),
                "transcript": {
                    "segment_count": len(segments),
                    "segments": [
                        {"start_ms": int(segment.get("start_ms") or 0), "text": str(segment.get("original_text") or "")}
                        for segment in segments[:TRANSCRIPT_PREVIEW_SEGMENTS]
                    ],
                },
                "source": {
                    "url": entry.canonical_url, "provider": entry.provider, "license": entry.source.get("license", ""),
                    "review_status": entry.source.get("review_status", ""), "imported_by": entry.source.get("imported_by", ""),
                },
                "learner_link": _learner_link(f"media:{entry.media_id}", "follow"),
            }
        lesson = next((item for item in _curated_lessons() if item.lesson_id == content_id), None)
        if lesson is None:
            raise orena_http_error(404, "content_not_found", "This media is not in the library.")
        record = curated_media_record(lesson)
        transcript = lesson.media_object.transcript
        segments = [
            segment for segment in (transcript.segments if transcript is not None else ())
            if lesson.excerpt_start_ms <= segment.start_ms < lesson.excerpt_end_ms
        ]
        source = lesson.source
        return {
            "record": record,
            "transcript": {
                "segment_count": len(segments),
                "segments": [{"start_ms": segment.start_ms, "text": segment.original_text}
                             for segment in segments[:TRANSCRIPT_PREVIEW_SEGMENTS]],
            },
            "source": {
                "url": source.source_url, "provider": source.source_provider, "license": source.license_name,
                "review_status": source.rights_review_status, "imported_by": "",
            },
            "learner_link": _learner_link(f"media:{lesson.lesson_id}", "follow") if record["status"] == "published" else None,
        }
    if kind == "vocabulary":
        repository = _state.repository
        collections = repository.list_vocabulary_collections() if repository is not None and _vocabulary_available() else []
        collection = next((item for item in collections if item["id"] == content_id), None)
        if collection is None:
            raise orena_http_error(404, "content_not_found", "This collection is not in the library.")
        entries, total = _state.vocabulary_repository.list_entries(content_id, limit=VOCABULARY_PREVIEW_ENTRIES)
        return {
            "record": vocabulary_record(collection),
            "entries": [
                {
                    "term": entry.get("term") or entry.get("word") or "",
                    "reading": _first_text(entry.get("readings")) or _first_text(entry.get("pronunciations")),
                    "meaning": _first_text(entry.get("short_meanings")),
                    "level": entry.get("level") or "",
                    "part_of_speech": entry.get("part_of_speech") or "",
                }
                for entry in entries
            ],
            "entry_total": int(total),
            "sources": [row for row in repository.list_vocabulary_imports() if row["collection_id"] == content_id],
            "admission": {"rights_status": collection.get("rights_status", ""), "completeness": collection.get("completeness", "")},
            "learner_link": None,
        }
    raise orena_http_error(404, "content_not_found", "Unknown content type.")


@router.get("/imports/history")
def imports_history(
    request: Request, response: Response, kind: str = "", status: str = "", limit: int = 25, offset: int = 0
) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    rows = _history()
    if rows is None:
        return {"available": False, "items": [], "total": 0, "summary": {}}
    selected = filter_history(rows, kind=kind, status=status)
    items, total = paginate(selected, offset=offset, limit=limit)
    week_ago = (_now() - timedelta(days=7)).isoformat()
    return {
        "available": True,
        "items": items,
        "total": total,
        "limit": max(1, min(int(limit or 25), 100)),
        "offset": max(0, int(offset or 0)),
        "summary": {
            "total": len(rows),
            "failed": sum(1 for row in rows if row["status"] == "failed"),
            "failed_7d": recent_failures(rows, since=week_ago),
        },
    }


def _credential_store_state() -> str:
    from writing_coach.ai.credentials import MASTER_KEY_ENV, ProviderCredentialStoreError, _encrypter

    if not os.getenv(MASTER_KEY_ENV, "").strip():
        return "not_configured"
    try:
        _encrypter()
    except ProviderCredentialStoreError:
        return "invalid"
    return "configured"


def _legacy_selection(providers: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """The one route every learner request takes while the runtime is `legacy`.

    Mirrors `ai/platform.py` `active_selection` without contacting anyone: a
    saved selection whose provider is not configured is replaced by the local
    default, so the effective route is reported beside the saved one.
    """
    from writing_coach.ai.control_plane import safe_model_display

    repository = _state.platform_repository
    try:
        row = repository.get_ai_selection() if repository is not None else None
    except Exception:  # noqa: BLE001
        row = None
    default = {"provider": "ollama", "model": safe_model_display(os.getenv("OLLAMA_MODEL", "qwen3:8b"))[0]}
    if row is not None and row.provider:
        states = providers if providers is not None else _provider_state()
        configured = bool(states.get(row.provider, {}).get("configured"))
        saved = {"provider": row.provider, "model": safe_model_display(row.model)[0]}
        return {"source": "saved", **saved, "provider_configured": configured,
                "effective": saved if configured else {**default, "fallback": True}}
    return {"source": "default", **default, "provider_configured": True, "effective": default}


def _health_rules() -> dict[str, int]:
    """The thresholds the control plane applies when it calls a capability degraded.

    Read from the control plane rather than restated, so the console's
    explanation of a health state cannot drift from the rule that set it.
    """
    from writing_coach.ai import control_plane

    return {
        "degraded_latency_ms": int(control_plane._DEGRADED_LATENCY_MS),
        "degraded_failure_rate_percent": int(control_plane._DEGRADED_FAILURE_RATE_PERCENT),
    }


@router.get("/runtime")
def runtime(request: Request, response: Response) -> dict[str, Any]:
    _admin(request)
    _no_store(response)
    facts = dict(_state.runtime_facts() if callable(_state.runtime_facts) else {})
    _entries, media_issue = _shared_media()
    repository = _state.repository
    books = repository.list_books(limit=1) if repository is not None else None
    return {
        "persistence_backend": _state.backend,
        "schema": facts.get("schema") or {"state": "unknown"},
        "account_backbone": facts.get("account_backbone") or "unknown",
        "stores": {
            "media_index": media_issue or "ok",
            "reading_library": "ok" if books is not None else "unavailable",
            "vocabulary": "ok" if _vocabulary_available() else "unavailable",
            "audit_log": "ok" if repository is not None else "unavailable",
        },
        "ai": {
            "learner_runtime_mode": _runtime_mode(),
            "legacy_selection": _legacy_selection(),
            "credential_store": _credential_store_state(),
            "activation": "human_gated",
            "health_rules": _health_rules(),
        },
        "services": [{"id": key, **value} for key, value in _state.runtime_services.items()],
        # Imports run inside the request that starts them; there is no queue.
        "background_jobs": "none",
        # Plans exist in the product model but billing is not enabled anywhere
        # (billing_ready is false), so there is no revenue to report.
        "billing": "not_active",
        "app_version": _state.app_version,
    }


# -- content actions -------------------------------------------------------------------


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rights_status: str = Field(default="", max_length=40)
    completeness: str = Field(default="", max_length=40)
    attested: bool = False


@router.post("/content/book/{book_id}/archive")
def archive_book(book_id: str, request: Request, response: Response) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    import uuid as _uuid

    try:
        _uuid.UUID(book_id)
    except ValueError as exc:
        raise orena_http_error(404, "content_not_found", "This book is not in the catalog.") from exc
    reading = _state.reading_repository
    if reading is None:
        raise orena_http_error(503, "reading_library_unavailable", "The Reading Library is not configured for this deployment.")
    try:
        archived = reading.archive_book(book_id)
    except Exception as exc:  # noqa: BLE001 - schema not ready or database down
        _logger.warning("admin console: archive failed for %s", book_id, exc_info=True)
        raise orena_http_error(503, "reading_library_unavailable", "The Reading Library is not available.") from exc
    if not archived:
        raise orena_http_error(404, "content_not_found", "No published book has this identifier.")
    _audit(admin, "admin.content.archive", entity_type="book", entity_id=book_id)
    return {"archived": True, "id": book_id}


@router.post("/content/vocabulary/{collection_id}/publish")
def publish_collection(collection_id: str, payload: PublishIn, request: Request, response: Response) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    if not payload.attested:
        raise orena_http_error(422, "vocabulary_admission_required",
                               "Confirm source rights and collection readiness before publishing.")
    rights = payload.rights_status.strip().casefold()
    if rights not in PUBLISHABLE_RIGHTS:
        raise orena_http_error(422, "vocabulary_rights_required", "Choose a verified source-rights status before publishing.")
    if payload.completeness.strip().casefold() != "complete":
        raise orena_http_error(422, "vocabulary_completeness_required",
                               "Only a complete, reviewed collection can be published to learners.")
    if not _vocabulary_available():
        raise orena_http_error(503, "vocabulary_schema_unavailable", "Vocabulary content persistence is not active.")
    admission = {
        "rights_status": rights,
        "completeness": "complete",
        "review_status": "approved",
        "publication_attested": True,
        "attested_by": _actor(admin),
    }
    try:
        collection = _state.vocabulary_repository.finalize_collection_publication(collection_id, admission=admission)
    except ValueError as exc:
        raise orena_http_error(422, "vocabulary_publication_refused", str(exc)) from exc
    _audit(admin, "admin.content.publish", entity_type="vocabulary_collection", entity_id=collection_id,
           payload={"rights_status": rights, "completeness": "complete"})
    return {"published": True, "collection": collection}


@router.post("/content/media/{media_id}/reprocess")
def reprocess_media(media_id: str, request: Request, response: Response) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    store = _state.media_store
    entry = store.get(media_id) if store is not None else None
    if entry is None or entry.library != "shared":
        raise orena_http_error(404, "content_not_found", "This media is not in the shared library.")
    if not entry.canonical_url or entry.provider not in {"youtube", "direct"}:
        raise orena_http_error(409, "media_reprocess_unsupported", "Only media imported from a URL can be read again.")
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
    item = media_library_api.MediaImportItemIn(
        url=entry.canonical_url,
        title=entry.title,
        level=entry.level or None,
        topic=str(lesson.get("topic") or "") or None,
        tags=[str(tag) for tag in (lesson.get("tags") or [])][:20],
    )
    result = media_library_api.admin_import(request, media_library_api.MediaImportIn(language=entry.language, items=[item]))
    row = (result.get("items") or [{}])[0]
    _media_receipt(admin, row, entry.language)
    _audit(admin, "admin.content.reprocess", entity_type="media", entity_id=media_id,
           payload={"status": row.get("status", "")})
    refreshed = store.get(media_id)
    return {"item": row, "record": media_record(refreshed) if refreshed is not None else None}


# -- imports ---------------------------------------------------------------------------


@router.post("/imports/books")
async def import_books(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(...),
    learning_language: str = Form(...),
) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    language = learning_language.strip().casefold()
    try:
        result = await reading_library_api.import_books(request, files, learning_language)
    except HTTPException as exc:
        category = _error_category(exc, "request_rejected")
        for upload in files:
            _receipt(admin, "book", {"source": upload.filename or "book.epub", "language": language,
                                     "status": "error", "category": category})
        raise
    for row in result.get("results") or []:
        if row.get("status") == "error":
            row["stage"] = book_error_stage(str(row.get("category") or ""))
        _receipt(admin, "book", {
            "source": str(row.get("filename") or ""),
            "language": language,
            "status": str(row.get("status") or "error"),
            "category": str(row.get("category") or ""),
            "title": str(row.get("title") or ""),
            "chapter_count": int(row.get("chapter_count") or 0),
        }, content_id=str(row.get("book_id") or ""))
    return result


@router.post("/imports/media")
def import_media(payload: media_library_api.MediaImportIn, request: Request, response: Response) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    language = payload.language.strip().casefold()
    try:
        result = media_library_api.admin_import(request, payload)
    except HTTPException as exc:
        category = _error_category(exc, "media_import_unavailable")
        for item in payload.items:
            _receipt(admin, "media", {"source": item.url, "language": language, "status": "error",
                                      "category": category, "detail": ""})
        raise
    for row in result.get("items") or []:
        _media_receipt(admin, row, language)
    return result


@router.post("/imports/media-upload")
async def import_media_upload(
    request: Request,
    response: Response,
    file: list[UploadFile] = File(default=[]),
    language: str = Form(default="en"),
) -> dict[str, Any]:
    admin = _admin(request)
    _no_store(response)
    selected = language.strip().casefold()
    try:
        result = await media_library_api.admin_upload(request, file, language)
    except HTTPException as exc:
        category = _error_category(exc, "media_import_unavailable")
        for upload in file or []:
            _receipt(admin, "media", {"source": upload.filename or "upload", "language": selected, "status": "error",
                                      "category": category, "detail": ""})
        raise
    for row in result.get("items") or []:
        _media_receipt(admin, row, selected)
    return result
