"""Read-only check: Reading books whose rights are not attested (D-252; PRE-203 part 2).

After migration 20261021_0037, a book is on the learner shelf only when its rights are `cleared` (attested, with a licence
note) or it was there before the revision (`grandfathered`, kept until a person decides). This lists every book that is
not `cleared` - grandfathered books still on the shelf, imported books waiting for an attestation, denied ones - with
its id, language, title, status and whether learners can read it now. It writes nothing; the database URL is never
printed. What to do with each book (attest it, deny it) is a human decision, in Admin.

Run it inside the application container, against the database named by `POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_books_rights.py

Exit status: 0 every book is cleared (or the gate is not installed yet), 1 at least one is not, 2 no usable database.
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

from writing_coach.persistence.reading_library_repository import PostgresReadingLibraryRepository  # noqa: E402


LIMIT = 1000


def find_books_needing_rights(engine: Engine) -> list[dict[str, Any]]:
    return PostgresReadingLibraryRepository(engine).rights_review(limit=LIMIT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = find_books_needing_rights(create_engine(url))
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading books ({type(exc).__name__})")
        return 2
    if not found:
        print("ok: every Reading book has attested rights (or migration 0037 is not applied)")
        return 0
    print(f"{len(found)} Reading book(s) without attested rights (nothing changed):")
    if len(found) >= LIMIT:
        print(f"(the list stops at {LIMIT}; decide these, then run it again)")
    for item in found:
        shelf = "on the learner shelf" if item["learner_visible"] else "not shown to learners"
        print(f"- {item['id']} [{item['language']}] {item['title']}: {item['rights_status']}, {item['status']}, {shelf}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
