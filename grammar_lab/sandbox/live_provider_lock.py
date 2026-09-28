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
     "cost_ceiling_usd": <number>}

A lane holds only the groups it uses. Groups are always taken in the fixed order
gemini-text -> gemini-live -> deepseek and released in reverse, so two lanes can never
each hold one lock the other is waiting for; failing to take one gives back every lock
already taken in that attempt.

A lock held by a live lane is re-checked every ``--poll-seconds`` up to
``--wait-max-seconds``, then acquisition stops and reports the holder's lane/PID. A lock
whose PID is no longer running, or whose ``acquired_at`` is older than
``--stale-seconds``, is an orphan: it is removed, reported as
``orphan lock removed: lane=... reason=dead-pid|stale``, and acquisition retries. A lock is
only ever deleted by the lane + PID that wrote it.

This is plain file coordination. The module never inspects or touches Docker or any
container -- it cannot spawn a process at all, so it cannot stop another lane's container.

CLI, from a runner script::

    python live_provider_lock.py acquire --lane grammar-lab --pid $$ \\
        --groups gemini-text,deepseek --cost-ceiling-usd 0.05
    python live_provider_lock.py release --lane grammar-lab --pid $$ \\
        --groups gemini-text,deepseek
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

GROUP_ORDER = ("gemini-text", "gemini-live", "deepseek")


@dataclass(frozen=True)
class LockInfo:
    lane: str
    pid: int
    acquired_at: str
    cost_ceiling_usd: float


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
    )


def _try_create(path: Path, info: LockInfo) -> bool:
    payload = {
        "lane": info.lane, "pid": info.pid, "acquired_at": info.acquired_at, "cost_ceiling_usd": info.cost_ceiling_usd,
    }
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


def _orphan_reason(info: LockInfo, *, stale_seconds: float, pid_alive: Callable[[int], bool]) -> str | None:
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
    path: Path,
    pid: int | None = None,
    wait_max_seconds: float = 1800.0,
    poll_seconds: float = 30.0,
    stale_seconds: float = 3600.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pid_alive: Callable[[int], bool] = _pid_alive,
    on_orphan_removed: Callable[[LockInfo, str, Path], None] | None = None,
) -> LockInfo:
    path.parent.mkdir(parents=True, exist_ok=True)
    mine = LockInfo(
        lane=lane, pid=pid if pid is not None else os.getpid(), acquired_at=_utc_now_iso(),
        cost_ceiling_usd=cost_ceiling_usd,
    )
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
                on_orphan_removed(existing, reason, path)
            mine = replace(mine, acquired_at=_utc_now_iso())
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
    stale_seconds: float = 3600.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pid_alive: Callable[[int], bool] = _pid_alive,
    on_orphan_removed: Callable[[LockInfo, str, Path], None] | None = None,
) -> list[str]:
    """Take every requested group's lock in GROUP_ORDER, one shared wait budget across them.
    On a timeout, gives back whatever this call already took before re-raising."""
    ordered = _ordered(groups)
    pid = pid if pid is not None else os.getpid()
    taken: list[str] = []
    start = clock()
    try:
        for group in ordered:
            acquire(
                lane, cost_ceiling_usd, path=lock_path(group, directory=directory), pid=pid,
                wait_max_seconds=max(0.0, wait_max_seconds - (clock() - start)), poll_seconds=poll_seconds,
                stale_seconds=stale_seconds, clock=clock, sleep=sleep, pid_alive=pid_alive,
                on_orphan_removed=on_orphan_removed,
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
    acquire_parser.add_argument("--stale-seconds", type=float, default=3600.0)

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
                stale_seconds=args.stale_seconds, on_orphan_removed=report_orphan,
            )
        except LiveProviderLockTimeout as exc:
            print(f"TIMEOUT: {exc}")
            return 1
        print(f"locks acquired: lane={args.lane} groups={','.join(taken)} cost_ceiling_usd={args.cost_ceiling_usd}")
        return 0

    released = release_groups(args.lane, groups, directory=lock_dir(), pid=args.pid)
    print(f"locks released: {','.join(released) or '(none held by this lane/pid)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
