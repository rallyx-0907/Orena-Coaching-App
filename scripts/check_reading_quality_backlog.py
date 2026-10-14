"""Read-only check: stored Reading articles the quality gate (D-191) could not judge.

Articles stored before the quality gate carry no `analysis.extraction.page_facts`, and pasted
or uploaded text never does, so the fact-based hard codes (`media_page`, `bot_challenge`,
`special_page`, a listing title or address) cannot have been raised for them. This lists every
article that is not rejected or archived and has no stored hard quality code but either lacks
those facts or fails a hard code recomputed from its body (`empty_body`). It writes nothing and
never prints the database URL. It cannot backfill: the raw page is gone, so what to do with a
listed article (re-import it, or review it by hand) is a human decision.

    python scripts/check_reading_quality_backlog.py            # POSTGRES_RUNTIME_URL or --url

Exit status: 0 nothing to review, 1 at least one article listed, 2 no usable database.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import Engine, create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from writing_coach.persistence.models import ReadingArticle  # noqa: E402
from writing_coach.reading_page_quality import hard_issues, quality_flags  # noqa: E402


def find_unflagged(engine: Engine) -> list[dict[str, Any]]:
    """Articles without a stored hard code whose facts are missing or whose body now fails one."""
    found: list[dict[str, Any]] = []
    with Session(engine) as session:
        if engine.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        rows = session.execute(
            select(ReadingArticle.id, ReadingArticle.title, ReadingArticle.language, ReadingArticle.status,
                   ReadingArticle.body, ReadingArticle.analysis_json)
            .where(ReadingArticle.status.notin_(("rejected", "archived")))
            .order_by(ReadingArticle.created_at)
        ).all()
        for row in rows:
            analysis = row.analysis_json if isinstance(row.analysis_json, Mapping) else {}
            if hard_issues(analysis.get("quality_issues")):
                continue  # already judged hard; the gate holds it
            extraction = analysis.get("extraction") if isinstance(analysis.get("extraction"), Mapping) else {}
            facts = extraction.get("page_facts")
            recomputed = hard_issues(quality_flags(
                body=row.body or "", language=row.language, title=row.title or "",
                confidence=str(extraction.get("confidence") or ""),
                facts=facts if isinstance(facts, Mapping) else None,
            ))
            if recomputed or not facts:
                found.append({
                    "id": str(row.id), "status": row.status, "language": row.language,
                    "title": (row.title or "")[:60], "missing_facts": not facts, "hard_now": recomputed,
                })
        session.rollback()
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = find_unflagged(create_engine(url))
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading articles ({type(exc).__name__})")
        return 2
    if not found:
        print("OK: every live article has a stored hard verdict or its page facts.")
        return 0
    print(f"{len(found)} article(s) the quality gate could not judge from page facts:")
    for item in found:
        print(f"- {item['id']}  {item['status']}  {item['language']}  facts_missing={item['missing_facts']}"
              f"  hard_now={item['hard_now']}  {item['title']!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
