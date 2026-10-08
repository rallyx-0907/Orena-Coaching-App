# Grammar content store: implementation record (non-UI backend)

Issue #99, after the architecture gate. Revision 3a of `GRAMMAR_CONTENT_STORE.md` was approved by the independent review
(`GRAMMAR_CONTENT_STORE.REV3.INDEPENDENT_REVIEW.md`, APPROVE at `b3ee8f09`) and merged in PR #100. The human then
authorized (2026-10-08): promote `0030` in source control only if its parent is still the real head; implement the
non-UI store, validator, importer, Admin lifecycle, learner API and progress/R5; reuse the approved 595-point corpus;
apply no migration to any runtime; touch no learner or Admin UI; stop and report when UI integration is next.
The work lives on its own branch, `feature/grammar-content-store`, cut from `main` (human direction: no unrelated
`codex/work` commits in the Grammar backend PR).

## What exists now

| Piece | Where |
| --- | --- |
| Migration promoted (parent `20261007_0029` verified on `main` `a96b0e6d`) | `migrations/versions/20261008_0030_grammar_content_store.py`; `proposed/20261005_0026_ai_cost_records.py` re-parented on it |
| ORM models (byte-identical CHECK/index SQL; a parity test compares `create_all` with the migration) | `writing_coach/persistence/models.py` (`Grammar*`) |
| Vendored export profile 1 (hash-pinned) and the boundary constants | `writing_coach/grammar_store/schema/`, `writing_coach/grammar_store/contract.py` |
| Package reader (byte budgets while decompressing) and validator (closed schema, cross checks, `r5_map`, labels) | `writing_coach/grammar_store/package.py` |
| Store: import (dry run, commit, receipts, diff, refusals), rights, review, publish/bulk/rollback, unpublish/archive/restore, admin reads, learner reads, R5 resolution | `writing_coach/persistence/grammar_store_repository.py` |
| Admin API, 15 routes (`require_admin`, same-origin, no-store, audit + review events) | `writing_coach/grammar_admin_api.py`, registered in `tests/test_admin_authorization_matrix.py` (83 routes) |
| Learner API (`/points`, `/points/{id}`, `/by-error`, `/progress` GET/PUT/DELETE) | `writing_coach/grammar_api.py` |
| Wiring (store only on PostgreSQL; 503 `grammar_store_unavailable` otherwise) | `app.py` (`configure_grammar_store_from_runtime`) |
| Dependency `jsonschema` (D-106.8) | `requirements.txt` |
| Real-corpus rehearsal tool | `scripts/rehearse_grammar_corpus_import.py` |

## Implementation decisions inside the approved design (for the reviewer of this PR)

1. **"The same content again" ignores `version`.** `version` is inside the hashed body, so `content_already_stored` and
   `content_previously_rejected` (D-106.10) compare a fingerprint of the body without `version`; otherwise they could
   never fire. A point at the same version with the same hash is `unchanged`.
2. **Upload is the deterministic zip** that upstream's `package_to_zip` writes; no JSON-bundle form (none exists upstream).
3. **A non-approved point fails the closed schema** (`status` is the constant `approved`), so it rejects the batch
   instead of being skipped; upstream never exports one.
4. **Writes never target an alias:** `PUT /progress/{r5-id}` answers `409 grammar_point_moved` with the redirect body.
5. **Progress via R5** counts only through primary rows; a merged point needs all its R5 ids; split secondaries inherit
   nothing; the earliest `completed_at` of the contributing rows is reported; nothing is rewritten.
6. **Restricting the published version** unpublishes it in the same transaction (the CHECK requires it).
7. **Function-label change** bumps the catalogue revision of every language whose published points use it (N-2).

## Evidence (local execution in the agent environment, not CI)

| Run | Result |
| --- | --- |
| `pytest tests/test_grammar_store.py tests/test_grammar_routes.py tests/test_grammar_content_store_migration.py` (SQLite) | 55 + 9 + 12 passed |
| `tests/test_admin_authorization_matrix.py` | 253 passed (83 admin routes) |
| `tests/test_grammar_store_postgres.py` on a throwaway PostgreSQL 16.15 at head `0030` | 5 passed (triggers under the repository, concurrent publishes, concurrent commits of one package, R5 progress through `PostgresLearningRepository`, restrict-unpublish) |
| `scripts/rehearse_grammar_content_store.py` on the promoted chain | 65 PASS, 0 FAIL |
| `scripts/rehearse_grammar_corpus_import.py` with the **real approved corpus** exported by Grammar Lab's own `export-package --zip --with-dropped` at `3579ece8` (EN 215, ZH 380; packages kept in the scratch area, never in the repository) | 23 PASS, 0 FAIL: both validate with 0 problems, import, accept, bulk-publish all 595, catalogue/levels/labels served, R5 redirect/composite/dropped, **R5 coverage complete in both languages (0 unresolved)** |
| `scripts/check_grammar_export_contract.py` | 24 PASS, 0 FAIL |
| Full `pytest -q test_app.py tests` (SQLite; and with `ORENA_TEST_POSTGRES_URL`) | see the PR description for the exact counts |

No migration was applied to :8000, :8010, :8011, :8021 or any persistent runtime.

## Runtime consequence (operator, human gate)

`migrations/versions/` now ends at `20261008_0030`. A PostgreSQL runtime that takes this code refuses to start until
`0030` is applied (`scripts/bootstrap_runtime_schema.py --upgrade --from 20261007_0029 --to 20261008_0030 --confirm`,
after a backup, on the runtime the human names; for :8000 through the reviewed release pack, D-143/D-144). The migration
takes no lock on any existing table (rehearsed with all 56 tables held `ACCESS EXCLUSIVE`).

## STOP: what UI integration needs (not started; the human decides the handoff)

Backend, API and the real import/publish path are ready. The next steps are UI work and are **not** done:

1. **Learner seam** `static/orena/product/grammar-source.js`: point `grammarCatalog()` at `GET /api/grammar/v1/points`
   and `grammarPoint()` at `GET /api/grammar/v1/points/{id}`; map `redirect` to the existing redirect, and `unavailable`
   / `dropped` / 404 to the existing not-found shape (D-106); delete `CONTENT_BASE`, the client `approved()` filter and
   the `zh-Hans` branch of `contractText` (the API serves `zh`). The screens (frames 44/47), `model.js` and copy do not
   change.
2. **Completion and quiz**: `screens/grammar-concept` sends its picks to `PUT /api/grammar/v1/progress/{id}`
   (`{"answers": [...]}`) instead of the R5 `completeGrammar`; reads `GET /progress` for completion state.
3. **Admin**: a Grammar entry in the existing Admin Imports flow (upload, dry-run diff, commit with rights attestation,
   receipt) and a review/publish view (versions, accept/reject, rights, publish/bulk, unpublish/archive/restore,
   preview, R5 coverage). `Orena Admin.dc.html` draws none of these (UI_BACKEND_GAPS G-10): the layout is a human design
   decision.
4. **Agent**: `grammar.point` stays out of `supported_intents` until (1) ships (D-126).
5. **Later, human-gated**: apply `0030` to a runtime; import and publish the approved packages there; R5 removal
   (step 9) only after `GET /coverage` is empty on that runtime.
