# I2 activation runbook

Everything activation needs, prepared ahead of the decision and then used for
it. `ORENA_ACCOUNT_DATA_ARCHITECTURE` §6 step 4 — explicit schema and runtime
authorization — is the human's, and this document exists so that the decision
is about the risk rather than about the unknowns.

Architecture review of the proposal is complete: §6 step 2 APPROVED at
`6cc3dc1`, step 3 executed and passed. See `I2_SCHEMA_REVIEW_REQUEST.md`.

## Status

**Step 7 done, step 9 not.** The human authorized *apply the schema and deploy,
but keep `ORENA_ACCOUNT_BACKBONE=off`*. The migration is in
`migrations/versions/`, the **sandbox** runtime (`orena-foundation-web`,
127.0.0.1:8011) is at `20260908_0005`, and the backbone reports `disabled`. §7
records the run.

**Production (8000) and preview (8010) were not touched.** They are human gates
under `ARCHITECTURE_INVARIANTS.md`, the authorization did not name them, and
deploying there is a separate decision that has not been made or asked for.

---

## 1. Policy inputs

These are values only the human can supply. **D-054 (2026-09-13) answered the
two that gated activation**: deletion is permanent, a restore never brings a
deleted account back, and re-registration is a new incarnation. The retention
durations are decoupled as operational/legal policy and do not block I2; while
absent, the behaviour below stands.

| Input | Needed for | Behaviour while absent |
| --- | --- | --- |
| Retention period by data class | destructive purge of deleted work | Purge is not implemented and cannot run. Deletion writes a tombstone and increments a version; nothing is erased. |
| Receipt/tombstone horizon | receipt compaction | No compaction. Receipts accumulate, which is correct but unbounded — see the operational note below. |
| Restore suppression — **answered, D-054** | restoring after a deletion | Never restore a deleted account. Before a restored database serves, every incarnation deleted after the backup is marked deleted again (`runtime_backup.py` restore path). Backup expiry itself is retention, below. |
| Deletion barrier retention — **answered, D-054** | how long a deleted incarnation blocks reactivation | Permanent for that incarnation. Re-registration allocates a new one. |
| Legal/regulatory retention obligations | all of the above | None assumed. No duration is invented anywhere in the code. |

**The input that gated activation is answered.** Without a
restore-suppression policy a restore could reinstate work a learner deleted;
D-054 settles it as never. Without retention durations nothing is purged,
which is safe: deleted data is never served, only kept until an
operational/legal retention policy exists to purge it.

Not required for I2 and listed so their absence is not mistaken for an
oversight: plan/price/grace/meter policies (I3), achievement and pedagogical
policies (I6), provider credentials (I5).

---

## 2. Backup and restore

`scripts/runtime_backup.py`, five modes: `capture`, `verify`, `rehearse`, and the
two that keep deletions deleted, `deletions` and `suppress` (below).

**The application image does not ship `postgresql-client`.** It is a Debian
base without it, so `pg_dump`, `pg_restore` and `psql` are absent and the
script says so rather than failing with a traceback. Install them into an
ephemeral container, as below, or run from an operator environment that has
them. This is an operational fact worth knowing before the night of a
migration rather than during it.

**And a dump written inside that ephemeral container dies with it.** Not
hypothetical: the real pre-I2 backup was written to `/tmp` in a
`docker run --rm`. It captured, verified and rehearsed successfully, and
ceased to exist the moment the container exited — every check passed and the
backup was still gone. `capture` therefore refuses `/tmp`, `/var/tmp` and
`/dev/shm` unless `--allow-ephemeral` states the dump is being copied out
before exit, and with no `--out` it writes a timestamped file under
`backups/`. That directory is gitignored: a dump holds learner data and is
never committed.

The repository is mounted read-only, so `backups/` needs its own writable
mount. Complete, and as actually run:

```
docker run --rm --network orena-foundation-review \
  -e POSTGRES_RUNTIME_URL="postgresql+psycopg://postgres@orena-foundation-postgres:5432/postgres" \
  -v "<repo>:/workspace:ro" \
  -v "<repo>/backups:/workspace/backups" \
  -w /workspace ai-writing-coach:local \
  sh -lc "apt-get update -qq && apt-get install -y -qq postgresql-client && \
          python scripts/runtime_backup.py capture"
```

Then, against the file it names:

