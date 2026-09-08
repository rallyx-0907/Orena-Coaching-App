"""Where a kept word was met, as occurrences rather than as one fact.

PROPOSAL — the table this writes is in `migrations/proposed/20260908_0005`,
awaiting re-review and schema authorization. No caller is wired to it.

`saved_words` owns the word and its review schedule and has no column for where
the learner met it, so provenance sits beside it. Two things about that
relationship needed correcting after review.

An occurrence, not a fact about the pair. Meeting the same word twice in one
source - two lines of a story, the same word attended to differently - is two
occurrences, and the first shape could not represent it. Focus is what tells
them apart, so it is part of the identity.

And the parent scope is checked here, in the transaction, rather than by the
database. A composite foreign key would need `saved_words` to carry a matching
unique constraint on (id, user_id, language_code); adding one means altering an
existing owner table to manufacture a key for a new dependant, which is not
this migration's to do. So the key is the saved word's id, and every write
takes a share lock on that row and compares its account and language against
the caller's scope before inserting. A saved word belonging to another account,
or to another language of the same account, is refused - and both are tested,
because a check that lives in code rather than in a constraint is only as good
as the test that holds it there.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import Scope

# The reasons a learner keeps language, matching KEEP_REASONS in the browser
# memory contract. A reason outside this set is a caller bug, not a new reason.
KEEP_REASONS = (
    'looked_up',
    'from_reading',
    'from_listening',
    'from_writing',
    'from_speaking',
    'from_grammar',
)

# Nobody has checked whether the origin still resolves. That is the honest
# starting state and it is not the same as knowing it is reachable.
UNKNOWN = 'unknown'
AVAILABILITY = ('available', UNKNOWN, 'unavailable')


class ProvenanceRejected(Exception):
    """A provenance write that must not happen, and why."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def focus_digest(focus: str) -> str:
    """Focus is unbounded text; its identity in an index has to be bounded."""
    return hashlib.sha256((focus or '').encode('utf-8')).hexdigest()


class PostgresProvenanceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record_occurrence(
        self,
        *,
        scope: Scope,
        saved_word_id: str,
        reason: str,
        source: dict[str, str] | None = None,
        focus: str = '',
        availability: str = UNKNOWN,
    ) -> dict[str, Any]:
        source = source or {}
        if reason not in KEEP_REASONS:
            raise ProvenanceRejected('unknown_reason')
        if availability not in AVAILABILITY:
            raise ProvenanceRejected('unknown_availability')
        if bool(source.get('kind')) != bool(source.get('id')):
            raise ProvenanceRejected('incomplete_source_ref')
        if source.get('revision') and not source.get('id'):
            raise ProvenanceRejected('revision_without_source')

        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            # The parent, held for the length of this transaction so its scope
            # cannot change under the check. FOR SHARE rather than FOR UPDATE:
            # this reads the parent, it does not modify it, and a review
            # happening concurrently should not be blocked by a bookmark.
            parent = connection.execute(
                text(
                    'SELECT user_id, language_code FROM saved_words '
                    'WHERE id = :id FOR SHARE'
                ),
                {'id': saved_word_id},
            ).mappings().first()
            if parent is None:
                raise ProvenanceRejected('unknown_saved_word')
            # The two refusals are separate because they are different
            # mistakes: one is another person's word, the other is this
            # person's word in a language this scope does not cover.
            if str(parent['user_id']) != str(scope.account):
                raise ProvenanceRejected('cross_account_saved_word')
            if str(parent['language_code']) != str(scope.language):
                raise ProvenanceRejected('cross_language_saved_word')

            occurrence = uuid.uuid4()
            connection.execute(
                text(
                    'INSERT INTO language_provenance (id, incarnation_id, language_code, '
                    'saved_word_id, source_kind, source_id, source_revision, focus, '
                    'focus_digest, reason, version, availability, created_at, updated_at) '
                    'VALUES (:id, :inc, :lang, :word, :source_kind, :source_id, '
                    ':source_revision, :focus, :digest, :reason, 1, :availability, '
                    ':now, :now)'
                ),
                {
                    'id': occurrence,
                    'inc': scope.incarnation,
                    'lang': scope.language,
                    'word': saved_word_id,
                    'source_kind': source.get('kind', ''),
                    'source_id': source.get('id', ''),
                    'source_revision': source.get('revision', ''),
                    'focus': focus,
                    'digest': focus_digest(focus),
                    'reason': reason,
                    'availability': availability,
                    'now': now,
                },
            )
        return {'id': str(occurrence), 'version': 1, 'availability': availability}

    def occurrences_for(self, scope: Scope, saved_word_id: str) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    'SELECT id, source_kind, source_id, source_revision, focus, reason, '
                    'version, availability FROM language_provenance '
                    'WHERE incarnation_id = :inc AND language_code = :lang '
                    'AND saved_word_id = :word ORDER BY created_at, id'
                ),
                {
                    'inc': scope.incarnation,
                    'lang': scope.language,
                    'word': saved_word_id,
                },
            ).mappings().all()
        return [dict(row) for row in rows]
