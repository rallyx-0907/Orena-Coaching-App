"""Rights on Reading books and a publish gate like Media's (D-251; PRE-203 part 2, Hermes for the owner 2026-10-21).

Books had no rights field at all, and an imported book was on the learner shelf at once. Five columns on
`reading_books`, additive:

- `rights_status` (varchar 20 NOT NULL DEFAULT 'unknown', CHECK in unknown | cleared | denied | grandfathered): whether
  learners may read it. Only `cleared` (an administrator attested the rights, with a licence note) and `grandfathered`
  (on the shelf before this revision; see the backfill) are shown to learners.
- `license_note` (text NOT NULL DEFAULT ''): the licence or permission the attestation rests on.
- `source_url` (varchar 1000 NOT NULL DEFAULT ''): where the text came from.
- `rights_attested_by` (varchar 255, NULL), `rights_attested_at` (timestamptz, NULL): who attested, and when.

**Backfill, the one data decision:** every book on the shelf (`ready`) when this runs becomes `grandfathered`, so nothing
already on the shelf disappears (Hermes for the owner: re-check, never take down on its own). An archived book stays
`unknown`: restoring it needs an attestation, so archiving (the only take-down there was) is no way round the gate.
`scripts/check_books_rights.py` lists them for a human decision; an administrator moves each to `cleared` or
`denied`. A book imported after this revision starts `unknown` and is not shown until attested.

Safe on populated tables: `ADD COLUMN`s with constant defaults (no rewrite on PostgreSQL 11+), one `UPDATE` over the
existing book rows (a small table: one row per imported book), one CHECK constraint, under `lock_timeout`. No index.

Status: PROPOSED, in `migrations/proposed/` - Alembic ignores it. Schema change: it needs an independent architecture
review and the owner's authorization before it is promoted (`git mv` into `versions/`) and applied, each runtime as its
own operator step after a fresh backup. The code that reads these columns checks for them first
(`persistence/reading_library_repository.py`, `_has_rights_columns`), so it runs unchanged - the gate dormant - on a
database without them.

`downgrade()` drops the five columns and every rights answer recorded in them. It exists for the rehearsal; a runtime
holding attestations is restored from backup, never downgraded.

Revision ID: 20261021_0037
Revises: 20261019_0036
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261021_0037"
down_revision = "20261019_0036"
branch_labels = None
depends_on = None

RIGHTS_STATUSES = ("unknown", "cleared", "denied", "grandfathered")


def _lock_timeout() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")


def upgrade() -> None:
    _lock_timeout()
    op.add_column("reading_books", sa.Column("rights_status", sa.String(20), nullable=False, server_default="unknown"))
    op.add_column("reading_books", sa.Column("license_note", sa.Text(), nullable=False, server_default=""))
    op.add_column("reading_books", sa.Column("source_url", sa.String(1000), nullable=False, server_default=""))
    op.add_column("reading_books", sa.Column("rights_attested_by", sa.String(255), nullable=True))
    op.add_column("reading_books", sa.Column("rights_attested_at", sa.DateTime(timezone=True), nullable=True))
    # What is on the shelf stays readable until a person decides; an archived book stays `unknown`, so restoring it
    # needs an attestation (archiving was the only take-down there was - it must not become a way round the gate).
    op.execute("UPDATE reading_books SET rights_status = 'grandfathered' WHERE status = 'ready'")
    allowed = ", ".join(f"'{value}'" for value in RIGHTS_STATUSES)
    op.create_check_constraint("ck_reading_book_rights_status", "reading_books", f"rights_status IN ({allowed})")


def downgrade() -> None:
    _lock_timeout()
    op.drop_constraint("ck_reading_book_rights_status", "reading_books", type_="check")
    for column in ("rights_attested_at", "rights_attested_by", "source_url", "license_note", "rights_status"):
        op.drop_column("reading_books", column)
