"""Per-item rights refinement (D-193, proposed): staff-only public domain for VOA.

Fixtures are trimmed real voachinese.com pages (2026-10-14): a staff-bylined report, and two
VOA rewrites that end with the agency derivation note ("本文依据了美联社的报道").
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event

from writing_coach.persistence.models import Base
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_admin_api import publication_blockers
from writing_coach.reading_content_engine import ReadingContentEngine
from writing_coach.reading_provenance import build_provenance
from writing_coach.reading_rights_refinement import detect_wire_credit, refine_item_rights, rule_for
from writing_coach.reading_source_import import DirectUrlAdapter, SubmittedInput

FIXTURES = Path(__file__).parent / "fixtures" / "voa_zh"
VOA_NOTE = "Public domain: VOA staff-produced content is a work of the US government."


def _page(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def parts(tmp_path):
    db = create_engine(f"sqlite+pysqlite:///{tmp_path / 'engine.db'}")

    @event.listens_for(db, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    content = ReadingContentRepository(db)
    content.ensure_built_in_sources()
    return ReadingContentEngine(content=content, jobs=ReadingJobRepository(db)), content, ReadingJobRepository(db)


def _fetcher(body: str):
    return lambda url, *, max_bytes, timeout, content_types: (body.encode("utf-8"), "text/html")


def _ingest(parts, page: str, *, base_url: str, url: str, note: str = VOA_NOTE):
    engine, content, jobs = parts
    source = content.create_source(
        slug="s-" + base_url.split("//")[1].split(".")[-2], name="Source", source_type="manual", base_url=base_url,
        languages=["zh", "en"], created_by="admin",
        rights={"can_republish": True, "can_adapt": True, "attribution_required": True,
                "automation_allowed": True, "license_note": note})
    content.set_source_state(source["id"], "active", actor="admin")
    engine.adapters["url"] = lambda: DirectUrlAdapter(fetcher=_fetcher(page))
    engine.submit(SubmittedInput(kind="url", url=url, source_id=source["id"]), actor="admin@example.com")
    return content.get_article(engine.process(jobs.claim("worker-1"))["article_id"])


def _licence(article) -> str:
    source = article["source"]
    return build_provenance(publisher="VOA", url=article.get("canonical_url") or "x", author="",
                            rights=source["rights_effective"])["license"]["name"]


def test_voa_hosts_carry_the_staff_authorship_flag_and_others_do_not():
    assert rule_for("www.voachinese.com") == {"public_domain_requires_staff_authorship": True}
    assert rule_for("learningenglish.voanews.com")
    assert rule_for("example.com") == {}


def test_a_staff_article_keeps_the_public_domain_licence(parts):
    article = _ingest(parts, _page("staff_article.html"), base_url="https://www.voachinese.com",
                      url="https://www.voachinese.com/a/staff/8210904.html")
    state = article["source"]["rights_state"]
    assert state["can_republish"] == "allowed" and state["can_adapt"] == "allowed"
    assert _licence(article) == "Public domain"
    refinement = article["analysis"]["rights_refinement"]
    assert refinement["outcome"] == "kept" and refinement["reasons"] == []
    assert not [b for b in publication_blockers(article) if b["code"].startswith("rights_")]


@pytest.mark.parametrize("name,marker", [
    ("wire_derived_article.html", "法新社"),
    ("wire_derived_article_ap.html", "美联社"),
])
def test_a_wire_derived_article_loses_the_licence_and_needs_an_override(parts, name, marker):
    article = _ingest(parts, _page(name), base_url="https://www.voachinese.com",
                      url="https://www.voachinese.com/a/wire/1.html")
    state = article["source"]["rights_state"]
    assert state["can_republish"] == "unknown" and state["can_adapt"] == "unknown"
    assert _licence(article) == ""  # a learner is never shown "Public domain" for it
    refinement = article["analysis"]["rights_refinement"]
    assert refinement["outcome"] == "withheld" and refinement["reasons"] == ["wire_copy"]
    assert marker in refinement["evidence"][0]["text"]
    # D-190: an administrator may still publish, only by acknowledging the warning with a reason.
    assert {"code": "rights_unknown", "question": "can_republish"} in publication_blockers(article)
    # D-111: automation refuses it.
    assert "rights_not_cleared" in article["analysis"]["admission"]["reasons"]
    assert article["status"] == "needs_review"


def _without_byline(page: str) -> str:
    """The staff page with its structured byline (JSON-LD) removed, so authorship is unestablished."""
    stripped = re.sub(r'<script type="application/ld\+json">.*?</script>', "", page, flags=re.S)
    assert "李逸华" not in stripped.split("<main>")[0]
    return stripped


def test_a_voa_item_without_a_byline_is_withheld(parts):
    article = _ingest(parts, _without_byline(_page("staff_article.html")), base_url="https://www.voachinese.com",
                      url="https://www.voachinese.com/a/nobyline/1.html")
    refinement = article["analysis"]["rights_refinement"]
    assert refinement["outcome"] == "withheld" and refinement["reasons"] == ["no_staff_byline"]
    assert article["source"]["rights_state"]["can_republish"] == "unknown"


def test_an_english_voa_item_adapted_from_an_agency_is_withheld(parts):
    article = _ingest(parts, (FIXTURES.parent / "voa_en" / "wire_adapted_article.html").read_text(encoding="utf-8"),
                      base_url="https://learningenglish.voanews.com",
                      url="https://learningenglish.voanews.com/a/plasma/7983265.html")
    refinement = article["analysis"]["rights_refinement"]
    assert refinement["outcome"] == "withheld" and "wire_copy" in refinement["reasons"]
    assert "Agence France-Presse" in refinement["evidence"][0]["text"]
    assert article["source"]["rights_state"]["can_republish"] == "unknown"
    assert _licence(article) == ""


def test_only_inherited_answers_are_withheld_by_the_engine(parts):
    """An answer submitted for the article itself survives; the source's inherited ones do not."""
    engine, content, jobs = parts
    source = content.create_source(
        slug="s-voa", name="Source", source_type="manual", base_url="https://www.voachinese.com",
        languages=["zh"], created_by="admin",
        rights={"can_republish": True, "can_adapt": True, "attribution_required": True,
                "automation_allowed": True, "license_note": VOA_NOTE})
    content.set_source_state(source["id"], "active", actor="admin")
    engine.adapters["url"] = lambda: DirectUrlAdapter(fetcher=_fetcher(_page("wire_derived_article.html")))
    engine.submit(SubmittedInput(kind="url", url="https://www.voachinese.com/a/wire/2.html",
                                 source_id=source["id"], rights={"can_republish": True}), actor="admin@example.com")
    article = content.get_article(engine.process(jobs.claim("worker-1"))["article_id"])
    state = article["source"]["rights_state"]
    assert state["can_republish"] == "allowed"  # the administrator's own answer
    assert state["can_adapt"] == "unknown"  # inherited from the source, so withheld
    assert article["analysis"]["rights_refinement"]["outcome"] == "withheld"


