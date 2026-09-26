"""Sources, snapshots, articles, targets and the review trail.

The rules these hold are the ones a learner would feel if they broke: a
published article is the only thing a learner can see, an admin's level
correction never destroys the machine's estimate, a rejected text cannot come
back as a new candidate, and a list of articles never carries article bodies.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, event, select  # noqa: E402

from writing_coach.persistence.models import Base, ReadingArticle  # noqa: E402
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    MAX_ARTICLE_PAGE,
    BUILT_IN_SOURCES,
    ReadingContentRepository,
    TargetInput,
)

BODY = (
    "The river rose overnight and the fields were flooded by morning. "
    "Farmers moved their animals to higher ground before the water reached the road. "
)


@pytest.fixture()
def repository(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'content.db'}")

    # SQLite ignores foreign keys unless asked; the runtime never does. Without
    # this the hermetic suite would happily accept an article whose snapshot
    # does not exist and call the schema proved.
    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    repository = ReadingContentRepository(engine)
    repository.ensure_built_in_sources()
    return repository


def _snapshot(repository, *, body=BODY, native_id="", url="", title="Rain returns"):
    return repository.record_source_item(
        source_id=repository.built_in_source_id("manual"),
        source_native_id=native_id,
        canonical_url=url,
        title=title,
        author="M. Tran",
        published_at=None,
        language="en",
        body=body,
        content_hash=f"{abs(hash(body)):064x}"[:64],
        metadata={"input_kind": "text"},
        rights={"can_republish": True},
    )


def _article(repository, *, body=BODY, targets=None, **kwargs):
    snapshot = _snapshot(repository, body=body, **kwargs)
    return repository.create_article(
        source_item_id=snapshot["id"],
        title="Rain returns to the valley",
        body=body,
        excerpt=body[:120],
        language="en",
        topic="environment",
        estimated_level="B1",
        estimated_confidence=0.62,
        word_count=28,
        reading_time_seconds=90,
        analysis={"sentence_count": 2},
        targets=targets
        or [
            TargetInput(text="higher ground", canonical_form="higher ground",
                        target_type="phrase", context="Farmers moved their animals to higher ground.",
                        estimated_level="", rank=0),
            TargetInput(text="flooded", canonical_form="flooded", target_type="word",
                        context="the fields were flooded by morning", estimated_level="", rank=1),
        ],
    )


# ---- sources ----------------------------------------------------------------

def test_the_three_built_in_sources_exist_and_are_stable(repository):
    ids = {kind: repository.built_in_source_id(kind) for kind in ("manual", "direct_url", "file")}
    assert set(ids) == set(BUILT_IN_SOURCES)
    assert len({*ids.values()}) == 3
    repository.ensure_built_in_sources()  # idempotent: the migration seeds these too
    assert repository.built_in_source_id("manual") == ids["manual"]


def test_a_new_external_source_starts_unapproved_and_cannot_poll(repository):
    source = repository.create_source(
        slug="valley-news", name="Valley News", source_type="rss",
        base_url="https://example.com/feed", languages=["en"],
        rights={"automation_allowed": False}, created_by="admin@example.com",
    )
    assert source["state"] == "needs_review"
    assert source["polling_enabled"] is False
    refused = repository.set_polling(source["id"], enabled=True, actor="admin@example.com")
    assert refused is None


def test_polling_turns_on_only_for_an_approved_source_that_allows_automation(repository):
    source = repository.create_source(
        slug="valley-news", name="Valley News", source_type="rss",
        base_url="https://example.com/feed", languages=["en"],
        rights={"automation_allowed": True}, created_by="admin@example.com",
    )
    repository.set_source_state(source["id"], "active", actor="admin@example.com")
    enabled = repository.set_polling(source["id"], enabled=True, actor="admin@example.com")
    assert enabled["polling_enabled"] is True


# ---- snapshots --------------------------------------------------------------

def test_the_same_bytes_from_one_source_are_one_snapshot(repository):
    first = _snapshot(repository)
    second = _snapshot(repository)
    assert second["duplicate"] is True and second["id"] == first["id"]


def test_a_changed_source_supersedes_rather_than_overwrites(repository):
    first = _snapshot(repository, native_id="valley-1", body=BODY)
    second = _snapshot(repository, native_id="valley-1", body=BODY + "A correction followed. ")
    assert second["duplicate"] is False and second["id"] != first["id"]
    assert second["supersedes_id"] == first["id"]
    assert second["revision"] == 2
    old = repository.get_source_item(first["id"])
    assert old["superseded_at"] is not None
    assert old["body"] == BODY  # the original text is still exactly what arrived


def test_the_same_text_under_another_source_is_visible_as_a_duplicate(repository):
    first = _snapshot(repository)
    elsewhere = repository.find_duplicate_content(
        first["content_hash"], exclude_source_id=repository.built_in_source_id("manual")
    )
    assert elsewhere == []
    also = repository.record_source_item(
        source_id=repository.built_in_source_id("file"),
        source_native_id="", canonical_url="", title="Rain returns", author="",
        published_at=None, language="en", body=BODY, content_hash=first["content_hash"],
        metadata={}, rights={},
    )
    assert also["duplicate"] is False
    seen = repository.find_duplicate_content(
        first["content_hash"], exclude_source_id=repository.built_in_source_id("file")
    )
    assert [item["id"] for item in seen] == [first["id"]]


# ---- articles and levels ----------------------------------------------------

def test_a_new_candidate_waits_for_review_and_is_not_learner_visible(repository):
    article = _article(repository)
    assert article["status"] == "needs_review"
    assert repository.list_published(language="en")["items"] == []


def test_an_admin_level_never_destroys_the_machine_estimate(repository):
    article = _article(repository)
    updated = repository.update_article(
        article["id"], actor="admin@example.com", reviewed_level="B2"
    )
    assert updated["estimated_level"] == "B1"
    assert updated["reviewed_level"] == "B2"
    assert updated["effective_level"] == "B2"
    cleared = repository.update_article(article["id"], actor="admin@example.com", reviewed_level=None)
    assert cleared["reviewed_level"] is None and cleared["effective_level"] == "B1"


def test_publishing_makes_it_learner_visible_and_stamps_the_time(repository):
    article = _article(repository)
    published = repository.set_status(article["id"], "published", actor="admin@example.com")
    assert published["published_at"] is not None
    listed = repository.list_published(language="en")["items"]
    assert [item["id"] for item in listed] == [article["id"]]


def test_unpublishing_hides_it_without_losing_it(repository):
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    repository.set_status(article["id"], "unpublished", actor="admin@example.com")
    assert repository.list_published(language="en")["items"] == []
    kept = repository.get_article(article["id"])
    assert kept["body"] == BODY and kept["unpublished_at"] is not None


def test_a_rejected_text_cannot_come_back_as_a_new_candidate(repository):
    article = _article(repository)
    repository.set_status(article["id"], "rejected", actor="admin@example.com", reason="not learner material")
    again = _snapshot(repository)
    assert again["duplicate"] is True
    existing = repository.article_for_source_item(again["id"])
    assert existing["status"] == "rejected" and existing["rejection_reason"] == "not learner material"


def test_editing_published_content_bumps_the_revision_a_cache_validates_on(repository):
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    before = repository.get_article(article["id"])["content_revision"]
    after = repository.update_article(
        article["id"], actor="admin@example.com", title="Rain returns to the valley floor"
    )
    assert after["content_revision"] == before + 1


def test_every_change_a_learner_can_see_moves_the_revision(repository):
    """`content_revision` is what a cached copy revalidates against, so it has
    to move for anything the learner routes return - not only the body. A
    corrected topic or level that keeps the old revision leaves a learner
    reading a card that is quietly wrong for up to a cache lifetime."""
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")

    def revision():
        return repository.get_article(article["id"])["content_revision"]

    for change in (
        {"title": "Rain returns to the valley floor"},
        {"topic": "weather"},
        {"excerpt": "The river rose overnight."},
        {"body": BODY + "A correction followed. "},
        {"reviewed_level": "C1"},
    ):
        before = revision()
        repository.update_article(article["id"], actor="admin@example.com", **change)
        assert revision() == before + 1, f"{change} is visible to a learner"


def test_a_change_nobody_can_see_does_not_move_the_revision(repository):
    """The converse matters too: a bump with no visible change makes every
    cached copy refetch for nothing."""
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    before = repository.get_article(article["id"])["content_revision"]
    repository.update_article(article["id"], actor="admin@example.com", subtopic="flooding")
    assert repository.get_article(article["id"])["content_revision"] == before
    repository.update_article(article["id"], actor="admin@example.com", title="Rain returns to the valley")
    assert repository.get_article(article["id"])["content_revision"] == before, "an unchanged title is not a change"


def test_a_target_decision_moves_the_revision_because_a_learner_reads_targets(repository):
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    targets = repository.get_article(article["id"])["targets"]
    before = repository.get_article(article["id"])["content_revision"]
    repository.decide_target(targets[0]["id"], article_id=article["id"], approved=True, actor="admin@example.com")
    after = repository.get_article(article["id"])["content_revision"]
    assert after == before + 1
    assert repository.get_published_article(article["id"])["content_revision"] == after


def test_adding_and_removing_a_target_moves_the_revision_too(repository):
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    before = repository.get_article(article["id"])["content_revision"]
    added = repository.add_target(
        article["id"],
        target=TargetInput(text="volunteers", canonical_form="volunteers", target_type="word",
                           context="volunteers began to clear the mud", estimated_level="", rank=9),
        actor="admin@example.com",
    )
    assert repository.get_article(article["id"])["content_revision"] == before + 1
    repository.remove_target(added["id"], actor="admin@example.com")
    assert repository.get_article(article["id"])["content_revision"] == before + 2


# ---- projections ------------------------------------------------------------

def test_the_learner_list_is_lightweight_and_says_nothing_about_review(repository):
    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    item = repository.list_published(language="en")["items"][0]
    assert set(item) == {
        "id", "title", "language", "level", "topic", "reading_time_seconds",
        "excerpt", "word_count", "published_at", "content_revision",
    }
    assert item["level"] == "B1"


def test_the_learner_detail_carries_the_body_and_only_approved_targets(repository):
    article = _article(repository)
    targets = repository.get_article(article["id"])["targets"]
    repository.decide_target(targets[0]["id"], article_id=article["id"], approved=True, actor="admin@example.com")
    repository.set_status(article["id"], "published", actor="admin@example.com")
    detail = repository.get_published_article(article["id"])
    assert detail["body"] == BODY
    assert [target["text"] for target in detail["targets"]] == ["higher ground"]
    assert "analysis" not in detail and "rights" not in detail


def test_an_unpublished_article_is_not_readable_through_the_learner_path(repository):
    article = _article(repository)
    assert repository.get_published_article(article["id"]) is None


def test_the_review_queue_is_metadata_and_paginated(repository):
    for index in range(4):
        _article(repository, body=BODY + f"Story {index}. ")
    page = repository.list_queue(limit=2)
    assert len(page["items"]) == 2 and page["next_cursor"]
    assert all("body" not in item for item in page["items"])
    second = repository.list_queue(limit=2, cursor=page["next_cursor"])
    assert {item["id"] for item in page["items"]} & {item["id"] for item in second["items"]} == set()
    assert len(repository.list_queue(limit=10_000)["items"]) <= MAX_ARTICLE_PAGE


def test_neither_list_asks_the_database_for_a_body(repository):
    """A projection that drops the body in Python still read it from disk and
    carried it across the connection for every row on the page. Both lists -
    the learner's and the admin queue - name their columns, so the cost of a
    page stops depending on how long the articles on it are."""
    from sqlalchemy import event

    statements: list[str] = []

    @event.listens_for(repository.engine, "before_cursor_execute")
    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(" ".join(statement.split()))

    article = _article(repository)
    repository.set_status(article["id"], "published", actor="admin@example.com")
    statements.clear()
    repository.list_published(language="en")
    repository.list_queue()
    event.remove(repository.engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.upper().startswith("SELECT") and "reading_articles" in s]
    assert len(selects) == 2
    for statement in selects:
        assert "reading_articles.body" not in statement, statement
        assert "reading_articles.analysis_json" not in statement, statement
        assert "reading_articles.title" in statement


def test_the_learner_list_filters_in_the_database_by_level_and_topic(repository):
    first = _article(repository, body=BODY + "One. ")
    second = _article(repository, body=BODY + "Two. ")
    repository.update_article(second["id"], actor="admin@example.com", reviewed_level="C1", topic="science")
    for article in (first, second):
        repository.set_status(article["id"], "published", actor="admin@example.com")
    assert [item["id"] for item in repository.list_published(language="en", level="C1")["items"]] == [second["id"]]
    assert [item["id"] for item in repository.list_published(language="en", topic="environment")["items"]] == [first["id"]]
    assert repository.list_published(language="zh")["items"] == []


def test_the_learner_list_pages_without_repeating_or_skipping(repository):
    published = []
    for index in range(5):
        article = _article(repository, body=BODY + f"Story {index}. ")
        repository.set_status(article["id"], "published", actor="admin@example.com")
        published.append(article["id"])
    seen, cursor = [], None
    while True:
        page = repository.list_published(language="en", cursor=cursor, limit=2)
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == sorted(published) and len(seen) == len(set(seen))


# ---- the review trail -------------------------------------------------------

def test_every_decision_leaves_a_readable_trail(repository):
    article = _article(repository)
    repository.update_article(article["id"], actor="admin@example.com", reviewed_level="B2")
    repository.set_status(article["id"], "published", actor="admin@example.com")
    actions = [event["action"] for event in repository.list_review_events(article["id"])]
    assert actions == ["created", "level_override", "published"]
    assert all(event["actor"] for event in repository.list_review_events(article["id"])[1:])


def test_a_target_decision_is_recorded_as_the_admins_not_the_machines(repository):
    article = _article(repository)
    target = repository.get_article(article["id"])["targets"][0]
    assert target["machine_suggested"] is True and target["admin_approved"] is False
    decided = repository.decide_target(target["id"], article_id=article["id"], approved=True, actor="admin@example.com")
    assert decided["admin_approved"] is True and decided["machine_suggested"] is True
    rejected = repository.decide_target(target["id"], article_id=article["id"], approved=False, actor="admin@example.com")
    assert rejected["admin_approved"] is False and rejected["admin_rejected"] is True


def test_two_targets_without_a_canonical_form_can_both_exist(repository):
    """The partial unique index exists so an uncanonicalized pair is allowed;
    without it the second target would fail on the primary workflow."""
    article = _article(
        repository,
        targets=[
            TargetInput(text="one", canonical_form="", target_type="word", context="c", estimated_level="", rank=0),
            TargetInput(text="two", canonical_form="", target_type="word", context="c", estimated_level="", rank=1),
        ],
    )
    assert len(repository.get_article(article["id"])["targets"]) == 2


def test_a_published_article_keeps_its_source_attribution(repository):
    article = _article(repository, url="https://example.com/news/rain")
    repository.set_status(article["id"], "published", actor="admin@example.com")
    detail = repository.get_published_article(article["id"])
    assert detail["attribution"]["author"] == "M. Tran"
    assert detail["attribution"]["source_url"] == "https://example.com/news/rain"


def test_the_repository_never_rewrites_a_snapshot(repository):
    """The trigger enforces this on PostgreSQL; on SQLite the invariant is
    this test - no UPDATE is ever issued against a snapshot's own columns."""
    statements: list[str] = []
    engine = repository.engine

    @event.listens_for(engine, "before_cursor_execute")
    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(" ".join(statement.split()))

    article = _article(repository, native_id="valley-1")
    repository.update_article(article["id"], actor="admin@example.com", reviewed_level="B2")
    repository.set_status(article["id"], "published", actor="admin@example.com")
    _snapshot(repository, native_id="valley-1", body=BODY + "Changed. ")
    event.remove(engine, "before_cursor_execute", record)

    snapshot_updates = [
        statement
        for statement in statements
        if statement.upper().startswith("UPDATE READING_SOURCE_ITEMS")
    ]
    assert snapshot_updates, "the supersede stamp is the one update this table receives"
    for statement in snapshot_updates:
        assert "superseded_at" in statement
        for column in ("original_content", "content_hash", "source_id", "fetched_at", "revision"):
            assert f"{column}=" not in statement.replace(" ", "")


