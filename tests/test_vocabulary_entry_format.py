"""The authored vocabulary entry format (docs/vocab) read into the existing catalogue record (D-17V).

The fixtures are the reference contract itself, `docs/vocab/samples/*.json`, not copies.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from writing_coach import vocabulary_entry_format as fmt
from writing_coach.becoming_library import _reading_texts
from writing_coach.orthography import validate_orthography
from writing_coach.vocabulary_source_import import VocabularySourceError, parse_vocabulary_source
from writing_coach.vocabulary_usage_notes import (
    USAGE_NOTE_TYPES,
    UsageNoteError,
    group_usage_notes,
    note_type,
    validate_usage_note,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "docs" / "vocab" / "samples"


def sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def source_of(rows, filename="entries.json"):
    if filename.endswith(".jsonl"):
        raw = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")
    else:
        raw = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    return parse_vocabulary_source(filename, raw)


def normalized(rows, language, filename="entries.json"):
    return fmt.normalize_authored_entries(source_of(rows, filename), language_code=language)


def test_the_vendored_schema_is_the_reference_contract_byte_for_byte():
    """The runtime image ships writing_coach/, not docs/; the copy must never drift."""

    assert fmt.SCHEMA_PATH.read_bytes() == (ROOT / "docs" / "vocab" / "vocab_entry.schema.json").read_bytes()


@pytest.mark.parametrize("name", ["en_resilient", "zh_senlin"])
def test_both_reference_samples_validate_and_are_detected(name):
    record = sample(name)
    assert fmt.schema_errors(record) == []
    assert fmt.is_authored_source(source_of([record]))


def test_a_column_file_is_not_mistaken_for_the_authored_format():
    plain = parse_vocabulary_source("words.json", json.dumps([{"term": "allocate", "meaning": "phân bổ"}]).encode())
    assert not fmt.is_authored_source(plain)


def test_english_sample_lands_in_existing_columns_and_json_keys():
    result = normalized([sample("en_resilient")], "en")
    assert [row["outcome"] for row in result["rows"]] == ["ready"]
    record = result["records"][0]
    assert record["term"] == "resilient" and record["language_code"] == "en"
    assert record["part_of_speech"] == "adjective"
    assert (record["level"], record["framework"]) == ("C1", "CEFR")
    assert record["provenance"]["level_source"] == "Oxford 5000"
    # The authored id is an editorial handle, not a sense: no identity inflation (D-17V).
    assert record["identity_key"] == "en|resilient|adjective|"
    assert record["sense_key"] == "" and record["provenance"]["source_id"] == "en:resilient"
    assert [(p["region"], p["text"]) for p in record["pronunciations"]] == [
        ("uk", "/rɪˈzɪliənt/"), ("us", "/rɪˈzɪljənt/"),
    ]
    assert record["readings"] == []
    # `en` of an English word is its definition; the Vietnamese meaning is a support-language meaning.
    assert record["short_meanings"] == [
        {"language": "vi", "text": "kiên cường; có khả năng phục hồi nhanh", "origin": "source"}
    ]
    assert record["detailed_definitions"][0]["language"] == "en"
    first = record["examples"][0]
    assert first["text"] == "Children are often more resilient than adults expect."
    assert first["highlight"] == {"match": "resilient"}
    assert first["label"] == {"vi": "Chỉ người"}
    assert first["translation"] == {"vi": "Trẻ em thường kiên cường hơn người lớn nghĩ."}
    assert first["explanation"]["vi"].startswith("Nói về tinh thần")
    groups = group_usage_notes(record["usage_notes"])
    assert [n["text"] for n in groups["collocation"]] == ["highly resilient", "remarkably resilient", "a resilient economy"]
    assert [(n["text"], n.get("pos")) for n in groups["word_family"]] == [("resilience", "(n)"), ("resiliently", "(adv)")]
    assert [n["text"] for n in groups["synonym"]] == ["tough", "hardy"]
    assert [n["text"] for n in groups["antonym"]] == ["fragile", "vulnerable"]
    assert groups["memory_tip"][0]["language"] == "vi"
    assert groups["usage"] == [] and groups["common_mistake"] == []
    assert record["orthography"] == {}
    assert record["topic"] == "character"
    assert record["provenance"]["etymology"] == {"vi": "Từ Latin resilire, “bật trở lại”."}
    assert record["provenance"]["illustration"]["ref"] == "sprout-through-crack"
    # Server state never comes from the file.
    assert "status" not in record and "created_at" not in record
    assert fmt.STATUS_IGNORED_WARNING in result["warnings"]


def test_chinese_sample_keeps_one_reading_and_puts_han_viet_in_orthography():
    result = normalized([sample("zh_senlin")], "zh")
    record = result["records"][0]
    assert record["language_code"] == "zh" and record["term"] == "森林"
    assert (record["level"], record["framework"]) == ("4", "HSK3")
    # Exactly one reading: a second (Hán-Việt) would stop a saved word linking to this entry.
    assert _reading_texts(record) == ["sēnlín"]
    validate_orthography(record["orthography"])
    units = record["orthography"]["units"]
    assert [unit["surface"] for unit in units] == ["森", "林"]
    assert units[0]["readings"] == [{"value": "sēn", "notation": "pinyin"}, {"value": "SÂM", "notation": "han_viet"}]
    assert units[0]["facts"]["stroke_count"]["value"] == 12
    assert units[0]["facts"]["radical"]["value"] == {"surface": "木", "reading": "mù", "name": {"vi": "Mộc"}, "gloss": {"vi": "cây"}}
    assert [c["surface"] for c in units[0]["facts"]["components"]["value"]] == ["木", "木", "木"]
    assert {m["language"] for m in record["short_meanings"]} == {"vi", "en"}
    assert record["detailed_definitions"] == []
    example = record["examples"][0]
    assert example["highlight"] == {"match": "森林"}
    assert example["reading"] == "Zhè piàn sēnlín lǐ zhùzhe hěn duō dòngwù."
    assert example["reading_highlight"] == {"match": "sēnlín"}
    groups = group_usage_notes(record["usage_notes"])
    assert groups["classifier"] == [{
        "type": "classifier", "text": "片", "language": "zh", "origin": "source",
        "reading": "piàn", "phrase": "一片森林", "phrase_reading": "yí piàn sēnlín",
    }]
    assert [(n["text"], n.get("relation"), n.get("gloss")) for n in groups["related"]] == [
        ("树林", None, {"vi": "rừng cây"}), ("森林火灾", "compound", {"vi": "cháy rừng"}),
    ]


def test_a_missing_highlight_is_a_warning_not_a_refusal():
    record = sample("en_resilient")
    record["examples"][0]["highlight"] = {"match": "sturdy"}
    zh = sample("zh_senlin")
    zh["examples"][1]["reading_highlight"] = {"match": "sēnlín", "occurrence": 2}
    en_result = normalized([record], "en")
    zh_result = normalized([zh], "zh")
    assert en_result["rows"][0]["outcome"] == "ready"
    assert "highlight is not in the sentence" in en_result["rows"][0]["warnings"][0]
    assert zh_result["rows"][0]["outcome"] == "ready"
    assert "reading highlight is not in the reading" in zh_result["rows"][0]["warnings"][0]


def test_chinese_units_must_spell_the_headword():
    record = sample("zh_senlin")
    record["zh"]["chars"] = list(reversed(record["zh"]["chars"]))
    result = normalized([record], "zh")
    assert result["records"] == []
    assert result["rows"][0]["outcome"] == "refused"
    assert "not the headword" in result["rows"][0]["reason"]


def test_a_schema_failure_is_refused_with_the_field_path():
    record = sample("en_resilient")
    record["level"]["value"] = "HSK 4"
    del record["meanings"]
    result = normalized([record], "en")
    reason = result["rows"][0]["reason"]
    assert result["rows"][0]["outcome"] == "refused"
    assert reason.startswith("schema:")
    assert "'meanings' is a required property" in reason


def test_an_id_repeated_in_one_file_keeps_only_its_first_row():
    first = sample("en_resilient")
    second = copy.deepcopy(first)
    second["meanings"][0]["vi"] = "bền bỉ"
    result = normalized([first, second], "en")
    assert [row["outcome"] for row in result["rows"]] == ["ready", "refused"]
    assert "duplicate id in source" in result["rows"][1]["reason"]
    assert len(result["records"]) == 1


def test_an_entry_in_another_language_than_the_set_is_refused():
    result = normalized([sample("zh_senlin")], "en")
    assert result["rows"][0]["outcome"] == "refused"
    assert "the set is in 'en'" in result["rows"][0]["reason"]


def test_jsonl_goes_through_the_same_parser_and_adapter():
    rows = [sample("en_resilient"), sample("zh_senlin")]
    source = source_of(rows, "entries.jsonl")
    assert source.format == "jsonl" and len(source.rows) == 2
    result = fmt.normalize_authored_entries(source, language_code="en")
    assert [row["outcome"] for row in result["rows"]] == ["ready", "refused"]


def test_jsonl_names_the_broken_line():
    raw = (json.dumps(sample("en_resilient")) + "\n{not json\n").encode()
    with pytest.raises(VocabularySourceError, match="line 2"):
        parse_vocabulary_source("entries.jsonl", raw)


def test_usage_note_types_are_closed_and_legacy_notes_are_usage():
    assert USAGE_NOTE_TYPES == (
        "collocation", "synonym", "antonym", "word_family", "related", "classifier", "memory_tip", "usage",
        "common_mistake",
    )
    assert note_type({"text": "Not with a bare noun."}) == "usage"
    assert note_type("plain string") == "usage"
    validate_usage_note({"type": "common_mistake", "text": "x"})
    with pytest.raises(UsageNoteError):
        validate_usage_note({"type": "etymology", "text": "x"})
    with pytest.raises(UsageNoteError):
        validate_usage_note({"type": "usage", "text": ""})


def test_every_note_the_adapter_writes_satisfies_the_typed_contract():
    for name, language in (("en_resilient", "en"), ("zh_senlin", "zh")):
        for note in normalized([sample(name)], language)["records"][0]["usage_notes"]:
            validate_usage_note(note)
