# Manual account deletion: operator runbook

Status: **DRAFT. Destructive. Needs independent architecture review before first use** (AGENTS.md section 1, "Architecture
review authority", and section 10: account deletion and destructive lifecycle changes require it; the account-deletion
runtime is a reserved hold, section 7). Nobody runs this against `:8000` until a Delegated Architecture Reviewer has
recorded their name, the reviewed commit and the outcome in Git. This file contains no code that deletes anything:
the public promise it serves is `/account-deletion` (D-162): a learner emails
`orena.support@chillpickle.org` from their Google account's email, and the account is deleted by hand within 30 days at most.

## 0. Before the first request

1. Review recorded in Git (reviewer, commit, outcome). Until then, answer requests with "received" and keep the clock.
2. Decide and record the three open points the code does not decide:
   - **The `users` row.** It SURVIVES as the incarnation barrier (`persistence/deletion_enumeration.py:1-5`; the journal
     anchors on it, `persistence/deletion_journal.py`). Its settings columns are reset (`USER_COLUMNS_TO_RESET`). The
     enumeration does not cover `email`, `name`, `picture`; the public text promises those are removed or irreversibly
     anonymised and that only an internal id, Google's opaque sign-in id and the deletion time are kept. The sign-in
     id (`google_sub`, the account key) must stay so the barrier holds. The reviewer decides the anonymised values
     (`email` is UNIQUE and NOT NULL, so it needs a per-account non-identifying placeholder).
   - **Backup retention** (`facts.json` `retention.backup_days` = 30). Enforced by `python scripts/runtime_backup.py rotate
     --dir <backup dir> --days 30 --apply`, run at least daily on the host (dry run first). Applying it on :8000 is part of
     the human-gated deploy.
   - **Whether `ai_cost_records` exists** on the public database (migration 0026-0028 are absent from
     `migrations/versions`; `ai/account_costs.py` pauses if the table is missing).
3. Keep the **deletion journal** outside any database (`scripts/runtime_backup.py deletions`), and after any restore run
   `suppress` before serving (`deletion_journal.py:40-48`): a restore must not undo a deletion.
4. Nobody else operates the shared Docker runtime and volumes meanwhile (AGENTS.md section 10). Never
   `docker compose down -v`.

## 1. Verify the request

- The mail comes from the email of the Google account (the `users.email`, verified at sign-in,
  `auth_support.py:401`). A request from another address is not acted on; reply asking them to write from the account's address.
- Find the account: `users` row by email; note `users.id`, `user_key` (the Google `sub`), and the active incarnation id.
- Record in the operator's request log (outside the repository): date received, requester address, account ids, date
  completed. The 30-day clock starts when the mail arrives.
- Reply "received" and the expected date.

## 2. Take a safety copy

`python scripts/runtime_backup.py capture --out <path>` (access-controlled; it holds learner data). It is deleted when it ages
out under the backup rule above. It is not a way to keep the learner's data past the promised window.

## 3. What to delete (derive the list again from the live schema first)

The enumeration in the code has gaps the audit found; list every table with a column that references the account
(`users.id`, `user_key` or the incarnation) with a read-only query on `information_schema.columns` and compare it
with this table. Any table not listed here is a finding for the reviewer.

