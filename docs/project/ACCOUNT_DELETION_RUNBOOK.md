# Manual account deletion: operator runbook

Status: **DRAFT. Destructive. Needs independent architecture review before first use** (AGENTS.md section 1, "Architecture
review authority", and section 10: account deletion and destructive lifecycle changes require it; the account-deletion
runtime is a reserved hold, section 7). Nobody runs this against `:8000` until a Delegated Architecture Reviewer has
recorded their name, the reviewed commit and the outcome in Git. The tool is `scripts/account_deletion.py`
(PRE-502 R4): a dry run by default (a READ ONLY plan, by table, with row counts), `--apply` to delete in one
transaction. It plans from the live schema, so a table added later is not missed. The procedure around it is this file:
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
3. Set **`ORENA_DELETION_LOG`** to a file that is **not on the database's volume**. Copy it off-host together with
   the backups, under the same access control; a log lost with the database is no log. fsync guarantees are weak on
   network filesystems. `--apply` refuses without it.
   - Each deletion appends an intent before its commit and a done after (`persistence/deletion_log.py`, D-054 a).
     Writers take `<log>.lock`.
   - If the tool reports `DELETED, but ... unconfirmed`, run, on the live database only:
     `python scripts/runtime_backup.py reconcile-log --log <path> --live`.
   - After any restore, before serving:
     `python scripts/runtime_backup.py suppress --into <restored db> --log <ORENA_DELETION_LOG> [--deletions <exports>]`.
     It puts every barrier back and deletes each logged deletion's owner rows again, bounded to that deletion (D-054 b).
     A learner who signed in again after their deletion keeps what they wrote since and their account row; tables
     without a timestamp are named for the operator to decide.
   - If the log has unsettled intents and the database they were written for is lost, add `--accept-unsettled`: a
     requested deletion is applied. Never reconcile against a restored database.
   - Then `suppress --check` must answer 0 not holding.
4. Nobody else operates the shared Docker runtime and volumes meanwhile (AGENTS.md section 10). Never
   `docker compose down -v`.

## 1. Verify the request

- The mail comes from the email of the Google account (the `users.email`, verified at sign-in,
  `auth_support.py:401`). A request from another address is not acted on; reply asking them to write from the account's address.
- Find the account: `users` row by email; note `users.id`, `user_key` (the Google `sub`), and the active incarnation id.
- Record in the operator's request log (outside the repository): date received, requester address, account ids, date
  completed. The 30-day clock starts when the mail arrives.
- Reply "received" and the expected date.

The tool's output names accounts (and, when an email is shared, the candidates' sign-in keys): keep it only with the
access-controlled request log, never in the repository or a ticket.

## 2. Take a safety copy

`python scripts/runtime_backup.py capture --out <path>` (access-controlled; it holds learner data). It is deleted when it ages
out under the backup rule above. It is not a way to keep the learner's data past the promised window.

## 3. What to delete

Run the dry run first and keep its output with the request: `python -m scripts.account_deletion --email <address>`.
It lists every table with an account, incarnation or sign-in-key column and its rows for this account, the commerce
rows (money records: `--commerce delete|keep` is required when there are any), the `admin.*` audit rows it keeps, and
any foreign key without a cascade that would make the delete fail. Then `--apply`. The rest of this section is the
reference the tool implements.

The enumeration in the code has gaps the audit found; list every table with a column that references the account
(`users.id`, `user_key` or the incarnation) with a read-only query on `information_schema.columns` and compare it
with this table. Any table not listed here is a finding for the reviewer.

