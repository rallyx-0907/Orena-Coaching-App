# Proposal (D-105 point 4): the grammar content store, Admin import and `/api/grammar/v1/*`

**Outcome (2026-10-08):** independent review APPROVE at `b3ee8f09` (PR #100, merged); migration `0030` promoted to
`migrations/versions/` on the human's authorization (source control only); the non-UI implementation and its evidence
are recorded in `GRAMMAR_CONTENT_STORE.IMPLEMENTATION.md`.

Status: **PROPOSED, revision 3** (2026-10-08), refreshed against `main` after PR #98 (`a2342e62`, schema head
`20261007_0029`) on `codex/work` (`379f83d6`, which is `main` plus three memory-only commits), for issue #99. Revision 2
(2026-09-30, `72cd4cd`) was **APPROVED** by the independent review `GRAMMAR_CONTENT_STORE.REVIEW.md` (architecture only,
with P2 items N-1..N-6 to carry), and the human answered its ten decisions in **D-106**. Revision 3 changes no approved
decision. It (a) corrects what `main` and the Grammar Lab export contract have since made stale (section 0a), (b) adds the
migration as a **proposal** (`migrations/proposed/20261008_0030_grammar_content_store.py`), (c) adds its PostgreSQL
rehearsal and a contract-boundary check with their evidence (sections 19-20, `GRAMMAR_CONTENT_STORE.REHEARSAL.md`), and
(d) folds N-1..N-6 into the text (section 18). **Revision 3a** (same day) answers the Codex review of PR #100 (two P1s,
section 18a): supersession is serving state, not a review verdict, so a rollback can republish the previous version; the
contract checker fails when a validator dependency is missing; and the rehearsal's synthetic bodies are validated against
export profile 1 before import.

Process (AGENTS section 1 "Architecture review authority", D-054, D-102, D-143/D-144): this revision and the migration
file -> **independent architecture review of revision 3** -> the human's authorization -> `git mv` of the migration into
`migrations/versions/` -> Store/API code and tests -> the human applies it to the runtime they name. **The author of this
file may not self-approve it, and no Store/API code is written before that review approves** (issue #99).

Legend: **[V]** read in code or docs at `379f83d6` (equal to `main` `a2342e62` for every file cited), or at
`origin/feature/grammar-lab-pipeline` `3579ece8` ("GL"); **[R]** shown by the rehearsal or the contract check that ran
for this revision (section 20); **[I]** inferred, to verify at implementation. `GCC` = `docs/project/GRAMMAR_CONTENT_CONTRACT.md`
(v0.4 with the PR #67 patch, merged 2026-10-04); `EP` = Grammar Lab's export profile 1 (`grammar_lab/schema/export_profile.schema.json`,
`pipeline/export_profile.py`, `pipeline/export_package.py`, `pipeline/r5_map.py` at GL); `ID` = GL
`docs/grammar_lab/INTEGRATION_DESIGN.md` (the export package v1 rewrite of 30/09); `D4` = `proposals/LEARNER_RECORDS_D4.md`.

## 0. The decisions this proposal implements

- **D-105.4** [V]: Grammar Lab is upstream; an approved export is imported into the **database** through Admin, reviewed and
  published there; learners read a published grammar API; content does **not** ship as JSON with the source. D-105.3 (H-20):
  completion and quiz result in one atomic write.
- **D-106** [V], the answers to revision 2's section 17: (1) the model is approved (content in the DB, immutable versions,
  authored only upstream, publish an explicit act); (2) an explicit `r5_map`, the canonical JSON/hash rule, and an R5 alias on
  the primary point only, split secondaries via `source_refs`; (3) batch atomicity as proposed; (4) a merged R5 point is
  complete only when **all** its aliased R5 lessons are; (5) no reviewer separation, four audited acts; (6) the hard rights gate;
  (7) publish refused while a published reference would dangle; (8) `jsonschema` with a **derived single-version
  export-profile schema**, not the multi-version upstream schema, plus drift and golden-vector tests; (9) `PUT
  /api/grammar/v1/progress/{id}` and manifest-only retention; (10) a rejected content hash cannot be re-imported. "For
  unavailable or dropped Grammar responses the learner UI uses the existing not-found shape; no new learner landing is invented."
- **D-111.4** [V]: the Store/API architecture is approved to build; no parallel Grammar system; the old 269 EN / 239 ZH R5
  lessons stay retired from the learner UI. **D-126** [V]: the agent contract's `grammar_id` is a Grammar Lab point id and
  `grammar.point` stays out of `supported_intents` until the Store/API serves points. **D-143/D-144** [V]: one UI at `/`
  (`/next` redirects), one schema chain, one release path; no new persistent runtime; rehearsals are disposable.

## 0a. Stale assumptions in revision 2, corrected here

