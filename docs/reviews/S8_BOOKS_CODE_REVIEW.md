# S8 Books Corrections Code Review

**Verdict: APPROVE.** No unresolved P0 or P1 finding remains in the bounded
diff. One non-blocking P2 counting edge case is recorded below. This is a
read-only code review and makes no runtime, browser, or test-pass claim.

**Reviewer:** `/root/review_progress` (independent code reviewer)  
**Branch:** `codex/work`  
**Base:** `af9f8bb5d2cbea7ed6986211ad864798c2f6241a`  
**Reviewed commit:** `b7380b1e2c83a06e35343f5ec6e26704c922f63d`
**Reviewed diff:** `af9f8bb5d2cbea7ed6986211ad864798c2f6241a..b7380b1e2c83a06e35343f5ec6e26704c922f63d`, inspected 2026-10-02. The committed five implementation/test files match the previously reviewed diff. The only implementation change since that review is extracting the title/author normalization lambda into `_metadata_identity`; the verdict and P2 finding are unchanged.

## Strengths

- Chapter word counts now count Han ideographs individually and keep
  whitespace-separated non-Han units, covering Chinese paragraphs and mixed
  English/Chinese text without changing ordinary English counts.
- Marked `pg-boilerplate` subtrees are removed from the reader projection
  before both chapter creation and link-ratio classification. The source EPUB
  bytes and rights metadata are not rewritten. The broad “license mentioned
  anywhere” exclusion is replaced by a narrow standalone-heading check, so a
  story mentioning the license is retained and an ordinary last chapter is not
  discarded merely because publisher boilerplate follows it.
- Short title pages are matched against the EPUB's own title and author
  metadata rather than a chapter-title dictionary.
- The Admin book address now uses the learner route's `book:<bookId>:<chapterId>`
  shape. The gate assertion feeds the generated address through the real
  `parseContentId` implementation and checks the parsed book and chapter IDs.

## Findings

### P0 / Critical

None.

### P1 / Important

None.

### P2 / Minor

1. **Supplementary Han ideographs are outside the count range.**
   `writing_coach/epub_import.py:90` counts Han ranges through the BMP but does
   not include supplementary CJK ideographs such as Extension B (`U+20000` and
   above). A run of those rare characters is treated as one whitespace token,
   so some classical or historical Chinese text can still be undercounted.
   Consider covering the supplementary Han ranges and adding a focused test.
   This is a narrow edge case and does not block the stated EN/ZH correction.

## Scope and verification

Inspected files:

- `writing_coach/epub_import.py`
- `tests/test_epub_import.py`
- `tests/test_epub_import_zh_word_count.py` (untracked at review time)
- `static/orena/capabilities/admin-reading.js`
- `scripts/test_orena_screen_admin_areas.mjs`
- Relevant consumers and route contract: `writing_coach/reading_library_api.py`,
  `static/orena/screens/content/model.js`, and
  `static/orena/capabilities/admin-content.js`.
- Governance/spec context: `docs/project/PROJECT_MEMORY.md`,
  `docs/project/REVIEW_POLICY.md`, `docs/project/DESIGN_CONTRACT.md`,
  `docs/product/ORENA_PRODUCT_CONSTITUTION.md`,
  `docs/product/ORENA_CONTENT_ARCHITECTURE.md`,
  `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`, and the Admin design
  authority in `docs/design/canonical-ui/screens/Orena-Admin.dc.html` plus
  `docs/design/canonical-ui/brief/ORENA_ADMIN_DESIGN_SPEC.md`.

I executed no tests, validators, browser sessions, Docker commands, or runtime
operations. The changed tests were read but not run. No behavior is claimed as
browser-verified here.

## Governance and repository evidence

- **Persistence/schema:** no schema or migration changes in the scoped diff;
  the import projection changes only. Original EPUB/rights preservation is
  retained.
- **Protected areas:** no named protected shared learner layout, design-system,
  Grammar, or canonical media contracts changed. The Admin capability change is
  within the scoped Platform Admin work.
- **Version/deployment/production:** no version, deployment, or production
  operation in the scoped diff.
- **`PROJECT_STATE.md`:** unchanged in observed status.
- **`CURRENT_HANDOFF.md`:** unchanged in observed status.
- **Decision Log:** unchanged in observed status.
- **Concurrent excluded work:** dirty media backend files and their tests were
  not inspected or judged. `docs/project/PROJECT_MEMORY.md` and
  `docs/reviews/evidence/s8-books-2026-10-02/` were outside this review scope.

Exact `git status --short` observed after this review-record update:

```text
 M docs/project/PROJECT_MEMORY.md
 M docs/reviews/S8_BOOKS_CODE_REVIEW.md
 M writing_coach/media_library_store.py
?? docs/reviews/evidence/s8-books-2026-10-02/
?? writing_coach/media_segmentation.py
?? writing_coach/media_spend.py
?? writing_coach/media_transcript_pipeline.py
```

## Declined to judge

- EPUB reimport effects on existing runtime records: outside the bounded code
  diff and not runtime-tested.
- Admin visual fidelity and interactive link behavior in a live browser:
  expressly excluded from this review; no browser operation was performed.
- Concurrent EPUB/media backend files beyond `writing_coach/epub_import.py`:
  expressly excluded by the task.
