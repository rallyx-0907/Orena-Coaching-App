# Canonical Reading cutover — integration runbook (D-082, D-083)

**Scope: the sandbox only, after independent delta review and explicit runtime
authorization for this integration revision.** D-083 authorized the Admin-lane
predecessor `20260924_0014` on the admin sandbox; that authorization does not
transfer to `20260924_0016`, whose parent and ID changed here. The new revision
is a deliberate non-additive cutover:
the legacy generated-reading tables become a read-only archive and the code
that retires the generated flow ships in the same deploy. Production (8000)
and preview (8010) keep every gate; both scripts below refuse them.

Two things this runbook does not decide:

- **The legacy archive's fate.** Step 3 reports it; the human decides. Test
  or development data may then be reset (step 9); meaningful learner history
  stays read-only.
- **Learner submit.** It stays off (`ORENA_READING_PRACTICE_SUBMIT` unset)
  until the complete live E2E passes on the sandbox (steps 7–8).

Placeholders: `<web>` is the sandbox application container, `<network>` its
Docker network, `<pg-url>` its `POSTGRES_RUNTIME_URL`, `<sandbox-db>` the
database that URL names, `<cluster>` the system identifier `target` prints,
`<repo>` the lane's worktree at the commit being deployed. Check `docker ps`
first: only one lane operates Docker at a time (`AGENTS.md`, Safety).

**How the cutover script knows it is the sandbox.** No single check is trusted
alone: `APP_ENV` must not be production and no URL may be on 8000 / 8010; the
production compose default database (`postgres` / `becoming`) is refused by
name even from a clean shell; `--confirm-sandbox <sandbox-db>` must name the
URL's database and the connected server must report that same database; and
the two commands that change anything - `apply` (the migration) and
`reset-legacy` - also need `--expect-cluster <cluster>`, so they act only in
the PostgreSQL cluster `target` showed. `apply` makes those checks and runs the
migration on one connection in one transaction; `bootstrap_runtime_schema.py
--upgrade` refuses to cross `20260924_0016` at all. The E2E driver accepts only
a loopback base URL, never 8000 / 8010, and stops if the server's
`/api/readiness` says `production`.

## 1. Stop writers

Stop the sandbox web container and any Reading worker. Nothing writes while
the schema changes.

## 2. Back up, verify, rehearse the restore

As in `I2_ACTIVATION_RUNBOOK.md` — the application image has no
`postgresql-client`, so from an ephemeral container with `backups/` mounted
writable:

```
docker run --rm --network <network> -e POSTGRES_RUNTIME_URL="<pg-url>" \
  -v "<repo>:/workspace:ro" -v "<repo>/backups:/workspace/backups" -w /workspace \
  ai-writing-coach:local sh -lc "apt-get update -qq && apt-get install -y -qq postgresql-client && \
    python scripts/runtime_backup.py capture && \
    python scripts/runtime_backup.py verify --dump backups/<file>.dump && \
    python scripts/runtime_backup.py rehearse --dump backups/<file>.dump --into orena_restore_rehearsal"
```

The rehearsal now also compares `reading_attempts`, `reading_comprehension_sets`
and the two archive tables (None before the upgrade), and the echoed commands
no longer show the connection password.

## 3. Name the target, then inventory the legacy archive — report it before anything else

```
docker run --rm --network <network> -e POSTGRES_RUNTIME_URL="<pg-url>" \
  -e APP_ENV=development -e PUBLIC_BASE_URL=http://localhost:<sandbox-port> \
  -v "<repo>:/workspace:ro" -w /workspace ai-writing-coach:local \
  sh -lc "python scripts/reading_canonical_cutover.py target --confirm-sandbox <sandbox-db> && \
          python scripts/reading_canonical_cutover.py inventory --confirm-sandbox <sandbox-db>"
```

`target` prints the database and its cluster's system identifier: record it
with the inventory — steps 4 and 9 need it. The inventory prints, per account and language, the legacy sessions and attempts, their
dates, the linked text discussions, masked identities and a hint of whether the
account looks like test data. **Send this to the human.** The hint is not a
decision.

## 4. Apply `20260924_0016` — one gated command

