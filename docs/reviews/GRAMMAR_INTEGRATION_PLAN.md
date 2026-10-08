# Grammar integration implementation plan

Goal: clear the approved contract/fixture prerequisites for S5 without exposing
AI drafts as learner lessons. Authority: D-106, D-111.4; Grammar Store revision2.
Assigned lane codex/work, sandbox :8021 only, native frozen.

- [x] Independently review exact PR67/68 heads; integrate only their bounded
  contract and test-fixture changes if no P0/P1, preserving human Design Contract.
- [x] Add regression coverage using all13 upstream draft fixtures through the
  actual Grammar models/feeder. Confirm drafts never become learner content.
- [x] Correct canonical zh-Hans locale/script mapping demonstrated by failing
  tests; retain the existing EN/VI fallback and original content.
- [x] Run Grammar, language, ESM and memory gates; bind independent review to
  the implementation commit. Record precise prerequisite/runtime limits.

Next S5 slice: approved single-version export-profile validation and Store/API,
additive migration rehearsal/review before runtime application. No R5 fallback,
sample promotion, paid generation or automatic migration.
