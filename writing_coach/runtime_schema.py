"""What state the runtime database is in, and what to say about it.

Pure decisions: no engine, no Alembic, no connection. A process starting up
answers one question - may I serve? - and the answer is never "let me build the
schema first". That was the previous behaviour: an empty database was migrated
to head by whichever process connected to it, so a deployment pointed at the
wrong database quietly created a schema there instead of refusing, and no
operator ever chose the moment.

Four states, and only one of them starts. See ORENA_ACCOUNT_DATA_ARCHITECTURE
section 6 ("Startup only verifies schema", "Add schema through an operator
command") and the standing persistence invariant against automatic startup
Alembic.
"""
from __future__ import annotations

from collections.abc import Collection

READY = 'ready'
EMPTY = 'empty'
MISMATCH = 'mismatch'
UNAVAILABLE = 'unavailable'

# The one way a schema is created. Named here so the refusal can point at it
# and so nothing else has to remember what it is called.
BOOTSTRAP_COMMAND = 'python scripts/bootstrap_runtime_schema.py --confirm'


def readiness(*, actual: str | None, tables: Collection[str] | None, expected: str) -> str:
    """Classify the database a process has just looked at.

    `tables` is None when the database could not be read at all, which is a
    different problem from anything the schema could explain. An empty database
    is only empty when it has no revision *and* no tables: a database with
    tables but no Alembic revision is somebody else's schema, or a half-applied
    one, and creating tables on top of it is the worst available move.
    """
    if tables is None:
        return UNAVAILABLE
    if actual == expected:
        return READY
    if actual is None and not tables:
        return EMPTY
    return MISMATCH


def describe_readiness(state: str, *, expected: str, actual: str | None) -> str:
    """What an operator needs to read in the log, and nothing else.

    Only the empty case names the bootstrap command, because it is the only
    case where creating the schema is the right next step.
    """
    if state == READY:
        return ''
    if state == EMPTY:
        return (
            'The runtime database is empty. Orena does not create a schema while '
            f'starting up, so no tables were made. Run: {BOOTSTRAP_COMMAND}'
        )
    if state == MISMATCH:
        return (
            'The runtime database is at a different Alembic revision than this '
            f'build expects: expected {expected}, found {actual or "no revision"}. '
            'Check which database this process is pointed at before migrating '
            'anything.'
        )
    return (
        'The runtime database is unavailable, so its schema could not be read. '
        'This is a connectivity or credentials problem, not a schema one.'
    )


class SchemaNotReady(RuntimeError):
    """Startup refused. Carries the state so a caller can tell them apart."""

    def __init__(self, state: str, message: str, *, expected: str, actual: str | None):
        super().__init__(message)
        self.state = state
        self.expected = expected
        self.actual = actual

    @classmethod
    def raise_for(cls, state: str, *, expected: str, actual: str | None) -> None:
        if state == READY:
            return
        raise cls(
            state,
            describe_readiness(state, expected=expected, actual=actual),
            expected=expected,
            actual=actual,
        )
