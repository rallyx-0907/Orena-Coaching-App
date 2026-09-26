"""Canonical Reading evidence: sets, attempts, ability, the next article.

The repository is the one owner of Reading evidence (D-082). These hold what a
learner or an Admin would feel if it broke: a set is grounded in the exact body
it was built from, a learner meets only an approved and anchored set, a submit
retried after a lost response records one attempt, an edit to the text never
falsifies evidence already recorded, ability is a replay of the attempts and
nothing else, and the next article is chosen by rule, never by chance. English
and Chinese run the same paths.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, event, func, insert, select  # noqa: E402

from writing_coach import reading_policy as policy  # noqa: E402
from writing_coach.persistence.models import (  # noqa: E402
    Base,
    LegacyReadingAttempt,
    LegacyReadingSession,
    ReadingAbilityProjection,
    ReadingAttempt,
    User,
)
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    ReadingContentRepository,
    TargetInput,
)
from writing_coach.persistence.reading_evidence_repository import (  # noqa: E402
    QuestionInput,
    ReadingEvidenceError,
    RECOMMENDATION_TTL,
    ReadingEvidenceRepository,
    body_sha256,
)

BODIES = {
    "en": (
        "Tom missed the early train. He waited forty minutes on a cold platform. "
        "When the next train came, it was full, so he stood all the way to the city."
    ),
    "zh": "小明错过了早班火车。他在寒冷的站台上等了四十分钟。下一班火车来的时候已经满了，所以他一路站到城里。",
}
EVIDENCE = {
    "en": ("forty minutes", "it was full"),
    "zh": ("四十分钟", "已经满了"),
}
LEVELS = {"en": ("A2", "B1", "B2", "C1"), "zh": ("HSK2", "HSK3", "HSK4", "HSK5")}


class Scope:
    def __init__(self) -> None:
        self.user = "learner-a"
        self.language = "en"


@pytest.fixture()
def world(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'evidence.db'}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    scope = Scope()
    evidence = ReadingEvidenceRepository(
        engine, user_key_provider=lambda: scope.user, language_provider=lambda: scope.language
    )
    yield engine, content, evidence, scope
    engine.dispose()


_clock = [datetime(2026, 9, 24, 8, 0, tzinfo=UTC)]


def _tick() -> datetime:
    _clock[0] += timedelta(minutes=1)
    return _clock[0]


def _article(content, *, language="en", level="B1", body=None, publish=True):
    body = body or BODIES[language]
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="",
        title="Train", author="", published_at=None, language=language, body=body,
        content_hash=uuid.uuid4().hex * 2, metadata={}, rights={"can_republish": True},
    )
    article = content.create_article(
        source_item_id=snapshot["id"], title=f"Train {uuid.uuid4().hex[:6]}", body=body, excerpt=body[:60],
        language=language, topic="travel", estimated_level=level, estimated_confidence=0.7,
        word_count=30, reading_time_seconds=60, analysis={},
        targets=[TargetInput(text=EVIDENCE[language][0], canonical_form=EVIDENCE[language][0],
                             target_type="phrase", context="", estimated_level="", rank=0)],
    )
    if publish:
        content.set_status(article["id"], "published", actor="admin", now=_tick())
    return article["id"]


def _questions(language="en"):
    first, second = EVIDENCE[language]
    return [
        QuestionInput("detail", "How long did he wait?", ["forty minutes", "ten minutes", "an hour", "all day"],
                      0, "Anh ấy đợi bốn mươi phút.", first, rank=0),
        QuestionInput("inference", "Why did he stand?", ["the train was full", "he liked standing",
                                                         "his seat broke", "he was late"],
                      0, "Tàu đã đầy.", second, rank=1),
        QuestionInput("main_idea", "What is it about?", ["a hard journey", "a holiday", "a race", "a meal"],
                      0, "Một chuyến đi vất vả.", None, rank=2),
    ]


def _anchor(content, article_id) -> str:
    """The hash of the body the questions are written from - what the Admin
    route takes before it asks the AI."""
    return body_sha256(content.get_article(article_id)["body"])


def _approved(content, evidence, *, language="en", level="B1", support="vi", body=None):
    article_id = _article(content, language=language, level=level, body=body)
    built = evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language=support, generator_version="test/1", model="stub",
                                questions=_questions(language), validation={}, actor="admin", now=_tick())
    evidence.transition(built["id"], "needs_review", actor="admin", now=_tick())
    for question in built["questions"]:
        evidence.decide_question(built["id"], question["id"], decision="approve", actor="admin", now=_tick())
    evidence.transition(built["id"], "approved", actor="admin", now=_tick())
    return article_id, built["id"]


def _answers(evidence, article_id, *, support="vi", right=True):
    served = evidence.served_set(article_id, support_language=support)
    # The stub's correct answer is always option 0.
    return served["id"], {item["id"]: (0 if right else 1) for item in served["questions"]}


def _count(engine, model, *where) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(model).where(*where)).scalar_one()


@pytest.mark.parametrize("language", ["en", "zh"])
def test_one_question_returns_feedback_without_writing_attempt(world, language):
    engine, content, evidence, scope = world
    scope.language = language
    article_id, set_id = _approved(content, evidence, language=language)
    served = evidence.served_set(article_id, support_language="vi")
    question_id = served["questions"][0]["id"]
    right = evidence.grade_question(set_id, question_id, 0, support_language="vi")
    wrong = evidence.grade_question(set_id, question_id, 1, support_language="vi")
    assert right["correct"] is True
    assert wrong["correct"] is False
    assert right["evidence_fragment"] == EVIDENCE[language][0]
    assert right["explanation"] == _questions(language)[0].explanation
    assert _count(engine, ReadingAttempt) == 0
    answers = {item["id"]: 0 for item in served["questions"]}
    submitted = evidence.submit_attempt(set_id=set_id, operation_id=str(uuid.uuid4()),
                                        answers=answers, support_language="vi")
    assert submitted.status == "committed"
    assert _count(engine, ReadingAttempt) == 1


def test_question_grade_rejects_unserved_or_invalid_choices(world):
    _, content, evidence, _ = world
    article_id, set_id = _approved(content, evidence)
    question_id = evidence.served_set(article_id, support_language="vi")["questions"][0]["id"]
    assert evidence.grade_question(set_id, question_id, 0, support_language="en") is None
    assert evidence.grade_question(set_id, str(uuid.uuid4()), 0, support_language="vi") is None
    with pytest.raises(ReadingEvidenceError) as caught:
        evidence.grade_question(set_id, question_id, 4, support_language="vi")
    assert caught.value.code == "reading_question_choice"
    content.set_status(article_id, "archived", actor="admin", now=_tick())
    assert evidence.grade_question(set_id, question_id, 0, support_language="vi") is None


# ---- sets: grounding and review ----------------------------------------------

@pytest.mark.parametrize("language", ["en", "zh"])
def test_a_set_is_grounded_in_the_exact_body_by_code_point(world, language):
    _, content, evidence, _ = world
    article_id = _article(content, language=language, level=LEVELS[language][1])
    built = evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language="VI", generator_version="test/1", model="stub",
                                questions=_questions(language), validation={}, actor="admin")
    body = BODIES[language]
    assert built["status"] == "draft"
    assert built["support_language"] == "vi"
    assert built["language_code"] == language
    assert built["article_body_sha256"] == body_sha256(body)
    assert built["anchored"] is True
    for question in built["questions"]:
        if question["evidence_text"]:
            assert body[question["evidence_start"]:question["evidence_end"]] == question["evidence_text"]
        else:
            assert question["question_type"] in {"main_idea", "authors_purpose"}


def test_an_ungrounded_question_is_refused_before_anything_is_written(world):
    engine, content, evidence, _ = world
    article_id = _article(content)
    bad = [*_questions(), QuestionInput("detail", "Where?", ["a", "b"], 0, "x", "not in the passage", rank=3)]
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language="vi", generator_version="test/1", model="",
                            questions=bad, validation={}, actor="admin")
    assert refused.value.code == "reading_evidence_not_grounded"
    assert evidence.list_sets(article_id) == []
    uncited = [QuestionInput("detail", "Where?", ["a", "b"], 0, "x", None)]
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language="vi", generator_version="test/1", model="",
                            questions=uncited, validation={}, actor="admin")
    assert refused.value.code == "reading_evidence_required"


def test_a_learner_meets_only_an_approved_set_and_never_its_answers(world):
    _, content, evidence, _ = world
    article_id = _article(content)
    built = evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language="vi", generator_version="test/1", model="stub",
                                questions=_questions(), validation={}, actor="admin", now=_tick())
    assert evidence.served_set(article_id, support_language="vi") is None
    evidence.transition(built["id"], "needs_review", actor="admin", now=_tick())
    first, second, third = (item["id"] for item in built["questions"])
    evidence.decide_question(built["id"], first, decision="approve", actor="admin", now=_tick())
    # An undecided question blocks approval.
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.transition(built["id"], "approved", actor="admin", now=_tick())
    assert refused.value.code == "reading_set_transition_refused"
    evidence.decide_question(built["id"], second, decision="reject", actor="admin", now=_tick())
    evidence.decide_question(built["id"], third, decision="approve", actor="admin", now=_tick())
    approved = evidence.transition(built["id"], "approved", actor="admin", now=_tick())
    assert approved["status"] == "approved" and approved["reviewed_by"] == "admin"
    # A decided set is frozen.
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.decide_question(built["id"], second, decision="approve", actor="admin", now=_tick())
    assert refused.value.code == "reading_set_frozen"
    served = evidence.served_set(article_id, support_language="vi")
    assert [item["id"] for item in served["questions"]] == [first, third]
    for item in served["questions"]:
        assert not {"correct_index", "explanation", "evidence_text"} & set(item)
    # Another support language is Free Reading.
    assert evidence.served_set(article_id, support_language="zh") is None
    # A set that reached learners is archived, never deleted.
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.discard_set(built["id"], actor="admin")
    assert refused.value.code == "reading_set_undeletable"


def test_an_unpublished_article_serves_no_set(world):
    _, content, evidence, _ = world
    article_id, _ = _approved(content, evidence)
    content.set_status(article_id, "archived", actor="admin", now=_tick())
    assert evidence.served_set(article_id, support_language="vi") is None


def test_a_set_is_built_and_approved_for_a_published_article_only(world):
    """D-082: publish, then the set. A candidate gets no questions, and a set
    whose article left the corpus before its approval stays undecided."""
    engine, content, evidence, _ = world
    candidate = _article(content, publish=False)
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.create_set(candidate, expected_body_sha256=_anchor(content, candidate), support_language="vi", generator_version="test/1", model="stub",
                            questions=_questions(), validation={}, actor="admin", now=_tick())
    assert refused.value.code == "reading_article_not_published"
    assert evidence.list_sets(candidate) == []

    article_id = _article(content)
    built = evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id), support_language="vi", generator_version="test/1", model="stub",
                                questions=_questions(), validation={}, actor="admin", now=_tick())
    evidence.transition(built["id"], "needs_review", actor="admin", now=_tick())
    for question in built["questions"]:
        evidence.decide_question(built["id"], question["id"], decision="approve", actor="admin", now=_tick())
    content.set_status(article_id, "unpublished", actor="admin", now=_tick())
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.transition(built["id"], "approved", actor="admin", now=_tick())
    assert refused.value.code == "reading_article_not_published"
    assert evidence.get_set(built["id"])["status"] == "needs_review"
    content.set_status(article_id, "published", actor="admin", now=_tick())
    assert evidence.transition(built["id"], "approved", actor="admin", now=_tick())["status"] == "approved"


# ---- the submit ----------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "zh"])
def test_a_set_is_anchored_only_to_the_body_its_questions_were_written_from(world, language):
    """The hash is taken before the AI call; an edit that lands while the model
    writes is refused under the article's lock, and nothing is written."""
    engine, content, evidence, scope = world
    scope.language = language
    article_id = _article(content, language=language)
    shown = _anchor(content, article_id)
    content.update_article(article_id, actor="admin", body=BODIES[language] + EVIDENCE[language][0])
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.create_set(article_id, expected_body_sha256=shown, support_language="vi",
                            generator_version="test/1", model="stub", questions=_questions(language),
                            validation={}, actor="admin", now=_tick())
    assert refused.value.code == "reading_article_changed"
    assert evidence.list_sets(article_id) == []
    built = evidence.create_set(article_id, expected_body_sha256=_anchor(content, article_id),
                                support_language="vi", generator_version="test/1", model="stub",
                                questions=_questions(language), validation={}, actor="admin", now=_tick())
    assert built["article_body_sha256"] == _anchor(content, article_id) != shown


