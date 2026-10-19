"""Check that constraints.txt pins every requirements.txt package exactly (D-242).

Stdlib only. Every line of constraints.txt must be ``name==version``, and every
package named in requirements.txt must appear in it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> int:
    problems: list[str] = []
    pinned: set[str] = set()
    for raw in (ROOT / "constraints.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.!+_-]+)", line)
        if not match:
            problems.append(f"constraints.txt: not an exact name==version pin: {line}")
            continue
        pinned.add(norm(match.group(1)))
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = NAME.match(line)
        if match and norm(match.group(1)) not in pinned:
            problems.append(f"requirements.txt package not pinned in constraints.txt: {match.group(1)}")
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"constraints.txt ok: {len(pinned)} exact pins cover requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
