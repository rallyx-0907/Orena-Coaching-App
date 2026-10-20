"""Rename a Reading source's public name, or archive it, as the Admin source routes do (PR BU). Dry run by default.

    python scripts/reading_source_admin.py --source sample-voa-learning-english --public-name "VOA Learning English" --actor X
    python scripts/reading_source_admin.py --source sample-zh-wikinews --archive --actor X --apply

`--public-name` calls `ReadingContentRepository.set_source_public_name`, the function behind
`POST /api/admin/reading/sources/{id}/public-name` (D-192: the publisher name learners see; each published text's
`content_revision` moves so cached copies refetch). `--archive` calls `set_source_state(id, "archived")`, the function
behind `POST /api/admin/reading/sources/{id}` with state `archived`: the existing lifecycle state (polling stops), never a
delete; the source's texts are not touched. Each change is recorded in `audit_logs` with the route's own event
(`admin.reading_source_public_name` / `admin.reading_source_state`), the `--actor` and `via: scripts/reading_source_admin.py`.
A change that is already in place writes nothing and records nothing.

`--source` is a source id or slug. The source's internal `name` (the operator's label, e.g. "[Mẫu kiểm thử] ...") is not
what learners see and no Admin route renames it; `--public-name` sets the learner-facing name.

Output: one JSON report (`changes`, `written`, the source before and after). Never prints the database URL.
Exit code: 0 done (or nothing to do); 1 a dry run found a change to make; 2 refused (unknown source, nothing asked).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.operator_cli import OperatorRefused, audit_recorder, database_url, emit, refused, require_actor  # noqa: E402

SCRIPT = "scripts/reading_source_admin.py"
ARCHIVED = "archived"


def find_source(repository: Any, key: str) -> dict[str, Any]:
    key = key.strip()
    found = repository.get_source(key)
    if found is None:
        found = next((source for source in repository.list_sources() if source.get("slug") == key), None)
    if found is None:
        raise OperatorRefused("source_not_found", f"{key[:80]!r} is not in the registry")
    return found


def _view(source: dict[str, Any]) -> dict[str, Any]:
    return {key: source.get(key) for key in ("id", "slug", "name", "public_name", "state", "polling_enabled")}


def run(repository: Any, *, source_key: str, public_name: str | None, archive: bool, apply: bool, actor: str,
        record_event: Any = None) -> tuple[dict[str, Any], int]:
    if public_name is None and not archive:
        raise OperatorRefused("nothing_asked", "pass --public-name and/or --archive")
    if public_name is not None and not public_name.strip():
        raise OperatorRefused("public_name_empty")
    if apply and record_event is None:
        raise OperatorRefused("audit_unavailable")
    source = find_source(repository, source_key)
    before = _view(source)
    changes: list[dict[str, Any]] = []
    if public_name is not None and public_name.strip() != (source.get("public_name") or ""):
        changes.append({"change": "public_name", "from": source.get("public_name") or "", "to": public_name.strip()})
    if archive and source.get("state") != ARCHIVED:
        changes.append({"change": "state", "from": source.get("state"), "to": ARCHIVED})
    written = 0
    if apply:
        for change in changes:
            if change["change"] == "public_name":
                updated = repository.set_source_public_name(source["id"], change["to"])
                if updated is None:
                    raise OperatorRefused("source_not_found", source["id"])
                record_event("admin.reading_source_public_name", actor_key=actor, entity_type="reading_source",
                             entity_id=source["id"], payload={"public_name": updated["public_name"], "via": SCRIPT, "actor": actor})
            else:
                updated = repository.set_source_state(source["id"], ARCHIVED, actor=actor)
                if updated is None:
                    raise OperatorRefused("source_not_found", source["id"])
                record_event("admin.reading_source_state", actor_key=actor, entity_type="reading_source",
                             entity_id=source["id"], payload={"state": ARCHIVED, "via": SCRIPT, "actor": actor})
            change["outcome"] = "written"
            written += 1
        source = repository.get_source(source["id"]) or source
    else:
        for change in changes:
            change["outcome"] = "would_write"
    report = {"script": SCRIPT, "mode": "apply" if apply else "dry_run", "actor": actor,
              "changes": len(changes), "written": written, "before": before, "after": _view(source), "items": changes}
    return report, (1 if not apply and changes else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--source", required=True, help="source id or slug")
    parser.add_argument("--public-name", default=None, help="the publisher name learners see")
    parser.add_argument("--archive", action="store_true", help="set the lifecycle state to archived (never a delete)")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--actor", default="", help="who is acting; recorded in audit_logs")
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    try:
        actor = require_actor(args.actor)
        from sqlalchemy import create_engine

        from writing_coach.persistence.reading_content_repository import ReadingContentRepository

        engine = create_engine(database_url(args.url))
        report, code = run(ReadingContentRepository(engine), source_key=args.source, public_name=args.public_name,
                           archive=args.archive, apply=args.apply, actor=actor,
                           record_event=audit_recorder(engine) if args.apply else None)
    except Exception as error:  # noqa: BLE001 - OperatorRefused prints its code; anything else only its kind
        return refused(SCRIPT, error)
    emit(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