@pytest.mark.parametrize("language", ["en", "zh"])
def test_a_retried_submit_records_one_attempt_and_moves_ability_once(world, language):
    engine, content, evidence, scope = world
    scope.language = language
    article_id, _ = _approved(content, evidence, language=language, level=LEVELS[language][1])
    set_id, answers = _answers(evidence, article_id)
    first = evidence.submit_attempt(set_id=set_id, operation_id="op-1", answers=answers, support_language="vi")
    again = evidence.submit_attempt(set_id=set_id, operation_id="op-1", answers=answers, support_language="vi")
    assert first.status == again.status == "committed"
    assert (first.replayed, again.replayed) == (False, True)
    assert again.attempt == first.attempt
    assert first.attempt["ordinal"] == 1 and first.attempt["correct_count"] == first.attempt["total"] == 3
    assert first.attempt["language_code"] == language
    assert first.attempt["ability_policy_version"] == policy.ABILITY_POLICY_VERSION
    assert first.attempt["ability_after"] > first.attempt["ability_before"]
    assert _count(engine, ReadingAttempt) == 1
    assert evidence.ability()["ability"] == first.attempt["ability_after"]
    # The same operation id with other answers is not a retry.
    changed = {key: 1 for key in answers}
    reused = evidence.submit_attempt(set_id=set_id, operation_id="op-1", answers=changed, support_language="vi")
    assert (reused.status, reused.reason) == ("rejected", "operation_reused")
    # Two submits with the same answers are two attempts.
    second = evidence.submit_attempt(set_id=set_id, operation_id="op-2", answers=answers, support_language="vi")
    assert second.attempt["ordinal"] == 2
    assert _count(engine, ReadingAttempt) == 2


