# EPUB explicit-directory import correction

Date: 2026-10-02. Base: `e04c8c2a4b30f26776e699331a2c32783bcf9c30`.
Code commit: the commit containing this record. Lane: `codex/work`.

MILESTONE=Reported Admin EPUB import failure
STATUS=REVIEWABLE
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/admin/imports/books
HOW_TO_REACH_IT=Admin -> Imports -> Books -> English -> choose EPUB -> Import -> Open
EN_PARITY=Actual reported English EPUB imported and Book detail opened
ZH_PARITY=Same language-neutral parser; Chinese regression fixture passes
CROSS_CAPABILITY_STATUS=Existing Book detail and learner link retained; no Books redesign

## Cause and correction

The reported local The Alchemist EPUB failed reproducibly with
`unsafe_archive_entry: META-INF/`. Explicit directory entries conventionally
end in a slash. The ZIP path validator incorrectly rejected that terminal empty
component. It now permits exactly one terminal separator while continuing to
reject absolute paths, parent traversal, internal empty components and repeated
trailing separators. Archive/XML limits and entity protections are unchanged.

Application files: `writing_coach/epub_import.py`, `tests/test_epub_import.py`.
No frontend, API, schema, ownership, publication policy or version change.

## Evidence

- Regression RED: two EN/ZH valid-directory tests failed, five unsafe-directory
  tests passed, 24 deselected.
- Local GREEN: 59 passed, zero failed/skipped, two dependency deprecation
  warnings across EPUB parser/limits/Chinese counts and Reading Library API.
  Ruff passed. `git diff --check` passed.
- Actual reported file parsed as English, two source chapters, 42,990 words.
  In the browser, Admin Import showed Imported and 1 of 1 imported; Open showed
  The Alchemist / Paulo Coelho, two chapters and 42,990 words with its existing
  learner link. Evidence images: `evidence/epub-directory-fix/imported.png` and
  `book-detail.png`. The user's source file was not modified or committed.
- Independent reviewer `/root/review_media_basic` reviewed the working delta
  against the base above: APPROVE, no actionable security regression. Source
  and tests reviewed; reviewer did not run Docker/tests.

Protected UI areas were not changed. Only sandbox `orena-next-verify-web` was
restarted to load the fix; no other runtime or production deployment was
changed, no persistent volumes deleted. Import wrote the requested book through
the existing repository and durable asset store. This parsing correction does
not establish redistribution rights or whole Books completion.

No P0/P1/P2 remains in this bounded fix. The Admin progress/control-center basic
gaps from S6 remain next. `PROJECT_STATE.md` unchanged; current handoff/status
and machine state record this verified correction. No durable decision changed,
so no Decision Log append is required. Git status is checked after checkpoint.
Local checks are not CI PASS or human product approval.
