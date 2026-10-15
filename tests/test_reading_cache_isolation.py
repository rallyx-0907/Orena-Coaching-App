"""PR-MON-7D1 (H7-5, D-MON-025): who may reuse an on-demand Reading answer.

    server-verified public/published -> shared in-process cache and the shared persistent store
    learner/private                  -> the learner's account incarnation, in-process only, never persisted
    no incarnation                   -> no learner caching (never a global learner cache)

A client id, prefix or flag never establishes the shared scope; the server's own published record does.
"""

from __future__ import annotations

from typing import Any

import pytest

from writing_coach import reading_cache_scope, word_deep, word_detail
from writing_coach.book_asset_store import AssetNotFound
from writing_coach.core.request_context import USER_KEY_CTX
from writing_coach.reading_cache_scope import SHARED, UNSCOPED, CacheScope, learner_scope, scope_for
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_summary import ReadingSummaryService
from writing_coach.reading_translation import ReadingTranslationService, TextSegment

PUBLISHED = {"pub": {"title": "Night", "body": "The lamp ran out of oil. It was dark."}}


class Store:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.reads = 0

    def get_many(self, kind, target, keys):
        self.reads += 1
        return {key: self.rows[(kind, target, key)] for key in keys if (kind, target, key) in self.rows}

    def put_many(self, kind, target, source, rows, *, provider, model):
        for key, value in rows:
            self.rows.setdefault((kind, target, key), value)


class Engine:
    engine_id = "local"
    model_version = "test"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def translate_batch(self, source, target, segments):
        self.calls.append([segment.original_text for segment in segments])
        return {segment.segment_id: f"{target}|{segment.original_text}" for segment in segments}


@pytest.fixture
def accounts(monkeypatch):
    """Two learners, A and B; `incarnations[user]` is the active incarnation (None: none readable)."""

    incarnations: dict[str, str | None] = {"learner-a": "inc-a1", "learner-b": "inc-b1"}
    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda user_key: incarnations.get(user_key))
    monkeypatch.setattr(reading_cache_scope, "_published_article",
                        lambda article_id: PUBLISHED.get(article_id))  # the server's own published record
    return incarnations


def as_learner(user_key: str):
    class _As:
        def __enter__(self):
            self.token = USER_KEY_CTX.set(user_key)

        def __exit__(self, *exc):
            USER_KEY_CTX.reset(self.token)

    return _As()


def translate(service, text, *, content_id=None):
    return service.translate("en", "vi", [TextSegment("s", text)],
                             scope=scope_for(content_id, [text]))


# ---- 1-3: the authority boundary ------------------------------------------------------------------------------------

def test_a_fake_article_id_with_no_published_row_gets_no_shared_scope(accounts):
    with as_learner("learner-a"):
        assert scope_for("article:abc", ["The lamp ran out of oil."]) == CacheScope("inc:inc-a1")
        assert scope_for("article:", ["x"]) == CacheScope("inc:inc-a1")


def test_learner_or_private_content_ids_never_get_the_shared_scope(accounts):
    with as_learner("learner-a"):
        for claim in ("book:b1:c1", "import:mine", "published:true", "pub", "article:pub-but-not-this-one"):
            assert scope_for(claim, ["The lamp ran out of oil."]).shared is False
        # A real published id, but text the article does not contain (a learner pasting their own text under it).
        assert scope_for("article:pub", ["My private diary line."]).shared is False


def test_an_unreadable_published_store_is_not_published(accounts, monkeypatch):
    def broken(_article_id):
        raise RuntimeError("store down")

    monkeypatch.setattr(reading_cache_scope, "_published_article", broken)
    with as_learner("learner-a"):
        assert scope_for("article:pub", ["The lamp ran out of oil."]).shared is False


def test_a_server_verified_published_article_is_shared_and_persisted(accounts):
    store = Store()
    engine = Engine()
    service = ReadingTranslationService(engine, cache=DerivedCache(store))
    with as_learner("learner-a"):
        assert scope_for("article:pub", ["The lamp ran out of oil.", "It was dark."]) == SHARED
        translate(service, "The lamp ran out of oil.", content_id="article:pub")
    assert len(store.rows) == 1
    with as_learner("learner-b"):
        translate(service, "The lamp ran out of oil.", content_id="article:pub")
    assert len(engine.calls) == 1   # B reuses the shared, published answer


def test_a_fake_article_claim_never_reaches_the_shared_table(accounts):
    store = Store()
    service = ReadingTranslationService(Engine(), cache=DerivedCache(store))
    with as_learner("learner-a"):
        translate(service, "My private diary line.", content_id="article:abc")
        translate(service, "My private diary line.", content_id="article:pub")
    assert store.rows == {} and store.reads == 0


# ---- 4-6: learner isolation -----------------------------------------------------------------------------------------

def test_learner_a_private_result_is_never_served_to_learner_b(accounts):
    engine = Engine()
    service = ReadingTranslationService(engine, cache=DerivedCache(Store()))
    with as_learner("learner-a"):
        translate(service, "My private diary line.")
    with as_learner("learner-b"):
        translate(service, "My private diary line.")
        assert service.cached("en", "vi", [TextSegment("s", "My private diary line.")]) is not None  # B's own now
    assert len(engine.calls) == 2   # B was answered by the provider, not from A's entry


def test_the_same_incarnation_reuses_its_own_result(accounts):
    engine = Engine()
    service = ReadingTranslationService(engine, cache=DerivedCache(Store()))
    with as_learner("learner-a"):
        translate(service, "My private diary line.")
        translate(service, "My private diary line.")
        assert service.cached("en", "vi", [TextSegment("s", "My private diary line.")]) is not None
    assert len(engine.calls) == 1