def test_a_submit_is_refused_with_a_reason_and_writes_nothing(world):
    engine, content, evidence, scope = world
    article_id, _ = _approved(content, evidence)
    set_id, answers = _answers(evidence, article_id)
    some = dict(list(answers.items())[:1])
    out_of_range = {key: 9 for key in answers}
    cases = [
        (dict(set_id=set_id, operation_id="", answers=answers, support_language="vi"), "operation_id_required"),
        (dict(set_id="nope", operation_id="a", answers=answers, support_language="vi"), "set_not_found"),
        (dict(set_id=str(uuid.uuid4()), operation_id="b", answers=answers, support_language="vi"), "set_not_found"),
        (dict(set_id=set_id, operation_id="c", answers=some, support_language="vi"), "answers_do_not_match_questions"),
        (dict(set_id=set_id, operation_id="d", answers=out_of_range, support_language="vi"), "answer_out_of_range"),
        (dict(set_id=set_id, operation_id="e", answers=answers, support_language="zh"), "support_language_mismatch"),
    ]
    for kwargs, reason in cases:
        result = evidence.submit_attempt(**kwargs)
        assert (result.status, result.reason) == ("rejected", reason), kwargs
    scope.language = "zh"
    result = evidence.submit_attempt(set_id=set_id, operation_id="f", answers=answers, support_language="vi")
    assert (result.status, result.reason) == ("rejected", "language_mismatch")
    assert _count(engine, ReadingAttempt) == 0
    assert _count(engine, User) == 0, "a refused submit does not even create the account row"


