"""#197 proofs: a learner never sees the administrator's internal source name.

Two kinds of proof:

1. A walk. A source whose internal name carries a unique marker is registered for English and for Chinese,
   a text is published from each (one with an approved thumbnail), and every learner route that can name a
   source or publisher is read. The marker must appear in none of them, with or without a public name. A
   control asserts the administrator's own reads DO carry it, so the walk is not vacuous.
2. A static grep proof. Every reader of the internal field outside the admin and engine modules is listed;
   a new learner-path reader fails the test until a person reads it and adds it to the allowlist below.
"""
from __future__ import annotations

import ast
import json
import uuid
import re
from pathlib import Path

import pytest
from sqlalchemy import update

from tests.test_reading_content_engine import ARTICLE, ZH_ARTICLE
from tests.test_reading_engine_routes import call, setup  # noqa: F401 - the route fixture
from tests.test_reading_images import (  # noqa: F401 - fixtures of the image suite
    ADMIN_BASE,
    _fresh_preview_cache,
    images,
)
from writing_coach.licences import licences_payload
from writing_coach.persistence.models import ReadingSourceItem
from writing_coach.reading_source_import import SubmittedInput

MARKER_EN = "ZZ-INTERNAL-QA-EN-7f3a91"
MARKER_ZH = "ZZ内部测试来源-7f3a91"
MARKERS = (MARKER_EN, MARKER_ZH, "7f3a91", "内部测试来源")
RIGHTS = {"automation_allowed": False, "can_republish": True, "can_adapt": False,
          "attribution_required": True, "license_note": "CC BY 4.0"}
IMAGE_URL = "https://media.example.org/photos/walk.jpg"


def _register(content, *, slug, name, language, public_name, base_url):
    source = content.create_source(
        slug=slug, name=name, public_name=public_name, source_type="manual", base_url=base_url,
        languages=[language], rights=RIGHTS, created_by="admin")
    content.set_source_state(source["id"], "active", actor="admin")
    return source


def _publish(parts, source, *, body, title, language, url):
    parts["engine"].submit(SubmittedInput(
        kind="text", text=body, title=title, author="", language=language, url=url,
        source_id=source["id"]), actor="admin")
    article_id = parts["engine"].process(parts["jobs"].claim("worker"))["article_id"]
    parts["content"].set_status(article_id, "published", actor="admin")
    return article_id


def _with_candidate(parts, article_id):
    item_id = uuid.UUID(parts["content"].get_article(article_id)["source"]["id"])
    with parts["content"].engine.begin() as connection:
        row = connection.execute(ReadingSourceItem.__table__.select().where(
            ReadingSourceItem.id == item_id)).first()
        metadata = dict(row.metadata_json or {})
        metadata["extraction"] = {**(metadata.get("extraction") or {}), "media": [
            {"role": "og", "url": IMAGE_URL, "alt": "A field", "caption": "", "credit": "",
             "width": 0, "height": 0, "source": "meta:og:image"}]}
        connection.execute(update(ReadingSourceItem).where(ReadingSourceItem.id == item_id)
                           .values(metadata_json=metadata))


