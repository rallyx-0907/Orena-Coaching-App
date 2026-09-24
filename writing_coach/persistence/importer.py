from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.core.storage import user_hash
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    Essay,
    EssayRevision,
    GrammarProgress,
    PlanEntitlement,
    PlanRecord,
    PlatformSetting,
    SavedWord,
    Subscription,
    UsageEvent,
    User,
    UserLanguageProfile,
    WritingError,
)
from writing_coach.product.catalog import PLANS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def _rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    if not _has_table(conn, table):
        return []
    return conn.execute(f'SELECT * FROM "{table}"').fetchall()


@dataclass(frozen=True)
class LearningSource:
    user_key: str
    language_code: str
    path: Path
    kind: str


@dataclass
class Discovery:
    data_root: Path
    auth_users: list[dict[str, Any]] = field(default_factory=list)
    learning_sources: list[LearningSource] = field(default_factory=list)
    orphan_user_dirs: list[str] = field(default_factory=list)
    product_db: Path | None = None
    platform_db: Path | None = None


@dataclass
class ImportStats:
    users: int = 0
    profiles: int = 0
    essays: int = 0
    revisions: int = 0
    writing_errors: int = 0
    saved_words: int = 0
    grammar_progress: int = 0
    subscriptions: int = 0
    usage_events: int = 0
    platform_settings: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


def _sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def discover_sources(data_root: Path) -> Discovery:
    data_root = data_root.resolve()
    result = Discovery(data_root=data_root)

    auth_db = data_root / "auth.db"
    if auth_db.is_file():
        with _sqlite(auth_db) as conn:
            if _has_table(conn, "users"):
                result.auth_users = [dict(row) for row in conn.execute("SELECT * FROM users")]

    known_hashes: set[str] = set()
    for user in result.auth_users:
        key = str(user.get("google_sub") or "").strip()
        if not key:
            continue
        h = user_hash(key)
        known_hashes.add(h)
        base = data_root / "users" / h
        canonical_en = base / "en" / "writing.db"
        for db_path in sorted(base.glob("*/writing.db")) if base.exists() else []:
            lang = db_path.parent.name.casefold()
            result.learning_sources.append(LearningSource(key, lang, db_path, "authenticated"))
        legacy_user_db = base / "writing.db"
        if legacy_user_db.is_file() and not canonical_en.is_file():
            result.learning_sources.append(LearningSource(key, "en", legacy_user_db, "authenticated-v08"))

    users_root = data_root / "users"
    if users_root.exists():
        for child in users_root.iterdir():
            if child.is_dir() and child.name not in known_hashes:
                result.orphan_user_dirs.append(child.name)

    legacy = data_root / "writing.db"
    if legacy.is_file():
        result.learning_sources.append(LearningSource("legacy", "en", legacy, "legacy"))
    legacy_languages = data_root / "languages"
    if legacy_languages.exists():
        for db_path in sorted(legacy_languages.glob("*/writing.db")):
            result.learning_sources.append(
                LearningSource("legacy", db_path.parent.name.casefold(), db_path, "legacy-language")
            )

    result.product_db = (data_root / "product.db") if (data_root / "product.db").is_file() else None
    result.platform_db = (data_root / "platform.db") if (data_root / "platform.db").is_file() else None

    # Canonicalize duplicate source paths/scopes while preserving discovery order.
    dedup: list[LearningSource] = []
    seen: set[tuple[str, str, str]] = set()
    for item in result.learning_sources:
        key = (item.user_key, item.language_code, str(item.path.resolve()))
        if key not in seen:
            seen.add(key)
            dedup.append(item)
    result.learning_sources = dedup
    return result


def source_counts(discovery: Discovery) -> ImportStats:
    stats = ImportStats(users=len(discovery.auth_users))
    if any(s.user_key == "legacy" for s in discovery.learning_sources):
        stats.users += 1

    for source in discovery.learning_sources:
        with _sqlite(source.path) as conn:
            stats.profiles += len(_rows(conn, "learner_profile"))
            essay_rows = _rows(conn, "essays")
            stats.essays += len(essay_rows)
            stats.revisions += len(essay_rows)
            for row in essay_rows:
                stats.writing_errors += sum(1 for item in _json(row["errors_json"] if "errors_json" in row.keys() else "[]", []) if isinstance(item, dict))
            stats.saved_words += len(_rows(conn, "saved_words"))
            stats.grammar_progress += len(_rows(conn, "grammar_progress"))

    if discovery.product_db:
        with _sqlite(discovery.product_db) as conn:
            stats.subscriptions += len(_rows(conn, "subscriptions"))
            stats.usage_events += len(_rows(conn, "usage_events"))
    if discovery.platform_db:
        with _sqlite(discovery.platform_db) as conn:
            stats.platform_settings += len(_rows(conn, "platform_ai_config"))
    return stats


