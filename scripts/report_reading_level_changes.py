"""Read-only report: Reading articles whose automatic level would change under the current estimator.

Recomputes `analyze_article` (LEVEL_VERSION in `writing_coach/reading_processing.py`) over the
stored body of every published or queued article and lists those whose stored `estimated_level`
differs. It writes nothing: stored rows are never changed by this script, and re-estimating them
is an owner decision (D-198). A reviewer's `reviewed_level` is shown and always wins downstream
(D-196), so an overridden article's learner-facing level does not move whatever this prints.
It never prints the database URL.

    python scripts/report_reading_level_changes.py            # POSTGRES_RUNTIME_URL or --url

Exit status: 0 nothing would change, 1 at least one article would change, 2 no usable database.
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
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    LEARNER_VISIBLE_STATUS,
    QUEUE_STATUSES,
)
from writing_coach.reading_processing import LEVEL_VERSION, analyze_article  # noqa: E402

LIVE_STATUSES = (LEARNER_VISIBLE_STATUS, *QUEUE_STATUSES)


def find_changes(engine: Engine, statuses: tuple[str, ...] = LIVE_STATUSES) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    with Session(engine) as session:
        if engine.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        rows = session.execute(
            select(ReadingArticle.id, ReadingArticle.title, ReadingArticle.language, ReadingArticle.status,
                   ReadingArticle.body, ReadingArticle.estimated_level, ReadingArticle.reviewed_level,
                   ReadingArticle.analysis_json)
            .where(ReadingArticle.status.in_(statuses))
            .order_by(ReadingArticle.created_at)
        ).all()
        for row in rows:
            new = analyze_article(row.body or "", row.language or "en")
            if new.estimated_level == (row.estimated_level or ""):
                continue
            analysis = row.analysis_json if isinstance(row.analysis_json, Mapping) else {}
            changes.append({
                "id": str(row.id), "status": row.status, "language": row.language,
                "current": row.estimated_level, "new": new.estimated_level,
                "reviewed": row.reviewed_level or "", "stored_version": analysis.get("level_version", ""),
                "title": (row.title or "")[:60],
            })
        session.rollback()
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        changes = find_changes(create_engine(url))
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading articles ({type(exc).__name__})")
        return 2
    if not changes:
        print(f"OK: no article's stored level differs from {LEVEL_VERSION}.")
        return 0
    print(f"{len(changes)} article(s) would change under {LEVEL_VERSION} (nothing was written):")
    for item in changes:
        print(f"- {item['id']}  {item['status']}  {item['language']}  {item['current']} -> {item['new']}"
              f"  reviewed={item['reviewed'] or '-'}  stored_version={item['stored_version'] or '-'}  {item['title']!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
