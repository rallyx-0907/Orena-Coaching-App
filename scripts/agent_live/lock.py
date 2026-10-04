"""The machine-wide locks lanes take before a real provider call, one per quota group (human direction 2026-09-28).

Lanes queue only when they use the same quota. One lock file per group, outside every repository:

    %USERPROFILE%\\.orena\\live-gemini-text.lock   Gemini text models (agent live runs, Grammar Lab's evaluator)
    %USERPROFILE%\\.orena\\live-gemini-live.lock   Gemini Live models (the voice spike)
    %USERPROFILE%\\.orena\\live-deepseek.lock      DeepSeek

The format is the one the Grammar Lab lane defined (grammar_lab/sandbox/live_provider_lock.py); keep it exactly:

    {"lane": "...", "pid": <int>, "acquired_at": "<ISO-8601 UTC>", "heartbeat_at": "<ISO-8601 UTC>",
     "cost_ceiling_usd": <number>}

The holder rewrites heartbeat_at every 60 s while it holds the lock.

A process holds exactly the locks of the groups it uses, taken in the order above and released in reverse. The
single live-provider.lock of before is retired.

- Created atomically (O_CREAT|O_EXCL) before a sandbox or a real provider call, and
  removed in the same finally/trap that takes the sandbox down.
- Held: look again every 30 s, for at most 30 min; then stop and name the lane and
  PID that hold it.
- Orphan: heartbeat_at is more than 10 min old, or - for this lane's own lock only - its PID is no longer
  alive (Windows: OpenProcess; POSIX: os.kill(pid, 0)); another lane's PID may live in WSL or a
  container and is never judged from here. A lock in the old format (no heartbeat_at) falls back to
  acquired_at against 60 min. Remove it, say
  "orphan lock removed: lane=... reason=dead-pid|stale", and try again at once.
- Remove it only when its lane and pid are the ones this run wrote.
- Never stop another lane's containers.

    python scripts/agent_live/lock.py status
    python scripts/agent_live/lock.py run --lane <lane> --group gemini-text --cost-ceiling-usd 0.30 -- <command ...>

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

POLL_SECONDS = 30
WAIT_SECONDS = 30 * 60
HEARTBEAT_SECONDS = 60
STALE_SECONDS = 10 * 60  # heartbeat_at older than this: an orphan
LEGACY_STALE_SECONDS = 60 * 60  # a lock with no heartbeat_at: acquired_at older than this


GROUPS = ("gemini-text", "gemini-live", "deepseek")  # the taking order: never two lanes waiting on each other


def lock_path(group: str) -> Path:
    if group not in GROUPS:
        raise ValueError(f"unknown quota group {group!r}; one of {GROUPS}")
    home = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(home) / ".orena" / f"live-{group}.lock"


class LockTimeout(RuntimeError):
    """Held by another lane for longer than this run may wait."""


def pid_alive(pid: int) -> bool:
    """Whether a process with this id runs here. On Windows through OpenProcess: os.kill(pid, 0) would
    terminate it there."""

    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists; anything else: it does not
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read(path: Path) -> tuple[dict | None, float | None]:
    """The holder's record (None when unreadable, e.g. half written) and the file's mtime (None: no file)."""

    try:
        mtime = path.stat().st_mtime
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    try:
        record = json.loads(text)
    except ValueError:
        return None, mtime
    return (record if isinstance(record, dict) else None), mtime


def _stamp(record: dict | None, key: str) -> float | None:
    try:
        moment = datetime.fromisoformat(str(record[key]).replace("Z", "+00:00"))  # type: ignore[index]
    except (TypeError, KeyError, ValueError):
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).timestamp()


def _age(record: dict | None, mtime: float, now: float) -> tuple[float, bool]:
    """(seconds since the last sign of life, whether that was a heartbeat). Old format: acquired_at; unreadable:
    the file's own time."""

    beat = _stamp(record, "heartbeat_at")
    if beat is not None:
        return now - beat, True
    acquired = _stamp(record, "acquired_at")
    return now - (acquired if acquired is not None else mtime), False


def refresh_heartbeat(path: Path, lane: str, pid: int, *, clock: Callable[[], float] = time.time) -> bool:
    """Stamps heartbeat_at on this lane and pid's own lock; False when it is not ours (any more)."""

    current, _ = _read(path)
    if not current or current.get("lane") != lane or current.get("pid") != pid:
        return False
    current = {**current, "heartbeat_at": datetime.fromtimestamp(clock(), UTC).isoformat()}
    temp = path.with_name(f"{path.name}.{pid}.tmp")
    temp.write_text(json.dumps(current), encoding="utf-8")
    try:
        os.replace(temp, path)
    except PermissionError:  # Windows: a reader has it open this instant; the next beat retries
        temp.unlink(missing_ok=True)
    return True


def _holder(record: dict | None) -> str:
    if not record:
        return "lane=? pid=?"
    return f"lane={record.get('lane', '?')} pid={record.get('pid', '?')}"


