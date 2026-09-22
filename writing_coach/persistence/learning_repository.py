from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    Essay, EssayRevision, GrammarProgress, SavedWord, User, WritingError,
)

class LearningRepository(Protocol):
    def get_essay(self, essay_id: int) -> dict[str, Any] | None: ...
    def classify_essay_scope(self, essay_id: int) -> str: ...
    def list_essays(
        self, limit: int = 200, *, ascending: bool = False, kept_only: bool = False
    ) -> list[dict[str, Any]]: ...
    def set_essay_review_kept(self, essay_id: int, kept: bool) -> dict[str, Any] | None: ...
    def list_latest_series(self) -> list[dict[str, Any]]: ...
    def list_series_revisions(self, series_id: int) -> list[dict[str, Any]]: ...
    def previous_revision(self, series_id: int, revision_no: int) -> dict[str, Any] | None: ...
    def next_revision_no(self, series_id: int) -> int: ...
    def create_essay(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def delete_series_for_essay(self, essay_id: int) -> bool: ...
    def completed_grammar_ids(self) -> set[str]: ...
    def grammar_completed(self, lesson_id: str) -> bool: ...
    def set_grammar_completed(self, lesson_id: str, completed_at: str) -> None: ...
    def unset_grammar_completed(self, lesson_id: str) -> bool: ...
    def list_saved_words(self) -> list[dict[str, Any]]: ...
    def upsert_saved_word(self, values: dict[str, Any]) -> None: ...
    def delete_saved_word(self, word: str) -> bool: ...


def _essay_module_data(values: dict[str, Any]) -> dict[str, Any]:
    """What travels in an essay's metadata bag, decided once for both backends.

    The practice it came from, the grammar it touched, and - since reviews
    became reusable - the identity of the review this row *is*: which words,
    which two languages, which level, which evaluator contract. Kept here so
    SQLite and PostgreSQL cannot drift into storing different things.
    """
    module_data: dict[str, Any] = {}
    practice_context = values.get("practice_context")
    grammar_links = values.get("grammar_links") or []
    review_identity = values.get("review_identity") or None
    if practice_context is not None or grammar_links:
        module_data["practice"] = practice_context
        module_data["grammar_links"] = grammar_links
    if review_identity:
        module_data["review"] = review_identity
    return module_data


class LearningCacheRepository(Protocol):
    def get_dictionary(self, word: str) -> dict[str, Any] | None: ...
    def put_dictionary(self, word: str, payload: dict[str, Any], fetched_at: str) -> None: ...
    def get_grammar_lesson(self, lesson_id: str) -> dict[str, Any] | None: ...
    def put_grammar_lesson(self, lesson_id: str, content: dict[str, Any], generated_at: str) -> None: ...


class SQLiteLearningRepository:
    """Authoritative learning store for the current request scope.

    The DB path resolver already isolates one user + one language. SQL is kept
    here so API handlers no longer own persistence statements.
    """

    def __init__(self, path_resolver: Callable[[], Path]) -> None:
        self._path_resolver = path_resolver

    def path(self) -> Path:
        return self._path_resolver()

    def connect(self) -> sqlite3.Connection:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(r["name"]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def initialize(self, *, schema_version: int = 11) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS essays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    text TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    target_cefr TEXT NOT NULL,
                    grammar REAL NOT NULL,
                    vocabulary REAL NOT NULL,
                    coherence REAL NOT NULL,
                    task_achievement REAL NOT NULL,
                    naturalness REAL NOT NULL,
                    overall REAL NOT NULL,
                    cefr_estimate TEXT NOT NULL,
                    evaluator TEXT NOT NULL,
                    summary_vi TEXT NOT NULL,
                    strengths_json TEXT NOT NULL,
                    priorities_json TEXT NOT NULL,
                    errors_json TEXT NOT NULL
                )
                """
            )
            cols = self._column_names(conn, "essays")
            if "series_id" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN series_id INTEGER")
            if "revision_no" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN revision_no INTEGER NOT NULL DEFAULT 1")
            if "parent_id" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN parent_id INTEGER")
            cols = self._column_names(conn, "essays")
            if "language_code" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN language_code TEXT NOT NULL DEFAULT 'en'")
            if "target_level" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN target_level TEXT")
            if "level_estimate" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN level_estimate TEXT")
            if "module_data_json" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN module_data_json TEXT NOT NULL DEFAULT '{}'")
            if "strength_evidence_json" not in cols:
                conn.execute("ALTER TABLE essays ADD COLUMN strength_evidence_json TEXT NOT NULL DEFAULT '[]'")
            if "review_kept_at" not in cols:
                # D-072.1, the same nullable column migration 20260922_0011 adds
                # to PostgreSQL. NULL is "not kept".
                conn.execute("ALTER TABLE essays ADD COLUMN review_kept_at TEXT")
            conn.execute("UPDATE essays SET language_code = 'en' WHERE language_code IS NULL OR language_code = ''")
            conn.execute("UPDATE essays SET target_level = target_cefr WHERE target_level IS NULL OR target_level = ''")
            conn.execute("UPDATE essays SET level_estimate = cefr_estimate WHERE level_estimate IS NULL OR level_estimate = ''")
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_essays_generic_metadata_after_insert
                AFTER INSERT ON essays
                BEGIN
                  UPDATE essays
                  SET
                    language_code = COALESCE(NULLIF(language_code, ''), 'en'),
                    target_level = COALESCE(NULLIF(target_level, ''), NEW.target_cefr),
                    level_estimate = COALESCE(NULLIF(level_estimate, ''), NEW.cefr_estimate),
                    module_data_json = COALESCE(NULLIF(module_data_json, ''), '{}')
                  WHERE id = NEW.id;
                END
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_essays_language_series_revision "
                "ON essays(language_code, series_id, revision_no)"
            )
            conn.execute("UPDATE essays SET series_id = id WHERE series_id IS NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_essays_series_revision ON essays(series_id, revision_no)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_essays_created_at ON essays(created_at)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS saved_words (
                    word TEXT PRIMARY KEY,
                    phonetic TEXT NOT NULL DEFAULT '',
                    part_of_speech TEXT NOT NULL DEFAULT '',
                    definition TEXT NOT NULL DEFAULT '',
                    added_at TEXT NOT NULL
                )"""
            )
            if "translation_vi" not in self._column_names(conn, "saved_words"):
                conn.execute("ALTER TABLE saved_words ADD COLUMN translation_vi TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS grammar_progress (
                    lesson_id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL
                )"""
            )
            conn.execute(f"PRAGMA user_version = {int(schema_version)}")
            conn.commit()

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    def get_essay(self, essay_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM essays WHERE id = ?", (essay_id,)).fetchone())

    def classify_essay_scope(self, essay_id: int) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT language_code FROM essays WHERE id = ?", (essay_id,)).fetchone()
        if row is None:
            return "parent_essay_not_found"
        if str(row["language_code"] or "en").casefold() != current_language_code().casefold():
            return "language_scope_mismatch"
        return "parent_essay_not_found"

    def list_essays(
        self, limit: int = 200, *, ascending: bool = False, kept_only: bool = False
    ) -> list[dict[str, Any]]:
        order = "ASC" if ascending else "DESC"
        where = " WHERE review_kept_at IS NOT NULL" if kept_only else ""
        sql = f"SELECT * FROM essays{where} ORDER BY id {order}"
        params: tuple[Any, ...] = ()
        if limit > 0:
            sql += " LIMIT ?"
            params = (limit,)
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def set_essay_review_kept(self, essay_id: int, kept: bool) -> dict[str, Any] | None:
        """Idempotent: keeping a kept review does not move its timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            row = conn.execute("SELECT review_kept_at FROM essays WHERE id = ?", (essay_id,)).fetchone()
            if row is None:
                return None
            if kept and not row["review_kept_at"]:
                conn.execute("UPDATE essays SET review_kept_at = ? WHERE id = ?", (now, essay_id))
            elif not kept:
                conn.execute("UPDATE essays SET review_kept_at = NULL WHERE id = ?", (essay_id,))
            conn.commit()
            return self._dict(conn.execute("SELECT * FROM essays WHERE id = ?", (essay_id,)).fetchone())

    def list_latest_series(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.*
                FROM essays e
                JOIN (
                    SELECT series_id, MAX(revision_no) AS max_revision
                    FROM essays
                    GROUP BY series_id
                ) latest
                ON e.series_id = latest.series_id
                AND e.revision_no = latest.max_revision
                ORDER BY e.id ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def list_series_revisions(self, series_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, revision_no, overall, created_at FROM essays WHERE series_id = ? ORDER BY revision_no",
                (series_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def previous_revision(self, series_id: int, revision_no: int) -> dict[str, Any] | None:
        if revision_no <= 1:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM essays WHERE series_id = ? AND revision_no = ?",
                (series_id, revision_no - 1),
            ).fetchone()
        return self._dict(row)

    def next_revision_no(self, series_id: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(revision_no), 0) + 1 FROM essays WHERE series_id = ?",
                (series_id,),
            ).fetchone()
        return int(row[0])

    def create_essay(self, values: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO essays (
                  created_at, prompt, text, word_count, target_cefr,
                  grammar, vocabulary, coherence, task_achievement, naturalness,
                  overall, cefr_estimate, evaluator, summary_vi,
                  strengths_json, strength_evidence_json, priorities_json, errors_json,
                  series_id, revision_no, parent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["created_at"], values["prompt"], values["text"], values["word_count"], values["target_cefr"],
                    values["grammar"], values["vocabulary"], values["coherence"], values["task_achievement"], values["naturalness"],
                    values["overall"], values["cefr_estimate"], values["evaluator"], values["summary_vi"],
                    values["strengths_json"], values["strength_evidence_json"], values["priorities_json"], values["errors_json"],
                    values.get("series_id"), values.get("revision_no", 1), values.get("parent_id"),
                ),
            )
            essay_id = int(cur.lastrowid)
            module_data = _essay_module_data(values)
            if module_data:
                conn.execute(
                    "UPDATE essays SET module_data_json = ? WHERE id = ?",
                    (json.dumps(module_data, ensure_ascii=False), essay_id),
                )
            series_id = int(values.get("series_id") or essay_id)
            if values.get("series_id") is None:
                conn.execute("UPDATE essays SET series_id = ? WHERE id = ?", (series_id, essay_id))
            conn.commit()
        return {"id": essay_id, "series_id": series_id, "revision_no": int(values.get("revision_no", 1))}

    def delete_series_for_essay(self, essay_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT series_id FROM essays WHERE id = ?", (essay_id,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM essays WHERE series_id = ?", (row["series_id"],))
            conn.commit()
        return True

    def completed_grammar_ids(self) -> set[str]:
        with self.connect() as conn:
            return {str(r["lesson_id"]) for r in conn.execute("SELECT lesson_id FROM grammar_progress").fetchall()}

    def grammar_completed(self, lesson_id: str) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM grammar_progress WHERE lesson_id = ?", (lesson_id,)).fetchone() is not None

    def set_grammar_completed(self, lesson_id: str, completed_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO grammar_progress(lesson_id, completed_at)
                   VALUES (?, ?)
                   ON CONFLICT(lesson_id) DO UPDATE SET completed_at = excluded.completed_at""",
                (lesson_id, completed_at),
            )
            conn.commit()

    def unset_grammar_completed(self, lesson_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM grammar_progress WHERE lesson_id = ?", (lesson_id,))
            conn.commit()
        return cur.rowcount > 0

    def list_saved_words(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM saved_words ORDER BY added_at DESC").fetchall()]

    def upsert_saved_word(self, values: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO saved_words(word, phonetic, part_of_speech, definition, added_at, translation_vi)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(word) DO UPDATE SET
                     phonetic = excluded.phonetic,
                     part_of_speech = excluded.part_of_speech,
                     definition = excluded.definition,
                     added_at = excluded.added_at,
                     translation_vi = excluded.translation_vi""",
                (
                    values["word"], values.get("phonetic", ""), values.get("part_of_speech", ""),
                    values.get("definition", ""), values["added_at"], values.get("translation_vi", ""),
                ),
            )
            conn.commit()

    def delete_saved_word(self, word: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM saved_words WHERE lower(word) = lower(?)", (word,))
            conn.commit()
        return cur.rowcount > 0


class SQLiteLearningCacheRepository:
    """Non-critical generated caches stay local and are independent from cutover."""

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS dictionary_cache (
                    word TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                # Generated segment meanings. Regenerable by definition, so this
                # lives with the other non-critical caches rather than in the
                # authoritative store: no Alembic migration, no cutover risk.
                #
                # cache_key carries the whole identity - asset, segment, a
                # fingerprint of the source text, the support language and the
                # provider/model - so a canonical text change or a provider
                # change misses rather than serving something stale.
                """CREATE TABLE IF NOT EXISTS media_translation_cache (
                    cache_key TEXT PRIMARY KEY,
                    translated_text TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS grammar_lesson_cache (
                    lesson_id TEXT PRIMARY KEY,
                    content_json TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                )"""
            )
            conn.commit()

    def get_media_translation(self, key: str) -> dict[str, Any] | None:
        """One cached segment meaning, or None when it must be generated."""

        with self._connect() as conn:
            row = conn.execute(
                "SELECT translated_text, provenance FROM media_translation_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return {"translated_text": str(row["translated_text"]), "provenance": str(row["provenance"])}

    def put_media_translation(
        self, key: str, translated_text: str, provenance: str, generated_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO media_translation_cache(
                       cache_key, translated_text, provenance, generated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(cache_key) DO UPDATE SET
                     translated_text = excluded.translated_text,
                     provenance = excluded.provenance,
                     generated_at = excluded.generated_at""",
                (key, translated_text, provenance, generated_at),
            )
            conn.commit()

    def get_dictionary(self, word: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json, fetched_at FROM dictionary_cache WHERE word = ?", (word,)).fetchone()
        if not row:
            return None
        return {"payload_json": str(row["payload_json"]), "fetched_at": str(row["fetched_at"])}

    def put_dictionary(self, word: str, payload: dict[str, Any], fetched_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO dictionary_cache(word, payload_json, fetched_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(word) DO UPDATE SET
                     payload_json = excluded.payload_json,
                     fetched_at = excluded.fetched_at""",
                (word, json.dumps(payload, ensure_ascii=False), fetched_at),
            )
            conn.commit()

    def get_grammar_lesson(self, lesson_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT content_json FROM grammar_lesson_cache WHERE lesson_id = ?", (lesson_id,)).fetchone()
        if not row:
            return None
        try:
            value = json.loads(row["content_json"])
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def put_grammar_lesson(self, lesson_id: str, content: dict[str, Any], generated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO grammar_lesson_cache(lesson_id, content_json, generated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(lesson_id) DO UPDATE SET
                     content_json = excluded.content_json,
                     generated_at = excluded.generated_at""",
                (lesson_id, json.dumps(content, ensure_ascii=False), generated_at),
            )
            conn.commit()


class PostgresLearningRepository:
    """SQLAlchemy implementation of the core learning contract.

    It is deliberately not selected by the application yet. Specialized BECOMING
    services still use their SQLite adapters, so runtime cutover remains blocked.
    """

    def __init__(
        self,
        engine: Engine | None = None,
        *,
        url: str | None = None,
        user_key_provider: Callable[[], str] = current_user_key,
        language_provider: Callable[[], str] = current_language_code,
    ) -> None:
        self.engine = engine or create_shadow_engine(url)
        self._user_key_provider = user_key_provider
        self._language_provider = language_provider

    def _scope(self) -> tuple[Any, str]:
        user_key = self._user_key_provider()
        return stable_uuid("user", user_key), self._language_provider().casefold()

    @staticmethod
    def _dt(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _essay_payload(essay: Essay, revision: EssayRevision | None) -> dict[str, Any]:
        return {
            "id": essay.legacy_id,
            "created_at": essay.created_at.isoformat(),
            "prompt": essay.prompt,
            "text": essay.text,
            "word_count": essay.word_count,
            "target_cefr": essay.target_level,
            "grammar": essay.grammar,
            "vocabulary": essay.vocabulary,
            "coherence": essay.coherence,
            "task_achievement": essay.task_achievement,
            "naturalness": essay.naturalness,
            "overall": essay.overall,
            "cefr_estimate": essay.level_estimate,
            "evaluator": essay.evaluator,
            "summary_vi": essay.summary_vi,
            "strengths_json": json.dumps(essay.strengths, ensure_ascii=False),
            "priorities_json": json.dumps(essay.priorities, ensure_ascii=False),
            "errors_json": json.dumps(essay.errors, ensure_ascii=False),
            "series_id": revision.series_legacy_id if revision else essay.legacy_id,
            "revision_no": revision.revision_no if revision else 1,
            "parent_id": revision.parent_legacy_id if revision else None,
            "language_code": essay.language_code,
            "target_level": essay.target_level,
            "level_estimate": essay.level_estimate,
            "module_data_json": json.dumps(essay.module_data, ensure_ascii=False),
            "strength_evidence_json": json.dumps(essay.strength_evidence, ensure_ascii=False),
            "review_kept_at": essay.review_kept_at.isoformat() if essay.review_kept_at else None,
        }

    def _essay_rows(self, session: Session, *, ascending: bool = True) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        order = Essay.legacy_id.asc() if ascending else Essay.legacy_id.desc()
        essays = session.scalars(select(Essay).where(Essay.user_id == uid, Essay.language_code == lang).order_by(order)).all()
        revs = {
            r.essay_id: r
            for r in session.scalars(select(EssayRevision).where(EssayRevision.user_id == uid, EssayRevision.language_code == lang)).all()
        }
        return [self._essay_payload(e, revs.get(e.id)) for e in essays]

    def get_essay(self, essay_id: int) -> dict[str, Any] | None:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            essay = session.scalar(select(Essay).where(Essay.user_id == uid, Essay.language_code == lang, Essay.legacy_id == essay_id))
            if essay is None:
                return None
            revision = session.scalar(select(EssayRevision).where(EssayRevision.essay_id == essay.id))
            return self._essay_payload(essay, revision)

    def classify_essay_scope(self, essay_id: int) -> str:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            essay = session.scalar(select(Essay).where(Essay.legacy_id == essay_id))
            if essay is None:
                return "parent_essay_not_found"
            if essay.user_id != uid:
                return "essay_scope_mismatch"
            if str(essay.language_code or "").casefold() != lang:
                return "language_scope_mismatch"
            return "parent_essay_not_found"

    def list_essays(
        self, limit: int = 200, *, ascending: bool = False, kept_only: bool = False
    ) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = self._essay_rows(session, ascending=ascending)
        if kept_only:
            rows = [row for row in rows if row.get("review_kept_at")]
        return rows if limit <= 0 else rows[:limit]

    def set_essay_review_kept(self, essay_id: int, kept: bool) -> dict[str, Any] | None:
        """Owner-scoped through the existing `(user_id, language_code, legacy_id)`
        lookup, so the endpoint cannot reach another learner's essay.

        Idempotent: keeping a kept review does not move its timestamp.
        """
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            essay = session.scalar(
                select(Essay).where(
                    Essay.user_id == uid, Essay.language_code == lang, Essay.legacy_id == essay_id
                )
            )
            if essay is None:
                return None
            if kept:
                if essay.review_kept_at is None:
                    essay.review_kept_at = datetime.now(timezone.utc)
            else:
                essay.review_kept_at = None
            revision = session.scalar(select(EssayRevision).where(EssayRevision.essay_id == essay.id))
            session.flush()
            return self._essay_payload(essay, revision)

    def list_latest_series(self) -> list[dict[str, Any]]:
        rows = self.list_essays(0, ascending=True)
        latest: dict[int, dict[str, Any]] = {}
        for row in rows:
            sid = int(row.get("series_id") or row["id"])
            current = latest.get(sid)
            if current is None or int(row.get("revision_no") or 1) > int(current.get("revision_no") or 1):
                latest[sid] = row
        return sorted(latest.values(), key=lambda r: int(r["id"]))

    def list_series_revisions(self, series_id: int) -> list[dict[str, Any]]:
        return [
            {"id": r["id"], "revision_no": r["revision_no"], "overall": r["overall"], "created_at": r["created_at"]}
            for r in self.list_essays(0, ascending=True)
            if int(r.get("series_id") or r["id"]) == series_id
        ]

    def previous_revision(self, series_id: int, revision_no: int) -> dict[str, Any] | None:
        target = revision_no - 1
        if target < 1:
            return None
        for row in self.list_essays(0, ascending=True):
            if int(row.get("series_id") or row["id"]) == series_id and int(row.get("revision_no") or 1) == target:
                return row
        return None

    def next_revision_no(self, series_id: int) -> int:
        values = [
            int(r.get("revision_no") or 1)
            for r in self.list_essays(0, ascending=True)
            if int(r.get("series_id") or r["id"]) == series_id
        ]
        return max(values, default=0) + 1

    def create_essay(self, values: dict[str, Any]) -> dict[str, Any]:
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            user = session.get(User, uid)
            if user is None:
                raise RuntimeError("PostgreSQL learning scope has no user row; shadow/import must run first.")
            max_id = session.scalar(select(func.max(Essay.legacy_id)).where(Essay.user_id == uid, Essay.language_code == lang))
            legacy_id = int(max_id or 0) + 1
            eid = stable_uuid("essay", self._user_key_provider(), lang, legacy_id)
            essay = Essay(
                id=eid, user_id=uid, language_code=lang, legacy_id=legacy_id,
                created_at=self._dt(values["created_at"]), prompt=values["prompt"], text=values["text"],
                word_count=int(values["word_count"]), target_level=values["target_cefr"],
                grammar=float(values["grammar"]), vocabulary=float(values["vocabulary"]), coherence=float(values["coherence"]),
                task_achievement=float(values["task_achievement"]), naturalness=float(values["naturalness"]), overall=float(values["overall"]),
                level_estimate=values["cefr_estimate"], evaluator=values["evaluator"], summary_vi=values["summary_vi"],
                strengths=json.loads(values["strengths_json"]), priorities=json.loads(values["priorities_json"]),
                errors=json.loads(values["errors_json"]), module_data=_essay_module_data(values),
                strength_evidence=json.loads(values["strength_evidence_json"]),
            )
            session.add(essay)
            for ordinal, err in enumerate(essay.errors):
                if not isinstance(err, dict):
                    continue
                confidence = err.get("confidence")
                try:
                    confidence = float(confidence) if confidence is not None else None
                except (TypeError, ValueError):
                    confidence = None
                session.add(WritingError(
                    id=stable_uuid("writing-error", self._user_key_provider(), lang, legacy_id, ordinal),
                    essay_id=eid,
                    ordinal=ordinal,
                    category=str(err.get("category") or "other")[:120],
                    fragment=str(err.get("fragment") or ""),
                    suggestion=str(err.get("suggestion") or ""),
                    explanation_vi=str(err.get("explanation_vi") or ""),
                    mini_rule_vi=str(err.get("mini_rule_vi") or ""),
                    confidence=confidence,
                    payload=err,
                ))
            series_id = int(values.get("series_id") or legacy_id)
            parent_legacy = values.get("parent_id")
            parent_uuid = None
            if parent_legacy:
                parent = session.scalar(select(Essay).where(Essay.user_id == uid, Essay.language_code == lang, Essay.legacy_id == int(parent_legacy)))
                parent_uuid = parent.id if parent else None
            session.add(EssayRevision(
                id=stable_uuid("revision", self._user_key_provider(), lang, legacy_id), essay_id=eid, user_id=uid,
                language_code=lang, series_legacy_id=series_id, revision_no=int(values.get("revision_no", 1)),
                parent_essay_id=parent_uuid, parent_legacy_id=int(parent_legacy) if parent_legacy else None,
            ))
        return {"id": legacy_id, "series_id": series_id, "revision_no": int(values.get("revision_no", 1))}

    def delete_series_for_essay(self, essay_id: int) -> bool:
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            essay = session.scalar(select(Essay).where(Essay.user_id == uid, Essay.language_code == lang, Essay.legacy_id == essay_id))
            if essay is None:
                return False
            rev = session.scalar(select(EssayRevision).where(EssayRevision.essay_id == essay.id))
            series_id = rev.series_legacy_id if rev else essay_id
            revs = session.scalars(select(EssayRevision).where(EssayRevision.user_id == uid, EssayRevision.language_code == lang, EssayRevision.series_legacy_id == series_id)).all()
            ids = [r.essay_id for r in revs]
            for item in session.scalars(select(Essay).where(Essay.id.in_(ids))).all() if ids else [essay]:
                session.delete(item)
        return True

    def completed_grammar_ids(self) -> set[str]:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            return set(session.scalars(select(GrammarProgress.lesson_id).where(GrammarProgress.user_id == uid, GrammarProgress.language_code == lang)).all())

    def grammar_completed(self, lesson_id: str) -> bool:
        return lesson_id in self.completed_grammar_ids()

    def set_grammar_completed(self, lesson_id: str, completed_at: str) -> None:
        uid, lang = self._scope()
        gid = stable_uuid("grammar", self._user_key_provider(), lang, lesson_id)
        with Session(self.engine) as session, session.begin():
            row = session.get(GrammarProgress, gid)
            if row is None:
                session.add(GrammarProgress(id=gid, user_id=uid, language_code=lang, lesson_id=lesson_id, completed_at=self._dt(completed_at)))
            else:
                row.completed_at = self._dt(completed_at)

    def unset_grammar_completed(self, lesson_id: str) -> bool:
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(GrammarProgress).where(GrammarProgress.user_id == uid, GrammarProgress.language_code == lang, GrammarProgress.lesson_id == lesson_id))
            if row is None:
                return False
            session.delete(row)
        return True

    def list_saved_words(self) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            rows = session.scalars(select(SavedWord).where(SavedWord.user_id == uid, SavedWord.language_code == lang).order_by(SavedWord.added_at.desc())).all()
            return [
                {"word": r.word, "phonetic": r.phonetic, "part_of_speech": r.part_of_speech, "definition": r.definition,
                 "added_at": r.added_at.isoformat(), "translation_vi": r.translation_vi}
                for r in rows
            ]

    def upsert_saved_word(self, values: dict[str, Any]) -> None:
        uid, lang = self._scope()
        normalized = str(values["word"]).casefold()
        sid = stable_uuid("saved-word", self._user_key_provider(), lang, normalized)
        with Session(self.engine) as session, session.begin():
            row = session.get(SavedWord, sid)
            when = self._dt(values["added_at"])
            if row is None:
                session.add(SavedWord(
                    id=sid, user_id=uid, language_code=lang, word=values["word"], normalized_word=normalized,
                    phonetic=values.get("phonetic", ""), part_of_speech=values.get("part_of_speech", ""), definition=values.get("definition", ""),
                    translation_vi=values.get("translation_vi", ""), added_at=when, source_essay_id=None, source_fragment="", source_kind="manual",
                    focus_note="", review_stage=0, successful_recalls=0, lapse_count=0, last_reviewed_at=None, next_review_at=None, updated_at=when,
                ))
            else:
                row.word = values["word"]; row.phonetic = values.get("phonetic", ""); row.part_of_speech = values.get("part_of_speech", "")
                row.definition = values.get("definition", ""); row.translation_vi = values.get("translation_vi", "")
                row.added_at = when; row.updated_at = when

    def delete_saved_word(self, word: str) -> bool:
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(SavedWord).where(SavedWord.user_id == uid, SavedWord.language_code == lang, SavedWord.normalized_word == word.casefold()))
            if row is None:
                return False
            session.delete(row)
        return True