| # | Revision 2 said | True on `main` `a2342e62` / GL `3579ece8` | Where |
| --- | --- | --- | --- |
| S-1 | Migration `2026MMDD_0024_grammar_content_store`, `down_revision = "20260930_0023"` | The real head is **`20261007_0029`** (0025 -> 0029) [V `migrations/versions/`]. Slot 0024 is taken by the open proposal `20261001_0024_media_entries.py`, 0026-0028 by `ai_cost_records`, `billing_orders`, `reading_derived_texts` (all in `proposed/`). **`20261008_0030`** is free in both folders [R]. Note: `proposed/20261005_0026_ai_cost_records.py` is also parented on 0029; whichever is promoted second is re-parented on the first. | 4 |
| S-2 | `PUT /progress` "lands after D4 section 15's model changes"; the ORM and SQLite lack `last_quiz_*` | **Resolved on `main`.** `GrammarProgress` carries `last_quiz_correct/total/at` and the CHECK `ck_grammar_progress_quiz` [V `models.py:267-293`]; both repositories implement `record_grammar_completion` as **one** `INSERT ... ON CONFLICT` and `get_grammar_progress(point_id, aliases)`, with `clean_quiz_result` holding the CHECK's invariant for SQLite [V `learning_repository.py:36-60, 389-430, 817-875`; `tests/test_d4_grammar_quiz.py`]. No route calls them yet. The dependency is gone; two gaps remain for the Store (section 8). | 8, 13 |
| S-3 | Vendor "the contract's closed schema" (`grammar_set.schema.json`); one `SUPPORTED_SCHEMA_VERSION` | Upstream now derives and commits a **single-version, closed export profile** `grammar-export-profile/1` from the internal schema, with a drift check (D-106.8, review N-1 resolved upstream) [V GL `export_profile.py`]. The app vendors **that** file and pins two constants: `export_profile = "grammar-export-profile/1"`, `schema_version = "0.4"`, plus the profile's hash `0671ac91...6541f` [R]. | 5.1 |
| S-4 | Function labels `{vi, en, zh-Hans}` all required; `zh-Hans -> zh` mapped by the importer | At the boundary the app sees **`zh` only**: `target_lang` is `en|zh`, locale keys `vi|en|zh` (EP maps upstream with `to_app_point`). The importer **maps nothing** and refuses `zh-Hans`. Inside Grammar Lab, GCC keeps `zh-Hans`. Function labels: GCC requires `vi`, `en`, `zh-Hans`; EP's exporter requires only `vi`, `en`, so **the importer is the stricter side** and requires `vi`, `en`, `zh` (all 43 labels at GL have all three [R]). | 5.3, 10 |
| S-5 | Manifest `{schema_version, set_version, language, source_commit, exported_at, points, r5_map, validator}`; `package_hash` echoed by the upload | The manifest is a **closed set of 15 keys** [V GL `export_package.py` `MANIFEST_KEYS`; R], adding `export_profile`, `profile_schema_hash`, `source_dirty`, `package_hash`, `external_references`, `functions` (equal to `functions.json`) and a `rights` **policy** block; each point entry adds `level` and the provenance keys `review_seconds`, `generated_at`, `source_refs`, `source_anchors`, `r5_source?`. **`package_hash` is semantic**: SHA-256 of the canonical JSON of `{export_profile, schema_version, language, functions, points:[{id, version, content_hash}], r5_map}`; audit metadata is outside it, so a re-export of the same content from another commit has the same hash and the import stays idempotent [V; R]. | 5.2, 5.4 |
| S-6 | GCC section 9 contradicts itself on splits; the store accepts either reading | **Settled by D-106.2** and implemented upstream: an R5 id is in the `aliases` of its primary point only; a split secondary records it in `source_refs.r5_split` [V GL `r5_map.py`; R]. A package must carry every piece of a split (`r5_map.incomplete`). The "either reading" flexibility is withdrawn. | 9 |
| S-7 | Fixtures: PR #68's 13 `draft_ai` points, converted, are the test corpus | GL holds **595 approved points** (215 EN + 380 ZH) at `3579ece8` [R, counted only] and a golden vector [V `fixtures/export/golden_vector.json`; R reproduced]. The corpus stays in Grammar Lab and is **not** copied into this repository; the importer's tests use synthetic packages and upstream's golden vector, and the first real import is an Admin act after the gate. | 14 |
| S-8 | `/next` seam switch; "the R5 UI at `/` is untouched until the cutover" | The cutover is done (D-143): the learner UI is the only UI, at `/`. The Grammar screens (`screens/grammar`, `screens/grammar-concept`) read only `product/grammar-source.js`, whose `CONTENT_BASE` is empty [V]. The R5 routes `/api/library/grammar*` still exist in `app.py` (2443-2549) and in `api.js:318-322`, used by no grammar screen [V]. | 13 |
| S-9 | Immutability: BEFORE UPDATE trigger on content columns only; events "append-only" by convention | The proposed migration also **rejects DELETE of a version** (nothing cascades into versions, so no cascade is blocked) and makes `grammar_review_events` append-only by trigger; the publish gate (`accepted` and `cleared`), the projection-while-published rule, the id/language agreement and "one resolution per R5 id" (review N-3) are database constraints, not only repository rules [R]. | 3 |
| S-10 | Rights attested as a field of `POST /imports` | Review N-4: the batch attestation may be given at commit **or later** (after the diff is read); versions stay `unknown` until then. Columns are nullable together (CHECK) [R]. | 3, 6 |
| S-11 | "Apply on :8021 only" | D-143/D-144: no new runtime; the human names the runtime; :8000 receives schema only through the reviewed release migration pack. Nothing here applies a migration anywhere. | 4 |

## 1. Summary

| # | Topic | Proposal | Section |
| --- | --- | --- | --- |
| 1 | Nature of the data | Shared **content**, not learner data. No learner-owned table or column; `grammar_progress` is reused unchanged. | 3, 8 |
| 2 | Tables | `grammar_import_batches`, `grammar_functions`, `grammar_points`, `grammar_point_versions`, `grammar_r5_map`, `grammar_point_error_tags`, `grammar_review_events`, `grammar_catalog_state` | 3 |
| 3 | Migration | `migrations/proposed/20261008_0030_grammar_content_store.py`, `down_revision = "20261007_0029"`; eight new tables, no existing table changed, no foreign key to an existing table, cycle-free; two PostgreSQL triggers; downgrade drops only these. Rehearsed on PostgreSQL 16 (66 PASS, 0 FAIL). | 4, 20 |
| 4 | Trust boundary | Export profile 1 only: vendored closed profile schema validated with `jsonschema` (Draft 2020-12), pinned profile id, schema version and profile hash; closed manifest; app-side cross checks; nothing self-attested is relied on. | 5 |
| 5 | Import | One package; dry run returns a diff; commit idempotent by the recomputed semantic `package_hash`; only `approved` points; imported versions are not visible. | 5 |
| 6 | R5 ids | The manifest's explicit `r5_map` (D-106.2); one primary or one drop per R5 id at the database; written at commit, independent of publish. | 9 |
| 7 | Lifecycle | Version review verdict `imported -> accepted / rejected`; serving state `is_published` + `superseded_at` (a superseded version stays `accepted`, so rollback republishes it). Point `unpublished <-> published`, `archived`. Publish atomic, audited, rights-gated, reference-gated. | 6 |
| 8 | Learner API | `GET /api/grammar/v1/points?level=`, `/points/{id}`, `/by-error`, `/progress`; `PUT/DELETE /progress/{id}`. Published only, whitelisted body. | 7 |
| 9 | Progress | `grammar_progress` and the existing one-statement `record_grammar_completion`; the server re-checks answers; R5 composite keys read through the map; merged = all. | 8 |
| 10 | Languages | `en`/`zh` at the boundary and in the store; no enum; `ja` is configuration and content, not a migration. | 10 |
| 11 | Caching | `content_hash` ETag per point; `W/"<lang>-<revision>"` for the catalogue, revision read **first**; label changes bump the revision (N-2). | 11 |
| 12 | Access | `require_admin`, same-origin, audit, authorization matrix. | 12 |
| 13 | Seam | Repoint `grammar-source.js`'s two readers; the screens do not change. | 13 |

## 2. Findings that shape the design

1. **The R5 progress key is a composite.** `_grammar_storage_key` writes `"{language}:grammar:v{content_version}:{lesson_id}"`
   [V `app.py:2416-2419`; `tests/test_grammar_storage_namespace.py:17`]. A join on the bare R5 id matches no stored row; the
   Store resolves through the map with the strict parse of section 9.4. (Unchanged since revision 2, still true.)
2. **`grammar_progress.lesson_id` has no foreign key and must not get one** [V `models.py:267-293`]; a point archived later must
   not cascade into a learner's history. The rehearsal shows a learner row under a point id surviving the point's archive [R].
3. **The boundary is machine-checked upstream now.** EP is a closed, single-version schema (only two documented open maps,
   section 5.1), with a drift check against Grammar Lab's internal schema and a golden vector for the hash [V GL; R]. The app
   still validates everything itself; upstream checks are not trusted (5.1).
4. **The quiz key is content.** `quick_practice[].answer` is inside the point and the screen grades in the browser [V
   `screens/grammar-concept`], so the browser holds the key; section 8 is written for that fact.
