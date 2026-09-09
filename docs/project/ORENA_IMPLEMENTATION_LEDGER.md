# Orena implementation ledger — I1 to I7

Implementation under the locked GPT-6 backbone (`27edeb0`). Sequence and exit
gates come from `ORENA_BACKBONE_INTEGRATION_GATES.md`; this file records what
was actually built, what it is verified against, and what each package
deliberately left gated. Package F remains human acceptance and is not claimed
here by anyone.

Owner: Opus, implementation. Architecture questions go back to Codex/GPT-6
rather than being answered by inventing a contract.

---

## I1 — Account, learner profile and preferences

**Specification:** `ORENA_ACCOUNT_DATA_ARCHITECTURE` §§1-3.
**Exit gate:** scoped read/patch and logout/incarnation scenarios; no theme WIP
edits.
**Status:** implemented, ungated adapters only. Amended by I2 review
finding 3: incarnation resolution moved out of the decision layer.

### What a learner gets

Saving one preference no longer rewrites the others, and two devices editing
preferences no longer silently overwrite each other. The endpoint that existed
took a whole profile with a default for every field, so a client sending only
the setting it meant to change reset the rest to product defaults — and the web
client's read-modify-write meant whichever save landed second won, with no sign
that anything was lost. A save now names only what it changes, against the
version it read; a save made against a version someone else has already moved
is refused, the current values are fetched and shown, and applying again is the
learner's decision rather than an automatic overwrite.

### What was built

`writing_coach/account_profile.py` — pure decisions, no storage or session:

- **Scope** is `reference_backbone.Scope`, not a second shape meaning the same
  thing. `scope_of(account, incarnation, language)` takes three server-verified
  facts and infers none of them; any missing one is refused, because
  language-scoped resources authorize on account and language together.
- **Incarnation** is server-owned and *resolved elsewhere*. It was originally
  derived here from the account's id and creation time; review finding 3 was
  that this made a module with no database the authority on an identity fact it
  cannot see, and that it could not express the deletion barrier at all,
  because a barrier is a stored row. Resolution, bootstrap, concurrent first
  use, the barrier and re-registration now live in
  `persistence/incarnation_repository.py`, and this layer receives the
  resolved value.
- **Effective settings** as `{value, source, version}` with the documented
  precedence — session override, saved preference, declared default. A stored
  value that is no longer valid falls back to the default and *says so* rather
  than being served as though the learner had chosen it.
- **Defaults** live in the registry, not in room constants. Support language
  resolves through `core/support_languages` rather than a second copy of the
  rule.
- **Patch semantics**: named fields only; an absent field keeps its saved
  value; an unsupported field, an invalid value, an empty patch and a stale
  version each refuse and write nothing, with a stable reason key so a surface
  can say something true in either interface language.

Runtime seam in `writing_coach/becoming_memory.py`, `PATCH
/api/learner-profile` in `app.py`, `patchLearnerProfile` in the web client.

### Deliberate limits

- **No schema.** The profile has no version column and none is authorized, so
  the concurrency token is the record's own `updated_at`. `patch_profile`
  compares versions for equality and cannot mint a non-integer successor, so
  the caller supplies it — the module does not hold a clock.
- **Two settings in the contract have no column**: a declared target level and
  an account-wide interface language. Both are declared in the registry, both
  read and override correctly, and a patch for either is refused as
  `not_yet_stored` rather than accepted and dropped on the way to the
  repository. They need the gated additive migration.
- **The durable deletion barrier is not implemented.** Incarnation changes
  correctly on recreation; denying reactivation until an explicit
  re-registration flow needs storage that is not authorized here.
- **Theme untouched.** `theme_preset` is read and written back unchanged and is
  not a member of the settings registry, per the gate's "no theme WIP edits"
  and the architecture's reservation of theme presentation to its own owner.
- **`PUT /api/learner-profile` is unchanged**, because `mobile/` calls it and
  native is frozen. Its whole-profile replace semantics are documented at the
  endpoint. The web client no longer uses it.

### Evidence

