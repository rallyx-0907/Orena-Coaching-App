# AI cost per account (AC-2) — proposal

Status: PROPOSED. The migration `migrations/proposed/20261005_0026_ai_cost_records.py` waits for an
independent review, a rehearsal on a copy, and the human's authorization (AGENTS.md §1 "Architecture review
authority", §7).

## The human's decision (2026-10-04)

Per-account AI cost at the smallest grain: account, feature, cost, time. No learner words. Kept 13 months,
then deleted automatically. Admin shows totals by default; only an administrator sees per person. The same
record serves plan quota.

## What is stored

One row of `ai_cost_records` per provider call that answered, made inside a signed-in account's request:

| Column | Meaning |
| --- | --- |
| `account_id` | `users.id`, `ON DELETE CASCADE` — the record is the account's and goes with it |
| `occurred_at` | server time of the call |
| `feature` | the capability (`writing_review`, `speech_asr`, `agent_turn_fast`, ...) |
| `provider`, `model` | as already in the anonymous `ai.operation` telemetry |
| `cost_state`, `cost_usd` | the same estimate the telemetry carries (`ai/pricing.py`) |
| `input_tokens`, `output_tokens`, `audio_seconds` | the units the estimate was priced on |

Not stored: prompt, answer, transcript, audio, essay, any text. The anonymous `ai.operation` rows are unchanged.

## How it is written and swept

- `writing_coach/ai/platform.py` already sanitizes every telemetry event; `ai/account_costs.py` records it once
  more for the request's own account (`current_user_key()`), never an account passed as an argument. Local mode
  (`legacy`, `local-admin`) and failed calls are not recorded.
- One statement in the request path (`INSERT ... SELECT id FROM users WHERE user_key = ...`), bounded by
  `statement_timeout` 500 ms and `lock_timeout` 200 ms. Before the table exists, or on any database error,
  recording pauses for five minutes and then tries again: nothing a learner does ever fails because of it, and
  the code can ship before the migration.
- An administrator's provider test and configuration checks (`origin` `operator_test`, `configuration`) are not
  an account's spend and are not recorded.
- Retention: at most once a day per process, off the request thread, `delete_ai_costs_before()` removes rows
  older than 396 days in batches of 5,000 (at most 20 batches a sweep), oldest first. It deletes from
  `ai_cost_records` only. Deleting is idempotent, so several processes sweeping repeat work only. Unlike the
  agent.turn sweep it has no off switch: deletion at 13 months is the human's decision for this record, and it
  starts once the table exists. The sweep is started by a write, so an idle process does not sweep.
- Reads: `GET /api/admin/ai/costs/accounts` (administrator only; each look is written to the admin audit log)
  gives cost and calls per account, most expensive first, the top 100 with a `truncated` flag, over at most 90
  days. Admin > AI > AI cost shows it below the totals.

## Independent review

Delegated Architecture Reviewer (an independent Claude agent, read-only), 2026-10-05, on codex/work `50e66c2`
plus the uncommitted AC-2 files: **APPROVE WITH CONDITIONS**. Conditions met in the same change: a database
error pauses recording for five minutes instead of until restart (P2-1); one bounded statement instead of a
lookup plus an insert (P2-2); operator test calls are not recorded (P3-3); the sweep's lack of an off switch is
stated (P3-4); the list says when it is cut (P3-5). Left as is: an `INCLUDE (cost_usd)` index for quota sums
(P3-6), until quota reads this table. Remaining before promotion: the rehearsal on a copy of :8000, and the
human's authorization.

## Indexes and growth

`(account_id, occurred_at)` for one account's history and quota windows; `(occurred_at)` for totals and the
sweep. At 100,000 learners and ~30 calls a day the table holds ~1.2 billion rows at the 13-month bound;
before that scale, partitioning by month (dropping a partition instead of the batched delete) is the next
step and needs its own migration.

## Quota

The plan quota (commerce buckets, migration 0007, deployed inactive) settles units per meter. This record is
its evidence of spend, not the bucket itself: wiring quota enforcement is the billing slice (completion plan
item 4) and stays off until the human enables a plan.

## Rehearsal

`tests/test_ai_account_costs.py` applies and rolls back the migration on a throwaway PostgreSQL schema
(`ORENA_TEST_POSTGRES_URL`): record, report, sweep only old rows, no other table touched, cascade with the
account, downgrade. `scripts/product_migration_rehearsal.ps1` runs the chain on a copy of :8000 once the file is
promoted.