5. **Vocabulary publication is not hard-gated, Reading is** (D-105.5a); grammar follows Reading (D-106.6), now as a CHECK.

## 3. Tables (as in the proposed migration)

All new, all shared content, none keyed to a learner, **none with a foreign key to a table that exists today**. Types follow the
existing catalogs: `sa.JSON` for documents (`json` on PostgreSQL, so SQLite, the hermetic test backend, works), timezone-aware
`DateTime`, string ids for natural keys, `Uuid` for rows. Creation order is the foreign-key order, so there is **no cycle**
(review P2-2): `grammar_import_batches` <- `grammar_functions` <- `grammar_points` <- versions, map, tags, events;
`grammar_catalog_state` stands alone. `grammar_points` never points at a version.

**`grammar_import_batches`** (the receipt). `id`; `status` (`imported | rejected`); `language_code`, `package_hash`,
`export_profile`, `profile_schema_hash`, `schema_version`, `set_version`, `source_commit`, `exported_at` (**nullable only for a
`rejected` receipt whose manifest could not be read**; a CHECK requires all of them, and `manifest`, when `status = 'imported'`);
`filename`; counts `new, changed, unchanged, refused, unlisted` (CHECK >= 0); `diff`, `refusals`, `manifest` JSON (the manifest
**without point bodies**: validator verdict, `r5_map`, per-point provenance, `external_references`, `rights` policy,
`source_dirty`); the batch attestation `rights_basis` (`orena_original | licensed | other`), `rights_attestation`,
`rights_attested_by`, `rights_attested_at`, **all NULL or all set, and set only on an `imported` batch** (CHECK; review N-4);
`imported_by`; `created_at`. Partial UNIQUE `(package_hash) WHERE status = 'imported'`; index `(created_at, id)` for the
newest-first cursor. A rejected batch writes a receipt and no content; a dry run writes nothing.

**`grammar_functions`**. `id` (`fn.<snake>`, PK); `title` JSON `{vi, en, zh}` (all three required by the importer, S-4);
`batch_id` FK; `updated_at`. The later committed batch wins; the change is shown in the diff and recorded as
`function_label_changed` with before/after, and **bumps the catalogue revision** of every language with a published point in
that function, in the commit transaction (review N-2).

**`grammar_points`** (identity and serving state). `id` VARCHAR(120) PK (`<en|zh>.<slug>`, immutable); `language_code`;
`lifecycle` (`unpublished | published | archived`, default `unpublished`); `published_at`, `unpublished_at`, `created_at`,
`updated_at`. Serving projection, **NULL until the first publish** and rewritten by each publish: `function_id` (FK ->
`grammar_functions`), `level_framework`, `level_value`, `level_rank`, `sequence`, `point_type`, `native_title`,
`native_title_pinyin`. CHECKs: the id's prefix equals `language_code || '.'`; **while `published`, the projection and
`published_at` are not NULL**. Index `(language_code, lifecycle, level_rank, function_id, sequence)`. The invariant "published
<=> exactly one published version" is a publish-transaction rule with a test (section 14); half of it is the partial unique
index below.

