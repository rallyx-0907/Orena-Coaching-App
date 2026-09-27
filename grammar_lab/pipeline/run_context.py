"""Shared ``reports/<run_id>/`` bookkeeping for generate/verify/route/report.

Each pipeline step is a separate CLI invocation (SPEC §2 "Lệnh chính"). A
run_id ties one invocation's output to the next: ``verify`` reads the point
data ``validate`` would recompute anyway, but ``route`` needs *verify's*
per-point flags, and ``report --run latest`` needs whatever the most recent
step wrote. ``reports/latest.txt`` records the most recent run_id so ``route``
and ``report`` can find it without the caller threading ``--run`` through
every command by hand.
"""

from __future__ import annotations

import time
from pathlib import Path

from grammar_lab.pipeline.jsonio import read_json, write_json

LATEST_FILE = Path("reports") / "latest.txt"


class NoRunError(RuntimeError):
    """No pipeline step has produced a run yet, or the requested run_id does not exist."""


def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def run_dir(root: Path, run_id: str) -> Path:
    return root / "reports" / run_id


def set_latest(root: Path, run_id: str) -> None:
    path = root / LATEST_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run_id, encoding="utf-8", newline="\n")


def resolve_run_id(root: Path, run: str) -> str:
    if run != "latest":
        if not run_dir(root, run).exists():
            raise NoRunError(f"no run {run!r} under reports/")
        return run
    path = root / LATEST_FILE
    if not path.exists():
        raise NoRunError("no pipeline run yet -- run generate/verify/route first")
    run_id = path.read_text(encoding="utf-8").strip()
    if not run_dir(root, run_id).exists():
        raise NoRunError(f"reports/latest.txt points at {run_id!r}, which does not exist")
    return run_id


def write_step(root: Path, run_id: str, step: str, data: dict) -> Path:
    path = run_dir(root, run_id) / f"{step}.json"
    write_json(path, data)
    set_latest(root, run_id)
    return path


def read_step(root: Path, run_id: str, step: str) -> dict | None:
    path = run_dir(root, run_id) / f"{step}.json"
    if not path.exists():
        return None
    return read_json(path)
