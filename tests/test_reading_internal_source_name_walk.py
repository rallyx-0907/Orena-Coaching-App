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


# -- the static proof ---------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
FIELD = re.compile(r"""source_name|ReadingSource\.name\b|source_head\.name|source\[["']name["']\]""")

# Whole modules that belong to the administrator or to the ingest engine: they may read the internal name.
ADMIN_OR_ENGINE = {
    "writing_coach/reading_admin_api.py": "administrator routes",
    "writing_coach/reading_content_engine.py": "ingest engine: copies the name into job metadata",
    "writing_coach/reading_source_poller.py": "ingest engine: hands the name to the job",
    "writing_coach/reading_source_import.py": "ingest input type (`SubmittedInput.source_name`)",
    "writing_coach/persistence/models.py": "the column definition",
}
# Every other reader, pinned by file and by the exact (stripped) line, with the reason it is not learner-facing.
OTHER_READERS = {
    ("writing_coach/persistence/reading_content_repository.py",
     'entered_name=metadata.get("source_name"),'):
        "resolve_publisher ignores it unless the source is a built-in path (a name typed for one text)",
    ("writing_coach/persistence/reading_content_repository.py",
     "select(ReadingSource).order_by(ReadingSource.state, ReadingSource.name)"): "admin list_sources ordering",
    ("writing_coach/persistence/reading_content_repository.py",
     'ReadingSource.name.label("source_name"),'): "admin readers: duplicate-content lookup and the admin article list",
    ("writing_coach/persistence/reading_content_repository.py",
     "ReadingSource.automation_allowed, ReadingSource.name,"): "admin get_article head",
    ("writing_coach/persistence/reading_content_repository.py",
     'article["source"]["source_name"] = source_head.name if source_head else ""'): "admin get_article payload",
    ("writing_coach/persistence/reading_content_repository.py",
     '"source_name": row.source_name,'): "admin duplicate-content lookup payload",
    ("writing_coach/persistence/reading_content_repository.py",
     '"source_name": getattr(row, "source_name", "") or "",'): "admin article row mapper (_article)",
    ("writing_coach/persistence/reading_content_repository.py",
     '"source_name": credit["publisher"],'): "published_credits: carries the resolved PUBLISHER under this key",
    ("writing_coach/licences.py",
     'publisher, author = _text(text.get("source_name")), _text(text.get("author"))'):
        "reads published_credits' resolved publisher, never the registry name",
    ("static/orena/capabilities/admin-reading.js", "if (source.trim()) submitted.source_name = source.trim();"):
        "admin submit form",
}
# Files that use the words for something else entirely (a language label for a prompt), not a source.
UNRELATED = {
    "writing_coach/media_interaction.py": "`source_name` is the language being studied in a tutor prompt",
    "writing_coach/reading_translation.py": "`source_name` is the language label in a translation prompt",
}


def _scan_files():
    roots = [ROOT / "writing_coach", ROOT / "static" / "orena"]
    for base in roots:
        for path in sorted(base.rglob("*")):
            if path.suffix in {".py", ".js", ".mjs"} and "__pycache__" not in path.parts:
                yield path
    yield ROOT / "app.py"


def test_the_internal_source_name_has_no_reader_on_a_learner_path():
    unknown = []
    for path in _scan_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ADMIN_OR_ENGINE or rel in UNRELATED or "/screens/admin" in rel or "/admin/" in rel:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if FIELD.search(line) and (rel, line.strip()) not in OTHER_READERS:
                unknown.append(f"{rel}:{number}: {line.strip()}")
    assert not unknown, (
        "A new reader of the internal source name outside the admin/engine modules. If it can reach a learner "
        "payload, resolve the publisher with writing_coach.reading_provenance.resolve_publisher instead; if it "
        "is administrator-only, add it to OTHER_READERS with the reason:\n" + "\n".join(unknown))


def test_the_allowlist_names_files_that_exist():
    for rel in [*ADMIN_OR_ENGINE, *UNRELATED, *(path for path, _ in OTHER_READERS)]:
        assert (ROOT / rel).is_file(), rel
