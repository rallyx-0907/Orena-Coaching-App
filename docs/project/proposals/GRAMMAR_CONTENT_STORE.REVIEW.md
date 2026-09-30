# Review: `GRAMMAR_CONTENT_STORE.md` (grammar content store, Admin import, `/api/grammar/v1/*`)

- **Role:** Delegated Architecture Reviewer, independent of the implementer (`AGENTS.md` section 1
  "Architecture review authority"). I did not write the proposal and did not assume it is right.
- **Reviewed HEAD:** `72cd4cd7c16c338de099aa2df46c20ca73f644cb` (`codex/work`). The working tree also holds unrelated
  uncommitted edits (Reading admin, `models.py`, tests); none were reviewed and none are cited as evidence.
- **Reviewed file:** `docs/project/proposals/GRAMMAR_CONTENT_STORE.md`, revision 1 (untracked, 465 lines).
- **Also read:** D-100, D-101 F, D-104 H-4, D-105 (points 3, 4, 5a), `docs/project/GRAMMAR_CONTENT_CONTRACT.md` (merged
  v0.4), open PR #67 and #68 (`gh pr view`), `docs/grammar_lab/INTEGRATION_DESIGN.md` on
  `origin/feature/grammar-lab-pipeline`, `grammar_lab/schema/grammar_set.schema.json`, `static/orena/product/grammar-source.js`,
  `app.py` grammar routes, the learning repositories, `models.py` (`GrammarProgress`), migrations 0008 and 0023, the Reading
  and Vocabulary admin routes, `tests/test_admin_authorization_matrix.py`, `AGENTS.md`, `REVIEW_POLICY.md`.
- **Limits:** documents and code were read; nothing was run, no test executed, no database touched. No PASS is claimed.

## Verdict: **REQUEST CHANGES**

There is no P0. Two P1s remain, and both are gaps in the specification that cannot be left to implementation. The
overall design is sound and appropriately conservative: new tables only, no learner-owned schema, immutable versions,
explicit publish, a hard rights gate, an idempotent import keyed by hashes, an audited, matrix-covered Admin surface, and
progress that reuses `grammar_progress` without rewriting a learner row. Its central factual finding (the stored R5 key is a
composite) is correct and important. Once the two P1s are answered in the text, no further design round is needed.

## Factual claims checked

| Claim | Result | Evidence |
| --- | --- | --- |
| `_grammar_storage_key` writes `"{language}:grammar:v{content_version}:{lesson_id}"` and both repositories store it in `lesson_id` (Finding 1) | **Correct** | `app.py:2039-2042`; `api_complete_grammar` passes `_grammar_storage_key(lesson)` to `set_grammar_completed` (`app.py:2157-2168`); `learning_repository.py:323, 715-724`; `tests/test_grammar_storage_namespace.py:17` asserts `en:grammar:v2:a1-present-simple`. D4 I11's "R5 rows keep their R5 id" is therefore wrong for a bare-id join, and the proposal's strict `^(en\|zh):grammar:v\d+:(.+)$` parse is the right fix |
| `grammar_progress.lesson_id` is `VARCHAR(255)`, unique on `(user, language, lesson_id)`, no FK | Correct | `models.py:214-226` |
| Schema-version finding: the repo's `grammar_set.schema.json` is the Phase 0 schema, older than GCC v0.4 and #67; no `jsonschema` dependency | **Correct** | `grammar_lab/schema/grammar_set.schema.json`: `schema_version` const `"0.2"` (line 13), point-level `title`, `summary`, `blocks` required (lines 103-127); GCC v0.4 removed point-level title/summary (contract "Phiên bản"); `requirements.txt` has no `jsonschema` |
| PR #68 fixtures are `draft_ai`, `sample: true`, `approved: false` | Correct | `gh pr view 68`; the importer must refuse them |
| Vocabulary publish is not hard-gated; Reading is (D-105) | Correct | `admin_console_api.py:1028-1032` ("decision support, not a permission gate"); `reading_admin_api.py` `publication_blockers` (D-105) |
| Upload read in chunks, capped, never read-then-check | Correct (line numbers drifted) | `reading_admin_api.py:545-562` (proposal cites 517-534) |
| Review events in the same transaction, `audit_logs` best effort | Correct | `reading_admin_api.py` `_audit` docstring; `models.py:1063-1076` |
| `archived -> unpublished` only; restore never straight to published | Correct | `admin_console_api.py:1070-1095` |
| The seam reads `CONTENT_BASE`, applies `approved()` client-side, and redirects through `aliases` | Correct | `grammar-source.js:19-21, 44-88` |
| Admin route matrix reads the app's routes and fails on an unlisted one | Correct | `tests/test_admin_authorization_matrix.py:180-201` (`len(routes) == 61` will change) |
| 0023 is now in `migrations/versions/`, so `down_revision = "20260930_0023"` is a real head | Correct | `migrations/versions/` listing; D-105.1 |
| GCC section 9: aliases resolve R5 ids; split pieces each keep the R5 id **and** an R5 id is in at most one point's `aliases` | **The contract contradicts itself** | GCC section 9 (lines 294-301). See P1-1 |
| The SQLite `grammar_progress` and ORM already carry `last_quiz_*` | **Not yet** | `grep last_quiz writing_coach` finds nothing at this HEAD; the D4 model and SQLite changes are still an implementation step. The proposal depends on them (P2-7) |