- `scripts/test_orena_account_profile.py` — 32 stdlib counterexamples, CI
  registered. Scope derivation and refusal, incarnation change on recreation,
  results refused across account/incarnation/language, precedence and invalid
  fallback for effective settings, account-wide versus language-scoped
  membership, and every patch refusal.
- `tests/test_orena_account_profile_runtime.py` — 9 pytest cases over the
  repository seam with a fake profile repository: the flat shape existing
  surfaces consume survives, a patch preserves what it does not name, the
  version advances, a stale writer gets 409 and writes nothing, theme preset is
  untouched, and an absent profile is created from the empty version.
- Browser at `127.0.0.1:8011`: read returns `{value, source, version}` per
  setting; a patch naming `pinyin` leaves goal, style and theme preset intact;
  a write against a moved version returns 409 `version_conflict` and changes
  nothing; the preferences dialog saves normally, and on a concurrent change
  keeps the other writer's value, refreshes itself and lets the learner apply
  again.
- Python suite in the app image: 799 passed / 20 failed. The 20 are the
  inherited governance-document failures recorded in `CURRENT_HANDOFF.md`;
  failure sets are byte-identical to a clean `git archive HEAD` tree, so this
  package adds 9 passing tests and no regression.
- 32 Node gates pass, ESM graph 51 modules, both validators OK. `ruff check`
  clean on both touched Python modules; the two findings in `app.py` are
  present at HEAD and are not from this change.

### Open for GPT-6

Nothing blocking. Two contract items are storage-gated rather than unclear, and
are named above so the migration slice knows what is waiting for it.


---

## I2 — Work persistence, sync and lifecycle

**Specification:** `ORENA_ACCOUNT_DATA_ARCHITECTURE` §§3-7.
**Exit gate:** I1; reviewed additive schema, receipts, cursor/snapshot and
PostgreSQL concurrency proof.
**Status:** in progress. Migration-order item 1 is done. The schema proposal
passed independent architecture review at `6cc3dc1` after three rounds:
**§6 step 2 APPROVED**, and step 3 authorized against an isolated scratch
PostgreSQL database only. **Step 3 has now run and passed**: upgrade from the
live head, 42 PostgreSQL cases, concurrency and isolation, and a rollback
rehearsal that dropped all eight tables and left the owner tables and their
rows intact. Evidence in `I2_SCHEMA_REVIEW_REQUEST.md`. Steps 4 onward — schema
authorization and any activation — remain the human's and are untouched.

### Item 1 — startup verifies the schema, it does not create one