This command begins at `20260924_0015`. On the Codex sandbox, the preceding
Reading Content Engine upgrade from Vocabulary Decks `20260923_0014` to
`20260924_0015` is a **separate** migration step. It must first receive its
own independent architecture review and explicit human sandbox authorization;
verify the database and cluster target, stop writers, take and verify a backup,
then apply that exact single revision under the independently reviewed
procedure. Confirm Alembic reports `20260924_0015` before starting this step.
Neither the Admin lane's earlier sandbox approval nor this integration's
isolated PostgreSQL rehearsal authorizes applying it to the Codex sandbox.

With the new code (the image built from `<repo>`), still with writers stopped,
in the same kind of ephemeral container as step 3:

```
python scripts/reading_canonical_cutover.py apply --confirm-sandbox <sandbox-db> \
  --expect-cluster <cluster> --from 20260924_0015
python scripts/reading_canonical_cutover.py status --confirm-sandbox <sandbox-db>
```

`apply` is the check and the migration together: on one connection, in one
transaction, it confirms the server is `<sandbox-db>` in `<cluster>`, takes a
lock against a second migrator, confirms the revision is `20260924_0015`, runs
the Alembic upgrade on that same connection, and confirms the result is
`20260924_0016` on the same server before committing. Any refusal rolls back
and changes nothing. Do not run `bootstrap_runtime_schema.py --upgrade` for
this step: it refuses to cross `20260924_0016` and prints the command above.

## 5. Deploy and start, submit off

Start the web container and the Reading worker from the same commit, with
`ORENA_READING_PRACTICE_SUBMIT` unset. Startup schema verification must pass.
Select the AI provider for Reading (Gemini in the sandbox; the key is already
in its environment — check it as a boolean, never print it).

## 6. The gated E2E (submit off)

From the host, against the sandbox URL (with OAuth on, put an administrator's
`writing_coach_session` cookie in `ORENA_E2E_SESSION` — the environment, never
the command line):

```
python scripts/reading_canonical_e2e.py run --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e-off.json --ai-provider gemini --ai-model gemini-3.5-flash-lite
```

Expected: every check passes - 19 per language, 38 in all with the local
stand-in; the article-dependent checks scale with the questions the provider
writes, not the count. They include `a candidate gets no comprehension set:
publish first`, `the selection policy offers a next article` (required: three
articles per language are published with approved sets, so the policy must
offer one), `and it comes with a signed recommendation`, `learner submit is
off: 503 reading_submit_disabled` and `and it wrote nothing`, in English and
Chinese.

## 7. The complete E2E (submit on, sandbox only)

Restart the web container with `ORENA_READING_PRACTICE_SUBMIT=on`, then:

```
python scripts/reading_canonical_e2e.py run --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e.json
```

It checks D-082 §12 steps 1–7 and 9, per language (47 checks each, 94 in
all with the local stand-in):

1. import → review → publish, rights warnings recorded beside the override; a
   set before publishing is refused;
2. grounded sets generated and approved for three articles;
3. the selection policy offers one, the same choice twice (the run fails if it
   offers none), with a signed recommendation;
4. **provenance is the recommendation, not a coincidence.** A request that
   states `selection_policy_version` itself is refused 422. The recommended
   article is answered first *without* its recommendation - as if opened from
   the library - and that attempt records no selection. It is then answered
   *with* the recommendation `/next` issued, and the server records
   `reading-select/1` although the evidence moved in between. The next choice
   moves on;
5. an article the learner picked records no selection; the attempt persists,
   is scored against the approved key, ability moves; a retry is the same
   attempt and ability moves once; a reload keeps all three attempts;
6. a body edit stales the set, keeps the questions and the evidence, and
   refuses a new answer against the old text;
