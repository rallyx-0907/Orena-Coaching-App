"""Read-only check: published Reading articles the D-250 rights gate would refuse now.

Since D-250 (amends D-190) an article is published only when its rights are clear - republish allowed, the adapt right
for an adapted text, a complete credit where attribution is required, and the attribution question answered - and there
is no override. Articles published before, some over D-190's warnings, are not taken down by the gate (Hermes for the
owner, 2026-10-21): this lists them for a human decision. For each: id, language, title, the blocker codes, and whether
its latest publish went over D-190's warnings. It writes nothing and unpublishes nothing; the database URL is never
printed.

Run it inside the application container, against the database named by `POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_published_reading_rights_gate.py

Exit status: 0 no published article fails the gate, 1 at least one does, 2 no usable database.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import Engine, create_engine  # noqa: E402

from writing_coach.persistence.reading_content_repository import ReadingContentRepository  # noqa: E402


def find_published_rights_violations(engine: Engine) -> list[dict[str, Any]]:
    return ReadingContentRepository(engine).published_rights_violations()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = find_published_rights_violations(create_engine(url))
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading articles ({type(exc).__name__})")
        return 2
    if not found:
        print("ok: every published Reading article passes the D-250 rights gate")
        return 0
    print(f"{len(found)} published Reading article(s) would be refused by the D-250 rights gate (nothing changed):")
    for item in found:
        overridden = " (published over D-190 warnings)" if item["overridden"] else ""
        print(f"- {item['id']} [{item['language']}] {item['title']}: {', '.join(item['blockers'])}{overridden}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
