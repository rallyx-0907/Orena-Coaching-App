"""One-time operator import of the shared media index into PostgreSQL (D-108.5; MEDIA_METADATA_POSTGRES.md rev 2, section 5).

NOT run by the application, at startup, or by Alembic (ARCHITECTURE_INVARIANTS: no startup import). An operator runs it once,
under the human's gate, after migration 20261001_0024 is applied and the app is confirmed stopped:

    python scripts/import_media_index.py --index data/media_library/index.json --assets data/media_library_assets \
        --database-url postgresql+psycopg://... --report-dir /safe/place                 # dry-run (the default)
    python scripts/import_media_index.py ... --apply                                      # writes
    python scripts/import_media_index.py ... --verify-only                                # compares, writes nothing

Behaviour:
- Dry-run is the default and touches nothing but its report. The index file is evidence: it is never repaired, and ANY invalid
  entry, a failed integrity hash, a duplicate id, an over-long bounded field or a lesson whose payload
  is not an object aborts before anything is written.
- `--apply` REFUSES unless `media_entries` is empty AND the single-use marker is absent. After cutover learners delete
  uploads while the archive still holds them; a re-run would resurrect their metadata. `--verify-only` is the way to check
  later; it writes nothing.
- A personal entry with no `source.owner` is imported under the explicit legacy owner token (the implicit rule made
  explicit; the count is reported; whether to keep or delete such rows is the human's call, Q4).
- `stored_bytes` of an upload is read from the asset store with a size lookup (`stat`, never the bytes): the original's key
  comes from `playback.url`, the thumbnail's from `thumbnail.ref`. A missing asset gives NULL and is listed; nothing is deleted.
- The index file's size and SHA-256 are recorded at the start and re-checked at the end; a change aborts the run.
- After the bulk insert it runs ANALYZE on both tables.

Exit code 0 only when the verification is exact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.book_asset_store import _validate_key  # noqa: E402
from writing_coach.media_library_store import MediaLibraryEntry, validate_entry  # noqa: E402
from writing_coach.persistence.media_library_repository import (  # noqa: E402
    LEGACY_OWNER_TOKEN,
    PostgresMediaLibraryRepository,
    entry_to_row,
    lesson_parts,
    owner_of,
    row_to_entry,
)

MARKER_NAME = "media_index_import.marker.json"
FILES_PREFIX = "/api/media/files/"
BATCH = 1000
LIMITS = {"media_id": 256, "provider": 256, "provider_media_id": 256, "language": 20, "level": 16}
TOPIC_MAX = 64


class ImportAborted(Exception):
    """Something makes the import unsafe. Nothing has been written."""


def file_fingerprint(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def canonical_entry(entry: MediaLibraryEntry) -> dict[str, Any]:
    """The comparable form: created_at as an instant (the stored spelling may differ), everything else verbatim."""
    value = asdict(entry)
    value["created_at"] = datetime.fromisoformat(entry.created_at.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    return value


def canonical_hash(entries: list[MediaLibraryEntry]) -> str:
    body = json.dumps([canonical_entry(e) for e in sorted(entries, key=lambda e: e.media_id)],
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def load_index(path: Path) -> tuple[list[MediaLibraryEntry], dict[str, Any]]:
    """Strict read of the legacy file. Raises ImportAborted on anything not exactly valid."""
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        body = payload["entries"]
        expected = payload["integrity"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ImportAborted(f"index unreadable: {type(error).__name__}") from error
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if not isinstance(body, list) or hashlib.sha256(canonical).hexdigest() != expected:
        raise ImportAborted("integrity hash mismatch")
    entries: list[MediaLibraryEntry] = []
    for position, item in enumerate(body):
        try:
            entry = validate_entry(MediaLibraryEntry(**item))
        except (TypeError, ValueError) as error:
            raise ImportAborted(f"entry {position} invalid: {error}") from error
        for name, limit in LIMITS.items():
            if len(getattr(entry, name)) > limit:
                raise ImportAborted(f"entry {entry.media_id}: {name} longer than {limit}")
        if entry.lesson is not None:
            if "payload" in entry.lesson and not isinstance(entry.lesson["payload"], dict):
                raise ImportAborted(f"entry {entry.media_id}: lesson.payload is not an object")
            try:
                json.dumps(entry.lesson)
            except (TypeError, ValueError) as error:
                raise ImportAborted(f"entry {entry.media_id}: lesson is not JSON: {error}") from error
            if len(str(entry.lesson.get("topic") or "")) > TOPIC_MAX:
                raise ImportAborted(f"entry {entry.media_id}: topic longer than {TOPIC_MAX}")
        entries.append(entry)
    if len({e.media_id for e in entries}) != len(entries):
        raise ImportAborted("duplicate media_id")
    return entries, {"entries": len(entries), **file_fingerprint(path)}


def asset_size(root: Path, key: str) -> int | None:
    """Size of a stored asset by `stat` (never its bytes); None if absent. Same key validation as the asset store."""
    try:
        path = root.joinpath(*_validate_key(key)).resolve()
        path.relative_to(root.resolve())
        return path.stat().st_size
    except (OSError, ValueError, Exception):  # noqa: BLE001 - an invalid or missing key is "no asset", reported
        return None


def stored_bytes_for(entry: MediaLibraryEntry, root: Path, missing: list[str]) -> int | None:
    if entry.provider != "upload":
        return None
    total, absent = 0, False
    url = entry.playback.get("url", "")
    keys = [url[len(FILES_PREFIX):]] if url.startswith(FILES_PREFIX) else []
    if entry.thumbnail["kind"] == "asset" and entry.thumbnail["ref"]:
        keys.append(entry.thumbnail["ref"])
    for key in keys:
        size = asset_size(root, key)
        if size is None:
            missing.append(f"{entry.media_id}: {key}")
            absent = True
        else:
            total += size
    return None if absent or not keys else total


def asset_report(entries: list[MediaLibraryEntry], root: Path) -> list[str]:
    """Every asset the entries point at (thumbnail refs and playback paths under /api/media/files/) that is not there."""
    missing: list[str] = []
    for entry in entries:
        keys = []
        if entry.thumbnail["kind"] == "asset":
            keys.append(entry.thumbnail["ref"])
        if entry.playback.get("url", "").startswith(FILES_PREFIX):
            keys.append(entry.playback["url"][len(FILES_PREFIX):])
        for key in keys:
            if asset_size(root, key) is None:
                missing.append(f"{entry.media_id}: {key}")
    return missing


_INSERT = text(
    """
    INSERT INTO media_entries (media_id, library, status, media_type, provider, provider_media_id, canonical_url, title,
        creator, duration_ms, language, level, playback, thumbnail_kind, thumbnail_ref, source, owner_token, lesson_meta,
        lesson_id, topic, tags, has_lesson, segment_count, stored_bytes, created_at, updated_at)
    VALUES (:media_id, :library, :status, :media_type, :provider, :provider_media_id, :canonical_url, :title,
        :creator, :duration_ms, :language, :level, CAST(:playback AS JSONB), :thumbnail_kind, :thumbnail_ref,
        CAST(:source AS JSONB), :owner_token, CAST(:lesson_meta AS JSONB), :lesson_id, :topic, CAST(:tags AS JSONB), :has_lesson, :segment_count,
        :stored_bytes, :created_at, :created_at)
    ON CONFLICT (media_id) DO NOTHING
    """
)
_INSERT_PAYLOAD = text(
    "INSERT INTO media_entry_payloads (media_id, payload) VALUES (:media_id, CAST(:payload AS JSONB))"
    " ON CONFLICT (media_id) DO NOTHING"
)


def insert_all(engine, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        with engine.begin() as connection:
            result = connection.execute(_INSERT, chunk)
            inserted += result.rowcount if result.rowcount and result.rowcount > 0 else 0
            payloads = [{"media_id": r["media_id"], "payload": r["payload"]} for r in chunk if r["payload"] is not None]
            if payloads:
                connection.execute(_INSERT_PAYLOAD, payloads)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("ANALYZE media_entries"))
        connection.execute(text("ANALYZE media_entry_payloads"))
    return inserted


def verify(engine, entries: list[MediaLibraryEntry], asset_root: Path) -> dict[str, Any]:
    """Every row read back through the repository equals the file's entry; counts per (library, language, status)."""
    repository = PostgresMediaLibraryRepository(engine)
    problems: list[str] = []
    rebuilt: list[MediaLibraryEntry] = []
    for entry in entries:
        got = repository.get(entry.media_id, with_payload=True)
        if got is None:
            problems.append(f"missing row {entry.media_id}")
            continue
        rebuilt.append(got)
        expected = canonical_entry(entry)
        actual = canonical_entry(got)
        # the explicit legacy owner is the only intended difference from the file
        if expected != actual:
            problems.append(f"row differs {entry.media_id}")
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT count(*) FROM media_entries")).scalar()
        personal_unowned = connection.execute(
            text("SELECT count(*) FROM media_entries WHERE library = 'personal' AND owner_token IS NULL")
        ).scalar()
        by_group = {
            f"{r[0]}/{r[1]}/{r[2]}": r[3]
            for r in connection.execute(
                text("SELECT library, language, status, count(*) FROM media_entries GROUP BY 1,2,3")
            )
        }
    expected_groups = Counter(f"{e.library}/{e.language}/{e.status}" for e in entries)
    return {
        "rows": rows,
        "expected_rows": len(entries),
        "count_ok": rows == len(entries),
        "groups_ok": dict(expected_groups) == by_group,
        "hash_ok": len(rebuilt) == len(entries) and canonical_hash(rebuilt) == canonical_hash(entries),
        "personal_without_owner": personal_unowned,
        "problems": problems[:20],
        "problem_count": len(problems),
        "ok": not problems and rows == len(entries) and dict(expected_groups) == by_group and personal_unowned == 0,
    }


