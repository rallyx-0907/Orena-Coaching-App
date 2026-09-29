"""Shared cross-lane locks for live (real, billed) provider runs -- one lock per quota group.

Orena's agent lanes run as separate processes under the same Windows user account on one
machine and draw on the same provider quotas. Each quota group has its own lock file in
``%USERPROFILE%\\.orena\\``, so two lanes only wait on each other when they actually
compete for the same quota:

    live-gemini-text.lock   Gemini text models (Grammar Lab's evaluator engine is here)
    live-gemini-live.lock   Gemini Live
    live-deepseek.lock      DeepSeek

Groq has no lock yet. Each file is one JSON object, the format every lane writes and reads:

    {"lane": "<name>", "pid": <int>, "acquired_at": "<ISO 8601 UTC>",
     "heartbeat_at": "<ISO 8601 UTC>", "cost_ceiling_usd": <number>}

The holder rewrites ``heartbeat_at`` every 60 seconds while it holds the lock (see
``Heartbeat`` / the ``heartbeat`` CLI command). Whether a lock is an orphan depends on whose
it is:

* Another lane's lock is an orphan only when ``heartbeat_at`` is older than
  ``--stale-seconds`` (default 600 s). Its PID is never checked: a PID from another lane may
  be in another process namespace and cannot be checked reliably, and a lane's runner once
  had its lock deleted by a PID check that read "dead" for a live holder.
* This lane's own lock is an orphan when its PID is dead or ``heartbeat_at`` is older than
  ``--stale-seconds``.
* A lock in the old format, with no ``heartbeat_at``, falls back to ``acquired_at`` against
  ``--legacy-stale-seconds`` (default 3600 s), whoever owns it (PID only for its own lane).

A lane holds only the groups it uses. Groups are always taken in the fixed order
gemini-text -> gemini-live -> deepseek and released in reverse, so two lanes can never
each hold one lock the other is waiting for; failing to take one gives back every lock
already taken in that attempt.

A lock held by a live lane is re-checked every ``--poll-seconds`` up to
``--wait-max-seconds``, then acquisition stops and reports the holder's lane/PID. An orphan
(above) is removed, reported as ``orphan lock removed: lane=... reason=dead-pid|stale``, and
acquisition retries. While waiting for a later group, the locks already taken are heartbeated
at every poll. A lock is only ever released by the lane + PID that wrote it.

This is plain file coordination. The module never inspects or touches Docker or any
container -- it cannot spawn a process at all, so it cannot stop another lane's container.

CLI, from a runner script::

    python live_provider_lock.py acquire --lane grammar-lab --pid $$ \\
        --groups gemini-text,deepseek --cost-ceiling-usd 0.05
    python live_provider_lock.py heartbeat --lane grammar-lab --pid $$ \\
        --groups gemini-text,deepseek        # long-lived; run in the background
    python live_provider_lock.py release --lane grammar-lab --pid $$ \\
        --groups gemini-text,deepseek
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

GROUP_ORDER = ("gemini-text", "gemini-live", "deepseek")
HEARTBEAT_SECONDS = 60.0
STALE_SECONDS = 600.0
LEGACY_STALE_SECONDS = 3600.0


@dataclass(frozen=True)
class LockInfo:
    lane: str
    pid: int
    acquired_at: str
    cost_ceiling_usd: float
    heartbeat_at: str | None = None  # None only for a lock written in the old format


class LiveProviderLockTimeout(RuntimeError):
    def __init__(self, holder: LockInfo, waited_seconds: float, lock: Path) -> None:
        self.holder = holder
        self.waited_seconds = waited_seconds
        self.lock_name = lock.name
        super().__init__(
            f"timed out after {waited_seconds:.0f}s waiting for {lock.name} "
            f"held by lane={holder.lane} pid={holder.pid} since {holder.acquired_at}"
        )


def lock_dir() -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(home) / ".orena"


def lock_path(group: str, *, directory: Path | None = None) -> Path:
    if group not in GROUP_ORDER:
        raise ValueError(f"unknown quota group {group!r}; expected one of {list(GROUP_ORDER)}")
    return (directory or lock_dir()) / f"live-{group}.lock"


def _ordered(groups: Iterable[str]) -> list[str]:
    wanted = set(groups)
    unknown = wanted - set(GROUP_ORDER)
    if unknown:
        raise ValueError(f"unknown quota group(s) {sorted(unknown)}; expected any of {list(GROUP_ORDER)}")
    return [group for group in GROUP_ORDER if group in wanted]


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
        lane=data["lane"], pid=data["pid"], acquired_at=data["acquired_at"], cost_ceiling_usd=data["cost_ceiling_usd"],
        heartbeat_at=data.get("heartbeat_at"),
    )


def _payload(info: LockInfo) -> dict:
    payload = {
        "lane": info.lane, "pid": info.pid, "acquired_at": info.acquired_at, "cost_ceiling_usd": info.cost_ceiling_usd,
    }
    if info.heartbeat_at is not None:
        payload["heartbeat_at"] = info.heartbeat_at
    return payload


def _try_create(path: Path, info: LockInfo) -> bool:
    payload = _payload(info)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return True


def _remove_if_matches(path: Path, expected: LockInfo) -> None:
    if _read_lock(path) == expected:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _orphan_reason(
    info: LockInfo, *, lane: str, stale_seconds: float, legacy_stale_seconds: float, pid_alive: Callable[[int], bool],
) -> str | None:
    """Why ``info`` may be removed by ``lane``, or None. Another lane's PID is never checked."""
    if info.lane == lane and not pid_alive(info.pid):
        return "dead-pid"
    if info.heartbeat_at is not None:
        age = (datetime.now(UTC) - datetime.fromisoformat(info.heartbeat_at)).total_seconds()
        limit = stale_seconds
    else:
        age = (datetime.now(UTC) - datetime.fromisoformat(info.acquired_at)).total_seconds()
        limit = legacy_stale_seconds
    return "stale" if age > limit else None