| Group | Tables / stores | Key | How |
| --- | --- | --- | --- |
| Account-keyed (enumerated) | `user_language_profiles`, `grammar_progress`, `listening_progress`, `shadowing_progress`, `speaking_attempts`, `essays` (and `essay_review_history` by cascade), `library_items`, `saved_words` | account (`user_id`) | delete rows (`ACCOUNT_KEYED_TABLES`, `CASCADED_TABLES`) |
| Incarnation-keyed (no cascade) | `works`, `work_turns`, `mutation_receipts`, `change_records`, `language_provenance` | the kept incarnation | delete rows explicitly (`INCARNATION_KEYED_TABLES`); drafts, conversations, notes and highlights, place, private imports live here (`ORENA_ACCOUNT_BACKBONE=on` on :8000) |
| Not in the enumeration (audit findings; D-170 put `essay_revisions`, `library_collections`, `reading_ability_projections`, `reading_attempts`, `reading_legacy_sessions`, `text_discussions` and `vocabulary_decks` into `ACCOUNT_KEYED_TABLES`, and a test keeps every table the target-language count reads there) | `essay_revisions`, `reading_legacy_sessions` (+ its attempts), `reading_attempts`, `reading_review_events`, `reading_ability_projections`, `vocabulary_decks` (+ `vocabulary_deck_members`), `vocabulary_collections` / `vocabulary_entries` / `vocabulary_collection_memberships` / `vocabulary_sense_localizations` owned by the account, `library_collections` (+ members), `text_discussions` (+ `text_discussion_turns`), `grammar_review_events` owned by the account | account | confirm ownership column per table, then delete rows |
| Plan and usage | `subscriptions`, `usage_events` | account | delete rows |
| Cost records | `ai_cost_records` (if the table exists) | `account_id` | delete rows |
| Audit rows of the account | `audit_logs` where `user_id` is the account: `agent.turn`, `learner.feedback` (ask the reviewer whether admin-action rows about the account stay as the record of the deletion) | `user_id` | for feedback, `platform_repository.delete_feedback_for_account(user_key)` (`persistence/platform_repository.py:794`, no runtime caller today) |
| File store | personal uploads under `data/media_library` (`MEDIA_LIBRARY_ROOT`): entries with `library='personal'`, provider `upload` or `youtube`, owner token of the account, in every learning language, with their original and thumbnail files | owner token | `writing_coach.media_library_api.delete_all_owned_media(user_key)` (`media_library_api.py:289`, `FILE_STORES`) |
| Caches / derived | any per-account cache or derived store found by the schema scan (e.g. `reading_derived_texts` if account-scoped) | | confirm, then delete |
| `users` row | KEPT as the barrier | | reset `learning_language`, `interface_language`, `weekly_goal_days`, `settings_updated_at` (`USER_COLUMNS_TO_RESET`); blank `name` and `picture`; replace `email` by the reviewer-approved placeholder; mark the incarnation deleted (`incarnation_repository.mark_deleted`, "no runtime caller", D-055) |
| Session | cookie-only sessions (`writing_coach_session`, 14 days, signed, no server-side revoke) | | cannot be revoked server-side; with the account deleted and the incarnation marked deleted, a leftover cookie reaches the barrier, not data. The reviewer confirms that |
| Device data | recordings, Orena Intelligence device memory, local settings | | not reachable by the operator; the learner clears site data. The public page says so |

Order: take the journal export (`runtime_backup.py deletions`) after marking the incarnation deleted; delete the file
store entries before the rows that name them; delete incarnation-keyed rows before anything that would orphan them.
One database transaction for the SQL part, so a failure leaves nothing half-deleted. Row counts per table are recorded.

## 4. What is not deleted (and why it is on the public page)

- The deletion record: internal ids, Google's opaque sign-in id, the deletion time. No name, email or content.
- Backups made before the deletion, until they are overwritten (`backup_days`).
- Server and network provider logs that contain the IP address.
- Text and audio already sent to AI and speech service providers (their retention, not ours).
- Anything on the learner's device.

## 5. Verify

- Re-run the schema scan: no row left for the account id, `user_key`, incarnation id or email in any table; the store
  lists no personal entry for the owner token.
- `runtime_backup.py suppress --check` (deletion holds against the journal) answers that every record holds.
- Sign-in with the same Google account yields a NEW incarnation with no data (`incarnation_repository.register_new`),
  not the old one.
- `GET /api/me`-style checks for the old session cookie return nothing of the account's content.

## 6. Close

Reply to the learner from `orena.support@chillpickle.org` that the account is deleted and what remains (section 4).
Record the completion date in the request log. If the 30 days are about to pass, tell the learner why and when.

## 7. Open items for the reviewer

1. The `users` row anonymisation values and `email` uniqueness.
2. The tables outside `deletion_enumeration.py` (section 3, "Not in the enumeration") added to it, so the future runtime
   deletes the same set.
3. Whether admin-action `audit_logs` rows about the account are kept.
4. Confirm backup rotation is applied on the host (`backup_days` = 30).
5. Whether session revocation is needed before the runtime is built.