def test_the_admin_detail_carries_what_review_needs_and_no_more(repository):
    article = _article(repository)
    detail = repository.get_article(article["id"])
    assert detail["source"]["title"] == "Rain returns"
    assert detail["source"]["rights"] == {"can_republish": True}
    assert detail["analysis"] == {"sentence_count": 2}
    assert len(detail["targets"]) == 2


def test_an_unknown_article_is_absent_rather_than_an_error(repository):
    assert repository.get_article(str(uuid.uuid4())) is None
    assert repository.set_status(str(uuid.uuid4()), "published", actor="admin@example.com") is None


def test_published_ordering_is_newest_first(repository):
    older = _article(repository, body=BODY + "Older. ")
    newer = _article(repository, body=BODY + "Newer. ")
    moment = datetime.now(UTC)
    repository.set_status(older["id"], "published", actor="a@example.com", now=moment - timedelta(days=1))
    repository.set_status(newer["id"], "published", actor="a@example.com", now=moment)
    assert [item["id"] for item in repository.list_published(language="en")["items"]] == [
        newer["id"],
        older["id"],
    ]


def test_the_engine_never_writes_an_article_without_its_snapshot(repository):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        repository.create_article(
            source_item_id=str(uuid.uuid4()), title="Orphan", body=BODY, excerpt="", language="en",
            topic="", estimated_level="B1", estimated_confidence=0.5, word_count=10,
            reading_time_seconds=30, analysis={}, targets=[],
        )
    with repository.engine.connect() as connection:
        assert connection.execute(select(ReadingArticle.id)).all() == []


