"""#198 proofs: an approved Reading picture is never shown, or served, without a credit.

The existing image tests cover the card payload. These hold the other ways the rule could be lost: the
`/image` route and the list after the credit disappears, the approve refusal, clear then re-approve, and the
source policy toggled off and on. The last test runs the read-only data audit (scripts/check_reading_image_credits.py).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


from tests.test_reading_engine_routes import call, setup  # noqa: F401 - the route fixture
from tests.test_reading_images import (  # noqa: F401 - fixtures and helpers of the image suite
    ADMIN_BASE,
    _approve,
    _article_with_candidates,
    _fresh_preview_cache,
    _learner,
    _policy,
    images,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_reading_image_credits.py"
NO_PUBLIC_NAME = ""


def _list_image(parts):
    listed = call(parts["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()["items"][0]
    return listed["image"]


def _route(parts, url):
    return call(parts["learner"], "GET", url, admin=False)


def _manual(parts):
    return parts["content"].built_in_source_id("manual")


def _shown(parts, article_id, url):
    """Card, list and route agree: all show the picture, or none does."""
    card, listed, served = _learner(parts, article_id).json()["image"], _list_image(parts), _route(parts, url).status_code
    assert (card is None) == (listed is None) == (served == 404), (card, listed, served)
    return card


def _checker():
    spec = importlib.util.spec_from_file_location("check_reading_image_credits", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_credit_that_was_the_publisher_disappearing_hides_card_list_and_route(images):  # noqa: F811
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    assert _approve(images, article_id, 0).status_code == 200  # no credit given: the publisher stands in
    url = _learner(images, article_id).json()["image"]["url"]
    assert _shown(images, article_id, url)["credit"] == "Orena Reading Desk"
    images["content"].set_source_public_name(_manual(images), NO_PUBLIC_NAME)
    assert _shown(images, article_id, url) is None
    assert _route(images, url).status_code == 404
    # The credit comes back with the name: nothing was deleted, only withheld.
    images["content"].set_source_public_name(_manual(images), "Orena Reading Desk")
    assert _shown(images, article_id, url)["credit"] == "Orena Reading Desk"


def test_an_explicit_credit_keeps_the_picture_when_the_publisher_goes(images):  # noqa: F811
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    assert _approve(images, article_id, 0, credit="Photo: A. Nguyen").status_code == 200
    url = _learner(images, article_id).json()["image"]["url"]
    images["content"].set_source_public_name(_manual(images), NO_PUBLIC_NAME)
    assert _shown(images, article_id, url)["credit"] == "Photo: A. Nguyen"


def test_approving_with_no_credit_and_no_publisher_is_refused_and_stores_nothing(images):  # noqa: F811
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    images["content"].set_source_public_name(_manual(images), NO_PUBLIC_NAME)
    for body in ({}, {"credit": ""}, {"credit": "   "}):
        refused = _approve(images, article_id, 0, **body)
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["category"] == "reading_image_credit_required"
    assert images["fetcher"].calls == [] and images["store"].files == {}
    assert _learner(images, article_id).json()["image"] is None
    assert _list_image(images) is None


def test_clearing_then_approving_again_restores_the_picture_with_its_credit(images):  # noqa: F811
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id, 0, credit="Photo: A")
    url = _learner(images, article_id).json()["image"]["url"]
    call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/image/clear", json={})
    assert _shown(images, article_id, url) is None
    # Re-approving without a credit while no publisher exists is still refused ...
    images["content"].set_source_public_name(_manual(images), NO_PUBLIC_NAME)
    assert _approve(images, article_id, 0).status_code == 422
    assert _shown(images, article_id, url) is None
    # ... and with a credit it is shown again, on the new revision's address.
    assert _approve(images, article_id, 0, credit="Photo: B").status_code == 200
    again = _learner(images, article_id).json()["image"]
    assert again["credit"] == "Photo: B"
    assert _route(images, again["url"]).status_code == 200


def test_the_source_policy_toggled_off_and_on_hides_and_restores_card_list_and_route(images):  # noqa: F811
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id, 0, credit="Photo: A")
    url = _learner(images, article_id).json()["image"]["url"]
    assert _shown(images, article_id, url)
    _policy(images, article_id, False)
    assert _shown(images, article_id, url) is None
    _policy(images, article_id, True)
    restored = _shown(images, article_id, url)
    assert restored and restored["credit"] == "Photo: A"
    assert _route(images, restored["url"]).status_code == 200


def test_the_data_audit_counts_zero_uncredited_pictures_and_sees_one_if_the_rule_were_lost(images):  # noqa: F811
    checker = _checker()
    engine = images["content"].engine
    assert checker.find_uncredited_images(engine) == {"approved": 0, "uncredited": []}
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id, 0)  # credited by the publisher only
    assert checker.find_uncredited_images(engine) == {"approved": 1, "uncredited": []}
    # The serving rule hides the picture when the publisher goes; the audit still reports the stored data,
    # so a build that stopped hiding it would be caught by the count, and the exit status says so.
    images["content"].set_source_public_name(_manual(images), NO_PUBLIC_NAME)
    found = checker.find_uncredited_images(engine)
    assert found["approved"] == 1 and [row["id"] for row in found["uncredited"]] == [article_id]
    assert _learner(images, article_id).json()["image"] is None


def test_the_audit_script_is_read_only_and_refuses_without_a_database(monkeypatch, capsys):
    checker = _checker()
    monkeypatch.delenv("POSTGRES_RUNTIME_URL", raising=False)
    assert checker.main([]) == 2
    assert "no database" in capsys.readouterr().out
    source = SCRIPT.read_text(encoding="utf-8")
    for write in ("insert(ReadingArticle", "update(", "delete(", "commit(", ".begin("):
        assert write not in source
