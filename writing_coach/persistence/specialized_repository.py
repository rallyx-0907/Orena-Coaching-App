from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    Essay,
    EssayRevision,
    ReadingAttempt,
    ReadingSession,
    ListeningProgress,
    ShadowingProgress,
    SavedWord,
    SpeakingAttempt,
    User,
    UserLanguageProfile,
)


class SpecializedLearningRepository(Protocol):
    def get_profile_record(self) -> dict[str, Any] | None: ...
    def upsert_profile_record(self, values: dict[str, Any]) -> None: ...
    def memory_essay_rows(self) -> list[dict[str, Any]]: ...
    def get_outcome_essay(self, essay_id: int) -> dict[str, Any] | None: ...
    def list_outcome_essays(self, limit: int) -> list[dict[str, Any]]: ...
    def list_library_records(self) -> list[dict[str, Any]]: ...
    def save_library_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def get_library_progress(self, word: str) -> dict[str, Any] | None: ...
    def update_library_review(self, word: str, values: dict[str, Any]) -> dict[str, Any] | None: ...
    def delete_library_record(self, word: str) -> bool: ...
    def select_library_terms(self, limit: int = 3) -> list[str]: ...
    def create_reading_session_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def get_reading_session_record(self, session_id: int) -> dict[str, Any] | None: ...
    def latest_reading_attempt(self, session_id: int) -> dict[str, Any] | None: ...
    def list_reading_session_records(self, limit: int) -> list[dict[str, Any]]: ...
    def create_reading_attempt_record(self, session_id: int, values: dict[str, Any]) -> None: ...
    def save_listening_progress_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_listening_progress_records(self, asset_id: str) -> list[dict[str, Any]]: ...
    def list_recent_listening_progress_records(self, limit: int = 20) -> list[dict[str, Any]]: ...
    def save_shadowing_progress_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_shadowing_progress_records(self, asset_id: str) -> list[dict[str, Any]]: ...
    def create_speaking_attempt_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_speaking_attempt_records(self, limit: int = 50, *, asset_id: str | None = None, segment_id: str | None = None) -> list[dict[str, Any]]: ...
    def speaking_progress(self) -> dict[str, Any]: ...
    def get_linguistic_essay(self, essay_id: int) -> dict[str, Any] | None: ...
    def update_essay_module_data(self, essay_id: int, module_data: dict[str, Any]) -> bool: ...
    def list_product_activity_events(self, since: datetime) -> list[dict[str, Any]]: ...