## Findings

### P1-1: The R5 alias model cannot express what the contract says, and has no source for its dispositions

**Evidence.**
- GCC section 9 says, for a split, "each piece keeps the original R5 id in `aliases`, with a primary piece chosen in
  `source_refs`", and in the same paragraph "each R5 id appears in the `aliases` of at most one point
  (`aliases.duplicate`)". Both cannot hold for a split.
- The proposal's `grammar_id_aliases` has primary key `(language_code, alias_id)`, a `disposition` of
  `replaced | merged | split_primary | dropped`, and a publish rule that an alias held by a different published point blocks
  the publish (sections 3, 6, 9). Under that rule only one piece of a split can ever be published with the R5 id.
- The dispositions have no stated source. A point file's `aliases` is a `string[]`; "merged" (several ids in one point) can be
  counted, but `split_primary` and `replaced` cannot be read from it, and `source_refs` is not in the package shape of section 5.1.
  The `dropped` rows have `point_id NULL`, so they belong to no point, yet the table is described as "rebuilt in the publish
  transaction" of a point (section 3). Nothing says when or from which batch a dropped row is written, or removed.
- The projection exists only for the *published* version. Unpublishing or archiving a point deletes its alias rows (section 6),
  so its R5 ids stop resolving. D-101 F, D-103.1 and step 9 (R5 removal) make this table the **only** resolver once the R5
  tables and JSON are gone, and require that no learner's old id fails silently.

**Why P1.** R5 resolution is the reason the table exists, its rule for merged and split points is learner-facing (completion
shown or not shown), and the contract it implements is ambiguous. Leaving this to the implementer would be a silent decision.

**Required change.**
1. Get the contradiction in GCC section 9 resolved (Grammar Lab lane plus the human) and state the chosen reading in the
   proposal. The reading that is consistent with `aliases.duplicate` and with `PK (language, alias_id)`: an R5 id is in the
   `aliases` of exactly one point; for a split only the primary piece carries it; other pieces carry none and inherit no
   completion.
2. Specify the package field that carries each R5 id's disposition (for example `r5_map: [{r5_id, point_id|null, disposition}]`
   in the manifest, validated against the point files' `aliases`), so dispositions are read, not inferred.
3. Persist alias rows independently of publish state: written from an *accepted* version, and kept when the point is
   unpublished or archived (the row then resolves to a point that is not served, and the API answers "unavailable" or the
   library, not 404). Say where `dropped` rows are written (the batch that carries `r5_map`) and how a later batch
   supersedes them.
4. Add tests for a split, a merge, a dropped id, an id whose replacement is unpublished, and the composite key of each.

