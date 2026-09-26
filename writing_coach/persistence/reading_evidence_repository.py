"""Canonical Reading: comprehension sets, learner attempts, the ability projection.

One flow (D-082): a published corpus article -> an Admin-reviewed comprehension
set -> a learner's attempt -> the ability projection -> the next article. This
repository is the single owner of that evidence. The rules it relies on are in
`docs/project/ADAPTIVE_READING_SCHEMA_PROPOSAL.md`; the ones worth restating
where the code runs:

* **Grounding is checked here, against one exact body.** A set carries the
  SHA-256 of the UTF-8 bytes of `reading_articles.body` as stored - no
  normalization - and every evidence offset indexes that string by code point.
  Generation computes offsets from the body, never from the model; every
  approval, and every serve and submit, re-hashes the body.
* **Lock order, always:** the per-(account, language) advisory lock, then the
  article row, then the set, then the insert. A body edit (`update_article`,
  through `stale_sets_for_body`) takes the article `FOR UPDATE` then updates
  sets, so the same order on both sides is
  what keeps a submit and a body edit from deadlocking.
* **The measurement never gates the evidence.** An attempt commits even when
  the ability policy cannot measure it; the four ability columns are then NULL.
* **Submit is idempotent.** The attempt row is its own receipt, keyed by
  `(user_id, operation_id)`; a retry with the same digest returns the stored
  attempt and moves ability no further.
* **Selection provenance is a server-issued recommendation.** `next_article`
  signs what it recommends (HMAC over account, language, article, set, policy
  version and the moment it was issued). An attempt carries the selection
  policy's version only when its submit presents that signature, unaltered,
  for the same account, language and set, within `RECOMMENDATION_TTL`, and the
  recommendation has not already been spent on an earlier attempt. The
  signature is not bound to the attempt's ordinal, so evidence recorded between
  the recommendation and its submit does not void it; a learner who opens the
  same article some other way presents none and is recorded as their own
  choice. A missing, altered, foreign or expired one records NULL - it never
  refuses the evidence.

PostgreSQL is the runtime. The SQLite path exists for the hermetic suite, where
the advisory lock and `FOR SHARE`/`FOR UPDATE` are no-ops because SQLite
serializes writers on the whole database.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    ReadingAbilityProjection,
    ReadingArticle,
    ReadingAttempt,
    ReadingComprehensionQuestion,
    ReadingComprehensionSet,
    ReadingReviewEvent,
    User,
)
from writing_coach import reading_policy as policy

QUESTION_TYPES = frozenset({
    "main_idea", "detail", "inference", "vocabulary_in_context",
    "cause_effect", "sequence", "authors_purpose", "reference",
})
SPANLESS_TYPES = frozenset({"main_idea", "authors_purpose"})
PUBLISHED = "published"
# The namespace of this repository's advisory locks, so a key can never
# collide with another advisory-lock user: "READ" as a 32-bit integer.
_ADVISORY_NAMESPACE = 0x52454144
RECENT_ATTEMPTS = policy.RECENT_WINDOW
CANDIDATE_POOL = 200
# How long a recommendation stays good for the submit it leads to. Long enough
# to read an article across a day; short enough that an old page is not
# counted as the policy's work.
RECOMMENDATION_TTL = timedelta(days=2)
_RECOMMENDATION_VERSION = "rr1"
# The fallback matches the session signer's, for local single-user mode; a
# deployment passes its own secret.
_LOCAL_SECRET = "local-single-user-mode"

# A learner's Reading rows, in deletion order: the enumeration the
# account-deletion workflow consumes (D-054, `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`
# §5). The archive is the learner's too. The migration carries the same list
# for its proof; `tests/test_reading_evidence_schema_parity.py` keeps the two
# equal, because the application never imports a migration.
ACCOUNT_OWNED: tuple[tuple[str, str], ...] = (
    ("reading_ability_projections", "user_id = :user_id"),
    ("reading_attempts", "user_id = :user_id"),
    ("reading_legacy_attempts",
     "session_id IN (SELECT id FROM reading_legacy_sessions WHERE user_id = :user_id)"),
    ("reading_legacy_sessions", "user_id = :user_id"),
)


class ReadingEvidenceError(ValueError):
    """A refusal with a stable reason code the API turns into a response."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class QuestionInput:
    question_type: str
    prompt: str
    options: Sequence[str]
    correct_index: int
    explanation: str
    evidence_text: str | None = None
    rank: int = 0


@dataclass(frozen=True)
class SubmitResult:
    status: str  # "committed" | "rejected"
    attempt: dict[str, Any] | None = None
    reason: str = ""
    replayed: bool = False


def body_sha256(body: str) -> str:
    """The grounding anchor: SHA-256 of the UTF-8 bytes of the body as stored."""
    return hashlib.sha256(str(body).encode("utf-8")).hexdigest()


def locate_evidence(body: str, evidence: str) -> tuple[int, int] | None:
    """Code-point offsets of `evidence` in `body`, or None when it is not there.

    The first occurrence: a span that occurs more than once is still grounded,
    and the reader highlights the first place it appears.
    """
    if not evidence:
        return None
    start = body.find(evidence)
    return None if start < 0 else (start, start + len(evidence))


def stale_sets_for_body(connection: Any, article_id: uuid.UUID, new_body: str, *, actor: str,
                        now: datetime) -> list[str]:
    """Inside a body edit's own transaction, after it has taken the article
    `FOR UPDATE`: every approved set whose anchor no longer matches the new
    body becomes `stale`, with a review event. Visible, never silent - and
    still correct if this were ever skipped, because serving and submitting
    re-hash the body."""
    anchor = body_sha256(new_body)
    stale = connection.execute(
        select(ReadingComprehensionSet.id).where(
            ReadingComprehensionSet.article_id == article_id,
            ReadingComprehensionSet.status == "approved",
            ReadingComprehensionSet.article_body_sha256 != anchor,
        )
    ).scalars().all()
    for set_id in stale:
        connection.execute(update(ReadingComprehensionSet)
                           .where(ReadingComprehensionSet.id == set_id)
                           .values(status="stale", updated_at=now))
        connection.execute(insert(ReadingReviewEvent).values(
            id=uuid.uuid4(), article_id=article_id, actor=actor, action="comprehension_set_stale",
            reason="the article's text changed", changes_json={"set_id": str(set_id)}, created_at=now,
        ))
    return [str(set_id) for set_id in stale]


