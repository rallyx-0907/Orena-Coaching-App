"""Re-estimate Reading articles' automatic level with the current estimator, and set reviewed levels (PR BU). Dry run.

    python scripts/reading_relevel.py --actor hermes-for-owner                          # dry run: what would change
    python scripts/reading_relevel.py --actor X --apply                                 # re-estimate them
    python scripts/reading_relevel.py --actor X --set "The Ants and the Grasshopper=A2" --apply

The articles are exactly those `scripts/report_reading_level_changes.py` lists (`find_changes`: published or queued
articles whose stored `estimated_level` differs from `analyze_article` under `LEVEL_VERSION`). `--apply` re-estimates
each through `ReadingContentRepository.reestimate_level`, which re-reads the body under a row lock, writes the machine's
`estimated_level`, its confidence and `analysis.level_version`, moves `effective_level` only when no `reviewed_level`
exists (D-196), bumps `content_revision` when the learner's level changes, and records a `level_reestimated` event with
the `--actor` in `reading_review_events`. An existing `reviewed_level` is never overridden by a re-estimate.

`--set <article>=<level>` (repeatable) sets `reviewed_level` explicitly through `update_article` (the Admin's correction:
event `level_override`, the actor, the reason). `<article>` is an article id or an exact, unique article title. That is
the only way this CLI changes a reviewed level, and only for the article it names.

Authority: re-estimating stored levels is an owner decision (D-198). The owner delegated it on 2026-10-20 ("Tôi uỷ
quyền làm thay tôi"), so Hermes may run `--apply` on the owner's behalf; record that in `--reason` if useful.

Output: one JSON report (`would_change`/`changed`, `reviewed_set`, one row per article). Nothing is deleted. Never prints
the database URL (`--url` or `POSTGRES_RUNTIME_URL`).
Exit code: 0 done (or a dry run with nothing to change); 1 a dry run found articles that would change; 2 refused.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.operator_cli import OperatorRefused, database_url, emit, refused, require_actor  # noqa: E402

SCRIPT = "scripts/reading_relevel.py"


def parse_sets(raw: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in raw:
        name, sep, level = item.rpartition("=")
        if not sep or not name.strip() or not level.strip():
            raise OperatorRefused("set_invalid", f"--set needs <article id or title>=<level>: {item[:80]!r}")
        out.append((name.strip(), level.strip()))
    return out


def resolve_article(engine: Any, repository: Any, key: str) -> str:
    """An article id, or the id of the one article with exactly this title."""
    from sqlalchemy import select

    from writing_coach.persistence.models import ReadingArticle

    try:
        found = repository.get_article(key)
    except (ValueError, TypeError):
        found = None
    if found is not None:
        return str(found["id"])
    with engine.connect() as connection:
        ids = list(connection.execute(select(ReadingArticle.id).where(ReadingArticle.title == key)).scalars())
    if len(ids) != 1:
        raise OperatorRefused("article_not_found" if not ids else "article_ambiguous", f"{key[:80]!r}: {len(ids)} match(es)")
    return str(ids[0])


def run(engine: Any, *, apply: bool, actor: str, sets: list[tuple[str, str]], reason: str) -> tuple[dict[str, Any], int]:
    from scripts.report_reading_level_changes import find_changes
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.reading_processing import EN_LEVEL_BANDS, LEVEL_VERSION, ZH_LEVEL_BANDS

    repository = ReadingContentRepository(engine)
    planned_sets: list[dict[str, Any]] = []
    for key, level in sets:
        article_id = resolve_article(engine, repository, key)
        current = repository.get_article(article_id) or {}
        bands = ZH_LEVEL_BANDS if current.get("language") == "zh" else EN_LEVEL_BANDS
        if level not in bands:
            raise OperatorRefused("level_invalid", f"{level!r} is not a level on this article's scale")
        planned_sets.append({"id": article_id, "title": (current.get("title") or "")[:60], "language": current.get("language"),
                             "reviewed_from": current.get("reviewed_level") or "", "reviewed_to": level})
    named = {item["id"] for item in planned_sets}
    changes = find_changes(engine)
    rows: list[dict[str, Any]] = []
    changed = 0
    for item in changes:
        row = {**item, "reviewed_kept": bool(item.get("reviewed")) and item["id"] not in named}
        if apply:
            result = repository.reestimate_level(item["id"], actor=actor, reason=reason)
            row["outcome"] = "missing" if result is None else ("changed" if result["changed"] else "unchanged")
            if result is not None and result["changed"]:
                changed += 1
                row["written"] = {"from": result["from"], "to": result["to"], "level_version": result["level_version"]}
        else:
            row["outcome"] = "would_change"
        rows.append(row)
    reviewed_set = 0
    for item in planned_sets:
        if apply:
            try:
                updated = repository.update_article(item["id"], actor=actor, reviewed_level=item["reviewed_to"], reason=reason)
            except ValueError as error:
                raise OperatorRefused("level_invalid", str(error)) from error
            item["outcome"] = "set" if updated and updated.get("reviewed_level") == item["reviewed_to"] else "unchanged"
            if item["reviewed_from"] == item["reviewed_to"]:
                item["outcome"] = "unchanged"
            reviewed_set += int(item["outcome"] == "set")
        else:
            item["outcome"] = "unchanged" if item["reviewed_from"] == item["reviewed_to"] else "would_set"
    report = {
        "script": SCRIPT, "mode": "apply" if apply else "dry_run", "actor": actor, "level_version": LEVEL_VERSION,
        "listed": len(changes), "would_change": len(changes), "changed": changed,
        "reviewed_kept": sum(1 for row in rows if row["reviewed_kept"]),
        "reviewed_set": reviewed_set, "sets": planned_sets, "items": rows,
    }
    pending = len(changes) + sum(1 for item in planned_sets if item["outcome"] == "would_set")
    return report, (1 if not apply and pending else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--actor", default="", help="who is acting; recorded in each article's review trail")
    parser.add_argument("--set", action="append", default=[], help="<article id or exact title>=<level> (repeatable)")
    parser.add_argument("--reason", default="relevel (D-198, delegated by the owner 2026-10-20)")
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    try:
        actor = require_actor(args.actor)
        sets = parse_sets(args.set)
        from sqlalchemy import create_engine

        engine = create_engine(database_url(args.url))
        report, code = run(engine, apply=args.apply, actor=actor, sets=sets, reason=args.reason.strip()[:300])
    except OperatorRefused as error:
        return refused(SCRIPT, error)
    except Exception as error:  # noqa: BLE001 - the kind only, never a URL
        return refused(SCRIPT, error)
    emit(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
