"""Where a kept word was met, as occurrences rather than as one fact.

DEPLOYED, NOT YET CALLED — the table this writes is in
`migrations/versions/20260908_0005`. The sandbox runs with the backbone
`active`, but no route writes kept-language provenance through this yet; kept
language's provenance still lives on the device.

`saved_words` owns the word and its review schedule and has no column for where
the learner met it, so provenance sits beside it. Three things about that
relationship needed correcting through review.

**An occurrence is an event, not a fact about the pair.** Meeting the same word
twice in one source - two lines of a story, the same word attended to twice the
same way - is two occurrences. The first shape made (saved word, source, focus)
unique, which collapsed them; the second made it unique over a focus digest,
which still collapsed the identical pair. Occurrence identity is the row's own
id and nothing else, because semantic equality is not identity: two distinct
operations that say the same thing are two things that happened.

**Which makes deduplication the operation's job.** Attaching provenance is a
mutation like any other - it takes a sequence, a receipt and a change record
through `mutation_commit`. A retry of the same operation replays the same
occurrence; a genuinely different operation with identical content creates
another. That is the only way both halves can be true at once.

**And the parent scope is checked here, in the transaction.** A composite
foreign key would need `saved_words` to carry a matching unique constraint on
(id, user_id, language_code); adding one means altering an existing owner table
to manufacture a key for a new dependant. So the key is the saved word's id,
and every write takes a share lock on that row and compares its account and
language against the caller's scope before inserting. `FOR SHARE` rather than
`FOR UPDATE` because this reads the parent and does not modify it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.persistence.mutation_commit import (
    MutationOutcome,
    MutationRefused,
    ResourceState,
    commit_mutation,
)
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

PROVENANCE_DOMAIN = 'provenance'


class ProvenanceRejected(Exception):
    """A provenance write that must not happen, and why."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def focus_digest(focus: str) -> str:
    """A bounded stand-in for unbounded focus text, for reading and comparison.

    It is deliberately *not* part of any uniqueness: two occurrences with the
    same focus are two occurrences.
    """
    return hashlib.sha256((focus or '').encode('utf-8')).hexdigest()


def occurrence_digest(
    saved_word_id: str,
    reason: str,
    source: dict[str, str],
    focus: str,
    availability: str,
) -> str:
    """The semantic content of one attachment, for the receipt's reuse guard.

    Every input that ends up written to the row is in here. `availability` was
    not, and it is state: reusing an operation id with a changed availability
    would have matched the digest and replayed, reporting success for a value
    that was never stored.

    This catches an operation id being replayed with different content. It is
    not the occurrence's identity - identical content under a different
    operation id is a second occurrence, on purpose.
    """
    material = json.dumps(
        {
            'type': 'provenance.attach',
            'word': saved_word_id,
            'reason': reason,
            'source': {k: source.get(k, '') for k in ('kind', 'id', 'revision')},
            'focus': focus,
            'availability': availability,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
    )
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


class PostgresProvenanceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def attach_occurrence(
        self,
        *,
        scope: Scope,
        occurrence_id: str,
        operation_id: str,
        saved_word_id: str,
        reason: str,
        source: dict[str, str] | None = None,
        focus: str = '',
        availability: str = UNKNOWN,
    ) -> MutationOutcome:
        """Record one occurrence, retry-safely.

        `occurrence_id` is supplied by the caller, like a work id: the row's
        identity has to exist before the transaction so a replay can name what
        it committed.
        """
        source = source or {}
        if reason not in KEEP_REASONS:
            raise ProvenanceRejected('unknown_reason')
        if availability not in AVAILABILITY:
            raise ProvenanceRejected('unknown_availability')
        if bool(source.get('kind')) != bool(source.get('id')):
            raise ProvenanceRejected('incomplete_source_ref')
        if source.get('revision') and not source.get('id'):
            raise ProvenanceRejected('revision_without_source')

        def load(connection):
            # The parent, held for the length of this transaction so its scope
            # cannot change under the check.
            parent = connection.execute(
                text(
                    'SELECT user_id, language_code FROM saved_words '
                    'WHERE id = :id FOR SHARE'
                ),
                {'id': saved_word_id},
            ).mappings().first()
            if parent is None:
                raise MutationRefused('unknown_saved_word')
            # Two separate refusals because they are two different mistakes:
            # another person's word, and this person's word in a language this
            # scope does not cover.
            if str(parent['user_id']) != str(scope.account):
                raise MutationRefused('cross_account_saved_word')
            if str(parent['language_code']) != str(scope.language):
                raise MutationRefused('cross_language_saved_word')
            # And the occurrence itself. Reporting version 0 unconditionally
            # assumed the id was free, so a distinct operation reusing an
            # existing occurrence id went to the insert and failed on the
            # primary key instead of being answered.
            existing = connection.execute(
                text(
                    'SELECT p.incarnation_id, p.language_code, p.version, i.user_id '
                    'FROM language_provenance p '
                    'JOIN account_incarnations i ON i.id = p.incarnation_id '
                    'WHERE p.id = :id FOR UPDATE OF p'
                ),
                {'id': occurrence_id},
            ).mappings().first()
            if existing is None:
                return ResourceState(0, False, scope, None)
            owner = Scope(
                str(existing['user_id']),
                str(existing['incarnation_id']),
                str(existing['language_code']),
            )
            # In our scope this is a version conflict against a creation; in
            # another scope it is a denial. Either way it is an answer.
            return ResourceState(int(existing['version']), False, owner, None)

        def write(connection, version, sequence, now, state):
            connection.execute(
                text(
                    'INSERT INTO language_provenance (id, incarnation_id, language_code, '
                    'saved_word_id, source_kind, source_id, source_revision, focus, '
                    'focus_digest, reason, version, availability, created_at, updated_at) '
                    'VALUES (:id, :inc, :lang, :word, :source_kind, :source_id, '
                    ':source_revision, :focus, :digest, :reason, :version, :availability, '
                    ':now, :now)'
                ),
                {
                    'id': occurrence_id,
                    'inc': scope.incarnation,
                    'lang': scope.language,
                    'word': saved_word_id,
                    'source_kind': source.get('kind', ''),
                    'source_id': source.get('id', ''),
                    'source_revision': source.get('revision', ''),
                    'focus': focus,
                    'digest': focus_digest(focus),
                    'reason': reason,
                    'version': version,
                    'availability': availability,
                    'now': now,
                },
            )
            return 'upsert'

        return commit_mutation(
            self._engine,
            scope=scope,
            domain=PROVENANCE_DOMAIN,
            operation_id=operation_id,
            digest=occurrence_digest(saved_word_id, reason, source, focus, availability),
            expected_version=0,
            resource_id=occurrence_id,
            load=load,
            write=write,
        )

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
