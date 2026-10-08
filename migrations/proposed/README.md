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

**Open proposal:** `20261001_0024_media_entries.py` (MEDIA_METADATA_POSTGRES.md rev 2; APPROVE WITH CONDITIONS,
awaiting the human's authorization). If it is promoted after 0025, re-parent it on `20261004_0025`.

**Promoted 2026-10-08:** `20261008_0030_grammar_content_store.py` (GRAMMAR_CONTENT_STORE.md rev 3a, issue #99;
independent architecture review APPROVE at `b3ee8f09`, PR #100; rehearsed on a throwaway PostgreSQL 16 with
`scripts/rehearse_grammar_content_store.py`). The human authorized the promotion in source control only: it is applied
to no runtime by that change, and every PostgreSQL runtime that takes this code must apply it (operator step, after a
backup, on the runtime the human names) before it starts. `20261005_0026_ai_cost_records.py` was re-parented on it
(`down_revision = "20261008_0030"`), as the 0030 proposal said the second of the two would be.

**Promoted 2026-10-04:** `20261004_0025_vocabulary_sense_localizations.py` (D-124, VOCABULARY_LOCALIZATION.md rev 2,
independent review APPROVE WITH CONDITIONS, conditions closed, PostgreSQL 16 rehearsal at 100k entries). The human
authorized :8021 only; it was applied there with `scripts/bootstrap_runtime_schema.py --upgrade` after a verified
`pg_dump` and restore check. Any other runtime that takes this code must apply it (operator step, after a backup) before
it starts: startup refuses a schema below head.

**Earlier:** D4, the learner records (`docs/project/proposals/LEARNER_RECORDS_D4.md`, revision 3, decided by
D-104), passed its independent review (APPROVE) and rehearsal (53 PASS at 100k rows); the human authorized it for the lane
runtime :8021 only (D-105). Its seven revisions moved into `versions/` together and were applied to :8021 one revision per
invocation after a backup (2026-09-30). :8000 is untouched until the merge and its own gates. Below, what D4 added, then
the earlier history.

| D4 revision (now in `versions/`) | What it adds |
| --- | --- |
| `20260930_0017_declared_level.py` | `user_language_profiles.declared_level` (H2, merged into D4). |
| `20260930_0018_account_settings.py` | `users.learning_language`, `interface_language`, `weekly_goal_days`, `settings_updated_at` (the server-owned version token). Own operator step after a backup. |
| `20260930_0019_review_settings.py` | Review new-per-day, limit-per-day and modes on `user_language_profiles`. |
| `20260930_0020_listening_score_source.py` | `listening_progress.score_source` (`client` for every existing row; the server recomputes Dictation scores). |
| `20260930_0021_essay_review_history.py` | New table `essay_review_history` (immutable prior reviews; scope is the essay's, no `user_id`/`language_code` copies) with a PostgreSQL `BEFORE UPDATE` trigger. |
| `20260930_0022_library_items_place.py` | `library_items.place`, `place_at` and a partial index (continuation). |
| `20260930_0023_grammar_quiz_result.py` | `grammar_progress.last_quiz_correct`, `last_quiz_total`, `last_quiz_at` and a PostgreSQL CHECK. |

**Apply one revision per invocation.** `migrations/env.py` runs an invocation in one transaction, so its locks last to the
commit; a single `--upgrade` to head would hold 0018's lock on `users` through 0022's index build and 0023's CHECK scan.
The operator applies `bootstrap_runtime_schema.py --upgrade --from <rev> --to <rev> --confirm` seven times, in order, and
**0018 alone, immediately after a fresh backup** (`users` is written on every sign-in). The maintenance window for :8000 is
set from the measured per-revision lock-hold times of `scripts/rehearse_learner_records_schema.py --volume N`
(proposal section 5.2).

The ORM models and application code do not change until authorization (the proposal lists the changes, section 15), so
a runtime at `20260924_0016` keeps working.


| Proposal | Outcome |
| --- | --- |
| `20260923_0013_my_library_and_entry_identity.py` | Independent architecture review round 1 **APPROVED WITH REQUIRED CHANGES** (`dc8b340`); every required change made and re-rehearsed. Human schema/runtime authorization given 2026-09-23 for **dev and sandbox only, not production**; moved into `versions/` and applied to the sandbox runtime (D-074). Three tables for the learner's own library (`library_items`, `library_collections`, `library_collection_members`) and three additive columns on `saved_words` (`entry_id`, `entry_identity_key`, `reading_key`) so a saved word knows which catalogue entry and which reading it is — the foundation per-word pronunciation audio needs. Additive; no existing column changes type or nullability, no data is backfilled, and no review schedule is duplicated. Chains on `20260922_0012` (this lane's head). Rehearsed up/down/up against a throwaway PostgreSQL 16 with 24 constraint and concurrency probes (`scripts/rehearse_my_library_schema.py`). See `docs/project/MY_LIBRARY_SCHEMA_REVIEW_REQUEST.md`. |
| `20260923_0014_vocabulary_decks.py` | Reviewed and authorized for dev and sandbox only; follows My Library. See `docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md`. |
| `20260924_0015_reading_content_engine.py` | Admin-lane predecessor reviewed and authorized for its sandbox. This integration revision follows Vocabulary Decks and needs independent delta review before shared-runtime apply. Additive Reading Content Engine tables. See `docs/project/READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md`. |
| `20260924_0016_adaptive_reading.py` | Admin-lane predecessor reviewed and authorized for its sandbox (D-083). This integration revision follows the Content Engine and needs independent delta review before shared-runtime apply. Canonical Reading cutover archives the generated-passage tables. See `docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`. |
| `20260916_0009_reading_library.py` | Two tables — `reading_books`, `reading_book_chapters`, admin EPUB import into a shared catalog every learner reads. Three rounds of delegated independent architecture review, round 3 **APPROVED**. Human schema/runtime authorization given 2026-09-16; moved into `versions/` together with `20260916_0008` (its chain parent) and applied to the sandbox runtime. See `docs/project/READING_LIBRARY_SCHEMA_REVIEW_REQUEST.md`. |
| `20260916_0008_vocabulary_content_catalog.py` | Shared vocabulary collections, reusable lexical entries, many-to-many memberships, and per-source import receipts; no learner-state or review tables. Independent architecture review **APPROVED** (`a1a90b7bfe8ebdd5f60e1a928f0b070f52cc3c8d`). Human schema/runtime authorization given 2026-09-16; moved into `versions/` and applied to the sandbox runtime. See `docs/project/VOCABULARY_SOURCE_SCHEMA_REVIEW_REQUEST.md`. |
| `20260908_0005_account_work_backbone.py` | I2: eight tables — account incarnation, stream head, mutation receipts, change records, work, work turns, kept-language provenance, projection checkpoints. Reviewed at `69ceb53` (APPROVED WITH REQUIRED CHANGES), revised through two re-reviews, approved at `6cc3dc1`, rehearsed under §6 step 3, and moved into `versions/` and applied to the sandbox runtime under §6 step 4. `ORENA_ACCOUNT_BACKBONE` remains off. |
| `20260911_0006_commerce_subscription_inbox.py` | I3: three tables — `commerce_subscriptions`, `commerce_provider_subscriptions`, `commerce_billing_event_receipts`. Delegated review round 3 (`7020925`): APPROVED WITH REQUIRED CHANGES - schema approved; the one required code reorder is made with its test (23/23). Moved into `versions/` with 0007 and applied to the sandbox runtime. See `I3_SCHEMA_REVIEW_REQUEST.md`. |
| `20260912_0007_commerce_quota_buckets.py` | I3: two tables — `commerce_quota_buckets`, `commerce_quota_reservations`. Round 3 (`7020925`): **APPROVED** (28/28 postgres cases incl. a deadlock stress; the reviewer's deadlock matrix 0 in all configurations). Moved into `versions/` and applied to the sandbox runtime. Chains on top of `20260911_0006` (linearity only — no shared foreign key). See `I3_SCHEMA_REVIEW_REQUEST.md`. |