def _world(parts, public_name):
    content = parts["content"]
    en = _register(content, slug="walk-en", name=MARKER_EN, language="en", public_name=public_name,
                   base_url="https://news.example.org")
    zh = _register(content, slug="walk-zh", name=MARKER_ZH, language="zh", public_name=public_name,
                   base_url="https://xinwen.example.cn")
    ids = {
        "en": _publish(parts, en, body=ARTICLE, title="Rain returns", language="en",
                       url="https://news.example.org/a/rain"),
        "zh": _publish(parts, zh, body=ZH_ARTICLE, title="雨又回来了", language="zh",
                       url="https://xinwen.example.cn/a/rain"),
    }
    for article_id in ids.values():
        _with_candidate(parts, article_id)
    for source in (en, zh):
        assert call(parts["admin"], "POST", f"{ADMIN_BASE}/sources/{source['id']}/image-policy",
                    json={"allowed": True}).status_code == 200
    # an approved thumbnail on each text, with no explicit credit: the fallback credit is the publisher
    for article_id in ids.values():
        approved = call(parts["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/images/0/approve", json={})
        assert approved.status_code == 200, approved.text
    return ids


def _learner_reads(parts, ids):
    """Every learner response that can name a source or publisher, as (label, text) pairs."""
    learner, seen = parts["learner"], []

    def get(label, path, **kwargs):
        response = call(learner, "GET", path, admin=False, **kwargs)
        assert response.status_code in (200, 304), (label, response.status_code)
        seen.append((label, response.text + json.dumps(dict(response.headers), ensure_ascii=False)))
        return response

    for language in ("en", "zh"):
        get(f"list {language}", f"/api/reading/articles?language={language}")
        get(f"list {language} filtered", f"/api/reading/articles?language={language}&level=A2&topic=environment")
        get(f"list {language} paged", f"/api/reading/articles?language={language}&limit=1")
        detail = get(f"detail {language}", f"/api/reading/articles/{ids[language]}")
        image = detail.json()["image"]
        assert image and image["credit"], "the thumbnail is credited, so the route is walked"
        get(f"image {language}", image["url"])
    content = parts["content"]
    # The licences page (/api/licences) is built from exactly these three reads in app.py.
    credits = licences_payload(reading_sources=content.list_sources, reading_texts=content.published_credits)
    seen.append(("licences", json.dumps(credits, ensure_ascii=False)))
    # The same rows the agent's find_content tool and a "continue" shelf are built from.
    for language in ("en", "zh"):
        seen.append((f"list_published {language}",
                     json.dumps(content.list_published(language=language), ensure_ascii=False, default=str)))
        seen.append((f"get_published_article {language}",
                     json.dumps(content.get_published_article(ids[language]), ensure_ascii=False, default=str)))
    return seen


@pytest.mark.parametrize("public_name", ["", "Open Desk"])
def test_no_learner_route_carries_the_internal_source_name(images, public_name):  # noqa: F811
    ids = _world(images, public_name)
    for label, text in _learner_reads(images, ids):
        folded = text.casefold()
        for marker in MARKERS:
            assert marker.casefold() not in folded, f"{label} leaks {marker!r}"
    # What the learner is shown instead: the public name, else the site's host.
    detail = call(images["learner"], "GET", f"/api/reading/articles/{ids['en']}", admin=False).json()
    assert detail["provenance"]["publisher"] == (public_name or "news.example.org")
    detail_zh = call(images["learner"], "GET", f"/api/reading/articles/{ids['zh']}", admin=False).json()
    assert detail_zh["provenance"]["publisher"] == (public_name or "xinwen.example.cn")


def test_control_the_administrator_reads_do_carry_the_internal_name(images):  # noqa: F811
    ids = _world(images, "Open Desk")
    sources = call(images["admin"], "GET", f"{ADMIN_BASE}/sources").text
    article = call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{ids['en']}").text
    assert MARKER_EN in sources and MARKER_ZH in sources
    assert MARKER_EN in article




@pytest.mark.parametrize("language", ["en", "zh"])
def test_the_summary_route_reading_a_published_article_carries_no_internal_name(images, monkeypatch, language):  # noqa: F811
    """`reading_translation_api` loads `get_published_article` for a learner POST: what it reads and answers."""
    from writing_coach import reading_translation_api
    from writing_coach.reading_derived import DerivedCache
    from writing_coach.reading_summary import ReadingSummaryService

    seen = []

    def generate(**kwargs):
        seen.append(json.dumps(kwargs, ensure_ascii=False, default=str))
        return {"bullets": ["One.", "Two.", "Three."]}

    ids = _world(images, "Open Desk")
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: language)
    reading_translation_api.configure_reading_summary(ReadingSummaryService(DerivedCache(), generate))
    try:
        response = _summary_via_router(language, ids[language])
    finally:
        reading_translation_api.configure_reading_summary(None)
    assert response.status_code == 200, response.text
    blob = (response.text + "".join(seen)).casefold()
    assert seen, "the article was read and handed to the summariser"
    for marker in MARKERS:
        assert marker.casefold() not in blob, marker


def _summary_via_router(language, article_id):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import reading_translation_api

    app = FastAPI()
    app.include_router(reading_translation_api.router)
    return TestClient(app).post("/api/reading/summary", json={
        "source_language": language, "target_language": "vi", "article_id": article_id})


# -- the static proof ---------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
FIELD = re.compile(r"""source_name|ReadingSource\.name\b|source_head\.name|source\[["']name["']\]""")
# A caller of the registry reads: `src.name` / `row["name"]` after these cannot be matched by name alone.
REGISTRY_CALL = re.compile(r"\b(?:list_sources|get_source)\(")
DEFINITION = re.compile(r"\bdef\s+(?:list_sources|get_source)\(")

