# Proposed migrations

Alembic does not look here. `alembic.ini` points at `migrations/versions`, so
nothing in this directory is part of the revision chain, nothing is a head, and
no running deployment's startup check is affected by a file arriving here.

That separation is the point. Startup verifies the schema and refuses anything
that is not at the expected head, so a migration merged into `versions/` before
it is approved would make every environment refuse to start on its next
restart — approving it by accident, in the one way the verification exists to
prevent.

A file here is a proposal: reviewable as code, diffable, and runnable against a
throwaway test database by pointing Alembic's `version_locations` at this
directory. It becomes real by being moved into `versions/` — one `git mv`,
after the review and authorization its own docstring names.

**One proposal is open.** `20260916_0008_vocabulary_content_catalog.py` is
pending independent architecture review and human schema/runtime
authorization. The table below is the history of what passed through here;
every historical proposal now lives in `versions/`.

| Proposal | Outcome |
| --- | --- |
| `20260916_0008_vocabulary_content_catalog.py` | **PENDING** independent architecture review and human schema/runtime authorization. Shared vocabulary collections, reusable lexical entries, many-to-many memberships, and per-source import receipts; no learner-state or review tables. See `docs/project/VOCABULARY_SOURCE_SCHEMA_REVIEW_REQUEST.md`. |
| `20260908_0005_account_work_backbone.py` | I2: eight tables — account incarnation, stream head, mutation receipts, change records, work, work turns, kept-language provenance, projection checkpoints. Reviewed at `69ceb53` (APPROVED WITH REQUIRED CHANGES), revised through two re-reviews, approved at `6cc3dc1`, rehearsed under §6 step 3, and moved into `versions/` and applied to the sandbox runtime under §6 step 4. `ORENA_ACCOUNT_BACKBONE` remains off. |
| `20260911_0006_commerce_subscription_inbox.py` | I3: three tables — `commerce_subscriptions`, `commerce_provider_subscriptions`, `commerce_billing_event_receipts`. Delegated review round 3 (`7020925`): APPROVED WITH REQUIRED CHANGES - schema approved; the one required code reorder is made with its test (23/23). Moved into `versions/` with 0007 and applied to the sandbox runtime. See `I3_SCHEMA_REVIEW_REQUEST.md`. |
| `20260912_0007_commerce_quota_buckets.py` | I3: two tables — `commerce_quota_buckets`, `commerce_quota_reservations`. Round 3 (`7020925`): **APPROVED** (28/28 postgres cases incl. a deadlock stress; the reviewer's deadlock matrix 0 in all configurations). Moved into `versions/` and applied to the sandbox runtime. Chains on top of `20260911_0006` (linearity only — no shared foreign key). See `I3_SCHEMA_REVIEW_REQUEST.md`. |
