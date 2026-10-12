"""The authored vocabulary entry format (`docs/vocab/`), read into the shared catalogue (D-17V).

`docs/vocab/vocab_entry.schema.json` describes one vocabulary card as an editor
writes it. A card is not a new thing in Orena: it is the existing shared
lexical entry (`vocabulary_entries`), shown differently. So this module is only
an adapter in front of the existing import path. It turns each authored record
into the canonical record `VocabularyRepository.import_source` already takes,
and every field lands in a column or JSON key that already exists:

- `headword`, `lang`, `pos[0].code`, `level`           -> `term`, `language_code`, `part_of_speech`, `level`/`framework`
- `meanings[].vi` / `.en`                              -> `short_meanings` (language-tagged), EN `en` -> `detailed_definitions`
- `en.ipa.uk/us`                                       -> `pronunciations` items with `region`
- `zh.pinyin`                                          -> one `readings` item (never Hán-Việt: a second reading
                                                          would stop a saved word linking to its entry)
- `zh.chars[]` (pinyin, Hán-Việt, strokes, radical,    -> `orthography.units[]`, readings with `notation`
  components)                                             `pinyin` / `han_viet`, facts with provenance
- `examples[]`                                         -> `examples` items with `highlight`, `reading`,
                                                          `reading_highlight`, and language-tagged `label`,
                                                          `translation`, `explanation`
- `collocations`, `related`, `zh.measure_words`,       -> typed `usage_notes` items (`vocabulary_usage_notes`)
  `memory_tip_vi`
- `id`                                                 -> `sense_key` (so it is part of the lexical identity)
                                                          and `provenance.source_id`
- `level.source`, `tags`, `illustration`, `audio`,     -> `provenance` (kept, not shown; nothing here decides
  `en.etymology_vi`                                       presentation)

`status`, `created_at` and `updated_at` are never read into server state: an
import lands in a `pending_review` set and moderation stays per set.

The README's checks run here, per row, so the preview and the import report
the same thing:

1. the record validates against the schema (else the row is refused, with the
   failing field paths);
2. a `highlight.match` missing from its `text` (or `reading_highlight.match`
   from its `reading`) is a warning, never a refusal;
3. Chinese `zh.chars[].hanzi` joined must equal `headword` (else refused);
4. an `id` repeated inside one source is refused after its first row.
   Duplicates against stored entries are decided by the repository, which
   knows what is published.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from writing_coach.orthography import OrthographyContractError, validate_orthography
from writing_coach.vocabulary_source_import import (
    ParsedVocabularySource,
    VocabularySourceError,
    canonical_vocabulary_identity,
    canonical_vocabulary_normalized_term,
)

SCHEMA_PATH = Path(__file__).with_name("vocabulary_entry.schema.json")
SOURCE_FORMAT = "orena-vocab-entry"
# The schema's language tags, as the catalogue spells them.
LANGUAGE_CODES = {"en": "en", "zh-Hans": "zh"}
FRAMEWORKS = {"CEFR": "CEFR", "HSK3": "HSK3"}
AUTHORED_PROVENANCE = {"source": "orena-authored-entry", "evidence_type": "editorial"}
STATUS_IGNORED_WARNING = (
    "The status in the file is not imported: entries land in a set that is pending review, "
    "and the set is published through the collection lifecycle."
)
# How an authored `related[].relation` is stored as a typed usage note.
_RELATION_TYPES = {
    "family": "word_family",
    "synonym": "synonym",
    "antonym": "antonym",
    "related": "related",
    "compound": "related",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def entry_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator

    schema = entry_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def is_authored_entry(row: Any) -> bool:
    """A row in the authored format: a headword, a schema language and a level object with a scale."""

    return (
        isinstance(row, Mapping)
        and "headword" in row
        and row.get("lang") in LANGUAGE_CODES
        and isinstance(row.get("level"), Mapping)
        and "scale" in row["level"]
    )


def is_authored_source(source: ParsedVocabularySource) -> bool:
    """A JSON/JSONL source whose rows are authored entries.

    One authored row is enough to route the whole source here, so a file that
    mixes formats is validated (and its other rows refused) rather than half
    read by the column mapper.
    """

    return source.format in {"json", "jsonl"} and any(is_authored_entry(row) for row in source.rows)


def schema_errors(record: Mapping[str, Any]) -> list[str]:
    """Each schema failure as `path: message`, in a stable order."""

    errors = sorted(_validator().iter_errors(dict(record)), key=lambda error: list(error.absolute_path))
    out = []
    for error in errors:
        path = "/".join(str(part) for part in error.absolute_path) or "(record)"
        out.append(f"{path}: {error.message}")
    return out


def _occurrences(text: str, match: str) -> int:
    count, start = 0, 0
    while match:
        found = text.find(match, start)
        if found < 0:
            break
        count += 1
        start = found + len(match)
    return count


def highlight_found(text: str, highlight: Mapping[str, Any] | None) -> bool:
    """`match` occurs in `text` at least `occurrence` times (default 1)."""

    if not isinstance(highlight, Mapping):
        return True
    match = _text(highlight.get("match"))
    occurrence = int(highlight.get("occurrence") or 1)
    return bool(match) and _occurrences(str(text or ""), match) >= occurrence


def _localized(language: str, value: Any) -> dict[str, str] | None:
    text = _text(value)
    return {language: text} if text else None


def _support(entry: Mapping[str, Any], key: str) -> dict[str, str] | None:
    """A Vietnamese-authored support field, stored language-tagged so another support language can join it."""

    return _localized("vi", entry.get(key))


def _examples(record: Mapping[str, Any], language: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for example in record.get("examples") or ():
        item: dict[str, Any] = {"language": language, "text": _text(example.get("text")), "origin": "source"}
        if isinstance(example.get("highlight"), Mapping):
            item["highlight"] = dict(example["highlight"])
        if _text(example.get("reading")):
            item["reading"] = _text(example["reading"])
        if isinstance(example.get("reading_highlight"), Mapping):
            item["reading_highlight"] = dict(example["reading_highlight"])
        for source_key, target_key in (
            ("label_vi", "label"),
            ("translation_vi", "translation"),
            ("explanation_vi", "explanation"),
        ):
            value = _support(example, source_key)
            if value:
                item[target_key] = value
        out.append(item)
    return out


def _usage_notes(record: Mapping[str, Any], language: str) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for text in record.get("collocations") or ():
        if _text(text):
            notes.append({"type": "collocation", "text": _text(text), "language": language, "origin": "source"})
    for related in record.get("related") or ():
        note: dict[str, Any] = {
            "type": _RELATION_TYPES[related["relation"]],
            "text": _text(related.get("word")),
            "language": language,
            "origin": "source",
        }
        if related["relation"] == "compound":
            note["relation"] = "compound"
        if _text(related.get("pos")):
            note["pos"] = _text(related["pos"])
        if _text(related.get("reading")):
            note["reading"] = _text(related["reading"])
        gloss = _support(related, "gloss_vi")
        if gloss:
            note["gloss"] = gloss
        notes.append(note)
    zh = record.get("zh") if isinstance(record.get("zh"), Mapping) else {}
    for measure in zh.get("measure_words") or ():
        note = {"type": "classifier", "text": _text(measure.get("mw")), "language": language, "origin": "source"}
        for source_key, target_key in (
            ("pinyin", "reading"),
            ("phrase", "phrase"),
            ("phrase_pinyin", "phrase_reading"),
        ):
            if _text(measure.get(source_key)):
                note[target_key] = _text(measure[source_key])
        notes.append(note)
    tip = _text(record.get("memory_tip_vi"))
    if tip:
        notes.append({"type": "memory_tip", "text": tip, "language": "vi", "origin": "source"})
    return notes


def _orthography(record: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    zh = record.get("zh") if isinstance(record.get("zh"), Mapping) else None
    if not zh:
        return {}
    provenance = {**AUTHORED_PROVENANCE, "reference": source_id}
    units = []
    for char in zh.get("chars") or ():
        readings = [{"value": _text(char.get("pinyin")), "notation": "pinyin"}]
        if _text(char.get("han_viet")):
            readings.append({"value": _text(char["han_viet"]), "notation": "han_viet"})
        facts: dict[str, Any] = {}
        if isinstance(char.get("strokes"), int):
            facts["stroke_count"] = {"value": char["strokes"], "provenance": dict(provenance)}
        radical = char.get("radical")
        if isinstance(radical, Mapping) and _text(radical.get("char")):
            value: dict[str, Any] = {"surface": _text(radical["char"])}
            if _text(radical.get("pinyin")):
                value["reading"] = _text(radical["pinyin"])
            name = _support(radical, "name_vi")
            if name:
                value["name"] = name
            gloss = _support(radical, "meaning_vi")
            if gloss:
                value["gloss"] = gloss
            facts["radical"] = {"value": value, "provenance": dict(provenance)}
        components = [{"surface": _text(part)} for part in char.get("components") or () if _text(part)]
        if components:
            facts["components"] = {"value": components, "provenance": dict(provenance)}
        units.append(
            {
                "surface": _text(char.get("hanzi")),
                "script": "han",
                "unit_kind": "character",
                "readings": readings,
                "facts": facts,
            }
        )
    return {"script": "han", "variant": "simplified", "units": units}


def _provenance_extras(record: Mapping[str, Any]) -> dict[str, Any]:
    """What the source said that no learner field shows yet, kept rather than dropped."""

    extras: dict[str, Any] = {}
    level_source = _text((record.get("level") or {}).get("source"))
    if level_source:
        extras["level_source"] = level_source
    if record.get("tags"):
        extras["tags"] = [_text(tag) for tag in record["tags"] if _text(tag)]
    if isinstance(record.get("illustration"), Mapping):
        extras["illustration"] = dict(record["illustration"])
    if isinstance(record.get("audio"), Mapping):
        extras["audio"] = dict(record["audio"])
    en = record.get("en") if isinstance(record.get("en"), Mapping) else {}
    etymology = _support(en, "etymology_vi")
    if etymology:
        extras["etymology"] = etymology
    if len(record.get("pos") or ()) > 1:
        extras["parts_of_speech"] = [item["code"] for item in record["pos"]]
    return extras


def _topic(record: Mapping[str, Any]) -> str:
    for tag in record.get("tags") or ():
        if _text(tag).startswith("topic:"):
            return _text(tag)[len("topic:"):]
    return ""


def canonical_record(
    record: Mapping[str, Any], *, filename: str, content_hash: str, row: int
) -> dict[str, Any]:
    """One schema-valid authored record as the canonical import record."""

    language = LANGUAGE_CODES[record["lang"]]
    source_id = _text(record["id"])
    term = _text(record["headword"])
    pos = record["pos"][0]["code"]
    meanings = record["meanings"]
    short_meanings: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    for meaning in meanings:
        vi = {"language": "vi", "text": _text(meaning["vi"]), "origin": "source"}
        note = _support(meaning, "note_vi")
        if note:
            vi["note"] = note
        short_meanings.append(vi)
        english = _text(meaning.get("en"))
        if english:
            # For an English word, `en` is its definition; for a Chinese one it
            # is the meaning in English, a support language like Vietnamese.
            target = detailed if language == "en" else short_meanings
            target.append({"language": "en", "text": english, "origin": "source"})
    pronunciations: list[dict[str, Any]] = []
    readings: list[dict[str, Any]] = []
    en = record.get("en") if isinstance(record.get("en"), Mapping) else {}
    for region in ("uk", "us"):
        ipa = _text((en.get("ipa") or {}).get(region))
        if ipa:
            pronunciations.append(
                {"text": ipa, "kind": "pronunciation", "notation": "ipa", "region": region, "origin": "source"}
            )
    zh = record.get("zh") if isinstance(record.get("zh"), Mapping) else {}
    if _text(zh.get("pinyin")):
        readings.append({"text": _text(zh["pinyin"]), "kind": "reading", "notation": "pinyin", "origin": "source"})
    examples = _examples(record, language)
    usage_notes = _usage_notes(record, language)
    orthography = _orthography(record, source_id)
    values = {
        "term": term,
        "pronunciations": pronunciations,
        "readings": readings,
        "short_meanings": short_meanings,
        "detailed_definitions": detailed,
        "part_of_speech": pos,
        "examples": examples,
        "usage_notes": usage_notes,
        "orthography": orthography,
        "level": _text(record["level"]["value"]),
        "framework": FRAMEWORKS[record["level"]["scale"]],
        "topic": _topic(record),
    }
    return {
        **values,
        "language_code": language,
        "normalized_term": canonical_vocabulary_normalized_term(language_code=language, term=term),
        "identity_key": canonical_vocabulary_identity(
            language_code=language, term=term, part_of_speech=pos, sense_key=source_id
        ),
        "sense_key": source_id,
        "content_origins": {field: "source" for field, value in values.items() if value},
        "provenance": {
            "filename": filename,
            "format": SOURCE_FORMAT,
            "content_hash": content_hash,
            "row": row,
            "origin": "source",
            "source_id": source_id,
            **_provenance_extras(record),
        },
    }


def row_warnings(record: Mapping[str, Any]) -> list[str]:
    warnings = []
    for index, example in enumerate(record.get("examples") or (), start=1):
        if not highlight_found(example.get("text", ""), example.get("highlight")):
            warnings.append(f"examples/{index}: the highlight is not in the sentence; it will show unhighlighted.")
        if "reading_highlight" in example and not highlight_found(
            example.get("reading", ""), example.get("reading_highlight")
        ):
            warnings.append(
                f"examples/{index}: the reading highlight is not in the reading; it will show unhighlighted."
            )
    return warnings


def row_refusal(record: Mapping[str, Any], language_code: str) -> str:
    """Why this row cannot be imported, or ''."""

    errors = schema_errors(record)
    if errors:
        return "schema: " + "; ".join(errors[:8]) + (f"; and {len(errors) - 8} more" if len(errors) > 8 else "")
    language = LANGUAGE_CODES[record["lang"]]
    if language != language_code:
        return f"the entry is in '{language}', the set is in '{language_code}'"
    zh = record.get("zh") if isinstance(record.get("zh"), Mapping) else None
    if zh is not None:
        joined = "".join(_text(char.get("hanzi")) for char in zh.get("chars") or ())
        if joined != _text(record["headword"]):
            return f"zh.chars spell '{joined}', not the headword '{_text(record['headword'])}'"
    return ""


def normalize_authored_entries(source: ParsedVocabularySource, *, language_code: str) -> dict[str, Any]:
    """The authored rows as canonical records, with the same report shape `normalize_vocabulary_rows` returns.

    `rows` adds one line per source row for the preview: its id, headword and
    outcome (`ready`, or `refused` with a reason), and its warnings.
    """

    language = _text(language_code).casefold()
    if not language:
        raise VocabularySourceError("Target language is required for import.")
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    status_seen = False
    for row_number, row in enumerate(source.rows, start=1):
        source_id = _text(row.get("id")) if isinstance(row, Mapping) else ""
        headword = _text(row.get("headword")) if isinstance(row, Mapping) else ""
        if isinstance(row, Mapping) and "status" in row:
            status_seen = True
        reason = row_refusal(row, language)
        if not reason and source_id in seen:
            reason = "duplicate id in source; the first row with this id is kept"
        report = {"row": row_number, "id": source_id, "term": headword, "warnings": [], "outcome": "ready"}
        if reason:
            report.update(outcome="refused", reason=reason)
            skipped.append({"row": row_number, "reason": reason, "term": headword, "id": source_id})
            rows.append(report)
            continue
        record = canonical_record(row, filename=source.filename, content_hash=source.content_hash, row=row_number)
        if record["orthography"]:
            try:
                validate_orthography(record["orthography"])
            except OrthographyContractError as error:
                reason = f"zh.chars: {error}"
                report.update(outcome="refused", reason=reason)
                skipped.append({"row": row_number, "reason": reason, "term": headword, "id": source_id})
                rows.append(report)
                continue
        seen.add(source_id)
        row_notes = row_warnings(row)
        report["warnings"] = row_notes
        warnings.extend(f"{source_id}: {note}" for note in row_notes)
        report["identity_key"] = record["identity_key"]
        records.append(record)
        rows.append(report)
    if status_seen:
        warnings.append(STATUS_IGNORED_WARNING)
    if skipped:
        warnings.append(f"Refused {len(skipped)} row(s); inspect the row reasons before retrying.")
    return {
        "filename": source.filename,
        "format": SOURCE_FORMAT,
        "content_hash": source.content_hash,
        "records": records,
        "skipped": skipped,
        "warnings": warnings,
        "rows": rows,
    }