def lesson_duplicates(entries: list[MediaLibraryEntry]) -> list[str]:
    counts = Counter(
        lesson_parts(e)["lesson_id"] for e in entries if e.library == "shared" and lesson_parts(e)["lesson_id"]
    )
    return sorted(key for key, count in counts.items() if count > 1)


def run(
    engine,
    index_path: Path,
    asset_root: Path,
    report_dir: Path,
    *,
    apply: bool = False,
    verify_only: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    report: dict[str, Any] = {"mode": "verify-only" if verify_only else "apply" if apply else "dry-run"}
    entries, fingerprint = load_index(index_path)
    report["index"] = fingerprint
    marker = report_dir / MARKER_NAME
    report_dir.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    rows = []
    for entry in entries:
        stored = stored_bytes_for(entry, asset_root, missing)
        rows.append(entry_to_row(entry, stored_bytes=stored))
    report["missing_upload_assets"] = missing
    report["missing_assets"] = asset_report(entries, asset_root)
    report["counts"] = {
        "entries": len(entries),
        "shared": sum(e.library == "shared" for e in entries),
        "personal": sum(e.library == "personal" for e in entries),
        "legacy_owner_rows": sum(e.library == "personal" and not e.source.get("owner") for e in entries),
        "with_lesson": sum(e.lesson is not None for e in entries),
        "upload_bytes": sum(r["stored_bytes"] or 0 for r in rows),
    }
    report["lesson_id_duplicates"] = lesson_duplicates(entries)
    report["legacy_owner_token"] = LEGACY_OWNER_TOKEN
    with engine.connect() as connection:
        existing = connection.execute(text("SELECT count(*) FROM media_entries")).scalar()
    report["existing_rows"] = existing

    if verify_only:
        report["verification"] = verify(engine, entries, asset_root)
        report["ok"] = report["verification"]["ok"]
    elif not apply:
        report["ok"] = True
    else:
        if existing:
            raise ImportAborted(f"REFUSED: media_entries already holds {existing} rows; the import runs once, on an empty table")
        if marker.exists():
            raise ImportAborted(f"REFUSED: the single-use marker {marker} exists; this import already ran")
        if report["lesson_id_duplicates"]:
            raise ImportAborted(f"duplicate shared lesson_id values {report['lesson_id_duplicates'][:5]} would violate the unique index")
        report["inserted"] = insert_all(engine, rows)
        report["verification"] = verify(engine, entries, asset_root)
        after = file_fingerprint(index_path)
        report["index_unchanged"] = after == {"size": fingerprint["size"], "sha256": fingerprint["sha256"]}
        report["ok"] = bool(report["verification"]["ok"] and report["index_unchanged"] and report["inserted"] == len(entries))
        if report["ok"]:
            marker.write_text(json.dumps({
                "index_sha256": fingerprint["sha256"], "entries": len(entries),
                "at": datetime.now(UTC).isoformat(),
            }), encoding="utf-8")
    report["seconds"] = round(time.monotonic() - started, 3)
    (report_dir / f"media_index_import.{report['mode']}.report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--database-url", required=True, help="explicit; POSTGRES_RUNTIME_URL is never read implicitly")
    parser.add_argument("--report-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url)
    try:
        report = run(engine, args.index, args.assets, args.report_dir, apply=args.apply, verify_only=args.verify_only)
    except ImportAborted as error:
        print(f"ABORTED: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
