# D4 migrations rehearsal (0017-0023), recorded

Throwaway `postgres:17-alpine` container on its own Docker network, removed after each run;
`scripts/rehearse_learner_records_schema.py` run in the application image with the repository mounted read-only.

| Run | Date | State | Result |
| --- | --- | --- | --- |
| 1 | 2026-09-30 | revision 3 (`0706e36`) | 48 PASS, 0 FAIL |
| 2 | 2026-09-30 | revision 3 + delta-review P2s, hardened probes | **52 PASS, 0 FAIL** |
| 3 | 2026-09-30 | same, `--volume 100000` (100k rows in each hot table) | **53 PASS, 0 FAIL**; slowest revision 0020 at 0.321 s; every revision under 0.33 s, one invocation each |

## Run 3 output (volume)

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260811_0001, Initial PostgreSQL shadow foundation.
INFO  [alembic.runtime.migration] Running upgrade 20260811_0001 -> 20260828_0002, Add privacy-bounded Speaking attempt evidence.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0002 -> 20260828_0003, Add durable Active Listening progress.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0003 -> 20260828_0004, Add durable Shadowing round progress.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0004 -> 20260908_0005, Account incarnation, mutation receipts, change stream and the work aggregate.
INFO  [alembic.runtime.migration] Running upgrade 20260908_0005 -> 20260911_0006, Subscription state and the provider-event inbox for I3.
INFO  [alembic.runtime.migration] Running upgrade 20260911_0006 -> 20260912_0007, Quota buckets and reservations for I3.
INFO  [alembic.runtime.migration] Running upgrade 20260912_0007 -> 20260916_0008, PROPOSAL - shared Vocabulary Source Import content catalog.
INFO  [alembic.runtime.migration] Running upgrade 20260916_0008 -> 20260916_0009, Reading Library catalog - `reading_books` and `reading_book_chapters`.
INFO  [alembic.runtime.migration] Running upgrade 20260916_0009 -> 20260921_0010, Record whether a hint was used in the last checked Dictation attempt (D-068, D-069, DC-5).
INFO  [alembic.runtime.migration] Running upgrade 20260921_0010 -> 20260922_0011, The learner kept this review to read again (D-072.1).
INFO  [alembic.runtime.migration] Running upgrade 20260922_0011 -> 20260922_0012, A learner's discussion about a whole text, kept with the account (D-072.2).
INFO  [alembic.runtime.migration] Running upgrade 20260922_0012 -> 20260923_0013, The learner's own library, and the identity a saved word points at.
INFO  [alembic.runtime.migration] Running upgrade 20260923_0013 -> 20260923_0014, A learner's own study set, in the domain that owns studying.
INFO  [alembic.runtime.migration] Running upgrade 20260923_0014 -> 20260924_0015, Reading Content Engine - six tables behind Admin -> Content -> Reading.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0015 -> 20260924_0016, Adaptive Reading - one canonical Reading flow, one canonical evidence model.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0018 -> 20260930_0019, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0019 -> 20260930_0020, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0020 -> 20260930_0021, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0021 -> 20260930_0022, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0022 -> 20260930_0023, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 20260930_0023 -> 20260930_0022, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0022 -> 20260930_0021, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0021 -> 20260930_0020, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0020 -> 20260930_0019, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0019 -> 20260930_0018, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0018 -> 20260930_0017, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 20260930_0023 -> 20260930_0022, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0022 -> 20260930_0021, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0021 -> 20260930_0020, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0020 -> 20260930_0019, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0019 -> 20260930_0018, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0018 -> 20260930_0017, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0017 -> 20260924_0016, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0018 -> 20260930_0019, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0019 -> 20260930_0020, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0020 -> 20260930_0021, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0021 -> 20260930_0022, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0022 -> 20260930_0023, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.