class SQLiteSpecializedLearningRepository:
    """SQLite implementation used by the live v1.3.3 runtime.

    The DB resolver already scopes one user + one language. Specialized services
    consume this contract and no longer own SQLite queries themselves.
    """

    def __init__(self, db_factory: Callable[[], sqlite3.Connection]) -> None:
        self._db_factory = db_factory

    def _db(self) -> sqlite3.Connection:
        return self._db_factory()

    def initialize(self) -> None:
        """Create or upgrade durable specialized-learning tables for SQLite.

        Core learning initialization must run first because the Active Recall
        compatibility backfill reads the durable ``saved_words`` table.
        """
        with self._db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    goal TEXT NOT NULL DEFAULT 'everyday',
                    style TEXT NOT NULL DEFAULT 'guided',
                    pinyin TEXT NOT NULL DEFAULT 'auto',
                    native_language TEXT NOT NULL DEFAULT 'vi',
                    theme_preset TEXT NOT NULL DEFAULT 'editorial',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            profile_columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(learner_profile)").fetchall()
            }
            if "native_language" not in profile_columns:
                conn.execute(
                    "ALTER TABLE learner_profile "
                    "ADD COLUMN native_language TEXT NOT NULL DEFAULT 'vi'"
                )
            if "theme_preset" not in profile_columns:
                conn.execute(
                    "ALTER TABLE learner_profile "
                    "ADD COLUMN theme_preset TEXT NOT NULL DEFAULT 'editorial'"
                )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vocabulary_learning (
                    word TEXT PRIMARY KEY COLLATE NOCASE,
                    source_essay_id INTEGER,
                    source_fragment TEXT NOT NULL DEFAULT '',
                    source_kind TEXT NOT NULL DEFAULT 'manual',
                    focus_note TEXT NOT NULL DEFAULT '',
                    review_stage INTEGER NOT NULL DEFAULT 0,
                    successful_recalls INTEGER NOT NULL DEFAULT 0,
                    lapse_count INTEGER NOT NULL DEFAULT 0,
                    last_reviewed_at TEXT NOT NULL DEFAULT '',
                    next_review_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            conn.execute(
                """
                INSERT OR IGNORE INTO vocabulary_learning(
                    word, source_kind, review_stage, successful_recalls,
                    lapse_count, last_reviewed_at, next_review_at, updated_at
                )
                SELECT
                    word, 'manual', 0, 0, 0, '',
                    COALESCE(NULLIF(added_at, ''), ?),
                    COALESCE(NULLIF(added_at, ''), ?)
                FROM saved_words
                """,
                (now, now),
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reading_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    target_level TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    learner_goal TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    passage TEXT NOT NULL,
                    questions_json TEXT NOT NULL,
                    recycled_words_json TEXT NOT NULL DEFAULT '[]',
                    generation_mode TEXT NOT NULL DEFAULT 'practice'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reading_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    answers_json TEXT NOT NULL,
                    correct_count INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES reading_sessions(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reading_sessions_created "
                "ON reading_sessions(created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reading_attempts_session "
                "ON reading_attempts(session_id, id DESC)"
            )
            conn.commit()

    @staticmethod
    def _has_table(conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    def get_profile_record(self) -> dict[str, Any] | None:
        try:
            with self._db() as conn:
                row = conn.execute(
                    "SELECT goal, style, pinyin, native_language, theme_preset, created_at, updated_at FROM learner_profile WHERE id=1"
                ).fetchone()
        except sqlite3.Error:
            return None
        return self._dict(row)

    def upsert_profile_record(self, values: dict[str, Any]) -> None:
        with self._db() as conn:
            existing = conn.execute("SELECT created_at FROM learner_profile WHERE id=1").fetchone()
            created_at = str(existing["created_at"]) if existing else values["created_at"]
            conn.execute(
                """INSERT INTO learner_profile(id,goal,style,pinyin,native_language,theme_preset,created_at,updated_at)
                   VALUES(1,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     goal=excluded.goal, style=excluded.style, pinyin=excluded.pinyin,
                     native_language=excluded.native_language, theme_preset=excluded.theme_preset,
                     updated_at=excluded.updated_at""",
                (values["goal"], values["style"], values["pinyin"], values["native_language"],
                 values["theme_preset"], created_at, values["updated_at"]),
            )
            conn.commit()

    def memory_essay_rows(self) -> list[dict[str, Any]]:
        try:
            with self._db() as conn:
                columns = {str(r["name"]) for r in conn.execute("PRAGMA table_info(essays)").fetchall()}
                if not columns:
                    return []
                strengths = "strengths_json" if "strengths_json" in columns else "'[]' AS strengths_json"
                evidence = "COALESCE(strength_evidence_json,'[]') AS strength_evidence_json" if "strength_evidence_json" in columns else "'[]' AS strength_evidence_json"
                module_data = "COALESCE(module_data_json,'{}') AS module_data_json" if "module_data_json" in columns else "'{}' AS module_data_json"
                rows = conn.execute(
                    f"SELECT id,series_id,revision_no,created_at,overall,errors_json,{strengths},{evidence},{module_data} FROM essays ORDER BY id ASC"
                ).fetchall()
        except sqlite3.Error:
            return []
        return [dict(r) for r in rows]

    def get_outcome_essay(self, essay_id: int) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute(
                """SELECT id,series_id,revision_no,created_at,overall,errors_json,
                          strength_evidence_json,module_data_json
                   FROM essays WHERE id=?""", (essay_id,)
            ).fetchone()
        return self._dict(row)

    def list_outcome_essays(self, limit: int) -> list[dict[str, Any]]:
        with self._db() as conn:
            rows = conn.execute(
                """SELECT id,series_id,revision_no,created_at,overall,errors_json,
                          strength_evidence_json,module_data_json
                   FROM essays
                   WHERE module_data_json IS NOT NULL AND module_data_json != '' AND module_data_json != '{}'
                   ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _library_select() -> str:
        return """SELECT s.word,s.phonetic,s.part_of_speech,s.definition,s.translation_vi,s.added_at,
                         v.source_essay_id,v.source_fragment,v.source_kind,v.focus_note,v.review_stage,
                         v.successful_recalls,v.lapse_count,v.last_reviewed_at,v.next_review_at
                  FROM saved_words s LEFT JOIN vocabulary_learning v ON lower(v.word)=lower(s.word)"""

    def list_library_records(self) -> list[dict[str, Any]]:
        with self._db() as conn:
            if not self._has_table(conn, "saved_words"):
                return []
            if self._has_table(conn, "vocabulary_learning"):
                rows = conn.execute(
                    self._library_select() + " ORDER BY s.added_at DESC"
                ).fetchall()
            else:
                # Legacy/partially initialized language DB: saved words are durable,
                # while Active Recall metadata has never been created. Mirror the
                # PostgreSQL importer defaults without mutating the SQLite source.
                rows = conn.execute(
                    """SELECT s.word,s.phonetic,s.part_of_speech,s.definition,
                              COALESCE(s.translation_vi,'') AS translation_vi,s.added_at,
                              NULL AS source_essay_id,'' AS source_fragment,'manual' AS source_kind,
                              '' AS focus_note,0 AS review_stage,0 AS successful_recalls,
                              0 AS lapse_count,'' AS last_reviewed_at,'' AS next_review_at
                       FROM saved_words s ORDER BY s.added_at DESC"""
                ).fetchall()
        return [dict(r) for r in rows]

    def save_library_record(self, values: dict[str, Any]) -> dict[str, Any]:
        term=values["word"]; now=values["now"]
        with self._db() as conn:
            existing=conn.execute("SELECT word FROM saved_words WHERE lower(word)=lower(?) LIMIT 1",(term,)).fetchone()
            canonical=str(existing["word"]) if existing else term
            if existing:
                conn.execute(
                    """UPDATE saved_words SET
                       phonetic=CASE WHEN ?!='' THEN ? ELSE phonetic END,
                       part_of_speech=CASE WHEN ?!='' THEN ? ELSE part_of_speech END,
                       definition=CASE WHEN ?!='' THEN ? ELSE definition END,
                       translation_vi=CASE WHEN ?!='' THEN ? ELSE translation_vi END
                       WHERE lower(word)=lower(?)""",
                    (values["phonetic"],values["phonetic"],values["part_of_speech"],values["part_of_speech"],
                     values["definition"],values["definition"],values["translation_vi"],values["translation_vi"],canonical),
                )
            else:
                conn.execute("INSERT INTO saved_words(word,phonetic,part_of_speech,definition,added_at,translation_vi) VALUES(?,?,?,?,?,?)",
                             (canonical,values["phonetic"],values["part_of_speech"],values["definition"],now,values["translation_vi"]))
            learning=conn.execute("SELECT word FROM vocabulary_learning WHERE lower(word)=lower(?) LIMIT 1",(canonical,)).fetchone()
            if learning and existing:
                conn.execute(
                    """UPDATE vocabulary_learning SET source_essay_id=COALESCE(?,source_essay_id),
                       source_fragment=CASE WHEN ?!='' THEN ? ELSE source_fragment END,
                       source_kind=CASE WHEN ?!='' THEN ? ELSE source_kind END,
                       focus_note=CASE WHEN ?!='' THEN ? ELSE focus_note END, updated_at=?
                       WHERE lower(word)=lower(?)""",
                    (values["source_essay_id"],values["source_fragment"],values["source_fragment"],values["source_kind"],values["source_kind"],
                     values["focus_note"],values["focus_note"],now,canonical),
                )
            elif learning:
                conn.execute(
                    """UPDATE vocabulary_learning SET word=?,source_essay_id=?,source_fragment=?,source_kind=?,focus_note=?,
                       review_stage=0,successful_recalls=0,lapse_count=0,last_reviewed_at='',next_review_at=?,updated_at=?
                       WHERE lower(word)=lower(?)""",
                    (canonical,values["source_essay_id"],values["source_fragment"],values["source_kind"],values["focus_note"],now,now,canonical),
                )
            else:
                conn.execute(
                    """INSERT INTO vocabulary_learning(word,source_essay_id,source_fragment,source_kind,focus_note,
                       review_stage,successful_recalls,lapse_count,last_reviewed_at,next_review_at,updated_at)
                       VALUES(?,?,?,?,?,0,0,0,'',?,?)""",
                    (canonical,values["source_essay_id"],values["source_fragment"],values["source_kind"],values["focus_note"],now,now),
                )
            conn.commit()
            row=conn.execute(self._library_select()+" WHERE lower(s.word)=lower(?) LIMIT 1",(canonical,)).fetchone()
        return dict(row)

    def get_library_progress(self, word: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row=conn.execute("SELECT review_stage,successful_recalls,lapse_count FROM vocabulary_learning WHERE lower(word)=lower(?) LIMIT 1",(word,)).fetchone()
        return self._dict(row)

    def update_library_review(self, word: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._db() as conn:
            conn.execute(
                """UPDATE vocabulary_learning SET review_stage=?,successful_recalls=?,lapse_count=?,last_reviewed_at=?,next_review_at=?,updated_at=?
                   WHERE lower(word)=lower(?)""",
                (values["review_stage"],values["successful_recalls"],values["lapse_count"],values["last_reviewed_at"],values["next_review_at"],values["updated_at"],word),
            )
            conn.commit()
            row=conn.execute(self._library_select()+" WHERE lower(s.word)=lower(?) LIMIT 1",(word,)).fetchone()
        return self._dict(row)

    def delete_library_record(self, word: str) -> bool:
        with self._db() as conn:
            conn.execute("DELETE FROM vocabulary_learning WHERE lower(word)=lower(?)",(word,))
            cur=conn.execute("DELETE FROM saved_words WHERE lower(word)=lower(?)",(word,))
            conn.commit()
        return cur.rowcount > 0

    def select_library_terms(self, limit: int = 3) -> list[str]:
        with self._db() as conn:
            if not self._has_table(conn, "saved_words"):
                return []
            if self._has_table(conn, "vocabulary_learning"):
                rows = conn.execute(
                    """SELECT s.word FROM saved_words s LEFT JOIN vocabulary_learning v ON lower(v.word)=lower(s.word)
                       ORDER BY CASE WHEN COALESCE(v.review_stage,0)<3 THEN 0 ELSE 1 END,
                                COALESCE(NULLIF(v.next_review_at,''),s.added_at) ASC, s.added_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT word FROM saved_words ORDER BY added_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [str(r["word"]) for r in rows if str(r["word"] or "").strip()]

    def create_reading_session_record(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._db() as conn:
            cur=conn.execute(
                """INSERT INTO reading_sessions(created_at,language_code,target_level,topic,learner_goal,title,passage,questions_json,recycled_words_json,generation_mode)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (values["created_at"],values["language_code"],values["target_level"],values["topic"],values["learner_goal"],values["title"],values["passage"],
                 json.dumps(values["questions"],ensure_ascii=False),json.dumps(values["recycled_words"],ensure_ascii=False),values["generation_mode"]),
            )
            sid=int(cur.lastrowid); conn.commit(); row=conn.execute("SELECT * FROM reading_sessions WHERE id=?",(sid,)).fetchone()
        return dict(row)

    def get_reading_session_record(self, session_id: int) -> dict[str, Any] | None:
        with self._db() as conn: row=conn.execute("SELECT * FROM reading_sessions WHERE id=?",(session_id,)).fetchone()
        return self._dict(row)

    def latest_reading_attempt(self, session_id: int) -> dict[str, Any] | None:
        with self._db() as conn:
            row=conn.execute("SELECT correct_count,total,created_at FROM reading_attempts WHERE session_id=? ORDER BY id DESC LIMIT 1",(session_id,)).fetchone()
        return self._dict(row)

    def list_reading_session_records(self, limit: int) -> list[dict[str, Any]]:
        with self._db() as conn:
            if not self._has_table(conn, "reading_sessions"):
                return []
            if self._has_table(conn, "reading_attempts"):
                rows = conn.execute(
                    """SELECT s.*,
                       (SELECT correct_count FROM reading_attempts a WHERE a.session_id=s.id ORDER BY a.id DESC LIMIT 1) AS last_correct,
                       (SELECT total FROM reading_attempts a WHERE a.session_id=s.id ORDER BY a.id DESC LIMIT 1) AS last_total
                       FROM reading_sessions s ORDER BY s.id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT s.*, NULL AS last_correct, NULL AS last_total
                       FROM reading_sessions s ORDER BY s.id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def create_reading_attempt_record(self, session_id: int, values: dict[str, Any]) -> None:
        with self._db() as conn:
            conn.execute("INSERT INTO reading_attempts(session_id,created_at,answers_json,correct_count,total) VALUES(?,?,?,?,?)",
                         (session_id,values["created_at"],json.dumps(values["answers"]),values["correct_count"],values["total"]))
            conn.commit()

    def save_listening_progress_record(self, values: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Durable Active Listening progress requires the PostgreSQL runtime.")

    def list_listening_progress_records(self, asset_id: str) -> list[dict[str, Any]]:
        raise RuntimeError("Durable Active Listening progress requires the PostgreSQL runtime.")

    def list_recent_listening_progress_records(self, limit: int = 20) -> list[dict[str, Any]]:
        raise RuntimeError("Durable Active Listening progress requires the PostgreSQL runtime.")

    def save_shadowing_progress_record(self, values: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Durable Shadowing progress requires the PostgreSQL runtime.")

    def list_shadowing_progress_records(self, asset_id: str) -> list[dict[str, Any]]:
        raise RuntimeError("Durable Shadowing progress requires the PostgreSQL runtime.")

    def create_speaking_attempt_record(self, values: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Durable Speaking attempts require the PostgreSQL runtime.")

    def list_speaking_attempt_records(self, limit: int = 50, *, asset_id: str | None = None, segment_id: str | None = None) -> list[dict[str, Any]]:
        raise RuntimeError("Durable Speaking attempts require the PostgreSQL runtime.")

    def speaking_progress(self) -> dict[str, Any]:
        raise RuntimeError("Durable Speaking attempts require the PostgreSQL runtime.")

    def get_linguistic_essay(self, essay_id: int) -> dict[str, Any] | None:
        with self._db() as conn:
            row=conn.execute("SELECT id,text,language_code,module_data_json FROM essays WHERE id=?",(essay_id,)).fetchone()
        return self._dict(row)

    def update_essay_module_data(self, essay_id: int, module_data: dict[str, Any]) -> bool:
        with self._db() as conn:
            cur=conn.execute("UPDATE essays SET module_data_json=? WHERE id=?",(json.dumps(module_data,ensure_ascii=False),essay_id))
            conn.commit()
        return cur.rowcount > 0

    def list_product_activity_events(self, since: datetime) -> list[dict[str, Any]]:
        raise RuntimeError("Product activity analytics requires the PostgreSQL runtime.")


class PostgresSpecializedLearningRepository:
    """SQLAlchemy implementation ready for a later explicit runtime cutover."""

    def __init__(self, engine: Engine | None = None, *, url: str | None = None,
                 user_key_provider: Callable[[], str] = current_user_key,
                 language_provider: Callable[[], str] = current_language_code) -> None:
        self.engine=engine or create_shadow_engine(url)
        self._user_key_provider=user_key_provider
        self._language_provider=language_provider

    def _scope(self) -> tuple[Any,str]:
        key=self._user_key_provider(); return stable_uuid("user",key), self._language_provider().casefold()

    def _key(self) -> str: return self._user_key_provider()

    @staticmethod
    def _dt(value: Any) -> datetime:
        if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00")); return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _iso(value: datetime | None) -> str:
        return value.isoformat() if value else ""

    def get_profile_record(self) -> dict[str, Any] | None:
        uid,lang=self._scope()
        with Session(self.engine) as s:
            r=s.scalar(select(UserLanguageProfile).where(UserLanguageProfile.user_id==uid,UserLanguageProfile.language_code==lang))
            if r is None: return None
            return {"goal":r.goal,"style":r.style,"pinyin":r.pinyin,"native_language":r.native_language,"theme_preset":r.theme_preset,
                    "created_at":self._iso(r.created_at),"updated_at":self._iso(r.updated_at)}

    def upsert_profile_record(self, values: dict[str, Any]) -> None:
        uid,lang=self._scope(); pid=stable_uuid("profile",self._key(),lang)
        with Session(self.engine) as s, s.begin():
            if s.get(User,uid) is None: raise RuntimeError("PostgreSQL scope user missing; shadow/import must run first.")
            r=s.get(UserLanguageProfile,pid)
            if r is None:
                s.add(UserLanguageProfile(id=pid,user_id=uid,language_code=lang,goal=values["goal"],style=values["style"],pinyin=values["pinyin"],
                                          native_language=values["native_language"],theme_preset=values["theme_preset"],created_at=self._dt(values["created_at"]),updated_at=self._dt(values["updated_at"])))
            else:
                r.goal=values["goal"]; r.style=values["style"]; r.pinyin=values["pinyin"]; r.native_language=values["native_language"]
                r.theme_preset=values["theme_preset"]; r.updated_at=self._dt(values["updated_at"])

    def _essay_rows(self, *, desc: bool=False) -> list[dict[str, Any]]:
        uid,lang=self._scope(); order=Essay.legacy_id.desc() if desc else Essay.legacy_id.asc()
        with Session(self.engine) as s:
            essays=s.scalars(select(Essay).where(Essay.user_id==uid,Essay.language_code==lang).order_by(order)).all()
            revs={r.essay_id:r for r in s.scalars(select(EssayRevision).where(EssayRevision.user_id==uid,EssayRevision.language_code==lang)).all()}
            out=[]
            for e in essays:
                r=revs.get(e.id)
                out.append({"id":e.legacy_id,"series_id":r.series_legacy_id if r else e.legacy_id,"revision_no":r.revision_no if r else 1,
                            "created_at":self._iso(e.created_at),"overall":e.overall,"errors_json":json.dumps(e.errors,ensure_ascii=False),
                            "strengths_json":json.dumps(e.strengths,ensure_ascii=False),"strength_evidence_json":json.dumps(e.strength_evidence,ensure_ascii=False),
                            "module_data_json":json.dumps(e.module_data,ensure_ascii=False)})
        return out

    def memory_essay_rows(self) -> list[dict[str, Any]]: return self._essay_rows()
    def get_outcome_essay(self, essay_id: int) -> dict[str, Any] | None:
        return next((r for r in self._essay_rows() if int(r["id"])==essay_id),None)
    def list_outcome_essays(self, limit: int) -> list[dict[str, Any]]:
        rows=[r for r in self._essay_rows(desc=True) if r.get("module_data_json") not in (None,"","{}")]
        return rows[:limit]

    def list_library_records(self) -> list[dict[str, Any]]:
        uid,lang=self._scope()
        with Session(self.engine) as s:
            rows=s.scalars(select(SavedWord).where(SavedWord.user_id==uid,SavedWord.language_code==lang).order_by(SavedWord.added_at.desc())).all()
            return [self._saved_payload(r) for r in rows]

    def _saved_payload(self,r: SavedWord) -> dict[str,Any]:
        source_legacy=None
        if r.source_essay_id:
            with Session(self.engine) as s:
                e=s.get(Essay,r.source_essay_id); source_legacy=e.legacy_id if e else None
        return {"word":r.word,"phonetic":r.phonetic,"part_of_speech":r.part_of_speech,"definition":r.definition,"translation_vi":r.translation_vi,
                "added_at":self._iso(r.added_at),"source_essay_id":source_legacy,"source_fragment":r.source_fragment,"source_kind":r.source_kind,
                "focus_note":r.focus_note,"review_stage":r.review_stage,"successful_recalls":r.successful_recalls,"lapse_count":r.lapse_count,
                "last_reviewed_at":self._iso(r.last_reviewed_at),"next_review_at":self._iso(r.next_review_at)}

    def _saved(self,s: Session,word: str) -> SavedWord | None:
        uid,lang=self._scope(); return s.scalar(select(SavedWord).where(SavedWord.user_id==uid,SavedWord.language_code==lang,SavedWord.normalized_word==word.casefold()))

    def save_library_record(self, values: dict[str, Any]) -> dict[str, Any]:
        uid,lang=self._scope(); normalized=values["word"].casefold(); sid=stable_uuid("saved-word",self._key(),lang,normalized); now=self._dt(values["now"])
        with Session(self.engine) as s, s.begin():
            r=s.get(SavedWord,sid)
            source_uuid=None
            if values.get("source_essay_id"):
                e=s.scalar(select(Essay).where(Essay.user_id==uid,Essay.language_code==lang,Essay.legacy_id==int(values["source_essay_id"])))
                source_uuid=e.id if e else None
            if r is None:
                r=SavedWord(id=sid,user_id=uid,language_code=lang,word=values["word"],normalized_word=normalized,phonetic=values["phonetic"],
                            part_of_speech=values["part_of_speech"],definition=values["definition"],translation_vi=values["translation_vi"],added_at=now,
                            source_essay_id=source_uuid,source_fragment=values["source_fragment"],source_kind=values["source_kind"],focus_note=values["focus_note"],
                            review_stage=0,successful_recalls=0,lapse_count=0,last_reviewed_at=None,next_review_at=now,updated_at=now); s.add(r)
            else:
                if values["phonetic"]: r.phonetic=values["phonetic"]
                if values["part_of_speech"]: r.part_of_speech=values["part_of_speech"]
                if values["definition"]: r.definition=values["definition"]
                if values["translation_vi"]: r.translation_vi=values["translation_vi"]
                if source_uuid: r.source_essay_id=source_uuid
                if values["source_fragment"]: r.source_fragment=values["source_fragment"]
                if values["source_kind"]: r.source_kind=values["source_kind"]
                if values["focus_note"]: r.focus_note=values["focus_note"]
                r.updated_at=now
            s.flush(); payload=self._saved_payload_from_session(s,r)
        return payload

    def _saved_payload_from_session(self,s:Session,r:SavedWord)->dict[str,Any]:
        source_legacy=None
        if r.source_essay_id:
            e=s.get(Essay,r.source_essay_id); source_legacy=e.legacy_id if e else None
        return {"word":r.word,"phonetic":r.phonetic,"part_of_speech":r.part_of_speech,"definition":r.definition,"translation_vi":r.translation_vi,
                "added_at":self._iso(r.added_at),"source_essay_id":source_legacy,"source_fragment":r.source_fragment,"source_kind":r.source_kind,"focus_note":r.focus_note,
                "review_stage":r.review_stage,"successful_recalls":r.successful_recalls,"lapse_count":r.lapse_count,"last_reviewed_at":self._iso(r.last_reviewed_at),
                "next_review_at":self._iso(r.next_review_at)}

    def get_library_progress(self, word: str) -> dict[str, Any] | None:
        with Session(self.engine) as s:
            r=self._saved(s,word)
            return None if r is None else {"review_stage":r.review_stage,"successful_recalls":r.successful_recalls,"lapse_count":r.lapse_count}

    def update_library_review(self, word: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with Session(self.engine) as s, s.begin():
            r=self._saved(s,word)
            if r is None: return None
            r.review_stage=int(values["review_stage"]); r.successful_recalls=int(values["successful_recalls"]); r.lapse_count=int(values["lapse_count"])
            r.last_reviewed_at=self._dt(values["last_reviewed_at"]); r.next_review_at=self._dt(values["next_review_at"]); r.updated_at=self._dt(values["updated_at"])
            s.flush(); return self._saved_payload_from_session(s,r)

    def delete_library_record(self, word: str) -> bool:
        with Session(self.engine) as s, s.begin():
            r=self._saved(s,word)
            if r is None: return False
            s.delete(r); return True

    def select_library_terms(self, limit: int = 3) -> list[str]:
        rows=self.list_library_records()
        rows.sort(key=lambda r:(0 if int(r["review_stage"] or 0)<3 else 1,r["next_review_at"] or r["added_at"],r["word"].casefold()))
        return [str(r["word"]) for r in rows[:limit]]

    def create_reading_session_record(self, values: dict[str, Any]) -> dict[str, Any]:
        uid,lang=self._scope()
        with Session(self.engine) as s, s.begin():
            max_id=s.scalar(select(func.max(ReadingSession.legacy_id)).where(ReadingSession.user_id==uid,ReadingSession.language_code==lang))
            legacy=int(max_id or 0)+1; sid=stable_uuid("reading-session",self._key(),lang,legacy)
            r=ReadingSession(id=sid,user_id=uid,language_code=lang,legacy_id=legacy,created_at=self._dt(values["created_at"]),target_level=values["target_level"],
                             topic=values["topic"],learner_goal=values["learner_goal"],title=values["title"],passage=values["passage"],questions=values["questions"],
                             recycled_words=values["recycled_words"],generation_mode=values["generation_mode"]); s.add(r); s.flush(); return self._reading_payload(r)

    def _reading_payload(self,r:ReadingSession)->dict[str,Any]:
        return {"id":r.legacy_id,"created_at":self._iso(r.created_at),"language_code":r.language_code,"target_level":r.target_level,"topic":r.topic,
                "learner_goal":r.learner_goal,"title":r.title,"passage":r.passage,"questions_json":json.dumps(r.questions,ensure_ascii=False),
                "recycled_words_json":json.dumps(r.recycled_words,ensure_ascii=False),"generation_mode":r.generation_mode}

    def _reading(self,s:Session,session_id:int)->ReadingSession|None:
        uid,lang=self._scope(); return s.scalar(select(ReadingSession).where(ReadingSession.user_id==uid,ReadingSession.language_code==lang,ReadingSession.legacy_id==session_id))

    def get_reading_session_record(self, session_id: int) -> dict[str, Any] | None:
        with Session(self.engine) as s:
            r=self._reading(s,session_id); return self._reading_payload(r) if r else None

    def latest_reading_attempt(self, session_id: int) -> dict[str, Any] | None:
        with Session(self.engine) as s:
            r=self._reading(s,session_id)
            if r is None: return None
            a=s.scalar(select(ReadingAttempt).where(ReadingAttempt.session_id==r.id).order_by(ReadingAttempt.legacy_id.desc()).limit(1))
            return None if a is None else {"correct_count":a.correct_count,"total":a.total,"created_at":self._iso(a.created_at)}

    def list_reading_session_records(self, limit: int) -> list[dict[str, Any]]:
        uid,lang=self._scope()
        with Session(self.engine) as s:
            rows=s.scalars(select(ReadingSession).where(ReadingSession.user_id==uid,ReadingSession.language_code==lang).order_by(ReadingSession.legacy_id.desc()).limit(limit)).all()
            out=[]
            for r in rows:
                item=self._reading_payload(r); a=s.scalar(select(ReadingAttempt).where(ReadingAttempt.session_id==r.id).order_by(ReadingAttempt.legacy_id.desc()).limit(1))
                item["last_correct"]=a.correct_count if a else None; item["last_total"]=a.total if a else None; out.append(item)
            return out

    def create_reading_attempt_record(self, session_id: int, values: dict[str, Any]) -> None:
        with Session(self.engine) as s, s.begin():
            r=self._reading(s,session_id)
            if r is None: raise ValueError("Reading session not found")
            max_id=s.scalar(select(func.max(ReadingAttempt.legacy_id))); legacy=int(max_id or 0)+1
            s.add(ReadingAttempt(id=stable_uuid("reading-attempt",self._key(),self._language_provider().casefold(),legacy),session_id=r.id,legacy_id=legacy,
                                 created_at=self._dt(values["created_at"]),answers=list(values["answers"]),correct_count=int(values["correct_count"]),total=int(values["total"])))

    def _listening_progress_payload(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "language": row.language_code,
            "asset_id": row.asset_id,
            "segment_id": row.segment_id,
            "presentation": row.presentation,
            "revealed": bool(row.revealed),
            "checked_attempt_count": int(row.checked_attempt_count or 0),
            "best_accuracy_percent": row.best_accuracy_percent,
            "best_exact": bool(row.best_exact),
            "last_answer": row.last_answer,
            "updated_at": self._iso(row.updated_at),
        }

    def save_listening_progress_record(self, values: dict[str, Any]) -> dict[str, Any]:
        uid, lang = self._scope()
        asset_id = str(values["asset_id"])
        segment_id = str(values["segment_id"])
        progress_id = stable_uuid("listening-progress", self._key(), lang, asset_id, segment_id)
        with Session(self.engine) as s, s.begin():
            if s.get(User, uid) is None:
                raise RuntimeError("PostgreSQL scope user missing; shadow/import must run first.")
            row = s.get(ListeningProgress, progress_id)
            fields = {
                "presentation": values.get("presentation", "prompt"),
                "revealed": bool(values.get("revealed", False)),
                "checked_attempt_count": int(values.get("checked_attempt_count", 0)),
                "best_accuracy_percent": values.get("best_accuracy_percent"),
                "best_exact": bool(values.get("best_exact", False)),
                "last_answer": str(values.get("last_answer", "")),
                "updated_at": self._dt(values["updated_at"]),
            }
            if row is None:
                row = ListeningProgress(
                    id=progress_id, user_id=uid, language_code=lang,
                    asset_id=asset_id, segment_id=segment_id, **fields,
                )
                s.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
            s.flush()
            return self._listening_progress_payload(row)

    def list_listening_progress_records(self, asset_id: str) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as s:
            rows = s.scalars(
                select(ListeningProgress)
                .where(
                    ListeningProgress.user_id == uid,
                    ListeningProgress.language_code == lang,
                    ListeningProgress.asset_id == asset_id,
                )
                .order_by(ListeningProgress.updated_at.desc())
            ).all()
            return [self._listening_progress_payload(row) for row in rows]

    def list_recent_listening_progress_records(self, limit: int = 20) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as s:
            rows = s.scalars(
                select(ListeningProgress)
                .where(ListeningProgress.user_id == uid, ListeningProgress.language_code == lang)
                .order_by(ListeningProgress.updated_at.desc())
                .limit(max(1, min(int(limit), 100)))
            ).all()
            return [self._listening_progress_payload(row) for row in rows]

    def _shadowing_progress_payload(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "language": row.language_code,
            "asset_id": row.asset_id,
            "segment_id": row.segment_id,
            "completed_rounds": int(row.completed_rounds or 0),
            "updated_at": self._iso(row.updated_at),
        }

    def save_shadowing_progress_record(self, values: dict[str, Any]) -> dict[str, Any]:
        uid, lang = self._scope()
        asset_id = str(values["asset_id"])
        segment_id = str(values["segment_id"])
        progress_id = stable_uuid("shadowing-progress", self._key(), lang, asset_id, segment_id)
        with Session(self.engine) as s, s.begin():
            if s.get(User, uid) is None:
                raise RuntimeError("PostgreSQL scope user missing; shadow/import must run first.")
            row = s.get(ShadowingProgress, progress_id)
            fields = {
                "completed_rounds": int(values.get("completed_rounds", 0)),
                "updated_at": self._dt(values["updated_at"]),
            }
            if row is None:
                row = ShadowingProgress(
                    id=progress_id, user_id=uid, language_code=lang,
                    asset_id=asset_id, segment_id=segment_id, **fields,
                )
                s.add(row)
            else:
                # Shadowing rounds are cumulative learner evidence. A delayed
                # client snapshot must never roll a newer persisted total back.
                row.completed_rounds = max(int(row.completed_rounds or 0), fields["completed_rounds"])
                row.updated_at = fields["updated_at"]
            s.flush()
            return self._shadowing_progress_payload(row)

    def list_shadowing_progress_records(self, asset_id: str) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as s:
            rows = s.scalars(
                select(ShadowingProgress)
                .where(
                    ShadowingProgress.user_id == uid,
                    ShadowingProgress.language_code == lang,
                    ShadowingProgress.asset_id == asset_id,
                )
                .order_by(ShadowingProgress.updated_at.desc())
            ).all()
            return [self._shadowing_progress_payload(row) for row in rows]

    @staticmethod
    def _speaking_payload(row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "created_at": PostgresSpecializedLearningRepository._iso(row.created_at),
            "language": row.language_code,
            "take_id": row.take_id,
            "asset_id": row.asset_id,
            "segment_id": row.segment_id,
            "reference_text": row.reference_text,
            "transcript_text": row.transcript_text,
            "dimensions": dict(row.dimensions or {}),
            "provenance": dict(row.provenance or {}),
            "evidence": dict(row.evidence or {}),
        }

    def create_speaking_attempt_record(self, values: dict[str, Any]) -> dict[str, Any]:
        uid, lang = self._scope()
        attempt_id = stable_uuid("speaking-attempt", self._key(), lang, values["take_id"])
        with Session(self.engine) as s, s.begin():
            if s.get(User, uid) is None:
                raise RuntimeError("PostgreSQL scope user missing; shadow/import must run first.")
            row = s.get(SpeakingAttempt, attempt_id)
            if row is None:
                row = SpeakingAttempt(
                    id=attempt_id, user_id=uid, language_code=lang,
                    take_id=values["take_id"],
                    asset_id=values.get("asset_id", ""), segment_id=values.get("segment_id", ""),
                    reference_text=values["reference_text"], transcript_text=values["transcript_text"],
                    dimensions=dict(values.get("dimensions", {})), provenance=dict(values.get("provenance", {})),
                    evidence=dict(values.get("evidence", {})), created_at=self._dt(values["created_at"]),
                )
                s.add(row)
            else:
                row.created_at = self._dt(values["created_at"])
                row.asset_id = values.get("asset_id", "")
                row.segment_id = values.get("segment_id", "")
                row.reference_text = values["reference_text"]
                row.transcript_text = values["transcript_text"]
                row.dimensions = dict(values.get("dimensions", {}))
                row.provenance = dict(values.get("provenance", {}))
                row.evidence = dict(values.get("evidence", {}))
            s.flush()
            return self._speaking_payload(row)

    def list_speaking_attempt_records(self, limit: int = 50, *, asset_id: str | None = None, segment_id: str | None = None) -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as s:
            filters = [SpeakingAttempt.user_id == uid, SpeakingAttempt.language_code == lang]
            if asset_id is not None:
                filters.append(SpeakingAttempt.asset_id == asset_id)
            if segment_id is not None:
                filters.append(SpeakingAttempt.segment_id == segment_id)
            rows = s.scalars(
                select(SpeakingAttempt)
                .where(*filters)
                .order_by(SpeakingAttempt.created_at.desc())
                .limit(max(1, min(int(limit), 100)))
            ).all()
            return [self._speaking_payload(row) for row in rows]

    def speaking_progress(self) -> dict[str, Any]:
        items = self.list_speaking_attempt_records(100)
        def average(key: str) -> float | None:
            values = [v for item in items if isinstance(v := item["dimensions"].get(key), (int, float))]
            return round(sum(values) / len(values), 2) if values else None
        return {
            "attempt_count": len(items),
            "average_content_match": average("content_match"),
            "average_pronunciation": average("pronunciation"),
            "average_fluency": average("fluency"),
            "latest_at": items[0]["created_at"] if items else None,
            "proficiency": None,
        }

    def get_linguistic_essay(self, essay_id: int) -> dict[str, Any] | None:
        uid,lang=self._scope()
        with Session(self.engine) as s:
            e=s.scalar(select(Essay).where(Essay.user_id==uid,Essay.language_code==lang,Essay.legacy_id==essay_id))
            return None if e is None else {"id":e.legacy_id,"text":e.text,"language_code":e.language_code,"module_data_json":json.dumps(e.module_data,ensure_ascii=False)}

    def update_essay_module_data(self, essay_id: int, module_data: dict[str, Any]) -> bool:
        uid,lang=self._scope()
        with Session(self.engine) as s, s.begin():
            e=s.scalar(select(Essay).where(Essay.user_id==uid,Essay.language_code==lang,Essay.legacy_id==essay_id))
            if e is None: return False
            e.module_data=module_data; return True

    def list_product_activity_events(self, since: datetime) -> list[dict[str, Any]]:
        """Read aggregate inputs across learners without selecting raw content."""
        with Session(self.engine) as s:
            events: list[dict[str, Any]] = []
            for essay_id, occurred, uid in s.execute(select(Essay.id, Essay.created_at, Essay.user_id).where(Essay.created_at >= since)).all():
                events.append({"skill": "writing", "occurred_at": self._iso(occurred), "learner_key": str(uid), "completed": True})
                events.extend({"skill": "writing", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": stage, "funnel_key": str(essay_id), "funnel_only": True} for stage in ("attempted", "completed"))
            for session_id, occurred, uid in s.execute(select(ReadingSession.id, ReadingSession.created_at, ReadingSession.user_id).where(ReadingSession.created_at >= since)).all():
                events.append({"skill": "reading", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "started", "funnel_key": str(session_id), "funnel_only": True})
            for session_id, occurred, uid, total in s.execute(select(ReadingAttempt.session_id, ReadingAttempt.created_at, ReadingSession.user_id, ReadingAttempt.total).join(ReadingSession, ReadingAttempt.session_id == ReadingSession.id).where(ReadingAttempt.created_at >= since)).all():
                completed = isinstance(total, int) and total > 0
                events.append({"skill": "reading", "occurred_at": self._iso(occurred), "learner_key": str(uid), "completed": completed})
                events.append({"skill": "reading", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "attempted", "funnel_key": str(session_id), "funnel_only": True})
                if completed:
                    events.append({"skill": "reading", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "completed", "funnel_key": str(session_id), "funnel_only": True})
            for asset_id, segment_id, occurred, uid, revealed, checked in s.execute(select(ListeningProgress.asset_id, ListeningProgress.segment_id, ListeningProgress.updated_at, ListeningProgress.user_id, ListeningProgress.revealed, ListeningProgress.checked_attempt_count).where(ListeningProgress.updated_at >= since)).all():
                completed = bool(revealed or (checked or 0) > 0)
                events.append({"skill": "listening", "occurred_at": self._iso(occurred), "learner_key": str(uid), "completed": completed})
                funnel_key = f"{asset_id}:{segment_id}"
                events.append({"skill": "listening", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "attempted", "funnel_key": funnel_key, "funnel_only": True})
                if completed:
                    events.append({"skill": "listening", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "completed", "funnel_key": funnel_key, "funnel_only": True})
            for take_id, occurred, uid in s.execute(select(SpeakingAttempt.take_id, SpeakingAttempt.created_at, SpeakingAttempt.user_id).where(SpeakingAttempt.created_at >= since)).all():
                events.append({"skill": "speaking", "occurred_at": self._iso(occurred), "learner_key": str(uid), "completed": True})
                events.append({"skill": "speaking", "occurred_at": self._iso(occurred), "learner_key": str(uid), "funnel_stage": "completed", "funnel_key": str(take_id), "funnel_only": True})
            return events
