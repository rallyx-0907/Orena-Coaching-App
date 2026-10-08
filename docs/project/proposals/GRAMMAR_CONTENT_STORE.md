# Proposal (D-105 point 4): the grammar content store, Admin import and `/api/grammar/v1/*`

Status: **PROPOSED, revision 2** (2026-09-30, `codex/work` at `72cd4cd`), answering the independent review
`GRAMMAR_CONTENT_STORE.REVIEW.md` (REQUEST CHANGES at revision 1: no P0, two P1s, eleven P2s; the finding-by-finding
mapping is section 18). Document only: no code, schema or migration file is changed by it. Process (AGENTS §1
"Architecture review authority", D-054, D-102): proposal -> **independent architecture review** -> human approval ->
migration rehearsal on a throwaway PostgreSQL -> code and tests -> the human applies the migration to the lane runtime
(:8021 only). The author of this file may not self-approve it.

Legend: **[V]** read in code or docs at `72cd4cd`, or in the named PR/branch; **[I]** inferred, to verify at
implementation. `GCC` = `docs/project/GRAMMAR_CONTENT_CONTRACT.md` (merged v0.4; PR #67 patch is OPEN and is read
only, cited as "#67"); `ID` = `docs/grammar_lab/INTEGRATION_DESIGN.md` on `origin/feature/grammar-lab-pipeline`
(`a6f9126`); `ADA` = `docs/product/ORENA_ACCOUNT_DATA_ARCHITECTURE.md`; `D4` = `proposals/LEARNER_RECORDS_D4.md`. Some
files in the working tree carry unrelated uncommitted edits, so code references to Reading Admin are by function name.

## 0. The decision this proposal implements, and what it replaces

D-105.4 [V `DECISION_LOG.md:3696`]: Grammar Lab is upstream; an approved export is imported into the **database**
through Admin, reviewed and published there; learners read a published grammar API; content does **not** ship as
JSON with the source. That replaces `ID` §1 ("published set, read-only, ships with the code, loaded at startup").
Everything else in `ID` that is not storage is reused: the route shape (`ID` §3), `by-error` (`ID` §5.1), the redirect
idea (`ID` §5.2, now the R5 map of section 9), the cutover order (`ID` §6, re-ordered in section 13). D-100.4 [V] held
`/api/grammar/v1/*` for this review; D-104 H-4 [V] requires the API to validate the published point before accepting
progress; D-105 H-20 [V] requires completion and quiz result in one atomic write.

## 1. Summary

| # | Topic | Proposal | Section |
| --- | --- | --- | --- |
| 1 | Nature of the data | Shared **content** (like the vocabulary catalog and the Reading engine), not learner data. Adds no learner-owned table or column. | 3 |
| 2 | Tables (one additive migration, new tables only) | `grammar_functions`, `grammar_points`, `grammar_point_versions`, `grammar_r5_map`, `grammar_point_error_tags`, `grammar_import_batches`, `grammar_review_events`, `grammar_catalog_state` | 3 |
| 3 | Migration | `2026MMDD_0024_grammar_content_store`, in `migrations/proposed/` first, no change to any existing table, cycle-free foreign keys, an immutability trigger. Downgrade drops content only. | 4 |
| 4 | Trust boundary | One `schema_version`, a vendored closed schema validated with `jsonschema` (recommended; human decision 8), unknown keys rejected, internal fields forbidden, a fixture corpus test. Implemented only against a **merged** contract. | 5 |
| 5 | Import | Admin uploads one approved **export package**; dry run returns a diff; commit is idempotent by package hash; only `status: approved` points enter; imported versions are **not** visible. | 5 |
| 6 | R5 ids | An explicit `r5_map` in the manifest with dispositions (replaced, merged, split primary/secondary, dropped); stored independently of publish state; the contract contradiction on splits is stated and a contract fix proposed, not decided here. | 9 |
| 7 | Lifecycle | Version: `imported -> accepted / rejected -> superseded`. Point: `unpublished <-> published`, `archived`. Publish is an explicit, atomic, audited admin act with a hard, batch-attested rights gate and a dangling-reference gate. | 6 |
| 8 | Learner API | `GET /api/grammar/v1/points?level=`, `/points/{id}`, `/by-error`, `/progress`, `PUT/DELETE /progress/{id}`. Serves only the published version, whitelisted contract JSON. | 7 |
| 9 | Progress | Reuse `grammar_progress` + 0023, `INSERT ... ON CONFLICT`, one statement. The client grades (the key is served); the server re-checks and stores its own arithmetic. Lands after D4's model changes. | 8 |
| 10 | Languages | `language_code` `en`/`zh` today (`zh-Hans` in content maps to `zh`); no enum, `ja` needs configuration and content rules, not a schema change. | 10 |
| 11 | Caching | `content_hash` per version, `catalog_revision` per language, ETag/304, revision read **before** content. | 11 |
| 12 | Access | Admin routes behind `require_admin` + same-origin + audit + rows in the authorization matrix. Learner routes never return unpublished content. | 12 |
| 13 | `/next` | Repoint the two readers of `grammar-source.js`; the screens do not change. | 13 |
| 14 | Holds | No AGENTS §7 hold is resolved. Independent review is required for the schema. | 15 |
| 15 | Open decisions | Ten, each with a proposed answer, section 17. | 17 |

## 2. Findings that shape the design

1. **The R5 progress key is a composite, not the R5 id.** `_grammar_storage_key` writes
   `"{language}:grammar:v{content_version}:{lesson_id}"` [V `app.py:2039-2042`], and both `set_grammar_completed`
   implementations store that string in `lesson_id` [V `app.py:2157-2168`; `learning_repository.py:323, 715-724`;
   `tests/test_grammar_storage_namespace.py:17` asserts `en:grammar:v2:a1-present-simple`]. `D4` I11 says "R5 rows already
   written keep their R5 id" and joins on `aliases` [V `D4:437-442`]; a join on the bare R5 id matches **no** existing row.
   **This proposal joins on the composite, parsed strictly (section 9), and `LEARNER_RECORDS_D4.md` needs the same
   correction** when it is next amended (it is not edited here). This is a defect in D4's wording, not in D4's schema.
2. **`grammar_progress.lesson_id` has no foreign key and must not get one.** It is `VARCHAR(255)` unique on
   `(user_id, language_code, lesson_id)` [V `models.py:214-226`], holds R5 keys, and a point later archived must not
   cascade into a learner's history.
3. **The contract is not machine-checked in this repo, and is not yet settled.** `grammar_lab/schema/grammar_set.schema.json`
   here is the Phase 0 schema: `schema_version` const `"0.2"`, point-level `title`, `summary`, `blocks` [V
   `grammar_set.schema.json:13, 103-127`], older than GCC v0.4 and #67; `jsonschema` is not in `requirements.txt` [V]. The
   pipeline cannot run in the app. Section 5 answers this.