PROBE                                                                                       RESULT  DETAIL
------------------------------------------------------------------------------------------  ------  ------
chain built to 20260924_0016 from versions/                                                 PASS    20260924_0016
no proposed revision is visible without version_locations                                   PASS    single head 0016
schema captured at 20260924_0016 (all public tables)                                        PASS    55 tables
volume seed: 100000 rows in each hot table                                                  PASS    14.7s to seed
rows seeded before the new columns exist                                                    PASS    {'users': 100002, 'user_language_profiles': 100003, 'listening_progress': 100001, 'grammar_progress': 100001, 'library_items': 100001, 'essays': 100001}
every revision sets lock_timeout, guarded by dialect                                        PASS    7 files
proposed revisions form one linear chain after 0016                                         PASS    0016 -> 0017 -> ... -> 0023, single head
upgraded to head, one revision per invocation                                               PASS    20260930_0023
user_language_profiles.declared_level                                                       PASS    character varying NOT NULL default=''::character varying
user_language_profiles.review_new_per_day                                                   PASS    smallint NULL default=None
user_language_profiles.review_limit_per_day                                                 PASS    smallint NULL default=None
user_language_profiles.review_modes                                                         PASS    json NULL default=None
users.learning_language                                                                     PASS    character varying NOT NULL default=''::character varying
users.interface_language                                                                    PASS    character varying NOT NULL default=''::character varying
users.weekly_goal_days                                                                      PASS    smallint NULL default=None
users.settings_updated_at                                                                   PASS    timestamp with time zone NULL default=None
listening_progress.score_source                                                             PASS    character varying NOT NULL default='client'::character varying
library_items.place                                                                         PASS    json NULL default=None
library_items.place_at                                                                      PASS    timestamp with time zone NULL default=None
grammar_progress.last_quiz_correct                                                          PASS    smallint NULL default=None
grammar_progress.last_quiz_total                                                            PASS    smallint NULL default=None
grammar_progress.last_quiz_at                                                               PASS    timestamp with time zone NULL default=None
rows that predate the migrations read the defaults                                          PASS    declared_level '', review NULL, users '' '' NULL NULL, score_source 'client' (88 kept), place NULL, quiz NULL
users.settings_updated_at: conditional update (expected version)                            PASS    NULL token -> 1 row; the same stale token -> 0 rows; the current token -> 1 row
users row still protected by the incarnation RESTRICT                                       PASS    account_incarnations.user_id -> users is still ON DELETE RESTRICT
listening_progress.score_source: default on insert                                          PASS    an insert that predates the column reads 'client'
essay_review_history: shape (scope is the essay's), unique key and index                    PASS    8 NOT NULL columns (no scope copy), json review, unique (essay_id, prior_fingerprint), index (essay_id, superseded_at)
essay_review_history: immutability trigger is UPDATE only                                   PASS    BEFORE UPDATE only (a DELETE trigger would block the cascade)
essay_review_history: a prior review is accepted                                            PASS    accepted
essay_review_history: the same prior review twice                                           PASS    refused (uq_essay_review_history_prior)
essay_review_history: an unknown essay                                                      PASS    refused (essay_review_history_essay_id_fkey)
essay_review_history: an UPDATE is rejected by the trigger                                  PASS    refused (immutable)
essay_review_history: cascade on essay delete                                               PASS    deleting the essay deleted its history (the DELETE is not blocked by the UPDATE trigger)
essay_review_history: cascade on user delete (through the essays)                           PASS    deleting the user deleted its essays and, through them, the history
library_items: partial place index                                                          PASS    partial index (user_id, language_code, place_at) WHERE place IS NOT NULL
library_items: place upsert (coalescing, version untouched, pin unaffected)                 PASS    created; 5 s non-boundary coalesced; boundary and +35 s written; version 1 and updated_at unchanged; a pin at version 1 still lands
library_items: JSON null is not SQL NULL (the hazard the ORM must avoid)                    PASS    a JSON null satisfies `place IS NOT NULL` and would enter the partial index: the ORM must declare `place` and `review_modes` with none_as_null=True (proposal section 15)
old-code inserts (no new columns) into users and user_language_profiles                     PASS    an old-code insert into users and user_language_profiles succeeds and reads the defaults
grammar_progress: a complete quiz result                                                    PASS    accepted
grammar_progress: completion with no quiz result                                            PASS    accepted
grammar_progress: correct greater than total                                                PASS    refused (ck_grammar_progress_quiz)
grammar_progress: a total without a time                                                    PASS    refused (ck_grammar_progress_quiz)
grammar_progress: a zero total                                                              PASS    refused (ck_grammar_progress_quiz)
lock_timeout: downgrade refused within seconds while users is locked; nothing half-applied  PASS    55P03 after 5.4s; still at 20260930_0023
downgraded to 20260924_0016                                                                 PASS    20260924_0016
downgrade removes everything the upgrade added                                              PASS    columns, table, indexes, trigger function and check are gone
schema after the downgrade equals the schema captured at 20260924_0016                      PASS    every public table identical: columns, indexes, constraints, triggers, functions
old rows survive the downgrade                                                              PASS    every seeded row is still there ({'users': 100002, 'user_language_profiles': 100003, 'listening_progress': 100002, 'grammar_progress': 100003, 'library_items': 100002, 'essays': 100001})
lock_timeout: upgrade refused within seconds while users is locked; nothing half-applied    PASS    55P03 after 5.2s; still at 20260924_0016
upgraded to head again                                                                      PASS    20260930_0023
schema after up-down-up equals the schema after the first upgrade                           PASS    identical columns, indexes, constraints, triggers
rows that predate the migrations read the defaults                                          PASS    declared_level '', review NULL, users '' '' NULL NULL, score_source 'client' (88 kept), place NULL, quiz NULL
essay_review_history: two writers, one prior review                                         PASS    two simultaneous refreshes of one prior review: one row, one refusal

LOCK-HOLD TIMES (one invocation per revision; the locks are held at most this long)
run                       revision        seconds
first upgrade             20260930_0017      0.254
first upgrade             20260930_0018      0.213
first upgrade             20260930_0019      0.201
first upgrade             20260930_0020      0.175
first upgrade             20260930_0021      0.168
first upgrade             20260930_0022      0.196
first upgrade             20260930_0023      0.155
second upgrade            20260930_0017      0.235
second upgrade            20260930_0018      0.233
second upgrade            20260930_0019      0.214
second upgrade            20260930_0020      0.321
second upgrade            20260930_0021      0.217
second upgrade            20260930_0022      0.234
second upgrade            20260930_0023      0.254
slowest: 20260930_0020 in second upgrade: 0.321 s

53 PASS, 0 FAIL
ALL PASS
```

## Run 2 output

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260811_0001, Initial PostgreSQL shadow foundation.
INFO  [alembic.runtime.migration] Running upgrade 20260811_0001 -> 20260828_0002, Add privacy-bounded Speaking attempt evidence.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0002 -> 20260828_0003, Add durable Active Listening progress.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0003 -> 20260828_0004, Add durable Shadowing round progress.
INFO  [alembic.runtime.migration] Running upgrade 20260828_0004 -> 20260908_0005, Account incarnation, mutation receipts, change stream and the work aggregate.
INFO  [alembic.runtime.migration] Running upgrade 20260908_0005 -> 20260911_0006, Subscription state and the provider-event inbox for I3.
INFO  [alembic.runtime.migration] Running upgrade 20260911_0006 -> 20260912_0007, Quota buckets and reservations for I3.
INFO  [alembic.runtime.migration] Running upgrade 20260912_0007 -> 20260916_0008, PROPOSAL - shared Vocabulary Source Import content catalog.
INFO  [alembic.runtime.migration] Running upgrade 20260916_0008 -> 20260916_0009, Reading Library catalog - `reading_books` and `reading_book_chapters`.
INFO  [alembic.runtime.migration] Running upgrade 20260916_0009 -> 20260921_0010, Record whether a hint was used in the last checked Dictation attempt (D-068, D-069, DC-5).
INFO  [alembic.runtime.migration] Running upgrade 20260921_0010 -> 20260922_0011, The learner kept this review to read again (D-072.1).
INFO  [alembic.runtime.migration] Running upgrade 20260922_0011 -> 20260922_0012, A learner's discussion about a whole text, kept with the account (D-072.2).
INFO  [alembic.runtime.migration] Running upgrade 20260922_0012 -> 20260923_0013, The learner's own library, and the identity a saved word points at.
INFO  [alembic.runtime.migration] Running upgrade 20260923_0013 -> 20260923_0014, A learner's own study set, in the domain that owns studying.
INFO  [alembic.runtime.migration] Running upgrade 20260923_0014 -> 20260924_0015, Reading Content Engine - six tables behind Admin -> Content -> Reading.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0015 -> 20260924_0016, Adaptive Reading - one canonical Reading flow, one canonical evidence model.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0018 -> 20260930_0019, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0019 -> 20260930_0020, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0020 -> 20260930_0021, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0021 -> 20260930_0022, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0022 -> 20260930_0023, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 20260930_0023 -> 20260930_0022, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0022 -> 20260930_0021, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0021 -> 20260930_0020, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0020 -> 20260930_0019, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0019 -> 20260930_0018, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0018 -> 20260930_0017, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 20260930_0023 -> 20260930_0022, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0022 -> 20260930_0021, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0021 -> 20260930_0020, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0020 -> 20260930_0019, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0019 -> 20260930_0018, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0018 -> 20260930_0017, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Running downgrade 20260930_0017 -> 20260924_0016, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260924_0016 -> 20260930_0017, The learner's declared level, per learning language (H2, merged into D4 as item I1).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0017 -> 20260930_0018, Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0018 -> 20260930_0019, Review modes and limits, per learning language (D4 item I13).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0019 -> 20260930_0020, Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0020 -> 20260930_0021, The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0021 -> 20260930_0022, Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260930_0022 -> 20260930_0023, The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.

PROBE                                                                                       RESULT  DETAIL
------------------------------------------------------------------------------------------  ------  ------
chain built to 20260924_0016 from versions/                                                 PASS    20260924_0016
no proposed revision is visible without version_locations                                   PASS    single head 0016
schema captured at 20260924_0016 (all public tables)                                        PASS    55 tables
rows seeded before the new columns exist                                                    PASS    {'users': 2, 'user_language_profiles': 3, 'listening_progress': 1, 'grammar_progress': 1, 'library_items': 1, 'essays': 1}
every revision sets lock_timeout, guarded by dialect                                        PASS    7 files
proposed revisions form one linear chain after 0016                                         PASS    0016 -> 0017 -> ... -> 0023, single head
upgraded to head, one revision per invocation                                               PASS    20260930_0023
user_language_profiles.declared_level                                                       PASS    character varying NOT NULL default=''::character varying
user_language_profiles.review_new_per_day                                                   PASS    smallint NULL default=None
user_language_profiles.review_limit_per_day                                                 PASS    smallint NULL default=None
user_language_profiles.review_modes                                                         PASS    json NULL default=None
users.learning_language                                                                     PASS    character varying NOT NULL default=''::character varying
users.interface_language                                                                    PASS    character varying NOT NULL default=''::character varying
users.weekly_goal_days                                                                      PASS    smallint NULL default=None
users.settings_updated_at                                                                   PASS    timestamp with time zone NULL default=None
listening_progress.score_source                                                             PASS    character varying NOT NULL default='client'::character varying
library_items.place                                                                         PASS    json NULL default=None
library_items.place_at                                                                      PASS    timestamp with time zone NULL default=None
grammar_progress.last_quiz_correct                                                          PASS    smallint NULL default=None
grammar_progress.last_quiz_total                                                            PASS    smallint NULL default=None
grammar_progress.last_quiz_at                                                               PASS    timestamp with time zone NULL default=None
rows that predate the migrations read the defaults                                          PASS    declared_level '', review NULL, users '' '' NULL NULL, score_source 'client' (88 kept), place NULL, quiz NULL
users.settings_updated_at: conditional update (expected version)                            PASS    NULL token -> 1 row; the same stale token -> 0 rows; the current token -> 1 row
users row still protected by the incarnation RESTRICT                                       PASS    account_incarnations.user_id -> users is still ON DELETE RESTRICT
listening_progress.score_source: default on insert                                          PASS    an insert that predates the column reads 'client'
essay_review_history: shape (scope is the essay's), unique key and index                    PASS    8 NOT NULL columns (no scope copy), json review, unique (essay_id, prior_fingerprint), index (essay_id, superseded_at)
essay_review_history: immutability trigger is UPDATE only                                   PASS    BEFORE UPDATE only (a DELETE trigger would block the cascade)
essay_review_history: a prior review is accepted                                            PASS    accepted
essay_review_history: the same prior review twice                                           PASS    refused (uq_essay_review_history_prior)
essay_review_history: an unknown essay                                                      PASS    refused (essay_review_history_essay_id_fkey)
essay_review_history: an UPDATE is rejected by the trigger                                  PASS    refused (immutable)
essay_review_history: cascade on essay delete                                               PASS    deleting the essay deleted its history (the DELETE is not blocked by the UPDATE trigger)
essay_review_history: cascade on user delete (through the essays)                           PASS    deleting the user deleted its essays and, through them, the history
library_items: partial place index                                                          PASS    partial index (user_id, language_code, place_at) WHERE place IS NOT NULL
library_items: place upsert (coalescing, version untouched, pin unaffected)                 PASS    created; 5 s non-boundary coalesced; boundary and +35 s written; version 1 and updated_at unchanged; a pin at version 1 still lands
library_items: JSON null is not SQL NULL (the hazard the ORM must avoid)                    PASS    a JSON null satisfies `place IS NOT NULL` and would enter the partial index: the ORM must declare `place` and `review_modes` with none_as_null=True (proposal section 15)
old-code inserts (no new columns) into users and user_language_profiles                     PASS    an old-code insert into users and user_language_profiles succeeds and reads the defaults
grammar_progress: a complete quiz result                                                    PASS    accepted
grammar_progress: completion with no quiz result                                            PASS    accepted
grammar_progress: correct greater than total                                                PASS    refused (ck_grammar_progress_quiz)
grammar_progress: a total without a time                                                    PASS    refused (ck_grammar_progress_quiz)
grammar_progress: a zero total                                                              PASS    refused (ck_grammar_progress_quiz)
lock_timeout: downgrade refused within seconds while users is locked; nothing half-applied  PASS    55P03 after 5.2s; still at 20260930_0023
downgraded to 20260924_0016                                                                 PASS    20260924_0016
downgrade removes everything the upgrade added                                              PASS    columns, table, indexes, trigger function and check are gone
schema after the downgrade equals the schema captured at 20260924_0016                      PASS    every public table identical: columns, indexes, constraints, triggers, functions
old rows survive the downgrade                                                              PASS    every seeded row is still there ({'users': 2, 'user_language_profiles': 3, 'listening_progress': 2, 'grammar_progress': 3, 'library_items': 2, 'essays': 1})
lock_timeout: upgrade refused within seconds while users is locked; nothing half-applied    PASS    55P03 after 5.2s; still at 20260924_0016
upgraded to head again                                                                      PASS    20260930_0023
schema after up-down-up equals the schema after the first upgrade                           PASS    identical columns, indexes, constraints, triggers
rows that predate the migrations read the defaults                                          PASS    declared_level '', review NULL, users '' '' NULL NULL, score_source 'client' (88 kept), place NULL, quiz NULL
essay_review_history: two writers, one prior review                                         PASS    two simultaneous refreshes of one prior review: one row, one refusal

LOCK-HOLD TIMES (one invocation per revision; the locks are held at most this long)
run                       revision        seconds
first upgrade             20260930_0017      0.233
first upgrade             20260930_0018      0.159
first upgrade             20260930_0019      0.190
first upgrade             20260930_0020      0.184
first upgrade             20260930_0021      0.243
first upgrade             20260930_0022      0.248
first upgrade             20260930_0023      0.164
second upgrade            20260930_0017      0.316
second upgrade            20260930_0018      0.289
second upgrade            20260930_0019      0.238
second upgrade            20260930_0020      0.238
second upgrade            20260930_0021      0.247
second upgrade            20260930_0022      0.163
second upgrade            20260930_0023      0.257
slowest: 20260930_0017 in second upgrade: 0.316 s

52 PASS, 0 FAIL
ALL PASS
```