def refresh_heartbeat(lane: str, *, path: Path, pid: int | None = None) -> bool:
    """Stamp ``heartbeat_at`` on this lane + PID's own lock; False if it is not ours (any more)."""
    pid = pid if pid is not None else os.getpid()
    try:
        existing = _read_lock(path)
    except (OSError, ValueError, KeyError):
        return False
    if existing is None or existing.lane != lane or existing.pid != pid:
        return False
    temp = path.with_name(f"{path.name}.{pid}.tmp")
    temp.write_text(json.dumps(_payload(replace(existing, heartbeat_at=_utc_now_iso()))), encoding="utf-8")
    try:
        os.replace(temp, path)
    except PermissionError:  # Windows: a reader has it open this instant; the next beat retries
        temp.unlink(missing_ok=True)
    return True


def acquire(
    lane: str,
    cost_ceiling_usd: float,
    *,
    path: Path,
    pid: int | None = None,
    wait_max_seconds: float = 1800.0,
    poll_seconds: float = 30.0,
    stale_seconds: float = STALE_SECONDS,
    legacy_stale_seconds: float = LEGACY_STALE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pid_alive: Callable[[int], bool] = _pid_alive,
    on_orphan_removed: Callable[[LockInfo, str, Path], None] | None = None,
) -> LockInfo:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now_iso()
    mine = LockInfo(
        lane=lane, pid=pid if pid is not None else os.getpid(), acquired_at=now,
        cost_ceiling_usd=cost_ceiling_usd, heartbeat_at=now,
    )
    start = clock()
    while True:
        if _try_create(path, mine):
            return mine
        existing = _read_lock(path)
        if existing is None:
            continue  # raced with another releaser/acquirer; retry immediately
        reason = _orphan_reason(
            existing, lane=lane, stale_seconds=stale_seconds, legacy_stale_seconds=legacy_stale_seconds,
            pid_alive=pid_alive,
        )
        if reason is not None:
            _remove_if_matches(path, existing)
            if on_orphan_removed is not None:
                on_orphan_removed(existing, reason, path)
            now = _utc_now_iso()
            mine = replace(mine, acquired_at=now, heartbeat_at=now)
            continue
        elapsed = clock() - start
        if elapsed >= wait_max_seconds:
            raise LiveProviderLockTimeout(existing, elapsed, path)
        sleep(poll_seconds)


def release(lane: str, *, path: Path, pid: int | None = None) -> bool:
    pid = pid if pid is not None else os.getpid()
    existing = _read_lock(path)
    if existing is None or existing.lane != lane or existing.pid != pid:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def acquire_groups(
    lane: str,
    cost_ceiling_usd: float,
    groups: Iterable[str],
    *,
    directory: Path | None = None,
    pid: int | None = None,
    wait_max_seconds: float = 1800.0,
    poll_seconds: float = 30.0,
    stale_seconds: float = STALE_SECONDS,
    legacy_stale_seconds: float = LEGACY_STALE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pid_alive: Callable[[int], bool] = _pid_alive,
    on_orphan_removed: Callable[[LockInfo, str, Path], None] | None = None,
) -> list[str]:
    """Take every requested group's lock in GROUP_ORDER, one shared wait budget across them.
    On a timeout, gives back whatever this call already took before re-raising. Locks already
    taken are heartbeated at every poll while a later group is awaited."""
    ordered = _ordered(groups)
    pid = pid if pid is not None else os.getpid()
    taken: list[str] = []
    start = clock()

    def heartbeating_sleep(seconds: float) -> None:
        for held in taken:
            refresh_heartbeat(lane, path=lock_path(held, directory=directory), pid=pid)
        sleep(seconds)

    try:
        for group in ordered:
            acquire(
                lane, cost_ceiling_usd, path=lock_path(group, directory=directory), pid=pid,
                wait_max_seconds=max(0.0, wait_max_seconds - (clock() - start)), poll_seconds=poll_seconds,
                stale_seconds=stale_seconds, legacy_stale_seconds=legacy_stale_seconds, clock=clock,
                sleep=heartbeating_sleep, pid_alive=pid_alive, on_orphan_removed=on_orphan_removed,
            )
            taken.append(group)
    except LiveProviderLockTimeout:
        release_groups(lane, taken, directory=directory, pid=pid)
        raise
    return taken


