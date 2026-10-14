"""D-18X (proposed): learners see a publisher name, never the administrator's internal source name.

Holds the pure resolution order, the stored public name and its cache-revision effect, and that
no learner payload (list, detail, licences page) leaks the internal name or the built-in labels.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import update

from tests.test_reading_content_engine import ARTICLE
from tests.test_reading_engine_routes import call, setup  # noqa: F401 - the route fixture
from writing_coach.licences import licences_payload, reading_source_credits
from writing_coach.persistence.models import ReadingSourceItem
from writing_coach.reading_provenance import host_name, public_name_of, resolve_publisher
from writing_coach.reading_source_import import SubmittedInput

INTERNAL = "QA NASA news releases (RSS) - trial"
RIGHTS = {"automation_allowed": False, "can_republish": True, "can_adapt": False,
          "attribution_required": True, "license_note": "CC BY 4.0"}
REPUBLICATION = {"provenance": [{"kind": "republication", "original_publisher": "Radio Free Asia"}]}


# -- the pure resolution ---------------------------------------------------------------------


def test_the_public_name_comes_first_then_the_typed_name_then_the_page_then_the_host():
    facts = {"page_facts": {"site_name": "VOA Chinese"}}
    url = "https://www.voachinese.com/a/1.html"
    assert resolve_publisher(public_name="VOA", extraction=facts, url=url) == ("VOA", "")
    assert resolve_publisher(entered_name="Typed", built_in=True, extraction=facts, url=url) == ("Typed", "")
    assert resolve_publisher(extraction=facts, url=url) == ("VOA Chinese", "")
    assert resolve_publisher(url=url) == ("voachinese.com", "")
    assert resolve_publisher() == ("", "")


def test_the_name_typed_for_one_text_counts_only_on_a_built_in_path():
    # On a registered source the stored `source_name` is the internal name copied in by the engine.
    assert resolve_publisher(entered_name=INTERNAL, built_in=False, url="https://nasa.gov/x") == ("nasa.gov", "")


@pytest.mark.parametrize("label", ["Direct URL", "direct url", "Manual paste", "File upload"])
def test_a_built_in_label_is_never_a_publisher(label):
    assert resolve_publisher(public_name=label, entered_name=label, built_in=True) == ("", "")
    assert public_name_of({"public_name": label}) == ""


def test_a_republication_credits_the_original_publisher_via_the_site():
    assert resolve_publisher(public_name="Global Voices", extraction=REPUBLICATION) == (
        "Radio Free Asia", "Global Voices")
    # The original is the site itself: one credit, no "via".
    assert resolve_publisher(public_name="radio free asia", extraction=REPUBLICATION) == ("Radio Free Asia", "")
    # Only a republication entry counts; an editorial note names nobody.
    note = {"provenance": [{"kind": "editorial_note", "original_publisher": "X"}]}
    assert resolve_publisher(public_name="Global Voices", extraction=note) == ("Global Voices", "")


@pytest.mark.parametrize("name", [
    "Global Voices (English)", "Global Voices [English]", "Acme Inc.", "美国之音（VOA）", "【美国之音】", "St. Louis Post-Dispatch",
])
def test_balanced_brackets_and_abbreviation_stops_survive(name):
    assert public_name_of({"public_name": f"  {name} - "}) == name
    assert resolve_publisher(public_name=f" {name}; ") == (name, "")


def test_a_name_that_is_an_address_or_empty_is_ignored():
    assert resolve_publisher(public_name="https://x.example/a", url="https://x.example/a") == ("x.example", "")
    assert host_name("not a url") == ""
    assert host_name("https://m.example.org/a") == "example.org"


# -- stored on the source, resolved in every payload ---------------------------------------------


def _source(content, *, public_name="", slug="qa-nasa"):
    source = content.create_source(
        slug=slug, name=INTERNAL, public_name=public_name, source_type="manual",
        base_url="https://www.nasa.gov", languages=["en"], rights=RIGHTS, created_by="admin")
    content.set_source_state(source["id"], "active", actor="admin")
    return source


def _publish(parts, source, *, url="https://www.nasa.gov/news/rain"):
    parts["engine"].submit(SubmittedInput(
        kind="text", text=ARTICLE, title="Rain returns", author="", language="en", url=url,
        source_id=source["id"]), actor="admin")
    article_id = parts["engine"].process(parts["jobs"].claim("worker"))["article_id"]
    parts["content"].set_status(article_id, "published", actor="admin")
    return article_id


def _no_internal_names(*payloads):
    blob = json.dumps(payloads, ensure_ascii=False).casefold()
    for secret in (INTERNAL.casefold(), "qa nasa", "direct url", "manual paste", "file upload"):
        assert secret not in blob


def test_the_learner_sees_the_public_name_and_never_the_internal_one(setup):  # noqa: F811
    content = setup["content"]
    article_id = _publish(setup, _source(content, public_name="NASA"))
    listed = call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert listed["items"][0]["provenance"]["publisher"] == "NASA"
    assert detail["provenance"]["publisher"] == "NASA"
    assert detail["provenance"]["text"].startswith("Originally published by NASA")
    credits = licences_payload(reading_texts=content.published_credits, reading_sources=content.list_sources)
    assert sorted(row["title"] for row in credits["content"]) == ["NASA", "Rain returns"]
    _no_internal_names(listed, detail, credits)


def test_without_a_public_name_the_host_stands_in_not_the_internal_name(setup):  # noqa: F811
    content = setup["content"]
    article_id = _publish(setup, _source(content))
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert detail["provenance"]["publisher"] == "nasa.gov"
    _no_internal_names(detail)


def test_the_page_site_name_and_the_original_publisher_come_from_the_extraction(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content)
    article_id = _publish(setup, source)
    with content.engine.begin() as connection:
        connection.execute(update(ReadingSourceItem).values(metadata_json={
            "extraction": {"page_facts": {"site_name": "NASA Science"}}}))
    assert content.get_published_article(article_id)["provenance"]["publisher"] == "NASA Science"
    with content.engine.begin() as connection:
        connection.execute(update(ReadingSourceItem).values(metadata_json={"extraction": {
            **REPUBLICATION, "page_facts": {"site_name": "NASA Science"}}}))
    credit = content.get_published_article(article_id)["provenance"]
    assert (credit["publisher"], credit["via"]) == ("Radio Free Asia", "NASA Science")
    assert credit["text"].startswith("Originally published by Radio Free Asia via NASA Science")


def test_a_direct_url_import_is_credited_to_its_host_not_to_direct_url(setup):  # noqa: F811
    content = setup["content"]
    direct = {"id": content.built_in_source_id("direct_url")}
    article_id = _publish(setup, direct, url="https://www.voachinese.com/a/rain.html")
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert detail["provenance"]["publisher"] == "voachinese.com"
    _no_internal_names(detail)


def test_changing_the_public_name_moves_the_cache_revision_of_its_published_texts_only(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, public_name="NASA")
    other = _source(content, public_name="Elsewhere", slug="other")
    mine, theirs = _publish(setup, source), _publish(setup, other, url="https://example.org/other")
    before = {i: content.get_published_article(i)["content_revision"] for i in (mine, theirs)}
    unchanged = content.set_source_public_name(source["id"], "NASA")
    assert content.get_published_article(mine)["content_revision"] == before[mine]
    assert unchanged["public_name"] == "NASA"
    content.set_source_public_name(source["id"], "NASA Newsroom")
    assert content.get_published_article(mine)["provenance"]["publisher"] == "NASA Newsroom"
    assert content.get_published_article(mine)["content_revision"] == before[mine] + 1
    assert content.get_published_article(theirs)["content_revision"] == before[theirs]
    assert content.set_source_public_name("00000000-0000-4000-8000-0000000000ff", "x") is None


def test_the_admin_route_sets_the_public_name_and_the_admin_list_keeps_the_internal_name(setup):  # noqa: F811
    source = _source(setup["content"])
    response = call(setup["admin"], "POST", f"/api/admin/reading/sources/{source['id']}/public-name",
                    json={"public_name": "  NASA  "})
    assert response.status_code == 200
    assert response.json()["public_name"] == "NASA"
    listed = call(setup["admin"], "GET", "/api/admin/reading/sources").json()["items"]
    assert [(row["name"], row["public_name"]) for row in listed if row["slug"] == "qa-nasa"] == [(INTERNAL, "NASA")]
    assert call(setup["admin"], "POST", "/api/admin/reading/sources/00000000-0000-4000-8000-0000000000ff/public-name",
                json={"public_name": "x"}).status_code == 404
    assert call(setup["learner"], "POST", f"/api/admin/reading/sources/{source['id']}/public-name",
                admin=False, json={"public_name": "x"}).status_code in (403, 404)


def test_the_source_credit_row_uses_the_public_name_or_the_host():
    rows = reading_source_credits([
        {"name": INTERNAL, "public_name": "NASA", "state": "active", "can_republish": True,
         "license_note": "CC BY 4.0", "base_url": "https://www.nasa.gov"},
        {"name": INTERNAL, "public_name": "", "state": "active", "can_republish": True,
         "license_note": "CC BY 4.0", "base_url": "https://www.esa.int"},
        {"name": INTERNAL, "public_name": "", "state": "active", "can_republish": True,
         "license_note": "CC BY 4.0", "base_url": ""},
    ])
    assert [row["title"] for row in rows] == ["NASA", "esa.int"]



def test_the_source_credit_row_reads_the_rights_the_registry_nests():
    nested = {"name": INTERNAL, "public_name": "NASA", "state": "active", "base_url": "https://www.nasa.gov",
              "rights": {"can_republish": True, "license_note": "CC BY 4.0"}}
    assert [row["title"] for row in reading_source_credits([nested])] == ["NASA"]
    denied = {**nested, "rights": {"can_republish": False, "license_note": "CC BY 4.0"}}
    assert reading_source_credits([denied]) == []
