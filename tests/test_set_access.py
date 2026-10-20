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

    def save(payload):
        saved[payload.word] = {"word": payload.word, "review_stage": 0, "due": True, "next_review_at": ""}
        return {"saved": True, "item": deepcopy(saved[payload.word])}

    state = type("VocabSet", (), {"app": app_module, "calls": calls, "saved": saved, "window": None})
    monkeypatch.setattr(app_module, "_persisted_vocabulary_collection", persisted)
    monkeypatch.setattr(app_module, "saved_vocabulary_state",
                        lambda words: {word: deepcopy(saved[word]) for word in words if word in saved})
    monkeypatch.setattr(app_module, "saved_vocabulary_words",
                        lambda words=(): {word for word in (words or saved) if word in saved})
    monkeypatch.setattr(app_module, "save_library_vocabulary", save)
    monkeypatch.setattr(app_module, "review_window", lambda user_key=None: state.window)
    return state


def _post(app_module, path, body):
    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, json=body, headers={"origin": "http://testserver"})

    return asyncio.run(exercise())


def _keep(app_module, word, collection_id="pack"):
    body = {"word": word, "source_kind": "collection"}
    if collection_id:
        body["source_collection_id"] = collection_id
    return _post(app_module, "/api/library/vocabulary", body)


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


def test_free_review_of_saved_words_stays_inside_the_window(vocab_set):
    """Review stays usable on Free: the set's saved words inside the review window keep their full rows in the review
    projection; the card of a paid position stays locked (keeping a word never unlocks it). Nothing saved is removed."""
    from writing_coach.becoming_library import ReviewWindow

    vocab_set.window = ReviewWindow(30, ["packed"], 1)
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        body = _get(vocab_set.app, "/api/vocabulary/library/collections/pack?include_review=true").json()
    assert body["review_items"] == [{"word": "packed", "review_stage": 2, "due": True,
                                     "next_review_at": "2026-10-21"}]
    assert body["review_limit"] == {"limit": 30, "saved": 1, "held": 0}
    packed = next(item for item in body["items"] if item["headword"] == "packed")
    assert packed["access"] == {"tier": "plus", "rotation": False, "locked": True}
    assert "meanings" not in packed and packed["saved"] is True and packed["review_stage"] == 2
    assert body["progress"]["learned_count"] == 1 and body["progress"]["due_count"] == 1
    vocab_set.window = ReviewWindow(30, ["buffer"], 31)
    with installed(MemoryPolicyStore(ENFORCED)):
        body = _get(vocab_set.app, "/api/vocabulary/library/collections/pack?include_review=true").json()
    assert body["review_items"] == [], "a word past the window waits for Plus"
    assert vocab_set.saved["packed"], "and is still kept"


# ================================================================== 2b. keeping a set's word (review of #485, P1) ==

def test_keeping_a_locked_word_of_a_set_is_refused_and_the_first_is_kept(vocab_set):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        locked = _keep(vocab_set.app, "hectic")
        first = _keep(vocab_set.app, "buffer")
        unnamed = _keep(vocab_set.app, "steady", collection_id="")
        stranger = _keep(vocab_set.app, "zebra")
    assert locked.status_code == 403 and locked.json()["detail"]["category"] == "plan_required"
    assert locked.json()["detail"]["context"]["kind"] == "vocab_set"
    assert first.status_code == 200 and "buffer" in vocab_set.saved
    assert unnamed.status_code == 422, "a new set save that leaves its set out is refused, not waved through"
    assert stranger.status_code == 422, "a word that is not in the named set"
    assert "hectic" not in vocab_set.saved and "steady" not in vocab_set.saved