def release_groups(lane: str, groups: Iterable[str], *, directory: Path | None = None, pid: int | None = None) -> list[str]:
    """Release in reverse GROUP_ORDER; returns the groups actually released (own locks only)."""
    return [
        group for group in reversed(_ordered(groups))
        if release(lane, path=lock_path(group, directory=directory), pid=pid)
    ]


class Heartbeat:
    """Background thread stamping ``heartbeat_at`` on this lane + PID's locks every ``interval`` s."""

    def __init__(
        self, lane: str, groups: Iterable[str], *, directory: Path | None = None, pid: int | None = None,
        interval: float = HEARTBEAT_SECONDS,
    ) -> None:
        self._lane = lane
        self._paths = [lock_path(group, directory=directory) for group in _ordered(groups)]
        self._pid = pid if pid is not None else os.getpid()
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="live-lock-heartbeat", daemon=True)

    def beat(self) -> int:
        """One pass; returns how many locks are still ours."""
        return sum(refresh_heartbeat(self._lane, path=path, pid=self._pid) for path in self._paths)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self.beat()

    def start(self) -> Heartbeat:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--lane", required=True)
    acquire_parser.add_argument("--groups", required=True, help=f"Comma-separated, from {', '.join(GROUP_ORDER)}.")
    acquire_parser.add_argument("--cost-ceiling-usd", required=True, type=float)
    acquire_parser.add_argument("--pid", type=int, default=None)
    acquire_parser.add_argument("--wait-max-seconds", type=float, default=1800.0)
    acquire_parser.add_argument("--poll-seconds", type=float, default=30.0)
    acquire_parser.add_argument("--stale-seconds", type=float, default=STALE_SECONDS,
                                help="Heartbeat age after which a lock is an orphan.")
    acquire_parser.add_argument("--legacy-stale-seconds", type=float, default=LEGACY_STALE_SECONDS,
                                help="acquired_at age for a lock with no heartbeat_at (old format).")

    heartbeat_parser = sub.add_parser("heartbeat", help="Keep this lane's locks fresh until they are released.")
    heartbeat_parser.add_argument("--lane", required=True)
    heartbeat_parser.add_argument("--groups", required=True)
    heartbeat_parser.add_argument("--pid", type=int, default=None)
    heartbeat_parser.add_argument("--interval", type=float, default=HEARTBEAT_SECONDS)
    heartbeat_parser.add_argument("--once", action="store_true")

    release_parser = sub.add_parser("release")
    release_parser.add_argument("--lane", required=True)
    release_parser.add_argument("--groups", required=True)
    release_parser.add_argument("--pid", type=int, default=None)

    args = parser.parse_args(argv)
    groups = [group.strip() for group in args.groups.split(",") if group.strip()]

    if args.command == "acquire":
        def report_orphan(existing: LockInfo, reason: str, lock: Path) -> None:
            print(f"orphan lock removed: lane={existing.lane} reason={reason} pid={existing.pid} lock={lock.name}")

        try:
            taken = acquire_groups(
                args.lane, args.cost_ceiling_usd, groups, directory=lock_dir(), pid=args.pid,
                wait_max_seconds=args.wait_max_seconds, poll_seconds=args.poll_seconds,
                stale_seconds=args.stale_seconds, legacy_stale_seconds=args.legacy_stale_seconds,
                on_orphan_removed=report_orphan,
            )
        except LiveProviderLockTimeout as exc:
            print(f"TIMEOUT: {exc}")
            return 1
        print(f"locks acquired: lane={args.lane} groups={','.join(taken)} cost_ceiling_usd={args.cost_ceiling_usd}")
        return 0

    if args.command == "heartbeat":
        beater = Heartbeat(args.lane, groups, directory=lock_dir(), pid=args.pid, interval=args.interval)
        if args.once:
            return 0 if beater.beat() else 1
        while beater.beat():
            time.sleep(args.interval)
        print("heartbeat stopped: no lock of this lane/pid remains")
        return 0

    released = release_groups(args.lane, groups, directory=lock_dir(), pid=args.pid)
    print(f"locks released: {','.join(released) or '(none held by this lane/pid)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
