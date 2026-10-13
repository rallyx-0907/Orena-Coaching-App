"""The n8n Vocabulary Generator (integrations/n8n) against what the repository itself says.

Three kinds of check, none of which needs n8n or a network:

1. The workflow carries the repo schema byte for byte, and the committed JSON is what its sources build.
2. The workflow's validator agrees with `jsonschema` on a shared set of cases (the JS side of the same cases is
   scripts/test_n8n_vocab_workflow.mjs), so the two cannot drift apart.
3. The files the workflow generates are accepted by the REAL admin preview / import routes, land in a set that is
   pending review, and the real responses keep the shape the workflow's strict readers expect. If app.py changes
   a response, this fails and the fixture (and the workflow's readers) must be revisited together.
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

import app as app_module

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "integrations" / "n8n" / "orena_vocab_generator.json"
SCHEMA = ROOT / "docs" / "vocab" / "vocab_entry.schema.json"
FIXTURES = ROOT / "tests" / "fixtures"
SAMPLES = ROOT / "docs" / "vocab" / "samples"


def _workflow() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 1. the schema in the workflow, and the build


def test_embedded_schema_is_the_repo_schema() -> None:
    repo_text = SCHEMA.read_bytes().decode("utf-8").replace("\r\n", "\n")
    carriers = [
        node
        for node in _workflow()["nodes"]
        if node["type"] == "n8n-nodes-base.code" and "const VOCAB_SCHEMA_TEXT = " in node["parameters"]["jsCode"]
    ]
    assert carriers, "no Code node carries the vocabulary schema"
    decoder = json.JSONDecoder()
    for node in carriers:
        code = node["parameters"]["jsCode"]
        start = code.index("const VOCAB_SCHEMA_TEXT = ") + len("const VOCAB_SCHEMA_TEXT = ")
        embedded, _end = decoder.raw_decode(code[start:])  # the JS string literal is a JSON string
        assert embedded == repo_text, f"{node['name']}: the embedded schema differs from docs/vocab/vocab_entry.schema.json"
        assert json.loads(embedded) == json.loads(repo_text)


def test_the_app_schema_and_the_docs_schema_are_one_file() -> None:
    # The app reads writing_coach/vocabulary_entry.schema.json; the workflow copies docs/vocab/. They must not diverge.
    app_copy = ROOT / "writing_coach" / "vocabulary_entry.schema.json"
    assert json.loads(app_copy.read_text(encoding="utf-8")) == json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_committed_workflow_is_what_the_sources_build() -> None:
    spec = importlib.util.spec_from_file_location("build_n8n_workflow", ROOT / "integrations" / "n8n" / "build_workflow.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert WORKFLOW.read_text(encoding="utf-8") == module.render(), (
        "integrations/n8n/orena_vocab_generator.json is stale: run python integrations/n8n/build_workflow.py"
    )


def test_workflow_has_no_credentials_and_no_secrets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = json.loads(text)
    assert {"name", "nodes", "connections", "settings"} <= set(workflow)
    assert all("credentials" not in node for node in workflow["nodes"])
    for needle in ("ORENA_AI_", "/home/node/.n8n-files", "etymology_en"):
        stripped = text.replace(json.dumps(SCHEMA.read_text(encoding="utf-8").replace("\r\n", "\n"), ensure_ascii=False)[1:-1], "")
        assert needle not in stripped, f"{needle} must not appear in the workflow"


# ---------------------------------------------------------------- 2. jsonschema agrees with the shared cases


def _apply(sample: dict, ops: list) -> dict:
    record = copy.deepcopy(sample)
    for op, path, *value in ops:
        parent = record
        for key in path[:-1]:
            parent = parent[key]
        if op == "set":
            new = value[0]
            if new == "__five__":
                new = [copy.deepcopy(record["examples"][0]) for _ in range(5)]
            parent[path[-1]] = new
        else:
            del parent[path[-1]]
    return record


def _cases() -> list[dict]:
    return json.loads((FIXTURES / "n8n_vocab_schema_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_shared_schema_cases_match_jsonschema(case: dict) -> None:
    sample = json.loads((SAMPLES / f"{case['sample']}.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    errors = list(validator.iter_errors(_apply(sample, case["ops"])))
    assert (not errors) is case["valid"], [error.message for error in errors]


# ---------------------------------------------------------------- 3. the real routes


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(exercise())


@pytest.fixture
def repository(tmp_path, monkeypatch):
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repo = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repo.initialize()
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, vocabulary_repository=repo))
    app_module.configure_becoming_library_content(repo)
    return repo


def _ready_files() -> dict[str, tuple[str, bytes]]:
    """The committed example of the workflow's output, split the way the workflow splits it: one file per language."""

    raw = (FIXTURES / "n8n_vocab_ready_example.jsonl").read_text(encoding="utf-8")
    groups: dict[str, list[str]] = {}
    for line in raw.splitlines():
        record = json.loads(line)
        groups.setdefault(record["lang"], []).append(line)
    names = {"en": "en", "zh-Hans": "zh"}
    return {
        lang: (f"example-{names[lang]}.jsonl", ("\n".join(lines) + "\n").encode("utf-8")) for lang, lines in groups.items()
    }


def _metadata(lang: str) -> dict:
    # What the workflow sends (Validate & group -> metadata): honest rights/completeness, no publish flags.
    code = "zh" if lang == "zh-Hans" else "en"
    return {
        "title": f"n8n example {code}",
        "language_code": code,
        "collection_id": f"n8n-example-{code}",
        "rights_status": "unknown",
        "completeness": "partial",
        "provenance": {"label": "n8n-vocab-generator"},
    }