def _ensure_user(session: Session, user_key: str, details: dict[str, Any] | None = None) -> User:
    uid = stable_uuid("user", user_key)
    item = session.get(User, uid)
    details = details or {}
    if item is None:
        created = _dt(details.get("created_at"), fallback=_now()) or _now()
        item = User(
            id=uid,
            user_key=user_key,
            email=str(details.get("email") or ""),
            name=str(details.get("name") or ""),
            picture=str(details.get("picture") or ""),
            role=str(details.get("role") or "user"),
            created_at=created,
            last_login=_dt(details.get("last_login")),
        )
        session.add(item)
        session.flush()
    return item


def _seed_catalog(session: Session) -> None:
    for plan in PLANS.values():
        row = session.get(PlanRecord, plan.id)
        if row is None:
            row = PlanRecord(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                price_label=plan.price_label,
                active=True,
            )
            session.add(row)
        else:
            row.name = plan.name
            row.description = plan.description
            row.price_label = plan.price_label
            row.active = True
        for entitlement in plan.entitlements:
            eid = stable_uuid("entitlement", plan.id, entitlement.key)
            item = session.get(PlanEntitlement, eid)
            if item is None:
                session.add(
                    PlanEntitlement(
                        id=eid,
                        plan_id=plan.id,
                        feature_key=entitlement.key,
                        enabled=entitlement.enabled,
                        monthly_limit=entitlement.monthly_limit,
                    )
                )
            else:
                item.enabled = entitlement.enabled
                item.monthly_limit = entitlement.monthly_limit


