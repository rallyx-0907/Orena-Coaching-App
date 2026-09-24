from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.importer import Discovery, LearningSource
from writing_coach.persistence.models import (
    Essay,
    EssayRevision,
    GrammarProgress,
    SavedWord,
    UserLanguageProfile,
    WritingError,
)


# Reading is not compared: the generated-passage tables are a read-only archive
# (D-075), the legacy SQLite import no longer writes them, and canonical Reading
# evidence has no SQLite source to compare against.
@dataclass(frozen=True)
class ScopeCounts:
    user_key: str
    language_code: str
    profiles: int
    essays: int
    revisions: int
    writing_errors: int
    saved_words: int
    grammar_progress: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _source_scope(source: LearningSource) -> ScopeCounts:
    conn = sqlite3.connect(source.path)
    try:
        conn.row_factory = sqlite3.Row
        errors = 0
        if _table_exists(conn, "essays"):
            rows = conn.execute("SELECT errors_json FROM essays").fetchall()
            import json
            for row in rows:
                try:
                    items = json.loads(row["errors_json"] or "[]")
                except Exception:
                    items = []
                errors += sum(1 for item in items if isinstance(item, dict))
        if _table_exists(conn, "saved_words"):
            saved_words = int(
                conn.execute(
                    "SELECT COUNT(DISTINCT lower(trim(word))) FROM saved_words WHERE trim(word) <> ''"
                ).fetchone()[0]
            )
        else:
            saved_words = 0
        essays = _count(conn, "essays")
        return ScopeCounts(
            user_key=source.user_key,
            language_code=source.language_code,
            profiles=_count(conn, "learner_profile"),
            essays=essays,
            revisions=essays,
            writing_errors=errors,
            saved_words=saved_words,
            grammar_progress=_count(conn, "grammar_progress"),
        )
    finally:
        conn.close()


def _target_scope(engine: Engine, source: LearningSource) -> ScopeCounts:
    uid = stable_uuid("user", source.user_key)
    lang = source.language_code
    with Session(engine) as session:
        essays = int(
            session.scalar(
                select(func.count()).select_from(Essay).where(
                    Essay.user_id == uid, Essay.language_code == lang
                )
            )
            or 0
        )
        profiles = int(
            session.scalar(
                select(func.count()).select_from(UserLanguageProfile).where(
                    UserLanguageProfile.user_id == uid,
                    UserLanguageProfile.language_code == lang,
                )
            )
            or 0
        )
        revisions = int(
            session.scalar(
                select(func.count()).select_from(EssayRevision).where(
                    EssayRevision.user_id == uid,
                    EssayRevision.language_code == lang,
                )
            )
            or 0
        )
        errors = int(
            session.scalar(
                select(func.count())
                .select_from(WritingError)
                .join(Essay, WritingError.essay_id == Essay.id)
                .where(Essay.user_id == uid, Essay.language_code == lang)
            )
            or 0
        )
        saved_words = int(
            session.scalar(
                select(func.count()).select_from(SavedWord).where(
                    SavedWord.user_id == uid, SavedWord.language_code == lang
                )
            )
            or 0
        )
        grammar = int(
            session.scalar(
                select(func.count()).select_from(GrammarProgress).where(
                    GrammarProgress.user_id == uid,
                    GrammarProgress.language_code == lang,
                )
            )
            or 0
        )
    return ScopeCounts(
        user_key=source.user_key,
        language_code=lang,
        profiles=profiles,
        essays=essays,
        revisions=revisions,
        writing_errors=errors,
        saved_words=saved_words,
        grammar_progress=grammar,
    )


def compare_scoped_reads(engine: Engine, discovery: Discovery) -> dict[str, Any]:
    scopes: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    fields = [
        "profiles",
        "essays",
        "revisions",
        "writing_errors",
        "saved_words",
        "grammar_progress",
    ]
    for source in discovery.learning_sources:
        source_counts = _source_scope(source)
        target_counts = _target_scope(engine, source)
        diff = {
            field: {"sqlite": getattr(source_counts, field), "postgres": getattr(target_counts, field)}
            for field in fields
            if getattr(source_counts, field) != getattr(target_counts, field)
        }
        item = {
            "user_key": source.user_key,
            "language_code": source.language_code,
            "kind": source.kind,
            "source": source_counts.as_dict(),
            "target": target_counts.as_dict(),
            "match": not diff,
        }
        scopes.append(item)
        if diff:
            mismatches.append(
                {
                    "user_key": source.user_key,
                    "language_code": source.language_code,
                    "differences": diff,
                }
            )
    return {
        "ok": not mismatches,
        "scope_count": len(scopes),
        "scopes": scopes,
        "mismatches": mismatches,
    }
