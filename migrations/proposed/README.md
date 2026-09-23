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

**One proposal is open:** `20260922_0010_reading_content_engine.py`. Every
other row below is history — those proposals now live in `versions/`.

| Proposal | Outcome |
| --- | --- |
| `20260923_0013_my_library_and_entry_identity.py` | Independent architecture review round 1 **APPROVED WITH REQUIRED CHANGES** (`dc8b340`); every required change made and re-rehearsed. Human schema/runtime authorization given 2026-09-23 for **dev and sandbox only, not production**; moved into `versions/` and applied to the sandbox runtime (D-074). Three tables for the learner's own library (`library_items`, `library_collections`, `library_collection_members`) and three additive columns on `saved_words` (`entry_id`, `entry_identity_key`, `reading_key`) so a saved word knows which catalogue entry and which reading it is — the foundation per-word pronunciation audio needs. Additive; no existing column changes type or nullability, no data is backfilled, and no review schedule is duplicated. Chains on `20260922_0012` (this lane's head). Rehearsed up/down/up against a throwaway PostgreSQL 16 with 24 constraint and concurrency probes (`scripts/rehearse_my_library_schema.py`). See `docs/project/MY_LIBRARY_SCHEMA_REVIEW_REQUEST.md`. |
| `20260922_0010_reading_content_engine.py` | **OPEN — independent architecture review APPROVED (`e09c6ce`, four rounds); awaiting human schema/runtime authorization.** Rehearsed up/down/up against a throwaway PostgreSQL 16. Six tables behind the Admin Reading Content Engine — `reading_sources`, `reading_source_items`, `reading_articles`, `reading_article_targets`, `reading_review_events`, `reading_ingestion_jobs`. Additive; nothing existing is altered. Chains on `20260916_0009` (this lane's head); `codex/work` has its own `0010`–`0012`, so integration needs an Alembic merge or a rebase — recorded, not resolved. See `docs/project/READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md`. |
| `20260916_0009_reading_library.py` | Two tables — `reading_books`, `reading_book_chapters`, admin EPUB import into a shared catalog every learner reads. Three rounds of delegated independent architecture review, round 3 **APPROVED**. Human schema/runtime authorization given 2026-09-16; moved into `versions/` together with `20260916_0008` (its chain parent) and applied to the sandbox runtime. See `docs/project/READING_LIBRARY_SCHEMA_REVIEW_REQUEST.md`. |
| `20260916_0008_vocabulary_content_catalog.py` | Shared vocabulary collections, reusable lexical entries, many-to-many memberships, and per-source import receipts; no learner-state or review tables. Independent architecture review **APPROVED** (`a1a90b7bfe8ebdd5f60e1a928f0b070f52cc3c8d`). Human schema/runtime authorization given 2026-09-16; moved into `versions/` and applied to the sandbox runtime. See `docs/project/VOCABULARY_SOURCE_SCHEMA_REVIEW_REQUEST.md`. |
| `20260908_0005_account_work_backbone.py` | I2: eight tables — account incarnation, stream head, mutation receipts, change records, work, work turns, kept-language provenance, projection checkpoints. Reviewed at `69ceb53` (APPROVED WITH REQUIRED CHANGES), revised through two re-reviews, approved at `6cc3dc1`, rehearsed under §6 step 3, and moved into `versions/` and applied to the sandbox runtime under §6 step 4. `ORENA_ACCOUNT_BACKBONE` remains off. |
| `20260911_0006_commerce_subscription_inbox.py` | I3: three tables — `commerce_subscriptions`, `commerce_provider_subscriptions`, `commerce_billing_event_receipts`. Delegated review round 3 (`7020925`): APPROVED WITH REQUIRED CHANGES - schema approved; the one required code reorder is made with its test (23/23). Moved into `versions/` with 0007 and applied to the sandbox runtime. See `I3_SCHEMA_REVIEW_REQUEST.md`. |
| `20260912_0007_commerce_quota_buckets.py` | I3: two tables — `commerce_quota_buckets`, `commerce_quota_reservations`. Round 3 (`7020925`): **APPROVED** (28/28 postgres cases incl. a deadlock stress; the reviewer's deadlock matrix 0 in all configurations). Moved into `versions/` and applied to the sandbox runtime. Chains on top of `20260911_0006` (linearity only — no shared foreign key). See `I3_SCHEMA_REVIEW_REQUEST.md`. |
