"""Replace one example sentence of a vocabulary entry, as the Admin correction does (PR BU). Dry run by default.

    python scripts/vocab_correct_example.py --collection pilot-zh-idioms --entry 守株待兔 --index 0 \\
        --text "他总想守株待兔，等着好机会自己找上门来。" --reading "Tā zǒng xiǎng shǒuzhū dàitù, ..." \\
        --translation vi="Anh ấy ..." --translation en="He always ..." --clear-explanation \\
        --reason "PRE-201 F3" --actor hermes-for-owner                                    # dry run
    python scripts/vocab_correct_example.py --file scripts/data/pilot_zh_idioms_f3_examples.json --actor X --apply

A thin wrapper over `SQLAlchemyVocabularyRepository.correct_entry_example` (#420), the function behind
`PATCH /api/admin/console/content/vocabulary/{collection}/entries/{entry}/examples/{index}`, which keeps all of its own
validation: every support language the old sentence was translated into is given again, a reading when the old one had
one, an old explanation given again or cleared, the highlight recomputed, every membership snapshot of the entry
corrected with it, and the actor, time, reason and before/after kept in the entry's `provenance.example_corrections`.
`--label vi=...` (optional) replaces the item's label (for a sentence whose label said where the old one came from).
A changed correction is also recorded in `audit_logs` as `admin.content.vocabulary_example`, as the route records it,
with `via: scripts/vocab_correct_example.py`. Nothing is deleted.

The dry run is the real function inside a transaction that is rolled back, so it checks exactly what `--apply` would
write. `--file` applies several corrections (JSON: `{"collection", "reason", "corrections": [{"entry" or "headword",
"index", "text", "reading", "translations", "explanations" | "clear_explanation", "label", "expect_from"}]}`) all or
nothing: one transaction, committed only when every correction passes. `--entry` / `"entry"` is an entry id; `--entry` may also be
the headword, and `"headword"` in a file must match the entry when both are given. `"expect_from"` (optional) is the
sentence the correction was written for: a different sentence at that index refuses the whole file.

Output: one JSON report (`corrections`, `changed`, `written`, one row per correction). Never prints the database URL.
Exit code: 0 written (or nothing to change); 1 a dry run found changes; 2 refused (nothing written).
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.operator_cli import OperatorRefused, audit_recorder, database_url, emit, refused, require_actor  # noqa: E402

SCRIPT = "scripts/vocab_correct_example.py"


def _pairs(raw: list[str], what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw:
        code, sep, text = item.partition("=")
        if not sep or not code.strip() or not text.strip():
            raise OperatorRefused(f"{what}_invalid", f"--{what} needs <language>=<text>")
        out[code.strip().casefold()] = text.strip()
    return out


def corrections_from_args(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    if args.file:
        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise OperatorRefused("file_unreadable", type(error).__name__) from error
        if not isinstance(data, Mapping) or not isinstance(data.get("corrections"), list) or not data["corrections"]:
            raise OperatorRefused("file_invalid", "expected {collection, reason, corrections: [...]}")
        collection = str(data.get("collection") or args.collection or "")
        reason = str(args.reason or data.get("reason") or "")
        items = []
        for item in data["corrections"]:
            if not isinstance(item, Mapping):
                raise OperatorRefused("file_invalid", "each correction is an object")
            items.append({**item, "collection": str(item.get("collection") or collection)})
        return items, reason
    if not (args.collection and args.entry and args.index is not None and args.text):
        raise OperatorRefused("arguments_missing", "pass --collection, --entry, --index and --text, or --file")
    item = {"collection": args.collection, "entry": args.entry, "index": args.index, "text": args.text,
            "reading": args.reading, "translations": _pairs(args.translation, "translation"),
            "explanations": _pairs(args.explanation, "explanation"), "clear_explanation": args.clear_explanation,
            "label": _pairs(args.label, "label")}
    return [item], str(args.reason or "")


def resolve_entry(connection: Any, collection: str, entry: str, headword: str = "") -> str:
    """An entry id, or the id of the one entry in the collection whose headword this is."""
    from sqlalchemy import select

    from writing_coach.persistence.models import VocabularyCollectionMembership, VocabularyEntry

    key = (entry or "").strip()
    try:
        wanted = str(uuid.UUID(key))
    except ValueError:
        wanted = ""
    term = headword.strip() or ("" if wanted else key)
    query = (select(VocabularyEntry.id, VocabularyEntry.term)
             .join(VocabularyCollectionMembership, VocabularyCollectionMembership.entry_id == VocabularyEntry.id)
             .where(VocabularyCollectionMembership.collection_id == collection))
    if wanted:
        rows = connection.execute(query.where(VocabularyEntry.id == uuid.UUID(wanted))).all()
        if rows and term and rows[0].term != term:
            raise OperatorRefused("headword_mismatch", f"{wanted} is {rows[0].term!r}, not {term!r}")
    else:
        rows = connection.execute(query.where(VocabularyEntry.term == term)).all()
    if len(rows) != 1:
        raise OperatorRefused("entry_not_found" if not rows else "entry_ambiguous",
                              f"{collection}/{key or term}: {len(rows)} match(es)")
    return str(rows[0].id)


def _support(values: Mapping[str, Any] | None, what: str, supported: set[str]) -> dict[str, str]:
    out = {str(code).strip().casefold(): str(text) for code, text in (values or {}).items()}
    if any(code not in supported for code in out) or len(out) != len(values or {}):
        raise OperatorRefused("example_invalid", f"choose a support language for each {what}")
    return out


def run(engine: Any, corrections: list[dict[str, Any]], *, reason: str, apply: bool, actor: str,
        repository_for: Any, record_event: Any = None) -> tuple[dict[str, Any], int]:
    """Every correction through `correct_entry_example`, in one transaction: committed with `apply`, else rolled back."""
    from writing_coach import media_corrections

    if not reason.strip():
        raise OperatorRefused("reason_required", "pass --reason (or \"reason\" in the file)")
    if apply and record_event is None:
        raise OperatorRefused("audit_unavailable")
    if not repository_for(engine).available():
        raise OperatorRefused("vocabulary_schema_unavailable")
    supported = set(media_corrections.support_codes())
    rows: list[dict[str, Any]] = []
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            repository = repository_for(connection)
            # The engine was checked just above; inside the outer transaction the schema check would open a second
            # connection, which a bound connection cannot do.
            repository._require_available = lambda: None
            for item in corrections:
                collection = str(item.get("collection") or "")
                entry_id = resolve_entry(connection, collection, str(item.get("entry") or ""), str(item.get("headword") or ""))
                index = item.get("index")
                if isinstance(index, bool) or not isinstance(index, int):
                    raise OperatorRefused("example_invalid", "index must be an integer")
                kwargs: dict[str, Any] = {
                    "text": str(item.get("text") or ""),
                    "translations": _support(item.get("translations"), "translation", supported),
                    "actor": actor, "reason": reason, "reading": item.get("reading"),
                    "explanations": _support(item.get("explanations"), "explanation", supported),
                    "clear_explanation": bool(item.get("clear_explanation")),
                }
                label = _support(item.get("label"), "label", supported)
                if label:
                    kwargs["label"] = label
                try:
                    result = repository.correct_entry_example(collection, entry_id, index, **kwargs)
                except LookupError:
                    raise OperatorRefused("entry_not_found", f"{collection}/{entry_id}") from None
                except ValueError as error:
                    raise OperatorRefused("example_invalid", f"{collection}/{entry_id}[{index}]: {error}") from error
                except TypeError as error:   # an image older than the `label` parameter
                    raise OperatorRefused("label_unsupported", str(error)[:200]) from error
                expected = str(item.get("expect_from") or "").strip()
                if expected and result["from"] != expected and result["to"] != result["from"]:
                    # The sentence at this index is not the one the correction was written for: refuse, roll back.
                    raise OperatorRefused("example_mismatch", f"{collection}/{entry_id}[{index}] is {result['from'][:80]!r}")
                rows.append({"collection": collection, "entry_id": entry_id, "index": index,
                             "headword": result["entry"].get("term", "") if isinstance(result.get("entry"), Mapping) else "",
                             "from": result["from"], "to": result["to"], "changed": result["changed"],
                             "snapshots_unmatched": result["snapshots_unmatched"],
                             "translation_languages": sorted(kwargs["translations"]),
                             "explanation": "cleared" if kwargs["clear_explanation"] else sorted(kwargs["explanations"]),
                             "label": label, "outcome": ("written" if apply else "would_write") if result["changed"] else "unchanged"})
        except BaseException:
            if outer.is_active:   # a failed correction may already have rolled the whole transaction back
                outer.rollback()
            raise
        if apply:
            outer.commit()
        else:
            outer.rollback()
    if apply:
        for row in rows:
            if row["changed"]:
                record_event("admin.content.vocabulary_example", actor_key=actor, entity_type="vocabulary_entry",
                             entity_id=row["entry_id"],
                             payload={"collection_id": row["collection"], "index": row["index"], "from": row["from"][:300],
                                      "to": row["to"][:300], "translation_languages": row["translation_languages"],
                                      "explanation": row["explanation"], "snapshots_unmatched": row["snapshots_unmatched"],
                                      "reason": reason.strip()[:300], "outcome": "ok", "via": SCRIPT, "actor": actor})
    changed = sum(1 for row in rows if row["changed"])
    report = {"script": SCRIPT, "mode": "apply" if apply else "dry_run", "actor": actor, "corrections": len(rows),
              "changed": changed, "written": changed if apply else 0, "items": rows}
    return report, (1 if not apply and changed else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--collection", default="", help="collection id (its slug)")
    parser.add_argument("--entry", default="", help="entry id or headword")
    parser.add_argument("--index", type=int, default=None, help="the example's position (0 is the first)")
    parser.add_argument("--text", default="", help="the new sentence")
    parser.add_argument("--reading", default=None, help="the new sentence's reading (pinyin)")
    parser.add_argument("--translation", action="append", default=[], help="<language>=<text> (repeatable)")
    parser.add_argument("--explanation", action="append", default=[], help="<language>=<text> (repeatable)")
    parser.add_argument("--clear-explanation", action="store_true")
    parser.add_argument("--label", action="append", default=[], help="<language>=<text>: replace the item's label")
    parser.add_argument("--file", default="", help="a JSON file of corrections")
    parser.add_argument("--reason", default="", help="why; recorded with each correction")
    parser.add_argument("--apply", action="store_true", help="write (default: dry run, rolled back)")
    parser.add_argument("--actor", default="", help="who is acting; recorded with each correction")
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    try:
        actor = require_actor(args.actor)
        if args.explanation and args.clear_explanation:
            raise OperatorRefused("example_invalid", "give new explanations or --clear-explanation, not both")
        corrections, reason = corrections_from_args(args)
        from sqlalchemy import create_engine

        from writing_coach.persistence.vocabulary_repository import SQLAlchemyVocabularyRepository

        engine = create_engine(database_url(args.url))
        report, code = run(engine, corrections, reason=reason, apply=args.apply, actor=actor,
                           repository_for=SQLAlchemyVocabularyRepository,
                           record_event=audit_recorder(engine) if args.apply else None)
    except Exception as error:  # noqa: BLE001 - OperatorRefused prints its code; anything else only its kind
        return refused(SCRIPT, error)
    emit(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