def _preview(name: str, raw: bytes) -> httpx.Response:
    return _request("POST", "/api/admin/vocabulary/preview", files=[("files", (name, raw, "application/x-ndjson"))])


def _import(name: str, raw: bytes, lang: str, duplicates: str = "skip") -> httpx.Response:
    return _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={"metadata": json.dumps(_metadata(lang)), "mappings": "{}", "duplicates": duplicates},
        files=[("files", (name, raw, "application/x-ndjson"))],
    )


def _types(value):
    return type(value).__name__


def _assert_keys_and_types(real: dict, expected: dict, where: str) -> None:
    """Every key the workflow reads exists in the real response with the same JSON type."""

    for key, sample in expected.items():
        assert key in real, f"{where}: the real response has no '{key}'"
        if isinstance(sample, bool) or sample is None:
            continue
        assert _types(real[key]) == _types(sample), f"{where}.{key}: {_types(real[key])} is not {_types(sample)}"


def test_generated_files_preview_ready_and_import_pending_review(repository) -> None:
    fixture = json.loads((FIXTURES / "n8n_vocab_orena_responses.json").read_text(encoding="utf-8"))
    files = _ready_files()
    assert set(files) == {"en", "zh-Hans"}
    for lang, (name, raw) in files.items():
        ids = [json.loads(line)["id"] for line in raw.decode("utf-8").splitlines()]

        preview = _preview(name, raw)
        assert preview.status_code == 200, preview.text
        assert preview.headers["content-type"].startswith("application/json")
        body = preview.json()
        assert list(body) == ["items"] and len(body["items"]) == 1
        item = body["items"][0]
        expected_item = fixture["preview"]["items"][0]
        _assert_keys_and_types(item, expected_item, "preview.items[0]")
        assert item["error"] == "" and item["filename"] == name
        authored = item["authored"]
        _assert_keys_and_types(authored, expected_item["authored"], "preview.authored")
        assert authored["language_code"] == ("zh" if lang == "zh-Hans" else "en")
        assert authored["format"] == "orena-vocab-entry"
        assert [row["id"] for row in authored["rows"]] == ids
        for row in authored["rows"]:
            _assert_keys_and_types(row, expected_item["authored"]["rows"][0], "preview.authored.rows[0]")
            assert row["outcome"] == "ready" and row["existing"] == "new", row
        assert authored["counts"] == {"ready": len(ids)}

        imported = _import(name, raw, lang)
        assert imported.status_code == 200, imported.text
        result = imported.json()
        assert set(result) == {"collection", "items"}
        assert result["collection"]["id"] == f"n8n-example-{authored['language_code']}"
        assert result["collection"]["catalog_status"] == "pending_review"
        _assert_keys_and_types(result["collection"], fixture["import"]["collection"], "import.collection")
        assert len(result["items"]) == 1
        _assert_keys_and_types(result["items"][0], fixture["import_item"], "import.items[0]")
        assert result["items"][0]["status"] == "imported"
        assert result["items"][0]["imported"] == len(ids) and result["items"][0]["failed"] == 0
        assert result["items"][0]["conflicts"] == 0

        # The moderation lifecycle `main` expects: the set exists but is NOT visible to learners until published.
        collection_id = result["collection"]["id"]
        stored = repository.get_collection(collection_id, limit=5, status=None)
        assert stored is not None and len(stored["entries"]) == len(ids)
        assert stored["catalog_status"] == "pending_review"
        assert repository.get_collection(collection_id, limit=5) is None, "a pending set must not be visible as published"
        published_ids = {item["id"] for item in repository.list_collections(authored["language_code"])}
        assert collection_id not in published_ids


def test_a_rerun_is_duplicate_safe_with_skip(repository) -> None:
    fixture = json.loads((FIXTURES / "n8n_vocab_orena_responses.json").read_text(encoding="utf-8"))
    for lang, (name, raw) in _ready_files().items():
        first = _import(name, raw, lang)
        assert first.status_code == 200 and first.json()["items"][0]["imported"] == 1

        preview = _preview(name, raw)
        rows = preview.json()["items"][0]["authored"]["rows"]
        assert all(row["outcome"] == "ready" and row["existing"] == "duplicate" for row in rows), rows

        again = _import(name, raw, lang, duplicates="skip")
        assert again.status_code == 200, again.text
        body = again.json()
        _assert_keys_and_types(body["items"][0], fixture["import_skipped_item"], "import.items[0] (rerun)")
        assert body["items"][0]["status"] == "skipped" and body["items"][0]["duplicates"] == 1
        assert body["items"][0]["imported"] == 0 and body["items"][0]["conflicts"] == 0
        assert body["collection"]["catalog_status"] == "pending_review"


def test_the_workflow_rejects_what_orena_would_refuse(repository) -> None:
    """A record the workflow would never emit (a field outside the schema) is refused by the real preview: the two agree."""

    record = json.loads((SAMPLES / "en_resilient.json").read_text(encoding="utf-8"))
    record["en"]["etymology_en"] = "from Latin resilire"
    raw = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    row = _preview("bad.jsonl", raw).json()["items"][0]["authored"]["rows"][0]
    assert row["outcome"] == "refused" and "etymology_en" in row["reason"]
