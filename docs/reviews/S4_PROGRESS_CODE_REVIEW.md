# S4 Progress and Speaking History Code Review

**Verdict: APPROVE for the reviewed code diff.** No unresolved P0 or P1 code finding remains in this review scope. This verdict does not establish the learner-facing fidelity gate or product approval. S4 remains `IMPLEMENTING`; it is not `REVIEWABLE` based on this review.

- **Reviewer:** `/root/review_progress` (independent code reviewer)
- **Branch:** `codex/work`
- **Base commit:** `50751946c6389bd483718be3584eb7c4a072309f`
- **Reviewed commit:** `a15d3c2d2346051b933ee95a32b3764137d8d01e`

**Reviewed diff:** `50751946c6389bd483718be3584eb7c4a072309f..a15d3c2d2346051b933ee95a32b3764137d8d01e`. The committed 23-file S4 diff matches the implementation and follow-up fixes reviewed in the working tree: account/language isolation, server-verified Speaking facts, source routing, repeated attempts, and truthful unavailable states.

## Review findings

The earlier review findings are resolved in the current diff:

- Speaking history now scopes local retained takes by the existing account/language scope. Attempt History and Speaking Summary use persisted server provenance as the authority for scores. Unmatched or stub-measured local takes remain visible as tasks/attempts without a score.
- Speaking Summary counts each server attempt and deduplicates a tab ledger entry by persisted attempt ID or `takeRef`/server `takeId`, including the case where the follow-up attempt-ID notification was missed. The display marks the bounded server result as `100+` when the response reaches its limit.
- Speaking Summary keeps the hero and actions outside the task-list scroll area. The task list is the only scrollable content in the card, so a long account history does not push the primary actions below the viewport (rule 49). The change reuses the existing frame components; no new visual component was introduced. Visual verification is still pending.
- A failed server-history read reaches an error state instead of presenting a partial history as complete. Writing essay-detail read failures propagate; deleted sources (404/410) may be skipped.
- Progress source lookup uses the active listening catalogue. A failed catalogue read surfaces as an error, and a source that is no longer available is identified in the evidence/history row.
- The Progress time metric has an explicit unavailable state. The active-day chart and the extra story-card activity counts were removed; supported streak and declared level/rank facts remain.

No unresolved P0 or P1 code findings remain. The `weekStrip` mapper is retained only as a tested data helper and does not render a replacement chart. No P2 finding is being raised for it.

## Scope and verification

S4 implementation and gate files reviewed:

- `static/orena/infrastructure/api.js`
- `static/orena/product/speaking-history.js` (new), `speaking-recorder.js`, `speaking-session.js`, `take-store.js`
- `static/orena/shell/context.js`
- `static/orena/screens/attempts/{copy,model,screen}.js`
- `static/orena/screens/errors/{model,screen}.js`
- `static/orena/screens/progress/{copy,model,screen}.js`
- `static/orena/screens/speak-summary/{copy,model,screen}.js`
- `static/orena/screens/speak-summary/speak-summary.css` (bounded task-list scrolling for rule 49)
- `scripts/test_orena_screen_{attempts,errors,progress,speak-summary,speak}.mjs`

The reviewer executed no tests, validators, browser sessions, or Docker/runtime operations. The implementation author reports targeted red-to-green gate checks for the changed behavior; those results were not independently executed or verified here. This review therefore makes no test-pass or CI-pass claim.

The learner-facing fidelity gate remains pending: live source comparison and physical-touch browser checks in the required languages, themes, and viewports have not been verified by this reviewer. Keep the milestone `IMPLEMENTING` until that evidence is recorded. The milestone must report the fidelity gate per checked item before it can be called `REVIEWABLE`.

## Repository state and governance evidence

- **Listed protected areas:** none of the named protected areas were changed. This diff changes learner-facing Progress and Speaking History/Summary surfaces.
- **Persistence/runtime:** no schema or migration change. The UI reads existing account/language-scoped server records and namespaces existing local Speaking retention by account/language. No runtime was operated.
- **Application/frontend version:** no version change observed in the reviewed S4 diff.
- **Deployment/production operations:** none performed.
- **`PROJECT_STATE.md`:** unchanged in the observed status.
- **`CURRENT_HANDOFF.md`:** changed in the wider dirty tree.
- **`CURRENT_PRODUCT_STATE.yaml`:** changed in the wider dirty tree.
- **`DECISION_LOG.md`:** changed in the wider dirty tree; this code review did not determine whether that separate update required a new durable decision.
- **Other concurrent work excluded:** the dirty EPUB/media backend files and its test were outside this S4 review scope. Other concurrent project-memory/status edits were not independently reviewed here.

Exact `git status --short` observed while updating this review after the S4 commit:

```text
 M docs/product/ORENA_STATUS.md
 M docs/project/CURRENT_HANDOFF.md
 M docs/project/CURRENT_PRODUCT_STATE.yaml
 M docs/project/DECISION_LOG.md
 M docs/project/PRODUCT_COMPLETION_PLAN.md
M writing_coach/epub_import.py
M writing_coach/media_library_store.py
?? docs/reviews/
?? tests/test_epub_import_zh_word_count.py
?? writing_coach/media_segmentation.py
?? writing_coach/media_spend.py
?? writing_coach/media_transcript_pipeline.py
```