def test_an_attempt_the_policy_cannot_measure_still_commits(world):
    engine, content, evidence, _ = world
    article_id, _ = _approved(content, evidence, level="")
    set_id, answers = _answers(evidence, article_id)
    result = evidence.submit_attempt(set_id=set_id, operation_id="op", answers=answers, support_language="vi")
    assert result.status == "committed"
    attempt = result.attempt
    assert attempt["passage_level"] == "unknown"
    assert (attempt["ability_policy_version"], attempt["ability_before"], attempt["ability_after"]) == (None,) * 3
    assert evidence.ability()["ability"] == policy.INITIAL_ABILITY
    assert evidence.ability()["attempts"] == 1


# ---- an edit never falsifies evidence ---------------------------------------------

def test_a_body_edit_stales_the_set_and_keeps_the_evidence(world):
    engine, content, evidence, _ = world
    article_id, set_id = _approved(content, evidence)
    served_id, answers = _answers(evidence, article_id)
    recorded = evidence.submit_attempt(set_id=served_id, operation_id="op", answers=answers, support_language="vi")
    edited = content.update_article(article_id, actor="admin", body=BODIES["en"] + " He was tired.", now=_tick())
    assert edited is not None
    assert evidence.get_set(set_id)["status"] == "stale"
    assert evidence.get_set(set_id)["anchored"] is False
    events = content.list_review_events(article_id)
    assert any(event["action"] == "comprehension_set_stale" for event in events)
    assert evidence.served_set(article_id, support_language="vi") is None
    late = evidence.submit_attempt(set_id=served_id, operation_id="late", answers=answers, support_language="vi")
    assert (late.status, late.reason) == ("rejected", "set_stale")
    # A retry of the already-recorded submit still answers with what was saved.
    retry = evidence.submit_attempt(set_id=served_id, operation_id="op", answers=answers, support_language="vi")
    assert retry.replayed and retry.attempt == recorded.attempt
    # The stale set cannot be re-approved against a body it does not match.
    with pytest.raises(ReadingEvidenceError) as refused:
        evidence.transition(set_id, "approved", actor="admin", now=_tick())
    assert refused.value.code == "reading_set_stale"
    listed = evidence.list_evidence()
    assert [item["id"] for item in listed] == [recorded.attempt["id"]]
    assert listed[0]["correct_count"] == 3
    # Putting the body back lets the same set be approved again.
    content.update_article(article_id, actor="admin", body=BODIES["en"], now=_tick())
    assert evidence.transition(set_id, "approved", actor="admin", now=_tick())["status"] == "approved"