def test_a_source_without_the_flag_is_unaffected_by_the_same_page(parts):
    article = _ingest(parts, _page("wire_derived_article.html"), base_url="https://example.org",
                      url="https://example.org/a/wire/1.html", note="Public domain")
    assert "rights_refinement" not in article["analysis"] or article["analysis"]["rights_refinement"] is None
    assert article["source"]["rights_state"]["can_republish"] == "allowed"
    assert _licence(article) == "Public domain"


def test_an_explicit_article_level_answer_is_not_overridden():
    refinement = refine_item_rights(
        source_base_url="https://www.voachinese.com", canonical_url="https://www.voachinese.com/a/1.html",
        author="美国之音", body="x\n\n(此文依据了法新社的报道。)", metadata={})
    assert refinement and refinement["outcome"] == "withheld"
    # The engine drops only keys whose origin is the source (see reading_content_engine), so an
    # administrator's own submitted answer survives; the refinement can only withhold inherited ones.
    assert refinement["withheld"] == ["can_republish", "can_adapt", "license_note"]


@pytest.mark.parametrize("line", [
    "(本文依据了美联社的报道。)", "（路透社）", "来源：路透社", "Reporting by Reuters", "(Reuters)",
])
def test_credit_lines_are_wire_evidence(line):
    assert detect_wire_credit(body=f"正文。\n\n{line}", author="美国之音")


@pytest.mark.parametrize("sentence", [
    "路透社援引消息人士的话说，美国已在提供情报支持，而一些地区和欧洲国家则主要提供防御性军事援助。",
    "他对美联社说：“我们还得等着看，不过在我看来，情况会好转。”",
    "由澳大利亚联邦警察(AFP)、维多利亚州警方组成的联合反恐小组证实，正在调查该男子。",
    "约翰霍普金斯大学彭博公共卫生学院教授保罗·斯皮格尔说。",
])
def test_ordinary_sourcing_inside_a_staff_story_is_not_wire_copy(sentence):
    assert detect_wire_credit(body=sentence, author="李逸华") == []


def test_an_agency_byline_is_wire_evidence():
    assert detect_wire_credit(body="x", author="路透社")
    assert detect_wire_credit(body="x", author="x", attribution_lines=["By Associated Press"])


def test_the_report_lists_a_published_wire_article_even_when_ingested_before_the_refinement(parts):
    """Existing rows carry no `rights_refinement`; the report judges the stored text now."""
    engine, content, jobs = parts
    wire = _ingest(parts, _page("wire_derived_article.html"), base_url="https://www.voachinese.com",
                   url="https://www.voachinese.com/a/wire/1.html")
    content.set_status(wire["id"], "published", actor="admin", reason="trial",
                       warnings=[{"code": "rights_unknown"}])
    found = content.published_staff_only_rights_candidates()
    assert [item["id"] for item in found] == [wire["id"]]
    assert found[0]["reasons"] == ["wire_copy"] and found[0]["asserted"] is False and found[0]["licence"] == ""


@pytest.mark.parametrize("line", [
    "Reuters contributed to this report.",
    "AP and Reuters contributed to this report",
    "The story was reported by AP.",
    "With reporting from Reuters",
    "Some information for this report came from AP, Reuters and AFP.",
    "Andrew Smith adapted this story for VOA Learning English based on reporting from Agence France-Presse.",
    "综合新华社、中央社报道",
    "(依据纽约时报的报道)",
    "来源：共同社",
    "(韩联社)",
    "Photo: Xinhua",
    "Some information for this report came from Kyodo.",
])
def test_english_and_further_agency_credits_are_wire_evidence(line):
    assert detect_wire_credit(body=f"Body text.\n\n{line}", author="VOA Learning English")


@pytest.mark.parametrize("sentence", [
    "Reuters reported that the talks had stalled on Tuesday.",
    "The Associated Press reported Tuesday that the camp, originally scheduled to close, would stay open.",
    "According to a Reuters report, analysts identified the aircraft as Chinese-made.",
    "She told AP that the plan was not final.",
    "An AP photo shows the minister arriving at the airport this morning, a spokesman said.",
    "新华社援引中国水利部的话报道称，水位已经下降。",
    "Officials said the Bloomberg School of Public Health would publish the study.",
])
def test_inline_agency_sourcing_in_english_prose_stays_staff(sentence):
    assert detect_wire_credit(body=sentence, author="Jane Doe") == []
