"""Read-only check: published Reading articles whose required attribution is incomplete (D-189).

Before the publish gate learned about attribution, an article whose source terms
require a credit could be published without the publisher, the original address
or the licence that the credit is made of. This lists every article that is
`published` today and fails `provenance_blockers` (the same function the publish
routes and the automatic admission use), with its id, language, title and the
missing parts. It writes nothing and unpublishes nothing: the engine is opened
for reading only and the database URL is never printed.

Run it inside the application container, against the database named by
`POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_published_reading_provenance.py

Exit status: 0 nothing to repair, 1 at least one article needs a decision,
2 no usable database. What to do about a listed article (record the rights
answers on its review page, or unpublish it) is a human decision.
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
        print(f"- {item['id']}  language={item['language']}  missing={','.join(item['missing'])}  title: {item['title']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
