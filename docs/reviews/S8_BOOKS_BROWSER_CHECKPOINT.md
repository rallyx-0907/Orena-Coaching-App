# S8a Books browser checkpoint — 2026-10-02

MILESTONE=S8a Books corrections; STATUS=IMPLEMENTING (full Books gate remains open).
COMMIT=b7380b1e2c83a06e35343f5ec6e26704c922f63d
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/discover → book Content → Reader; Admin → Imports → Books.
HOW_TO_REACH_IT=Import an EPUB in Admin, open its learner address, or select the book in Discover and Start reading.

This is execution evidence, not another product authority. ROADMAP owns the
current program. Governance reconciliation is committed in
af9f8bb5d2cbea7ed6986211ad864798c2f6241a; D-113 explicitly supersedes the old
R21/mobile-first and individual-skill release sequence without rewriting history.

## Actual journeys

- Retried the browser upload after the extension reconnected: real Alice and
  Chinese EPUB3 imports succeeded through Admin's file chooser and Import action.
  Earlier, while upload was blocked, an API diagnostic imported the older Chinese
  EPUB; that diagnostic is not represented as UI completion.
- Admin's previous learner book link reached a missing lesson. Correcting its
  chapter separator to the actual `book:<book>:<chapter>` contract made the live
  Admin → Content → Reader journey work after reload.
- English: opened Alice's first story chapter, looked up and saved `beginning`,
  selected a sentence and added “Alice is bored before the unexpected journey
  begins.” Reload restored the note. A subsequent normal web/worker restart
  preserved it on desktop and a fresh 390×844 browser tab.
- Chinese: selected Chinese through Profile/Settings, discovered 幼學瓊林,
  saved the book, entered Reader, opened `混沌`, saw actual pinyin and Vietnamese
  dictionary meaning, and saved it. After restart and reload the word sheet's
  accessible button remained **Unsave word**. The book remained saved.
- Desktop was 1910×855; phone viewport was 390×844, with the Reader occupying
  the viewport. These are browser viewport checks, not a physical-device claim.
  Temporary viewport overrides were reset afterward.

Evidence:

- [English note, desktop after restart](evidence/s8-books-2026-10-02/en-note-desktop-after-restart.jpg)
- [English note, phone after restart](evidence/s8-books-2026-10-02/en-note-phone-after-restart.jpg)
- [Chinese saved word, phone after restart](evidence/s8-books-2026-10-02/zh-word-phone-after-restart.jpg)

EN_PARITY=Real English import/reader/word-save/note/reload/restart paths exercised.
ZH_PARITY=Real Chinese import/discovery/reader/pinyin/dictionary/book-save/word-save/restart paths exercised.
CROSS_CAPABILITY_STATUS=Reader saves real vocabulary state; complete Library/Recall transfer and account/device continuity remain open.

## Changes and validation

Implementation/test files in b7380b1:

- `writing_coach/epub_import.py`
- `tests/test_epub_import.py`
- `tests/test_epub_import_zh_word_count.py`
- `static/orena/capabilities/admin-reading.js`
- `scripts/test_orena_screen_admin_areas.mjs`
- Review record: `docs/reviews/S8_BOOKS_CODE_REVIEW.md`.

The importer now counts ordinary Han text appropriately, strips publisher-marked
Gutenberg boilerplate from the reader projection, keeps the final story chapter,
and excludes short metadata-matching title pages. Original EPUB bytes and rights
metadata are retained. The actual Admin URL is tested through the learner parser.

Local execution, not CI:

- Focused EPUB/API/projection tests: **64 passed**, 2 warnings.
- Canonical Python suite: **2726 passed, 370 skipped**, 19 warnings; exit 0.
- CI-listed bare Node gates: **122 passed, 1 failed**. The failure is the inherited
  Word Detail date fixture at `scripts/test_orena_screen_word.mjs:110`, previously
  reproduced on the clean baseline in S4; its dated expectation is now due today.
  No validator or Word behavior was weakened.
- Browser ESM graph: **331 modules linked**, PASS.
- Relevant Admin areas, Content, Reader and Quick Sheet gates: PASS.
- Ruff on the three touched Python files, with no cache: PASS.
- Project-memory/architecture validators and diff hygiene: checked at checkpoint.

Independent code review: APPROVE, no P0/P1; non-blocking P2 supplementary Han
counting is recorded in the linked review. No schema/migration or new persistence
authority was introduced. PostgreSQL remains authoritative. Only sandbox :8021
web/worker were normally restarted; the durable shared volume was not removed.
No production/deployment activation or application/frontend version change.
Protected shared UI/layout/Grammar/Media contracts were not changed.

## Limits and next work

Full Books is **not complete**. Real authenticated second-device continuity,
complete Library/Recall transfers, light-theme and physical-touch checks, and
measured full canonical fidelity remain open. The English contextual gloss was
truthfully unavailable where not prepared; that is a visible capability gap.

Final parser validation retains Alice's 12 story chapters and Chinese book's
17,841 reading units without a license chapter. The English browser record was
imported before the title-page correction and still has 13 sections; existing
imports are not silently migrated. Older lost/bad QA records and intermediate
catalogue pollution still require a recoverable Admin archive pass.

Sources were Project Gutenberg [Alice](https://www.gutenberg.org/ebooks/11)
and [幼學瓊林](https://www.gutenberg.org/ebooks/52269), labelled public domain in
the USA. This is sandbox QA content, not a worldwide-rights or level-validation
claim. Existing sandbox EPUB publishing and Admin review wording still need
alignment with the accepted rights/quality lifecycle before public readiness.
Classical Chinese content does not establish modern level-appropriate breadth.

Finish the Books continuity/fidelity gap, then transcript-backed Media/Listening.
S4 Progress full fidelity remains open. The entire canonical UI inventory,
Intelligence/Agent evidence-grounding, Grammar EN/ZH runtime, Admin control center
and substantial validated EN/ZH library remain in the Product Completion program.
Missing design connector access is not itself a fidelity blocker: the permitted
full pinned canonical source can be read locally, as clarified in the S4 report.

WHAT_THE_HUMAN_SHOULD_REVIEW=Admin book handoff; EN sentence note after restart;
ZH word sheet/save after restart. These corrections are browser-visible; full
Books and public Product Completion have not been declared REVIEWABLE/APPROVED.

Memory transaction: PROJECT_STATE.md unchanged; CURRENT_HANDOFF.md and current
state/status updated. D-113 was required for the human-directed governance
supersession; no new durable architecture decision was required for these fixes.
Unfinished media files remain excluded and preserved. Final checkpoint status
retains only their existing dirty work after the scoped documentation commit.
