# Proposal (D-108.5): media metadata moves to PostgreSQL as its authority

Status: **PROPOSED, revision 1** (2026-10-01, `codex/work` at `0f14ed7`). Document only: no code, schema, migration,
Docker or runtime is changed by this file. Not reviewed, not approved.

Origin: human decision **D-108 point 5** (`DECISION_LOG.md`): "Long term, media metadata uses PostgreSQL as its authority;
the shared media file (`index.json`) is not a writable source of truth." It is also gate **G1** of
`ACCOUNT_RECORD_LIMITS.md` (section 8): per-account limits cannot make a single shared JSON file viable, and the human's
D-107 point 5 rollout gate beyond :8021 requires it. This is a **new persistence and schema decision**, so it goes through
the AGENTS section 7 / section 1 process: proposal -> independent architecture review -> human approval -> code +
migration + tests -> PostgreSQL up/down/up rehearsal at volume -> the human applies the migration to a runtime. The author
of this proposal may not review it. Production (:8000) and preview (:8010) are never touched by it, and **nothing here enables
the account backbone beyond :8021**.

Constraints taken as given (`ARCHITECTURE_INVARIANTS.md`, "Persistence"): PostgreSQL is authoritative; no dual-write; no
reverse sync; no silent fallback; **no startup import**; **no automatic startup Alembic**; no destructive persistent-volume
cleanup; production data mutation is a human gate; schema ownership is Alembic. AGENTS section 7: learner-owned records the
human approved for the server (D-104: learner-imported private content and its provenance) are server records; the
account-deletion runtime, the export format and the multi-device sync protocol stay reserved and are not decided here.

Legend: **[V]** read in code at the stated path in this working tree; **[I]** inferred or estimated, to be replaced by a
measurement; **[A]** a stated assumption. Format follows `LEARNER_RECORDS_D4.md` and `LEARNER_RECORDS_D4.REHEARSAL.md`.

---

## 1. Summary

**Today** every media entry of every account and of the shared library is one record in one file,
`data/media_library/index.json` (`MEDIA_LIBRARY_ROOT`), read and rewritten whole by a single-process store
(`FileMediaLibraryStore`, `media_library_store.py`). **Proposed:** two tables in PostgreSQL (one row per entry; the lesson
payload in a 1:1 side table), a repository with the same read/write surface plus the few queries the file cannot answer
(bytes by owner, paged listings, a status-only update), a one-time operator import of the existing file, and a cutover with no
dual-write. **The asset bytes do not move**: originals, thumbnails and other files stay on the asset store under
`media/<token>/...`. **No new learner-facing behaviour, copy or UI.**

| Question | Answer |
| --- | --- |
| Where is the authority after cutover? | PostgreSQL `media_entries` (+ `media_entry_payloads`). `index.json` becomes a read-only archive that the application never reads or writes |
| Do the files move? | No. `MEDIA_LIBRARY_ASSET_ROOT` and `FilesystemBookAssetStore` are unchanged |
| Schema | **One Alembic revision (`0024`, additive: two tables, indexes, CHECKs)**; no change to an existing table; downgrade drops only the two tables (rehearsal only) |
| Data move | An operator script (`scripts/import_media_index.py`), dry-run by default, idempotent, verifying, run once under a human gate; **not** at startup, **not** in the Alembic revision |
| Rollback | Inside the maintenance window: re-point the old code at the archived file. After writes resumed: restore the pre-cutover backup (never downgrade); post-cutover personal uploads are then orphan files, reported by the reconciler |
| Quota | `SELECT sum(stored_bytes)` over a partial index by owner, in the creating transaction under an advisory lock (D-107.3 / D-108.7 uploaded-media bytes) |
| Open for the human | Q1-Q8 (section 13): unique `lesson_id`, owner column choice, orphan policy, window length |

---

## 2. Current state [V]

### 2.1 The store

`FileMediaLibraryStore` (`media_library_store.py`): one file, `index.json`, `{schema_version: 1, entries: [...], integrity:
sha256}`. The docstring states the limit: *"single-process ... A future multi-process deployment must replace this
implementation rather than pretending a JSON file has cross-process locks."*

- **Reads parse the whole file.** `get`, `list` and the write path all call `_read()`, which reads the file, parses it,
  recomputes the SHA-256 over every entry, runs `validate_entry` on every entry and checks id uniqueness. There is no cache.
  Every call is O(entries).
- **Writes rewrite the whole file** through a temporary file and `replace`, under a **per-process `threading.Lock`** keyed by
  the index path (`_writer_for`). Two processes, or two hosts, would each read-modify-write over the other.
- **Fail-closed on a bad index** (since the media-index fix): `_read()` returns an empty map and sets `last_read_issue`
  (`index_missing`, `index_unreadable`, `index_corrupt`); `upsert`/`delete`/`assert_writable` raise `MediaIndexUnavailable`
  on the last two, so a failed read can no longer be followed by a write that erases the others. Readers still answer "not
  found" on a bad index (`stored_media_entry` swallows every exception, `_shared_entries` returns `[]`).