| Group | Tables / stores | Key | How |
| --- | --- | --- | --- |
| Account-keyed (enumerated) | `user_language_profiles`, `grammar_progress`, `listening_progress`, `shadowing_progress`, `speaking_attempts`, `essays` (and `essay_review_history` by cascade), `library_items`, `saved_words` | account (`user_id`) | delete rows (`ACCOUNT_KEYED_TABLES`, `CASCADED_TABLES`) |
| Incarnation-keyed (no cascade) | `works`, `work_turns`, `mutation_receipts`, `change_records`, `language_provenance` | the kept incarnation | delete rows explicitly (`INCARNATION_KEYED_TABLES`); drafts, conversations, notes and highlights, place, private imports live here (`ORENA_ACCOUNT_BACKBONE=on` on :8000) |
| Not in the enumeration (audit findings; `reading_review_events` and `grammar_review_events` record editors' actions on content, not learner data, and are not deleted; D-170 put `essay_revisions`, `library_collections`, `reading_ability_projections`, `reading_attempts`, `reading_legacy_sessions`, `text_discussions` and `vocabulary_decks` into `ACCOUNT_KEYED_TABLES`, and a test keeps every table the target-language count reads there) | `essay_revisions`, `reading_legacy_sessions` (+ its attempts), `reading_attempts`, `reading_review_events`, `reading_ability_projections`, `vocabulary_decks` (+ `vocabulary_deck_members`), `vocabulary_collections` / `vocabulary_entries` / `vocabulary_collection_memberships` / `vocabulary_sense_localizations` owned by the account, `library_collections` (+ members), `text_discussions` (+ `text_discussion_turns`), `grammar_review_events` owned by the account | account | confirm ownership column per table, then delete rows |
| Plan and usage | `subscriptions`, `usage_events` | account | delete rows |
| Billing: in-app plan operations (PR-MON-9 §4.2.1) | `platform_settings` keys `billing.polar.op.*` (incarnation, action, our canonical PATCH fields, states; no card data) | the deleted incarnation | not deleted by hand: the billing reconciler deletes a deleted incarnation's **terminal** operation records at its next tick; an unresolved one (`pending` / `sent` / `provider_unknown`) is a money question and stays until it resolves or an operator closes it. Verify: `SELECT count(*) FROM platform_settings WHERE key LIKE 'billing.polar.op.%' AND value->>'incarnation' = '<incarnation id>'` is 0, or lists only unresolved ones under an open operator item |
| Billing: Polar customer (PR-MON-10 §4.8) | Polar's customer for the incarnation (`external_customer_id`): its card subscriptions, benefits and personal data at Polar | the deleted incarnation | **not deleted by hand.** After the incarnation is marked deleted, run `POST /api/admin/billing/polar/customer-cleanup` (or wait for the billing reconciler). It deletes the customer with `anonymize=true`, which cancels its subscriptions at once; a refund owed for a paid period follows `paid_deleted_account` and is issued from Polar's dashboard |
| Cost records | `ai_cost_records` (if the table exists) | `account_id` | delete rows |
| Audit rows of the account | `audit_logs` where `user_id` is the account: `agent.turn`, `learner.feedback` (ask the reviewer whether admin-action rows about the account stay as the record of the deletion) | `user_id` | for feedback, `platform_repository.delete_feedback_for_account(user_key)` (`persistence/platform_repository.py:794`, no runtime caller today) |
| File store | personal uploads under `data/media_library` (`MEDIA_LIBRARY_ROOT`): entries with `library='personal'`, provider `upload` or `youtube`, owner token of the account, in every learning language, with their original and thumbnail files | owner token | `writing_coach.media_library_api.delete_all_owned_media(user_key)` (`media_library_api.py:289`, `FILE_STORES`) |
| Caches / derived | any per-account cache or derived store found by the schema scan (e.g. `reading_derived_texts` if account-scoped) | | confirm, then delete |
| `users` row | KEPT as the barrier | | reset by the tool: `USER_COLUMNS_TO_RESET`, the consent columns when present, `role` to `user`; `name` and `picture` blanked; `email` replaced by `deleted+<users.id>@deleted.invalid`. The incarnations are marked deleted (a deleted epoch-1 row when the account has none), the same state `incarnation_repository.mark_deleted` writes |
| Session | cookie-only sessions (`writing_coach_session`, 14 days, signed; revocable per account since #377) | | revoked by the tool in the same transaction: the account's "revoked before" instant (`auth.session_revoked_before.*`, #377), so every cookie issued before the deletion is refused |
| Device data | recordings, Orena Intelligence device memory, local settings | | not reachable by the operator; the learner clears site data. The public page says so |

Order, as the tool runs it: one database transaction marks the incarnations deleted (or writes a deleted epoch-1
row for an account that never had one), deletes the rows, resets and anonymises the `users` row and revokes the
sessions; a failure leaves nothing half-deleted. Then the steps it prints: the personal media files (the sign-in key
survives, so they are still found), the Polar customer clean-up, and the journal export (`runtime_backup.py
deletions`). Keep the dry-run and apply outputs (row counts per table) with the request.

**Money records are kept.** The billing, credit and commerce tables keep their history append-only (the schema refuses
the delete), so `--commerce keep` is the only choice when the account has any. The public deletion page
(`account-deletion.en.json`) does not yet say payment records are kept: **owner decision before first use** -
disclose it, or design a deletable path.

## 4. What is not deleted (and why it is on the public page)

- The deletion record: internal ids, Google's opaque sign-in id, the deletion time. No name, email or content.
- Backups made before the deletion, until they are overwritten (`backup_days`).
- Server and network provider logs that contain the IP address.
- Text and audio already sent to AI and speech service providers (their retention, not ours).
- Anything on the learner's device.

## 5. Verify

- Re-run the schema scan: no row left for the account id, `user_key`, incarnation id or email in any table; the store
  lists no personal entry for the owner token.
- **Billing, Polar customer (PR-MON-10 §4.8).** The clean-up marker of the incarnation is `complete`:
  `SELECT value->>'state' FROM platform_settings WHERE key = 'billing.polar.customer_cleanup.<incarnation id>'`
  answers `complete` (read-only). And `GET /api/admin/billing/reconciliation` lists no open `event_undecided` item
  whose reason starts with `polar_customer_cleanup_failed` for it. While the marker is `pending`, run the clean-up
  route again; **do not close the request while it is pending.** A marker that is missing is pending, not done.
- `runtime_backup.py suppress --check` (deletion holds against the journal) answers that every record holds.
- The account's incarnations are all `deleted` (a returning learner meets the barrier, `DeletionBarrier`), and the
  dry run run again lists no row to delete. The operator does not sign in as the learner.
- The session revocation row exists for the account (`platform_settings` key `auth.session_revoked_before.<hash>`).

## 6. Close

Close only after section 5 holds, including the Polar customer clean-up (`complete`). Reply to the learner from
`orena.support@chillpickle.org` that the account is deleted and what remains (section 4).
Record the completion date in the request log. If the 30 days are about to pass, tell the learner why and when.

## 7. Open items for the reviewer

1. The `users` row anonymisation values and `email` uniqueness.
2. The tables outside `deletion_enumeration.py` (section 3, "Not in the enumeration") added to it, so the future runtime
   deletes the same set.
3. Whether admin-action `audit_logs` rows about the account are kept.
4. Confirm backup rotation is applied on the host (`backup_days` = 30).
5. Session revocation exists (#377); the tool applies it.
7. A learner who signs in again after the deletion meets the barrier on the backbone routes (`DeletionBarrier`), but
   the legacy owner routes do not check it, and `register_new` has no caller (D-055): what a returning learner gets
   is a product decision still open.
6. **D-054's gate** (`tests/test_deletion_journal.py`, `ORENA_BACKBONE_INTEGRATION_GATES.md`): no code may mark an
   incarnation deleted until each deletion is journaled outside the database **as it happens** and the owner-table
   deletion is **replayed after a restore**. The tool marks incarnations, so it cannot merge until that gate is
   lifted in its own reviewed change (continuous journal append with a defined order, a replay path wired next to
   `suppress`, a DECISION_LOG entry, and the test edited to allow exactly `persistence/account_deletion.py`).
