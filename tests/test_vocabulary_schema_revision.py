"""The vocabulary schema is usable at its own revision and at every descendant.

Alembic's `iterate_revisions(upper, lower)` stops before `lower`, so a check
built on it never saw the vocabulary revision below a later head and reported
the vocabulary schema missing on every database migrated past it (the reading
library revision is the first). Learners lost the Vocabulary Library and
administrators lost vocabulary import on a correctly migrated runtime.
"""
from writing_coach.persistence.vocabulary_repository import (
    VOCABULARY_SCHEMA_REVISION,
    _vocabulary_revision_is_usable,
)


def test_vocabulary_revision_itself_is_usable():
    assert _vocabulary_revision_is_usable(VOCABULARY_SCHEMA_REVISION) is True


def test_a_later_revision_that_descends_from_it_is_usable():
    assert _vocabulary_revision_is_usable("20260916_0009") is True


def test_an_earlier_revision_is_not_usable():
    assert _vocabulary_revision_is_usable("20260912_0007") is False


def test_an_unknown_revision_is_not_usable():
    assert _vocabulary_revision_is_usable("not_a_revision") is False
    assert _vocabulary_revision_is_usable("") is False
