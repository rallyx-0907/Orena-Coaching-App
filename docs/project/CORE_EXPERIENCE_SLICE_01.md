# Core learner experience — shared text exploration

STATUS: REVIEWABLE. Base: 728a8dfa197ae86ed04596c2bde3f00d5cb54a4e.
Lane: codex/core-encounter, isolated worktree created by explicit human direction.
No merge, persistence activation or human product approval.

## Baseline and slice

Canonical Media Learning payloads, transcript timeline, word timing, acquisition
and translation already exist. Listening already composes annotatedLine, shared
understanding, optional Pinyin and real word spans. Reading uses the same Encounter
route but previously showed plain paragraphs and selection-based explanation.
Speaking consumes shared media/voice primitives; no separate engine was added.

This slice extracts annotation request/cache/pending/stale-result handling into
product/annotation-session.js and consumes it from both media Follow and Reading.
ui/text-lens.js composes the existing annotatedLine renderer, language service and
openUnderstanding. Reading has an explicit Look closer control before the passage,
POS legend, loading/unavailable text and source-bound token interaction. Turning
the lens off returns original text. Comprehension clears the lens before marking
its evidence so late annotation completion cannot erase that highlight.

Token text/offsets, POS and Pinyin come from the existing annotation endpoint;
invalid/mismatched data falls back to original text. No meaning or pronunciation
quality is inferred. Explanation remains provider-dependent and unavailable is
truthful. No score, saved language or provenance write is introduced.

Timing: renderer preserves supplied word spans for media; segment-only playback
keeps its existing segment focus; untimed Reading emits no data-word spans and
has no playback clock. Subtitle acquisition/progress, translation, media selection
and Speaking remain existing implementations, not newly verified provider jobs.

## Fresh local evidence

- Six Node gates passed: annotation_session, close_look, word_follow, reading,
  pure_listening and understanding. No failures in these gates.
- Browser ESM graph: 53 modules linked.
- Playwright browser gate passed EN/ZH on the actual Encounter route, using
  real sandbox annotation APIs: tokens, supplied ZH Pinyin, selected-token context
  in shared explanation, untimed rendering, toggle off, no browser exceptions,
  no horizontal overflow at 390/1440/1920. Six full-page screenshots captured in
  the session's temporary evidence directory; ZH narrow screenshot visually inspected.
- Existing preference optimistic conflict was encountered. Test follows its visible
  refresh/reapply flow; no I1 change was made.
- No fresh full Python, microphone, paid-provider, live subtitle-generation,
  all-theme or full Golden Star acceptance claim. The browser run used Paper.

Browser command: `node scripts/test_orena_text_lens_browser.mjs`, with explicit
ORENA_PREVIEW_URL, optional ORENA_PLAYWRIGHT_MODULE / ORENA_BROWSER_EXECUTABLE,
and ORENA_BROWSER_EVIDENCE. Playwright installed outside the repository.

Preview: http://127.0.0.1:8012/#/encounter?id=story%3Afamiliar-street
Choose EN/ZH in Your Orena, reopen the story and press Look closer.
Session-local preview proxy serves this worktree's /orena-assets frontend and
uses existing localhost:8011 sandbox APIs; no Docker restart or volume operation.
Preview helper: temporary orena-core-preview.py. It is development tooling,
not a deployed product server; backend availability is still required.

## Changed files and reserved ownership

Changed: .github/workflows/ci.yml; static/orena/product/annotation-session.js;
static/orena/ui/text-lens.js; static/orena/ui/encounter.js; static/orena/rooms.css;
scripts/test_orena_annotation_session.mjs; scripts/test_orena_text_lens_browser.mjs;
this record; CURRENT_HANDOFF and CURRENT_PRODUCT_STATE lane/task fields.
Shared CSS change deliberately extends existing token styles to Reading; no new
theme tokens, brand files, shell or navigation changes.

Reserved and unchanged: all I2 migrations, account_profile.py, work_contract.py,
incarnation_repository.py, provenance_repository.py, work_repository.py,
mutation_commit.py, PostgreSQL persistence tests, I2 review/governance records,
Collection/My Language persistence and all Opus WIP. Original worktree untouched.
Application/frontend versions unchanged; PROJECT_STATE and Decision Log unchanged.

Next slice: extend the source-focus/selection contract into Speaking's own text
and unify phrase-selection behavior, preserving existing voice evidence and
provider/subtitle truthfulness. Do not implement any I2 persistence mechanism.