# ---- rights, in three states ------------------------------------------------

def test_an_unanswered_rights_question_is_not_a_refusal(repository):
    """`False` and "nobody said" are different answers and look different."""
    snapshot = repository.record_source_item(
        source_id=repository.built_in_source_id("manual"),
        source_native_id="", canonical_url="", title="Unasserted", author="",
        published_at=None, language="en", body=BODY + "x",
        content_hash=f"{abs(hash(BODY + 'x')):064x}"[:64],
        metadata={"input_kind": "text"}, rights={},
    )
    assert snapshot["rights_state"]["can_republish"] == "unknown"
    assert snapshot["rights_state"]["attribution_required"] == "unknown"


def test_a_right_that_was_answered_says_which_answer(repository):
    snapshot = repository.record_source_item(
        source_id=repository.built_in_source_id("manual"),
        source_native_id="", canonical_url="", title="Answered", author="",
        published_at=None, language="en", body=BODY + "y",
        content_hash=f"{abs(hash(BODY + 'y')):064x}"[:64],
        metadata={"input_kind": "text"},
        rights={"can_republish": True, "can_adapt": False},
    )
    state = snapshot["rights_state"]
    assert state["can_republish"] == "allowed"
    assert state["can_adapt"] == "denied"
    assert state["automation_allowed"] == "unknown"