### P1-2: The trust boundary for content served verbatim to learners is a self-attested boolean plus shallow checks

**Evidence.**
- Finding 3 (correct) says the app cannot re-run Grammar Lab's validator. The proposal therefore validates "required top-level
  fields of GCC sections 0-7 with the right JSON types" and accepts the manifest's `validator.passed` (section 5.3). That boolean
  is part of the uploaded file and is not covered by any hash; nothing in the app can check it.
- The learner API returns `content` "verbatim" (section 7) and the two screens draw the nested structure (formula roles, example
  spans, timeline data, quick-practice options, pinyin arrays). A point that passes the shallow check but has, say, a span outside
  its sentence, a missing option or a wrong-length pinyin array reaches a learner as a broken screen or a thrown error. The
  admin preview is the second gate, but it is human eyes on up to hundreds of points.
- The checks do not say that unknown top-level keys are rejected. PR #68 shows the point files are meant to omit internal
  `provenance`, `review` and `flags`; an export that includes them would publish reviewer identity, model names and routing flags
  to learners.

**Required change.**
1. Choose the deep-validation route explicitly (decision 8). Recommendation: vendor the exact accepted schema and validate every
   point with `jsonschema` (a reviewed new dependency), plus the app-side cross checks already listed (hashes, ids, symmetric
   contrasts, acyclic prereqs, alias uniqueness, function labels). If the human declines the dependency, the hand-written
   validator must cover every field the two screens read, and be proved against the fixtures below.
2. Reject any unknown key in the point object (top level and each nested object the schema closes). Serve only the whitelisted
   contract keys.
3. State the accepted `schema_version` set concretely. Today the repo's schema says `0.2`, the contract says `v0.4`, and #67 (open)
   changes `target_lang` to `zh-Hans` and the locale rules. The importer should accept exactly one contract version at a time,
   and be implemented against a merged contract, not an open PR.
4. Add a corpus test: the 13 PR #68 points converted to `approved` import and validate; a set of mutated copies (bad span,
   missing locale, extra key, wrong pinyin length, asymmetric contrast) is refused.

### P2 findings (non-blocking; fold in while editing)

- **P2-1 A stale cache can be pinned to a new label.** Section 11 serves `GET /points` with `ETag: W/"<language>-<catalog_revision>"`.
  If the handler reads the points first and `grammar_catalog_state.revision` second, a publish between the two reads returns old
  content labelled with the new revision, and clients revalidate against a matching ETag until the next publish. Read the revision
  first, then the content (content newer than its label is harmless), or read both in one statement or one repeatable-read
  transaction. Also `GET /points/{id}` puts `catalog_revision` in a body keyed by the point's `content_hash` ETag, so an unrelated
  publish changes the body but not the ETag: drop the field from that body.
- **P2-2 Circular foreign key.** `grammar_points.published_version_id -> grammar_point_versions` and
  `grammar_point_versions.point_id -> grammar_points` form a cycle, which Alembic cannot create in one `create_table` and
  SQLAlchemy's SQLite `create_all` cannot express. Prefer a cycle-free design: `grammar_point_versions.is_published` with a
  partial unique index `(point_id) WHERE is_published`, which also makes "one published version per point" a database fact.
  The CHECK `(lifecycle = 'published') = (published_version_id IS NOT NULL)` then becomes a publish-transaction invariant with a
  test.
- **P2-3 Immutability by convention only.** "A row is never updated except `review_status`, `rights_status`, `reviewed_*`" needs
  enforcement. D4's `essay_review_history` and migration 0015 use a PostgreSQL `BEFORE UPDATE` trigger; here the trigger would reject
  changes to `content`, `content_hash`, `version`, `point_id`, `provenance` while allowing the review columns. Add it (guarded by
  dialect, with a repository invariant and test for the SQLite backend).
