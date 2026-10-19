"""Recount Reading articles whose stored word count / reading time no longer match their body.

An admin body edit used to leave `word_count` and `reading_time_seconds` as admitted. This finds
those rows (same `analyze_article` admission uses; Chinese counts characters, English words) and,
with `--apply`, fixes them and bumps `content_revision`. Dry run by default; idempotent; no AI.

    python scripts/recount_reading_articles.py [--apply] [--id ARTICLE_ID] [--url DATABASE_URL]

The database URL defaults to `POSTGRES_RUNTIME_URL` and is never printed.
Exit status: 0 done (or nothing stale), 2 no usable database.
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
    parser.add_argument("--apply", action="store_true", help="write the corrections (default: dry run)")
    parser.add_argument("--id", default="", help="only this article")
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        found = ReadingContentRepository(create_engine(url)).recount_articles(
            apply=args.apply, article_id=args.id or None)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not recount ({type(exc).__name__})")
        return 2
    for item in found:
        print(f"{item['id']} {item['language']} words {item['word_count']['from']} -> {item['word_count']['to']}, "
              f"seconds {item['reading_time_seconds']['from']} -> {item['reading_time_seconds']['to']}")
    print(f"{len(found)} stale; {'corrected' if args.apply else 'dry run, nothing written (use --apply)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