def import_to_engine(engine: Engine, discovery: Discovery) -> ImportStats:
    stats = ImportStats()
    auth_by_key = {
        str(item.get("google_sub") or ""): item
        for item in discovery.auth_users
        if item.get("google_sub")
    }

    with Session(engine) as session, session.begin():
        _seed_catalog(session)
        for key, details in auth_by_key.items():
            _ensure_user(session, key, details)
        if any(source.user_key == "legacy" for source in discovery.learning_sources):
            _ensure_user(session, "legacy", {"name": "Legacy local learner"})

        for source in discovery.learning_sources:
            user = _ensure_user(session, source.user_key, auth_by_key.get(source.user_key))
            lang = source.language_code
            with _sqlite(source.path) as conn:
                profiles = _rows(conn, "learner_profile")
                for row in profiles:
                    pid = stable_uuid("profile", source.user_key, lang)
                    item = session.get(UserLanguageProfile, pid)
                    created = _dt(row["created_at"] if "created_at" in row.keys() else None, fallback=_now()) or _now()
                    updated = _dt(row["updated_at"] if "updated_at" in row.keys() else None, fallback=created) or created
                    values = dict(
                        user_id=user.id,
                        language_code=lang,
                        goal=str(row["goal"] or "everyday"),
                        style=str(row["style"] or "guided"),
                        pinyin=str(row["pinyin"] or "auto"),
                        native_language=str((row["native_language"] if "native_language" in row.keys() else "vi") or "vi"),
                        theme_preset=str((row["theme_preset"] if "theme_preset" in row.keys() else "editorial") or "editorial"),
                        created_at=created,
                        updated_at=updated,
                    )
                    if item is None:
                        session.add(UserLanguageProfile(id=pid, **values))
                    else:
                        for k, v in values.items(): setattr(item, k, v)

                essays = _rows(conn, "essays")
                essay_id_map: dict[int, Any] = {}
                for row in essays:
                    legacy_id = int(row["id"])
                    eid = stable_uuid("essay", source.user_key, lang, legacy_id)
                    essay_id_map[legacy_id] = eid
                    item = session.get(Essay, eid)
                    values = dict(
                        user_id=user.id,
                        # One SQLite DB is already scoped to exactly one user + language.
                        # Older rows may still contain the historical default "en" even
                        # inside a canonical zh/writing.db. The source scope is authoritative.
                        language_code=lang,
                        legacy_id=legacy_id,
                        created_at=_dt(row["created_at"], fallback=_now()) or _now(),
                        prompt=str(row["prompt"] or ""),
                        text=str(row["text"] or ""),
                        word_count=int(row["word_count"] or 0),
                        target_level=str((row["target_level"] if "target_level" in row.keys() else None) or row["target_cefr"] or ""),
                        grammar=float(row["grammar"] or 0),
                        vocabulary=float(row["vocabulary"] or 0),
                        coherence=float(row["coherence"] or 0),
                        task_achievement=float(row["task_achievement"] or 0),
                        naturalness=float(row["naturalness"] or 0),
                        overall=float(row["overall"] or 0),
                        level_estimate=str((row["level_estimate"] if "level_estimate" in row.keys() else None) or row["cefr_estimate"] or ""),
                        evaluator=str(row["evaluator"] or ""),
                        summary_vi=str(row["summary_vi"] or ""),
                        strengths=_json(row["strengths_json"], []),
                        priorities=_json(row["priorities_json"], []),
                        errors=_json(row["errors_json"], []),
                        module_data=_json(row["module_data_json"] if "module_data_json" in row.keys() else "{}", {}),
                        strength_evidence=_json(row["strength_evidence_json"] if "strength_evidence_json" in row.keys() else "[]", []),
                    )
                    if item is None:
                        session.add(Essay(id=eid, **values))
                    else:
                        for k, v in values.items(): setattr(item, k, v)

                    for ordinal, err in enumerate(values["errors"]):
                        if not isinstance(err, dict):
                            continue
                        wid = stable_uuid("writing-error", source.user_key, lang, legacy_id, ordinal)
                        w = session.get(WritingError, wid)
                        confidence = err.get("confidence")
                        try: confidence = float(confidence) if confidence is not None else None
                        except Exception: confidence = None
                        ev = dict(
                            essay_id=eid,
                            ordinal=ordinal,
                            category=str(err.get("category") or "other")[:120],
                            fragment=str(err.get("fragment") or ""),
                            suggestion=str(err.get("suggestion") or ""),
                            explanation_vi=str(err.get("explanation_vi") or ""),
                            mini_rule_vi=str(err.get("mini_rule_vi") or ""),
                            confidence=confidence,
                            payload=err,
                        )
                        if w is None: session.add(WritingError(id=wid, **ev))
                        else:
                            for k,v in ev.items(): setattr(w,k,v)

                session.flush()
                for row in essays:
                    legacy_id=int(row["id"])
                    eid=essay_id_map[legacy_id]
                    rid=stable_uuid("revision", source.user_key, lang, legacy_id)
                    item=session.get(EssayRevision,rid)
                    parent_legacy = int(row["parent_id"]) if "parent_id" in row.keys() and row["parent_id"] is not None else None
                    series_legacy = int(row["series_id"] or legacy_id) if "series_id" in row.keys() else legacy_id
                    values=dict(
                        essay_id=eid,
                        user_id=user.id,
                        language_code=lang,
                        series_legacy_id=series_legacy,
                        revision_no=int(row["revision_no"] or 1) if "revision_no" in row.keys() else 1,
                        parent_essay_id=essay_id_map.get(parent_legacy) if parent_legacy else None,
                        parent_legacy_id=parent_legacy,
                    )
                    if item is None: session.add(EssayRevision(id=rid, **values))
                    else:
                        for k,v in values.items(): setattr(item,k,v)

                learning_by_word = {}
                for row in _rows(conn, "vocabulary_learning"):
                    learning_by_word[str(row["word"] or "").casefold()] = row
                for row in _rows(conn, "saved_words"):
                    word=str(row["word"] or "").strip()
                    if not word: continue
                    normalized=word.casefold()
                    learning=learning_by_word.get(normalized)
                    source_legacy = int(learning["source_essay_id"]) if learning is not None and learning["source_essay_id"] is not None else None
                    sid=stable_uuid("saved-word", source.user_key, lang, normalized)
                    item=session.get(SavedWord,sid)
                    added=_dt(row["added_at"], fallback=_now()) or _now()
                    updated=_dt(learning["updated_at"] if learning is not None else None, fallback=added) or added
                    values=dict(
                        user_id=user.id,
                        language_code=lang,
                        word=word,
                        normalized_word=normalized,
                        phonetic=str(row["phonetic"] or ""),
                        part_of_speech=str(row["part_of_speech"] or ""),
                        definition=str(row["definition"] or ""),
                        translation_vi=str((row["translation_vi"] if "translation_vi" in row.keys() else "") or ""),
                        added_at=added,
                        source_essay_id=essay_id_map.get(source_legacy) if source_legacy else None,
                        source_fragment=str((learning["source_fragment"] if learning is not None else "") or ""),
                        source_kind=str((learning["source_kind"] if learning is not None else "manual") or "manual"),
                        focus_note=str((learning["focus_note"] if learning is not None else "") or ""),
                        review_stage=int((learning["review_stage"] if learning is not None else 0) or 0),
                        successful_recalls=int((learning["successful_recalls"] if learning is not None else 0) or 0),
                        lapse_count=int((learning["lapse_count"] if learning is not None else 0) or 0),
                        last_reviewed_at=_dt(learning["last_reviewed_at"] if learning is not None else None),
                        next_review_at=_dt(learning["next_review_at"] if learning is not None else None),
                        updated_at=updated,
                    )
                    if item is None: session.add(SavedWord(id=sid, **values))
                    else:
                        for k,v in values.items(): setattr(item,k,v)

                for row in _rows(conn, "grammar_progress"):
                    lesson=str(row["lesson_id"] or "")
                    gid=stable_uuid("grammar", source.user_key, lang, lesson)
                    item=session.get(GrammarProgress,gid)
                    values=dict(
                        user_id=user.id,
                        language_code=lang,
                        lesson_id=lesson,
                        completed_at=_dt(row["completed_at"], fallback=_now()) or _now(),
                    )
                    if item is None: session.add(GrammarProgress(id=gid, **values))
                    else:
                        for k,v in values.items(): setattr(item,k,v)

                # Legacy generated-reading rows are not imported: that flow is
                # retired (D-075) and its PostgreSQL tables are a read-only
                # archive. Canonical Reading evidence has no SQLite source.

        if discovery.product_db:
            with _sqlite(discovery.product_db) as conn:
                for row in _rows(conn,"subscriptions"):
                    key=str(row["user_key"] or "")
                    user=_ensure_user(session,key,auth_by_key.get(key))
                    sid=stable_uuid("subscription",key)
                    item=session.get(Subscription,sid)
                    values=dict(
                        user_id=user.id,
                        plan_id=str(row["plan_id"] or "free"),
                        status=str(row["status"] or "active"),
                        provider=str(row["provider"] or ""),
                        external_customer_id=str(row["external_customer_id"] or ""),
                        external_subscription_id=str(row["external_subscription_id"] or ""),
                        current_period_end=_dt(row["current_period_end"]),
                        updated_at=_dt(row["updated_at"],fallback=_now()) or _now(),
                    )
                    if item is None: session.add(Subscription(id=sid,**values))
                    else:
                        for k,v in values.items(): setattr(item,k,v)
                for row in _rows(conn,"usage_events"):
                    key=str(row["user_key"] or "")
                    user=_ensure_user(session,key,auth_by_key.get(key))
                    legacy_id=int(row["id"])
                    uid=stable_uuid("usage-legacy",key,legacy_id)
                    item=session.get(UsageEvent,uid)
                    values=dict(
                        user_id=user.id,
                        feature=str(row["feature"] or ""),
                        amount=int(row["amount"] or 0),
                        request_id=str(row["request_id"] or ""),
                        occurred_at=_dt(row["occurred_at"],fallback=_now()) or _now(),
                    )
                    if item is None: session.add(UsageEvent(id=uid,**values))
                    else:
                        for k,v in values.items(): setattr(item,k,v)

        if discovery.platform_db:
            with _sqlite(discovery.platform_db) as conn:
                rows=_rows(conn,"platform_ai_config")
                for row in rows:
                    key="ai.active_selection"
                    item=session.get(PlatformSetting,key)
                    updated=_dt(row["updated_at"],fallback=_now()) or _now()
                    value={"provider":str(row["provider"] or ""),"model":str(row["model"] or "")}
                    if item is None:
                        session.add(PlatformSetting(key=key,value=value,updated_at=updated,updated_by=str(row["updated_by_sub"] or "")))
                    else:
                        item.value=value; item.updated_at=updated; item.updated_by=str(row["updated_by_sub"] or "")

    return target_counts(engine)


def target_counts(engine: Engine) -> ImportStats:
    mapping = {
        "users": User,
        "profiles": UserLanguageProfile,
        "essays": Essay,
        "revisions": EssayRevision,
        "writing_errors": WritingError,
        "saved_words": SavedWord,
        "grammar_progress": GrammarProgress,
        "subscriptions": Subscription,
        "usage_events": UsageEvent,
        "platform_settings": PlatformSetting,
    }
    values = {}
    with Session(engine) as session:
        for key, model in mapping.items():
            values[key] = int(session.scalar(select(func.count()).select_from(model)) or 0)
    return ImportStats(**values)