@dataclass
class Lock:
    path: Path
    record: dict
    notes: list[str] = field(default_factory=list)  # what the run's result must say (orphans removed, waits)
    released: bool = False
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _beater: threading.Thread | None = field(default=None, repr=False)

    def beat(self) -> bool:
        return refresh_heartbeat(self.path, self.record["lane"], self.record["pid"])

    def start_heartbeat(self, interval: float = HEARTBEAT_SECONDS) -> Lock:
        """Stamps heartbeat_at every `interval` s until released (a daemon thread)."""

        def run() -> None:
            while not self._stop.wait(interval):
                if not self.beat():
                    return  # not ours any more
        self._beater = threading.Thread(target=run, name="live-lock-heartbeat", daemon=True)
        self._beater.start()
        return self

    def release(self) -> None:
        """Removes the lock only while its lane and pid are this run's; someone else's is never touched."""

        if self.released:
            return
        self.released = True
        self._stop.set()
        if self._beater is not None and self._beater.is_alive():
            self._beater.join(timeout=5)
        current, _ = _read(self.path)
        if current and current.get("lane") == self.record["lane"] and current.get("pid") == self.record["pid"]:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def acquire(
    lane: str,
    cost_ceiling_usd: float,
    *,
    group: str = "gemini-text",
    path: Path | None = None,
    poll: float = POLL_SECONDS,
    wait: float = WAIT_SECONDS,
    stale_after: float = STALE_SECONDS,
    legacy_stale_after: float = LEGACY_STALE_SECONDS,
    alive: Callable[[int], bool] = pid_alive,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    say: Callable[[str], None] = print,
) -> Lock:
    path = path or lock_path(group)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = clock() + wait
    notes: list[str] = []
    waited = False
    while True:
        stamp = datetime.fromtimestamp(clock(), UTC).isoformat()
        record = {
            "lane": lane,
            "pid": os.getpid(),
            "acquired_at": stamp,
            "heartbeat_at": stamp,
            "cost_ceiling_usd": cost_ceiling_usd,
        }
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            if waited:
                notes.append("waited for the live-provider lock")
            return Lock(path, record, notes)

        holder, mtime = _read(path)
        if mtime is None:
            continue  # released between the two looks: try again at once
        reason = _orphan(holder, mtime, clock(), stale_after, alive, lane=lane, legacy_stale_after=legacy_stale_after)
        if reason and _remove_if_unchanged(path, holder, mtime):
            note = f"orphan lock removed: lane={(holder or {}).get('lane', '?')} reason={reason}"
            notes.append(note)
            say(note)
            continue  # try again at once
        if clock() >= deadline:
            raise LockTimeout(
                f"the live-provider lock is held by {_holder(holder)}; waited {int(wait // 60)} min - "
                "stopping, ask the human"
            )
        if not waited:
            say(f"live-provider lock held by {_holder(holder)}; checking every {int(poll)} s")
        waited = True
        sleep(poll)


@dataclass
class Locks:
    """The locks of every quota group a process uses, released together (in reverse)."""

    held: list[Lock]

    @property
    def notes(self) -> list[str]:
        return [note for lock in self.held for note in lock.notes]

    def start_heartbeat(self, interval: float = HEARTBEAT_SECONDS) -> Locks:
        for lock in self.held:
            lock.start_heartbeat(interval)
        return self

    def release(self) -> None:
        for lock in reversed(self.held):
            lock.release()


def acquire_groups(lane: str, cost_ceiling_usd: float, groups: list[str] | tuple[str, ...], **kw) -> Locks:
    """Each group's lock, in the fixed order of GROUPS; if one cannot be had, those taken are given back."""

    taken: list[Lock] = []
    sleep = kw.pop("sleep", time.sleep)

    def heartbeating_sleep(seconds: float) -> None:  # locks already taken stay alive while a later one is awaited
        for lock in taken:
            lock.beat()
        sleep(seconds)

    try:
        for group in sorted(set(groups), key=GROUPS.index):
            taken.append(acquire(lane, cost_ceiling_usd, group=group, sleep=heartbeating_sleep, **kw))
    except BaseException:
        Locks(taken).release()
        raise
    return Locks(taken)


def _orphan(
    holder: dict | None, mtime: float, now: float, stale_after: float, alive, *, lane: str | None = None,
    legacy_stale_after: float = LEGACY_STALE_SECONDS,
) -> str | None:
    pid = (holder or {}).get("pid")
    # A pid is judged only on this lane's own locks: another lane may run in WSL or a container, where its pid means
    # nothing to this host (2026-09-28: a Grammar Lab lock one minute old was taken for dead and removed). Another
    # lane's lock is an orphan only when its heartbeat is stale.
    own = lane is None or (holder or {}).get("lane") == lane
    if own and isinstance(pid, int) and not isinstance(pid, bool) and not alive(pid):
        return "dead-pid"
    age, beating = _age(holder, mtime, now)
    if age > (stale_after if beating else legacy_stale_after):
        return "stale"
    return None


def _remove_if_unchanged(path: Path, holder: dict | None, mtime: float) -> bool:
    """Removes the orphan only if the file is still the one judged: a lock taken meanwhile is left alone."""

    current, current_mtime = _read(path)
    if current != holder or current_mtime != mtime:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    run = sub.add_parser("run", help="run a command while holding the locks of its quota groups")
    run.add_argument("--lane", required=True)
    run.add_argument("--group", action="append", choices=GROUPS, required=True, help="repeat for each group used")
    run.add_argument("--cost-ceiling-usd", type=float, required=True)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "status":
        for group in GROUPS:
            holder, mtime = _read(lock_path(group))
            held = "free" if mtime is None else json.dumps(holder, ensure_ascii=False) if holder else "held (unreadable)"
            print(f"{group}: {held}")
        return 0
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    try:
        lock = acquire_groups(args.lane, args.cost_ceiling_usd, args.group).start_heartbeat()
    except LockTimeout as error:
        print(error)
        return 3
    try:
        return subprocess.run(argv, check=False).returncode
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(_cli())