4. **The fixtures cannot be imported as they are.** PR #68's 13 points are `draft_ai`, `sample: true, approved: false`
   [V PR #68 body]. Under D-105.4 the importer refuses them; converted copies are the corpus of section 14.
5. **Vocabulary publication is not hard-gated today** ("decision support, not a permission gate") [V
   `admin_console_api.py:1028-1032`], while D-105.5a makes copyright a hard gate for Reading (`publication_blockers` in
   `reading_admin_api.py`). Whether grammar follows Reading is decision 6.
6. **GCC §9 contradicts itself on splits** (section 9.1). The alias model cannot be finalised without a contract fix.
7. **The quiz key is content.** `quick_practice[].answer` sits inside the point and the seam and screen grade in the
   browser [V `screens/grammar-concept/screen.js:120`], so the browser holds the key. Section 8 is written for that fact.

## 3. Tables

All new, all shared content, none keyed to a learner. Types follow the existing catalogs: `sa.JSON` for documents,
`DateTime(timezone=True)`, string ids for natural keys, `Uuid` for rows [V `0008:32-120`, `0015`]. `[I]` PostgreSQL JSONB
is not used elsewhere in the chain; `sa.JSON` keeps SQLite (the hermetic test backend) working. **No foreign-key cycle**
(review P2-2): `grammar_points` never points at a version; the version points at its point.

**`grammar_functions`** (Library group labels, language-neutral). `id` (`fn.<snake>`, PK); `title` JSON (`{vi, en, zh-Hans}`,
all three required, #67 item 1); `batch_id` FK; `updated_at`. If two batches disagree on a label the **later committed
batch wins**, the diff shows the change before commit, and a `function_label_changed` event records before/after.
Publishing a point whose `function` has no complete label is refused.

**`grammar_points`** (identity and serving state, one row per point id, created at first import). `id` VARCHAR(120) PK
(`en.present_perfect_experience`, immutable, GCC §0); `language_code` VARCHAR(20); `lifecycle`
(`unpublished | published | archived`, default `unpublished`); `published_at`, `unpublished_at`; `created_at`,
`updated_at`. **Serving columns, all NULL until first publish** and rewritten in each publish transaction: `function`,
`level_framework`, `level_value`, `level_rank`, `sequence`, `point_type`, `native_title`, `native_title_pinyin` JSON. Index
`(language_code, lifecycle, level_rank, function, sequence)`. Invariant (a publish-transaction rule with a test, not a
CHECK across tables): `lifecycle = 'published'` <=> exactly one version of the point has `is_published`.

**`grammar_point_versions`** (immutable content). `id` Uuid PK; `point_id` FK -> `grammar_points`; `version` INT (GCC
`version`); `content` JSON (the point as exported, closed-schema validated, section 5); `content_hash` VARCHAR(64) (sha256 of
canonical JSON, section 11); `source_status` VARCHAR(20) (always `approved`, CHECK); `review_status`
(`imported | accepted | rejected | superseded`); `is_published` BOOL default false; `rights_status`
(`unknown | cleared | restricted`); `provenance` JSON (the manifest's per-point upstream reviewer, `reviewed_at`, `run_id`,
`model`, `prompt_version`, and the point's `source_refs`); `batch_id` FK; `imported_at`; `reviewed_by`, `reviewed_at`,
`review_note`. UNIQUE `(point_id, version)`; UNIQUE `(point_id, content_hash)`; **partial UNIQUE `(point_id) WHERE is_published`**
(one published version per point as a database fact; a partial unique index works on PostgreSQL and SQLite [I]). **Immutability
is enforced, not conventional (review P2-3):** a PostgreSQL `BEFORE UPDATE` trigger rejects any change to `point_id`,
`version`, `content`, `content_hash`, `source_status`, `provenance`, `batch_id`, `imported_at`, allowing only `review_status`,
`is_published`, `rights_status` and `reviewed_*` (the pattern `essay_review_history` uses [V `D4` I19; `0021`]); SQLite, the
test backend, has the same rule as a repository invariant with a test. Content is never edited in Orena: a fix is a new
version from upstream (D-100.1).

**`grammar_r5_map`** (R5 id resolution, section 9; **independent of publish state**). Surrogate `id` Uuid PK; `language_code`;
`r5_id` VARCHAR(255) (the bare R5 lesson id); `point_id` FK -> `grammar_points` **nullable**; `disposition`
(`replaced | merged | split_primary | split_secondary | dropped`); `is_primary` BOOL; `batch_id` FK; `created_at`. Constraints:
CHECK `(disposition = 'dropped') = (point_id IS NULL)`; partial UNIQUE `(language_code, r5_id) WHERE is_primary`;
partial UNIQUE `(language_code, r5_id) WHERE point_id IS NULL` (a dropped id appears once); UNIQUE `(language_code, r5_id,
point_id)`. One R5 id therefore has at most one primary point (or is dropped), and may have further secondary pieces.
Rows are **written when the batch carrying the `r5_map` is committed**, not when anything is published, and are never deleted
by unpublish, archive, or the later removal of the R5 tables (section 9.3).

**`grammar_point_error_tags`** (projection of the published version, serving only). `point_id`, `error_tag`, `has_mistake` BOOL
(the point has a `common_mistakes` entry with that tag, the ranking key of `ID` §5.1); PK `(point_id, error_tag)`; index
`(error_tag)`. Rebuilt in the publish transaction, emptied by unpublish and archive.

**`grammar_import_batches`** (the receipt, the pattern of `vocabulary_source_imports` [V `0008:76-105`]). `id` Uuid;
`language_code`; `package_hash` VARCHAR(64); `filename`; `schema_version`; `set_version`; `source_commit`; `exported_at`;
`status` (`imported | rejected`); counts `new_count, changed_count, unchanged_count, refused_count, unlisted_count`; `diff` JSON
(bounded); `refusals` JSON (code, point id, path); **`manifest` JSON (the manifest without point bodies: it holds the
`validator` verdict and the `r5_map`, so they stay auditable, review Recommendation 9)**; `rights_basis`,
`rights_attestation` (text), `rights_attested_by` (section 6); `imported_by`; `created_at`. **A rejected batch writes a receipt
(status `rejected`, its refusals) and no content rows; `already_imported` is answered only for an `imported` batch**, so a
corrected re-upload of a rejected file is a fresh attempt. Partial UNIQUE `(package_hash) WHERE status = 'imported'`. A dry run
writes nothing.

**`grammar_review_events`** (append-only; the pattern of `reading_review_events` [V `models.py` `ReadingReviewEvent`;
`reading_content_repository.py` `_record_event`]). `id`, `point_id`, `version_id` nullable, `actor`, `action`
(`imported | accepted | rejected | rights_set | published | unpublished | archived | restored | function_label_changed |
r5_map_changed`), `reason`, `changes` JSON, `created_at`. Written **in the same transaction** as the change; `audit_logs` is
written after it, best effort, as Reading does (`_audit` in `reading_admin_api.py`).

**`grammar_catalog_state`**. `language_code` PK; `revision` INT; `updated_at`. Incremented in every publish, unpublish, archive
and bulk publish transaction. It is the catalogue ETag source (section 11). It is **not** bumped by an import (imports change
nothing learners see) or by an R5 map change (which affects `GET /points/{id}` for old ids only, ETag-independent).

Deliberately absent: a quiz-key table (the key is inside `content`), a learner-facing progress table (section 8), a stored copy
of the package file (the manifest and version rows are the record).

## 4. Migration plan (files are NOT written here)

One revision, `migrations/proposed/2026MMDD_0024_grammar_content_store.py`, `down_revision = "20260930_0023"` [V `0023:26-27`],
creating the eight tables with their indexes, the partial unique indexes and CHECKs, and the PostgreSQL immutability trigger
(dialect-guarded). It changes **no existing table**, takes no lock on `grammar_progress` or any learner table, and so needs no
`SET LOCAL lock_timeout` beyond the chain convention [V `0023:37-45`]. Every foreign key points one way, so `create_table` order
is `grammar_functions`, `grammar_import_batches`, `grammar_points`, then versions, map, tags, events, state.

- **Downgrade** drops the eight tables (and the trigger). Unlike 0017-0023 it holds no learner data, so it is safe to rehearse
  and run; the content is restored by re-importing the export.
- **Rehearsal**: extend `scripts/rehearse_learner_records_schema.py` (or a sibling) on a throwaway PostgreSQL: up, down, up;
  import a synthetic 1,000-point package (about 20 KB each) and 100,000 `grammar_progress` rows; check the three read paths'
  plans use their indexes; check that a failed publish leaves state unchanged; **check the ETag ordering (a publish between the
  two reads of a `GET /points` never yields old content labelled with a newer revision)**; check the trigger rejects an update to
  `content`; time the synchronous import (section 5.5).
- **Apply**: `scripts/bootstrap_runtime_schema.py`, one revision, after a backup, on :8021 only, on the human's authorization
  (D-105.1 pattern). Startup never applies it (D-002). :8000/:8010 are not touched.
- **Nothing else migrates**: no data move, no R5 rewrite, no startup import.

## 5. Trust boundary and Admin import

### 5.1 What is trusted, and the single contract version

Everything in the uploaded file is untrusted, including the manifest's `validator` verdict, which is a self-attested boolean
covered by no hash. It is recorded for audit and **never relied on for safety**. Safety comes from deep validation performed by
the app, then a human review.

- **Exactly one `schema_version` is accepted**, held in one constant, `SUPPORTED_SCHEMA_VERSION`, whose value is the version the
  merged contract names. Today the repo's schema says `0.2`, GCC says v0.4 and #67 (**open**) changes `target_lang` and the locale
  rules to `zh-Hans`. **Code for this proposal starts only against a merged contract** (dependency of step 2, section 13): if #67
  is not merged, this proposal implements nothing that #67 changes. A later contract version is a new constant, a new vendored
  schema and a reviewed change, never a silent widening; a package of any other version is rejected.
- **The vendored schema is the contract's closed schema** (`additionalProperties: false` at every object), copied into the repo
  at `writing_coach/grammar_schema/` with the upstream commit recorded. It is a schema, not content, so it does not violate
  D-105.4; the guard test of section 14 allows only that directory.
- **Deep validation route (decision 8): add `jsonschema` (a reviewed new dependency) and validate every point against the vendored
  schema, plus app-side cross checks (5.3).** Recommended over a hand validator because the two screens read deeply nested
  structures (formula roles, example spans, timeline data, options, pinyin arrays) and a hand validator drifts silently. If the
  human declines the dependency, the fallback is a hand-written validator that must cover **every field either screen reads**,
  be generated from or checked against the schema, and pass the corpus test below; the shallow "required top-level fields"
  check of revision 1 is withdrawn in both cases.
- **Unknown keys are rejected**: at the top level and at every nested object the schema closes (mismatch = hard failure). The
  point object may carry **only** contract keys. `provenance`, `review`, `flags` and Grammar Lab's internal fields are
  **forbidden in point files** (they belong to the manifest, whose per-point `provenance` is stored in `provenance` and never
  served). As belt and braces the API serves `content` through a whitelist of the contract's top-level keys, so even a future
  bug in import cannot publish reviewer identity, model names or routing flags to learners.

### 5.2 The package

A single upload (`.zip`, or one `.json` bundle for small sets). Shape from PR #68's fixture set [V] plus the manifest fields the
importer needs [I, to be agreed with the Grammar Lab lane, decision 2]:

```
package.json    {schema_version, set_version, language, source_commit, exported_at,
                 points:[{id, version, content_hash, provenance:{reviewer, reviewed_at, run_id, model, prompt_version}}],
                 r5_map:[{r5_id, point_id|null, disposition, is_primary}],
                 validator:{tool, version, passed, codes:[...]}}
functions.json  [{id, title:{vi,en,zh-Hans}}]
points/<id>.json  one GCC point object each, "status": "approved", closed keys only
```

`content_hash` uses the normative canonical form of section 11. The export command (`cli export-package`; `ID` §1's `cli publish`
renamed, it exports and does not publish) is Grammar Lab's. This proposal specifies only what Orena accepts.

### 5.3 Endpoints (`/api/admin/grammar/*`, section 12) and validation

| Route | Effect |
| --- | --- |
| `POST /imports/validate` (multipart) | Dry run. Report and diff of 5.4. **Writes nothing.** |
| `POST /imports` (multipart, `package_hash` echo, `rights_basis`, `rights_attestation`) | Commits. `201` with the receipt; `200 {already_imported: true, batch}` only if an `imported` batch has the hash. Refuses if the echoed hash differs from the recomputed one. A hard failure writes a `rejected` receipt (`422`). |
| `GET /imports`, `GET /imports/{id}` | Receipts, newest first, cursor-paged like Reading (`list_jobs`). |

**Hard failures reject the whole batch** (cross-point checks would otherwise be unsound): package/manifest shape; a
`schema_version` other than `SUPPORTED_SCHEMA_VERSION`; every listed point file present and vice versa; recomputed
`content_hash` equals the manifest's; **closed-schema validation of every point** (5.1); `id` starts with the package language
prefix and equals its filename; `target_lang` maps to the package `language`; duplicate ids; `contrasts` symmetric; `prereqs`
acyclic and resolvable; `aliases` unique across the package; every `function` has a complete label; the `r5_map` is consistent
(section 9.2). **Reference targets** (`prereqs`, `contrasts`, `compare.with`) resolve to a point in the package or to a point
already stored with at least one version `accepted` or `published`.

**Per-point refusals** (the point is skipped and reported, the batch continues): `not_approved` (`status != approved`);
`version_lower_than_stored`; `version_not_bumped` (same `version`, different hash); **`content_already_stored`** (a higher
`version` whose hash already exists for that point, e.g. upstream reverting to earlier content, which would otherwise hit
`UNIQUE (point_id, content_hash)` as a database error); **`content_previously_rejected`** (the hash matches a `rejected` version:
upstream must change the content, decision 10); a point of another language.

### 5.4 Idempotency and the diff

Keyed on `package_hash` (batch) and `(point_id, content_hash)` (version). Re-importing an identical package returns the
existing receipt. An overlapping package inserts only new hashes. The diff lists per point `new`, `changed` (with the top-level
sections that differ), `unchanged`, `refused:<code>`; plus `unlisted` (published points the package does not mention) and
`r5_map` and `function` changes. **Unlisted points are reported, never unpublished or removed.** A `changed` version is inserted
as `imported` beside the published one; learners keep the old version until an admin publishes the new one.

### 5.5 Streaming limits and the time budget

- The **compressed** upload is capped by a running byte budget while reading, never read-then-check (`_read_upload` in
  `reading_admin_api.py` is the pattern; the cap is a module constant, [I] 32 MiB).
- **Zip limits are enforced while decompressing** with a running budget on actually produced bytes, not from `ZipInfo.file_size`
  (the sender controls that header): member count <= 2,000, each member <= 1 MiB, total uncompressed <= 64 MiB, decompression
  aborted the moment any is exceeded; reject absolute or `..` names, symlinks, duplicate names, and anything but `package.json`,
  `functions.json`, `points/*.json`; UTF-8 only; JSON parsed with a depth and size bound.
- The import is **synchronous** (validate and commit in one request, one transaction) for packages within those limits; the
  rehearsal times a 1,000-point package and the route budget is 30 s [I]. Larger sets are split by upstream (per level), not
  handled by a job queue in this proposal. Reading's 202-and-worker form is not needed at this size.
- No request runs a model or fetches a URL.

## 6. Review and publish

- **Version**: `imported` -> `accepted` or `rejected` (`POST /versions/{id}/review`, reason required for reject). Import, accept,
  rights and publish are four separately audited acts; the same admin may do all (decision 5).
- **Rights (batch-level, review P2-9)**: at commit the admin supplies one attestation for the batch, `rights_basis`
  (`orena_original | licensed | other`), `rights_attestation` text, recorded with the actor on the receipt and copied to each
  imported version as `rights_status = cleared`. Without an attestation versions start `unknown`. An admin may set a single
  version to `restricted` (event `rights_set`). Grammar Lab records catalogue codes only (`source_refs` "never source text" [V
  `grammar_set.schema.json:117-118`]); the attestation is the human statement that the examples are Orena's own or licensed.
  **Publish refuses anything not `accepted` and `cleared`** (hard gate, mirroring D-105.5a, decision 6). One attestation per
  batch scales to a level of hundreds of points; the per-version override remains for exceptions.
- **Publish** (`POST /points/{id}/publish {version_id, attested: true}`): one transaction that (a) checks the version is
  `accepted` and `cleared`, belongs to the point, its `function` label is complete, and all reference targets are (or, in a bulk
  publish, become) published; (b) clears `is_published` and sets `review_status = superseded` on the point's previous published
  version; (c) sets `is_published` on this one (the partial unique index makes a second concurrent publish fail cleanly), sets
  `lifecycle = published` and the serving columns; (d) rebuilds this point's `grammar_point_error_tags`; (e) bumps
  `grammar_catalog_state`; (f) writes the `grammar_review_events` row. Any failure rolls all of it back. The R5 map is **not
  touched** by publish.
- **Dangling references (decision 7)**: publish is refused while any `prereqs`, `contrasts` or `compare.with` target is not
  published, evaluated against the **resulting** state so a bulk publish can satisfy it. A single-point override needs an
  explicit `override_references: true`, is recorded as an event with the list, and is the only case in which the API can serve a
  reference that does not resolve (the screen already draws `compare.with` as a link, so the default must not 404).
- **Bulk**: `POST /publish` with up to N `{point_id, version_id}` pairs, **all-or-nothing** in one transaction (the R5
  replacement is hundreds of points, by level). Cross-checks run against the resulting state.
- **Unpublish / archive / restore** (`POST /points/{id}/status`): unpublish clears `is_published`, empties the point's tag rows,
  nulls nothing else and bumps the revision in the same transaction; `archived -> unpublished` is the only way back, never
  straight to `published` (the vocabulary rule [V `admin_console_api.py`, route `/content/vocabulary/{collection_id}/status`]).
  Nothing is deleted. **R5 map rows are untouched** (section 9.3).
- **Learner progress is untouched by any of these**, by design (section 8).
- Nothing in the import, the validator or a worker calls publish: "no route publishes as a side effect" (`reading_admin_api.py`
  module docstring).
- Admin read routes: `GET /points?language=&status=&level=`, `GET /points/{id}` (versions, events, a diff of the newest
  `imported` version against the published one), `GET /points/{id}/preview?version_id=` (the whitelisted GCC object, admin-only,
  so the review is of the real data), `GET /r5-map` and `GET /coverage` (R5 ids with no published primary replacement and not
  `dropped`: the input to the human's removal gate, section 13).
- The Admin screens are the UI lane's, on the pinned `Orena Admin.dc.html` (AGENTS §7, D-101 E). Where that file does not draw an
  import/diff/review view, it goes in `UI_BACKEND_GAPS.md`; this proposal adds no UI.

## 7. Learner API (`/api/grammar/v1/*`)

The reading language is the session's language (as the R5 routes are [V `ID` §3]); a point id must carry its prefix (`en.`/`zh.`).
All learner routes require the same authentication as the other `/api/` learner routes [I]. **Only `lifecycle = published` is ever
returned**; there is no learner route by version. Point bodies are the stored `content` passed through the top-level whitelist
(5.1).

| Route | Answer |
| --- | --- |
| `GET /points?level=` | `{language, catalog_revision, functions:[{id,title}], levels:[{framework,value,rank}], points:[{id, header:{native_title, native_title_pinyin?, title, sub}, level, function, sequence, point_type, error_tags, aliases, content_hash}]}` sorted by `level.rank, function, sequence` (GCC §9). `levels` come from the data, replacing the screen's hard-coded level list. **No per-learner field.** |
| `GET /points/{id}` | `{language, version, content_hash, point:<whitelisted GCC object>}`. **No `catalog_revision` in this body**, so the body is a function of the point's own hash. 404 if the id is neither published nor in the R5 map. For an id in the R5 map (bare or composite): `{point: null, redirect: "<primary point id>"}` when that point is published; `{point: null, unavailable: true, point_id}` when it exists but is unpublished or archived (the screen lands on the library, never a 404); `{point: null, dropped: true}` for a dropped id. All 200, matching the seam [V `grammar-source.js:79-90`]. |
| `GET /by-error?error_tag=&level=&limit=` | `{language, error_tag, points:[{grammar_id, title, level, reason}]}` from `grammar_point_error_tags`, ranked by level distance, then `has_mistake`, then id (`ID` §5.1). `reason` is the matching `common_mistakes` entry's `reason` for the support language [I]. Consumed by the later `/api/evaluate` swap (section 13). |
| `GET /progress` | The learner's completions for the session language, section 8. |
| `PUT /progress/{id}`, `DELETE /progress/{id}` | Section 8. |

The `aliases` field in the catalogue row is served from the published version's `aliases` for the seam's existing redirect logic;
it is informational, and **the R5 map is the resolver** (section 9). Errors use `orena_http_error` codes
(`grammar_point_not_found`, `grammar_language_mismatch`, `grammar_store_unavailable`). Until the migration is applied every route
answers `503 grammar_store_unavailable`, the Reading/Vocabulary convention, and `/next` draws its load-error frame.

`D4`'s placeholder `PUT /api/learner/grammar/{point_id}/completion` [V `D4:454-456`] is superseded by
`PUT /api/grammar/v1/progress/{id}` so that all grammar reads and writes sit under one prefix and one authorization review
(decision 9; the reviewer finds the change fine).

## 8. Progress: completion and quiz result, atomic (H-20)

Storage is the existing table, unchanged in shape (0023 already added `last_quiz_*` and the CHECK) [V `0023:53-60`]. `lesson_id`
holds the **bare point id** for new writes. No new learner-owned schema, so AGENTS §7's persistence hold is not touched (section 15).

**Dependency (review P2-7).** At this HEAD the ORM `GrammarProgress` and the SQLite `initialize()` do not yet carry
`last_quiz_correct`, `last_quiz_total`, `last_quiz_at` (`grep last_quiz writing_coach` is empty; only migration 0023 has them).
`PUT /progress` therefore **lands after D4 section 15's model and repository changes**, which add the three columns to the ORM and
to the SQLite schema and both `set_grammar_completed` implementations. It is not implementable before them.

`PUT /progress/{id}` body: `{"answers": [2, 0, null]}` (optional) or `{}`.

1. Resolve `{id}` to a **published** point in the session language, else `404 grammar_point_not_found`. An R5 id is refused with the
   redirect body of section 7 (writes never target an alias).
2. **Who grades (corrected).** The answer key is part of `content` and `GET /points/{id}` serves it, so the browser holds the key and
   grades instantly, as the screen does [V `screen.js:120`]. Serving the key is kept because the design's quiz gives per-question
   feedback without a round trip. The `answers` posted are therefore **the client's picks**. The server **re-checks**: it requires
   exactly `len(quick_practice)` entries, each a valid option index or null, recomputes `correct`/`total` from the published key, and
   **stores its own arithmetic, never a client-supplied score**. That removes arbitrary claimed scores and arithmetic error; it does
   not make the number evidence of learning: it stays activity, `claim: "activity_evidence_not_mastery"`, not mastery (EA:14). (If the
   human wants a quiz whose answers a client cannot read, that is a different content contract and a separate decision; not
   proposed.)
3. **One statement, race-safe (review P2-7).** `INSERT INTO grammar_progress (...) VALUES (...) ON CONFLICT ON CONSTRAINT
   uq_grammar_progress_scope DO UPDATE SET last_quiz_correct = COALESCE(EXCLUDED.last_quiz_correct, grammar_progress.last_quiz_correct),
   last_quiz_total = COALESCE(...), last_quiz_at = COALESCE(...)`, leaving `completed_at` as the first value. Both backends implement
   it as one upsert (SQLAlchemy `on_conflict_do_update` for PostgreSQL and SQLite), replacing today's `get`-then-`add`, which under a
   race raises `IntegrityError` and would answer 500 [V `learning_repository.py:715-724`]. Without `answers`, a completion never
   clears an earlier quiz result (the COALESCE). Completion and quiz result are columns of one row written by one statement, so
   there is no state with one but not the other (H-20); the CHECK keeps the three quiz columns together on PostgreSQL and the SQLite
   repository enforces the same invariant in code [V `0023:15-16`]. The rehearsal runs a concurrent-PUT race on PostgreSQL.
4. Response: `{point_id, completed: true, completed_at, last_quiz: {correct, total, at}|null, claim: "activity_evidence_not_mastery"}`.

`DELETE /progress/{id}` is **the learner's own un-completion, never an admin or system path**. It removes the row under the point
id and the R5 rows that make the point read as completed (section 9.4) in one transaction and reports `changed`. It therefore
deletes historical R5 rows that D-103.1 says are kept as data; that is acceptable because the learner asked, and it is stated so.
No admin route and no import, publish or unpublish deletes a `grammar_progress` row.

`GET /progress` returns `[{point_id, completed_at, last_quiz|null, via: "own"|"r5", r5_id?}]`. The two new repository operations
(`record_grammar_progress`, `list_grammar_progress`) are added to the learning repository contract and implemented for **both**
backends [V `learning_repository.py:32-36`]. The R5 route and its composite key keep working until step 9; the new UI cannot write
an R5 key.

Not persisted here, because they are not content and not decided: Try-it-yourself results (they belong to the Writing/evaluator
record, D4 I11 [V]), "saved" (`library_items`), "recent errors" (engine), and the general multi-device sync (AGENTS §7).

## 9. R5 id resolution (D-101 F)

### 9.1 The contradiction in GCC §9, and the proposed contract fix (not decided here)

GCC §9 says, for a split, "each piece keeps the original R5 id in `aliases`, with a primary piece chosen in `source_refs`", and in
the same paragraph "each R5 id appears in the `aliases` of at most one point (`aliases.duplicate`)" [V GCC §9, "Cầu nối R5"]. Both
cannot hold for a split. Revision 1 assumed one reading silently; this revision does not.

**Proposed contract fix, for the Grammar Lab lane and the human (decision 2):** an R5 id appears in the `aliases` of **exactly one**
point, its primary piece (or its replacement/merge target). Other pieces of a split do **not** carry it in `aliases`; they record
it as provenance only (`source_refs.r5_split`, catalogue code, not an alias). `aliases.duplicate` then holds unchanged. The
disposition of every R5 id, including which pieces exist, travels in the manifest's `r5_map` (9.2). The store is built to accept
**either** resolution of the contradiction: `grammar_r5_map` allows several rows per `r5_id` with one `is_primary` row, so if the
human instead keeps aliases on every piece, only the validator's alias rule changes, not the schema.

### 9.2 The package field: `r5_map`, read and never inferred

`r5_map: [{r5_id, point_id|null, disposition, is_primary}]` in the manifest, one row per (R5 id, piece):

| Disposition | Meaning | Rows |
| --- | --- | --- |
| `replaced` | one R5 id -> one point | 1, primary |
| `merged` | several R5 ids -> one point | one row per R5 id, all to the same point, each primary for its id |
| `split_primary` | an R5 id divided into pieces; this is the chosen main piece | 1 primary |
| `split_secondary` | another piece of the same R5 id | >= 1 non-primary |
| `dropped` | no replacement (editing skill, review lesson) | 1, `point_id = null` |

Validation (hard failure, the batch): every `point_id` exists in the package or the store; each R5 id has exactly one primary or one
`dropped`; an id is never both mapped and dropped; a `split_secondary` has a `split_primary` for the same id; **for every primary
row, the point's `aliases` contains the `r5_id`** (or, under the alternative contract reading, every piece's does); an R5 id in the
`aliases` of a point is present in the `r5_map`; and no R5 id appears in the `aliases` of two points (`aliases.duplicate`, unchanged).
A later batch may carry an `r5_map` for the same language: for each R5 id it lists, its rows **replace** the earlier rows for that id
(all pieces), recorded as an `r5_map_changed` event with before/after; ids it does not list are untouched. A batch cannot turn a
mapped id into `dropped` (or the reverse) unless it lists that id and the diff shows the change.

### 9.3 Independent of publish state

The R5 map is **written when its batch is committed** and read whenever an old id arrives. It is **not** a projection of the
published version and is not rebuilt by publish. Unpublish and archive never delete or change its rows; the R5 tables, routes and
JSON may be removed (step 9) and it still resolves. A row whose target point is not published resolves to `unavailable` (section 7),
a row whose target has no `accepted` or `published` version yet is treated as unresolved (404) until it does. This is what
D-101 F, D-103.1 and step 9 require: no learner's old id fails silently.

### 9.4 Parsing and reading progress

- **Ids to accept**: the bare R5 id (deep links, Writing's `grammar_links`, `/api/library/grammar/{lesson_id}`) and the stored
  composite `{lang}:grammar:v{n}:{r5id}`. The composite is parsed with the strict pattern `^(en|zh):grammar:v(\d+):(.+)$`, whole
  string, never by substring, and the `(.+)` part is the R5 id even if it contains `:` (test, review P2-11). The `{lang}` must equal
  the row's `language_code`.
- **Progress read**: a learner's row counts toward point P when `lesson_id` equals P, or is the composite (or bare) form of an R5 id
  whose **primary** row (`replaced`, `merged`, `split_primary`) points to P. **Split secondaries inherit nothing.** A **merged**
  point is complete only when **all** its mapped R5 ids are complete (reviewer's recommendation, proposed answer to decision 4);
  partial completion reads as not completed. The answer marks `via: r5` and lists the R5 ids. Nothing is rewritten: the learner row
  keeps its key (D4 I11, GCC §9 rule 2).
- **Frozen links**: an essay's stored `grammar_links` with R5 ids stays as written [V `ID` §5.2]; opening one calls
  `GET /points/{r5id}`.
- **Publish-time guard**: none needed for aliases (the map, not publish, holds them); the import validator prevents a duplicate
  alias, and `GET /coverage` lists R5 ids with neither a published primary nor a `dropped` row, which step 9 requires to be empty.
- **No R5 revival**: the R5 tables and routes are read by nothing new (D-104 H-4).

## 10. Languages

`language_code` is the app's code (`en`, `zh`, as `grammar_progress.language_code` and the routes use it [V `models.py:224`]). The
content's target key `zh-Hans` and locale key `zh-Hans` (#67) stay **inside** `content`; one mapping function (`zh-Hans -> zh`)
turns `target_lang` into the column, at import only. English and Chinese are first-class: one importer, one store, one API, no
per-language branch beyond that mapping and GCC §8's pinyin structure (a genuine linguistic difference, in the schema). Level
frameworks are data (`cefr`, `hsk3`), not columns per framework. **ja-ready**: no table, column, route or CHECK names a language;
adding `ja` needs (a) a language entry in the importer's supported-language configuration, (b) its script rules in the vendored
schema (the analogue of the pinyin check), (c) a level framework value (`jlpt`), (d) an upstream package. No migration.

## 11. Caching, `content_hash` and read ordering

**Canonical form (normative; Grammar Lab must produce the same):** `content` serialised as JSON with keys sorted by code point at
every level, separators `(",", ":")`, UTF-8, **no ASCII escaping**, **integers as integers (never floats)**, no NaN/Infinity, **no
Unicode normalisation**; `content_hash` = sha256 of those bytes. The import recomputes it and rejects a mismatch, so drift is a
loud failure. A **golden vector** (one small point with Vietnamese diacritics and pinyin, and its expected hash) is committed with
the tests and shared with the Grammar Lab lane.

- `GET /points/{id}` sends `ETag: "<content_hash>"`; `GET /points` sends `ETag: W/"<language>-<catalog_revision>"`; both honour
  `If-None-Match` with `304`. `Cache-Control: private, no-cache` (revalidate every time; a publish or unpublish takes effect on the
  next request, which the rollback in section 16 relies on).
- **Read ordering (review P2-1).** `GET /points` reads `grammar_catalog_state.revision` **first**, then the points, and labels the
  response with the revision it read first: content newer than its label is harmless (the client refetches once), content older than
  its label is impossible. Alternatively both reads run in one repeatable-read transaction. A test forces a publish between the two
  reads. `GET /points/{id}` has no revision in its body, so an unrelated publish cannot change a body under an unchanged ETag.
- The catalogue projection is built from `grammar_points` (denormalized columns, one indexed query) and may be cached in-process
  keyed by `(language, catalog_revision)`; with several workers each reads the revision per request [I]. The progress call is per
  learner, never shared-cached.

## 12. Access control

- New router `writing_coach/grammar_admin_api.py`, same construction as `reading_admin_api.py`: `admin_guard = require_admin` (the
  existing wirings in `app.py` are the pattern), `_same_origin` on every change, `Cache-Control: no-store`, an `audit_logs` row per
  privileged change (`admin.grammar_import`, `admin.grammar_review`, `admin.grammar_publish`, ...), plus the transactional
  `grammar_review_events`. There is no second admin backend (AGENTS §7).
- **Every new admin route is added to `tests/test_admin_authorization_matrix.py`**, and its route-count assertion is updated [V
  `test_admin_authorization_matrix.py:180-201`]: the test reads the app's routes, so an unlisted route fails; each is called as
  nobody, as a learner (refused) and as an administrator.
- Learner routes: authenticated, language-scoped, published-only. Admin preview is the only path to unpublished content and it is
  admin-only.
- Import bodies are untrusted data: never `eval`, never used as a path, never rendered as HTML by Admin; JSON is parsed with a depth
  and size bound.

## 13. `/next` seam switch, cutover order, and what stays

`static/orena/product/grammar-source.js` is the only seam: `grammarCatalog()` and `grammarPoint()` read static files under
`CONTENT_BASE`, which is empty [V `grammar-source.js:1-21, 44-88`]. The switch repoints those two readers to `/api/grammar/v1/points`
and `/points/{id}` and consumes `redirect`, `unavailable` and `dropped`; the screens, `model.js` and copy do not change (the seam's
own statement, `grammar-source.js:7-8`). `CONTENT_BASE` and the client-side `approved()` filter are deleted when the API is the source
(the server is now the filter). Completion and quiz result move from `api.completeGrammar` (R5 route) [V `api.js:305-306`] to
`PUT /progress/{id}`; `screens/grammar-concept` sends its picks.

Order (re-ordered from `ID` §6; every step before 9 only adds; each has its own rollback):

| # | Step | Gate |
| --- | --- | --- |
| 0 | This proposal reviewed and approved; **contract PR #67 merged and the `r5` split reading settled (9.1)** | independent review, then the human |
| 1 | Migration 0024 rehearsed, then applied to :8021 | the human's authorization |
| 2 | Repository, importer, vendored schema and validator, Admin routes, tests | after 0 and 1 |
| 3 | Grammar Lab: `export-package` in the agreed shape (manifest, `r5_map`, canonical hash); first approved batch | upstream lane, Grammar Lab review |
| 4 | Admin import/review/publish screens | UI lane, Admin frames |
| 5 | D4 model changes (`last_quiz_*` in ORM and SQLite); learner API and progress routes | after 2 |
| 6 | Seam switch on `/next` | after 3-5 |
| 7 | `/api/evaluate` links via `by-error` (`ID` §5.1) and the `AGENT_CONTRACT` bump | `codex/work` lane; core batch covers the grammar error tags |
| 8 | Cutover D-091 | per D-091 |
| 9 | R5 removal (`/api/library/grammar*`, R5 registry and JSON, `writing_grammar_transfer.py`, R5-bound tests, `LEGACY_TOMBSTONES.md` entry) | **the human**; `GET /coverage` empty; every R5 level the old course covers is published |

## 14. Tests (real repositories, no mocks of the store)

Runs in the application image with the repository mounted read-only, `PERSISTENCE_BACKEND=sqlite`, as CI does (AGENTS §9); the
PostgreSQL-specific parts run in the rehearsal.

1. **Corpus test (P1-2).** The 13 PR #68 points, converted to `status: approved` (and their provenance moved to a manifest), import
   and validate against the vendored schema; the unconverted originals are refused `not_approved`. A set of **mutated copies** is
   refused, each with its own code: span outside its sentence, missing required locale (`en`), an extra key at the top level and at
   a nested object, an internal field (`provenance`/`review`/`flags`) in a point file, wrong-length pinyin array, quick-practice
   `answer` out of range, asymmetric `contrasts`, wrong `illustration.kind` for `point_type`, unsupported `schema_version`. A test
   that the whitelist at serve time removes a forbidden key even if it were stored.
2. **Importer**: hash mismatch, duplicate ids, wrong language prefix, cyclic `prereqs`, duplicate aliases, incomplete function label
   and `validator.passed: false` each reject the batch and write a `rejected` receipt without content rows;
   `version_not_bumped`, `version_lower_than_stored`, `content_already_stored` (upstream revert) and `content_previously_rejected`
   refuse only that point; a hostile zip (traversal, symlink, a bomb whose `file_size` header lies, oversize, too many members) is
   refused while decompressing, before parsing.
3. **Idempotency**: same package twice -> one `imported` batch, `200 already_imported`; a re-upload after a `rejected` batch is a
   fresh attempt; overlapping package -> only new hashes; `unlisted` reported and nothing unpublished; dry run writes zero rows.
4. **Lifecycle**: publish requires `accepted` and `cleared`; publish swaps the version atomically (a fault injected after the tag
   rebuild leaves the old version served and the revision unchanged); a second concurrent publish of the same point fails on the
   partial unique index; unpublish removes the point from `/points`, `/points/{id}` and `/by-error` in the same request cycle;
   archived cannot publish directly; bulk publish is all-or-nothing and satisfies mutual references; a dangling reference blocks
   publish and the override leaves an event; the batch attestation clears versions and a `restricted` override blocks publish.
5. **Projections (P2-4).** After **every** lifecycle operation (import, accept, publish, bulk, unpublish, archive, restore) a helper
   rebuilds the serving columns and `grammar_point_error_tags` from `content` and compares row by row; the invariant "published <=>
   exactly one `is_published` version" is asserted; serving columns are NULL before first publish.
6. **Immutability (P2-3).** The PostgreSQL trigger rejects an UPDATE of `content`, `content_hash`, `version`, `point_id`,
   `provenance` and allows `review_status`, `is_published`, `rights_status`, `reviewed_*` (rehearsal); the SQLite repository refuses
   the same in code.
7. **Learner API**: only published content is returned; the served `point` equals the whitelisted `content`; ETag and `304`; the
   ETag ordering test; no `catalog_revision` in the point body; language mismatch; `levels` derived from data; EN and ZH parity (the
   corpus has 3 ZH points; the same tests run for both); 503 before the migration.
8. **R5 map (P1-1).** A **merge** (two R5 ids -> one point: complete only when both are), a **split** (primary inherits, secondary
   does not, both resolve to the primary via redirect), a **dropped** id (`dropped: true`), an id whose replacement is
   **unpublished** (`unavailable`, not 404) and stays resolvable after unpublish, archive **and simulated R5 removal**; the composite
   key of each, including a lesson id that itself contains `:`; strict-pattern look-alikes rejected; a later batch replacing one id's
   rows; map validation failures (primary not in `aliases`, mapped and dropped, split with no primary, duplicate alias).
9. **Progress**: completion + quiz in one statement (a rollback leaves neither); retake keeps the first `completed_at`; without
   `answers` an earlier quiz result survives (COALESCE); the server recomputes from the key and rejects a wrong-length `answers`;
   unpublished or R5 id refused; **concurrent PUTs on PostgreSQL** return 200 twice, not 500; `DELETE` removes own and R5 rows and is
   reachable only as the learner; deleting a user cascades (`ondelete=CASCADE` [V `models.py:221-223`]); archiving a point leaves
   learner rows. Skipped until the D4 model changes exist, then required.
10. **Access**: every `/api/admin/grammar/*` route in the authorization matrix (count updated); missing/foreign `Origin` refused;
    every privileged change writes an `audit_logs` row and a `grammar_review_events` row.
11. **Guards**: a test that fails if grammar **point** JSON is added under `writing_coach/` or `static/` (D-105.4; the vendored
    schema directory and `tests/fixtures/` are the only exceptions). The `.mjs` seam test for `grammar-source.js` gets an
    API-backed fixture; the R5 gates stay until step 9.
12. **Rehearsal (PostgreSQL)**: up/down/up; 1,000-point import and its wall time; 100,000 progress rows; `EXPLAIN` of the three reads;
    concurrent publish and read (no torn read, no label newer than content); the trigger; the race on `PUT /progress`.

## 15. Holds (AGENTS §7), safety and what this proposal does not decide

- **Learner-data persistence / account sync**: not resolved. No new learner-owned schema; `grammar_progress` and 0023 were approved
  by D-104/D-105. The content tables carry no learner identity (only admin actors in receipts and events, retained with
  `audit_logs`). `lesson_id` deliberately has no foreign key.
- **Deletion and export**: account deletion is ADA §5's workflow. Grammar content is not learner data and is neither exported nor
  deleted with an account. The learner's `grammar_progress` rows (with `last_quiz_*`) are learner-owned, go with the deletion
  (cascade on `users.id`) and into the export; the export **format** stays deferred (D-104 H-18). Nothing here changes either
  runtime.
- **Platform Admin**: reused, not replaced (section 12). **Native mobile**: frozen; `useGrammar.ts` is untouched. **Reading breadth**:
  unaffected.
- **Protected areas**: R5 Grammar contracts and Concept IDs stay protected until step 9 (D-100.5). This proposal does not edit them.
- **New dependency**: `jsonschema` if decision 8 is accepted; it is a reviewed change in `requirements.txt`, not an incidental one.
- **Safety**: no Docker, no compose, no volume operation, no push, no :8000/:8010 contact is part of this document. Migration
  application is the human's, one revision, after a backup.
- **Reviewer independence**: needs an independent architecture review recorded in Git (reviewer, commit, outcome) of this revision
  before any code (AGENTS §1).

## 16. Rollback

- **Learner impact**: `POST /points/{id}/status unpublished` (or a bulk unpublish) hides content immediately; the next request sees a
  new `catalog_revision`. `/next` shows the design's empty state, as today.
- **Code**: revert the seam commit (`/next` returns to the empty static seam); the R5 UI at `/` is untouched until the cutover.
- **Schema**: `downgrade()` drops the eight content tables (no learner data), then re-import from the export package; the migration
  is otherwise restored-from-backup like any revision. `grammar_progress` and 0023 are not affected; rows written under new point
  ids remain and re-attach when the points are re-imported. **The R5 map is content: dropping it loses old-id resolution until the
  packages are re-imported, so step 9 must not run before the map is verified by `GET /coverage`.**
- **Bad batch**: versions are immutable and unpublished by default, so a bad import is rejected/unused rather than reverted; a bad
  *publish* is an unpublish, and the previous version stays `superseded` (re-publishable by an explicit act).

## 17. Open human decisions (each with a proposed answer)

1. **Approve the model**: content in the database, versions immutable (trigger-enforced) and authored only upstream, one published
   version per point by index, publish an explicit act. *Proposed: approve.*
2. **Package and contract**: agree with the Grammar Lab lane (a) the manifest of 5.2 with `r5_map`, per-point provenance and a
   `validator` verdict; (b) the normative canonical-JSON rule and golden vector of section 11; (c) **the GCC §9 fix of 9.1** (an R5
   id in the `aliases` of its primary only; secondaries via `source_refs`). *Proposed: yes to all three; recorded in Git by the
   Grammar Lab lane before step 3.*
3. **Batch atomicity**: hard failure rejects the whole batch; status and version problems refuse only that point. *Proposed: as
   written (reviewer concurs).*
4. **Merged R5 points**: complete only when **all** aliased R5 lessons are complete (learner-facing rule). *Proposed: all (reviewer
   recommends; revision 1 proposed "any").*
5. **Reviewer separation**: none now (one admin team); import, accept, rights and publish are four separately audited acts.
   *Proposed: none now.*
6. **Rights gate**: D-105.5a's hard gate extends to grammar, with a batch-level attestation. *Proposed: yes.*
7. **Dangling references**: publish refused while any `prereqs`, `contrasts` or `compare.with` target is unpublished, evaluated
   against the resulting state; a single-point override needs an explicit flag and an event. *Proposed: refuse (reviewer
   recommends; revision 1 proposed "warn").*
8. **Deep validation**: add `jsonschema` and vendor the exact closed schema (a reviewed new dependency). If declined, a hand-written
   validator that covers every field the two screens read and passes the corpus test. *Proposed: add `jsonschema`.*
9. **Names and retention**: `PUT /api/grammar/v1/progress/{id}` (not D4's placeholder path); do not keep the raw uploaded package,
   keep the manifest (without point bodies) on the batch receipt. *Proposed: as written.*
10. **Re-offering rejected content**: a `rejected` version's hash cannot be re-imported (`content_previously_rejected`); upstream
    must change the content. *Proposed: refuse.* Also: **which contract version and when** (a merged #67, one constant). *Proposed:
    step 2 does not start until #67 is merged.*

Dependencies outside this proposal: PR #67 (contract patch, OPEN) must merge first; PR #68 (fixtures) is test data only; the D4
proposal's R5 join wording (Finding 1) needs the same correction when D4 is next amended; D4 section 15's model changes are a
prerequisite of section 8.

## 18. Review response (`GRAMMAR_CONTENT_STORE.REVIEW.md`, REQUEST CHANGES at revision 1)

| Finding | Resolution in revision 2 |
| --- | --- |
| **P1-1** R5 alias model (contradiction, dispositions, split, publish-independence) | GCC §9's split contradiction is stated and a contract fix proposed for the Grammar Lab lane, not decided (9.1, decision 2). Dispositions come from an explicit `r5_map` in the manifest, validated against `aliases` (5.2, 9.2). New `grammar_r5_map` (surrogate key, nullable `point_id`, `is_primary` with partial unique indexes) permits one R5 id -> several points with one primary. Rows are written at batch commit, independent of publish, and survive unpublish, archive and R5 removal (3, 9.3). `dropped` rows come from the batch carrying `r5_map`, superseded id-by-id by a later batch with an event. Tests for split, merge, dropped, unpublished replacement, composite keys (14.8). |
| **P1-2** Trust boundary | Deep validation with vendored closed schema and `jsonschema` recommended, hand validator as counted fallback (5.1, decision 8). Unknown keys rejected everywhere; internal `provenance`/`review`/`flags` forbidden in point files and stripped by a serve-time whitelist (5.1, 7). One `SUPPORTED_SCHEMA_VERSION` implemented only against a merged contract; #67 is open and gates step 2 (5.1, 13). Manifest `validator` verdict demoted to an audit record. Corpus test with converted fixtures and mutated copies (14.1). |
| P2-1 ETag ordering; revision in point body | Revision read first (or one repeatable-read transaction), tested; `catalog_revision` removed from the `/points/{id}` body (11, 7, 14.7, 14.12). |
| P2-2 Circular FK | Removed. `is_published` on versions with partial unique `(point_id) WHERE is_published`; `grammar_points` has no version FK; the lifecycle invariant is a publish-transaction rule with a test (3, 4, 6, 14.5). |
| P2-3 Immutability | PostgreSQL `BEFORE UPDATE` trigger, dialect-guarded, plus SQLite repository invariant and tests (3, 14.6). |
| P2-4 Projection drift | Serving columns nullable until first publish; rebuild-and-compare test after every lifecycle operation (3, 14.5). |
| P2-5 Reverted content / hash collision | Refusal codes `content_already_stored` and `content_previously_rejected` (5.3, decision 10, 14.2). |
| P2-6 Import details | (a) limits enforced while decompressing and on the compressed upload (5.5); (b) synchronous, bounded, timed in rehearsal (5.5, 4); (c) rejected batch writes a `rejected` receipt, `already_imported` only for `imported`, partial unique on hash (3, 5.3); (d) reference target state defined: package or stored point with an `accepted`/`published` version (5.3); (e) later batch wins on function labels, shown in the diff, event `function_label_changed` (3). |
| P2-7 D4 dependency; `ON CONFLICT` | `PUT /progress` lands after D4 section 15's ORM/SQLite changes; single `INSERT ... ON CONFLICT DO UPDATE` with `COALESCE` and first `completed_at`; PostgreSQL race test (8, 13 step 5, 14.9, 14.12). |
| P2-8 "server grades" | Corrected: the key is served, the client grades, the server re-checks and stores its own arithmetic; still activity, not evidence (8). |
| P2-9 Rights mechanics | Batch-level attestation (`rights_basis`, text, actor) copied to versions, per-version `restricted` override, publish refuses anything not `cleared` (3, 6). |
| P2-10 `DELETE` | Stated as a learner action only, reports `changed`, never from an admin path; it removes R5 rows the learner asked to un-complete (8). |
| P2-11 Drift | Reading Admin references are by function name (working tree carries unrelated edits); composite-key parse test with a `:`-containing id (9.4, 14.8). |
| Reviewer Recommendations on section 17 | Folded in as proposed answers, still human decisions: 4 "all", 7 "refuse", 8 `jsonschema`, 9 store the manifest, 2 canonical JSON with a golden vector and the alias dispositions (17). |
| Requested correction of D4's R5 join | Done in this proposal (Finding 1, 9.4: composite key, strict pattern); `LEARNER_RECORDS_D4.md` needs the same correction and is not edited here. |