7. Collection and Learner Summary read the attempt; the cross-skill cue names
   **this run's** attempt and article; **Admin Activity for this exact
   account** (`account_id` from the learner's ability projection) counts
   exactly this run's 3 attempts in this language more than before; **product
   analytics** - which names no learner, by design - counts exactly 3 more
   Reading activities and 3 more completions than before.

Two conditions for an honest run: the account should have no pending writing
review (the cue prefers one to Reading; the run reports it as a failure rather
than passing over it), and no other learner should be submitting Reading in the
sandbox while it runs (analytics is a count across learners, so another
learner's attempt fails the exact-delta check rather than hiding in it).

In the product, the recommendation is what Home's "for you" rail (the rail
Orena Home Discover draws for what fits the learner) links to: only that card
carries the signed recommendation, so the same article opened from the library
or the Reading rail is the learner's own choice.

## 8. Recreate the runtime and verify

Containers down and up, **volumes kept** (never `down -v`), then:

```
python scripts/reading_canonical_e2e.py verify --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e.json
python scripts/reading_canonical_e2e.py verify --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e-off.json
```

Expected with the local stand-in: `verify` of the complete run 30 checks
(per language: three articles still published with unchanged questions and
the expected set status, all three attempts still evidence, Admin Activity's
count for the account unchanged, ability unchanged, both retries replayed with
the recommended attempt still `reading-select/1`, the cue still naming the
run's attempt); of the gated run 18.

**Only when steps 6–8 all pass** may learner submit stay on in the sandbox. If
any check fails, restart with the flag unset and report the failure.

## 9. The legacy archive, after the human's decision

Only if the human decided from step 3 that the archive is test or
development data:

```
python scripts/reading_canonical_cutover.py reset-legacy --confirm-sandbox <sandbox-db> \
  --expect-cluster <cluster> --expect-sessions <N> --expect-attempts <M>
```

`<cluster>`, `N` and `M` are what step 3 printed; the command refuses if the
cluster is another one or the archive holds anything else. Text discussions keep their rows and lose the link.
Otherwise leave the archive as it is: it is read-only, and nothing reads it as
evidence, as an ability baseline or as "earlier practice".

## Rollback

While the canonical model is empty, `alembic downgrade 20260924_0015` restores
the legacy tables with every row (then redeploy the previous code). Once any
canonical set, attempt, projection or non-default `content_kind` exists the
downgrade refuses and changes nothing: the path is a reviewed forward repair,
or a restore of step 2's backup.

## Rehearsed locally (local execution, not the sandbox)

Each result below names the commit it was measured at. None of it is the
sandbox run, and the AI provider was a local stand-in (an Ollama-shaped server
answering only the question schema with spans copied from the E2E passages), so
the sandbox run with Gemini (step 6) is also the first live check of the
question processor.

**At the commit that follows `1d9a36b`** (the historical Admin-lane review
round, before integration renumbering), PostgreSQL 16 in a throwaway container,
seeded at `20260923_0013` with 6 legacy sessions / 6
attempts for two accounts:

- `bootstrap_runtime_schema --upgrade --from 20260923_0013 --confirm` refused
  (exit 1) and printed the `apply` command;
- `apply` refused an empty database (no revision), a wrong `--expect-cluster`
  and a wrong `--from`, each with nothing changed; with the database and
  cluster `target` printed it migrated to `20260924_0014`: archive 6 / 6,
  11 lifecycle triggers, startup readiness `ready`;
- the gated E2E: 38 passed (EN, ZH); the complete E2E with submit on: 94
  passed, including the recommended article answered without its
  recommendation (NULL) and with it (`reading-select/1`), Admin Activity +3 for
  the exact account per language and analytics +3 activities / +3 completions
  per language; after removing the app and worker and restarting PostgreSQL,
  `verify`: 30 + 18 passed;
- in Chromium (desktop): on Home the "for you" card for the recommended article
  carried a recommendation and the Reading rail's card for the same article
  did not; answered through the quiz, the Reading rail's card recorded NULL and
  the "for you" card `reading-select/1`.

Not re-run this round (unchanged tooling, results from `974e639`): the backup
capture and restore rehearsal (131,596 bytes, 266 restorable entries, every
compared count matched), the downgrade / upgrade with legacy rows (6 / 6 back
and writable; downgrade refused once canonical data existed), `reset-legacy`
(refused before the upgrade and with wrong counts; reset 6 / 6 only with the
exact counts, on a restored copy), and the phone (390×844, touch) check.

**At `1d9a36b`** the driver of that round - then with provenance recomputed at
submit, since replaced - passed 36 gated, 89 complete and 28 on verify. **At
`974e639`** the first driver passed 20, 61 and 12 + 6. Those counts belong to
those drivers and are not comparable with the ones above.
