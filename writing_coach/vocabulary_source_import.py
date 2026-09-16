"""Source parsing and normalization for the shared vocabulary catalog.

The importer deliberately stops at *source truth*.  It does not call an AI
provider and it never fills a missing pronunciation, translation, definition,
example, or part of speech.  Enrichment can be added as a separate stage later
because every imported field carries an explicit ``origin`` marker.

This module is independent of persistence so the Admin preview can be useful
even while a deployment is waiting for the vocabulary-content migration.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any


CANONICAL_FIELDS = (
    "term",
    "short_meaning",
    "detailed_definition",
    "pronunciation",
    "part_of_speech",
    "example",
    "usage",
    "level",
    "framework",
    "topic",
    "meaning_language",
    "target_language",
    "reading",
    "orthography",
    "sense_key",
)

REQUIRED_FIELDS = ("term",)
MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_SOURCE_ROWS = 100_000
_LANGUAGE_CODE_RE = re.compile(r"[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{2,8})?")


class VocabularySourceError(ValueError):
    """A source cannot be parsed or normalized truthfully."""


class VocabularyMappingRequired(VocabularySourceError):
    """The source needs an explicit mapping before it can be imported."""


@dataclass(frozen=True)
class ParsedVocabularySource:
    filename: str
    format: str
    headers: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    content_hash: str


@dataclass(frozen=True)
class DetectedVocabularyMapping:
    mapping: dict[str, str | None]
    confidence: dict[str, str]
    warnings: tuple[str, ...]


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\ufeff", "").split()).strip()


def _field_token(value: object) -> str:
    text = unicodedata.normalize("NFKC", _clean_text(value)).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def _format_for_filename(filename: str) -> str:
    suffix = PurePath(filename or "").suffix.casefold()
    if suffix == ".csv":
        return "csv"
    if suffix == ".tsv":
        return "tsv"
    if suffix == ".json":
        return "json"
    if suffix in {".txt", ".text"}:
        return "txt"
    if suffix in {".xlsx", ".xlsm"}:
        return "xlsx"
    raise VocabularySourceError(
        "Unsupported vocabulary source format. Use CSV, TSV, JSON, or TXT."
    )


def _decode_source(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise VocabularySourceError(
            "Source must be UTF-8 encoded; the file was not decoded."
        ) from exc


def _rows_from_json(value: object) -> tuple[list[str], list[dict[str, Any]]]:
    payload = value
    if isinstance(payload, Mapping):
        for key in ("entries", "items", "words", "data", "rows"):
            candidate = payload.get(key)
            if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
                payload = candidate
                break
        else:
            payload = [payload]
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise VocabularySourceError("JSON source must contain an object or an array.")

    rows: list[dict[str, Any]] = []
    for position, item in enumerate(payload, start=1):
        if isinstance(item, Mapping):
            rows.append({str(key): value for key, value in item.items()})
        elif isinstance(item, (str, int, float)) and not isinstance(item, bool):
            rows.append({"term": str(item)})
        else:
            raise VocabularySourceError(
                f"JSON row {position} must be an object or a scalar term."
            )
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers, rows


def parse_vocabulary_source(filename: str, raw: bytes) -> ParsedVocabularySource:
    """Parse one upload without applying a field mapping."""

    name = _clean_text(filename) or "source"
    if len(raw) > MAX_SOURCE_BYTES:
        raise VocabularySourceError(
            f"Source is too large ({MAX_SOURCE_BYTES // (1024 * 1024)} MB maximum)."
        )
    source_format = _format_for_filename(name)
    if source_format == "xlsx":
        # openpyxl is intentionally not a base dependency.  Do not silently
        # reinterpret a binary workbook as text or ask the worker to install a
        # random host dependency during an import request.
        try:
            import openpyxl  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise VocabularySourceError(
                "XLSX import is unavailable in this runtime. Export the sheet as UTF-8 CSV/TSV, "
                "or enable the optional openpyxl importer for this deployment."
            ) from exc
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        worksheet = workbook.active
        values = list(worksheet.iter_rows(values_only=True))
        workbook.close()
        if not values:
            raise VocabularySourceError("The XLSX source has no rows.")
        headers = [_clean_text(value) or f"column_{index + 1}" for index, value in enumerate(values[0])]
        rows = [
            {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            for row in values[1:]
        ]
    elif source_format == "json":
        try:
            payload = json.loads(_decode_source(raw))
        except json.JSONDecodeError as exc:
            raise VocabularySourceError(f"Invalid JSON: {exc.msg}.") from exc
        headers, rows = _rows_from_json(payload)
    elif source_format == "txt":
        lines = [_clean_text(line) for line in _decode_source(raw).splitlines()]
        rows = [{"term": line} for line in lines if line]
        headers = ["term"]
    else:
        text = _decode_source(raw)
        delimiter = "\t" if source_format == "tsv" else ","
        if source_format == "csv":
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
        if not headers:
            raise VocabularySourceError("The tabular source has no header row.")
        rows = [{str(key): value for key, value in row.items()} for row in reader]

    if not rows:
        raise VocabularySourceError("The source contains no data rows.")
    if len(rows) > MAX_SOURCE_ROWS:
        raise VocabularySourceError(
            f"Source contains too many rows ({MAX_SOURCE_ROWS:,} maximum)."
        )
    return ParsedVocabularySource(
        filename=name,
        format=source_format,
        headers=tuple(headers),
        rows=tuple(rows),
        content_hash=hashlib.sha256(raw).hexdigest(),
    )


_FIELD_ALIASES: dict[str, tuple[tuple[str, int], ...]] = {
    "term": (
        ("term", 100), ("word", 100), ("headword", 100), ("expression", 90),
        ("english", 86), ("chinese", 86), ("hanzi", 86), ("simplified", 82),
        ("traditional", 82), ("vocabulary", 80),
    ),
    "short_meaning": (
        ("shortmeaning", 100), ("gloss", 96), ("translation", 92),
        ("meaning", 90), ("vietnamese", 88), ("native", 80), ("meaningvi", 100),
        ("translationvi", 100), ("meaningzh", 92),
    ),
    "detailed_definition": (
        ("detaileddefinition", 100), ("definition", 95), ("description", 82),
        ("explanation", 82), ("definitionen", 92),
    ),
    "pronunciation": (
        ("pronunciation", 100), ("phonetic", 100), ("ipa", 100),
        ("phonetics", 96), ("pronunciationipa", 100),
    ),
    "reading": (("reading", 100), ("readings", 100), ("pinyin", 100), ("jyutping", 100)),
    "part_of_speech": (("partofspeech", 100), ("pos", 100), ("wordclass", 88), ("category", 70)),
    "example": (("example", 100), ("examples", 100), ("sentences", 86), ("examplesentence", 100)),
    "usage": (("usage", 100), ("grammar", 90), ("usagenote", 100), ("collocation", 88)),
    "level": (("level", 100), ("cefr", 100), ("hsk", 100), ("difficulty", 82), ("rank", 65)),
    "framework": (("framework", 100), ("system", 80), ("exam", 75)),
    "topic": (("topic", 100), ("theme", 88), ("category", 65)),
    "meaning_language": (("meaninglanguage", 100), ("supportlanguage", 100), ("languageofmeaning", 100)),
    "target_language": (("targetlanguage", 100), ("learninglanguage", 100)),
    "orthography": (("orthography", 100), ("script", 90), ("characters", 80)),
    "sense_key": (("sensekey", 100), ("senseid", 100), ("meaningid", 95)),
}


def detect_vocabulary_mapping(source: ParsedVocabularySource) -> DetectedVocabularyMapping:
    """Suggest a safe mapping, leaving ambiguous fields unmapped."""

    mapping: dict[str, str | None] = {field: None for field in CANONICAL_FIELDS}
    confidence: dict[str, str] = {field: "none" for field in CANONICAL_FIELDS}
    warnings: list[str] = []
    used_headers: set[str] = set()
    tokenized_headers = {header: _field_token(header) for header in source.headers}
    for field, aliases in _FIELD_ALIASES.items():
        candidates: list[tuple[int, str]] = []
        for header, token in tokenized_headers.items():
            scores = [score for alias, score in aliases if token == alias]
            if scores:
                candidates.append((max(scores), header))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        if not candidates:
            continue
        best_score = candidates[0][0]
        best = [header for score, header in candidates if score == best_score]
        if len(best) > 1:
            warnings.append(
                f"Field '{field}' has multiple equally likely source columns; choose one explicitly."
            )
            continue
        header = best[0]
        if header in used_headers and field not in {"short_meaning", "detailed_definition"}:
            continue
        mapping[field] = header
        used_headers.add(header)
        confidence[field] = "high" if best_score >= 95 else "medium"
    if mapping["term"] is None:
        warnings.append("No term column was detected; map a source column to term before importing.")
    for field in ("short_meaning", "detailed_definition"):
        if mapping[field] is None:
            warnings.append(f"No {field.replace('_', ' ')} column was detected; it will remain empty.")
    return DetectedVocabularyMapping(mapping=mapping, confidence=confidence, warnings=tuple(warnings))


def _mapping_value(row: Mapping[str, Any], mapping: Mapping[str, str | None], field: str) -> Any:
    header = mapping.get(field)
    return row.get(header) if header else None


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        selected = (
            value.get("text")
            or value.get("value")
            or value.get("term")
            or value.get("meaning")
        )
        if selected is not None:
            return _list_value(selected)
        values: list[str] = []
        for item in value.values():
            values.extend(_list_value(item))
        return values
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        values: list[str] = []
        for item in value:
            values.extend(_list_value(item))
        return values
    text = _clean_text(value)
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        decoded = None
    if isinstance(decoded, Sequence) and not isinstance(decoded, (str, bytes)):
        return _list_value(decoded)
    if isinstance(decoded, Mapping):
        return _list_value(decoded)
    return [part.strip() for part in re.split(r"\s*[;|]\s*", text) if part.strip()]


def _json_value(value: Any) -> Any:
    if isinstance(value, (Mapping, list)):
        return value
    text = _clean_text(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text, "origin": "source"}


def _normalize_term(term: str, language_code: str) -> str:
    # NFC preserves accents and distinguishes résumé from resume.  Casefold is
    # useful for Latin scripts; CJK has no case to fold and keeps its original
    # simplified/traditional spelling.  Whitespace is collapsed for all.
    normalized = unicodedata.normalize("NFC", term)
    normalized = " ".join(normalized.split()).strip()
    return normalized.casefold() if language_code not in {"zh", "ja", "ko"} else normalized


def canonical_vocabulary_normalized_term(*, language_code: str, term: str) -> str:
    """Return the normalized term used by the shared vocabulary identity."""

    language = _clean_text(language_code).casefold()
    return _normalize_term(_clean_text(term), language)


def canonical_vocabulary_identity(
    *, language_code: str, term: str, part_of_speech: str = "", sense_key: str = ""
) -> str:
    """Return a stable language-aware lexical identity key.

    An explicit sense key wins.  When a source does not provide one, callers
    may pass a normalized short meaning/definition fingerprint.  The fallback
    intentionally keeps POS in the identity so a homograph can have distinct
    lexical records without attempting to solve full dictionary sense
    disambiguation.
    """

    language = _clean_text(language_code).casefold()
    normalized_term = canonical_vocabulary_normalized_term(
        language_code=language, term=term
    )
    pos = _field_token(part_of_speech)
    sense = _normalize_term(_clean_text(sense_key), language)[:240]
    return "|".join((language, normalized_term, pos, sense))


def stable_collection_id(title: str, language_code: str, framework: str = "") -> str:
    """Create a deterministic display-independent id for an imported pack."""

    language = _clean_text(language_code).casefold()
    source = "-".join(
        part for part in (_clean_text(language), _clean_text(framework), _clean_text(title)) if part
    )
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKC", source).casefold()).strip("-")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    if not slug:
        slug = f"{language or 'unknown'}-collection"
    # Keep the readable prefix, but include the source hash so punctuation,
    # transliteration, or two non-Latin titles cannot silently collide.
    return f"{slug[:147]}-{digest}"


def normalize_vocabulary_rows(
    source: ParsedVocabularySource,
    *,
    mapping: Mapping[str, str | None],
    language_code: str,
    meaning_language: str = "",
    collection_level: str = "",
    collection_framework: str = "",
    collection_topic: str = "",
) -> dict[str, Any]:
    """Map and validate rows, returning source-only canonical records."""

    language = _clean_text(language_code).casefold()
    if not language:
        raise VocabularySourceError("Target language is required for import.")
    if not _LANGUAGE_CODE_RE.fullmatch(language):
        raise VocabularySourceError("Target language must be a valid language code.")
    missing = [field for field in REQUIRED_FIELDS if not mapping.get(field)]
    if missing:
        raise VocabularyMappingRequired(
            "Map the required source field(s) before importing: " + ", ".join(missing) + "."
        )
    invalid_headers = [header for header in mapping.values() if header and header not in source.headers]
    if invalid_headers:
        raise VocabularyMappingRequired(
            "The mapping refers to a source column that is not present: " + ", ".join(sorted(set(invalid_headers)))
        )

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row_number, row in enumerate(source.rows, start=2):
        term = _clean_text(_mapping_value(row, mapping, "term"))
        if not term:
            skipped.append({"row": row_number, "reason": "term is empty"})
            continue
        # Validate the row's target language before deriving identity or
        # updating the source-local deduplication set.  An invalid first row
        # must not suppress a valid later row with the same term.
        target_language = _clean_text(_mapping_value(row, mapping, "target_language")).casefold() or language
        if not _LANGUAGE_CODE_RE.fullmatch(target_language):
            skipped.append(
                {
                    "row": row_number,
                    "reason": f"target language '{target_language}' is not a valid language code",
                    "term": term,
                }
            )
            continue
        if target_language != language:
            skipped.append(
                {
                    "row": row_number,
                    "reason": f"target language '{target_language}' does not match collection language '{language}'",
                    "term": term,
                }
            )
            continue
        pos = _clean_text(_mapping_value(row, mapping, "part_of_speech"))
        short_texts = _list_value(_mapping_value(row, mapping, "short_meaning"))
        detailed_texts = _list_value(_mapping_value(row, mapping, "detailed_definition"))
        explicit_sense = _clean_text(_mapping_value(row, mapping, "sense_key"))
        sense_seed = explicit_sense or (short_texts[0] if short_texts else (detailed_texts[0] if detailed_texts else ""))
        identity_key = canonical_vocabulary_identity(
            language_code=language,
            term=term,
            part_of_speech=pos,
            sense_key=sense_seed,
        )
        if identity_key in seen:
            skipped.append({"row": row_number, "reason": "duplicate identity in source", "term": term})
            continue
        seen.add(identity_key)
        row_level = _clean_text(_mapping_value(row, mapping, "level")) or _clean_text(collection_level)
        row_framework = _clean_text(_mapping_value(row, mapping, "framework")) or _clean_text(collection_framework)
        row_topic = _clean_text(_mapping_value(row, mapping, "topic")) or _clean_text(collection_topic)
        row_meaning_language = (
            _clean_text(_mapping_value(row, mapping, "meaning_language"))
            or _clean_text(meaning_language)
            or ""
        ).casefold()
        pronunciation = _list_value(_mapping_value(row, mapping, "pronunciation"))
        readings = _list_value(_mapping_value(row, mapping, "reading"))
        examples = [
            {"language": target_language, "text": text, "origin": "source"}
            for text in _list_value(_mapping_value(row, mapping, "example"))
        ]
        usage_notes = [
            {"language": target_language, "text": text, "origin": "source"}
            for text in _list_value(_mapping_value(row, mapping, "usage"))
        ]
        orthography = _json_value(_mapping_value(row, mapping, "orthography"))
        source_values = {
            "term": term,
            "pronunciations": pronunciation,
            "readings": readings,
            "short_meanings": short_texts,
            "detailed_definitions": detailed_texts,
            "part_of_speech": pos,
            "examples": examples,
            "usage_notes": usage_notes,
            "orthography": orthography,
            "level": row_level,
            "framework": row_framework,
            "topic": row_topic,
        }
        record = {
            "term": term,
            "language_code": language,
            "normalized_term": _normalize_term(term, language),
            "identity_key": identity_key,
            # Persist the exact sense seed used to derive identity.  This is
            # explicit source sense data when available, otherwise the
            # source-provided short meaning/definition fingerprint.
            "sense_key": sense_seed,
            "pronunciations": [
                {"text": text, "kind": "pronunciation", "origin": "source"}
                for text in pronunciation
            ],
            "readings": [
                {"text": text, "kind": "reading", "origin": "source"}
                for text in readings
            ],
            "short_meanings": [
                {"language": row_meaning_language or "unknown", "text": text, "origin": "source"}
                for text in short_texts
            ],
            "detailed_definitions": [
                {"language": target_language, "text": text, "origin": "source"}
                for text in detailed_texts
            ],
            "part_of_speech": pos,
            "examples": examples,
            "usage_notes": usage_notes,
            "orthography": orthography,
            "level": row_level,
            "framework": row_framework,
            "topic": row_topic,
            "content_origins": {
                field: "source"
                for field in (
                    "term", "pronunciations", "readings", "short_meanings",
                    "detailed_definitions", "part_of_speech", "examples",
                    "usage_notes", "orthography", "level", "framework", "topic",
                )
                if source_values.get(field)
            },
            "provenance": {
                "filename": source.filename,
                "format": source.format,
                "content_hash": source.content_hash,
                "row": row_number,
                "origin": "source",
            },
        }
        records.append(record)

    if not records and not skipped:
        warnings.append("The source had no importable rows.")
    if skipped:
        warnings.append(f"Skipped {len(skipped)} row(s); inspect the row reasons before retrying.")
    return {
        "filename": source.filename,
        "format": source.format,
        "content_hash": source.content_hash,
        "records": records,
        "skipped": skipped,
        "warnings": warnings,
    }


def record_value_present(field: str, local_values: Mapping[str, Any]) -> bool:
    """Keep origin metadata truthful without making empty values look sourced."""

    value_map = {
        "term": local_values.get("term"),
        "pronunciations": local_values.get("pronunciation"),
        "readings": local_values.get("readings"),
        "short_meanings": local_values.get("short_texts"),
        "detailed_definitions": local_values.get("detailed_texts"),
        "part_of_speech": local_values.get("pos"),
        "examples": local_values.get("examples"),
        "usage_notes": local_values.get("usage_notes"),
        "orthography": local_values.get("orthography"),
        "level": local_values.get("row_level"),
        "framework": local_values.get("row_framework"),
        "topic": local_values.get("row_topic"),
    }
    value = value_map.get(field)
    return bool(value) if not isinstance(value, str) else bool(value.strip())