```
python scripts/runtime_backup.py verify   --dump backups/<file>.dump
python scripts/runtime_backup.py rehearse --dump backups/<file>.dump \
    --into orena_restore_rehearsal
```

`rehearse` restores into a **separate** database and compares the Alembic
revision and the row counts of eight owner tables against the source, then
drops the target. It refuses to restore over its own source. A backup nobody
has restored is a hope, not a backup, so the rehearsal is not optional in §5.

Rehearsed against a seeded copy: 41,181-byte dump, 98 restorable entries,
restore matching the source on revision and on every compared count. Then run
for real before the deployment: 49,784-byte dump of the sandbox runtime, 98
entries, restore matching on revision and on all eight counts — `users` 1,
`user_language_profiles` 2, `saved_words` 5, `speaking_attempts` 2,
`listening_progress` 10.

Re-verified after the destination fix, against the deployed sandbox: `capture`
with no `--out` wrote `backups/orena-20260909T231447Z.dump` (62,478 bytes,
140 restorable entries — more than the earlier 98 because the eight backbone
tables now exist), the file was still on the host after the container exited,
and `capture --out /tmp/...` was refused with the reason instead of silently
obliging.

### A restore reapplies every deletion before it serves (D-054)

Deleting an account is permanent, so a backup taken before a deletion must not
bring the account back. Two more modes carry that:

```
python scripts/runtime_backup.py deletions --out backups/deletions-<when>.json
python scripts/runtime_backup.py suppress  --into <restored database> \
    --deletions backups/deletions-<when>.json [--deletions <older journal> ...]
python scripts/runtime_backup.py suppress  --into <restored database> --check \
    --deletions backups/deletions-<when>.json [--deletions <older journal> ...]
```

The order of an incident restore is fixed: **export the deletion journal from
the database being replaced, restore, `suppress`, verify, and only then
serve.** `deletions` writes every deleted incarnation (opaque ids and times,
no content) to a journal outside any database, so the restore cannot take it
back; keep it with the same access control as backups. `suppress` makes each
record hold in the restored database in a single transaction - all or
nothing - and reports `reapplied` (active there, deleted again),
`already_deleted`, `barrier_restored` (the account is there but the
incarnation row is not, as in a backup older than the account's incarnation
rows; the barrier row is put back with the same id, epoch and times, so sign-in
meets it instead of starting a fresh incarnation) and `absent` (the account is
not in the restore at all, so nothing of it can be served or signed in as). It
never sets anything active, and it stops without changing anything if a
journal is unreadable, or names an incarnation under another account or epoch,
or an epoch the restore gives to a different incarnation. The verify step is
`suppress --check`: it writes nothing, prints each record that does not hold,
and exits non-zero until none remain; serve only after it exits 0.
`rehearse --deletions <journal>` suppresses inside a rehearsal.

When `suppress` stops on a disagreement, the restore is not served. The
message names the incarnation or account and what disagrees: the same id
under another account or epoch means the journal and the backup are from
different deployments (check which database each came from); an epoch taken
by a different id means someone signed in to the restored database before
suppression ran, which the fixed order above forbids - stop serving it,
restore again, and suppress before anything else touches it. Do not edit a
journal to make it pass; it is the one record of the deletion.

If the database being replaced cannot be read at all, the journal is only as
recent as its last copy - which is why the account-deletion workflow, when it
is built, must also append each deletion to an out-of-database journal as it
happens. That workflow (removing an account's rows from owner tables keyed by
account, not incarnation) is not built and is a destructive lifecycle change
that needs its own independent review; after a restore it must be replayed
too. Until both exist no runtime path deletes or re-registers an account -
the hard gate in `ORENA_BACKBONE_INTEGRATION_GATES.md`, enforced by a test.

Proven against a scratch database (`tests/test_deletion_journal.py`): an
incarnation deleted after the backup comes back `active` in the restore and is
deleted again by `suppress`; an account restored without its incarnation row
gets its barrier back; `--check` reports both before and nothing after; sign-in
then meets the deletion barrier; re-registration still gets a new incarnation
that the journal does not touch; a journal naming an account the restore never
had reports it `absent`; an identity disagreement (another account, another
epoch, an epoch taken) changes nothing. Backups are access-controlled
operational copies and are never account sync authority.

---

## 3. Operator migration