def test_a_new_incarnation_of_the_same_account_inherits_nothing(accounts):
    engine = Engine()
    service = ReadingTranslationService(engine, cache=DerivedCache(Store()))
    with as_learner("learner-a"):
        translate(service, "My private diary line.")
        accounts["learner-a"] = "inc-a2"   # the account was deleted and registered again
        assert service.cached("en", "vi", [TextSegment("s", "My private diary line.")]) is None
        translate(service, "My private diary line.")
    assert len(engine.calls) == 2


def test_with_no_incarnation_nothing_is_cached_for_the_learner(accounts):
    accounts["learner-a"] = None
    engine = Engine()
    store = Store()
    service = ReadingTranslationService(engine, cache=DerivedCache(store))
    with as_learner("learner-a"):
        assert learner_scope() == UNSCOPED
        translate(service, "My private diary line.")
        translate(service, "My private diary line.")
    assert len(engine.calls) == 2 and store.rows == {}   # bypassed, never a global learner cache
    with as_learner("learner-b"):
        translate(service, "My private diary line.")
    assert len(engine.calls) == 3


def test_a_learner_scope_still_reads_the_shared_published_answers(accounts):
    engine = Engine()
    service = ReadingTranslationService(engine, cache=DerivedCache(Store()))
    with as_learner("learner-a"):
        translate(service, "It was dark.", content_id="article:pub")
    with as_learner("learner-b"):
        assert service.cached("en", "vi", [TextSegment("tap", "It was dark.")]) is not None   # a tap, no content id
    assert len(engine.calls) == 1


def test_an_unverified_summary_is_the_learners_own(accounts):
    calls = []

    def generate(**_kw):
        calls.append(1)
        return {"bullets": ["One."]}

    store = Store()
    service = ReadingSummaryService(DerivedCache(store), generate)
    with as_learner("learner-a"):
        service.summarize("My own long text.", "en", "vi")
        service.summarize("My own long text.", "en", "vi")
    with as_learner("learner-b"):
        service.summarize("My own long text.", "en", "vi")
    assert len(calls) == 2 and store.rows == {}


def test_word_detail_shares_only_verified_published_text(accounts, monkeypatch):
    store = Store()
    monkeypatch.setattr(word_detail, "_cache", DerivedCache(store))
    asked = []

    def compute():
        asked.append(1)
        return {"context_meaning": "ran out"}

    def ask(content_id, context="The lamp ran out of oil."):
        return word_detail._through_cache("gloss", "en", "vi", "ran out", context, content_id, compute)

    with as_learner("learner-a"):
        ask("article:fake")
        ask("article:pub", context="My lamp ran out of oil last night.")   # a sentence the article does not have
    assert store.rows == {}
    with as_learner("learner-b"):
        ask("article:fake")
    assert len(asked) == 3   # neither of A's private answers reached B
    with as_learner("learner-a"):
        ask("article:pub")
    assert len(store.rows) == 1


# ---- 7-8: word deep -------------------------------------------------------------------------------------------------

class AssetStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def get(self, key):
        if key not in self.files:
            raise AssetNotFound(key)
        return self.files[key]

    def put(self, key, value):
        self.files[key] = value


@pytest.fixture
def deep(accounts, monkeypatch):
    files = AssetStore()
    monkeypatch.setattr(word_deep, "_store", lambda: files)
    monkeypatch.setattr(word_deep, "_learner_layers", DerivedCache(entries=64))
    asked: list[str] = []

    def explain(payload):
        asked.append(payload.context)
        return {"summary": "s", "mental_model": f"about: {payload.context}"}

    monkeypatch.setattr(word_deep.media_interaction, "explain_media_text", explain)
    return files, asked


def layer(context, *, public):
    return word_deep._deep_layer(word="mythword", context=context, language="en", support="vi", identity="",
                                 reading="", public=public)


def test_a_learner_fragment_explanation_never_reaches_another_learner_or_the_store(deep):
    files, asked = deep
    with as_learner("learner-a"):
        assert layer("A's secret sentence with mythword.", public=False)["mentalModel"].endswith("A's secret sentence with mythword.")
        layer("A's secret sentence with mythword.", public=False)
    assert files.files == {} and len(asked) == 1   # A reuses their own; nothing on disk
    with as_learner("learner-b"):
        got = layer("B's own sentence with mythword.", public=False)
    assert "A's secret" not in got["mentalModel"] and len(asked) == 2


def test_different_fragments_of_one_learner_do_not_collide(deep):
    _files, asked = deep
    with as_learner("learner-a"):
        one = layer("First sentence with mythword.", public=False)
        other = layer("Second sentence with mythword.", public=False)
    assert one != other and len(asked) == 2


def test_a_poisoned_shared_file_is_never_read_for_a_learner_fragment(deep):
    files, asked = deep
    files.put(word_deep.cache_key("mythword", "", "vi"), b'{"mentalModel": "from someone else", "commonMistake": "", "contrast": []}')
    with as_learner("learner-b"):
        got = layer("B's sentence with mythword.", public=False)
    assert got["mentalModel"] != "from someone else" and len(asked) == 1


def test_a_catalogue_example_explanation_stays_shareable(deep):
    files, asked = deep
    with as_learner("learner-a"):
        layer("The catalogue's example with mythword.", public=True)
    assert len(files.files) == 1
    with as_learner("learner-b"):
        layer("The catalogue's example with mythword.", public=True)
    assert len(asked) == 1   # B reuses the shared, catalogue-derived explanation
