# I2 schema proposal — architecture review

## Outcome: APPROVED WITH REQUIRED CHANGES

| | |
| --- | --- |
| Reviewer role | Delegated Independent Architecture Reviewer |
| Reviewer model | ChatGPT GPT-5.6 Sol |
| Reviewed commit | `69ceb5314e86161a23948cf215f21f1ffcb7d335` |
| Outcome | APPROVED WITH REQUIRED CHANGES |

Review was conducted outside the repository. Recorded here per AGENTS.md
"Architecture review authority": reviewer identity, reviewed commit and outcome
must be in Git.

### Response, per finding

Recorded against the revision. Nothing is applied; the migration is still in
`migrations/proposed/` and the live head is still `20260828_0004`.

| # | Done | How |
| --- | --- | --- |
| 1 | yes | `mutation_receipts.expected_version` is a column, written from the command and read back on retry. |
| 2 | yes | The receipt also persists `language_code`, `resource_id` and `domain`, and the historical command is rebuilt from those columns alone — no field comes from the request that is retrying. |
| 3 | yes | Derivation left the pure layer. `scope_of(account, incarnation, language)` now takes a resolved incarnation and refuses an empty one; `persistence/incarnation_repository.py` owns resolution, bootstrap, concurrent first use, the deletion barrier, explicit re-registration and epoch allocation under an account row lock. |
| 4 | yes | `language_provenance` is occurrences: uniqueness is over saved word, source and a focus digest; `source_revision` and a relation `version` are columns; availability defaults to `unknown`; parent scope is validated transactionally in `provenance_repository.py` under `FOR SHARE`, with separate cross-account and cross-language refusals, both tested. |
| 5 | yes | `ck_work_source_ref_integrity`: `(source_kind = '') = (source_id = '')`. |
| 6 | yes | Non-negative and positive checks on receipt expected/committed versions and sequence, change-record sequence and object version, work updated sequence, turn evidence version, and checkpoint sequence. |
| 7 | yes | `ix_change_records_pull` removed; the unique constraint provides the index. |
| 8 | yes | Eight, not seven. The count is corrected wherever it is stated as current. |
| 9 | yes | `WORK_KINDS` and `MUTATION_DOMAINS` in `work_contract.py`, with `validate_kind`/`validate_domain` refusing anything unregistered — exact match, no case or whitespace forgiveness — called before any write. No PostgreSQL ENUM. |

**Constraint applied to finding 3** (from the human, this revision): the pure
decision layer must not become a database-reading module. `account_profile.py`
imports nothing from `sqlalchemy`, `alembic`, `psycopg` or `writing_coach.persistence`,
and a test asserts that by parsing its imports rather than grepping its text.

**Constraint applied to finding 4** (from the human, this revision): do not
alter `saved_words` to manufacture a composite foreign key. It carries
`user_id` and `language_code` but no `UNIQUE (id, user_id, language_code)`, so a
composite key would require adding one to an existing owner table. The plain id
foreign key is kept and the parent scope is validated in the repository
transaction instead. The contract is met without widening the owner; if
review disagrees that this is safe enough, the schema question comes back
rather than the table being widened.

### Required changes, verbatim

1. `mutation_receipts` must persist the command's `expected_version`; it must
   not be reconstructed from retry input.
2. Historical receipt command identity must not be reconstructed from current
   request fields. Persist enough canonical command identity, or compare only
   persisted canonical command facts.
3. Complete the I1 → persisted incarnation seam. Current I1 derives incarnation
   from account identity/created_at, while the proposed schema uses a UUID
   incarnation row. Define safe bootstrap/resolution/re-registration,
   concurrent first use, deleted-incarnation refusal, and epoch allocation.
4. Redesign `language_provenance` so multiple occurrences of the same saved item
   in the same source are representable; retain source revision where known;
   add relation versioning; unknown origin must not default to available;
   enforce/validate saved-word account/language parent scope; test
   cross-account/cross-language rejection and repeated same-source/different-focus
   occurrence.
5. Add SourceRef integrity for `works`: source kind/id must be both present or
   both absent.
6. Add positive/non-negative constraints for receipt/change/evidence/checkpoint
   versions and sequences.
7. Remove the duplicate `change_records(incarnation_id, sequence)` index unless
   PostgreSQL evidence proves it is needed; the UNIQUE constraint already
   provides an index.
8. Correct proposal documentation from seven tables to eight.
9. `works.kind` and `mutation_receipts.domain` remain PostgreSQL strings backed
   by canonical application registries and strict validation; do not use
   PostgreSQL ENUMs.

### Gate

**Step 3 remains blocked until the revised proposal is re-reviewed.** The
migration stays in `migrations/proposed/`; nothing is applied and nothing moves
into `migrations/versions/`.

The proposal itself is unchanged by this record — it is deliberately a
docs/governance-only commit, so the reviewed artifact at `69ceb53` and the
findings against it can be verified against each other.

---

## The request as submitted, at `69ceb53`

Retained below as the artifact the findings were made against, including the
two questions the review answered: item 9 answers the enumeration question, and
items 1 and 2 answer the expected-version question — both more strictly than the
request proposed. It is a historical record, not the current state: its one
factual error, the table count, is marked in place rather than rewritten, and
its "nothing is applied" statement remains true.

---

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
| `migrations/proposed/20260908_0005_account_work_backbone.py` | Seven new tables. *(Miscount — it is **eight**; this is review finding 8. Left as written because this section is the artifact that was reviewed.)* Additive only; no existing table is altered, so old readers are unaffected. |
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
