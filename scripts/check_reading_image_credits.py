"""Read-only check: an approved Reading thumbnail with neither a credit nor a publisher (#198).

A card shows a picture only when a credit exists: the credit stored at approval, else the learner-facing
publisher. The serving code and the approve route both enforce that, so the expected count of approved
pictures with an empty credit AND an empty publisher is 0. This counts them from the stored data, so a
future change that loosens either rule shows up here. It writes nothing; the database URL is never printed.

    python scripts/check_reading_image_credits.py            # POSTGRES_RUNTIME_URL, or --url

Exit status: 0 none found, 1 at least one, 2 no usable database.
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

from sqlalchemy import Engine, create_engine, select  # noqa: E402

from writing_coach.persistence.models import ReadingArticle  # noqa: E402
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    IMAGE_EVENTS,
    LEARNER_VISIBLE_STATUS,
    ReadingContentRepository,
    fold_image_events,
)
from writing_coach.reading_images import clean_text  # noqa: E402


def find_uncredited_images(engine: Engine) -> dict[str, Any]:
    """`{"approved": n, "uncredited": [{id, title, language}]}` over published articles."""
    repo = ReadingContentRepository(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            select(ReadingArticle.id, ReadingArticle.title, ReadingArticle.language)
            .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
            .order_by(ReadingArticle.language, ReadingArticle.title, ReadingArticle.id)
        ).all()
        ids = [row.id for row in rows]
        # Private repository methods (_decision_events, _credits_and_images): a refactor of them must update this.
        events = repo._decision_events(connection, ids)
        # Private repository methods (_decision_events, _credits_and_images): a refactor of them must update this.
        credits, _ = repo._credits_and_images(connection, ids, revisions=None)
    approved, uncredited = 0, []
    for row in rows:
        picture = fold_image_events([e for e in events.get(row.id, []) if e["action"] in IMAGE_EVENTS])["approved"]
        if not picture or not picture.get("asset_key"):
            continue
        approved += 1
        credit = clean_text(picture.get("credit"), 400)
        publisher = clean_text((credits.get(row.id) or {}).get("publisher"), 400)
        if not credit and not publisher:
            uncredited.append({"id": str(row.id), "title": row.title, "language": row.language})
    return {"approved": approved, "uncredited": uncredited}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = find_uncredited_images(create_engine(url))
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the Reading images ({type(exc).__name__})")
        return 2
    if not found["uncredited"]:
        print(f"OK: {found['approved']} approved picture(s), none without a credit or publisher.")
        return 0
    print(f"{len(found['uncredited'])} of {found['approved']} approved picture(s) have no credit and no publisher:")
    for item in found["uncredited"]:
        print(f"- {item['id']}  language={item['language']}  title: {item['title']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
