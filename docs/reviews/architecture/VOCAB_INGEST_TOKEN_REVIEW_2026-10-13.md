# Architecture review - Scoped service token for vocabulary preview/import (issue #145)

- Reviewer role: **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority").
- Reviewer model: Claude Opus 5.5 (independent of the implementer). I did not write this change.
- Reviewed: branch `claude/n8n-vocab-generator`, auth commit `6ec68757` (`writing_coach/service_auth.py`, `auth_support.py`, three `app.py` lines, `tests/test_vocabulary_ingest_token.py`, one assertion in `tests/test_admin_authorization_matrix.py`, DECISION_LOG D-18X). The n8n commits `c940860b` and `f9c4c9e1` were skimmed for server-auth impact only: they touch no server auth code (`ci.yml` only adds the workflow test).
- Date: 2026-10-13. Read-only review: no Docker, no app run, no network beyond `gh issue view`. pytest was not run (host has no dependencies); tests were reviewed by reading. Not product approval and not activation authorization.

## VERDICT: CHANGES REQUIRED

The credential mechanics are sound (route scope, digest storage, constant-time compare, no fallback, own context key). One P1 blocks merge: the decision log and commit message say "the credential cannot publish", but a token holder can publish learner-visible vocabulary through a non-authored source. Fix P1-1 and add the test; the rest are conditions or follow-ups.

## What was verified

- **Route scope.** The token is recognised in one place, `UserIsolationMiddleware.dispatch` (`auth_support.py`, new first branch), only when `method == POST`, the path is exactly one of the two strings in `VOCABULARY_INGEST_PATHS`, and a bearer header is present (`service_auth.py` `is_vocabulary_ingest_request`). Any other path or method with the token falls through to the normal session logic and is anonymous (401). A near-miss path (trailing slash, case) is not matched by the middleware either, so it also gets session handling: the failure direction is safe. The two routes call `require_vocabulary_ingest`; grep shows `require_admin` remains the only guard on every other admin route, and `require_vocabulary_ingest` falls back to `require_admin`. `test_the_token_reaches_no_other_route_and_no_other_method` walks the OpenAPI paths with a valid token and expects 401 for all non-scoped `/api/*` routes.
- **Principal cannot be forged.** `request.state.service_principal` is set only by the middleware after a digest match; a client cannot set `request.state`. A wrong or disabled token is refused outright with 401 and never falls back to a session; a valid token ignores any session cookie, so session plus token cannot escalate (the service principal has role `service`, not admin, and is honoured only by the two routes).
- **Bearer parsing and storage.** `bearer_token` takes the case-insensitive `Bearer` scheme and the remainder; an empty token or an empty/malformed hash list never matches. Hashes are 64-hex SHA-256 digests only (others ignored: fail closed), compared with `hmac.compare_digest` against every configured digest without early exit. Unset means off. The module and the new middleware branch log nothing; I found no header logging on this path. 401 text is identical for wrong, missing-but-bearer and disabled, so there is no existence or configuration leak beyond the early-return timing on "no hashes configured", which is immaterial.
- **#137 interaction.** The token branch runs before `foreign_signed_out`/`request_is_local`, so a token request neither needs nor receives local-admin or the shared `legacy` scope: it sets `_user_key` to `service-vocabulary-ingest` and the default language. It is not weakened by a remote peer (the token is the explicit grant). On an auth-off development runtime a remote peer with a valid token reaches the two routes, which is the deliberate scope and still token-gated.
- **CSRF/Origin.** A header-credential route is not CSRF-able; a browser cannot attach the header cross-site without a preflight. Session behaviour and the outer origin check are unchanged.

## Findings