- Config: `MEDIA_LIBRARY_ROOT` (index) and `MEDIA_LIBRARY_ASSET_ROOT` (bytes), `app.py:598-610`.

### 2.2 The entry (`MediaLibraryEntry`, frozen dataclass; validated by `validate_entry`)

| Field | Type / rule | Notes |
| --- | --- | --- |
| `media_id` | text, `^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$` (<= 256) | identity; `upload-<uuid hex>` for uploads, `direct-<sha256[:32]>` for admin direct URLs, `yt-...` for YouTube |
| `media_type` | `video` \| `audio` | |
| `provider`, `provider_media_id` | ids, same pattern | `upload`, `youtube`, `direct` |
| `canonical_url` | http(s), no credentials, may be empty | |
| `playback` | map `{provider, kind, url}`, all non-empty | |
| `title`, `creator` | text (title non-empty) | uploads: `title[:240]` |
| `thumbnail` | map `{kind: provider-url\|asset\|none, ref}` | `ref == ''` iff `none`; `asset` ref is `media/<token>/thumbnail.jpg` |
| `duration_ms` | int >= 0 | |
| `language`, `level` | `en` \| `zh`; level in the language's level list or empty | |
| `source` | map with at least `provider,type,provenance_url,license,review_status,imported_by`; **personal rows add `owner`** = `owner_token(user_key)` = `sha256("orena-media-owner:" + key)[:32]` | provenance; the index never holds an email address for a learner |
| `library` | `shared` \| `personal` | |
| `created_at` | ISO-8601 with timezone | |
| `lesson` | map or `None`: `{lesson_id, topic, tags, payload: {asset, transcript{segments}, translations, ...}}` | present for YouTube sources; `None` for uploads and direct URLs |
| `status` | `published` \| `unpublished` \| `archived` (default `published`) | none is a deletion |

**Ownership** (`visible_to`): a `shared` entry is everyone's; a `personal` entry is visible only to the account whose
`owner_token` equals `source.owner` **and** only in `entry.language`. An entry with no `source.owner` is treated as the single
local account's (`LEGACY_OWNER_KEY = "legacy"`) and refused to every signed-in account (fail closed). Callers answer 404, never
403.

### 2.3 Libraries

- **Curated catalog**: constants in code (`listening_catalog.CATALOG`), not in the file; resolved before the store.
  Out of scope.
- **Shared**: published by an administrator (`library='shared'`): YouTube sources (with a lesson payload), direct public URLs,
  admin file uploads. Browsed by language, filtered by level/topic/tag.
- **Personal**: learner uploads only (`library='personal'`, `provider='upload'`). **The only personal writer is
  `learner_upload` -> `import_upload(library='personal')`** [V]. A learner's pasted link (`url:`) is not written to the index:
  it is re-acquired from the provider and kept as an account import record in `works`.

### 2.4 Every reader and writer

| # | Caller | File | Operation | Scope / notes |
| --- | --- | --- | --- | --- |
| R1 | `find_entry(media_id)` | `media_library_api.py:464-474` | `get` + `visible_to` | the one resolver behind `open_my_media`, `resolve_learner_payload`, `resolve_by_lesson_id`, the Listening/Content rooms |
| R2 | `stored_media_file` (`GET /api/media/files/{key}`) | `media_library_api.py:118-155` | `get("upload-<token>")` + `visible_to` | **once per image/audio request**; a personal file's bytes and thumbnail are as private as its entry; `private` cache headers for personal |
| R3 | `stored_media_entry` | `listening_api.py:113-130` | `get` + `visible_to`, swallowing any exception | Listening open by id |
| R4 | `_shared_entries` (`listening_api.py:436-460`) | | `list(language)` then filter `library`, level, topic, tag in Python | shared browse |
| R5 | `shared_browse_items` | `media_library_api.py:515-530` | `list(language, library="shared")` | Discover/Library cards (`browse_item`) |
| R6 | `resolve_by_lesson_id` | `media_library_api.py:600-612` | `find_entry`, then **`list(library="shared")` scanned for `lesson_id`** | O(entries) per call |
| R7 | `open_my_media`, `delete_my_media` | `media_library_api.py:170-205,235-258` | `get`/`find_entry`, `visible_to` | `delete_my_media` also asks `media_still_named` (works table) |
| R8 | `admin_library` | `media_library_api.py:255-268` | `list(language, status=None)`, `library == shared` | unpaged operator listing |
| R9 | Admin `_shared_media` | `admin_console_api.py:292-306` | `list(language=None, library="shared", status=None)` | all shared, all languages, unpaged; reports `last_read_issue` |
| R10 | Admin `_media_receipt` / `media_record` | `admin_console_api.py:560-575,790-800` | `get` (reads the lesson payload to count transcript segments) | per request |
| R11 | Admin status change | `admin_console_api.py:1150-1159` | `get`, then **`upsert(replace(entry, status=...))`**, `get` | a read-modify-write of the **whole entry** to change one field |
| R12 | Admin reprocess | `admin_console_api.py:1168-1187` | `get`, re-import by URL (`upsert`), `get` | |
| R13 | `_stored_upload` (admin dedupe by content hash) | `admin_console_api.py:1325-1335` | `get(media_id)` after the admin repository's `find_import` | |
| R14 | `delete_owned_media` / `_remove_personal_entry` | `media_library_api.py:209-232` | `get`, `visible_to`, files first (`delete_prefix`, thumbnail), then `store.delete` last | `assert_writable` first |
| R15 | `delete_all_owned_media` | `media_library_api.py:220-232` | **`list(library="personal", status=None)` over every account**, filtered by owner token | the D-055(b) account-deletion remover (`FILE_STORES`) |
| W1 | `MediaSourceImporter.import_urls` | `media_source_import.py:285-300` | `upsert` (shared, YouTube/direct) | admin import |
| W2 | `MediaSourceImporter.import_upload` | `media_source_import.py:344-390` | `put` original, `put` thumbnail, `upsert` | admin upload (`shared`) and learner upload (`personal`, `owner_key`) |
| W3 | Admin status change (R11) | | `upsert` | |
| D1 | Deletion enumeration | `persistence/deletion_enumeration.py:44-52` `FILE_STORES` | names `delete_owned_media` / `delete_all_owned_media` | the store is file-based, outside SQL deletion |