def test_an_unchanged_body_does_not_stale_anything(world):
    _, content, evidence, _ = world
    article_id, set_id = _approved(content, evidence)
    content.update_article(article_id, actor="admin", body=BODIES["en"], title="Renamed", now=_tick())
    assert evidence.get_set(set_id)["status"] == "approved"


# ---- ability ------------------------------------------------------------------

def test_ability_rebuilt_from_the_attempts_equals_the_incremental_projection(world):
    engine, content, evidence, _ = world
    for index, level in enumerate(("A2", "B1", "B2", "B1", "C1", "B2")):
        article_id, _ = _approved(content, evidence, level=level)
        set_id, answers = _answers(evidence, article_id, right=index % 3 != 2)
        evidence.submit_attempt(set_id=set_id, operation_id=f"op-{index}", answers=answers, support_language="vi")
    incremental = evidence.ability()
    rebuilt = evidence.rebuild_projection()
    assert rebuilt == incremental
    assert incremental["attempts"] == 6
    # The last attempt's recorded measurement is the projection's ability.
    with engine.connect() as connection:
        last = connection.execute(select(ReadingAttempt.ability_after).order_by(ReadingAttempt.ordinal.desc())
                                  .limit(1)).scalar_one()
    assert last == incremental["ability"]
    # A discarded projection is a rebuild, never lost evidence.
    with engine.begin() as connection:
        connection.execute(ReadingAbilityProjection.__table__.delete())
    assert evidence.ability() == incremental
    assert _count(engine, ReadingAttempt) == 6


def test_ability_is_per_account_and_language(world):
    _, content, evidence, scope = world
    article_id, _ = _approved(content, evidence)
    set_id, answers = _answers(evidence, article_id)
    evidence.submit_attempt(set_id=set_id, operation_id="op", answers=answers, support_language="vi")
    assert evidence.ability()["attempts"] == 1
    scope.language = "zh"
    assert evidence.ability()["attempts"] == 0
    scope.language, scope.user = "en", "learner-b"
    assert evidence.ability()["attempts"] == 0
    assert evidence.list_evidence() == []


# ---- the next article -------------------------------------------------------------

def _choice(offer):
    """A choice without its recommendation, which carries the moment it was
    issued: two identical choices a second apart sign differently."""
    return {key: value for key, value in offer.items() if key != "recommendation"}


def test_the_next_article_is_chosen_by_rule_and_never_repeats(world):
    _, content, evidence, _ = world
    by_level = {level: _approved(content, evidence, level=level)[0] for level in ("A1", "A2", "B1", "C2")}
    first = evidence.next_article(support_language="vi")
    assert _choice(first) == _choice(evidence.next_article(support_language="vi")), \
        "the same inputs choose the same article"
    # A fresh learner starts at A2.
    assert first["article_id"] == by_level["A2"]
    assert first["selection_policy_version"] == policy.SELECTION_POLICY_VERSION
    assert "correct_index" not in first["set"]["questions"][0]
    set_id, answers = _answers(evidence, first["article_id"])
    saved = evidence.submit_attempt(set_id=set_id, operation_id="op", answers=answers, support_language="vi",
                                    recommendation=first["recommendation"])
    assert saved.attempt["selection_policy_version"] == policy.SELECTION_POLICY_VERSION
    second = evidence.next_article(support_language="vi")
    assert second["article_id"] != first["article_id"]
    # All right moved ability and recent performance up: the next is harder.
    assert second["article_id"] == by_level["B1"]
    assert evidence.list_evidence()[0]["passage_level"] == "A2"