### P1-1 - The token can publish learner-visible content through a non-authored source (contradicts D-18X "cannot publish")
- Where: `app.py` `admin_vocabulary_source_import`: `requested_catalog_status, admission = _vocabulary_admission(collection_metadata, imported_by=imported_by)` and `if authored_in_batch: requested_catalog_status = "pending_review"` (around the end of the route); `_vocabulary_admission` (`app.py:3632-3675`).
- Issue: the forced `pending_review` applies only when the batch contains an authored (JSON/JSONL entry-schema) source. For any other source (CSV/TSV/JSON rows read by the column mapper), `metadata` supplied by the caller decides: `publish: true` with `publication_attested: true` publishes with `attested_by` = the service principal, and a cleared `rights_status` with `completeness: "complete"` auto-publishes with no attestation at all. A leaked token (or any compromised n8n) can therefore make arbitrary vocabulary visible to learners, with caller-chosen rights and completeness. `test_a_published_token_import_is_impossible` covers only an authored JSON batch, so this path is untested. The claims "The credential cannot publish" and "a human still decides what learners see" are false for it.
- Required: for the service principal (role `service`), force `requested_catalog_status = "pending_review"` and `publication_attested = False` for every source format, and ignore `publish`, `publication_attested` and the auto-publish rule (reject with 422 if `publish` is requested, or silently downgrade and report it). Do it in the route (or `_vocabulary_admission`) keyed on the principal, not on the file format. Add tests: a CSV source with `publish: true` and attestation, and one with licensed/complete auto-publish metadata, both imported with a token, must end `pending_review`; session admin behaviour unchanged. Correct the D-18X wording.

### P2-1 - Authored `overwrite` by the token
- `duplicates=overwrite` lets the caller replace a stored authored entry in any non-published set (published sets are refused, D-178). That is the stated admin behaviour and cannot touch published content, but a leaked token can rewrite pending content other reviewers are looking at. Consider restricting the service principal to `duplicates=skip`, or record this as accepted. The `imported_by` recorded is the fixed `service:vocabulary-ingest`, so rewrites cannot be attributed to a client; see P2-3.

### P2-2 - Token strength is not enforced and no throttle exists
- A wrong token costs one SHA-256; there is no per-IP or per-token limit on 401s (the route rate group applies only to authenticated accounts, `app.py` rate limiter keys by session). With a high-entropy token this is fine; the README one-liner hashes whatever the operator types. Required: README/decision text must say "generate 32 random bytes" (for example `secrets.token_urlsafe(32)`), not a typed passphrase. Optional: a small per-IP failure limiter on the two paths.

### P2-3 - No expiry, no per-client identity, long-lived shared secret
- Acknowledged by the implementer. Accepted for a single operator-run ingest client if rotation is documented (comma list is supported). Record that every service import appears under one actor and add a request-id or client label to the import receipt when feasible. A leaked token also reveals which words exist (including published) through preview; accepted by the implementer, I agree it is low severity next to P1-1.

### P2-4 - A session administrator whose browser sends a stray `Authorization: Bearer` header to these two routes gets 401
- Because a bearer header selects the token branch and a mismatch is refused without fallback, any proxy or extension adding an `Authorization` header breaks the admin page for those two routes only. Availability only. Document it or fall back to the session when a bearer header is present but the feature is off (still never when a token is configured and wrong).

### P2-5 - Service key and per-user storage on local SQLite
- The branch skips `ensure_user_db()` and the language seeding that normal requests get. On PostgreSQL (staging/production) the vocabulary repository is global and unaffected; in the SQLite development mode a per-user path derived from `service-vocabulary-ingest` may be missing. Confirm the two routes do not depend on a per-user database, or call the initializer.

### P2-6 - Tests
- Good: digest/compare/parse unit tests, route walk, revocation, session-admin unchanged, learner-with-token still a learner, matrix assertion updated legitimately (it now names the scoped guard and still pins the fallback to `require_admin`; not weakened). Missing: the non-authored publish cases (P1-1) and `duplicates=overwrite` with a token.

### P2-7 - D-18X
- Placeholder id and "reviewer pending": renumber at merge, record this review (reviewer, commit, outcome), and correct the "cannot publish" claim.

## Conditions to merge