**`grammar_point_versions`** (immutable content). `id`; `point_id` FK; `version` (CHECK >= 1); `content` JSON (the point body as
exported, validated, section 5); `content_hash` (64 hex, CHECK length); `source_status` (CHECK `= 'approved'`); `review_status`
(`imported | accepted | rejected`: the review verdict only); `is_published` (default false); `superseded_at` (set when a later
publish replaced this version, cleared when it is published again; serving state, not a verdict); `rights_status` (`unknown | cleared |
restricted`); `provenance` JSON (the manifest's per-point entry: reviewer, timings, run, model, prompt, `source_refs`,
`source_anchors`, `r5_source`; never served); `batch_id` FK; `imported_at`; `reviewed_by`, `reviewed_at`, `review_note`. UNIQUE
`(point_id, version)`, UNIQUE `(point_id, content_hash)`, **partial UNIQUE `(point_id) WHERE is_published`** (one published
version per point), and **CHECK `is_published = false OR (review_status = 'accepted' AND rights_status = 'cleared')`**: the
publish gate of D-105.5a/D-106.6 is a database fact; CHECK `is_published = false OR superseded_at IS NULL`. Because supersession
does not change the verdict, the version a newer publish replaced is still `accepted` and passes the gate again: **rollback is a
publish of the previous version** (Codex review P1, section 18a; revision 2's `superseded` review status made that impossible).
Consequence, stated for the reviewer: restricting the rights of the
**published** version is refused until it is unpublished (the admin route does both in one transaction). Indexes
`(review_status, imported_at)` (the review queue) and `(batch_id)`.
**Immutability (review P2-3; S-9).** A PostgreSQL `BEFORE UPDATE OR DELETE` row trigger refuses any change to `id`, `point_id`,
`version`, `content`, `content_hash`, `source_status`, `provenance`, `batch_id`, `imported_at`, and any DELETE; `json` columns are
compared as `CAST(... AS text)` (byte identity, the 20260924_0015 precedent: `json` has no equality operator). Only
`review_status`, `is_published`, `superseded_at`, `rights_status` and `reviewed_*` move. SQLite holds the same rule as a repository invariant
with a test. A fix is a new version from upstream (D-100.1, D-106.1).

**`grammar_r5_map`** (section 9; independent of publish state). `id`; `language_code`; `r5_id` VARCHAR(255) (the bare R5 lesson
id); `point_id` FK **nullable**; `disposition` (`replaced | merged | split_primary | split_secondary | dropped`); `is_primary`;
`batch_id` FK; `created_at`. CHECKs: `point_id IS NULL` exactly when `dropped`; `is_primary` exactly for `replaced`, `merged`,
`split_primary`. UNIQUE `(language_code, r5_id, point_id)`; **partial UNIQUE `(language_code, r5_id) WHERE is_primary OR point_id
IS NULL`**: one resolution per R5 id, a primary row **or** a dropped row, never two and never both, across batches (review N-3,
at the database; revision 2 had two indexes that allowed "mapped and dropped"). Index `(point_id)` (the R5 ids of a merged point).
Rows are written when the batch carrying them commits; for every R5 id a batch lists, its rows **replace** all earlier rows for
that id in the same transaction (event `r5_map_changed`). Never deleted by unpublish, archive or the later R5 removal.

**`grammar_point_error_tags`** (projection of the published version). `point_id` FK, `error_tag`, `has_mistake`; PK
`(point_id, error_tag)`; index `(error_tag)`. Rebuilt by publish, emptied by unpublish and archive.

**`grammar_review_events`** (append-only by trigger on PostgreSQL). `id`, `point_id` nullable, `version_id` nullable, `batch_id`
nullable (label and R5 map events have no point), `actor`, `action` (`imported | accepted | rejected | rights_set |
rights_attested | published | unpublished | archived | restored | function_label_changed | r5_map_changed`), `reason`, `changes`
JSON, `created_at`. Written in the same transaction as the change; `audit_logs` after it, best effort, as Reading does.

**`grammar_catalog_state`**. `language_code` PK; `revision` BIGINT (CHECK >= 0); `updated_at`. **No seed row**: a language
without a row reads as revision 0, so the migration names no language. Incremented by publish, unpublish, archive, bulk
publish, and a function-label change that affects published points (N-2); not by an import or an R5 map change.

Deliberately absent: a quiz-key table, any learner-facing table, a stored copy of the uploaded file.

## 4. Migration

`migrations/proposed/20261008_0030_grammar_content_store.py` [R], `revision = "20261008_0030"`, `down_revision =
"20261007_0029"`. Alembic does not read `migrations/proposed/` (`migrations/proposed/README.md`), so the file is not a head and
no runtime's startup check sees it; the chain head of `migrations/versions/` stays `20261007_0029` [R].

- **Additive and lock-free for existing tables.** It creates eight tables, their indexes and constraints, and on PostgreSQL two
  trigger functions and triggers. It alters no table and no foreign key points at an existing table, so it takes no lock on
  `grammar_progress`, `users` or any other table: the rehearsal applied it while **every one of the 56 existing tables** was held
  `ACCESS EXCLUSIVE` by another session, with `lock_timeout = 5s`, and it completed in under 0.1 s [R]. It therefore needs no
  `SET LOCAL lock_timeout` of its own.
- **Downgrade** drops the two triggers, their functions and the eight tables, in reverse order. They hold shared content only,
  re-importable from the packages; no learner row is touched. The rehearsal shows the downgraded schema **identical** to the
  0029 schema (columns, constraints, indexes, triggers, functions) and a re-upgrade identical to the first [R].
- **Sibling proposal.** `proposed/20261005_0026_ai_cost_records.py` also names `20261007_0029` as its parent. Both may stay
  proposals together; whichever is promoted second is re-parented on the first in its own reviewed commit.
- **Promotion and apply (human gates).** After the independent review approves this revision and the human authorizes it: `git
  mv` into `migrations/versions/` (one commit), and the operator applies it with `scripts/bootstrap_runtime_schema.py --upgrade
  --from 20261007_0029 --to 20261008_0030 --confirm`, after a backup, on the runtime the human names (D-127: :8021 is dev/QA).
  :8000 receives it only through the reviewed release migration pack and restored-copy rehearsal of D-143.3/D-144. Startup
  never applies it (D-002). Nothing in this revision applies a migration anywhere.
- **Nothing else migrates**: no data move, no R5 rewrite, no startup import.

## 5. Trust boundary and Admin import

### 5.1 What is trusted: nothing in the upload

Everything in the upload is untrusted, including the manifest's `validator` verdict, its `package_hash` and its
`profile_schema_hash`; they are recomputed or compared, recorded for audit, and never relied on.

- **One accepted boundary**, held in two constants and one vendored file: `SUPPORTED_EXPORT_PROFILE = "grammar-export-profile/1"`,
  `SUPPORTED_SCHEMA_VERSION = "0.4"`, and `writing_coach/grammar_schema/export_profile.schema.json` copied byte for byte from GL with
  its commit and its hash recorded beside it (at `3579ece8`: `0671ac912967a230d6073a454f82d6e66e20af67a6adfe3bde95c03c9f06541f`,
  the canonical-JSON SHA-256 of the file [R]). A package whose `export_profile`, `schema_version` or `profile_schema_hash`
  differs is rejected. A new profile is a new vendored file, a new constant and a reviewed change, never a widening. The
  vendored file is a schema, not content (D-105.4); the guard test allows only that directory.
- **Deep closed validation** (D-106.8): every point body is validated against the vendored profile with `jsonschema`
  (`Draft202012Validator`; the profile is a valid 2020-12 schema [R]). The profile is closed at every object
  (`additionalProperties: false`) except two documented maps, both checked [R]: `locale_map` (keys restricted to `vi|en|zh`,
  `vi` and `en` required, non-empty strings) and `source_refs` (snake_case catalogue codes -> arrays of non-empty strings). `jsonschema`
  becomes a reviewed dependency in `requirements.txt` in the implementation step, not in this revision.
- **No internal field in a body.** `provenance`, `review`, `flags`, `source_anchors`, `schema_version`, `title`, `summary`, `blocks`
  are absent from the profile, so a body carrying one fails closed validation [R]. Per-point audit data travels only in the
  manifest and is stored in `provenance`, never served.
- **Serve-time whitelist** (belt and braces): the API serves `content` through the profile's top-level keys **minus
  `source_refs`** (catalogue codes and `r5_split` are provenance; no screen reads them [V `static/orena/screens/grammar*`]). This is
  a change from revision 2 ("the contract's top-level keys") for the reviewer to confirm (decision R3-2).

### 5.2 The package (EP, as built upstream)

```
package.json      closed manifest, exactly these 15 keys:
                  export_profile, profile_schema_hash, schema_version, language (en|zh), set_version, source_commit,
                  source_dirty, exported_at, package_hash, external_references, functions,
                  points:[{id, version, content_hash, level,
                           provenance:{reviewer, reviewed_at, review_seconds, run_id, model, prompt_version,
                                       generated_at, source_refs, source_anchors, r5_source?}}],
                  r5_map:[{r5_id, point_id|null, disposition, is_primary}],
                  validator:{tool, version, passed, codes},
                  rights:{source_text_policy, external_text_included, attestation_required_at_import, note}
functions.json    [{id, title:{vi, en, zh}}]   equal to manifest.functions
points/<id>.json  one export-profile-1 body each, "status": "approved"
```

Upload as `.zip` (upstream's `package_to_zip` is deterministic) or a package directory's three parts. The `rights` block is the
upstream **policy** ("catalogue codes only, no external text"), never an attestation; the attestation is the admin's (section 6).

### 5.3 Endpoints (`/api/admin/grammar/*`) and validation

| Route | Effect |
| --- | --- |
| `POST /imports/validate` (multipart) | Dry run: the report and diff of 5.4. Writes nothing. |
| `POST /imports` (multipart, `package_hash` echo, optional `rights_basis` + `rights_attestation`) | Commits. `201` with the receipt; `200 {already_imported: true, batch}` only for an `imported` batch with the hash. Refuses if the echoed hash differs from the recomputed one. A hard failure writes a `rejected` receipt (`422`). |
| `POST /imports/{id}/rights` | The batch attestation, after the diff is read (N-4); copies `cleared` to the batch's versions still `unknown`. |
| `GET /imports`, `GET /imports/{id}` | Receipts, newest first, cursor-paged. |

**Hard failures reject the whole batch** (D-106.3): the manifest's key set is not exactly the 15 keys, or a per-point provenance
key is unknown; `export_profile`, `schema_version` or `profile_schema_hash` differs from the pinned values; `language` not `en|zh`;
`source_dirty` is true (decision R3-1); `functions.json` differs from `manifest.functions`; a listed point file missing or an
unlisted one present; a body's `id` differs from its filename, its `version` from the manifest's, or its recomputed `content_hash`
from the manifest's; the recomputed `package_hash` differs from the manifest's; **closed validation of any body fails**; any locale
map lacks `vi` or `en` or has `en` equal to a `vi` that carries Vietnamese letters (`locale.en_placeholder`); the id does not start
with the package language or `target_lang` differs from it; duplicate ids; `contrasts` asymmetric inside the package;
`compare[].with` not in the point's `contrasts`; a `prereqs` cycle; a function label without `vi`, `en` **and** `zh`, or a used
function without a label; any `r5_map` rule of section 9.2; and **references**: every `prereqs`, `contrasts` and `compare.with`
target is in the package or listed in `external_references`, and every external reference resolves to a stored point with an
`accepted` or `published` version. These are the checks GL runs in `validate_package` [V]; the app re-implements them and does not
import Grammar Lab code.

**Per-point refusals** (skip and report, the batch continues): `version_lower_than_stored`; `version_not_bumped` (same version,
other hash); `content_already_stored` (a higher version whose hash the point already has); `content_previously_rejected` (D-106.10);
a point of another language.

### 5.4 Idempotency and the diff

Keyed on the **recomputed semantic `package_hash`** (S-5) for the batch and `(point_id, content_hash)` for a version. Because audit
metadata is outside the hash, re-exporting identical content from a later Grammar Lab commit returns the existing receipt instead
of a second batch; that is intended (the content is the same). An overlapping package inserts only new hashes. The diff lists per
point `new`, `changed` (top-level sections that differ), `unchanged`, `refused:<code>`, plus `unlisted` (published points the package
does not mention: reported, never unpublished), `r5_map` changes and function-label changes.

### 5.5 Limits and time budget

Unchanged from revision 2: the compressed upload is capped while reading (32 MiB [I]); zip limits enforced on produced bytes while
decompressing (<= 2,000 members, <= 1 MiB each, <= 64 MiB total), no absolute or `..` names, no symlinks or duplicates, only
`package.json`, `functions.json`, `points/*.json`; UTF-8; JSON parsed with depth and size bounds; synchronous within a 30 s budget
[I]. The rehearsal's SQL part of a 1,000-point import (about 19 KB per profile-valid body) took 1.9 s on PostgreSQL 16 [R]; parsing and validation
cost is measured when the importer exists. No request runs a model or fetches a URL.

## 6. Review and publish

- **Version**: `imported -> accepted | rejected` (`POST /versions/{id}/review`, reason required to reject). That verdict is final for
  the version's content; publishing and superseding never change it.
- **Rights (D-106.6, N-4)**: the batch attestation (`rights_basis`, text, actor, time) is given at commit or later through
  `POST /imports/{id}/rights`; until then the batch's versions stay `unknown`. An admin may set one version `restricted` (`rights_set`);
  for the published version that route first unpublishes it in the same transaction (the CHECK of section 3 requires it).
- **Publish** (`POST /points/{id}/publish {version_id, attested: true}`), one transaction: lock the point row (`FOR UPDATE`, which
  serializes concurrent publishes of one point [R]); check the version is the point's, `accepted` and `cleared`, its function label is
  complete, and its references resolve in the resulting state; supersede the previous published version (`is_published = false`,
  `superseded_at = now`, verdict unchanged); set `is_published` (and clear `superseded_at`), the
  lifecycle and the projection; rebuild the point's tags; bump `grammar_catalog_state`; write the event. Any failure rolls all of it
  back: the rehearsal shows a gate failure after superseding, an injected fault after the tag rebuild and revision bump, and a
  concurrent second publish each leave versions, projection, tags, events and revision as they were, or exactly one published
  version with one bump per committed publish [R]; a `rejected` version is refused by the CHECK [R]. The R5 map is not touched by
  publish.
- **Rollback of a bad publish**: publish the previous version again (it is still `accepted`; its rights are re-checked by the same
  gate). The rehearsal republishes a superseded version: it is served again, the newer one becomes superseded, both stay `accepted`,
  one revision bump [R].
- **Dangling references (D-106.7)**: refused, evaluated against the resulting state; a single-point override needs
  `override_references: true` and leaves an event.
- **Bulk publish**: up to N pairs, all-or-nothing in one transaction; the rehearsal published 1,000 points in 0.9 s [R].
- **Unpublish / archive / restore** (`POST /points/{id}/status`): unpublish clears `is_published`, empties the tags, bumps the
  revision; `archived -> unpublished` is the only way back. Nothing is deleted; R5 rows untouched; learner progress untouched.
- Nothing in import, validation or any worker calls publish.
- Admin reads: `GET /points?language=&status=&level=`, `GET /points/{id}` (versions, events, a diff of the newest `imported` version
  against the published one), `GET /points/{id}/preview?version_id=` (admin-only, the whitelisted body), `GET /r5-map`, `GET /coverage`
  (R5 ids with neither a published primary nor a `dropped` row).
- Admin screens are the UI lane's, on the pinned `Orena Admin.dc.html`; what it does not draw goes to `UI_BACKEND_GAPS.md` (G-10
  already records the missing package import). This proposal adds no UI.

## 7. Learner API (`/api/grammar/v1/*`)

Unchanged in shape from revision 2 (approved): the session's language; a point id carries its prefix; authentication as the other
learner routes; **only `lifecycle = published`**; bodies through the whitelist of 5.1.

| Route | Answer |
| --- | --- |
| `GET /points?level=` | `{language, catalog_revision, functions:[{id,title}], levels:[{framework,value,rank}], points:[{id, header:{native_title, native_title_pinyin?, title, sub}, level, function, sequence, point_type, error_tags, aliases, content_hash}]}`, sorted by `level.rank, function, sequence`. No per-learner field. |
| `GET /points/{id}` | `{language, version, content_hash, point}`. No `catalog_revision` in the body. An id in the R5 map (bare or composite): `{point: null, redirect}` when its primary is published; `{point: null, unavailable: true, point_id}` when the target exists unpublished or archived; `{point: null, dropped: true}`; otherwise 404. |
| `GET /by-error?error_tag=&level=&limit=` | `{language, error_tag, points:[{grammar_id, title, level, reason}]}` from `grammar_point_error_tags`. |
| `GET /progress`, `PUT /progress/{id}`, `DELETE /progress/{id}` | Section 8. |

**Seam mapping (N-6, D-106).** The seam maps `unavailable` and `dropped` to the existing not-found shape `{point: null}`; no new
learner landing is drawn. Errors: `grammar_point_not_found`, `grammar_language_mismatch`, `grammar_store_unavailable`; every route
answers `503 grammar_store_unavailable` until the migration is applied.

## 8. Progress: completion and quiz result, atomic (H-20)

Storage is `grammar_progress`, unchanged. New writes use the **bare point id** as `lesson_id`. No new learner-owned schema (AGENTS
section 7 hold untouched).

**What already exists on `main` (S-2).** `record_grammar_completion(point_id, completed_at, quiz)` writes completion and quiz
result in **one** statement on both backends: PostgreSQL `INSERT ... ON CONFLICT ON CONSTRAINT uq_grammar_progress_scope` (DO
NOTHING without a quiz, so an earlier result survives; DO UPDATE of the three quiz columns with one, keeping the first
`completed_at`), SQLite `ON CONFLICT(lesson_id)` on the per-user database whose `grammar_progress` is keyed by `lesson_id` alone
(review N-5 answered: each backend uses its own conflict target). `clean_quiz_result` holds the CHECK's invariant for SQLite. Tests:
`tests/test_d4_grammar_quiz.py` [V]. No route calls it yet.

`PUT /progress/{id}` body `{"answers": [2, 0, null]}` or `{}`:

1. Resolve `{id}` to a **published** point in the session language, else `404`; an R5 id is refused with the redirect body (writes
   never target an alias).
2. The key is served, the browser grades; the server **re-checks**: exactly `len(quick_practice)` entries, each a valid option index
   or null; it recomputes `correct/total` from the published key and passes **its own** result to `record_grammar_completion`. The
   number stays activity, `claim: "activity_evidence_not_mastery"` (EA section 1).
3. Response `{point_id, completed: true, completed_at, last_quiz|null, claim}`.

**Two gaps the Store must close** (found in the existing read, not in the schema): (a) `get_grammar_progress(point_id, aliases)`
compares aliases as bare names [V `learning_repository.py:416-430, 853-875`], but stored R5 rows hold the composite key (Finding 1),
so the Store passes the composite candidates the map resolves (section 9.4), never bare aliases; (b) it returns the **first** match,
while D-106.4 says a merged point is complete only when **all** its R5 ids are; the merged rule is applied in the Store's progress
read (`GET /progress` and the catalogue's completion flags), with tests.

`DELETE /progress/{id}`: the learner's own un-completion only (removes the point-id row and the R5 rows that make it read as
completed, reports `changed`). No admin, import, publish or unpublish path deletes a `grammar_progress` row.

## 9. R5 id resolution (D-101 F, D-106.2, D-106.4)

### 9.1 The rule (settled)

An R5 id is in the `aliases` of **exactly one** point, its primary piece or its replacement/merge target. Other pieces of a split
record it in `source_refs.r5_split`, never in `aliases`. `aliases.duplicate` holds. The disposition of every R5 id travels in the
manifest's `r5_map`; the importer reads it and **never infers** it from aliases [V GL `r5_map.py`, `ID` section 4].

### 9.2 Validation of `r5_map` (hard failure)

Rows have exactly `{r5_id, point_id, is_primary, disposition}`; disposition one of the five [R: equal to the migration's]; `point_id`
null exactly for `dropped`; every `point_id` in the package; each R5 id has exactly one primary or exactly one `dropped` row, never
both; a `split_secondary` has a `split_primary` for the same id and vice versa; no point listed twice for one id; a primary's body
lists the id in `aliases`; a secondary's body does **not**, and lists it in `source_refs.r5_split`; every alias in the package has a
row; no alias on two points. A package carries every piece of a split (`r5_map.incomplete`, enforced upstream; the importer checks
the same through the rules above). A later batch's rows for an R5 id replace every earlier row for that id (event with before/after);
the database's one-resolution index makes "mapped and dropped at once" impossible whatever the code does [R].

### 9.3 Independent of publish state

Written at batch commit, read whenever an old id arrives, never rebuilt by publish, never changed by unpublish or archive, and
still resolving after the R5 tables, routes and JSON are removed (step 9). Target unpublished -> `unavailable`; target with no
`accepted`/`published` version -> unresolved (404).

### 9.4 Parsing and reading progress

- Accepted ids: the bare R5 id, and the stored composite parsed with `^(en|zh):grammar:v(\d+):(.+)$` (whole string; the `(.+)` part
  may contain `:`); `{lang}` must equal the language.
- A learner row counts toward point P when `lesson_id` is P, or is the composite (or bare) form of an R5 id whose **primary** row
  points to P. Split secondaries inherit nothing. A **merged** P is complete only when **all** its primary R5 ids are complete
  (D-106.4). The answer says `via: "r5"` and lists the ids. Nothing is rewritten.
- Frozen links (an essay's `grammar_links`) stay as written and resolve through `GET /points/{r5id}`.

## 10. Languages

`language_code` is the app's code (`en`, `zh`) in every table and at the boundary (EP: `target_lang` `en|zh`, locale keys `vi|en|zh`).
The importer **maps nothing**: a body or label with `zh-Hans` fails closed validation [R]. Grammar Lab's internal `zh-Hans` (GCC) is
upstream's business. The seam's `contractText` branch for a `zh-Hans` key [V `grammar-source.js:94-98`] becomes dead code at step 6
and is removed there. English and Chinese are first-class: one importer, one store, one API; level frameworks are data (`cefr`,
`hsk3`). **ja-ready**: no table, column, CHECK or route names a language (the catalogue state has no seed row); `ja` needs a new
export profile upstream, its vendored file, an `en|zh|ja` app-language configuration, a level framework (`jlpt`) and content. No
migration.

## 11. Caching, `content_hash` and read order

**Canonical form (normative, D-106.2; identical upstream):** keys sorted by code point at every level, separators `,` `:`, UTF-8,
no ASCII escaping, integers only (a float anywhere is an error), no NaN/Infinity, no Unicode normalisation; `content_hash` =
lowercase hex SHA-256. The importer recomputes and rejects a mismatch. The upstream golden vector
(`cf92888909aadba47cac25209a173fdf1fa9ee0f66dacd7e425b2326be19ee27`) is reproduced by this rule with the standard library [R]; the
importer's tests run it.

- `GET /points/{id}`: `ETag: "<content_hash>"`. `GET /points`: `ETag: W/"<language>-<catalog_revision>"`. Both honour
  `If-None-Match`; `Cache-Control: private, no-cache`.
- **Read order (review P2-1).** `GET /points` reads the revision **first**, then the points, and labels the response with what it read
  first; or both in one REPEATABLE READ transaction. The rehearsal shows, on PostgreSQL: a publish between the two reads yields newer
  content under the older label (harmless: the next request sees a new revision and refetches); the reversed order labels **older**
  content with the **newer** revision (the 304-forever hazard); REPEATABLE READ is consistent; and under a concurrent stress (1
  publisher, 4 revision-first readers, 8 s) revision-first reads showed **0** violations while reversed-order readers showed some [R].
- A function-label change bumps the revision of the affected languages (N-2), because `GET /points` returns labels.

## 12. Access control

Unchanged from revision 2: a new router `writing_coach/grammar_admin_api.py` built like `reading_admin_api.py` (`require_admin`,
`_same_origin` on every change, `Cache-Control: no-store`, an `audit_logs` row per privileged change, plus the transactional events);
every route in `tests/test_admin_authorization_matrix.py` with its count updated; learner routes authenticated, language-scoped,
published-only; preview admin-only; upload bodies never evaluated, used as a path or rendered as HTML.

## 13. The seam switch, cutover order, and what stays

`static/orena/product/grammar-source.js` is the only data seam of the two Grammar screens; `grammarCatalog()` and `grammarPoint()`
read static files under an empty `CONTENT_BASE` [V]. The switch repoints those two readers to `/api/grammar/v1/points` and
`/points/{id}` (mapping `unavailable`/`dropped` to `{point: null}`), deletes `CONTENT_BASE` and the client-side `approved()` filter,
and sends completion with the picks to `PUT /progress/{id}`. The screens, models and copy do not change. The R5 client calls in
`api.js:318-322` and the R5 routes are removed in step 9, not before.

| # | Step | Gate | State |
| --- | --- | --- | --- |
| 0 | Revision 2 reviewed (APPROVE), decisions answered (D-106), contract merged (#67), split reading settled (D-106.2) | | done |
| 0' | **This revision 3 and `proposed/20261008_0030` independently reviewed**; the human authorizes promotion | independent review, the human | **pending (this PR)** |
| 1 | `git mv` 0030 into `versions/`; applied to the runtime the human names, after a backup | the human | after 0' |
| 2 | ORM models, repository, importer (vendored profile, `jsonschema`, cross checks), Admin routes, tests | after 1 | |
| 3 | Grammar Lab `export-package` (exists at GL `3579ece8`); first approved packages per level | upstream lane | tooling done |
| 4 | Admin import/review/publish screens | UI lane, Admin frames | |
| 5 | Learner API and progress routes (repository functions exist, S-2; gaps of section 8) | after 2 | |
| 6 | Seam switch at `/` | after 3-5 | |
| 7 | `/api/evaluate` links via `by-error`; `grammar.point` intent and the agent contract bump (D-126) | `codex/work` lane | |
| 8 | (former "Cutover D-091": done by D-143) | | done |
| 9 | R5 removal (`/api/library/grammar*`, R5 registry and JSON, `writing_grammar_transfer.py`, R5-bound tests, tombstone) | **the human**; `GET /coverage` empty | |

## 14. Tests

**In this revision (exist and pass, section 20):**
- `tests/test_grammar_content_store_migration.py` (CI, SQLite): the file is a proposal, not in `versions/`; it is parented on the real
  head and its slot is unique; **no Store code exists before the gate** (no ORM model for the eight tables, no `/api/grammar/v1` or
  `/api/admin/grammar` route); no grammar point JSON under `writing_coach/`, `static/`, `templates/` (D-105.4); on SQLite the upgrade
  adds exactly the eight tables over the full app schema and the downgrade restores it exactly; one published version and the publish
  gate; a superseded version stays `accepted` and is republished (rollback); a rejected version cannot be published; projection and
  id/language CHECKs; one resolution per R5 id across batches; package-hash uniqueness for imported batches only.
- `scripts/rehearse_grammar_content_store.py` (by hand, throwaway PostgreSQL): the twelve groups of `GRAMMAR_CONTENT_STORE.REHEARSAL.md`,
  with every synthetic body validated against export profile 1 before import.
- `scripts/check_grammar_export_contract.py` (by hand, reads GL with `git show`): the boundary of sections 5, 9, 10, 11.

**At implementation (revision 2's list, still required):** importer refusals for every hard-failure and per-point code of 5.3, with
synthetic packages and mutated copies (an extra key at the top level and nested, an internal field in a body, `zh-Hans`, `en`
placeholder, wrong-length pinyin, answer out of range, asymmetric contrasts, unknown `export_profile`, wrong `profile_schema_hash`,
wrong `package_hash`, `source_dirty`), hostile zips refused while decompressing; the golden vector; a drift test comparing the vendored
profile's hash with the pinned constant; idempotency and the diff; lifecycle and the rebuild-and-compare projection test after every
operation; the SQLite immutability invariant; learner API (published only, whitelist drops `source_refs`, ETags, EN/ZH parity, 503
before the migration); R5 merge/split/drop/unavailable incl. composite keys with `:`; progress re-check and the merged-all rule;
authorization matrix; audit rows.

## 15. Holds, safety, what this proposal does not decide

- **Learner-data persistence / sync (AGENTS section 7)**: not touched. No new learner-owned schema; content tables carry only admin
  actors.
- **Deletion and export**: grammar content is not learner data; `grammar_progress` rows go with the account (cascade on `users.id`)
  and into the export; the export format stays deferred (D-104 H-18).
- **Runtimes (D-143.5)**: no new runtime. The rehearsal used a disposable local PostgreSQL 16 cluster created for it and removed
  afterwards; no shared runtime, Docker volume or :8000/:8010/:8011/:8021 was contacted.
- **Protected areas**: R5 Grammar contracts and Concept IDs stay protected until step 9 (D-100.5); not edited.
- **Corpus**: the 595 approved points stay in Grammar Lab; nothing is imported, published or copied here.
- **Reviewer independence**: revision 3 needs its own independent architecture review recorded in Git (reviewer, commit, outcome).

## 16. Rollback

- **Learner impact**: unpublish (or bulk unpublish) hides content on the next request (new revision).
- **Code**: revert the seam commit; the screens return to the empty static seam.
- **Schema**: `downgrade()` drops the eight content tables (no learner data) and re-import restores content; `grammar_progress` is
  unaffected and rows under point ids re-attach when the points return. The R5 map is content: step 9 must not run before `GET
  /coverage` verifies it.
- **Bad batch**: versions are unpublished by default, so a bad import is rejected/unused; a bad publish is an unpublish, the previous
  version is still `accepted` (only `superseded_at` is set) and is re-published by the same gated publish (section 6).

## 17. Decisions

Revision 2's ten decisions are answered by D-106 (section 0) and are not reopened. Revision 3 asks the reviewer (and, where product
or policy, the human) about the following, each with a proposed answer:

1. **R3-1 `source_dirty`**: a package exported from a dirty Grammar Lab tree is rejected (its `source_commit` would not reproduce it).
   *Proposed: reject.*
2. **R3-2 Served body**: the serve-time whitelist is the export profile's top-level keys minus `source_refs`. *Proposed: yes.*
3. **R3-3 Stronger database rules than revision 2**: version DELETE blocked and events append-only by trigger; the publish gate,
   the published projection, the id/language agreement and one-resolution-per-R5-id as constraints; restricting the published
   version's rights requires unpublishing it first. *Proposed: keep all.*
4. **R3-4 Function labels**: the importer requires `vi`, `en` and `zh` (GCC), stricter than the exporter (`vi`, `en`); upstream is
   asked to align its exporter. No corpus change (all 43 labels comply). *Proposed: yes.*
5. **R3-5 Promotion order with `proposed/0026`**: either may go first; the second is re-parented. *Proposed: as stated.*
6. **R3-6 Which runtime first receives 0030**: the human's (D-127, D-143/D-144). *Not proposed here.*
7. **R3-7 Review verdict separate from serving state** (answers the Codex P1): `review_status` is `imported | accepted | rejected`;
   supersession is `superseded_at`. This narrows revision 2's approved version lifecycle (`... -> superseded`) so that the rollback
   revision 2 already promised works. *Proposed: yes.*

## 18. Review response (`GRAMMAR_CONTENT_STORE.REVIEW.md`, revision 2 APPROVE with N-1..N-6)

| Item | Resolution in revision 3 |
| --- | --- |
| N-1 Upstream schema not vendorable | Upstream derived the closed single-version export profile with a drift check (D-106.8). The app vendors that file, pins profile id, schema version and profile hash, and the contract check verifies the profile is valid, closed except two documented maps, and free of internal fields (5.1, 20). |
| N-2 Label change without revision bump | A label change that affects published points bumps the catalogue revision of those languages in the commit transaction (3, 11). |
| N-3 Mapped-versus-dropped only in the validator | One partial unique index `(language_code, r5_id) WHERE is_primary OR point_id IS NULL`; the rehearsal and the SQLite test show a second batch cannot leave both (3, 9.2, 20). |
| N-4 Attestation before anyone looked | Attestation at commit or later (`POST /imports/{id}/rights`); versions stay `unknown` until then; columns all-or-none by CHECK (3, 5.3, 6). |
| N-5 Upsert syntax across backends | Already implemented on `main` with each backend's conflict target (`uq_grammar_progress_scope` on PostgreSQL, `lesson_id` on the per-user SQLite table) (8). |
| N-6 Response shapes the screens do not know | D-106: the seam maps `unavailable` and `dropped` to `{point: null}`; no new landing (7, 13). |

## 18a. Codex review of PR #100 (commit `3f971976`, two P1)

| Finding | Resolution in revision 3a |
| --- | --- |
| **P1 Contract checker passes when dependencies are missing** (`scripts/check_grammar_export_contract.py`: an unexecuted schema check and function-label check were recorded as PASS) | A missing `jsonschema` or PyYAML is now a FAIL row with "NOT RUN" and a non-zero exit; the migration's constants are read with `ast`, so the script needs no Alembic. Shown by shadowing both modules: 22 PASS, 2 FAIL, exit 1 (section 19). |
| **P1 Superseded versions cannot be republished** (the publish transaction set `review_status = 'superseded'`, the gate requires `accepted`, so the promised rollback could not pass it) | Review verdict and serving state are separated (R3-7): `review_status` is `imported | accepted | rejected`; supersession is `superseded_at` (CHECK: never on the published version). A rollback publishes the previous, still `accepted`, version through the same gate (sections 3, 6, 16). The migration, the SQLite test (`test_a_superseded_version_stays_accepted_and_can_be_republished_for_rollback`) and the rehearsal (group 9: rollback, `superseded_at` CHECK, rejected version refused) show it. |
| Also asked by the human: the rehearsal's synthetic bodies carried a non-contract `rehearsal_marker` | Removed. Every synthetic body is generated in the export-profile-1 shape and validated before import against the profile read from GL at `3579ece8` (hash pinned) plus the importer's cross checks; `jsonschema` is required. A negative control shows the closed profile rejects the old key. The ETag race test now reads the served body's contract field `version` (each race publish carries `version` = the revision it is published under). |

## 19. Contract boundary verification (issue #99 point 4; GL `3579ece8`)

`scripts/check_grammar_export_contract.py` read every upstream file with `git show` and parsed upstream Python with `ast` (nothing
imported, nothing copied). It requires `jsonschema` and PyYAML; a missing one is a FAIL row, never a skipped PASS (Codex review
P1; shown by shadowing both: 22 PASS, 2 FAIL, exit 1). Result with both installed: **24 PASS, 0 FAIL** [R].

| Contract point | Upstream at `3579ece8` | This revision | Match |
| --- | --- | --- | --- |
| Export profile / package shape | `grammar-export-profile/1`, `schema_version` `0.4`, 15 manifest keys, `functions.json` = `manifest.functions`, `points/<id>.json` | 5.1, 5.2 | yes |
| Canonical JSON and SHA-256 | sorted keys, `,`/`:`, UTF-8 unescaped, no floats/NaN, no normalisation; golden vector `cf9288...ee27` | 11; reproduced with the standard library | yes |
| `package_hash` | over profile, schema version, language, functions, points' `(id, version, content_hash)`, `r5_map` only | 5.4 (S-5) | yes |
| `en`/`zh` mapping | `target_lang` `en|zh`; locale keys `vi|en|zh`, `vi`+`en` required; `zh-Hans` mapped upstream | 10: importer maps nothing, refuses `zh-Hans` | yes |
| `r5_map` | rows of exactly four keys; five dispositions; primary-only aliases; `source_refs.r5_split` for secondaries | 3, 9 | yes |
| Unknown / internal fields | closed profile; `provenance`, `review`, `flags`, `source_anchors`, `schema_version`, `title`, `summary`, `blocks` absent from bodies | 5.1 | yes |
| Deep closed validation | Draft 2020-12, `additionalProperties: false` everywhere except `locale_map` (closed by `propertyNames`) and `source_refs` (snake_case -> string arrays) | 5.1 | yes |
| Function labels | exporter requires `vi`, `en`; GCC requires `vi`, `en`, `zh-Hans`; data has all three for 43/43 | importer requires all three (R3-4) | latent mismatch, no corpus change |
| Corpus | 595 approved (215 EN, 380 ZH), counted only | not copied, not imported | n/a |

No contract mismatch that requires a corpus change was found, so the corpus is not touched.

## 20. Evidence and the next gate

Run in this agent environment on 2026-10-08 (local execution, not CI):

| Command | Result |
| --- | --- |
| `python scripts/rehearse_grammar_content_store.py <throwaway PostgreSQL 16.15 URL> --report ...` | **66 PASS, 0 FAIL** (1,000 synthetic points, every stored version validated against export profile 1 before import, 100,000 `grammar_progress` rows); full table in `GRAMMAR_CONTENT_STORE.REHEARSAL.md` |
| `python scripts/check_grammar_export_contract.py` (GL `3579ece8`) | **24 PASS, 0 FAIL**; with the two dependencies hidden: 22 PASS, 2 FAIL, exit 1 |
| `pytest -q tests/test_grammar_content_store_migration.py` (SQLite) | 12 passed |
| `pytest -q test_app.py tests` (`PERSISTENCE_BACKEND=sqlite`), the stdlib validators, the ESM graph and the 120 `.mjs` gates of `ci.yml` | 4540 passed, 380 skipped; validators exit 0 (`GRAMMAR_CONTENT_STORE.REHEARSAL.md`) |

**Next gate, in order:** (1) **independent architecture review** of this revision, the migration file and the evidence, by a
reviewer who did not write them, scoped by `GRAMMAR_CONTENT_STORE.REV3_REVIEW_REQUEST.md` and recorded in Git as
`GRAMMAR_CONTENT_STORE.REVIEW.md` "Review of revision 3" (reviewer, commit, verdict); (2) the human's authorization; (3)
promote the migration (`git mv` into `migrations/versions/`, re-parent if 0026 went first) and apply it only where the human says,
after a backup; (4) only then the Store/API implementation of steps 2 and 5. Until (1) and (2), nothing in step 2 or later is written.