Startup verifies the schema and refuses; it never migrates. The only thing that
migrates is `scripts/bootstrap_runtime_schema.py`, and it has two modes because
creating a schema where none exists and migrating a database with a learner's
work in it are different risks.

```
python scripts/bootstrap_runtime_schema.py
    report only, always safe

python scripts/bootstrap_runtime_schema.py --confirm
    create the schema in an EMPTY database

python scripts/bootstrap_runtime_schema.py --upgrade --from 20260828_0004 --confirm
    migrate a database that already has data
```

`--upgrade` requires `--from`: the operator states the revision they believe
the database is at, and the command stops if it is at a different one. That
mismatch usually means the connection string points somewhere unexpected, which
is exactly the moment not to run a migration. Without `--confirm` it reports
what it would do and reminds you to take a backup.

Plain `--confirm` refuses a database that has data, and says to use `--upgrade`.

---

## 4. Deployment order, and what happens if it is wrong

Moving `20260908_0005` into `migrations/versions/` changes what every process
expects. Startup then verifies against the new head, so **the migration and the
deploy are one change, not two**.

| Order | Result |
| --- | --- |
| Migrate, then deploy | Old build sees a revision ahead of its own → refuses to start. Downtime between the two steps. |
| Deploy, then migrate | New build sees a revision behind its own → refuses to start. Downtime between the two steps. |
| Both together, in one window | The only order without a refusal. |

Both wrong orders **fail closed** — they refuse rather than serving against a
schema they do not understand — which is the behaviour to want, but it means
the window is real and should be planned rather than discovered. Verified in
§7: the new build against an un-migrated database refuses with both revisions
named.

### Rollback

The migration is additive and its `downgrade()` drops the eight tables in
dependency order. Rehearsed in Step 3 with data present: revision returned to
`20260828_0004`, the eight tables gone, the 19 pre-existing tables intact, and
`saved_words` and `users` rows still there — **the downgrade does not cascade
into owner tables**.

```
# roll the code back first, then the schema
python scripts/bootstrap_runtime_schema.py            # confirm what it is at
alembic downgrade 20260828_0004                       # operator, deliberately
```

Rolling back is safe **only while the backbone has never been active**. Once it
holds authoritative work, `downgrade()` destroys that work, and rollback stops
being a schema question and becomes a data-loss question. That line is worth
naming now: the last moment rollback is free is the moment before activation.

### Forward repair

Preferred over rollback once anything real is stored. The additive shape means
a defect in the new tables can usually be corrected by a further additive
migration without touching the existing owners, which is why nothing in
`20260908_0005` alters an existing table.

---

## 5. Activation checklist

Ordered. Steps 1–6 are reversible; step 7 is the gate. Steps 1–8 are **done**
for the sandbox runtime; step 9 is outstanding.

1. **Policy inputs recorded** — §1 answered, or explicitly deferred with the
   consequence accepted (no purge, no sync, restore unsafe after deletion).
2. **Backup captured and verified** — `capture` then `verify`.
3. **Restore rehearsed** — `rehearse` into a separate database, revision and
   counts matching. Not skippable.
4. **Migration rehearsed on a copy** — restore the backup into a scratch
   database and run `--upgrade --from 20260828_0004 --confirm` there first.
   Done in Step 3 against synthetic data; do it once against a copy of the real
   database before the real one.
5. **Deploy window agreed** — §4; both wrong orders refuse to start.
6. **`git mv migrations/proposed/20260908_0005_account_work_backbone.py
   migrations/versions/`** — the moment the build's expected head changes.
   Reversible until deployed.
7. **HUMAN GATE — apply to the runtime database and deploy together.**
   Irreversible in the sense that matters: from here rollback costs the window,
   and after activation it costs data. **Done for the sandbox**, migration and
   restart in one window; §7 has the output.
8. **Verify at rest** — the backbone reports `disabled`, because the flag is
   still off. Nothing writes through it. **Confirmed.**
9. **HUMAN GATE — set `ORENA_ACCOUNT_BACKBONE=on`.** A separate decision from
   the schema, deliberately: the schema can be present and correct for as long
   as you like before anything uses it. **Not done, and not asked for.**

Steps 7 and 9 are the two irreversible ones and they are separate on purpose.
Applying the schema changes nothing a learner sees; the flag does.

---

## 6. Runtime wiring

`writing_coach/account_backbone.py` holds the switch and the three states:

