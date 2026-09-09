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

These are values only the human can supply. **Every one of them is absent
today**, and the code's behaviour with them absent is defined rather than
guessed — that is what makes activation a decision rather than a rush.

| Input | Needed for | Behaviour while absent |
| --- | --- | --- |
| Retention period by data class | destructive purge of deleted work | Purge is not implemented and cannot run. Deletion writes a tombstone and increments a version; nothing is erased. |
| Receipt/tombstone horizon | receipt compaction | No compaction. Receipts accumulate, which is correct but unbounded — see the operational note below. |
| Backup expiry and restore-suppression policy | restoring after a deletion | `runtime_backup.py` captures and rehearses. Applying deletion records before serving a restored database is **not implemented**; a restore today is only safe if no deletion happened after the dump. |
| Deletion barrier retention | how long a deleted incarnation blocks reactivation | The barrier row is kept indefinitely. It cannot be dropped while old credentials, jobs or operations could still be accepted. |
| Legal/regulatory retention obligations | all of the above | None assumed. No duration is invented anywhere in the code. |

**Two of these gate activation rather than merely limiting it.** Without a
restore-suppression policy, a restore can reinstate work a learner deleted.
Without a retention policy, nothing is ever purged. Neither blocks *this*
milestone, because neither destructive purge nor sync is being switched on —
but both must be answered before sync or deletion is enabled, and the account
architecture says so.

Not required for I2 and listed so their absence is not mistaken for an
oversight: plan/price/grace/meter policies (I3), achievement and pedagogical
policies (I6), provider credentials (I5).

---

## 2. Backup and restore

`scripts/runtime_backup.py`, three modes: `capture`, `verify`, `rehearse`.

**The application image does not ship `postgresql-client`.** It is a Debian
base without it, so `pg_dump`, `pg_restore` and `psql` are absent and the
script says so rather than failing with a traceback. Run it from an operator
environment that has the client tools, or install them into an ephemeral
container. This is an operational fact worth knowing before the night of a
migration rather than during it.

```
python scripts/runtime_backup.py capture  --out backups/pre-i2.dump
python scripts/runtime_backup.py verify   --dump backups/pre-i2.dump
python scripts/runtime_backup.py rehearse --dump backups/pre-i2.dump \
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

What a restore does **not** do: reapply deletion records before serving. That
needs the policy in §1 and is not implemented. Backups are access-controlled
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

No caller reads the backbone yet. Wiring it into the learner-facing write paths
is I2's remaining work and it happens **after** activation, not before, because
a write path that is present and inert is harder to reason about than one that
is not there.

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