**Not through the store**: the account import record (`works` kind `imported`, form `upload`/`url`, `mediaPending`,
`media_still_named`), the `/api/imports` list, and the quota rails of `ACCOUNT_RECORD_LIMITS.md`. They reference a media entry
by its opaque `media_id` and stay where they are.

### 2.5 Findings that motivate the change [V unless marked]

1. **Cost.** Every R-row above is O(total entries) in time and memory, including R2 (an image request). Entries at the target
   (section 3.3): about 680 k personal rows a year [I].
2. **Single process.** The lock is `threading.Lock`; the file cannot be shared by two workers (the docstring says so).
3. **Whole-entry rewrites.** R11 rewrites the entry (and the entire file) to flip one field; a concurrent reprocess (R12)
   could be undone by it.
4. **No query for the quota.** "Bytes of this owner's live uploads" (D-107.3) cannot be answered without scanning the file, and
   the entry carries no size field.
5. **Unpaged listings** (R8, R9, R15 across accounts).
6. **Bad-index handling** already fails closed on writes; reads still degrade to "empty", which for the shared library means
   the learner sees a library with the admin's items missing.

---

## 3. Proposed schema (migration `20261001_0024`; additive)

Design rules: one table for the entry (one row per `media_id`), one 1:1 side table for the big lesson payload, constraints that
replace `validate_entry`'s database-expressible rules, no change to any existing table, **no foreign key to `users`**
(see 3.4), the file `index.json` untouched.

### 3.1 `media_entries`

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `media_id` | `VARCHAR(256)` | PK | same pattern as the code; CHECK `media_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$'` |
| `library` | `VARCHAR(10)` | no | CHECK in (`shared`,`personal`) |
| `status` | `VARCHAR(12)` | no, default `published` | CHECK in (`published`,`unpublished`,`archived`) |
| `media_type` | `VARCHAR(5)` | no | CHECK in (`video`,`audio`) |
| `provider`, `provider_media_id` | `VARCHAR(256)` | no | same pattern CHECKs |
| `canonical_url` | `TEXT` | no, default `''` | the application still validates http(s); no DB CHECK on URL shape |
| `title` | `TEXT` | no | CHECK `length(title) > 0` (provider titles are not bounded in the code today) |
| `creator` | `TEXT` | no, default `''` | |
| `duration_ms` | `BIGINT` | no | CHECK >= 0 |
| `language` | `VARCHAR(20)` | no | **no CHECK**: the code's `{en, zh}` is a registry, not a schema (as `works.language_code`) |
| `level` | `VARCHAR(16)` | no, default `''` | |
| `playback` | `JSONB` | no | `{provider, kind, url}`; CHECK `jsonb_typeof = 'object'` |
| `thumbnail_kind` | `VARCHAR(12)` | no | CHECK in (`provider-url`,`asset`,`none`) |
| `thumbnail_ref` | `TEXT` | no, default `''` | CHECK `(thumbnail_kind = 'none') = (thumbnail_ref = '')` |
| `source` | `JSONB` | no | provenance map, kept verbatim (the six required keys; `owner` for personal) |
| `owner_token` | `VARCHAR(32)` | yes | the digest, **explicit**; CHECK `library = 'shared' OR owner_token IS NOT NULL`; CHECK `source->>'owner' IS NULL OR source->>'owner' = owner_token` (one value, two spellings, never disagreeing) |
| `lesson_id` | `VARCHAR(256)` | yes | extracted from `lesson.lesson_id` (R6 lookup) |
| `topic` | `VARCHAR(64)` | no, default `''` | extracted from `lesson.topic` (Listening filter) |
| `tags` | `JSONB` | no, default `[]` | extracted array of strings; CHECK `jsonb_typeof = 'array'` |
| `has_lesson` | `BOOLEAN` | no, default false | `lesson is not None` |
| `segment_count` | `INTEGER` | no, default 0 | transcript segments, so R9/R10 need not load the payload |
| `stored_bytes` | `BIGINT` | yes | **new, server-measured**: original + thumbnail for `provider='upload'` rows; NULL for provider-hosted/direct rows. CHECK `stored_bytes IS NULL OR stored_bytes >= 0` |
| `created_at` | `TIMESTAMPTZ` | no | from the entry's ISO string |
| `updated_at` | `TIMESTAMPTZ` | no | server-set on every write (new; was not in the file) |
| `version` | `INTEGER` | no, default 1 | CHECK >= 1; incremented by writes that change the entry (optimistic check for the admin reprocess/status race) |

