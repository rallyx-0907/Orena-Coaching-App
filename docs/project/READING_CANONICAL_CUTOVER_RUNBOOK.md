# Canonical Reading cutover — admin sandbox runbook (D-075, D-076)

**Scope: the admin sandbox only.** D-076 authorizes applying
`20260924_0014` to the admin sandbox as a deliberate non-additive cutover:
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
Docker network, `<pg-url>` its `POSTGRES_RUNTIME_URL`, `<repo>` the lane's
worktree at the commit being deployed. Check `docker ps` first: only one lane
operates Docker at a time (`AGENTS.md`, Safety).

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

## 3. Inventory the legacy archive — report it before anything else

```
docker run --rm --network <network> -e POSTGRES_RUNTIME_URL="<pg-url>" \
  -e APP_ENV=development -e PUBLIC_BASE_URL=http://localhost:<sandbox-port> \
  -v "<repo>:/workspace:ro" -w /workspace ai-writing-coach:local \
  python scripts/reading_canonical_cutover.py inventory --confirm-sandbox
```

It prints, per account and language, the legacy sessions and attempts, their
dates, the linked text discussions, masked identities and a hint of whether the
account looks like test data. **Send this to the human.** The hint is not a
decision.

## 4. Apply `20260924_0014`

With the new code (the image built from `<repo>`), still with writers stopped:

```
python scripts/bootstrap_runtime_schema.py --upgrade --from 20260923_0013 --confirm
python scripts/reading_canonical_cutover.py status --confirm-sandbox
```

`bootstrap_runtime_schema` refuses if the database is not at `20260923_0013`
— the usual sign the connection string points somewhere unexpected.

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

Expected: every check passes, including `learner submit is off: 503
reading_submit_disabled` and `and it wrote nothing`, in English and Chinese.

## 7. The complete E2E (submit on, sandbox only)

Restart the web container with `ORENA_READING_PRACTICE_SUBMIT=on`, then:

```
python scripts/reading_canonical_e2e.py run --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e.json
```

It checks D-075 §12 steps 1–7 and 9: import → review → publish (rights
warnings recorded beside the override) → a grounded set generated and approved
→ the learner meets it without answers → the attempt persists → ability moves
→ the next article is chosen by the policy, the same way twice → a retry is the
same attempt and ability moves once → a reload keeps both → a body edit stales
the set, keeps the questions and the evidence, refuses a new answer against the
old text → Collection, Learner Summary, the cross-skill cue, Admin Activity and
analytics read the canonical attempt.

## 8. Recreate the runtime and verify

Containers down and up, **volumes kept** (never `down -v`), then:

```
python scripts/reading_canonical_e2e.py verify --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e.json
python scripts/reading_canonical_e2e.py verify --base-url http://localhost:<sandbox-port> \
  --state backups/reading-e2e-off.json
```

**Only when steps 6–8 all pass** may learner submit stay on in the sandbox. If
any check fails, restart with the flag unset and report the failure.

## 9. The legacy archive, after the human's decision

Only if the human decided from step 3 that the archive is test or
development data:

```
python scripts/reading_canonical_cutover.py reset-legacy --confirm-sandbox \
  --expect-sessions <N> --expect-attempts <M>
```

`N` and `M` are the totals step 3 printed; the command refuses if the archive
holds anything else. Text discussions keep their rows and lose the link.
Otherwise leave the archive as it is: it is read-only, and nothing reads it as
evidence, as an ability baseline or as "earlier practice".

## Rollback

While the canonical model is empty, `alembic downgrade 20260923_0013` restores
the legacy tables with every row (then redeploy the previous code). Once any
canonical set, attempt, projection or non-default `content_kind` exists the
downgrade refuses and changes nothing: the path is a reviewed forward repair,
or a restore of step 2's backup.

## Rehearsed locally (2026-09-24, local execution, not the sandbox)

PostgreSQL 16 in the cloud container, seeded at `20260923_0013` with 6 legacy
sessions / 6 attempts for two accounts:

- capture 131,596 bytes, 266 restorable entries; restore rehearsal matched the
  revision and every compared count;
- inventory before and after the upgrade identical (6 / 6, archive renamed);
- `bootstrap_runtime_schema --upgrade --from 20260923_0013` → ready at
  `20260924_0014`; archive read-only (an update raised), 11 lifecycle triggers;
- downgrade → legacy tables back with 6 / 6 rows and writable; upgrade again →
  6 / 6, read-only; after canonical data existed the downgrade refused;
- `reset-legacy` refused before the upgrade, with wrong or missing counts, and
  reset 6 / 6 only with the exact counts (on a restored copy);
- the gated E2E: 20 checks passed (EN, ZH); the complete E2E with submit on:
  61 passed; after stopping the app and worker and restarting PostgreSQL,
  `verify`: 12 + 6 passed; ports 8000 and 8010 refused;
- the learner check in Chromium, desktop 1920×1080 and a touch phone 390×844,
  English and Chinese: offered, answered, scored, the answer panel in the
  support language;
- the learner who owned 3 archived sessions started from the policy's initial
  ability with 1 attempt: the archive gave no baseline.

The AI provider there was a local stand-in serving grounded questions — the
container has no provider — so the sandbox run with Gemini (step 6) is also
the first live check of the question processor.