`_verify_runtime_readiness` ran `alembic upgrade head` whenever it found an
empty database. The first process to connect therefore built a schema wherever
it was pointed, so a deployment aimed at the wrong database created one there
instead of refusing, and no operator ever chose the moment. This is the tracked
P1 named as item 1 of the migration order, and it contradicted both the
architecture ("Startup only verifies schema", "Add schema through an operator
command") and the standing persistence invariant against automatic startup
Alembic.

Startup now classifies what it found and refuses everything except a database
already at the expected revision:

| State | What it means | What happens |
| --- | --- | --- |
| `ready` | revision matches the build | serve |
| `empty` | no revision and no tables | refuse, naming the operator command |
| `mismatch` | wrong revision, or tables with no revision at all | refuse, reporting both revisions and saying to check which database this is |
| `unavailable` | could not be read | refuse, and say it is connectivity, not schema |

Tables without an Alembic revision are a mismatch rather than an empty
database: that is somebody else's schema, or a half-applied one, and creating
tables on top of it is the worst available move. Only the empty refusal names
the bootstrap command, because it is the only state where creating a schema is
the right next step.

`scripts/bootstrap_runtime_schema.py` is that command. It reports before it
acts, requires `--confirm`, refuses anything that is not empty, and verifies
the result. Existing operator tooling is untouched: `postgres_shadow.py` still
builds a shadow database and the cutover rehearsal still verifies the head.

**Evidence.** `scripts/test_orena_runtime_schema.py` — 13 stdlib cases, CI
registered: the four states, that each refusal says the right thing and only
the empty one points at the command, and that `runtime.py` contains no
migration call at all. `tests/test_persistence_runtime.py` was rewritten to the
new contract — the previous version asserted that startup *did* migrate an
empty database, which is the behaviour the architecture forbids; the rewrite
holds all four states and both "no bootstrap" cases. 14 pass. Full suite 797
passed / 20 failed, failure set byte-identical to a clean `git archive HEAD`.

### The additive schema proposal — reviewed, changes required

`ORENA_ACCOUNT_DATA_ARCHITECTURE` §6 step 2 is done. The proposal at `69ceb53`
was reviewed outside the repository by a **Delegated Independent Architecture
Reviewer (ChatGPT GPT-5.6 Sol)**, whose outcome was **APPROVED WITH REQUIRED
CHANGES**. The nine required changes are recorded verbatim in
`I2_SCHEMA_REVIEW_REQUEST.md`, with the request as submitted retained beneath
them. All nine were addressed; two further re-reviews followed, and the final
verdict at `6cc3dc1` approved step 2 and authorized step 3.

Eight additive tables in
`migrations/versions/20260908_0005_account_work_backbone.py`: account
incarnation with its deletion barrier, the per-incarnation stream head,
mutation receipts, change records, the work aggregate, work turns, kept-language
provenance and projection checkpoints. `work_contract.py` holds the decisions
around the aggregate (26 stdlib counterexamples, CI registered) and reuses
`reference_backbone.mutation_decision` rather than restating it;
`persistence/work_repository.py` is the transactional seam and no caller is
wired to it.

**It was held outside `migrations/versions/` until it was authorized.** Startup
refuses any database that is not at the expected head, so merging an unapproved
migration into the live chain would have made every environment refuse on its
next restart — approving it by accident, in exactly the way the verification
exists to prevent. It sat in `migrations/proposed/`, which Alembic does not
read, and the PostgreSQL fixture reached it by adding that directory to
`version_locations` explicitly. Approving it was one `git mv`, and that is what
step 4 was: the file is in the live chain now, and the fixture runs the
unmodified chain the way a deployment does.

Ten concurrency cases in `tests/test_orena_work_persistence_postgres.py` cover
the I2 rows of the acceptance matrix — two edits from one version, lost
acknowledgment replay, operation-id reuse, a stalled transaction holding the
stream head, snapshot-plus-changes covering exactly once, the stream not being
language-filtered, writes after deletion, and a recreated incarnation starting
its own stream. They skip unless `ORENA_TEST_POSTGRES_URL` is set. Executed
under §6 step 3 against an isolated scratch database, and re-executed against
the live chain after deployment: 42 cases, all passing.

The two questions raised for the reviewer were both answered, and more strictly
than the request had proposed: `works.kind` and `mutation_receipts.domain` stay
PostgreSQL strings backed by canonical application registries and strict
validation rather than becoming PostgreSQL ENUMs, and a receipt must persist the
expected version it was issued against rather than have it reconstructed.

### The revision — all nine findings addressed

Two constraints came with the work. The pure decision layer must not become a
database-reading module, so incarnation resolution went to a persistence
adapter and `scope_of` receives the resolved value. And `saved_words` must not
be altered to manufacture a composite foreign key, so provenance keeps the
plain id key and validates parent scope inside the transaction instead.

- **1, 2 — receipts.** `expected_version`, `language_code`, `resource_id` and
  `domain` are all persisted, and a retry is compared against those columns
  alone. Rebuilding any part of a historical command from the request that is
  retrying compares a field with itself, so a changed one passes as a match.
- **3 — the incarnation seam.** `writing_coach/persistence/incarnation_repository.py`
  resolves, bootstraps epoch 1, survives concurrent first use through the
  partial unique index by reading the winner rather than retrying, refuses a
  deleted account with `DeletionBarrier` instead of resurrecting it, and
  allocates the next epoch on explicit re-registration under an account row
  lock. A new incarnation gets its stream head in the same transaction, because
  an incarnation without one is an account that cannot be written to.
- **4 — provenance as occurrences.** Uniqueness over saved word, source and a
  focus digest, so the same word met twice in one source with different focus
  is two occurrences and the identical occurrence twice is not. `source_revision`
  retained where known, relation `version` added, availability defaulting to
  `unknown` rather than asserting a reachability nobody checked. Parent scope is
  validated under `FOR SHARE` on the saved word, with cross-account and
  cross-language refused separately and both tested — a check in code rather
  than in a constraint is only as good as the test holding it there.
- **5, 6 — integrity.** A SourceRef is both halves or neither, on `works` and on
  provenance; versions and sequences carry positive or non-negative checks
  throughout.
- **7 — index.** The duplicate removed; the unique constraint is the index.
- **8 — eight tables**, not seven. The miscount was mine.
- **9 — registries.** `WORK_KINDS` and `MUTATION_DOMAINS` with exact-match
  validation called before any write. Strings in the column so a new domain is a
  code change; strict validation so "string" does not quietly mean "anything".

Fifteen further PostgreSQL cases were added for findings 3 and 4, bringing that
file to 25. They still skip without `ORENA_TEST_POSTGRES_URL` and still have not
been executed.

### Re-review corrections

`0a1a0a5` came back CHANGES REQUIRED. Six corrections, all made and recorded in
`I2_SCHEMA_REVIEW_REQUEST.md`. Two changed the design rather than a detail.

**An occurrence is an event, so nothing may be unique over its content.** The
revision had made provenance unique over saved word, source and focus digest,
which still collapsed two identical attachments into one. That constraint is
gone: identity is the row id, and a schema cannot tell a retry from a second
attachment because they look the same.

**So deduplication became the operation's job.** Attaching provenance is now a
mutation through the receipt and change-stream contract, with a caller-supplied
occurrence id and an operation id. A retry replays its occurrence; a genuinely
different operation with identical content creates another. Both halves are
true at once, which no constraint could achieve.

That put two repositories on the same transactional path, so the envelope moved
to `persistence/mutation_commit.py`: stream lock, account re-resolution, receipt
comparison, decision, then sequence, domain write, change record and receipt.
Each domain supplies only how to read its state and how to write its row.
Keeping two copies would have let them drift, and the drifted one would be
whichever nobody was reading.

The account is now re-resolved from the incarnation row and a mismatch is
refused before any receipt is read, so a request cannot supply the account half
of the identity its own replay is compared against.

### Final re-review corrections

`728a8df` came back CHANGES REQUIRED on two blockers, both in the adapters
rather than the schema, so the migration did not change.

**The provenance digest was missing `availability`.** It is written to the row,
so an operation id reused with a different availability matched the digest and
replayed - reporting success for a value that was never stored. Every input
that reaches the row is in the digest now.

**And resource scope was assumed rather than read.** The envelope passed the
request's own scope in as the resource's, so the scope check compared a value
with itself and could never fire: a work id owned by another incarnation looked
absent, creation went ahead, and the answer a caller got was a primary key
violation. `load` now returns the resource's persisted version, deletion and
scope - joined to `account_incarnations` so the owning account is fact rather
than claim - and the four cases separate properly: another account's id is
denied, another language's id is denied, an existing id in the caller's own
scope is a version conflict carrying the server's payload, and a reused
provenance occurrence id is inspected instead of assumed free.

A raw integrity error is not an answer. Every one of those situations now
returns something a caller can act on.

### Activation preparation — complete and reversible

Everything I2 needs before the human's §6 step 4 decision, and nothing that
would pre-empt it. `I2_ACTIVATION_RUNBOOK.md` is the canonical document.

**The operator command could not do the job.** It created a schema in an empty
database and refused everything else, which is not the activation path — the
runtime database has data and sits at `20260828_0004`. It now has an explicit
`--upgrade --from <revision> --confirm` mode. `--from` is the safeguard: the
operator states the revision they believe the database is at, and the command
stops if it differs, because that mismatch usually means the connection string
points somewhere unexpected.

**Backup and restore** is `scripts/runtime_backup.py` — capture, verify, and a
rehearsal that restores into a separate database and compares revision and row
counts against the source before dropping it. A backup nobody has restored is a
hope. Rehearsed: 41,181-byte dump, 98 entries, every count matched. It also
surfaced an operational fact worth knowing before a migration night rather than
during one: **the application image does not ship `postgresql-client`**, so the
script says where to run it instead of failing with a traceback.

**The runtime wiring exists and is off.** `account_backbone.py` has three
states, not two: `disabled` is a product decision, `unavailable` is a fault, and
a surface may say "your drafts stay on this device" for the first and must not
for the second. Both the flag and the schema are required, so a migration
applied ahead of a deploy changes nothing on its own — which is what lets the
schema decision and the activation decision be separate.

**Deployment order is a real constraint, and both wrong orders fail closed.**
Startup verifies against the build's head, so migrating without deploying and
deploying without migrating each refuse to start. That is the behaviour to
want, but the window is real and belongs in a plan rather than in a discovery.

**Rollback is free exactly once.** The downgrade drops the eight tables and does
not cascade into owner tables — proven with data present. Once the backbone
holds authoritative work, that same downgrade destroys it, and rollback becomes
a data-loss question. The last moment rollback is free is the moment before
activation.

**Compatibility verified end to end** on a throwaway copy of the tree with the
migration in `versions/`, against a scratch database seeded to the live head:
the un-migrated refusal names both revisions, every operator safeguard fires,
the migration applies, the app starts and serves `/`, `/api/learner-profile`
and `/api/dashboard`, pre-existing rows survive, and the backbone reports
`disabled` at rest and `active` only with the flag. Both scratch databases were
dropped. That rehearsal is what the real deployment then repeated.

**Five policy inputs are absent and every one has defined behaviour** rather
than a guess. Two of them — restore suppression after deletion, and retention —
do not block this milestone but must be answered before sync or deletion is
enabled, because without them a restore can reinstate work a learner deleted
and nothing is ever purged.

### §6 step 4 — schema deployed to the sandbox, flag off

Authorized by the human as *apply the schema and deploy, but keep
`ORENA_ACCOUNT_BACKBONE=off`* — deliberately not the same decision as switching
it on, and deliberately not taken in the same window as the migration.

Done in the runbook's order. Backup captured from the sandbox runtime and
verified (49,784 bytes, 98 restorable entries), then rehearsed into a separate
database, which came back matching on revision and on every compared count —
`users` 1, `user_language_profiles` 2, `saved_words` 5, `speaking_attempts` 2,
`listening_progress` 10. Then `git mv` into `versions/`,
`bootstrap_runtime_schema.py --upgrade --from 20260828_0004 --confirm`, which
applied `20260828_0004 → 20260908_0005` and reported `ready`, and a restart of
`orena-foundation-web` in the same window.

After it: the sandbox serves `/`, `/api/learner-profile` and `/api/dashboard`
at 200; the head is `20260908_0005`; the 19 pre-existing tables and every
learner row are unchanged; the eight new tables exist and are empty; the
backbone reports `disabled`, because nothing sets the flag. The 42 PostgreSQL
concurrency cases were re-run against the live chain rather than against a
patched `version_locations`, and pass.

**Sandbox only.** This was applied to `orena-foundation-web` at 127.0.0.1:8011,
the runtime `CURRENT_HANDOFF.md` names. Production (8000) and preview (8010)
are human gates, were not named in the authorization, and were not touched.

Drafts, conversation turns and continuation still live only in device memory;
`Essay`/`EssayRevision` still own the immutable submitted snapshot and its
evaluator result, and those evidence owners do not move. The tables that would
hold the rest now exist and nothing writes to them.

The remaining gate is step 9, `ORENA_ACCOUNT_BACKBONE=on`, and the write-path
integration that follows it. Rollback is free until then and stops being free
the moment the backbone holds authoritative work. Activation is not Opus's to
declare.
