# Vocabulary Source Import architecture review

Status: `APPROVED` for the committed implementation under review.

## Review record

- Reviewer role: Delegated Architecture Reviewer
- Reviewer identity: independent Codex review session
- Reviewer model: `GPT-5/Codex` (requested model profile: `gpt-5.6-luna`)
- Reviewed commit: `a1a90b7bfe8ebdd5f60e1a928f0b070f52cc3c8d`
- Review date: 2026-09-16
- Scope: Vocabulary Source Import, shared Library/Card content repository,
  source normalization, publication isolation, and regression coverage.
- Unrelated Reading Library worktree changes were excluded.

## Verdict

`APPROVED`: no remaining P0 or P1 findings were identified in the follow-up
review.

The review specifically verified that:

1. A pending source that shares identity with an entry in a published
   collection no longer mutates the published lexical entry. The imported
   source record is retained as a collection-scoped `content_snapshot` in the
   existing membership JSON metadata and is projected when that collection is
   read. Finalizing the pending collection therefore preserves its source
   content while the earlier published collection remains unchanged.
2. JSON localized meaning and definition objects preserve each object's
   language. Language maps and simple scalar/list source fields retain the
   correct fallback behavior.
3. The fix adds no learner-owned persistence, AI enrichment, duplicate review
   scheduler, or parallel vocabulary identity. Source origin/provenance remains
   explicit.

## Verification evidence

- Follow-up reviewer verdict: `APPROVED`, reviewed commit recorded above.
- Canonical local Docker suite: `1059 passed, 114 skipped, 4 warnings`.
- Targeted vocabulary importer/repository suite: `18 passed, 1 skipped`.
- Python compile and Ruff checks: pass.
- Admin, Vocabulary Card, Vocabulary Experience, Feed, Library, Saved Card,
  browser ESM graph, and Orena foundation gates: pass; ESM graph linked 59
  modules.
- These are local execution results, not a CI claim.

## Remaining authorization boundary

This review does not authorize schema activation, deployment, or product
approval. Migration `20260916_0008_vocabulary_content_catalog.py` remains in
`migrations/proposed/` and still requires explicit human schema/runtime
authorization followed by the documented throwaway PostgreSQL rehearsal.

## Review execution note

`claude-2` was not available because its CLI authentication was missing
(`INFRA_FAILURE=auth`). Two initial Codex reviewer launches were also
classified as runner infrastructure failures (`launcher_error` and `timeout`)
because the nested CLI inherited an incompatible shell/MCP environment. The
final independent review used a UTF-8 stdin patch transport with the user
configuration ignored and completed successfully. No secret values were
exposed or stored.