def _require_published(article: Any) -> None:
    """A set is built and approved for a published corpus article only (D-082:
    publish, then the set). A candidate has not been reviewed as content yet,
    so questions about it would be reviewed before the text they ask about."""
    if article.status != PUBLISHED:
        raise ReadingEvidenceError(
            "reading_article_not_published",
            "Publish the article first: a comprehension set is built for a published article only.",
        )


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text_value: str) -> bytes:
    return base64.urlsafe_b64decode(text_value + "=" * (-len(text_value) % 4))


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(UTC)


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _maybe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return _uuid(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


class ReadingEvidenceRepository:
    def __init__(
        self,
        engine: Engine,
        *,
        user_key_provider: Callable[[], str] = current_user_key,
        language_provider: Callable[[], str] = current_language_code,
        recommendation_secret: str = "",
    ) -> None:
        self.engine = engine
        self._user_key_provider = user_key_provider
        self._language_provider = language_provider
        # Domain-separated from every other use of the same secret.
        self._recommendation_key = hashlib.sha256(
            b"orena.reading.recommendation\x00" + (recommendation_secret or _LOCAL_SECRET).encode("utf-8")
        ).digest()

    # -- plumbing --------------------------------------------------------

    @property
    def _postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    def _scope(self) -> tuple[uuid.UUID, str, str]:
        key = self._user_key_provider()
        return stable_uuid("user", key), self._language_provider().casefold(), key

    def _for(self, statement: Any, mode: str) -> Any:
        """`FOR SHARE` / `FOR UPDATE` on PostgreSQL; SQLite serializes writers."""
        if not self._postgres or mode not in {"share", "update"}:
            return statement
        return statement.with_for_update(read=(mode == "share"))

    def _record_event(self, connection: Any, *, article_id: uuid.UUID, actor: str, action: str,
                      reason: str, changes: Mapping[str, Any], now: datetime) -> None:
        connection.execute(insert(ReadingReviewEvent).values(
            id=uuid.uuid4(), article_id=article_id, actor=actor, action=action,
            reason=reason, changes_json=dict(changes), created_at=now,
        ))

    def _article(self, connection: Any, article_id: uuid.UUID, mode: str) -> Any:
        return connection.execute(self._for(
            select(ReadingArticle.id, ReadingArticle.body, ReadingArticle.language,
                   ReadingArticle.status, ReadingArticle.effective_level, ReadingArticle.title,
                   ReadingArticle.content_kind, ReadingArticle.published_at)
            .where(ReadingArticle.id == article_id), mode)).first()

    def _set_row(self, connection: Any, set_id: uuid.UUID, mode: str | None = None) -> Any:
        statement = select(ReadingComprehensionSet).where(ReadingComprehensionSet.id == set_id)
        if mode:
            statement = self._for(statement, mode)
        return connection.execute(statement).first()

    def _questions(self, connection: Any, set_id: uuid.UUID, *, approved_only: bool = False) -> list[Any]:
        statement = select(ReadingComprehensionQuestion).where(ReadingComprehensionQuestion.set_id == set_id)
        if approved_only:
            statement = statement.where(ReadingComprehensionQuestion.admin_approved.is_(True))
        return list(connection.execute(statement.order_by(
            ReadingComprehensionQuestion.rank, ReadingComprehensionQuestion.id)).all())

    @staticmethod
    def _question_payload(row: Any, *, with_answer: bool) -> dict[str, Any]:
        payload = {
            "id": str(row.id),
            "rank": row.rank,
            "question_type": row.question_type,
            "prompt": row.prompt,
            "options": list(row.options_json or []),
        }
        if with_answer:
            payload |= {
                "correct_index": row.correct_index,
                "explanation": row.explanation,
                "evidence_text": row.evidence_text,
                "evidence_start": row.evidence_start,
                "evidence_end": row.evidence_end,
                "machine_suggested": bool(row.machine_suggested),
                "admin_approved": bool(row.admin_approved),
                "admin_rejected": bool(row.admin_rejected),
            }
        return payload

    def _set_payload(self, connection: Any, row: Any, *, with_answers: bool,
                     approved_only: bool = False, body: str | None = None) -> dict[str, Any]:
        questions = self._questions(connection, row.id, approved_only=approved_only)
        payload = {
            "id": str(row.id),
            "article_id": str(row.article_id),
            "language_code": row.language_code,
            "support_language": row.support_language,
            "status": row.status,
            "generator_version": row.generator_version,
            "model": row.model,
            "reviewed_by": row.reviewed_by if with_answers else None,
            "reviewed_at": _iso(row.reviewed_at),
            "created_at": _iso(row.created_at),
            "questions": [self._question_payload(item, with_answer=with_answers) for item in questions],
        }
        if with_answers:
            payload |= {
                "article_body_sha256": row.article_body_sha256,
                "validation": dict(row.validation_json or {}),
                "review_reason": row.review_reason,
            }
        if body is not None:
            payload["anchored"] = body_sha256(body) == row.article_body_sha256
        return payload

    # -- sets: the Admin side --------------------------------------------

    def create_set(
        self,
        article_id: str,
        *,
        support_language: str,
        generator_version: str,
        model: str,
        questions: Sequence[QuestionInput],
        validation: Mapping[str, Any],
        actor: str,
        expected_body_sha256: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """A draft set, grounded in the article's body as it is now.

        `expected_body_sha256` is the hash of the body the questions were
        written from, taken before the AI was asked. Under the article's lock
        the body must still hash to it: an edit that landed while the model was
        writing is refused (`reading_article_changed`), never anchored to text
        the questions were not written about.

        Offsets are computed from the body; a question whose evidence is not in
        the body is refused before anything is written, so an ungrounded draft
        never exists.
        """
        moment = _now(now)
        article_uuid = _maybe_uuid(article_id)
        if article_uuid is None:
            raise ReadingEvidenceError("reading_article_not_found", "That article is not in the catalog.")
        support = str(support_language or "").strip().casefold()
        if not support:
            raise ReadingEvidenceError("reading_support_language_required", "A set needs its support language.")
        if not questions:
            raise ReadingEvidenceError("reading_set_empty", "A set needs at least one question.")
        with self.engine.begin() as connection:
            article = self._article(connection, article_uuid, "update")
            if article is None:
                raise ReadingEvidenceError("reading_article_not_found", "That article is not in the catalog.")
            _require_published(article)
            if body_sha256(article.body) != str(expected_body_sha256 or ""):
                raise ReadingEvidenceError(
                    "reading_article_changed",
                    "The article changed while its questions were being written. Generate them again.",
                )
            rows = self._grounded_rows(article.body, questions)
            set_id = uuid.uuid4()
            connection.execute(insert(ReadingComprehensionSet).values(
                id=set_id, article_id=article_uuid, language_code=article.language,
                support_language=support, article_body_sha256=body_sha256(article.body),
                status="draft", generator_version=generator_version, model=model or "",
                validation_json=dict(validation), reviewed_by="", review_reason="",
                created_at=moment, updated_at=moment,
            ))
            for rank, row in enumerate(rows):
                connection.execute(insert(ReadingComprehensionQuestion).values(
                    id=uuid.uuid4(), set_id=set_id, rank=rank, created_at=moment, updated_at=moment,
                    machine_suggested=True, admin_approved=False, admin_rejected=False, **row,
                ))
            self._record_event(connection, article_id=article_uuid, actor=actor,
                               action="comprehension_set_created", reason="",
                               changes={"set_id": str(set_id), "questions": len(rows),
                                        "support_language": support}, now=moment)
            return self._set_payload(connection, self._set_row(connection, set_id), with_answers=True,
                                     body=article.body)

    @staticmethod
    def _grounded_rows(body: str, questions: Sequence[QuestionInput]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(sorted(questions, key=lambda q: q.rank)):
            qtype = str(item.question_type or "").strip()
            if qtype not in QUESTION_TYPES:
                raise ReadingEvidenceError("reading_question_type", f"Question {index + 1}: unknown type {qtype!r}.")
            options = [str(option).strip() for option in item.options]
            if not 2 <= len(options) <= 6 or any(not option for option in options):
                raise ReadingEvidenceError("reading_question_options", f"Question {index + 1}: 2-6 non-empty options.")
            if len({option.casefold() for option in options}) != len(options):
                raise ReadingEvidenceError("reading_question_options", f"Question {index + 1}: options repeat.")
            if not 0 <= int(item.correct_index) < len(options):
                raise ReadingEvidenceError("reading_question_answer", f"Question {index + 1}: the answer is not an option.")
            prompt, explanation = str(item.prompt or "").strip(), str(item.explanation or "").strip()
            if not prompt or not explanation:
                raise ReadingEvidenceError("reading_question_text", f"Question {index + 1}: prompt and explanation.")
            evidence = (item.evidence_text or "").strip() or None
            span = locate_evidence(body, evidence) if evidence else None
            if evidence and span is None:
                raise ReadingEvidenceError(
                    "reading_evidence_not_grounded",
                    f"Question {index + 1}: its evidence is not in the passage.",
                )
            if evidence is None and qtype not in SPANLESS_TYPES:
                raise ReadingEvidenceError(
                    "reading_evidence_required", f"Question {index + 1}: a {qtype} question must cite the passage."
                )
            rows.append({
                "question_type": qtype, "prompt": prompt, "options_json": options,
                "correct_index": int(item.correct_index), "explanation": explanation,
                "evidence_text": evidence, "evidence_start": span[0] if span else None,
                "evidence_end": span[1] if span else None,
            })
        return rows

    def list_sets(self, article_id: str) -> list[dict[str, Any]]:
        article_uuid = _maybe_uuid(article_id)
        if article_uuid is None:
            return []
        with self.engine.connect() as connection:
            article = self._article(connection, article_uuid, "none")
            if article is None:
                return []
            rows = connection.execute(
                select(ReadingComprehensionSet).where(ReadingComprehensionSet.article_id == article_uuid)
                .order_by(ReadingComprehensionSet.created_at.desc(), ReadingComprehensionSet.id)
            ).all()
            attempts = dict(connection.execute(
                select(ReadingAttempt.set_id, func.count()).where(
                    ReadingAttempt.set_id.in_([row.id for row in rows])).group_by(ReadingAttempt.set_id)
            ).all()) if rows else {}
            payloads = []
            for row in rows:
                payload = self._set_payload(connection, row, with_answers=True, body=article.body)
                payload["attempts"] = int(attempts.get(row.id, 0))
                payloads.append(payload)
            return payloads

    def get_set(self, set_id: str) -> dict[str, Any] | None:
        set_uuid = _maybe_uuid(set_id)
        if set_uuid is None:
            return None
        with self.engine.connect() as connection:
            row = self._set_row(connection, set_uuid)
            if row is None:
                return None
            article = self._article(connection, row.article_id, "none")
            return self._set_payload(connection, row, with_answers=True, body=article.body if article else None)

    def decide_question(self, set_id: str, question_id: str, *, decision: str, actor: str,
                        now: datetime | None = None) -> dict[str, Any] | None:
        """Approve, reject or undecide one question while its set is undecided.
        A decided set is frozen by the database; that refusal becomes
        `reading_set_frozen`."""
        flags = {"approve": (True, False), "reject": (False, True), "undecided": (False, False)}
        if decision not in flags:
            raise ReadingEvidenceError("reading_invalid_decision", "Decide approve, reject or undecided.")
        set_uuid, question_uuid = _maybe_uuid(set_id), _maybe_uuid(question_id)
        if set_uuid is None or question_uuid is None:
            return None
        moment = _now(now)
        approved, rejected = flags[decision]
        try:
            with self.engine.begin() as connection:
                row = self._set_row(connection, set_uuid, "update")
                if row is None:
                    return None
                changed = connection.execute(
                    update(ReadingComprehensionQuestion)
                    .where(ReadingComprehensionQuestion.id == question_uuid,
                           ReadingComprehensionQuestion.set_id == set_uuid)
                    .values(admin_approved=approved, admin_rejected=rejected, updated_at=moment)
                ).rowcount
                if not changed:
                    return None
                self._record_event(connection, article_id=row.article_id, actor=actor,
                                   action=f"comprehension_question_{decision}", reason="",
                                   changes={"set_id": str(set_uuid), "question_id": str(question_uuid)},
                                   now=moment)
        except IntegrityError as exc:
            raise ReadingEvidenceError("reading_set_frozen", "A decided set is frozen: build a new set.") from exc
        return self.get_set(set_id)

    def transition(self, set_id: str, status: str, *, actor: str, reason: str = "",
                   now: datetime | None = None) -> dict[str, Any] | None:
        """Move a set along its review lifecycle.

        Every entry into `approved` - from `needs_review`, `stale` or
        `archived` - runs the grounding check under the article's row lock:
        the body's hash must equal the set's anchor and every span must still
        read its evidence. The database refuses any transition that is not a
        review transition, and a decision that does not record a new moment.
        """
        set_uuid = _maybe_uuid(set_id)
        if set_uuid is None:
            return None
        target = str(status or "").strip()
        moment = _now(now)
        try:
            with self.engine.begin() as connection:
                current = self._set_row(connection, set_uuid)
                if current is None:
                    return None
                # Lock order: the article, then the set.
                article = self._article(connection, current.article_id, "update")
                row = self._set_row(connection, set_uuid, "update")
                values: dict[str, Any] = {"status": target, "updated_at": moment}
                if target in {"approved", "rejected"}:
                    if not str(actor or "").strip():
                        raise ReadingEvidenceError("reading_reviewer_required", "A decision names its reviewer.")
                    values |= {"reviewed_by": actor, "reviewed_at": moment, "review_reason": reason}
                if target == "approved":
                    if article is not None:
                        _require_published(article)
                    self._check_grounding(connection, row, article)
                    if row.status == "needs_review":
                        self._renumber(connection, set_uuid, moment)
                connection.execute(update(ReadingComprehensionSet)
                                   .where(ReadingComprehensionSet.id == set_uuid).values(**values))
                self._record_event(connection, article_id=row.article_id, actor=actor,
                                   action=f"comprehension_set_{target}", reason=reason,
                                   changes={"set_id": str(set_uuid), "from": row.status, "to": target},
                                   now=moment)
        except IntegrityError as exc:
            raise ReadingEvidenceError(
                "reading_set_transition_refused",
                "That change is not allowed for this set: it may be decided already, another set may be "
                "approved for this article and language, or an approval needs an approved question and "
                "no undecided one.",
            ) from exc
        return self.get_set(set_id)

    def _check_grounding(self, connection: Any, row: Any, article: Any) -> None:
        if article is None or body_sha256(article.body) != row.article_body_sha256:
            raise ReadingEvidenceError(
                "reading_set_stale",
                "The article's text has changed since this set was built. Build a new set.",
            )
        for question in self._questions(connection, row.id):
            if question.evidence_text is None:
                continue
            if article.body[question.evidence_start:question.evidence_end] != question.evidence_text:
                raise ReadingEvidenceError("reading_evidence_not_grounded", "A question's evidence moved.")

    def _renumber(self, connection: Any, set_id: uuid.UUID, moment: datetime) -> None:
        """Contiguous ranks before approval freezes them."""
        for rank, question in enumerate(self._questions(connection, set_id)):
            if question.rank != rank:
                connection.execute(update(ReadingComprehensionQuestion)
                                   .where(ReadingComprehensionQuestion.id == question.id)
                                   .values(rank=rank, updated_at=moment))

    def discard_set(self, set_id: str, *, actor: str, now: datetime | None = None) -> bool:
        """Delete a set nobody ever served (draft, needs_review, rejected).
        One that reached learners is refused by the database."""
        set_uuid = _maybe_uuid(set_id)
        if set_uuid is None:
            return False
        moment = _now(now)
        try:
            with self.engine.begin() as connection:
                row = self._set_row(connection, set_uuid, "update")
                if row is None:
                    return False
                self._record_event(connection, article_id=row.article_id, actor=actor,
                                   action="comprehension_set_discarded", reason="",
                                   changes={"set_id": str(set_uuid), "status": row.status}, now=moment)
                connection.execute(delete(ReadingComprehensionSet).where(ReadingComprehensionSet.id == set_uuid))
        except IntegrityError as exc:
            raise ReadingEvidenceError(
                "reading_set_undeletable", "A set that reached learners is archived, never deleted."
            ) from exc
        return True

    # -- the learner side ------------------------------------------------

    def served_set(self, article_id: str, *, support_language: str) -> dict[str, Any] | None:
        """The approved set a learner meets for a published article, in their
        support language, still anchored - without its answers. None means the
        article is Free Reading for this learner."""
        article_uuid = _maybe_uuid(article_id)
        if article_uuid is None:
            return None
        with self.engine.connect() as connection:
            article = self._article(connection, article_uuid, "none")
            if article is None or article.status != PUBLISHED:
                return None
            row = connection.execute(select(ReadingComprehensionSet).where(
                ReadingComprehensionSet.article_id == article_uuid,
                ReadingComprehensionSet.support_language == str(support_language).casefold(),
                ReadingComprehensionSet.status == "approved",
            )).first()
            if row is None or body_sha256(article.body) != row.article_body_sha256:
                return None
            payload = self._set_payload(connection, row, with_answers=False, approved_only=True)
            payload["article"] = {"id": str(article.id), "title": article.title,
                                  "level": article.effective_level, "content_kind": article.content_kind}
            return payload

    def grade_question(self, set_id: str, question_id: str, selected_index: int,
                       *, support_language: str) -> dict[str, Any] | None:
        """Return feedback for one approved question without writing an attempt.

        The set must still be the published article's approved, grounded set in
        the learner's support language. The complete answer sheet remains the
        only canonical evidence write.
        """
        set_uuid, question_uuid = _maybe_uuid(set_id), _maybe_uuid(question_id)
        if set_uuid is None or question_uuid is None:
            return None
        with self.engine.connect() as connection:
            row = self._set_row(connection, set_uuid)
            if row is None or row.status != "approved" or row.support_language != str(support_language).casefold():
                return None
            article = self._article(connection, row.article_id, "none")
            if article is None or article.status != PUBLISHED or body_sha256(article.body) != row.article_body_sha256:
                return None
            question = next((item for item in self._questions(connection, set_uuid, approved_only=True)
                             if item.id == question_uuid), None)
            if question is None:
                return None
            if selected_index < 0 or selected_index >= len(question.options_json):
                raise ReadingEvidenceError("reading_question_choice", "That choice is not in the question.")
            return {
                "question_id": str(question.id), "selected_index": selected_index,
                "correct": selected_index == question.correct_index,
                "correct_index": question.correct_index,
                "explanation": question.explanation,
                "evidence_fragment": question.evidence_text or "",
            }

    def answer_key(self, set_id: str) -> dict[str, dict[str, Any]]:
        """The approved questions' answers, by question id - shown to a learner
        after their complete attempt on the set is saved. Per-question feedback
        uses ``grade_question`` and returns only the question just answered."""
        set_uuid = _maybe_uuid(set_id)
        if set_uuid is None:
            return {}
        with self.engine.connect() as connection:
            return {
                str(row.id): {"correct_index": row.correct_index, "explanation": row.explanation,
                              "evidence_text": row.evidence_text}
                for row in self._questions(connection, set_uuid, approved_only=True)
            }

    def submit_attempt(
        self,
        *,
        set_id: str,
        operation_id: str,
        answers: Mapping[str, int],
        support_language: str,
        recommendation: str | None = None,
        now: datetime | None = None,
    ) -> SubmitResult:
        """The idempotent submit. See the module docstring for the lock order.
        `recommendation` is what `next_article` issued, passed back untouched;
        whether it counts is the server's to verify (`_recommended_version`)."""
        operation = str(operation_id or "").strip()
        if not operation or len(operation) > 120:
            return SubmitResult("rejected", reason="operation_id_required")
        set_uuid = _maybe_uuid(set_id)
        if set_uuid is None:
            return SubmitResult("rejected", reason="set_not_found")
        try:
            selected = {str(key): int(value) for key, value in dict(answers).items()}
        except (TypeError, ValueError):
            return SubmitResult("rejected", reason="answers_invalid")
        digest = policy.request_digest(str(set_uuid), selected)
        uid, language, user_key = self._scope()
        try:
            return self._submit(uid, user_key, language, set_uuid, operation, digest, selected,
                                str(support_language or "").casefold(), recommendation, _now(now))
        except IntegrityError:
            # A raced duplicate committed first: no success receipt was written
            # here, and the committed one is the answer.
            with self.engine.connect() as connection:
                replay = self._receipt(connection, uid, operation)
            if replay is not None:
                return self._replay(replay, digest)
            raise

    def _receipt(self, connection: Any, uid: uuid.UUID, operation: str) -> Any:
        return connection.execute(select(ReadingAttempt).where(
            ReadingAttempt.user_id == uid, ReadingAttempt.operation_id == operation)).first()

    def _replay(self, row: Any, digest: str) -> SubmitResult:
        if row.request_digest != digest:
            return SubmitResult("rejected", reason="operation_reused")
        return SubmitResult("committed", attempt=self._attempt_payload(row), replayed=True)

    def _ensure_user(self, connection: Any, uid: uuid.UUID, user_key: str, moment: datetime) -> None:
        if connection.execute(select(User.id).where(User.id == uid)).first() is not None:
            return
        connection.execute(insert(User).values(
            id=uid, user_key=user_key, email="", name="", picture="", role="user",
            created_at=moment, last_login=None,
        ))

    def _submit(self, uid: uuid.UUID, user_key: str, language: str, set_uuid: uuid.UUID, operation: str,
                digest: str, selected: dict[str, int], support: str, recommendation: str | None,
                moment: datetime) -> SubmitResult:
        with self.engine.begin() as connection:
            existing = self._receipt(connection, uid, operation)
            if existing is not None:
                return self._replay(existing, digest)
            # 1. The per-(account, language) lock. Not the projection row: that
            #    would make evidence depend on the projection existing.
            if self._postgres:
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:key))"),
                    {"namespace": _ADVISORY_NAMESPACE, "key": f"{uid}:{language}"},
                )
                existing = self._receipt(connection, uid, operation)
                if existing is not None:
                    return self._replay(existing, digest)
            # 2. The set, to learn its article; then the article, then the set,
            #    both FOR SHARE - the order a body edit also takes.
            probe = self._set_row(connection, set_uuid)
            if probe is None:
                return SubmitResult("rejected", reason="set_not_found")
            article = self._article(connection, probe.article_id, "share")
            row = self._set_row(connection, set_uuid, "share")
            if article is None or article.status != PUBLISHED:
                return SubmitResult("rejected", reason="article_not_published")
            if row.status == "stale":
                return SubmitResult("rejected", reason="set_stale")
            if row.status != "approved":
                return SubmitResult("rejected", reason="set_not_approved")
            if row.language_code != language:
                return SubmitResult("rejected", reason="language_mismatch")
            if support and row.support_language != support:
                return SubmitResult("rejected", reason="support_language_mismatch")
            if body_sha256(article.body) != row.article_body_sha256:
                return SubmitResult("rejected", reason="set_stale")
            questions = [
                {"id": str(item.id), "question_type": item.question_type,
                 "correct_index": item.correct_index, "options": item.options_json}
                for item in self._questions(connection, set_uuid, approved_only=True)
            ]
            if set(selected) != {item["id"] for item in questions}:
                return SubmitResult("rejected", reason="answers_do_not_match_questions")
            if any(not 0 <= selected[item["id"]] < len(item["options"]) for item in questions):
                return SubmitResult("rejected", reason="answer_out_of_range")
            judged = policy.judge(questions, selected)
            correct = sum(1 for item in judged if item.correct)
            self._ensure_user(connection, uid, user_key, moment)
            ordinal = int(connection.execute(select(func.coalesce(func.max(ReadingAttempt.ordinal), 0)).where(
                ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)).scalar_one()) + 1
            level = str(article.effective_level or "").strip() or "unknown"
            # 3. Where the article came from: the policy's, only on a
            #    recommendation this server issued for this account and set.
            selection_policy_version = self._recommended_version(
                connection, recommendation, uid=uid, language=language, set_uuid=set_uuid, moment=moment)
            # 4. The measurement, best-effort: a failure leaves the evidence
            #    unmeasured and the projection behind its checkpoint.
            measurement = self._measure(connection, uid, language, ordinal, level, judged, moment)
            attempt_id = uuid.uuid4()
            connection.execute(insert(ReadingAttempt).values(
                id=attempt_id, user_id=uid, language_code=language, set_id=set_uuid, ordinal=ordinal,
                operation_id=operation, request_digest=digest, evaluator_version=policy.EVALUATOR_VERSION,
                passage_level=level,
                ability_policy_version=measurement.policy_version if measurement else None,
                passage_difficulty=measurement.passage_difficulty if measurement else None,
                ability_before=measurement.ability_before if measurement else None,
                ability_after=measurement.ability_after if measurement else None,
                selection_policy_version=selection_policy_version,
                answers=[item.as_answer() for item in judged],
                correct_count=correct, total=len(judged), created_at=moment,
            ))
            saved = connection.execute(select(ReadingAttempt).where(ReadingAttempt.id == attempt_id)).first()
            return SubmitResult("committed", attempt=self._attempt_payload(saved))

    def _measure(self, connection: Any, uid: uuid.UUID, language: str, ordinal: int, level: str,
                 judged: list[policy.Judged], moment: datetime) -> policy.Measurement | None:
        """Bring the projection up to date and apply this attempt - or, on any
        failure, leave the projection behind its checkpoint and return None so
        the attempt commits unmeasured. On PostgreSQL a savepoint contains the
        failure, since an error there would abort the whole transaction; on
        SQLite the projection's own statements are the only writes in it."""
        savepoint = connection.begin_nested() if self._postgres else None
        try:
            state = self._state(connection, uid, language, through=ordinal - 1)
            measurement = policy.apply(state, ordinal=ordinal, passage_level=level, judged=judged)
            self._save_state(connection, uid, language, state, moment)
        except Exception:  # noqa: BLE001 - the evidence must not depend on the projection
            if savepoint is not None:
                savepoint.rollback()
            return None
        if savepoint is not None:
            savepoint.commit()
        return measurement

    def _attempt_payload(self, row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "set_id": str(row.set_id),
            "language_code": row.language_code,
            "ordinal": row.ordinal,
            "operation_id": row.operation_id,
            "correct_count": row.correct_count,
            "total": row.total,
            "answers": list(row.answers or []),
            "passage_level": row.passage_level,
            "evaluator_version": row.evaluator_version,
            "ability_policy_version": row.ability_policy_version,
            "ability_before": row.ability_before,
            "ability_after": row.ability_after,
            "selection_policy_version": row.selection_policy_version,
            "created_at": _iso(row.created_at),
        }

    # -- the projection --------------------------------------------------

    def _state(self, connection: Any, uid: uuid.UUID, language: str, *, through: int) -> policy.AbilityState:
        """The projection under the current policy, caught up to `through`.

        Uses the stored projection when its checkpoint is exactly there;
        otherwise replays every attempt in ordinal order - the definition of
        ability, of which the stored row is only a cache.
        """
        stored = connection.execute(select(ReadingAbilityProjection).where(
            ReadingAbilityProjection.user_id == uid,
            ReadingAbilityProjection.language_code == language,
            ReadingAbilityProjection.policy_version == policy.ABILITY_POLICY_VERSION,
        )).first()
        if stored is not None and stored.consumed_through_ordinal == through:
            return policy.AbilityState(
                ability=float(stored.ability),
                consumed_through_ordinal=stored.consumed_through_ordinal,
                by_question_type={key: list(value) for key, value in dict(stored.by_question_type_json or {}).items()},
            )
        return self._replay_state(connection, uid, language, through=through)

    def _replay_state(self, connection: Any, uid: uuid.UUID, language: str, *, through: int) -> policy.AbilityState:
        state = policy.AbilityState()
        attempts = connection.execute(
            select(ReadingAttempt.ordinal, ReadingAttempt.passage_level, ReadingAttempt.answers)
            .where(ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language,
                   ReadingAttempt.ordinal <= through)
            .order_by(ReadingAttempt.ordinal)
        ).all()
        question_ids = {
            _maybe_uuid(answer.get("question_id"))
            for row in attempts for answer in (row.answers or []) if isinstance(answer, dict)
        } - {None}
        types = dict(connection.execute(
            select(ReadingComprehensionQuestion.id, ReadingComprehensionQuestion.question_type)
            .where(ReadingComprehensionQuestion.id.in_(question_ids))
        ).all()) if question_ids else {}
        for row in attempts:
            judged = [
                policy.Judged(
                    question_id=str(answer.get("question_id")),
                    question_type=types.get(_maybe_uuid(answer.get("question_id")), "unknown"),
                    selected_index=int(answer.get("selected_index", -1)),
                    correct=bool(answer.get("correct")),
                )
                for answer in (row.answers or []) if isinstance(answer, dict)
            ]
            # A replay tolerates a gap: the checkpoint follows the ordinals
            # that exist, so a deleted attempt cannot wedge the projection.
            state.consumed_through_ordinal = row.ordinal - 1
            policy.apply(state, ordinal=row.ordinal, passage_level=row.passage_level, judged=judged)
        state.consumed_through_ordinal = max(state.consumed_through_ordinal, 0)
        return state

    def _save_state(self, connection: Any, uid: uuid.UUID, language: str, state: policy.AbilityState,
                    moment: datetime) -> None:
        payload: dict[str, Any] = {key: list(value) for key, value in state.by_question_type.items()}
        values = {"ability": state.ability, "consumed_through_ordinal": state.consumed_through_ordinal,
                  "by_question_type_json": payload, "updated_at": moment}
        changed = connection.execute(update(ReadingAbilityProjection).where(
            ReadingAbilityProjection.user_id == uid,
            ReadingAbilityProjection.language_code == language,
            ReadingAbilityProjection.policy_version == policy.ABILITY_POLICY_VERSION,
        ).values(**values)).rowcount
        if not changed:
            connection.execute(insert(ReadingAbilityProjection).values(
                id=uuid.uuid4(), user_id=uid, language_code=language,
                policy_version=policy.ABILITY_POLICY_VERSION, **values))

    def ability(self) -> dict[str, Any]:
        """The learner's ability under the current policy, rebuilt when the
        stored projection is behind the attempts."""
        uid, language, _ = self._scope()
        with self.engine.begin() as connection:
            latest = int(connection.execute(select(func.coalesce(func.max(ReadingAttempt.ordinal), 0)).where(
                ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)).scalar_one())
            state = self._state(connection, uid, language, through=latest)
            if latest:
                self._save_state(connection, uid, language, state, _now())
            return {
                # Whose projection this is - the account the attempts are
                # recorded under, so an operator can find exactly this
                # account's evidence in Admin Activity.
                "account_id": str(uid),
                "language_code": language,
                "policy_version": policy.ABILITY_POLICY_VERSION,
                "ability": round(state.ability, 6),
                "attempts": state.consumed_through_ordinal,
                "by_question_type": {key: list(value) for key, value in state.by_question_type.items()},
                "weak_types": list(policy.weak_types(state.by_question_type)),
            }

    def rebuild_projection(self) -> dict[str, Any]:
        """Discard the stored projection and rebuild it from the attempts."""
        uid, language, _ = self._scope()
        with self.engine.begin() as connection:
            connection.execute(delete(ReadingAbilityProjection).where(
                ReadingAbilityProjection.user_id == uid, ReadingAbilityProjection.language_code == language))
        return self.ability()

    # -- choosing the next article --------------------------------------

    def _choose(self, connection: Any, uid: uuid.UUID, language: str, support: str,
                state: policy.AbilityState, next_ordinal: int) -> policy.Choice | None:
        """The selection policy over this learner's evidence as `connection`
        sees it. The one place a choice is made: `next_article` offers it, and
        a submit replays it to decide its own provenance."""
        recent = connection.execute(
            select(ReadingAttempt.correct_count, ReadingAttempt.total)
            .where(ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)
            .order_by(ReadingAttempt.ordinal.desc()).limit(RECENT_ATTEMPTS)
        ).all()
        attempted = connection.execute(
            select(ReadingComprehensionSet.article_id).join(
                ReadingAttempt, ReadingAttempt.set_id == ReadingComprehensionSet.id)
            .where(ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)
        ).scalars().all()
        pool = connection.execute(
            select(ReadingArticle.id, ReadingArticle.effective_level, ReadingArticle.published_at,
                   ReadingComprehensionSet.id.label("set_id"))
            .join(ReadingComprehensionSet, ReadingComprehensionSet.article_id == ReadingArticle.id)
            .where(ReadingArticle.status == PUBLISHED, ReadingArticle.language == language,
                   ReadingComprehensionSet.status == "approved",
                   ReadingComprehensionSet.support_language == support)
            .order_by(ReadingArticle.published_at.desc(), ReadingArticle.id)
            .limit(CANDIDATE_POOL)
        ).all()
        set_ids = [row.set_id for row in pool]
        types: dict[Any, set[str]] = {}
        if set_ids:
            for set_id, qtype in connection.execute(
                select(ReadingComprehensionQuestion.set_id, ReadingComprehensionQuestion.question_type)
                .where(ReadingComprehensionQuestion.set_id.in_(set_ids),
                       ReadingComprehensionQuestion.admin_approved.is_(True))
            ).all():
                types.setdefault(set_id, set()).add(qtype)
        return policy.choose(
            ability=float(state.ability),
            by_question_type=state.by_question_type,
            recent_accuracy=[row.correct_count / row.total for row in recent if row.total],
            next_ordinal=next_ordinal,
            candidates=[
                policy.Candidate(article_id=str(row.id), set_id=str(row.set_id), level=row.effective_level,
                                 published_at=_iso(row.published_at) or "",
                                 question_types=frozenset(types.get(row.set_id, set())))
                for row in pool
            ],
            attempted_article_ids=[str(value) for value in attempted],
        )

    def _sign(self, payload: Mapping[str, Any]) -> str:
        body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64(hmac.new(self._recommendation_key, f"{_RECOMMENDATION_VERSION}.{body}".encode("ascii"),
                                  hashlib.sha256).digest())
        return f"{_RECOMMENDATION_VERSION}.{body}.{signature}"

    def _recommendation(self, token: str | None) -> dict[str, Any] | None:
        """The payload of a recommendation this server signed, or None."""
        parts = str(token or "").split(".")
        if len(parts) != 3 or parts[0] != _RECOMMENDATION_VERSION or len(token or "") > 1024:
            return None
        expected = _b64(hmac.new(self._recommendation_key, f"{parts[0]}.{parts[1]}".encode("ascii"),
                                 hashlib.sha256).digest())
        if not hmac.compare_digest(expected, parts[2]):
            return None
        try:
            payload = json.loads(_unb64(parts[1]))
        except (ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _recommended_version(self, connection: Any, token: str | None, *, uid: uuid.UUID, language: str,
                             set_uuid: uuid.UUID, moment: datetime) -> str | None:
        """The selection policy's version when `token` is a live recommendation
        of this set for this account and language that no earlier attempt has
        spent; otherwise None - "the learner chose it"."""
        payload = self._recommendation(token)
        if payload is None:
            return None
        if (payload.get("u"), payload.get("l"), payload.get("s")) != (str(uid), language, str(set_uuid)):
            return None
        version = payload.get("p")
        if not isinstance(version, str) or not version.strip():
            return None
        try:
            issued = datetime.fromtimestamp(int(payload.get("t")), UTC)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
        if not (issued - timedelta(minutes=5) <= moment <= issued + RECOMMENDATION_TTL):
            return None
        spent = connection.execute(select(ReadingAttempt.id).where(
            ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language,
            ReadingAttempt.set_id == set_uuid, ReadingAttempt.selection_policy_version.is_not(None),
        ).limit(1)).first()
        return None if spent is not None else version

    def next_article(self, *, support_language: str, now: datetime | None = None) -> dict[str, Any] | None:
        """The policy's choice and a signed recommendation of it: the one
        thing a submit can present to be recorded as the policy's work."""
        uid, language, _ = self._scope()
        support = str(support_language or "").casefold()
        # Brings the stored projection up to date, so the state below is read
        # from its checkpoint rather than replayed.
        ability = self.ability()
        with self.engine.connect() as connection:
            latest = int(connection.execute(select(func.coalesce(func.max(ReadingAttempt.ordinal), 0)).where(
                ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)).scalar_one())
            state = self._state(connection, uid, language, through=latest)
            choice = self._choose(connection, uid, language, support, state, latest + 1)
        if choice is None:
            return None
        # "Approved" implies "anchored" because every body edit stales its sets
        # in the same transaction; the one chosen article is re-hashed here.
        served = self.served_set(choice.article_id, support_language=support)
        if served is None:
            return None
        issued = int(_now(now).timestamp())
        return {
            "article_id": choice.article_id,
            "set_id": choice.set_id,
            "selection_policy_version": choice.policy_version,
            "recommendation": self._sign({"u": str(uid), "l": language, "a": choice.article_id,
                                          "s": choice.set_id, "p": choice.policy_version, "t": issued}),
            "target_difficulty": choice.target_difficulty,
            "probe": choice.probe,
            "weak_types": list(choice.weak_types),
            "ability": ability["ability"],
            "set": served,
        }

    # -- the one read contract for every consumer -----------------------

    def list_evidence(self, limit: int = 20) -> list[dict[str, Any]]:
        """`list_reading_evidence`: the learner's canonical attempts, newest
        first, each with its article - the one Reading read contract the
        cross-skill cue, Collection, Learner Summary and History consume. The
        legacy archive is never read here."""
        uid, language, _ = self._scope()
        bounded = max(1, min(int(limit or 20), 100))
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingAttempt.id, ReadingAttempt.set_id, ReadingAttempt.created_at,
                       ReadingAttempt.passage_level, ReadingAttempt.correct_count, ReadingAttempt.total,
                       ReadingArticle.id.label("article_id"), ReadingArticle.title,
                       ReadingArticle.topic, ReadingArticle.content_kind)
                .join(ReadingComprehensionSet, ReadingComprehensionSet.id == ReadingAttempt.set_id)
                .join(ReadingArticle, ReadingArticle.id == ReadingComprehensionSet.article_id)
                .where(ReadingAttempt.user_id == uid, ReadingAttempt.language_code == language)
                .order_by(ReadingAttempt.ordinal.desc())
                .limit(bounded)
            ).all()
        return [
            {
                "id": str(row.id),
                "kind": "reading_attempt",
                "article_id": str(row.article_id),
                "set_id": str(row.set_id),
                "language": language,
                "title": row.title,
                "topic": row.topic,
                "content_kind": row.content_kind,
                "created_at": _iso(row.created_at),
                "passage_level": row.passage_level,
                "correct_count": row.correct_count,
                "total": row.total,
            }
            for row in rows
        ]


def question_inputs(raw: Iterable[Mapping[str, Any]]) -> list[QuestionInput]:
    """`QuestionInput`s from the processor's validated dictionaries."""
    return [
        QuestionInput(
            question_type=str(item.get("question_type") or ""),
            prompt=str(item.get("prompt") or ""),
            options=list(item.get("options") or []),
            correct_index=int(item.get("correct_index", -1)),
            explanation=str(item.get("explanation") or ""),
            evidence_text=(str(item.get("evidence_text")) if item.get("evidence_text") else None),
            rank=int(item.get("rank", index)),
        )
        for index, item in enumerate(raw)
    ]
