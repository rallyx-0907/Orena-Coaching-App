"""Read-only check: published Reading articles whose required attribution is incomplete (D-189).

An administrator may publish over unclear rights or an incomplete credit, but only
with an explicit, reasoned override that is recorded (D-189 amends D-105). This lists
every article that is `published` today and fails `provenance_blockers` (the same
function the publish route and the automatic admission use), with its id, language,
title, the missing parts, and whether its latest publish decision recorded such an
override. It writes nothing and unpublishes nothing: the engine is opened for
reading only and the database URL is never printed.

Run it inside the application container, against the database named by
`POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_published_reading_provenance.py

Exit status: 0 every incomplete credit was published over a recorded override (or
there is none), 1 at least one article is incomplete with no recorded override, 2 no
usable database. An overridden article is reported but is not a violation. What to do
about an unrecorded one (record the answers on its review page, or unpublish it) is a
human decision.
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


def find_published_without_provenance(engine: Engine) -> list[dict[str, Any]]:
    """Every published article whose required attribution is incomplete."""

    return ReadingContentRepository(engine).published_missing_provenance()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        engine = create_engine(url)
        found = find_published_without_provenance(engine)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading articles ({type(exc).__name__})")
        return 2
    if not found:
        print("OK: every published Reading article has the attribution its source terms require.")
        return 0
    print(f"{len(found)} published Reading article(s) missing required attribution:")
    for item in found:
        state = "overridden" if item["overridden"] else "NO RECORDED OVERRIDE"
        print(f"- {item['id']}  language={item['language']}  missing={','.join(item['missing'])}  {state}  title: {item['title']}")
    return 1 if any(not item["overridden"] for item in found) else 0


if __name__ == "__main__":
    raise SystemExit(main())