- **P2-4 Denormalised projections can drift.** Serving columns on `grammar_points`, `grammar_id_aliases` and
  `grammar_point_error_tags` are three copies of data inside `content`. Add a test that rebuilds each projection from `content`
  and compares, run after every lifecycle operation, and state the nullability of the serving columns before first publish.
- **P2-5 `UNIQUE (point_id, content_hash)` versus a bumped version.** Upstream reverting to earlier content under a higher version
  violates the second unique key while passing the version check; the proposal has no refusal code for it, so it would surface as
  a database error. Add `content_already_stored` (refused per point), and decide whether a `rejected` version's hash may be
  re-offered.
- **P2-6 Import details.**
  (a) Zip limits (member count, size, uncompressed total) must be enforced while decompressing with a running byte budget, not from the
  `ZipInfo.file_size` header, which the sender controls; also cap the compressed upload (Reading's `MAX_FILE_BYTES` pattern).
  (b) A 1,000-point import in one request is 20 MB of JSON and cross-checks in one transaction: state the time budget and whether it
  runs inline (Reading returns 202 and uses a worker; the proposal's synchronous form is acceptable at this size if bounded and tested
  in the rehearsal).
  (c) A hard-failure batch: the summary says "nothing written", but `grammar_import_batches` has `status: rejected` and `refusals`; say
  whether a rejected batch writes a receipt, and that `already_imported` is never returned for one.
  (d) Cross-references to points "already in the database" need a defined target state (published version, or latest accepted).
  (e) `grammar_functions` are shared across languages but written per batch: define who wins when two packages disagree, and record it
  as an event.
- **P2-7 Dependency on the D4 implementation.** `PUT /progress/{id}` writes `last_quiz_*`, which the ORM and the SQLite `initialize()`
  do not carry at this HEAD. State that the route lands after D4 section 15's model changes. Implement the write as
  `INSERT ... ON CONFLICT (uq_grammar_progress_scope) DO UPDATE` keeping the first `completed_at` and using
  `COALESCE(EXCLUDED.x, existing.x)` for each of the three quiz columns; the current repository pattern is `get` then `add`
  (`learning_repository.py:715-724`), which under a race raises `IntegrityError` and would 500. Test the race on PostgreSQL.
- **P2-8 "The server grades" is overstated.** The quiz key is inside `content` and `GET /points/{id}` serves it verbatim, so the
  browser holds the answers; the `answers` posted are still client-reported picks. Grading on the server fixes arithmetic and
  arbitrary claimed scores, and it remains activity, not evidence (`EA:14`). Reword section 8 item 2 and the response claim.
- **P2-9 Rights gate mechanics.** `rights_status` per version, starting `unknown`, means every upstream bump needs a fresh human
  attestation, which does not scale to hundreds of points and invites rubber-stamping. Grammar Lab records catalogue codes only, so the
  real question is batch-wide (were the examples authored under Orena's own rights?). Record a batch-level attestation
  (`rights_basis`, actor, text) copied to each version, with a per-version override to `restricted`, and keep publish refusing anything
  not `cleared`.
- **P2-10 `DELETE /progress/{id}`** deletes the learner's alias rows as well. That is the learner's own un-completion and is
  acceptable, but it removes historical R5 rows that D-103.1 says are kept as data: state that this is a learner action, report
  `changed`, and never do it from an admin path.
- **P2-11 Small drift.** Line references for `_read_upload` and the audit helper are off by about thirty lines. The route name change from
  D4's placeholder is fine. Add a test for the composite-key parse using a lesson id that itself contains `:`.

## Judgement on the specific questions

- **AGENTS section 7.** Grammar content is shared curriculum, not learner-owned data, so the content store resolves no hold. Progress
  reuses `grammar_progress` and 0023 (D-104, D-105). No sync cursor, tombstone horizon, compaction or account-deletion runtime is
  designed. Correct.
- **Schema (eight content tables).** Additive and independent of learner tables. The choices are sensible (immutable versions, an
  append-only event table, a batch receipt keyed by `package_hash`, `sa.JSON` for portability). Fix the cycle (P2-2), enforce
  immutability (P2-3), and keep the projections honest (P2-4).
- **Migration plan.** One revision after `20260930_0023`, no lock on a learner table, downgrade drops content only and is safe
  to rehearse. The rehearsal plan (1,000 points, 100,000 progress rows, `EXPLAIN`, a failed-publish check, a concurrent publish and
  read) is right; add the ETag ordering check (P2-1).
- **Import idempotency and validation.** Keyed on `package_hash` and `(point_id, content_hash)`, dry run writes nothing, unlisted points
  reported and never unpublished. Good. The validation depth is P1-2.
- **Lifecycle and rights gate.** Explicit, atomic, audited, never a side effect of import; archived cannot go straight to published.
  Bulk publish being all-or-nothing is right for an R5-sized replacement.
- **Learner API and atomic progress.** Published-only, no per-learner field in the catalogue, redirect body for R5 ids consistent with the
  seam. Progress in one statement satisfies D-105 H-20 once P2-7 is applied.
- **Access control.** Same guard, same-origin, audit and matrix as Reading; every new route must be added to the matrix and its count updated.
- **Deletion and export.** Content is not learner data and is neither exported nor deleted with an account; `grammar_progress` rows are
  already in the D-055(b) enumeration from D4. Correct.
- **Tests.** Real repositories, no store mocks, importer/lifecycle/API/progress/R5/access/guard/rehearsal groups. Add the P1 corpus test,
  the split/merge/dropped alias tests, the ETag ordering test, the immutability trigger test and the progress race.
- **Rollback.** Unpublish is immediate; the migration downgrade drops content only; a bad import is unused rather than reverted. Sound.
- **Native client.** `useGrammar.ts` is untouched (frozen); the R5 routes stay until step 9.

## Recommendations on the open decisions (section 17)

| # | Recommendation |
| --- | --- |
| 1 Model | Approve: database content, immutable versions authored upstream only, explicit publish, with the immutability trigger and the one-published-version index (P2-2, P2-3). |
| 2 Package contract | Not acceptable until it carries the alias dispositions (P1-1), one `schema_version`, and a normative canonical-JSON rule for `content_hash` (sorted keys, no ASCII escaping, integers not floats, no Unicode normalisation) with a golden vector containing Vietnamese and pinyin strings. It must be agreed and recorded by the Grammar Lab lane before step 3. |
| 3 Batch atomicity | Whole-batch rejection for structural and cross-point failures, per-point refusal for status and version, as proposed. |
| 4 Merged R5 points | Complete only when **all** aliased R5 lessons are complete. Completion drives "next" and library state, and understating a merged point is safer than claiming content the learner never studied; upstream's `ID` section 4 option 2 says the same. Show partial completion as not completed; the human decides. |
| 5 Reviewer separation | No separation now (one admin team); keep import, accept, rights and publish as four separately audited acts. |
| 6 Rights gate | Yes, hard gate on publish, with a batch-level attestation (P2-9). |
| 7 Dangling references | Refuse publish while any `prereqs`, `contrasts` or `compare.with` target is unpublished, evaluated against the resulting state so a bulk publish can satisfy it; a single-point override needs an explicit flag and an event. `compare.with` is drawn as a link and must not 404. |
| 8 Validation | Add `jsonschema` and vendor the exact schema (P1-2). If declined, the hand validator must be deep and corpus-tested. |
| 9 Names and retention | `PUT /api/grammar/v1/progress/{id}` is fine. Do not keep the raw package, but store the manifest (without point bodies) on the batch receipt so the `validator` verdict and `r5_map` are auditable. |

## To reach APPROVE

1. P1-1: reconcile the contract on splits, specify the disposition source, and keep alias rows independent of publish state.
2. P1-2: choose deep validation, reject unknown keys, name one accepted `schema_version`, add the corpus test.

The P2s should be folded in but do not block. Human approval remains required after this review (D-105.4). This review is not
product approval, not authorization to write or apply a migration, and does not touch `ORENA_ACCOUNT_BACKBONE` or any runtime.

## Re-check of revision 2

- **Reviewer:** the same Delegated Architecture Reviewer, independent of the implementer.
- **Reviewed HEAD:** `72cd4cd7c16c338de099aa2df46c20ca73f644cb` (`codex/work`; unchanged since the first review).
- **File:** `docs/project/proposals/GRAMMAR_CONTENT_STORE.md`, revision 2 (610 lines, untracked): sections 3-9, 11, 13, 14, 17, 18.
- **Scope:** whether P1-1, P1-2 and each P2 is resolved in the text and consistent with the code and the contract. Not a second design
  review. Nothing was run and no PASS is claimed. Items presented as human decisions count as resolved when options and
  consequences are stated honestly.

### Per finding

| Finding | Status | Evidence |
| --- | --- | --- |
| P1-1 R5 alias model | **RESOLVED** | Section 9.1 states the GCC section 9 contradiction and proposes a contract fix for the Grammar Lab lane and the human (an R5 id in the `aliases` of exactly its primary; secondaries via `source_refs`), without deciding it, and the store accepts either reading (only the validator rule changes). Dispositions come from an explicit manifest `r5_map` (5.2, 9.2), validated against the point files' `aliases`. New `grammar_r5_map` (section 3): nullable `point_id`, CHECK `(disposition = 'dropped') = (point_id IS NULL)`, partial unique `(language_code, r5_id) WHERE is_primary`, a dropped id once, one primary or one drop per id. Rows are written when the batch commits and are never touched by publish, unpublish, archive or R5 removal (9.3); an unpublished target answers `unavailable`, a dropped id `dropped`. Merge, split and drop tests are in 14.8. Consistent with GCC section 9 and the composite key confirmed earlier |
| P1-2 Trust boundary | **RESOLVED** (with new issue N-1) | Section 5.1: the manifest verdict is demoted to an audit record; deep validation against a vendored closed schema with `jsonschema` is the proposed answer to decision 8 (a hand validator that covers every field the screens read is the counted fallback); unknown keys rejected at every closed object; `provenance`, `review`, `flags` forbidden in point files; a serve-time top-level whitelist as belt and braces; one `SUPPORTED_SCHEMA_VERSION`, and code starts only against a merged contract (steps 0 and 2, section 13). Corpus test with converted fixtures and mutated copies (14.1) |
| P2-1 ETag ordering, revision in body | RESOLVED | Revision read first (or one repeatable-read transaction), a test forces a publish between reads; `catalog_revision` removed from the `/points/{id}` body (7, 11, 14.7) |
| P2-2 Circular FK | RESOLVED | Section 3: no cycle; `is_published` on versions with partial unique `(point_id) WHERE is_published`; create order in section 4 |
| P2-3 Immutability | RESOLVED | Trigger on `point_id`, `version`, `content`, `content_hash`, `source_status`, `provenance`, `batch_id`, `imported_at`; SQLite as a repository invariant; tests 14.6 |
| P2-4 Projection drift | RESOLVED | Serving columns NULL until first publish; rebuild-and-compare after every lifecycle operation (14.5) |
| P2-5 Hash collisions | RESOLVED | `content_already_stored`, `content_previously_rejected` (5.3), decision 10 |
| P2-6 Import details | RESOLVED (see N-2) | 5.5 (running byte budgets while decompressing, compressed cap, synchronous with a 30 s budget timed in the rehearsal); rejected batches write a receipt and `already_imported` only for `imported` (partial unique on hash); reference target state defined (5.3); later batch wins on function labels with an event |
| P2-7 D4 dependency, `ON CONFLICT` | RESOLVED (see N-5) | Section 8 states the dependency on D4 section 15 and step 5 orders it; one upsert with `COALESCE`, first `completed_at`; race test in 14.9 |
| P2-8 "Server grades" | RESOLVED | Section 8 item 2: the key is served, the client grades, the server re-checks and stores its own arithmetic; still activity, not evidence |
| P2-9 Rights | RESOLVED (see N-4) | Batch-level `rights_basis`, attestation text and actor on the receipt, copied to versions, per-version `restricted`, publish refuses anything not `cleared` |
| P2-10 `DELETE` | RESOLVED | Stated as a learner action only, reports `changed`, never an admin or system path |
| P2-11 Drift | RESOLVED | References by function name; composite-key parse test with a `:` in the id (9.4, 14.8) |

### New issues (all P2; carry into implementation)

- **N-1 The upstream schema cannot be vendored as it stands.** On `origin/feature/grammar-lab-pipeline`,
  `grammar_set.schema.json` accepts `schema_version` `0.2`, `0.3` and `0.4` in one file, keeps `blocks`, `story`, `title` and
  `summary` for older versions, and **requires** `provenance` and `review` on every point. Section 5.1 both says "copy the contract's
  closed schema" and forbids `provenance`/`review`/`flags` in point files. Both cannot hold for the file as written. Specify a derived
  **export-profile schema** (one version only, `status` const `approved`, internal fields removed, the optional story block decided
  and added to the serve whitelist if kept), record the upstream commit it was derived from, and add a test that fails when the
  derived profile and the upstream schema disagree on any shared definition. Also confirm that upstream has a JSON Schema for the
  #67 changes at all (its Python validator was updated; the schema file is not shown to be); until then decision 8 has nothing to
  vendor.
- **N-2 Function labels change without a revision bump.** `GET /points` returns `functions:[{id,title}]`, and a later batch can
  change a label (`function_label_changed`), but `grammar_catalog_state` is bumped only by publish, unpublish and archive
  (section 3). The catalogue ETag would not change and clients would keep old group titles. Bump the revision of every language
  whose published points use that function when a label changes, in the commit transaction, or define the ETag over the functions too.
- **N-3 The R5 map's mapped-versus-dropped rule lives only in the validator.** The partial unique indexes allow an R5 id to have both
  a primary row and a `dropped` row across separate batches. Enforce it in the batch-commit transaction by replacing all rows of an
  id together (already stated in 9.2) and add a database-level test that a second batch cannot leave both.
- **N-4 The rights attestation is given before anyone has looked.** The attestation is a field of `POST /imports`, so it is made at
  upload, before the preview and before accept. Allow the batch attestation to be recorded or confirmed at accept time, after the
  admin has read the diff, and keep versions `unknown` until then.
- **N-5 Upsert syntax across backends.** `ON CONFLICT ON CONSTRAINT uq_grammar_progress_scope` is PostgreSQL-only; SQLite needs a
  column conflict target. Say the repository uses column conflict targets on both (SQLAlchemy `index_elements`), and note that the
  SQLite repository's per-user `grammar_progress` table is keyed by `lesson_id` only, which the D4 model work must reconcile.
- **N-6 Response shapes the screens do not know.** The seam today handles `{point}`, `{point:null, redirect}` and `{point:null}`.
  The `unavailable` and `dropped` bodies must be mapped by the seam to the existing not-found shape unless the design draws a
  landing (invent nothing, CLAUDE.md rule 4); "lands on the library" is the UI lane's decision, not the API's.

### Final verdict: **APPROVE** (architecture proposal only)

P1-1 and P1-2 are resolved, every P2 from the first review is resolved in the text and consistent with the code and the contract,
and the six new items are P2. Under `REVIEW_POLICY.md`, with no unresolved P0 or P1, the verdict is APPROVE. This approves the
**architecture proposal** only. Conditions that remain outside this review:
- the human's answers to the ten decisions of section 17 (the proposed answers agree with my recommendations, except that decision
  8 depends on N-1);
- PR #67 merged, the GCC section 9 split reading settled by the Grammar Lab lane and the human, and the package shape and canonical
  hash rule agreed and recorded in Git before step 3;
- the migration stays a proposal (`migrations/proposed/`) until a recorded throwaway-PostgreSQL rehearsal and the human's
  authorization; it applies to :8021 only.

This review is not product approval and does not authorise writing or applying any migration or touching any runtime.
