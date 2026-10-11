"""AI cost per account (AC-2; human decision 2026-10-04; proposals/AI_COST_PER_ACCOUNT.md).

One row per priced provider call made for a signed-in account: the account, the feature (capability), the
provider and model, the estimated cost and its state, the units it was priced on (tokens, audio seconds), and
when. Nothing a learner wrote or said is stored - no prompt, answer, transcript or audio. It is the shared record
for the Admin cost page (totals by default; per account for an administrator) and for per-plan quota.

Retention: 13 months, then deleted automatically in bounded batches (writing_coach/ai/account_costs.py). A deleted
account's rows go with it (ON DELETE CASCADE): the record is the account's, not an archive.

Indexes: (account_id, occurred_at) for an account's history and quota windows; (occurred_at) for the totals and
the retention sweep.

Review and gate. Promoted from `migrations/proposed/` into the chain (D-17H, branch schema/ai-cost-0026) after the
independent review of 2026-10-05 (APPROVE WITH CONDITIONS, conditions met in e54a2aa3) and a delta review recorded
in docs/reviews/architecture/AI_COST_0026_REVIEW_2026-10-12.md. Promotion is source control only: every PostgreSQL
runtime that takes this code must apply it (operator step, after a backup and a rehearsal on a copy, on the runtime
the human names) before it starts - startup refuses a schema below head. Startup never applies it (D-002). The recorder still
tolerates a missing table (recording skipped, the per-account view says it is not available), which is how every
runtime ran before this promotion. `downgrade()` drops the table and every record in it; it exists
for rehearsal and rollback only.

Revision ID: 20261005_0026
Revises: 20261008_0030
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261005_0026"
down_revision = "20261008_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_cost_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default=""),
        sa.Column("model", sa.String(160), nullable=False, server_default=""),
        sa.Column("cost_state", sa.String(16), nullable=False),
        sa.Column("cost_usd", sa.Numeric(14, 8), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("audio_seconds", sa.Numeric(10, 3), nullable=True),
        sa.CheckConstraint("cost_state IN ('estimated', 'unpriced', 'partial', 'unknown')", name="ck_ai_cost_state"),
        sa.CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="ck_ai_cost_nonnegative"),
    )
    op.create_index("ix_ai_cost_records_account_time", "ai_cost_records", ["account_id", "occurred_at"])
    op.create_index("ix_ai_cost_records_time", "ai_cost_records", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_cost_records_time", table_name="ai_cost_records")
    op.drop_index("ix_ai_cost_records_account_time", table_name="ai_cost_records")
    op.drop_table("ai_cost_records")