def test_the_duplicate_warning_names_the_other_source(repository):
    """A count is not a decision. An admin needs to know *whose* copy it is."""
    first = _snapshot(repository)
    repository.record_source_item(
        source_id=repository.built_in_source_id("file"),
        source_native_id="", canonical_url="", title="Rain returns", author="",
        published_at=None, language="en", body=BODY, content_hash=first["content_hash"],
        metadata={}, rights={},
    )
    seen = repository.find_duplicate_content(
        first["content_hash"], exclude_source_id=repository.built_in_source_id("file")
    )
    assert [item["source_name"] for item in seen] == ["Manual paste"]


# ---- the order targets are taught in ----------------------------------------

def test_reordering_targets_writes_the_new_rank_and_records_who_did_it(repository):
    article = _article(repository, body=BODY + "order", native_id="ord")
    detail = repository.get_article(article["id"])
    first, second = [target["id"] for target in detail["targets"]]
    reordered = repository.reorder_targets(article["id"], order=[second, first], actor="admin@example.com")
    assert [target["id"] for target in reordered] == [second, first]
    assert [target["rank"] for target in reordered] == [0, 1]
    assert [target["id"] for target in repository.get_article(article["id"])["targets"]] == [second, first]
    assert repository.list_review_events(article["id"])[-1]["action"] == "targets_reordered"


def test_an_order_that_is_not_this_articles_targets_is_refused(repository):
    article = _article(repository, body=BODY + "refuse", native_id="ref")
    other = _article(repository, body=BODY + "other", native_id="oth")
    mine = [target["id"] for target in repository.get_article(article["id"])["targets"]]
    theirs = [target["id"] for target in repository.get_article(other["id"])["targets"]]
    assert repository.reorder_targets(article["id"], order=[mine[0]], actor="a@b.c") is None
    assert repository.reorder_targets(article["id"], order=[mine[0], theirs[0]], actor="a@b.c") is None
    # Refused means nothing moved.
    assert [target["id"] for target in repository.get_article(article["id"])["targets"]] == mine