`library='personal'` further requires `provider = 'upload'` today (the only writer); not a DB CHECK, so a future personal
provider is a code change (registry), as `works.kind` is.

### 3.2 `media_entry_payloads` (1:1, only when `lesson is not None`)

| Column | Type | Notes |
| --- | --- | --- |
| `media_id` | `VARCHAR(256)` | PK, FK `media_entries(media_id)` `ON DELETE CASCADE` |
| `payload` | `JSONB` | the acquisition (`asset`, `transcript`, `translations`, ...) exactly as `lesson["payload"]` today |

**JSONB in a side table, not a column on the entry and not normalized segments.** The payload is read whole, as a unit
(`resolve_learner_payload`), never queried inside; a transcript of a 10-minute source is about 25 KB and an hour about 150 KB
[A], so keeping it out of the main row keeps the row narrow for every list and for the per-request R2 `get`, and keeps
list scans index-only-friendly. Normalizing segments into rows would invent a transcript model (the M1 Shared Media Learning
contract is protected, `ARCHITECTURE_INVARIANTS.md`) and is rejected. The extracted columns (`lesson_id`, `topic`, `tags`,
`has_lesson`, `segment_count`) are written by the repository from the same value in the same transaction; the payload is the
authority and a test asserts they agree (section 11).

### 3.3 Sizes and volumes [I]/[A]

Only **uploads** and **admin imports** create entries; a learner's link import does not (2.3). So the personal row count is not
the 2.3 M a year of `ACCOUNT_RECORD_LIMITS.md` G1 (which counted link imports too); it is uploads: 5,000 heavy x 100 + 15,000
typical x 12 = **680,000 personal entries a year** (assumptions A2, A10 of that document, unmeasured), about 2 M in three
years. Shared entries are admin-curated: of the order of thousands.

| Item | Estimate |
| --- | --- |
| Main row, heap (5 short strings, `playback` about 120 B, `source` about 330 B, ids) | about 0.9 KB |
| Indexes on the row (PK, browse, owner partial) | about 0.2-0.3 KB |
| **Per entry** | **about 1.2 KB** |
| 680 k personal entries a year | about 0.8 GB a year (the file equivalent is about 1.4 GB a year of JSON, rewritten whole on each write) |
| Shared lesson payloads | thousands x 25-150 KB = at most a few hundred MB |

These replace the file's O(total) per-request cost with O(log n) probes.

### 3.4 Why no foreign key to `users`, and what the owner column is

`owner_token` is a digest of the stable **account key** (`user_key`), not `users.id`; `users.id` is `stable_uuid('user', key)` and
neither is derivable from the digest. The index has only the digest, so an FK cannot be populated at import, and re-keying
existing entries would change identities. The proposal therefore keeps `owner_token` as the owner column (the repository
computes it exactly as `owner_token()` does) and keeps the account-deletion remover that takes the key (`delete_all_owned_media`,
D-055(b)). Whether to add a nullable `user_id` for new rows is Q2.

### 3.5 Indexes: one per query

