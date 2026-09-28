"""Shared cross-lane lock for live-provider (real, billed API) runs.

Orena's agent lanes -- Grammar Lab, Claude Code, Codex, Orena Intelligence --
run as separate processes under the same Windows user account on one
machine and can each make real, billed calls to shared external AI
providers. A lane that starts a live run without checking risks stacking its
spend and its rate-limit pressure on top of another lane's live session.

This lock is a plain file coordination mechanism only. It never inspects or
touches Docker or any container -- a lane must never be able to stop another
lane's container, even by accident, and this module has no way to.

Lock file (one JSON object), by default at
``%USERPROFILE%\\.orena\\live-provider.lock``::

    {"lane": "<name>", "pid": <int>, "acquired_at": "<ISO 8601 UTC>",
     "cost_ceiling_usd": <float>}

This is the format every lane should write and read so the lock means the
same thing to all of them; see ``grammar_lab/sandbox/README.md``.

Usage as a CLI, from a runner script::

    python live_provider_lock.py acquire --lane grammar-lab --pid $$ \\
        --cost-ceiling-usd 0.05
    python live_provider_lock.py release --lane grammar-lab --pid $$

``acquire`` waits for a live (non-orphaned) lock held by another lane,
re-checking every ``--poll-seconds`` up to ``--wait-max-seconds``, then
exits 1 and reports the holder. A lock whose PID is no longer running, or
whose ``acquired_at`` is older than ``--stale-seconds``, is an orphan: it is
removed and reported, and acquisition retries immediately.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class LockInfo:
    lane: str
    pid: int
    acquired_at: str
    cost_ceiling_usd: float


class LiveProviderLockTimeout(RuntimeError):
    def __init__(self, holder: LockInfo, waited_seconds: float) -> None:
        self.holder = holder
        self.waited_seconds = waited_seconds
        super().__init__(
            f"timed out after {waited_seconds:.0f}s waiting for live-provider.lock "
            f"held by lane={holder.lane} pid={holder.pid} since {holder.acquired_at}"
        )


def default_lock_path() -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(home) / ".orena" / "live-provider.lock"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock(path: Path) -> LockInfo | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(raw)
    return LockInfo(
        lane=data["lane"],
        pid=data["pid"],
        acquired_at=data["acquired_at"],
        cost_ceiling_usd=data["cost_ceiling_usd"],
    )


def _try_create(path: Path, info: LockInfo) -> bool:
    payload = {
        "lane": info.lane,
        "pid": info.pid,
        "acquired_at": info.acquired_at,
        "cost_ceiling_usd": info.cost_ceiling_usd,
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return True


def _remove_if_matches(path: Path, expected: LockInfo) -> None:
    current = _read_lock(path)
    if current == expected:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _orphan_reason(
    info: LockInfo,
    *,
    stale_seconds: float,
    pid_alive: Callable[[int], bool],
) -> str | None:
    if not pid_alive(info.pid):
        return "dead-pid"
    age = (datetime.now(UTC) - datetime.fromisoformat(info.acquired_at)).total_seconds()
    if age > stale_seconds:
        return "stale"
    return None


def acquire(
    lane: str,
    cost_ceiling_usd: float,
    *,
    path: Path | None = None,
    pid: int | None = None,
    wait_max_seconds: float = 1800.0,
    poll_seconds: float = 30.0,
    stale_seconds: float = 3600.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pid_alive: Callable[[int], bool] = _pid_alive,
    on_orphan_removed: Callable[[LockInfo, str], None] | None = None,
) -> LockInfo:
    path = path or default_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    mine = LockInfo(lane=lane, pid=pid if pid is not None else os.getpid(), acquired_at=_utc_now_iso(), cost_ceiling_usd=cost_ceiling_usd)
    start = clock()
    while True:
        if _try_create(path, mine):
            return mine
        existing = _read_lock(path)
        if existing is None:
            continue  # raced with another releaser/acquirer; retry immediately
        reason = _orphan_reason(existing, stale_seconds=stale_seconds, pid_alive=pid_alive)
        if reason is not None:
            _remove_if_matches(path, existing)
            if on_orphan_removed is not None:
                on_orphan_removed(existing, reason)
            mine = replace(mine, acquired_at=_utc_now_iso())
            continue
        elapsed = clock() - start
        if elapsed >= wait_max_seconds:
            raise LiveProviderLockTimeout(existing, elapsed)
        sleep(poll_seconds)


def release(lane: str, *, path: Path | None = None, pid: int | None = None) -> bool:
    path = path or default_lock_path()
    pid = pid if pid is not None else os.getpid()
    existing = _read_lock(path)
    if existing is None or existing.lane != lane or existing.pid != pid:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--lane", required=True)
    acquire_parser.add_argument("--cost-ceiling-usd", required=True, type=float)
    acquire_parser.add_argument("--pid", type=int, default=None)
    acquire_parser.add_argument("--wait-max-seconds", type=float, default=1800.0)
    acquire_parser.add_argument("--poll-seconds", type=float, default=30.0)
    acquire_parser.add_argument("--stale-seconds", type=float, default=3600.0)

    release_parser = sub.add_parser("release")
    release_parser.add_argument("--lane", required=True)
    release_parser.add_argument("--pid", type=int, default=None)

    args = parser.parse_args(argv)

    if args.command == "acquire":
        def report_orphan(existing: LockInfo, reason: str) -> None:
            print(
                f"orphan lock removed: lane={existing.lane} pid={existing.pid} "
                f"acquired_at={existing.acquired_at} reason={reason}"
            )

        try:
            info = acquire(
                args.lane,
                args.cost_ceiling_usd,
                path=default_lock_path(),
                pid=args.pid,
                wait_max_seconds=args.wait_max_seconds,
                poll_seconds=args.poll_seconds,
                stale_seconds=args.stale_seconds,
                on_orphan_removed=report_orphan,
            )
        except LiveProviderLockTimeout as exc:
            print(f"TIMEOUT: {exc}")
            return 1
        print(f"lock acquired: lane={info.lane} pid={info.pid} cost_ceiling_usd={info.cost_ceiling_usd}")
        return 0

    released = release(args.lane, path=default_lock_path(), pid=args.pid)
    print("lock released" if released else "lock not held by this lane/pid; left untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