- `active` — flag on **and** all eight tables present;
- `disabled` — flag off, the default and today's answer;
- `unavailable` — flag on, tables absent.

`disabled` is a product decision and `unavailable` is a fault, and a surface may
say "your drafts stay on this device" for the first and must not for the
second. The repositories are constructed only when `active`; otherwise nothing
engine-bound is built and `require()` raises rather than returning `None`.

Both halves are required. A migration applied ahead of a deploy leaves the
backbone `disabled` and changes nothing on its own — which is what makes step 7
and step 9 separable.

The server half of the first write path exists and follows the state:
`app.py` builds the backbone at startup (the tables are read only when the
flag asks), `GET /api/account-backbone` reports the state, and `/api/works`
(`writing_coach/work_api.py`) answers only when `active` - otherwise 503 with
`account_backbone_disabled` / `account_backbone_unavailable`, never "saved".
No surface calls it yet: the client half (a draft kept with the account when
`active`, on the device otherwise, and saying which) is the next slice, after
the flag is on in the sandbox so it can be walked in a browser.

---

## 7. Compatibility verification

### Rehearsal, before the decision

Run against a throwaway copy of the tree with the migration moved into
`versions/`, and a scratch database seeded to the live head with data. The real
repository and the runtime database were not touched.

| Check | Result |
| --- | --- |
| New build against un-migrated database | Refuses: "expected 20260908_0005, found 20260828_0004. Check which database this process is pointed at." |
| Report-only run | `mismatch`, and it prints the exact `--upgrade` command to use |
| Plain `--confirm` on a database with data | Refused |
| `--upgrade` with the wrong `--from` | Stopped: "This database is at 20260828_0004, not 20260811_0001." |
| `--upgrade` with the right `--from`, no `--confirm` | Reports the migration and asks for a backup first |
| `--upgrade --from 20260828_0004 --confirm` | Applies `20260828_0004 → 20260908_0005`, then reports `ready` |
| New build against migrated database | Starts; `GET /`, `/api/learner-profile` and `/api/dashboard` all 200 |
| Pre-existing rows after migration | Intact |
| Existing readers | Unaffected — no existing table is altered |
| Backbone at rest after migration | `disabled` |
| Backbone with the flag on | `active`, all three repositories constructed |

Every row is fresh command output from a throwaway copy of the tree with the
migration moved into `versions/`, against a scratch database seeded to the live
head. Both databases were dropped afterwards; the real repository and the
runtime database were not touched.

### The deployment itself

Same sequence, against the real sandbox runtime, under the human authorization
in the Status section. Fresh output, not the rehearsal's.

| Check | Result |
| --- | --- |
| Backup captured | 49,784 bytes from the sandbox runtime |
| Backup verified | 98 restorable entries |
| Restore rehearsed into a separate database | Matched on revision and all eight counts; target dropped |
| `git mv` into `versions/` | The build's expected head becomes `20260908_0005` |
| `--upgrade --from 20260828_0004 --confirm` | Applied `20260828_0004 → 20260908_0005`, reported `ready` |
| Restart in the same window | `orena-foundation-web` started; no head refusal |
| `GET /`, `/api/learner-profile`, `/api/dashboard` | 200, 200, 200 |
| Head after | `20260908_0005` |
| Learner rows after | Unchanged: `users` 1, `saved_words` 5, `user_language_profiles` 2, `speaking_attempts` 2, `listening_progress` 10 |
| The eight new tables | Present, empty |
| Backbone at rest | `disabled` — the flag is not set |
| 42 PostgreSQL concurrency cases against the live chain | Pass |
| Nine rooms walked in the browser, EN and ZH | Render; the learner-profile write path still works |

The 19 pre-existing tables were not altered, which is what makes existing
readers unaffected: the migration adds and never changes.

---

## 8. What this runbook does not authorize

Applying the schema to the runtime database; activating authoritative writes;
enabling sync or import; destructive migration or deletion; production
credentials or payments; deploying an incompatible schema/runtime boundary.

Of those, one has since been authorized separately and done: the schema was
applied to the **sandbox** runtime under an explicit instruction that named the
flag and kept it off. Everything else on that list stands — no authoritative
write is active, no sync or import is enabled, nothing destructive has run, no
production credential or payment is enabled, and no production or preview
runtime has been deployed to. None of it follows from this document existing.
