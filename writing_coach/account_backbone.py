"""Whether the account backbone is switched on, and what it is when it is not.

I2 wiring. The schema is in the live chain and the sandbox runtime runs with
the flag on (`active`); production and preview run without it (`disabled`).
So the product has to hold both facts at once: the code is present and the
feature may be off, and "off" has to be a real answer rather than a crash or a
silent pretence that work was saved.

Three states, and the difference between the last two matters:

  * `active`   - the schema is present and the operator switched it on;
  * `disabled` - switched off, which is the default and today's answer;
  * `unavailable` - switched on, but the schema is not there.

`disabled` is a product decision and `unavailable` is a fault. A surface may
say "this device remembers your drafts" for the first and must not say it for
the second, because the second means someone intended otherwise and something
is wrong.

Turning it on is `ORENA_ACCOUNT_BACKBONE=on` plus a runtime database at the
revision that carries the tables. Both, and neither alone: the flag without the
schema is `unavailable`, and the schema without the flag stays `disabled`, so a
migration applied ahead of a deploy changes nothing on its own.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

FLAG = 'ORENA_ACCOUNT_BACKBONE'

ACTIVE = 'active'
DISABLED = 'disabled'
UNAVAILABLE = 'unavailable'

# Every table migration 20260908_0005 creates. All of them or none: a partial
# set is a half-applied migration, which is not something to run on.
BACKBONE_TABLES = (
    'account_incarnations',
    'account_streams',
    'mutation_receipts',
    'change_records',
    'works',
    'work_turns',
    'language_provenance',
    'projection_checkpoints',
)


def requested(env: object = None) -> bool:
    """Whether an operator asked for it. Off unless explicitly on."""
    values = os.environ if env is None else env
    return str(values.get(FLAG, '')).strip().casefold() in {'on', '1', 'true', 'yes'}


def state(*, present: bool, asked: bool) -> str:
    """What the backbone is, given what exists and what was asked for."""
    if not asked:
        return DISABLED
    return ACTIVE if present else UNAVAILABLE


def schema_present(tables: object) -> bool:
    """All eight tables, or it is not present.

    `tables` is None when the database could not be read, which is not the same
    as the tables being absent and is not treated as a reason to report them
    missing.
    """
    if tables is None:
        return False
    return set(BACKBONE_TABLES) <= set(tables)


@dataclass(frozen=True)
class AccountBackbone:
    """The account-scoped repositories, or an explanation instead of them.

    Held rather than reached for: a caller asks `backbone.state` and gets a
    truthful answer, instead of discovering the situation from an exception
    somewhere further in.
    """

    state: str
    incarnations: object | None = None
    work: object | None = None
    provenance: object | None = None

    @property
    def is_active(self) -> bool:
        return self.state == ACTIVE

    def require(self):
        """For a caller that has already checked. Raises rather than returning None."""
        if not self.is_active:
            raise RuntimeError(f'The account backbone is {self.state}')
        return self


def build_backbone(engine, tables: object, *, env: object = None) -> AccountBackbone:
    """Construct the repositories only when both halves are true.

    Importing the adapters is deferred to here so that a deployment with the
    feature off does not need them importable at module load, and so that
    nothing constructs an engine-bound repository that has no tables to read.
    """
    asked = requested(env)
    current = state(present=schema_present(tables), asked=asked)
    if current != ACTIVE or engine is None:
        return AccountBackbone(current)

    from writing_coach.persistence.incarnation_repository import (
        PostgresIncarnationRepository,
    )
    from writing_coach.persistence.provenance_repository import (
        PostgresProvenanceRepository,
    )
    from writing_coach.persistence.work_repository import PostgresWorkRepository

    return AccountBackbone(
        ACTIVE,
        incarnations=PostgresIncarnationRepository(engine),
        work=PostgresWorkRepository(engine),
        provenance=PostgresProvenanceRepository(engine),
    )
