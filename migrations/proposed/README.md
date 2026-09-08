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

| Proposal | For | Waiting on |
| --- | --- | --- |
| `20260908_0005_account_work_backbone.py` | I2: account incarnation, mutation receipts, change stream, work aggregate, provenance, projection checkpoints | Codex architecture review (`ORENA_ACCOUNT_DATA_ARCHITECTURE` §6 step 2), then explicit schema authorization (step 4) |
