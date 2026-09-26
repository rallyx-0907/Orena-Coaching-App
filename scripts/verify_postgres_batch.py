from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    [sys.executable, str(ROOT / "scripts" / "archive" / "release-gates" / "validate_postgres_foundation.py")],
    [sys.executable, "-m", "writing_coach.becoming_memory_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_practice_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_outcomes_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_library_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_linguistics_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_polish_selftest"],
    [sys.executable, "-m", "writing_coach.becoming_polish_r2_selftest"],
    [sys.executable, "-m", "writing_coach.persistence.selftest"],
    ["alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head", "--sql"],
]


def main() -> None:
    for command in COMMANDS:
        print("$", " ".join(str(x) for x in command), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            raise SystemExit(result.returncode)
    print("BECOMING v1.3 PostgreSQL foundation batch verification OK")
    print("Runtime cutover remains DISABLED")


if __name__ == "__main__":
    main()
