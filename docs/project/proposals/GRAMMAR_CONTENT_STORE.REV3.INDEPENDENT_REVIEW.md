# Independent architecture review: Grammar Content Store revision 3a

- **Reviewer:** ChatGPT (GPT-5.6 Sol), acting as **Delegated Architecture Reviewer** under `AGENTS.md` section "Architecture review authority".
- **Independence:** I did not author revision 3/3a, the proposed migration, rehearsal, contract checker, or implementation commits. I previously identified review findings but made no implementation changes to the Grammar design before this verdict.
- **Reviewed PR:** #100.
- **Reviewed implementation/content HEAD:** `b3ee8f09f0bf6da07ca2f042f5aedeeb86db0312` (`codex/work`).
- **Base:** `main` `5045fe74e9bbcb29d6fe0244567c9dacdf9faf2b`.
- **Policy:** `AGENTS.md` architecture-review rules and `docs/project/REVIEW_POLICY.md`.
- **Files inspected for the gate:** the complete 11-file PR diff: `CURRENT_HANDOFF.md`, `UI_BACKEND_GAPS.md`, `GRAMMAR_CONTENT_STORE.md`, `GRAMMAR_CONTENT_STORE.REHEARSAL.md`, `GRAMMAR_CONTENT_STORE.REV3_REVIEW_REQUEST.md`, this review file, proposed migration `20261008_0030_grammar_content_store.py`, `migrations/proposed/README.md`, the contract checker, PostgreSQL rehearsal script, and migration tests.
- **Execution/evidence:** I did not rerun the PostgreSQL rehearsal or local suite. I inspected their recorded evidence and code. GitHub Actions CI #310 succeeded on the immediately preceding Grammar-equivalent head `e1a8f51e`; the only delta `e1a8f51e -> b3ee8f09` removes an unrelated 11-line release-record diff and corrects the proposal summary from 59 PASS to 66 PASS, with no architecture/migration/script/test change. The author also reports project-memory/architecture validators exit 0 and 12 Grammar migration tests pass locally. CI #311 for `b3ee8f09` was still running when this verdict was recorded, so merge readiness remains conditional on that CI completing successfully; architecture approval itself does not depend on a new code path because the cleanup delta is documentation-only.

## Verdict: **APPROVE**

Revision 3a is approved at the architecture/migration-gate level. The prior P1 scope blocker is resolved: PR #100 is back to a Grammar-only 11-file diff, and the unrelated staging/deployment/auth/agent/runtime work is no longer part of this PR. The stale rehearsal summary is also corrected to **66 PASS, 0 FAIL**.

No P0 or P1 finding remains in the reviewed Grammar architecture.

## Findings closed

1. **Contract-check dependency false PASS — CLOSED.** Missing `jsonschema` or PyYAML now produces FAIL/NOT RUN and non-zero exit; unexecuted contract validation cannot contribute a PASS.
2. **Rollback of a superseded version — CLOSED.** `review_status` is the review verdict (`imported | accepted | rejected`); `superseded_at` is serving state. A previously accepted version remains eligible for rollback publish through the normal rights/publish gate.
3. **Synthetic rehearsal outside export-profile/1 — CLOSED.** Stored synthetic bodies are validated against the pinned export profile before import, and a negative control demonstrates that the removed non-contract `rehearsal_marker` is rejected.
4. **Scope contamination — CLOSED.** The current PR diff contains only Grammar gate/project-state files. Runtime/deployment/auth/agent/listening/staging changes are no longer in #100.
5. **Evidence summary drift — CLOSED.** The proposal now states 66 PASS, 0 FAIL, matching the current rehearsal record.

## Architecture decisions approved

- **R3-1 `source_dirty`:** reject dirty-tree packages.
- **R3-2 served body:** whitelist export-profile top-level keys minus internal/non-served provenance such as `source_refs`.
- **R3-3 DB invariants:** keep immutable version content, append-only review events, publish gate, published projection, id/language agreement, and one resolution per R5 id.
- **R3-4 function labels:** the stricter app-side requirement is safe for the current 43 labels; align the upstream exporter/contract before relying on it for future package evolution.
- **R3-5 promotion order:** migration `0030` may be promoted while its parent remains `20261007_0029`; if another proposed migration is promoted first and `0030` must be re-parented, the changed migration requires fresh chain/downgrade rehearsal and review evidence.
- **R3-6 runtime:** applying a migration to a persistent runtime remains a separate human-authorized operational act.
- **R3-7 rollback model:** review verdict and serving supersession remain separate so rollback does not erase prior acceptance.

## Non-blocking conditions carried forward

- Before the first real/future package relies on the stricter function-label boundary, align the Grammar Lab exporter/contract so the producer and importer require the same locale set.
- Any re-parenting of `0030` invalidates the current exact-chain rehearsal and must be re-rehearsed.
- Promotion of the migration into `migrations/versions/`, Store/API implementation, and any runtime apply remain separate actions. This architecture approval does **not** authorize applying a migration to `:8000`, `:8021`, or any persistent database.
- Learner UI integration is not part of this gate. The existing Grammar screens should remain unchanged until the backend/API seam is ready and the human explicitly proceeds with UI integration.

## Gate state

- Independent architecture review: **APPROVED**.
- Grammar architecture core: **no P0/P1 remaining**.
- PR scope: **clean** for the Grammar architecture/migration gate.
- Migration parent at reviewed head: `20261007_0029`.
- Migration promotion/code implementation: may proceed only under the human's next-step authorization and repository migration policy.
- Runtime apply/deploy: **not authorized by this review**.
- Learner UI changes: **not authorized by this review**.

This review records the verdict on implementation/content head `b3ee8f09`. The commit that writes this review file changes only the review record itself and does not alter the architecture, migration, scripts, or tests under review.
