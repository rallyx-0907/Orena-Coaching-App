"""The machine-wide lock every lane takes before a real provider call (human direction 2026-09-28).

Two lanes on one machine share one Docker runtime and one provider quota. Before
a lane starts a sandbox or calls a real provider it creates, atomically,

    %USERPROFILE%\\.orena\\live-provider.lock      (outside every repository)

and removes it in the same finally/trap that takes its sandbox down. The file is
JSON: {"lane", "pid", "host", "started_at" (UTC ISO 8601), "cap_usd", "purpose"}.
`pid` is the Windows process id of the process that will release it (in Git Bash:
`cat /proc/$$/winpid`, not `$$`).

A lock that exists is held: wait, looking again every 30 s, for at most 30 min,
then stop and tell the human. A lock is an orphan - and may be removed, saying so
in the run's result - when its holder on this host is no longer alive, or it has
been held for more than 60 min. Nobody stops another lane's containers.

    python scripts/agent_live/lock.py status
    python scripts/agent_live/lock.py run --lane <lane> --cap-usd 0.30 -- <command ...>

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

POLL_SECONDS = 30
WAIT_SECONDS = 30 * 60
ORPHAN_SECONDS = 60 * 60


def lock_path() -> Path:
    home = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(home) / ".orena" / "live-provider.lock"


class LockTimeout(RuntimeError):
    """Held by another lane for longer than this run may wait."""


def pid_alive(pid: int) -> bool:
    """Whether a process with this id runs here. Never signals it (os.kill(pid, 0) terminates on Windows)."""

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
    """The holder's record (None when unreadable, e.g. half written) and the file's age basis (mtime)."""

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


def _started(record: dict | None, mtime: float) -> float:
    try:
        return datetime.fromisoformat(str(record["started_at"])).timestamp()  # type: ignore[index]
    except (TypeError, KeyError, ValueError):
        return mtime


@dataclass
class Lock:
    path: Path
    record: dict
    notes: list[str] = field(default_factory=list)  # what the run's result must say (orphans removed, waits)
    released: bool = False

    def release(self) -> None:
        """Removes the lock if it is still this one; someone else's is never touched."""

        if self.released:
            return
        self.released = True
        current, _ = _read(self.path)
        if current == self.record:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def acquire(
    lane: str,
    cap_usd: float,
    *,
    purpose: str = "",
    path: Path | None = None,
    poll: float = POLL_SECONDS,
    wait: float = WAIT_SECONDS,
    orphan_after: float = ORPHAN_SECONDS,
    alive: Callable[[int], bool] = pid_alive,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    say: Callable[[str], None] = print,
) -> Lock:
    path = path or lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    deadline = clock() + wait
    notes: list[str] = []
    waited = False
    while True:
        record = {
            "lane": lane,
            "pid": os.getpid(),
            "host": host,
            "started_at": datetime.fromtimestamp(clock(), UTC).isoformat(),
            "cap_usd": cap_usd,
            "purpose": purpose,
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
        why = _orphan(holder, mtime, host, clock(), orphan_after, alive)
        if why and _remove_if_unchanged(path, holder, mtime):
            note = f"removed an orphaned live-provider lock ({why}): {json.dumps(holder, ensure_ascii=False)}"
            notes.append(note)
            say(note)
            continue
        if clock() >= deadline:
            raise LockTimeout(
                f"the live-provider lock is held ({json.dumps(holder, ensure_ascii=False)}); "
                f"waited {int(wait // 60)} min - stopping, ask the human"
            )
        if not waited:
            say(f"live-provider lock held by {json.dumps(holder, ensure_ascii=False)}; checking every {int(poll)} s")
        waited = True
        sleep(poll)


def _orphan(holder: dict | None, mtime: float, host: str, now: float, orphan_after: float, alive) -> str | None:
    if now - _started(holder, mtime) > orphan_after:
        return f"held for more than {int(orphan_after // 60)} min"
    if holder and holder.get("host") == host and isinstance(holder.get("pid"), int) and not alive(holder["pid"]):
        return f"process {holder['pid']} is no longer running"
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
    run = sub.add_parser("run", help="run a command while holding the lock")
    run.add_argument("--lane", required=True)
    run.add_argument("--cap-usd", type=float, required=True)
    run.add_argument("--purpose", default="")
    run.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "status":
        holder, mtime = _read(lock_path())
        print("free" if mtime is None else json.dumps(holder, ensure_ascii=False) or "held (unreadable)")
        return 0
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    try:
        lock = acquire(args.lane, args.cap_usd, purpose=args.purpose or " ".join(argv)[:120])
    except LockTimeout as error:
        print(error)
        return 3
    try:
        return subprocess.run(argv, check=False).returncode
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(_cli())