| Query (section 2.4) | Index | Shape |
| --- | --- | --- |
| R1, R2, R3, R7, R10-R14 `get(media_id)` | primary key | point probe; R2 now costs one probe per image request |
| R4, R5 shared browse by language, published, newest first, filter level/topic/tag | `ix_media_entries_browse (library, language, status, created_at DESC, media_id DESC)` | range scan, keyset-pageable; level/topic/tag filtered in SQL over the range (a shared library is thousands of rows; no GIN on `tags` proposed) |
| R8, R9 operator listing, all languages and statuses | `ix_media_entries_library_created (library, created_at DESC, media_id DESC)` | keyset-pageable |
| R6 `resolve_by_lesson_id` (today a scan) | `ix_media_entries_lesson_id (lesson_id) WHERE lesson_id IS NOT NULL` | point probe; **unique if the data allows** (Q1) |
| R15, quota sum, a learner's own uploads | `ix_media_entries_owner (owner_token, language, created_at DESC, media_id DESC) INCLUDE (stored_bytes) WHERE library = 'personal'` | index-only sum by owner (all languages: `owner_token` prefix); per-language listing |
| Orphan reconciliation (section 9.4) | `ix_media_entries_owner` + `created_at` | read-only operator query |
| Counts by library/status (admin) | `ix_media_entries_library_created` | |

No index is added "just in case". Section 12 asserts each query uses its named index at volume.

---

## 4. Repository and behaviour (what the code change is, after approval)

A `PostgresMediaLibraryRepository` implements the existing `MediaLibraryStore` surface (`list`, `get`, `upsert`, `delete`) so
the ~20 call sites above keep working, plus:

- `list_page(library, language, status, after, limit)` and `list_owned_page(owner_token, language, after, limit)`: **keyset
  pagination** on `(created_at, media_id)`, `limit <= 50` default 24; admin listings page the same way (R8/R9 lose the
  unpaged `list`).
- `set_status(media_id, status)`: a single `UPDATE ... SET status, updated_at, version = version + 1 WHERE media_id AND
  library = 'shared'`. **R11 stops being a read-modify-write of the whole entry**; the lesson, the owner and the other fields
  cannot be overwritten by a stale copy.
- `upsert(entry)`: `INSERT ... ON CONFLICT (media_id) DO UPDATE` in one transaction that also writes/clears the payload row,
  the extracted columns and `updated_at`. Idempotent for the admin re-import (R12) and the direct-URL token id.
- `sum_upload_bytes(owner_token)` and `insert_personal(entry, byte_limit)`: see section 8.
- `delete(media_id)`: `DELETE` (the payload row cascades). Order of operations in `_remove_personal_entry` is **unchanged**
  (files first, row last), so a failed file removal leaves the row and its bytes in the sum.
- Errors: a database error raises `MediaStoreUnavailable` (replaces `MediaIndexUnavailable`/`last_read_issue`); routes keep
  their 503 `media_library_unavailable` mappings; readers keep today's degradation (R3 returns not found, R4 returns `[]`,
  logged) so a PostgreSQL outage cannot raise an unhandled 500 in a learner room. This is an availability behaviour, not a
  fallback to another authority: nothing reads `index.json` instead.
- `visible_to` stays a pure function in code, applied after `get`; the SQL layer additionally offers an owner-scoped `get` so
  R2 can refuse in one probe. The 404-never-403 rule is unchanged.
- The per-process lock (`_WRITERS`) is deleted with the file store's write path; concurrency is the database's: row-level for
  upsert/status, an advisory lock keyed by `owner_token` for the quota (section 8).

The file store class stays in the tree **for the import script only** (to read the archive and to run the contract tests
against both implementations until cutover), is not constructed by `app.py` after cutover, and is deleted in a later cleanup.

---

## 5. Migration of existing `index.json` entries (one time, operator-run)

Not Alembic data migration, not at startup (invariants). An operator script, `scripts/import_media_index.py`, run once under a
human gate after the schema revision is applied.

1. **Preconditions**: a fresh backup of PostgreSQL and a copy of `index.json` (and its size, SHA-256 and entry count recorded);
   the application is stopped or has `media` writes disabled (the maintenance window, section 10); schema `0024` is the head.
2. **Read and validate**: parse `index.json`, recompute the integrity hash, run `validate_entry` on every entry. **Any
   failure aborts before anything is written** (the file is evidence; it is never repaired).
3. **Map** each entry to rows: scalar columns; `thumbnail` -> `thumbnail_kind/ref`; `source`, `playback` verbatim;
   `owner_token` = `source.owner` for personal rows, and for a personal row **without** an owner the explicit
   `owner_token('legacy')` (the implicit rule made explicit; the count of such rows is reported); lesson -> extracted columns +
   payload row; `segment_count` from the payload; `created_at` parsed; `updated_at = created_at`, `version = 1`.
4. **Measure bytes**: for each `provider='upload'` row, `stored_bytes` = the sizes of `media/<provider_media_id>/original*` and
   the thumbnail asset, read from the asset store (a `stat`, never the bytes). A missing asset sets `stored_bytes` NULL and is
   listed in the report (the entry is still imported; nothing is deleted).
5. **Write**: batches of 1,000 in transactions, `INSERT ... ON CONFLICT (media_id) DO NOTHING`. **Idempotent**: a second run
   inserts nothing. If a row already exists and differs from the file's entry, the script **reports a conflict and does not
   overwrite** (the database is the authority once written).
