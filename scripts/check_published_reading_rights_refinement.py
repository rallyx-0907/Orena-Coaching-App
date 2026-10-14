"""Read-only check: published Reading articles that assert staff-only public domain but show wire copy (D-193).

Some sources (VOA) are public domain only for what their own staff produced. This lists every
`published` article from such a source whose stored text carries a wire credit or derivation note
(for example "本文依据了美联社的报道"), or has no byline, together with whether its effective
rights still answer "can republish" yes and which licence a learner would be shown. It judges the
stored snapshot now, so it also covers articles ingested before the per-item refinement existed.
It writes nothing and unpublishes nothing; the database URL is never printed.

Run inside the application container against `POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_published_reading_rights_refinement.py

Exit status: 0 none found, 1 at least one found (a human decision: unpublish, or record the rights
answers on its review page), 2 no usable database.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from writing_coach.persistence.reading_content_repository import ReadingContentRepository  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = ReadingContentRepository(create_engine(url)).published_staff_only_rights_candidates()
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading articles ({type(exc).__name__})")
        return 2
    if not found:
        print("OK: no published article from a staff-only public-domain source shows wire copy or lacks a byline.")
        return 0
    print(f"{len(found)} published article(s) from a staff-only public-domain source need a human look:")
    for item in found:
        state = f"republish=yes licence='{item['licence']}'" if item["asserted"] else "republish not asserted"
        evidence = "; ".join(entry["text"] for entry in item["evidence"]) or "-"
        print(f"- {item['id']}  language={item['language']}  reasons={','.join(item['reasons'])}  {state}")
        print(f"    title: {item['title']}")
        print(f"    evidence: {evidence}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