@pytest.mark.parametrize("language", ["en", "zh"])
def test_opening_the_recommended_article_some_other_way_is_the_learners_choice(world, language):
    """Provenance is the recommendation the server issued, not a coincidence:
    the very article the policy would choose, answered without its
    recommendation, is recorded as the learner's own."""
    _, content, evidence, scope = world
    scope.language = language
    for level in LEVELS[language]:
        _approved(content, evidence, language=language, level=level)
    offer = evidence.next_article(support_language="vi")
    set_id, answers = _answers(evidence, offer["article_id"])
    independent = evidence.submit_attempt(set_id=set_id, operation_id="library", answers=answers,
                                          support_language="vi")
    assert independent.attempt["selection_policy_version"] is None
    # The request cannot state provenance itself.
    with pytest.raises(TypeError):
        evidence.submit_attempt(set_id=set_id, operation_id="claim", answers=answers, support_language="vi",
                                selection_policy_version=policy.SELECTION_POLICY_VERSION)


@pytest.mark.parametrize("language", ["en", "zh"])
def test_a_recommendation_keeps_its_provenance_when_evidence_moves_before_its_submit(world, language):
    """Recommended, then another attempt lands first (another tab, another
    article): the policy would choose differently now, and the recommendation
    still counts - it records what was recommended, not a recomputation."""
    engine, content, evidence, scope = world
    scope.language = language
    easy, middle, hard = (("A2", "B1", "B2") if language == "en" else ("HSK2", "HSK3", "HSK4"))
    by_level = {level: _approved(content, evidence, language=language, level=level)[0]
                for level in (easy, middle, hard)}
    offer = evidence.next_article(support_language="vi")
    assert offer["article_id"] == by_level[easy]
    # All right on the hard one first: ability 2.0 -> ~3.06, target ~3.56.
    set_id, answers = _answers(evidence, by_level[hard])
    evidence.submit_attempt(set_id=set_id, operation_id="first", answers=answers, support_language="vi")
    assert evidence.next_article(support_language="vi")["article_id"] == by_level[middle], \
        "the policy has moved on"
    set_id, answers = _answers(evidence, offer["article_id"])
    late = evidence.submit_attempt(set_id=set_id, operation_id="recommended", answers=answers,
                                   support_language="vi", recommendation=offer["recommendation"])
    assert late.attempt["selection_policy_version"] == policy.SELECTION_POLICY_VERSION
    replay = evidence.submit_attempt(set_id=set_id, operation_id="recommended", answers=answers,
                                     support_language="vi", recommendation=offer["recommendation"])
    assert replay.replayed and replay.attempt == late.attempt
    # Spent: a second attempt on the same set does not count it again.
    again = evidence.submit_attempt(set_id=set_id, operation_id="again", answers=answers,
                                    support_language="vi", recommendation=offer["recommendation"])
    assert again.attempt["selection_policy_version"] is None
    with engine.connect() as connection:
        stored = dict(connection.execute(select(ReadingAttempt.operation_id,
                                                ReadingAttempt.selection_policy_version)).all())
    assert stored == {"first": None, "recommended": policy.SELECTION_POLICY_VERSION, "again": None}