6. **Verify** (the script's exit code depends on it): (a) row count == entry count, and per `(library, language, status)`;
   (b) every row, read back through the repository, equals the file's entry field for field (a canonical-JSON comparison of
   the reconstructed entries, ordered by id) and its SHA-256 equals the file's `entries` canonical hash; (c) every personal
   row has `owner_token`; (d) `lesson_id` uniqueness report (Q1); (e) asset existence for every `thumbnail.ref` and every
   playback path under `/api/media/files/`; (f) the report (counts, legacy-owner rows, missing assets, conflicts, bytes by
   library) is written to a file for the Decision Log entry.
7. **Dry-run is the default**; `--apply` writes. A dry-run touches nothing but its report.

No dual-write: the script is the only writer besides the new repository, and it runs while the application is not writing.

---

## 6. Cutover

| Step | Action | Gate |
| --- | --- | --- |
| 0 | Review approved; human authorizes the `git mv` of the migration from `migrations/proposed/` to `versions/` | human |
| 1 | Backup (database + `index.json` + a note of the asset root) | human |
| 2 | Apply `0024` with `scripts/bootstrap_runtime_schema.py` (one invocation; additive; sub-second expected, section 12) | human |
| 3 | Maintenance window opens: the app is stopped (the sandbox is one container) | human |
| 4 | `import_media_index.py` dry-run, then `--apply`, then the verification report is attached to the Decision Log | human |
| 5 | Deploy the code that constructs `PostgresMediaLibraryRepository` instead of `FileMediaLibraryStore`; `index.json` is renamed `index.json.pre-postgres` (an archive: read-only, never read by the app) | human |
| 6 | Smoke: shared browse, a shared item opens, a learner upload + its thumbnail + delete, admin status change, admin import, the account-deletion remover on a test account | agent, reported |
| 7 | Window closes | human |

**Read path** after cutover: every R-row of 2.4 goes to the repository. **Write path**: W1-W3 and the quota insert go to the
repository only. **There is never a moment with two authorities**: before step 5 the old code runs and the new tables are
empty/ignored; after step 5 the new code runs and the file is an archive. A rolled-back deployment (step 5 reverted) would
resume the old code on the **archived** file, so any entry written after step 5 is not in it (section 7).

---

## 7. Rollback

- **Before step 5** (schema applied, import done, code not deployed): nothing depends on the new tables; `downgrade()` drops the
  two tables (rehearsal only, as D4: it drops data).
- **Inside the window after step 5** (before writes resumed): re-deploy the previous code and restore `index.json` from its
  archive name; the new tables are left in place, unread.
- **After writes resumed**: **restore the pre-cutover backup**, never downgrade. Entries (personal uploads, admin imports)
  created since cutover are then missing from the restored file; their asset files remain on the asset store as orphans, listed
  by the reconciler (9.4). A reverse export from PostgreSQL to a new `index.json` is **not proposed** (it would be the
  reverse sync the invariants forbid); if the human wants one it is its own reviewed decision.

---

## 8. Byte accounting for the uploaded-media quota (D-107.3, D-108.7)

`ACCOUNT_RECORD_LIMITS.md` 4.5 defines `ORENA_LIMIT_MEDIA_UPLOAD_BYTES` (10 GiB default, per account across languages, original +
thumbnail, live uploads only). With this schema:

