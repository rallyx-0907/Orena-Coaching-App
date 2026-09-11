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

**One proposal is open:** `20260911_0006_commerce_subscription_inbox.py`,
awaiting the review `docs/project/I3_SCHEMA_REVIEW_REQUEST.md` asks for.
Rehearsed against a disposable scratch database only; the runtime database
was never touched and nothing here is applied anywhere real.

| Proposal | Outcome |
| --- | --- |
| `20260908_0005_account_work_backbone.py` | I2: eight tables — account incarnation, stream head, mutation receipts, change records, work, work turns, kept-language provenance, projection checkpoints. Reviewed at `69ceb53` (APPROVED WITH REQUIRED CHANGES), revised through two re-reviews, approved at `6cc3dc1`, rehearsed under §6 step 3, and moved into `versions/` and applied to the sandbox runtime under §6 step 4. `ORENA_ACCOUNT_BACKBONE` remains off. |
| `20260911_0006_commerce_subscription_inbox.py` | I3: two tables — `commerce_subscriptions`, `commerce_billing_event_receipts`. Rehearsed (chain, 6 concurrency cases incl. a real thread race x5 for flakiness, downgrade, up/down/up) against scratch databases only. Not yet reviewed. See `I3_SCHEMA_REVIEW_REQUEST.md`. |