def test_only_an_unaltered_live_recommendation_for_this_account_and_set_counts(world):
    engine, content, evidence, scope = world
    other_article, other_set = _approved(content, evidence, level="C2")
    _approved(content, evidence, level="A2")
    issued_at = datetime.now(UTC)
    offer = evidence.next_article(support_language="vi", now=issued_at)
    assert offer["article_id"] != other_article
    token = offer["recommendation"]
    set_id, answers = _answers(evidence, offer["article_id"])
    _, other_answers = _answers(evidence, other_article)
    version, body, signature = token.split(".")
    flipped = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")
    for operation, target, sheet, presented in (
        ("altered-signature", set_id, answers, f"{version}.{body}.{flipped}"),
        ("altered-payload", set_id, answers, f"{version}.{forged}.{signature}"),
        ("garbage", set_id, answers, "not-a-recommendation"),
        ("another-set", other_set, other_answers, token),
    ):
        result = evidence.submit_attempt(set_id=target, operation_id=operation, answers=sheet,
                                         support_language="vi", recommendation=presented)
        assert result.status == "committed", operation
        assert result.attempt["selection_policy_version"] is None, operation
    # Another account presenting this account's recommendation.
    scope.user = "learner-b"
    foreign = evidence.submit_attempt(set_id=set_id, operation_id="foreign", answers=answers,
                                      support_language="vi", recommendation=token)
    assert foreign.attempt["selection_policy_version"] is None
    scope.user = "learner-a"
    # Past its life.
    expired = evidence.submit_attempt(set_id=set_id, operation_id="expired", answers=answers,
                                      support_language="vi", recommendation=token,
                                      now=issued_at + RECOMMENDATION_TTL + timedelta(minutes=1))
    assert expired.attempt["selection_policy_version"] is None
    # A deployment with another secret cannot have issued it.
    stranger = ReadingEvidenceRepository(engine, user_key_provider=lambda: scope.user,
                                         language_provider=lambda: scope.language,
                                         recommendation_secret="another-deployment")
    elsewhere = stranger.submit_attempt(set_id=set_id, operation_id="elsewhere", answers=answers,
                                        support_language="vi", recommendation=token, now=issued_at)
    assert elsewhere.attempt["selection_policy_version"] is None
    # And the genuine one, in time, still counts.
    genuine = evidence.submit_attempt(set_id=set_id, operation_id="genuine", answers=answers,
                                      support_language="vi", recommendation=token,
                                      now=issued_at + timedelta(hours=1))
    assert genuine.attempt["selection_policy_version"] == policy.SELECTION_POLICY_VERSION


def test_nothing_left_to_offer_is_none(world):
    _, content, evidence, _ = world
    assert evidence.next_article(support_language="vi") is None
    article_id, _ = _approved(content, evidence)
    set_id, answers = _answers(evidence, article_id)
    evidence.submit_attempt(set_id=set_id, operation_id="op", answers=answers, support_language="vi")
    assert evidence.next_article(support_language="vi") is None


# ---- the read contract --------------------------------------------------------------

def test_the_legacy_archive_is_never_read_as_evidence(world):
    engine, content, evidence, scope = world
    uid = stable_uuid("user", scope.user)
    now = _tick()
    # Rows the generated flow wrote before the cutover: the archive's
    # read-only triggers came with the migration, so they are lifted here for
    # the seed alone and restored at once.
    from writing_coach.persistence.reading_evidence_ddl import SQLITE_TRIGGERS

    guards = [sql for sql in SQLITE_TRIGGERS if "read_only_insert" in sql.split("\n", 1)[0]]
    assert len(guards) == 2
    with engine.begin() as connection:
        for sql in guards:
            connection.exec_driver_sql(f"DROP TRIGGER {sql.split()[2]}")
        connection.execute(insert(User).values(id=uid, user_key=scope.user, email="", name="", picture="",
                                               role="user", created_at=now, last_login=None))
        session_id = uuid.uuid4()
        connection.execute(insert(LegacyReadingSession).values(
            id=session_id, user_id=uid, language_code="en", legacy_id=1, created_at=now, target_level="B1",
            topic="", learner_goal="", title="Old", passage="P", questions=[], recycled_words=[],
            generation_mode="generated"))
        connection.execute(insert(LegacyReadingAttempt).values(
            id=uuid.uuid4(), session_id=session_id, legacy_id=1, created_at=now, answers=[0],
            correct_count=1, total=1))
        for sql in guards:
            connection.exec_driver_sql(sql)
    assert evidence.list_evidence() == []
    assert evidence.ability()["attempts"] == 0
    assert evidence.ability()["ability"] == policy.INITIAL_ABILITY
    # Account deletion can still remove the archive row; nothing else writes it.
    with engine.begin() as connection:
        connection.execute(LegacyReadingSession.__table__.delete())
    assert _count(engine, LegacyReadingAttempt) == 0


def test_the_answer_key_is_the_approved_questions_only(world):
    _, content, evidence, _ = world
    article_id, set_id = _approved(content, evidence)
    key = evidence.answer_key(set_id)
    assert len(key) == 3
    assert {entry["correct_index"] for entry in key.values()} == {0}
    assert evidence.answer_key("nope") == {}