- C1: fix P1-1 with tests and corrected wording. C2: P2-2 (token generation guidance). C3: P2-7. P2-1, P2-3 to P2-6 may follow if tracked.
- After the fix, a short re-review of the new diff is required; the approval does not carry to later security-sensitive changes.

## Not verified

- pytest and CI were not run; the new tests were read, not executed.
- `finalize_collection_publication` and the repository behaviour for non-authored sources were read in the route, not run; P1-1 follows from the route logic and the `_vocabulary_admission` code and should be confirmed by the new tests.
- Whether the outer origin check or rate groups apply to these paths was inferred from `rate_group`/`origin_refusal` use in `app.py`, not run.
- The n8n workflow files were skimmed only for auth and secrets; the token is held as an n8n Header Auth credential per the README, not in the workflow JSON.

Architecture review is not product approval and is not activation authorization.

---

## Re-review of 96e23d35 (2026-10-13)

Scope: `git diff 1d4c7e9a..96e23d35` (8 files). Read-only; pytest not run, tests read only. Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5 (independent of the implementer).

### Prior findings

- **P1-1 (publish) - fixed.** In `admin_vocabulary_source_import`, `is_service = admin.get("role") == "service"` (only the token path produces that role) now sets `publish` and `publication_attested` to False before `_vocabulary_admission`, then overrides `requested_catalog_status` to `pending_review` and replaces `admission` with a pending, unattested record (no `attested_by`, no `auto_published`). This is route-level, so it holds for every format (CSV/TSV/XLSX/TXT/JSON/JSONL), authored or not, and mixed batches; `finalize_collection_publication` is only reached when the requested status is `published`. The explicit `catalog_status`, `origin` and `admission` keys in the route override anything the caller put in `metadata`. Session admins are untouched (the guard is the role). The scoped guard is still used by exactly the two routes; the collection publish/lifecycle routes use `require_admin`, so the token (401 on any other route) cannot reach them. New tests drive a CSV import with a token through the publish+attestation, the auto-publish rule (cleared rights + complete) and publish-without-attestation, and assert `pending_review`, not learner-visible, no attestation/`attested_by`/`auto_published`; a session-admin CSV publish test pins unchanged behaviour. They would fail without the fix (the unfixed route published the CSV).
- **P2-1 (overwrite) - fixed.** The service principal gets 422 unless `duplicates == "skip"`, for authored and CSV alike (parametrized test, and nothing stored). The workflow downgrades `overwrite` to `skip` in api mode with a note; the README and config comment say so.
- **P2-2/P2-3/P2-4/P2-5/P2-7 - documented.** D-18X and the README now carry the corrected lifecycle statement, token-generation and rotation guidance and the residuals; the status line records the review and "re-review pending" (to be updated to this outcome, and renumbered at merge).

### New finding

#### P1-2 - The token can alter the display metadata of an already published collection via a non-authored re-import
- Where: `writing_coach/persistence/vocabulary_repository.py` `import_source`, existing-collection branch (lines ~704-726): for a non-authored source (`duplicates is None`) into an existing published collection id, the loop sets `title`, `framework`, `level`, `level_range` and `topic` from the caller's metadata (only `catalog_status` and `provenance` are protected). The authored path is refused for published sets (`duplicates is not None and collection_was_published`), but the CSV path is not. New entries and memberships are refused (good), so content words are safe; the learner-visible title, level and topic of a published set are not.
- Issue: a leaked token (the review's threat) can rename or re-level a published collection by importing a CSV with its `collection_id`. Pre-existing for session admins, but the scoped credential must not widen what it can change on published content.
- Required: for the service principal, refuse any import whose target collection already exists and is published (422 with a clear message), before `import_source`, for every format; add a test that a token CSV import into a published collection id leaves its title/level/topic unchanged and returns 422. Keep session-admin behaviour as is.

### Final verdict: CHANGES REQUIRED (narrow)

P1-1 and P2-1 are properly fixed. One small P1 (P1-2) remains; after it and its test land, a one-diff re-check will give APPROVED. No approved head SHA is issued yet. Not product approval and not activation authorization.
