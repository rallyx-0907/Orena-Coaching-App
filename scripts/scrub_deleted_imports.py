"""Scrub the content of private imports that were deleted before the tombstone fix (D4 I12; human-approved).

Before `a13e0a3` a deleted import kept its whole payload (title, text, link) in the `works` row and
`GET /api/works/{id}` served it. The fix tombstones new deletions; this script erases what the earlier ones left.

What it does, and only this: for every `works` row with `kind = 'imported'` and `lifecycle = 'deleted'` whose payload
holds anything beyond the tombstone keys `{id, form, ref}`, it rewrites the payload to `{id, form}` plus, for a link or a file, a hash reference (`ref`) so devices can tell which import it was. Kept: the row,
its version, sequence and timestamps (so no sync client sees a change), the source reference and the client id - the
audit-safe metadata that integrity and history need. Dropped: title, text, url and anything else in the payload.

It is idempotent (a scrubbed row is skipped the next time), DRY-RUN BY DEFAULT (`--apply` writes), one transaction, and
it prints counts only - never a title, text, link or connection string. It also reports, without changing them:
  * `mutation_receipts` / `change_records`: whether any column of either could hold content (they hold ids, versions
    and a digest, not payloads);
  * records DERIVED from a deleted import's text - annotations (highlight excerpts), typed responses and saved places
    that name it - as counts, for the human to decide; the approval covers the import payload only.

    python scripts/scrub_deleted_imports.py              # dry run against POSTGRES_RUNTIME_URL
    python scripts/scrub_deleted_imports.py --apply
    python scripts/scrub_deleted_imports.py --url postgresql+psycopg://... --apply

Take a backup first (`scripts/staging_backup.ps1 -Postgres <container>`). Production and preview are not operated by
this repository's agents: the operator chooses the URL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TOMBSTONE_KEYS = {"id", "form", "ref"}
# Columns of these tables that are identifiers, versions, times and a digest - never content.
SAFE_RECEIPT_COLUMNS = {
    "mutation_receipts": {"id", "incarnation_id", "language_code", "domain", "resource_id", "operation_id", "request_digest",
                          "expected_version", "result_ref", "committed_version", "sequence", "created_at"},
    "change_records": {"id", "incarnation_id", "sequence", "language_code", "object_domain", "object_id", "object_version",
                       "change_kind", "created_at"},
}


def tombstone_of(payload: Any) -> dict[str, str]:
    """What is left of an import payload: its client id and its form, nothing else."""
    body = payload if isinstance(payload, dict) else {}
    form = str(body.get("form") or "text")
    tomb = {"id": str(body.get("id") or ""), "form": form}
    reference = str(body.get("mediaId") or "") if form == "upload" else str(body.get("url") or "") if form == "url" else ""
    if reference:  # a content-free reference, the same as writing_coach.account_records_api.import_ref
        tomb["ref"] = hashlib.sha256(f"orena.import-ref:{form}:{reference}".encode()).hexdigest()
    return tomb


def needs_scrub(payload: Any) -> bool:
    return not isinstance(payload, dict) or bool(set(payload) - TOMBSTONE_KEYS)


def receipt_columns_holding_content(conn) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for table, safe in SAFE_RECEIPT_COLUMNS.items():
        rows = conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t AND table_schema = current_schema()"),
            {"t": table},
        ).scalars().all()
        found[table] = sorted(set(rows) - safe)
    return found


def scrub(engine: Engine, *, apply: bool = False) -> dict[str, Any]:
    """Count (and, with `apply`, erase). Returns counts only."""
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, payload, source_id FROM works WHERE kind = 'imported' AND lifecycle = 'deleted' ORDER BY id")
        ).mappings().all()
        dirty = [row for row in rows if needs_scrub(row["payload"])]
        public_ids = {f"{tombstone_of(row['payload'])['form']}:{tombstone_of(row['payload'])['id']}" for row in rows}
        public_ids |= {str(row["source_id"]) for row in rows if row["source_id"]}
        if apply:
            for row in dirty:
                conn.execute(
                    text("UPDATE works SET payload = CAST(:payload AS JSON) WHERE id = :id AND kind = 'imported' AND lifecycle = 'deleted'"),
                    {"payload": json.dumps(tombstone_of(row["payload"]), ensure_ascii=False), "id": row["id"]},
                )
        derived = {"annotations": 0, "responses": 0, "places": 0}
        if public_ids:
            ids = sorted(public_ids)
            derived["annotations"] = conn.execute(
                text("SELECT count(*) FROM works WHERE kind = 'annotation' AND lifecycle <> 'deleted' AND source_id = ANY(:ids)"),
                {"ids": ids},
            ).scalar_one()
            derived["responses"] = conn.execute(
                text("SELECT count(*) FROM works WHERE kind = 'response' AND lifecycle <> 'deleted' AND source_id = ANY(:ids)"),
                {"ids": ids},
            ).scalar_one()
            derived["places"] = conn.execute(
                text("SELECT count(*) FROM library_items WHERE place IS NOT NULL AND source_id = ANY(:ids)"), {"ids": ids}
            ).scalar_one()
        copies = receipt_columns_holding_content(conn)
        receipts = conn.execute(text("SELECT count(*) FROM mutation_receipts WHERE domain = 'imported'")).scalar_one()
        changes = conn.execute(text("SELECT count(*) FROM change_records WHERE object_domain = 'imported'")).scalar_one()
    return {
        "deleted_imports": len(rows),
        "with_content": len(dirty),
        "already_clean": len(rows) - len(dirty),
        "scrubbed": len(dirty) if apply else 0,
        "applied": apply,
        "receipts_for_imports": receipts,
        "change_records_for_imports": changes,
        "receipt_columns_that_could_hold_content": copies,
        "derived_records_left_untouched": derived,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the scrub (default: dry run)")
    parser.add_argument("--url", default="", help="SQLAlchemy URL (default: POSTGRES_RUNTIME_URL)")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("No database: pass --url or set POSTGRES_RUNTIME_URL.", file=sys.stderr)
        return 2
    engine = create_engine(url, future=True)
    try:
        report = scrub(engine, apply=args.apply)
    finally:
        engine.dispose()
    print("APPLIED" if args.apply else "DRY RUN (nothing written; pass --apply)")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
