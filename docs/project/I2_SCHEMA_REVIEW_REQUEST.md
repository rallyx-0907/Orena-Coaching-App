# I2 schema proposal — architecture review request for Codex/GPT-6

Raised by Opus under `ORENA_ACCOUNT_DATA_ARCHITECTURE` §6 step 2: *"Opus
proposes additive Alembic changes and adapters against this specification.
Codex reviews constraints, parent isolation, transactional receipts and
indexes."* Step 4's explicit schema/runtime authorization is separate and
belongs to the human.

**Nothing is applied.** The migration is in `migrations/proposed/`, which
Alembic does not read; the live head is still `20260828_0004` and the sandbox
starts against real PostgreSQL unchanged. Approving it is a `git mv` into
`migrations/versions/`.

## What is being proposed

| File | What it is |
| --- | --- |
| `migrations/proposed/20260908_0005_account_work_backbone.py` | Seven new tables. Additive only; no existing table is altered, so old readers are unaffected. |
| `writing_coach/work_contract.py` | Pure decisions around the aggregate: lifecycle, conversation head, conflict branches, snapshot paging, stream contiguity. 26 stdlib counterexamples. |
| `writing_coach/persistence/work_repository.py` | The transactional seam. No caller is wired to it. |
| `tests/test_orena_work_persistence_postgres.py` | Ten concurrency cases against real PostgreSQL, skipped unless `ORENA_TEST_POSTGRES_URL` is set. |

Tables, in the order the migration order requires — incarnation, receipt and
stream primitives first, then work, then what reads on top:

`account_incarnations`, `account_streams`, `mutation_receipts`,
`change_records`, `works`, `work_turns`, `language_provenance`,
`projection_checkpoints`.

## The four things review is asked to check

### 1. Constraints

- `account_incarnations`: `epoch >= 1`; `status IN ('active','deleted')`; and
  `(status = 'deleted') = (deleted_at IS NOT NULL)` so the two cannot drift.
  `user_id` is `ON DELETE RESTRICT`, not CASCADE — a deleted incarnation is the
  barrier, and a cascade would remove the thing denying reactivation.
- A **partial unique index** on `user_id WHERE status = 'active'` enforces at
  most one active incarnation per account.
- `works`: `version >= 1`, `lifecycle IN ('active','completed','deleted')`.
- `work_turns`: `ordinal >= 1`, `author_role IN ('learner','partner')`, and a
  check that the evidence triple is all-present or all-absent, so a turn cannot
  claim half an evidence reference.
- `change_records`: `change_kind IN ('upsert','delete')`.
- `language_provenance`: `availability IN ('available','unknown','unavailable')`
  — missing provenance stays *unknown* rather than being asserted as absent.

**Question for review:** should `works.kind` and `mutation_receipts.domain` be
constrained to enumerations here, or left open so a new domain does not need a
migration? They are unconstrained strings in the proposal.

### 2. Parent isolation

`works` carries `UNIQUE (id, incarnation_id, language_code)` purely so that
`work_turns` can hold a **composite foreign key** on all three columns. A turn
therefore cannot be attached to a work in another incarnation or another
language even if the caller supplies a valid work id — opaque IDs alone give no
access, and the database enforces it rather than the service remembering to.
`tests/…_postgres.py::test_a_turn_cannot_be_attached_across_a_language` is that
case.

Everything else hangs off `incarnation_id`, not `user_id`, so a recreated
account inherits no work, no receipts and no cursors.

### 3. Transactional receipts

`UNIQUE (incarnation_id, domain, operation_id)` is the scoped operation
identity. In `commit_mutation` the order inside one transaction is: lock the
stream head → recheck the incarnation is still active → **look up the receipt
before comparing versions** → lock the work row → decide → write domain row,
change record and receipt together.

Receipt-before-version is the part worth checking: a retry whose acknowledgment
was lost must get its original result, not a conflict against the version its
own first attempt produced. `request_digest` is a guard against reusing an
operation id with different input; it is deliberately **not** the identity,
because two distinct attempts are not one operation merely because their text
matches.

**Question for review:** the proposal reconstructs the receipt's original
`expected_version` from the current command when comparing. That is sound for
single-step versions but assumes one command advances a work by exactly one.
Should the receipt store the expected version it was issued against
explicitly?

### 4. Indexes

- `works (incarnation_id, language_code, updated_sequence, id)` — the work-list
  page, with `id` as the cursor tie-break.
- `change_records (incarnation_id, sequence)` and `UNIQUE (incarnation_id,
  sequence)` — the pull, and the ordering guarantee enforced rather than
  assumed. Language is a column, **not** a leading key, because a language
  filter must not skip changes in another language; `changes_after` reads the
  whole account stream.
- `mutation_receipts (incarnation_id, sequence)` — oldest-first for compaction.
- `language_provenance (incarnation_id, language_code, saved_word_id)`.

**Not yet indexed:** `account+language+due` for recall. That belongs to the
existing `saved_words` owner, which this migration does not touch.

### 5. Concurrency and migration safety

The concurrency proof covers the I2 rows of the acceptance matrix: two edits
from one version (one commits, one conflicts, both texts retained, nothing
merged); a lost acknowledgment replaying with no second change record; an
operation id reused with different input; a stalled transaction holding the
stream head so the next writer waits rather than allocating past it, verified
by `sequence_is_contiguous`; a snapshot watermark plus changes covering each
change exactly once; the stream not being filtered by language; writes refused
after deletion; and a recreated incarnation starting its own stream and seeing
none of the old work.

Migration safety: additive only, single linear head once moved, and a
`downgrade()` that drops in dependency order. It has **not** been executed —
running it is §6 step 3, after this review.

## What Opus is not deciding

Retention days, receipt/tombstone horizons, hard-deletion policy and any
commercial value. Absent policy leaves destructive purge disabled, as the
architecture requires.

## Requested outcome

Approve, or name the constraint, isolation, receipt or index changes wanted.
On approval Opus runs §6 step 3 against a throwaway database and returns to the
human for step 4 authorization before anything is moved into `versions/`.