# Whole modules that belong to the administrator or to the ingest engine: they may read the internal name.
ADMIN_OR_ENGINE = {
    "writing_coach/reading_admin_api.py": "administrator routes",
    "writing_coach/reading_content_engine.py": "ingest engine: copies the name into job metadata",
    "writing_coach/reading_source_poller.py": "ingest engine: hands the name to the job",
    "writing_coach/reading_source_import.py": "ingest input type (`SubmittedInput.source_name`)",
    "writing_coach/persistence/models.py": "the column definition",
}
REPO = "writing_coach/persistence/reading_content_repository.py"
# Every other Python reader, keyed by (file, enclosing function) -> (occurrences, reason). The occurrence
# count is exact: a second read inside an allowlisted function fails until a person looks at it.
OTHER_READERS = {
    (REPO, "_learner_credit"): (1, "resolve_publisher ignores it unless the source is a built-in path "
                                   "(a name typed for one text); the internal registry name is not read"),
    (REPO, "list_sources"): (1, "ORDER BY only; the rows are the admin registry and the licences page, "
                                 "which publishes public_name else host"),
    (REPO, "set_source_public_name"): (1, "returns the admin registry row to the admin route"),
    (REPO, "set_source_state"): (1, "returns the admin registry row to the admin route"),
    (REPO, "set_polling"): (2, "admin registry row read and returned to the admin route"),
    (REPO, "find_duplicate_content"): (2, "admin review page: names the other source holding the same text "
                                          "(called from reading_admin_api only)"),
    (REPO, "get_article"): (2, "admin article detail (the learner read is get_published_article, which never "
                                "selects the name)"),
    (REPO, "list_queue"): (1, "admin review queue row (`_queue_row`); its only caller is reading_admin_api. "
                               "The learner list is list_published, which selects no source name"),
    (REPO, "_queue_row"): (1, "mapper for the admin queue row"),
    (REPO, "published_credits"): (1, "carries the RESOLVED publisher under this key, never the registry name"),
    ("writing_coach/licences.py", "creator"): (1, "reads published_credits' resolved publisher"),
    ("app.py", "orena_licences"): (1, "wires list_sources into licences_payload, which publishes "
                                      "public_name else host (reading_source_credits)"),
}
JS_READERS = {
    ("static/orena/capabilities/admin-reading.js", "if (source.trim()) submitted.source_name = source.trim();"):
        "admin submit form",
}
# Files that use the words for something else entirely (a language label for a prompt), not a source.
UNRELATED = {
    "writing_coach/media_interaction.py": "`source_name` is the language being studied in a tutor prompt",
    "writing_coach/reading_translation.py": "`source_name` is the language label in a translation prompt",
}


def _scan_files():
    for base in (ROOT / "writing_coach", ROOT / "static" / "orena"):
        for path in sorted(base.rglob("*")):
            if path.suffix in {".py", ".js", ".mjs"} and "__pycache__" not in path.parts:
                yield path
    yield ROOT / "app.py"


def _enclosing(tree, number):
    inside = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and node.lineno <= number <= node.end_lineno]
    return min(inside, key=lambda node: node.end_lineno - node.lineno).name if inside else "<module>"


def test_the_internal_source_name_has_no_reader_on_a_learner_path():
    found, js_unknown = {}, []
    for path in _scan_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ADMIN_OR_ENGINE or rel in UNRELATED or "/screens/admin" in rel or "/admin/" in rel:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if path.suffix == ".py":
            tree = ast.parse(text)
            for number, line in enumerate(lines, 1):
                if FIELD.search(line) or (REGISTRY_CALL.search(line) and not DEFINITION.search(line)):
                    found.setdefault((rel, _enclosing(tree, number)), []).append(f"{number}: {line.strip()}")
        else:
            for number, line in enumerate(lines, 1):
                if FIELD.search(line) and (rel, line.strip()) not in JS_READERS:
                    js_unknown.append(f"{rel}:{number}: {line.strip()}")
    problems = list(js_unknown)
    for key, hits in sorted(found.items()):
        allowed = OTHER_READERS.get(key)
        if allowed is None or len(hits) != allowed[0]:
            expected = "not allowlisted" if allowed is None else f"expected {allowed[0]}, found {len(hits)}"
            problems.append(f"{key[0]} :: {key[1]} ({expected}): " + " | ".join(hits))
    assert not problems, (
        "A reader of the internal source name (or of the registry rows that carry it) outside the admin/engine "
        "modules. If it can reach a learner payload, resolve the publisher with "
        "writing_coach.reading_provenance.resolve_publisher instead; if it is administrator-only, add its "
        "(file, function) to OTHER_READERS with the count and the reason:\n" + "\n".join(problems))


def test_the_allowlist_names_files_and_functions_that_exist():
    for rel in [*ADMIN_OR_ENGINE, *UNRELATED, *(path for path, _ in OTHER_READERS), *(path for path, _ in JS_READERS)]:
        assert (ROOT / rel).is_file(), rel
    for rel, function in OTHER_READERS:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert function in names, f"{rel} has no function {function}"