- **The size is on the entry**, server-measured at upload (`stored_bytes`, set by `import_upload` from the streamed byte count
  and the thumbnail it wrote), never taken from the client. The client's import record (`works`, form `upload`, `mediaId`) names
  the entry; the account-record guard resolves the entry, checks `owner_token` and uses **its** `stored_bytes` (the earlier
  review's P3-2).
- **Sum by account**: `SELECT coalesce(sum(stored_bytes), 0) FROM media_entries WHERE library = 'personal' AND owner_token =
  :t AND provider = 'upload'`, an index-only scan of `ix_media_entries_owner` (the `INCLUDE (stored_bytes)` column), O(that
  account's uploads), independent of the total.
- **Atomic quota check**: `insert_personal(entry, byte_limit)` runs in one transaction: `pg_advisory_xact_lock(hashtextextended
  (owner_token, 0))`, the sum, the comparison `sum + entry.stored_bytes <= limit`, the insert. Two concurrent uploads of one
  account cannot both pass; uploads of different accounts do not contend. A refusal rolls back and the importer deletes the
  files it just stored (the order in `ACCOUNT_RECORD_LIMITS.md` 4.5, stage 2).
- **Removal-pending bytes stay counted without any extra field**: the row is deleted last (section 4), so a file removal that
  failed leaves the row and its `stored_bytes` in the sum until the retry succeeds (the earlier review's P3-5).
- The **pre-check** (stage 1: declared `Content-Length` against `limit - sum`) is the same sum without the lock.
- The **uploads-per-hour** rail counts from the account's import records in `works`, as specified there; this schema does not
  change it.
- **Orphans**: an entry whose upload never got an account import record (a crash between the media write and the record) is
  counted in the sum. Its detection is a read-only operator query (9.4), not an automatic deletion.

---

## 9. Other cross-cutting behaviour

**9.1 Pagination.** Every list that can exceed a page is keyset-paged by `(created_at, media_id)` with an opaque cursor: the
shared browse (R4/R5), the operator listings (R8/R9) and a learner's own uploads. The account-import list (`GET /api/imports`,
D-108.6, in `works`) pages on its own index (`ix_works_scope_sequence`) and is specified in `ACCOUNT_RECORD_LIMITS.md`, not here.

**9.2 Admin console.** The console reuses `media_library_api` and the store protocol; no new admin API, no change to
`require_admin`, no second admin backend (AGENTS section 7, D-101 E). The changes inside it are mechanical: R9 pages; R10 reads
`has_lesson`/`segment_count` instead of the payload; R11 calls `set_status`; R12/R13 are unchanged calls; the `storage.read_issue`
field reports the database state (`ok` / `unavailable`) instead of the file's. The pinned `Orena Admin.dc.html` is unaffected
(it renders the same JSON).

**9.3 Deletion enumeration (D-055(b)).** The SQL half moves into the enumerated tables: `media_entries` (rows with
`library='personal'` and the account's `owner_token`, in every language) and `media_entry_payloads` by cascade; the **file half
stays** in `FILE_STORES` (the asset bytes under `media/<token>/`), with `delete_all_owned_media` now iterating
`list_owned_page(owner_token)` instead of scanning every account's entries. No runtime deletion path exists yet (D-055); this
proposal adds none. The enumeration test (D4 section 9 pattern) is updated to assert both halves.

**9.4 Reconciler (read-only).** An operator query lists (a) personal entries older than N hours with no live import record
(`works` kind `imported`, form `upload`, `mediaId`) and (b) asset prefixes under `media/` with no entry. It reports; deletion of
orphans is a human-gated operator action.

**9.5 Caching.** None added. R2 is one primary-key probe; the response's cache headers are unchanged.

---

## 10. Maintenance window and availability [I]

The sandbox and lane runtimes are single-container. The window is the time to stop the app, run the import and the smoke: sized
from the rehearsal (section 12), expected minutes for a lane-sized file (hundreds to thousands of entries) and under an hour at 2 M
entries. Production is not touched by this proposal. During the window media routes are unavailable (the container is stopped);
nothing is served from a half-state.

---

## 11. Tests

Unit/API tests run on SQLite where the repository can (the D4 pattern) and on PostgreSQL where it cannot; **PostgreSQL-only
proofs are local execution, not CI evidence** (`ORENA_TEST_POSTGRES_URL`; CI has no PostgreSQL service).

| Area | Test |
| --- | --- |
| Contract parity | one suite (`list`, `get`, `upsert`, `delete`, `visible_to` matrix: shared, personal owner, other account, other language, legacy owner, no owner) runs against `FileMediaLibraryStore` and the PostgreSQL repository with identical results, **before** cutover |
| Schema | every CHECK refuses its bad row; the owner/`source.owner` agreement CHECK; `thumbnail` kind/ref CHECK; FK cascade of the payload; the extracted columns equal the payload (property test over generated entries) |
| Indexes | `EXPLAIN` for each query of 3.5 names its index at volume (no seq scan) |
| Import tool | dry-run writes nothing; apply twice = no change; a differing existing row is a reported conflict and is not overwritten; a corrupt/hash-mismatched index aborts with zero rows written; the verification catches a tampered row; legacy-owner count is reported; missing assets listed |
| Concurrency | 8 concurrent uploads of one account at the quota edge admit exactly the limit; uploads of different accounts do not block; concurrent admin `set_status` and reprocess do not lose the lesson; `ON CONFLICT` upsert is idempotent |
| Behaviour parity | R1-R15 through the HTTP routes: shared browse, open by id and by lesson id, file and thumbnail privacy (404 for another account/language), delete order and removal-pending, `delete_all_owned_media` for one account leaves others |
| No dual write | the repository never opens `index.json` (a test points `MEDIA_LIBRARY_ROOT` at a directory containing a poisoned file and an unreadable one and asserts startup, reads and writes succeed untouched); `app.py` with PostgreSQL unavailable does not fall back to the file (media routes 503, browse degrades empty and logged) |
| No startup import | startup against an empty `media_entries` and a populated archive imports nothing |
| Pagination | keyset cursor is stable under concurrent inserts, no duplicates or gaps across pages, page size bounds |
| Admin | the console routes of R9-R13 return the same JSON as before for a fixture library (golden comparison) |
| Deletion enumeration | `media_entries` and `media_entry_payloads` are in the enumeration; both halves asserted |
| Regression | existing media/Listening/admin tests unchanged and green; the fail-closed bad-index tests are replaced by the database-unavailable equivalents |

---

## 12. Rehearsal plan (PostgreSQL up/down/up at volume)

Format of `LEARNER_RECORDS_D4.REHEARSAL.md`: a throwaway `postgres:17-alpine` container on its own Docker network, removed after
each run; `scripts/rehearse_media_metadata_schema.py` (proposed) run in the application image with the repository mounted
read-only, one revision per invocation, when no other lane is doing heavy Docker work (D-101 working rules). Results are
recorded in `MEDIA_METADATA_POSTGRES.REHEARSAL.md`.

| Run | State | What it proves |
| --- | --- | --- |
| 1 | `0023 -> 0024 -> 0023 -> 0024` on an empty database | the revision applies, downgrades (dropping only the two tables) and re-applies; the schema after downgrade equals the schema captured at `0023` |
| 2 | `--volume 100000`: 100 k personal + 5 k shared (with payloads of 25-150 KB) rows | per-revision timing (expected sub-second, additive), per-query `EXPLAIN` index use, p50/p95 latency of `get`, browse page, owner sum, `lesson_id` probe |
| 3 | `--volume 2000000`: about three years of personal uploads at the target | the same at the planning volume; table and index sizes (`pg_total_relation_size`) replace the estimates of 3.3; owner-sum latency for a heavy owner (about 100 uploads a year, 300 in three) and for a synthetic 10,000-row owner |
| 4 | import tool at volume | `import_media_index.py` against a generated `index.json` of 100 k and of 2 M entries: wall time (the maintenance-window input), memory, idempotent second run, verification pass; a corrupt file aborts with zero rows |
| 5 | probes | CHECK refusals; owner/`source.owner` agreement; advisory-lock quota race at the edge (8 workers); keyset paging under concurrent insert; JSONB round-trip equality of `playback`, `source`, `tags` and a 150 KB payload; non-ASCII titles (Chinese), emoji, NUL rejection behaviour of JSONB documented |
| 6 | old-code compatibility | the previous release's `users`/`works` inserts and reads work on the `0024` schema (the revision touches no existing table) |

Pass criteria: every probe passes, every revision invocation under the D4 window rule (15 minutes floor; expected seconds), every
query in 3.5 index-served at 2 M rows, the import verification exact. A run at the full target volume is recorded before :8000.

---

## 13. Questions for the reviewer and the human

1. **`lesson_id` uniqueness.** `resolve_by_lesson_id` assumes one entry per `lesson_id` (first match wins). Make
   `ix_media_entries_lesson_id` **unique** if the import report shows no duplicates; otherwise define the tie-break (newest
   published shared). Which?
2. **Owner column.** Keep `owner_token` (digest of the account key) as the only owner column, or add a nullable `user_id` for new
   rows (requires the request's `users.id`, which the importer has) to make the D-055(b) deletion a plain SQL delete? Both can be
   done; the second is extra schema.
3. **Orphan policy.** The reconciler only reports (9.4). Should a personal entry with no import record after N hours be
   auto-deleted (files first), or stay a human-gated cleanup?
4. **Legacy owner rows.** Rows with no `source.owner` become `owner_token('legacy')`, visible to the single local account only
   and refused to signed-in accounts (today's rule). Confirm, or delete them in the import (they are lane-era test data)?
5. **`updated_at` and `version`** are new fields the file never had. Is `version` (an optimistic counter for admin status and
   reprocess) wanted now, or is `updated_at` enough?
6. **Shared and personal in one table** (a `library` discriminator) or two tables? One table matches the current model and the
   one resolver (R1); two would separate admin content from learner records and make the account-deletion enumeration cleaner.
7. **Window and archive.** Is a stop-the-app maintenance window acceptable for the lane, and how long is `index.json.pre-postgres`
   kept (it holds no secrets; it holds titles and provenance, personal rows included)?
8. **Order with the limits.** `ACCOUNT_RECORD_LIMITS.md` makes this a gate for anything beyond :8021 (G1) and its byte rail depends
   on `stored_bytes`. Implement this before the byte rail, in the same milestone, or after with an interim sum scan of the file?
   (Recommended: before, so the rail never ships on the file.)

---

## Appendix A. Facts re-read for this proposal

HEAD `0f14ed7`. `media_library_store.py` (281 lines): `FileMediaLibraryStore._read/_write/list/get/upsert/delete/assert_writable`,
`MediaIndexUnavailable`, `visible_to`, `owner_token`, `validate_entry`. `media_library_api.py`: lines cited in 2.4.
`listening_api.py:113-130,436-460`. `admin_console_api.py:292-306,560-575,790-800,1150-1187,1325-1335`.
`media_source_import.py:285-300,344-390`. `persistence/deletion_enumeration.py:44-52`. `app.py:598-610,780`. `persistence/` has no
media table today; migrations end at `20260930_0023`.