def test_add_all_through_the_api_keeps_only_what_the_plan_reaches(vocab_set):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        answers = {word: _keep(vocab_set.app, word).status_code for word in ("buffer", "hectic", "packed", "steady")}
    assert answers == {"buffer": 200, "hectic": 403, "packed": 403, "steady": 403}
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(ENFORCED)):
        assert _keep(vocab_set.app, "hectic").status_code == 200, "Plus keeps any word of the set"
    _plan(catalog.FREE)
    with installed():
        assert _keep(vocab_set.app, "steady").status_code == 200, "enforcement off refuses nothing"


def test_a_word_kept_another_way_never_unlocks_its_card(vocab_set):
    """A reading tap or a manual save is not a set item and stays free; the set's card stays locked all the same."""
    vocab_set.saved["hectic"] = {"word": "hectic", "review_stage": 0, "due": True, "next_review_at": ""}
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        manual = _post(vocab_set.app, "/api/library/vocabulary", {"word": "steady", "source_kind": "reading"})
        items = {item["headword"]: item for item in
                 _get(vocab_set.app, "/api/vocabulary/library/collections/pack").json()["items"]}
    assert manual.status_code == 200, "a word tapped in the learner's own reading stays free"
    for word in ("hectic", "steady"):
        assert items[word]["access"]["locked"] is True and "meanings" not in items[word], word
        assert items[word]["saved"] is True


def test_the_daily_feed_offers_a_free_learner_only_open_words(vocab_set, monkeypatch):
    app_module = vocab_set.app
    pool = [{"word": word, "normalized_word": word, "language_code": "en", "definition": f"{word} meaning"}
            for word in ("buffer", "hectic", "packed", "steady")]
    monkeypatch.setattr(app_module, "_vocabulary_feed_pool", lambda code: deepcopy(pool))
    monkeypatch.setattr(app_module, "list_vocabulary_collections", lambda code: [])
    monkeypatch.setattr(app_module, "_persisted_vocabulary_collections",
                        lambda code: [{"id": "pack", "origin": "imported"}])
    vocab_set.saved.clear()
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        free_feed = _get(app_module, "/api/vocabulary/feed?language_code=en").json()["items"]
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(ENFORCED)):
        plus_feed = _get(app_module, "/api/vocabulary/feed?language_code=en").json()["items"]
    assert [item["headword"] for item in free_feed] == ["buffer"]
    assert "hectic meaning" not in str(free_feed)
    assert {item["headword"] for item in plus_feed} == {"buffer", "hectic", "packed", "steady"}


# ======================================================================= 3b. the Free review window (D-248 item 10) ==

class _Library:
    """A learner's saved words for `becoming_library`, in memory."""

    def __init__(self, words):
        self.rows = {word: {"word": word, "phonetic": "", "part_of_speech": "", "definition": "", "translation_vi": "",
                            "added_at": f"2026-10-{index + 1:02d}T00:00:00+00:00", "source_essay_id": None,
                            "source_fragment": "", "source_kind": "manual", "focus_note": "", "review_stage": 0,
                            "successful_recalls": 0, "lapse_count": 0, "last_reviewed_at": "", "next_review_at": ""}
                     for index, word in enumerate(words)}
        self.graded = []

    def library_counts(self, now=""):
        return {"saved": len(self.rows), "due": len(self.rows), "mastered": 0}

    def list_review_window(self, limit):
        return sorted(self.rows, key=lambda word: self.rows[word]["added_at"])[:limit]

    def list_saved_rows(self, words):
        return [dict(self.rows[word]) for word in words if word in self.rows]

    def get_library_progress(self, word):
        return dict(self.rows[word]) if word in self.rows else None

    def update_library_review(self, word, values):
        self.graded.append(word)
        self.rows[word].update(values)
        return dict(self.rows[word])


@pytest.fixture()
def library(monkeypatch):
    from writing_coach import becoming_library

    store = _Library(["alpha", "bravo", "charlie", "delta"])
    monkeypatch.setattr(becoming_library, "_repository", store)
    monkeypatch.setattr(becoming_library, "_catalog_resolver", lambda language: (lambda normalized: None))
    monkeypatch.setattr(becoming_library, "_catalog_entry_for", lambda word, resolve=None: None)
    return store


