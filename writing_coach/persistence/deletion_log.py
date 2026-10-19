"""The continuous deletion journal: each account deletion is appended, as it happens, to a file outside the database
(D-054 precondition a; `ORENA_BACKBONE_INTEGRATION_GATES.md`).

`deletion_journal.export_deletions` is a point-in-time export. A database lost between a deletion and the next export
would lose the record of that deletion, and a restore would bring the account back. This log closes that window.

**The order is defined.**
- An **intent** record is written and fsynced before the deletion's transaction commits. It names the account, the
  incarnations this deletion changes (ids, epochs, creation times) and the operation id.
- A **done** record follows the commit.

**A crash between the two** leaves an intent with no done:
- **On the live database,** `reconcile(..., live=True)` settles it. Incarnations deleted there mean the commit
  happened, so it appends `done`. Still active means it rolled back, so it appends `abandoned`.
- **After the database was lost,** the database cannot answer. A restore predates the deletion, so its incarnations
  look active, and reconciling against it would wrongly abandon a committed deletion. `reconcile` therefore refuses
  unless the operator states the database is the live one. A restore takes the unsettled intent as confirmed instead,
  once the operator acknowledges it (`accept_unsettled`): the learner asked for the deletion, so applying it is the
  safe direction.
- **A torn record** (a crash part-way through writing an intent) is dropped. That write never finished, so its
  transaction never committed. The next write starts on its own line.

The file is JSON Lines and append-only. Writers take a lock file, so the operator tool and `reconcile` never
interleave. It holds opaque ids and times only, never an email, name or content.

**Where it lives:** outside the database's own volume, copied off-host together with the backups, under the same
access control. A log on the database's disk is lost with it. fsync guarantees are weak on network filesystems.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_KIND = "orena.deletion_log"
LOG_VERSION = 1
LOG_ENV = "ORENA_DELETION_LOG"

try:  # the platform is chosen once, outside any lock context
    import fcntl

    _POSIX = True
except ImportError:  # Windows
    import msvcrt

    _POSIX = False


class DeletionLogInvalid(ValueError):
    """A log that cannot be trusted is refused whole."""


def log_path(environ: Mapping[str, str] | None = None) -> Path | None:
    raw = str((os.environ if environ is None else environ).get(LOG_ENV, "")).strip()
    return Path(raw) if raw else None


_held: dict[str, int] = {}  # paths whose lock this process holds (re-entrant: a nested append must not deadlock)
_held_guard = threading.Lock()


def _lock_file(handle: Any) -> None:
    if _POSIX:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    else:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)


def _unlock_file(handle: Any) -> None:
    if _POSIX:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    else:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def held(path: Path) -> Iterator[None]:
    """An exclusive lock on `<log>.lock` for the whole block, re-entrant within this process. The deletion tool holds it
    from its intent through its done record, and `reconcile` for its whole run, so neither sees the other half-way."""
    key = str(Path(path).resolve())
    with _held_guard:
        nested = _held.get(key, 0) > 0
        _held[key] = _held.get(key, 0) + 1
    try:
        if nested:
            yield
            return
        lock = Path(str(path) + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with open(lock, "a+b") as handle:
            _lock_file(handle)
            try:
                yield
            finally:
                _unlock_file(handle)
    finally:
        with _held_guard:
            _held[key] -= 1


def _append(path: Path, record: Mapping[str, Any]) -> None:
    """One line, flushed and fsynced before returning: on disk, not in a buffer."""
    path = Path(path)
    line = json.dumps({"kind": LOG_KIND, "version": LOG_VERSION, **record}, ensure_ascii=False, sort_keys=True)
    with held(path):
        created = not path.exists()
        # A torn last line (a crash mid-write) has no newline: start on a fresh line, never glue onto it.
        torn = not created and path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(("\n" if torn else "") + line + "\n")
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
    """Before the commit. `incarnations`: the ones THIS deletion changes. Returns the operation id."""
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
    """op -> {"intent", "done" | None, "abandoned"}. A record torn by a crash (a `{...` line that does not parse) is
    dropped: that write never finished, and every later write starts on its own line. Anything else malformed - a line
    that is not JSON at all, or JSON that is not a log record - refuses the whole log."""
    ops: dict[str, dict[str, Any]] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ops
    except OSError as error:
        raise DeletionLogInvalid(f"cannot read the deletion log: {error}") from None
    while lines and not lines[-1].strip():
        lines.pop()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            if line.lstrip().startswith("{"):
                continue  # a record torn by a crash mid-write: that write never finished, so its transaction never committed
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


def pending(path: Path) -> list[str]:  # intents with neither a done nor an abandoned
    return [op for op, entry in read_log(path).items() if entry["done"] is None and not entry["abandoned"]]


def confirmed_operations(path: Path, *, accept_unsettled: bool = False) -> list[dict[str, Any]]:
    """The deletions to make hold after a restore: {op, user_id, incarnations, deleted_at}, in log order.

    An unsettled intent refuses, unless the operator accepts it: then it counts as confirmed, at its intent's time,
    because after a database loss nothing can show the commit did not happen."""
    out: list[dict[str, Any]] = []
    unsettled = 0
    for op, entry in read_log(path).items():
        if entry["abandoned"] and entry["done"] is None:  # a done beats an abandoned: the commit is a fact
            continue
        if entry["done"] is None:
            unsettled += 1
            if not accept_unsettled:
                continue
        intent = entry["intent"]
        out.append({"op": op, "user_id": intent["user_id"], "incarnations": intent["incarnations"],
                    "deleted_at": (entry["done"] or {}).get("deleted_at") or intent["at"]})  # fmt: skip
    if unsettled and not accept_unsettled:
        raise DeletionLogInvalid(f"{unsettled} unsettled intent(s): reconcile against the live database, or, after a "
                                 "database loss, accept them as confirmed")  # fmt: skip
    return out


def confirmed_journal(path: Path, *, accept_unsettled: bool = False) -> dict[str, Any]:
    """The confirmed deletions as a `deletion_journal` body for `reapply_deletions`. One record per incarnation: a
    deletion applied twice keeps the earliest time (as `deletion_journal.merge`)."""
    from writing_coach.persistence.deletion_journal import journal

    by_id: dict[str, dict[str, Any]] = {}
    for operation in confirmed_operations(path, accept_unsettled=accept_unsettled):
        for inc in operation["incarnations"]:
            record = {"id": inc["id"], "user_id": operation["user_id"], "epoch": inc["epoch"],
                      "created_at": inc["created_at"], "deleted_at": operation["deleted_at"]}  # fmt: skip
            prior = by_id.get(inc["id"])
            if prior is None or datetime.fromisoformat(record["deleted_at"]) < datetime.fromisoformat(prior["deleted_at"]):
                by_id[inc["id"]] = record
    return journal(by_id.values())


def reconcile(engine: Any, path: Path, *, live: bool) -> dict[str, int]:
    """Settle every unsettled intent against THE LIVE database it was written for: incarnations deleted there mean the
    commit happened (`done`); otherwise it rolled back (`abandoned`). Refused unless `live` - a restored database
    would show a committed deletion as never made. Reads the database only."""
    from sqlalchemy import text

    if not live:
        raise DeletionLogInvalid("reconcile only against the live database it was written for (live=True); "
                                 "after a database loss, accept unsettled intents instead")  # fmt: skip
    summary = {"done": 0, "abandoned": 0}
    with held(path), engine.connect() as conn:  # no deletion is between its intent and its done meanwhile
        ops = read_log(path)
        for op in [o for o, e in ops.items() if e["done"] is None and not e["abandoned"]]:
            ids = [inc["id"] for inc in ops[op]["intent"]["incarnations"]]
            rows = conn.execute(text("SELECT status, deleted_at FROM account_incarnations"
                                     " WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}).all()  # fmt: skip
            if ids and len(rows) == len(ids) and all(r[0] == "deleted" for r in rows):
                write_done(path, op, deleted_at=max(r[1] for r in rows))
                summary["done"] += 1
            elif not ids:
                # A deletion that changed no incarnation (all were deleted before): the database cannot tell; the
                # owner rows are what it removed, so keep it - applying a requested deletion again is the safe side.
                write_done(path, op, deleted_at=datetime.fromisoformat(ops[op]["intent"]["at"]))
                summary["done"] += 1
            else:
                write_abandoned(path, op)
                summary["abandoned"] += 1
    return summary
