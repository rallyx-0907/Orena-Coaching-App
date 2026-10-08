# S2 Media / Listening Basic Code Review

## Reported correction review — 2026-10-02

Reviewer: independent Codex `/root/review_media_basic`, code-review role.
Reviewed base: `4742bef2e1fc4bcb5c14116fe8cbc56ed034b8db` plus the scoped working diff checkpointed in CURRENT_PRODUCT_STATE.yaml.
Scope: media reuse/deletion scope, support-language cache and partial batches, real word timing, player chrome, loading/copy, dictionary-first Quick Sheet, stroke direction, wrapping, and final encountered-word audio delta.
Initial P1 joined-cache deletion race was corrected and covered by a regression test; P2 freshness was bounded to five minutes. Final verdict: no actionable P0/P1/P2 in scope, including the subsequent pronunciation delta. Derived audio keys do not create learner or catalogue authority; Chinese lookup requires an explicit reading. Future reference-audio cache quota is non-blocking follow-up, not this basic slice.
Reviewer ran no Docker/tests/browser; implementer evidence is in S2_MEDIA_BASIC_BROWSER_CHECKPOINT.md. This is independent code review, not human product approval or public-readiness approval. Historical reviews follow.

**Verdict: APPROVE — code review scope.**

**Reviewer:** independent Codex reviewer (`/root/review_media_basic`)
**Reviewed base:** `933377473ac84bbe7f8372431fcb13e1c40eef4d`
**Reviewed subject:** `c315bd2e0b72e86501a2bcd85afe00bfe5c0e2b2` on `codex/work`, containing the reviewed Media/Listening diff after the ownership, publication, and archive/reprocess corrections.
**Scope:** normal browser-usable Media/Listening paths for EN and ZH; ownership and deletion, transcript admission, rights, spending caps, publication state, and shared/personal access. This is not a fidelity or release-readiness verdict.

## Findings

No unresolved P0 or P1 code-review findings remain in the reviewed scope.

The reviewed flow uses provider captions first, then ASR fallback, and only publishes shared media after deterministic transcript validation and cleared rights. Unknown rights and unusable transcripts remain held. Personal stored media is owner- and language-scoped; direct media imports are stored under the owner-managed asset path, and owned YouTube references are removed through the media deletion enumeration. Shared learner reads require published status. Processing completion uses atomic update-if-present writes so deletion cannot be undone by an in-flight job, and archive cancellation prevents stale processing from republishing content. Admin publication rechecks transcript validity and rights.

## Non-blocking follow-up

- The Admin UI does not yet expose a source-specific rights decision for uploaded files. Those imports remain in review unless a configured source policy clears them; this is safe and truthful, and can be handled in the next Admin content-control slice.
- A learner whose private transcript job fails can refresh its status or re-import the source. The current UI does not offer an owner-scoped retry of the same private media record.

## Validation boundary

The reviewer ran no tests, Docker commands, or browser sessions. The implementation owner reports final local evidence for the reviewed commit: pytest `2738 passed, 370 skipped`; ESM graph `331` passed; Ruff on the Media files passed. The Node gates reported `122/123`, with the remaining failure identified as the inherited Word date assertion. These are local results, not CI evidence. Browser evidence was present under `docs/reviews/evidence/s2-media-basic-2026-10-02/`; it was not used as a substitute for direct browser verification by this reviewer.

The implementation owner remains responsible for recording final gate output, runtime/provider limitations, exact Git status, and any milestone browser evidence in the completion report.

## Support meaning / processing follow-up review (2026-10-02)

Independent reviewer: `/root/review_media_basic` (code-review role), base `eea4d06`,
scoped working diff checkpointed by the following translation/UI commit.
Reviewed implementation checkpoint: `eb8aa317f16d5cc66f4d87271d35d2d829050056`.
Reviewed bounded splitting, protocol inputs, canonical-ID mapping, processing
poll/teardown and truthful EN/VI/ZH resource notices. Initial P1 inaccurate paid
claim and P2 paid translation-stage copy were corrected and re-reviewed.
Final verdict: no remaining P0/P1/P2 in scope. Reviewer ran no Docker or browser
operations; runtime and local gate evidence remain the implementer's observations.
