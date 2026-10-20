"""Own sets and list payloads (D-248 §4, MV2-5): `product/content_access.py`'s rule for sets on the routes.

Proved here, hermetically:

  1. the rule: the first `access.set_free_items` items of a set are Free, the rest Plus, a learner's saved word is never
     locked, and the plan is read strictly (503, never an upgrade prompt over an outage);
  2. a vocabulary set's detail read: for Free with enforcement on, the first word keeps its body and the rest arrive
     locked with their headword only; Plus reads everything; enforcement off locks nothing; a searched or later page
     ranks against the set's head, not the page's;
  3. review stays usable on Free: the set's saved words keep their full rows in the review projection, a saved word in a
     paid position is not locked, and nothing a learner saved is removed;
  4. a grammar set: the catalogue carries each point's tier, the first point of a (function, level) opens, the next is
     403 `plan_required` with its title line only, and its quiz cannot be graded; Plus opens both;
  5. My Library's Reading entries carry the same `access` block as a Discover card; a video never does.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi import HTTPException

from policy_support import MemoryPolicyStore, installed
from writing_coach.product import catalog, content_access, quota
from writing_coach.product.content_access import Item

ENFORCED = {"access.enforced": True}


@pytest.fixture(autouse=True)
def _isolated():
    previous_quota = quota.runtime()
    saved_plan_for = previous_quota.plan_for
    previous_access = content_access._runtime
    content_access.configure()
    yield
    content_access.configure(store=previous_access.store, reading_pool=previous_access.reading_pool,
                             record_usage=previous_access.record_usage,
                             trial_available=previous_access.trial_available, clock=previous_access.clock)
    quota.runtime().plan_for = saved_plan_for


def _plan(plan):
    quota.runtime().plan_for = plan if callable(plan) else (lambda user_key, strict=True: plan)


# ============================================================================================== 1. the rule ==

def test_the_head_of_a_set_is_free_and_the_rest_plus():
    with installed():
        members = [Item("vocab_set", f"c:{key}", position=content_access.set_rank(key, ["w0"]))
                   for key in ("w0", "w1", "w2")]
        assert [block["tier"] for block in content_access.set_card_access(members)] == ["free", "plus", "plus"]
    with installed(MemoryPolicyStore({"access.set_free_items": 2})):
        assert content_access.set_rank("w1", ["w0", "w1"]) == 1
        assert content_access.set_rank("w9", ["w0", "w1"]) == 2
        assert content_access.access_tier(Item("vocab_set", "c:w1", position=1)) == "free"


def test_only_enforcement_and_a_lower_plan_lock_and_a_saved_item_never_does():
    members = [Item("grammar", f"en.{n}", position=n) for n in range(3)]
    _plan(catalog.FREE)
    with installed():
        assert not any(block["locked"] for block in content_access.set_card_access(members)), "off locks nothing"
    with installed(MemoryPolicyStore(ENFORCED)):
        assert [b["locked"] for b in content_access.set_card_access(members)] == [False, True, True]
        own = content_access.set_card_access(members, own=lambda index: index == 2)
        assert [b["locked"] for b in own] == [False, True, False], "a saved item stays the learner's"
        _plan(catalog.PLUS)
        assert not any(b["locked"] for b in content_access.set_card_access(members))


def test_a_set_with_a_paid_item_reads_the_plan_strictly():
    def down(user_key, strict=True):
        raise RuntimeError("subscription store down")

    _plan(down)
    with installed(MemoryPolicyStore(ENFORCED)), pytest.raises(HTTPException) as refused:
        content_access.set_card_access([Item("vocab_set", "c:a", position=0), Item("vocab_set", "c:b", position=1)])
    assert refused.value.status_code == 503
    with installed(MemoryPolicyStore(ENFORCED)):
        # a set whose every item is Free never needs the plan
        assert content_access.set_card_access([Item("vocab_set", "c:a", position=0)])[0]["locked"] is False


# ======================================================================================= 2-3. a vocabulary set ==

def _get(app_module, path):
    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(exercise())


@pytest.fixture()
def vocab_set(monkeypatch):
    import app as app_module

    entries = [{"word": word, "normalized_word": word, "language_code": "en", "definition": f"{word} meaning",
                "examples": [{"text": f"A {word} example."}]} for word in ("buffer", "hectic", "packed", "steady")]
    pack = {"id": "pack", "language_code": "en", "item_count": len(entries), "entries": entries}
    saved = {"packed": {"word": "packed", "review_stage": 2, "due": True, "next_review_at": "2026-10-21"}}
    calls = []

    def persisted(collection_id, *, search="", level="", limit=100, offset=0):
        calls.append({"search": search, "level": level, "limit": limit, "offset": offset})
        rows = [entry for entry in deepcopy(entries) if not search or search in entry["word"]]
        return {**deepcopy(pack), "entries": rows[offset:offset + limit]}

    monkeypatch.setattr(app_module, "_persisted_vocabulary_collection", persisted)
    monkeypatch.setattr(app_module, "saved_vocabulary_state",
                        lambda words: {word: deepcopy(saved[word]) for word in words if word in saved})
    monkeypatch.setattr(app_module, "save_library_vocabulary", lambda *a, **k: pytest.fail("opening must not save"))
    return type("VocabSet", (), {"app": app_module, "calls": calls})


def test_free_opens_the_first_word_and_gets_the_rest_without_their_body(vocab_set):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        response = _get(vocab_set.app, "/api/vocabulary/library/collections/pack")
    assert response.status_code == 200
    items = {item["headword"]: item for item in response.json()["items"]}
    assert items["buffer"]["access"] == {"tier": "free", "rotation": False, "locked": False}
    assert items["buffer"]["meanings"], "the first word keeps its body"
    hectic = items["hectic"]
    assert hectic["access"] == {"tier": "plus", "rotation": False, "locked": True}
    assert "meanings" not in hectic and "examples" not in hectic, "a locked word sends its headword only"
    assert "hectic meaning" not in response.text and "A hectic example." not in response.text


def test_plus_reads_every_word_and_off_locks_nothing(vocab_set):
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(ENFORCED)):
        items = _get(vocab_set.app, "/api/vocabulary/library/collections/pack").json()["items"]
    assert all(not item["access"]["locked"] and item["meanings"] for item in items)
    assert [item["access"]["tier"] for item in items] == ["free", "plus", "plus", "plus"], "Plus still sees the tier"
    _plan(catalog.FREE)
    with installed():
        items = _get(vocab_set.app, "/api/vocabulary/library/collections/pack").json()["items"]
    assert all(not item["access"]["locked"] and item["meanings"] for item in items), "enforcement off"


def test_a_searched_page_ranks_against_the_head_of_the_set(vocab_set):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        items = _get(vocab_set.app, "/api/vocabulary/library/collections/pack?search=steady").json()["items"]
    assert [(item["headword"], item["access"]["locked"]) for item in items] == [("steady", True)], \
        "the first row of a search is not the first item of the set"
    assert {"search": "", "level": "", "limit": 1, "offset": 0} in vocab_set.calls, "the head is read unfiltered"


def test_free_review_of_saved_words_stays_whole(vocab_set):
    """D-248 keeps review usable on Free: the set's saved words keep their full rows in the review projection, and a
    saved word in a paid position is not locked. Nothing a learner saved is removed."""
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        body = _get(vocab_set.app, "/api/vocabulary/library/collections/pack?include_review=true").json()
    assert body["review_items"] == [{"word": "packed", "review_stage": 2, "due": True,
                                     "next_review_at": "2026-10-21"}]
    packed = next(item for item in body["items"] if item["headword"] == "packed")
    assert packed["access"] == {"tier": "plus", "rotation": False, "locked": False}
    assert packed["meanings"] and packed["saved"] is True and packed["review_stage"] == 2
    assert body["progress"]["learned_count"] == 1 and body["progress"]["due_count"] == 1


# ============================================================================================== 4. a grammar set ==

@pytest.fixture()
def grammar(tmp_path):
    from tests.test_grammar_routes import World

    from writing_coach import grammar_admin_api, grammar_api

    saved = (grammar_admin_api._state, grammar_api._state)
    world = World(tmp_path)
    from tests.grammar_store_support import body

    world.import_and_publish([body("en.first", sequence=1), body("en.second", sequence=2),
                              body("en.other", function="fn.describe", sequence=1)])
    yield world
    world.engine.dispose()
    grammar_admin_api._state, grammar_api._state = saved


def test_the_catalogue_carries_each_points_tier_per_function_and_level(grammar):
    response = grammar.client.get("/api/grammar/v1/points")
    tiers = {point["id"]: point["access"] for point in response.json()["points"]}
    assert tiers == {"en.first": {"tier": "free", "rotation": False}, "en.second": {"tier": "plus", "rotation": False},
                     "en.other": {"tier": "free", "rotation": False}}, "each function's first point is Free"
    assert grammar.store.set_rank("en", "en.second") == 1 and grammar.store.set_rank("en", "nope") is None


def test_free_opens_the_first_point_and_is_refused_the_next(grammar):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        assert grammar.client.get("/api/grammar/v1/points/en.first").status_code == 200
        refused = grammar.client.get("/api/grammar/v1/points/en.second")
        graded = grammar.client.put("/api/grammar/v1/progress/en.second", headers={"origin": "http://testserver"},
                                    json={"answers": [0, 1, 0]})
        missing = grammar.client.get("/api/grammar/v1/points/en.nope")
    assert refused.status_code == 403
    context = refused.json()["detail"]["context"]
    assert (context["kind"], context["item_id"], context["required_tier"]) == ("grammar", "en.second", "plus")
    assert context["preview"]["header"]["native_title"] == "Point 2"
    assert "quick_practice" not in refused.text and "When one" not in refused.text, "no body in the refusal"
    assert graded.status_code == 403, "a locked point's quiz is not graded"
    assert missing.status_code == 404, "an unpublished id is a 404 before any 403"


def test_plus_opens_every_point(grammar):
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(ENFORCED)):
        assert grammar.client.get("/api/grammar/v1/points/en.second").status_code == 200


# ========================================================================================== 5. My Library rows ==

def test_my_librarys_reading_entries_carry_the_access_block_and_a_video_none():
    from writing_coach.collection_api import with_reading_access
    from writing_coach.collection_query import CollectionEntry, reading_entries

    content_access.configure(store=MemoryPolicyStore())
    content_access.save_overrides({"set": {"reading:a-plus": "plus"}}, actor="admin")
    rows = with_reading_access([
        {"article_id": "a-plus", "language": "en", "article_level": "B1", "title": "Rain", "created_at": "2026-10-20"},
        {"article_id": "a-free", "language": "en", "article_level": "B1", "title": "Sun", "created_at": "2026-10-19"},
    ])
    entries = [entry.as_dict() for entry in reading_entries(rows, "en")]
    assert entries[0]["access"] == {"tier": "plus", "rotation": False}
    assert entries[1]["access"]["tier"] == "free", "a one-article level has it Free (the floor)"
    video = CollectionEntry(domain="media", id="m1", title="Clip", learning_language="en", relationship="practised")
    assert "access" not in video.as_dict(), "a video never carries a tier (III.F.3.a)"
