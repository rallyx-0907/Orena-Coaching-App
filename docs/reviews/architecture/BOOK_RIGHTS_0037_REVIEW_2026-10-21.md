# Architecture review: Reading book rights, migration 20261021_0037 (D-252, PR #486)

- **Reviewer:** Delegated Architecture Reviewer, an independent read-only Claude subagent with a separate context. AGENTS.md, "Architecture review authority": the implementer, the Intelligence lane, does not self-approve.
- **Implementer:** Intelligence lane (Claude Opus 5.5).
- **Reviewed commits:**
  - `733f517a`: first review, CHANGES REQUIRED.
  - `47a56e32`: the delta re-review, **APPROVE FOR PROMOTION (subject to the human gate)**.
- **Scope:**
  - `migrations/proposed/20261021_0037_reading_book_rights.py`;
  - `writing_coach/persistence/reading_library_repository.py`, `writing_coach/persistence/admin_repository.py`, `writing_coach/admin_content.py` and the book rights route in `writing_coach/admin_console_api.py`;
  - `scripts/check_books_rights.py` and `tests/test_book_rights.py`;
  - D-252.
- **Not covered:** this is not product approval, and not authorization to promote or apply the migration. Both are human gates.

## First review (733f517a): CHANGES REQUIRED
No P0. The DDL is sound: a chain on head `20261019_0036`, metadata-only `ADD COLUMN`s with constant defaults, a trivial backfill and CHECK scan on a one-row-per-book table, `lock_timeout` first, and a downgrade that is correct and documented as destructive.

| Id | Finding | Resolution (47a56e32) |
|---|---|---|
| P1-A | The column probe cached a failure as "no columns" for the life of the process, leaving the gate open | "Yes" is kept for the engine's life; "no" is re-checked after 30 s; a failed look is never cached; the cache is a `WeakKeyDictionary` (closes P2-1) |
| P1-B | Cover regeneration used the learner-filtered `get_book`, so a draft book got a 404 | `get_book(item_id, learner=False)` |
| P1-C | The backfill marked archived books `grandfathered`, so a restore bypassed the gate | The backfill is `WHERE status = 'ready'`; archived books stay `unknown` and need an attestation after a restore |
| P1-D | The admin detail view did not read `rights_status`, so a draft showed as `published` | It selects `rights_status` like the list; tested on a SQLite table |

## Re-review (47a56e32): APPROVE FOR PROMOTION, subject to the human gate
All four P1s are resolved. Remaining, none blocking:
- **P2-a:** a failed probe returns "no" for that one call, so during a transient error before the first successful look, unattested books could show. This is far smaller than before.
- **P2-b:** the tests now cover the probe (a failure is not cached, "no" is re-checked after 30 s), the admin detail, and in PostgreSQL an archived book needing an attestation plus a downgrade that removes the columns.
- **P2-c:** the checker's 1000-row cap. It now says when its list is cut.

## Conditions for promotion and apply (each runtime, each a human gate)
1. **Promotion commit:** `git mv` the migration into `versions/`, and update the single-head pins in `tests/test_consent_evidence.py` and `tests/test_orena_memory_migration.py`.
2. **Backup:** take a fresh backup (`scripts/runtime_backup.py`) and verify the restore, per runtime.
3. **Rehearsal:** up/down/up on a copy of the real runtime data. Confirm that the `grandfathered` count equals the `ready` count, that archived rows are `unknown`, and that the CHECK holds. Time it.
4. **Apply:** `scripts/bootstrap_runtime_schema.py --upgrade`, one runtime per invocation, on the runtime the human names.
5. **Restart:** restart every app worker right after the apply.
6. **After:** run `python scripts/check_books_rights.py` and have a person attest or deny each grandfathered book. Expect the shelf to be unchanged on the day; compare list counts before and after.
7. **Rollback:** a runtime that holds attestations is restored from backup, never downgraded.
