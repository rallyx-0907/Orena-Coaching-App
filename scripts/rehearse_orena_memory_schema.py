"""Rehearsal of the PROPOSED migration 20261018_0035 (Orena Memory, M2) on a throwaway PostgreSQL.

`docs/project/proposals/ORENA_MEMORY.md` rev 4.1 §4.1, §4.4, §9. Run by hand against a database given by URL; not part
of CI; it refuses anything that is not clearly throwaway and empty (the guard of `rehearse_learner_records_schema.py`).
It applies the proposal from a temporary Alembic version location holding only this one file, on top of the real
`migrations/versions/` chain, so the shared runtimes (which read `migrations/versions/` alone) never see it.

    python scripts/rehearse_orena_memory_schema.py "$REHEARSAL_URL"

Steps (each a PASS/FAIL row; non-zero exit on any FAIL):
 1. chain: `versions/` alone has the single head 20261015_0033; with the proposal the head is 20261018_0035.
 2. empty -> 0033 (real chain), then 0033 -> 0035; the three tables and their indexes exist.
 3. constraints: class, kind, text length, value_key length, key_version, provenance size, expiry required for
    continuity and inferred, evidence only on inferred, slot required off explicit; the composite owner FK refuses an
    incarnation of another user; uniqueness of a single-valued slot, of a multi-valued slot's value, of an explicit
    note's text, of a suppression key; one state row per incarnation, version never negative.
 4. downgrade refuses while memory rows exist; once they are gone it restores 0033's schema exactly; upgrade again
    gives the same schema as the first upgrade.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import sqlalchemy as sa  # noqa: E402
from alembic import command  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import text  # noqa: E402

from rehearse_grammar_content_store import alembic_config  # noqa: E402
from rehearse_learner_records_schema import refuse_unless_empty, refuse_unless_throwaway  # noqa: E402

HEAD, REV = "20261015_0033", "20261018_0035"
PROPOSAL = ROOT / "migrations" / "proposed" / "20261018_0035_orena_memory.py"
TABLES = ("learner_memories", "learner_memory_suppressions", "learner_memory_state")
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def refused(engine, sql: str, params: dict) -> str | None:
    """The SQLSTATE a statement is refused with, or None when it succeeds (rolled back either way)."""

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(text(sql), params)
        except sa.exc.DBAPIError as exc:
            tx.rollback()
            return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None) or "error"
        tx.rollback()
    return None


def schema(engine) -> dict:
    inspector = sa.inspect(engine)
    out = {}
    for table in sorted(inspector.get_table_names()):
        out[table] = {
            "columns": sorted((c["name"], str(c["type"]), c["nullable"]) for c in inspector.get_columns(table)),
            "indexes": sorted(i["name"] for i in inspector.get_indexes(table)),
            "uniques": sorted(u["name"] for u in inspector.get_unique_constraints(table)),
            "fks": sorted(f["name"] or "" for f in inspector.get_foreign_keys(table)),
            "checks": sorted(c["name"] for c in inspector.get_check_constraints(table)),
        }
    return out


def memory_row(**over) -> dict:
    row = {"id": str(uuid.uuid4()), "lang": "zh", "cls": "explicit", "kind": "goal", "slot": None, "text": "Đi làm",
           "key": "a" * 64, "kv": 1, "src": "learner_asked", "prov": "{}", "exp": None, "ev": None}
    row.update(over)
    return row


INSERT = ("INSERT INTO learner_memories (id, incarnation_id, user_id, language_code, class, kind, slot, text,"
          " value_key, key_version, source, provenance, expires_at, evidence_count, created_at, updated_at)"
          " VALUES (:id, :inc, :user, :lang, :cls, :kind, :slot, :text, :key, :kv, :src, CAST(:prov AS jsonb),"
          " CAST(:exp AS timestamptz), :ev, now(), now())")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    refuse_unless_throwaway(args.url)
    engine = sa.create_engine(args.url)
    refuse_unless_empty(engine)

    proposal_dir = Path(tempfile.mkdtemp(prefix="orena-memory-proposal-"))
    shutil.copy(PROPOSAL, proposal_dir / PROPOSAL.name)
    try:
        cfg_v, cfg_p = alembic_config(args.url, None), alembic_config(args.url, proposal_dir)
        check("1 chain: versions/ head", ScriptDirectory.from_config(cfg_v).get_heads() == [HEAD])
        check("1 chain: with the proposal", ScriptDirectory.from_config(cfg_p).get_heads() == [REV])

        command.upgrade(cfg_v, HEAD)
        before = schema(engine)
        command.upgrade(cfg_p, REV)
        first = schema(engine)
        check("2 tables", all(t in first for t in TABLES), ", ".join(TABLES))
        indexes = set(first["learner_memories"]["indexes"])
        check("2 indexes", {"uq_learner_memories_single_slot", "uq_learner_memories_multi_slot",
                            "uq_learner_memories_explicit_text", "ix_learner_memories_pack",
                            "ix_learner_memories_expiry"} <= indexes, ", ".join(sorted(indexes)))

        with engine.begin() as conn:
            users = [conn.execute(text(
                "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                " VALUES (gen_random_uuid(), :k, '', '', '', 'user', now()) RETURNING id"), {"k": f"rehearsal-{n}"}
            ).scalar() for n in (1, 2)]
            incs = [conn.execute(text(
                "INSERT INTO account_incarnations (id, user_id, epoch, status, created_at)"
                " VALUES (gen_random_uuid(), :u, 1, 'active', now()) RETURNING id"), {"u": u}).scalar() for u in users]
        a, b = {"inc": str(incs[0]), "user": str(users[0])}, {"inc": str(incs[1]), "user": str(users[0])}

        def ok(**over) -> bool:
            return refused(engine, INSERT, {**a, **memory_row(**over)}) is None

        def refuses(state: str, **over) -> bool:
            return refused(engine, INSERT, {**a, **memory_row(**over)}) == state

        check("3 a valid explicit item", ok())
        check("3 class", refuses("23514", cls="opinion"))
        check("3 kind", refuses("23514", kind="secret"))
        check("3 text length", refuses("22001", text="x" * 201) or refuses("23514", text="x" * 201))
        check("3 empty text", refuses("23514", text=""))
        check("3 value_key length", refuses("23514", key="short"))
        check("3 key_version", refuses("23514", kv=0))
        check("3 provenance size", refuses("23514", prov='{"s": "' + "x" * 3000 + '"}'))
        check("3 continuity needs expiry", refuses("23514", cls="continuity", slot="interest", kind="context"))
        check("3 continuity needs a slot", refuses("23514", cls="continuity", exp="2026-11-01T00:00:00Z"))
        check("3 evidence only on inferred", refuses("23514", ev=3))
        check("3 owner: another user's incarnation", refused(engine, INSERT, {**b, **memory_row()}) == "23503")

        with engine.begin() as conn:
            conn.execute(text(INSERT), {**a, **memory_row(cls="continuity", kind="context", slot="occupation",
                                                          key="b" * 64, exp="2026-11-01T00:00:00Z")})
            conn.execute(text(INSERT), {**a, **memory_row(cls="continuity", kind="context", slot="interest",
                                                          key="c" * 64, exp="2026-11-01T00:00:00Z")})
            conn.execute(text(INSERT), {**a, **memory_row(key="d" * 64)})
        check("3 single-valued slot once", refuses("23505", cls="continuity", kind="context", slot="occupation",
                                                   key="e" * 64, exp="2026-11-01T00:00:00Z"))
        check("3 multi-valued slot: another value", ok(cls="continuity", kind="context", slot="interest", key="f" * 64,
                                                     exp="2026-11-01T00:00:00Z"))
        check("3 multi-valued slot: the same value once", refuses("23505", cls="continuity", kind="context",
                                                                  slot="interest", key="c" * 64,
                                                                  exp="2026-11-01T00:00:00Z"))
        check("3 explicit text once", refuses("23505", key="d" * 64))
        check("3 another language is another item", ok(lang="en", key="d" * 64))

        suppression = ("INSERT INTO learner_memory_suppressions (id, incarnation_id, user_id, language_code, class,"
                       " slot, value_key, key_version, expires_at) VALUES (gen_random_uuid(), :inc, :user, 'zh',"
                       " :cls, 'interest', :key, 1, now() + interval '14 days')")
        with engine.begin() as conn:
            conn.execute(text(suppression), {**a, "cls": "continuity", "key": "c" * 64})
        check("3 suppression key once", refused(engine, suppression, {**a, "cls": "continuity", "key": "c" * 64})
              == "23505")
        check("3 no suppression of an explicit item",
              refused(engine, suppression, {**a, "cls": "explicit", "key": "9" * 64}) == "23514")
        state = ("INSERT INTO learner_memory_state (incarnation_id, user_id, enabled, version, updated_at)"
                 " VALUES (:inc, :user, true, :v, now())")
        with engine.begin() as conn:
            conn.execute(text(state), {**a, "v": 0})
        check("3 one state row per incarnation", refused(engine, state, {**a, "v": 1}) == "23505")
        check("3 version never negative", refused(engine, "UPDATE learner_memory_state SET version = -1", {})
              == "23514")

        try:
            command.downgrade(cfg_p, HEAD)
            check("4 downgrade refuses while memory rows exist", False)
        except RuntimeError:
            check("4 downgrade refuses while memory rows exist", True)
        with engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"DELETE FROM {table}"))
        command.downgrade(cfg_p, HEAD)
        check("4 downgrade restores 0033's schema", schema(engine) == before)
        command.upgrade(cfg_p, REV)
        check("4 upgrade again gives the same schema", schema(engine) == first)
    finally:
        shutil.rmtree(proposal_dir, ignore_errors=True)
    failed = [name for name, passed, _ in results if not passed]
    print(f"\n{len(results) - len(failed)} PASS, {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