CAPPED = {**ENFORCED, "access.free_review_words": 2}


def test_the_window_is_the_earliest_saved_words_and_only_for_free(library):
    from writing_coach import becoming_library

    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(CAPPED)):
        window = becoming_library.review_window()
    assert window.words == ("alpha", "bravo") and window.as_dict() == {"limit": 2, "saved": 4, "held": 2}
    with installed(MemoryPolicyStore({"access.free_review_words": 2})):
        assert becoming_library.review_window() is None, "enforcement off: no cap"
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(CAPPED)):
        assert becoming_library.review_window() is None, "Plus reviews everything"
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        assert becoming_library.review_window().limit == 30, "the default is the founder's 30"


def test_the_due_list_and_the_summary_hold_the_window_and_keep_every_word(library):
    from writing_coach import becoming_library

    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(CAPPED)):
        page = becoming_library.library_page(status="due", order="due", limit=50)
    assert [item["word"] for item in page["items"]] == ["alpha", "bravo"]
    assert page["summary"]["due"] == 2 and page["summary"]["saved"] == 4, "every saved word is still counted as kept"
    assert page["summary"]["review_limit"] == {"limit": 2, "saved": 4, "held": 2}
    assert set(library.rows) == {"alpha", "bravo", "charlie", "delta"}, "nothing is deleted"


def test_grading_a_word_past_the_window_is_refused_and_inside_it_works(library):
    from writing_coach import becoming_library
    from writing_coach.becoming_library import VocabularyReviewIn

    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(CAPPED)):
        assert becoming_library.review_library_vocabulary("alpha", VocabularyReviewIn(result="got_it"))["found"]
        with pytest.raises(HTTPException) as refused:
            becoming_library.review_library_vocabulary("delta", VocabularyReviewIn(result="got_it"))
    assert refused.value.status_code == 403 and refused.value.detail["category"] == "plan_required"
    assert refused.value.detail["context"]["preview"]["review_limit"]["held"] == 2
    assert library.graded == ["alpha"]
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(CAPPED)):
        assert becoming_library.review_library_vocabulary("delta", VocabularyReviewIn(result="got_it"))["found"]


def test_the_review_queue_holds_the_window(library, monkeypatch):
    from writing_coach import library_api

    class Queue:
        def review_queue(self, limit):
            return {"pinned": [{"id": "p1", "word": "delta"}, {"id": "p2", "word": "alpha"}], "pinned_count": 2,
                    "due_count": 4, "first_due_word": "alpha", "total": 6}

    monkeypatch.setattr(library_api, "_library", lambda: Queue())
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(CAPPED)):
        queue = library_api.library_review_queue()
    assert [entry["word"] for entry in queue["pinned"]] == ["alpha"]
    assert queue["due_count"] == 2 and queue["total"] == 3 and queue["review_limit"]["held"] == 2
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(CAPPED)):
        assert library_api.library_review_queue()["due_count"] == 4


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


def test_by_error_gives_a_locked_point_without_its_reason(grammar):
    _plan(catalog.FREE)
    with installed(MemoryPolicyStore(ENFORCED)):
        points = {point["grammar_id"]: point for point in
                  grammar.client.get("/api/grammar/v1/by-error", params={"error_tag": "tense_choice"}).json()["points"]}
    assert points["en.second"]["reason"] is None and points["en.second"]["access"]["locked"] is True
    assert points["en.second"]["title"], "the title stays"
    assert points["en.first"]["reason"] and points["en.first"]["access"]["locked"] is False
    _plan(catalog.PLUS)
    with installed(MemoryPolicyStore(ENFORCED)):
        points = grammar.client.get("/api/grammar/v1/by-error", params={"error_tag": "tense_choice"}).json()["points"]
    assert all(point["reason"] for point in points)


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
