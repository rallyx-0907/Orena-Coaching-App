"""The continuous deletion journal: each account deletion is appended, as it happens, to a file outside the database
(D-054 precondition a; `ORENA_BACKBONE_INTEGRATION_GATES.md`).

`deletion_journal.export_deletions` is a point-in-time export. A database lost between a deletion and the next export
would lose the record of that deletion, and a restore would bring the account back. This log closes that window.

**The order is defined:**
1. An **intent** record is written and fsynced before the deletion's transaction commits. It names the account, its
   incarnations (ids, epochs, creation times) and the operation id.
2. A **done** record follows the commit.

A crash between the two leaves an intent with no done. `reconcile` settles it against the live database: the
incarnations deleted there mean the commit happened, so `done` is appended; still active means it rolled back, so
`abandoned` is appended. A replay uses **confirmed** operations only. An unconfirmed intent never deletes a live
account on restore.

The file is JSON Lines, append-only, opened per write. It holds opaque ids and times only, never an email, name or
content. Keep it beside the backups, outside the database, under the same access control.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_KIND = "orena.deletion_log"
LOG_VERSION = 1
LOG_ENV = "ORENA_DELETION_LOG"


class DeletionLogInvalid(ValueError):
    """A log that cannot be trusted is refused whole."""


def log_path(environ: Mapping[str, str] | None = None) -> Path | None:
    raw = str((os.environ if environ is None else environ).get(LOG_ENV, "")).strip()
    return Path(raw) if raw else None


def _append(path: Path, record: Mapping[str, Any]) -> None:
    """One line, flushed and fsynced before returning: on disk, not in a buffer."""
    path = Path(path)
    created = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"kind": LOG_KIND, "version": LOG_VERSION, **record}, ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    if created and hasattr(os, "O_DIRECTORY"):  # the new file's directory entry too (POSIX)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _iso(moment: datetime) -> str:
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def write_intent(path: Path, *, account_id: str, incarnations: list[Mapping[str, Any]], at: datetime) -> str:
    """Before the commit. Returns the operation id the done record names."""
    op = str(uuid.uuid4())
    _append(path, {"event": "intent", "op": op, "user_id": str(uuid.UUID(account_id)), "at": _iso(at),
                   "incarnations": [{"id": str(uuid.UUID(str(i["id"]))), "epoch": int(i["epoch"]),
                                     "created_at": _iso(i["created_at"])} for i in incarnations]})  # fmt: skip
    return op


def write_done(path: Path, op: str, *, deleted_at: datetime) -> None:
    _append(path, {"event": "done", "op": op, "deleted_at": _iso(deleted_at)})


def write_abandoned(path: Path, op: str) -> None:
    _append(path, {"event": "abandoned", "op": op})


def read_log(path: Path) -> dict[str, dict[str, Any]]:
    """op -> {"intent": ..., "done": ... | None, "abandoned": bool}. A malformed line refuses the whole log."""
    ops: dict[str, dict[str, Any]] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ops
    except OSError as error:
        raise DeletionLogInvalid(f"cannot read the deletion log: {error}") from None
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            raise DeletionLogInvalid(f"line {number} is not JSON") from None
        if record.get("kind") != LOG_KIND or record.get("version") != LOG_VERSION:
            raise DeletionLogInvalid(f"line {number} is not a version-{LOG_VERSION} deletion log record")
        op, event = str(record.get("op", "")), record.get("event")
        if event == "intent":
            if op in ops:
                raise DeletionLogInvalid(f"line {number}: operation {op} has two intents")
            ops[op] = {"intent": record, "done": None, "abandoned": False}
        elif event in ("done", "abandoned"):
            if op not in ops:
                raise DeletionLogInvalid(f"line {number}: {event} for an operation with no intent")
            if event == "done":
                ops[op]["done"] = record
            else:
                ops[op]["abandoned"] = True
        else:
            raise DeletionLogInvalid(f"line {number}: unknown event {event!r}")
    return ops


def pending(path: Path) -> list[str]:
    return [op for op, entry in read_log(path).items() if entry["done"] is None and not entry["abandoned"]]


def confirmed_journal(path: Path) -> dict[str, Any]:
    """The confirmed deletions as a `deletion_journal` body: what `reapply_deletions` makes hold after a restore.
    Refused while any intent is unsettled: run `reconcile` against the database the log was written for first."""
    from writing_coach.persistence.deletion_journal import journal

    ops = read_log(path)
    unsettled = [op for op, e in ops.items() if e["done"] is None and not e["abandoned"]]
    if unsettled:
        raise DeletionLogInvalid(f"{len(unsettled)} unsettled intent(s): reconcile the log first")
    records = [{"id": inc["id"], "user_id": e["intent"]["user_id"], "epoch": inc["epoch"],
                "created_at": inc["created_at"], "deleted_at": e["done"]["deleted_at"]}
               for e in ops.values() if e["done"] is not None for inc in e["intent"]["incarnations"]]  # fmt: skip
    return journal(records)


def confirmed_accounts(path: Path) -> list[str]:
    """Accounts with a confirmed deletion, in log order: whose owner-table rows a restore must delete again."""
    seen: dict[str, None] = {}
    for entry in read_log(path).values():
        if entry["done"] is not None:
            seen.setdefault(entry["intent"]["user_id"], None)
    return list(seen)


def reconcile(engine: Any, path: Path) -> dict[str, int]:
    """Settle every unsettled intent against the database it was written for: incarnations deleted there mean the
    commit happened (`done`); otherwise it rolled back (`abandoned`). Reads the database only."""
    from sqlalchemy import text

    summary = {"done": 0, "abandoned": 0}
    ops = read_log(path)
    with engine.connect() as conn:
        for op in pending(path):
            ids = [inc["id"] for inc in ops[op]["intent"]["incarnations"]]
            rows = conn.execute(text("SELECT status, deleted_at FROM account_incarnations WHERE id = ANY(CAST(:ids AS uuid[]))"),
                                {"ids": ids}).all()  # fmt: skip
            if ids and len(rows) == len(ids) and all(r[0] == "deleted" for r in rows):
                write_done(path, op, deleted_at=max(r[1] for r in rows))
                summary["done"] += 1
            else:
                write_abandoned(path, op)
                summary["abandoned"] += 1
    return summary
