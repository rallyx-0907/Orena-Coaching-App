# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/work` is the baseline and the UI lane. It is the UI lane (D-066, D-098)
whichever agent works it: a Claude session continues here, not on `claude/<task>`. `feature/orena-intelligence`
builds Agent Intelligence (D-085) against `AGENT_CONTRACT.md` v5 (D-092, D-094,
D-095, D-096), which is edited only on `codex/work`. Verified history:
`PROJECT_STATE.md` "New learner UI migration".

New learner UI (D-088 - D-091): the pinned design is built at `/next` and
replaces the old UI at `/` in one cutover. Between slices `/` is the old UI,
unchanged; `/next` holds the built surfaces; both share one domain layer; no
learner-data schema changes; the agent runs on the contract mock and nothing
calls `/api/agent/*` until the human says the intelligence lane is integrated.
The intelligence lane integrates against `/next`. Frame → route → code →
status: `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

- Foundation: REVIEWABLE.
- Wave A destinations: REVIEWABLE (`f13c542`) - built, reviewed, integrated,
  re-checked in the browser, language layer finished, every API reader checked
  against captured real payloads (`scripts/fixtures/api/`). Reviewable at
  http://127.0.0.1:8021/next (isolated stack) until the 8011 sandbox is migrated.
- Wave B workspaces: REVIEWABLE (`161d917`) - reading (Reader, Check,
  Discussion, Reading Transfer), listening (Workspace, Dictation, Shadowing,
  React, Respond), speaking (Scripted, Compare, Attempts, Summary, Free Talk,
  Conversation, Situation), writing (Writing, Compare Versions), review (Review,
  Feed, From Your Errors), Orena (Home, panel, voice, on the mock), Onboarding
  and the shared overlays. Each is one commit, independently reviewed and fixed.
  Routes with no backend are the design's Coming soon screen
  (IMPLEMENTATION_MAP `coming-soon`). The two Grammar screens wait for the
  contract below.
- Agent UI side: contract v5 on the mock; Orena's entry points hide when the
  agent is absent.
- Grammar: Grammar Lab replaces R5 (D-100; PR #66 merged at `f86a2bf`). The two
  Grammar screens (frames 44 and 47) are being framed on the merged contract and
  connect to data when the lane's 13-point fixture arrives (its PR B); its PR A
  patches the contract and adds the "Try it yourself" rule, and until then the
  card never concludes the pattern was used. `/api/grammar/v1/*` waits for its
  own architecture review.

## Last verified batch

2026-09-29, the D-098 batch (`5d9d64c`..`3f2cc23`), local: every node gate in
ci.yml (114), the browser ESM graph and the memory validator pass; each learner
change was checked in the browser on the isolated stack (en/vi/zh, both themes,
desktop and phone touch; the Settings picker at all four rule-49 sizes). Full
pytest on a clean export of `3f2cc23` (SQLite, CI backend): `2450 passed, 195 skipped`. The isolated stack
mounts the checkout read-only, so a real upload cannot be stored there; the
upload route is covered by `tests/test_media_learner_upload.py` (real WAV,
ffprobe) instead.

Before it: 2026-09-29, `161d917`, local: each Wave B commit was checked on a clean export
of HEAD plus the commit (all CI gate commands - 113 at the last, the browser ESM
graph and the memory/architecture validators pass) and reviewed in the browser
on the isolated stack (en/vi/zh, both themes, the four rule-49 sizes). Full
pytest on a clean export (SQLite, CI backend): `2420 passed, 195 skipped`
(`51522e4`). No CI pass is claimed. Visual-source gate: PINNED.

## DONE

Design pinned and governed (D-088 - D-093); foundation at `/next`; agent
contract v4 (D-095); copy engine fixes; Wave A destinations and Wave B
workspaces (REVIEWABLE); the Writing request minimum per learning language.
D-098 (the human's answers, 2026-09-29): Japanese Writing-minimum row
(`c1393c9`); Writing's countdown while Review is off (`1ac1e6f`); Lesson
complete draws only server-measured numbers (`6a402af`); the empty address
opens Welcome for a learner with no profile (`81ae4bb`, the level half is H2
below); Compare Versions follows the frame (`b221909`); Import > File uploads
audio/video (`2052cb7`); the support-language picker past four (`3f2cc23`).
Wave A review items confirmed in HEAD: theme row `b4373e2`, Today greeting
`755d65b`, word audio 500 `7574765`, essay excerpt `8de1863`. PR #66 was
reviewed on the PR (2026-09-28, three levels); it awaits the human.

## IN PROGRESS

- Human review of Wave A and Wave B.
- Chinese writing evaluator recall: causes and fix options in
  `ZH_WRITING_EVALUATOR_RECALL.md`; no change until the human chooses a fix.
- `UI_COMPLETION_ROADMAP.md` (PROPOSED): Grammar, the eight Coming-soon
  screens, cutover preparation and cutover, Admin, the live Orena panel; its
  decisions H1-H10 wait for the human.

## PENDING

Human: the 8011 sandbox migration (BLOCKED); approval of
`UI_COMPLETION_ROADMAP.md` and its decisions H1-H10 (H1 Grammar Concept frame
23 or 47; H2 storing the declared level for the entry rule); the Chinese
evaluator fix; merging PR #66.

## BLOCKED

- The 8011 sandbox refuses to start: its database (named volume
  `orena-foundation-sandbox-data`, data intact) is at `20260923_0014`, the code
  expects `20260924_0016`. The human authorised 0015/0016 on it; the harness
  blocks the agent, so the human runs them (`scripts/start_orena_sandbox.ps1`
  reports the state).
- Every other shared runtime's Reading migration needs explicit human
  authorization.

## OPEN P0

None.

## OPEN P1

See `ORENA_STATUS.md` and `UI_BACKEND_GAPS.md` section N.

## HUMAN GATES

Web is active; native mobile is frozen. PostgreSQL is the authoritative
runtime, SQLite only an isolated test or frozen rollback/archive backend.
Production, preview, provider credentials, OAuth/DNS/Cloudflare, billing,
deployment, destructive lifecycle, and new learner-owned persistence remain
human gates. Never touch persistent volumes as cleanup.

## NEXT EXACT TASK

UI lane: wait for the human's decision on `UI_COMPLETION_ROADMAP.md`, then follow
its approved order: the two Grammar screens after PR #66 is merged and the R5 →
Grammar Lab decision is recorded; the Coming-soon screens; cutover preparation
(the new UI's indirect imports of old `ui/`, Admin's host, the map's routes);
then the cutover (tombstones, legacy redirects, the old UI and its gates
replaced).
Once every §6.1 surface is built: a one-line purpose per surface id in the copy
layer (interface, en/vi/zh), published for the intelligence lane (contract v5
§6.2).

Intelligence lane: D-085 against `AGENT_CONTRACT.md` v5; merging `codex/work`
forward brings the version bump its contract test checks, the `address` note
and `context.address`, the S5/S2 wording and `copy/surfaces.json` (§6.2).

## Grammar Lab (merged from `feature/grammar-lab`)

Phase 0 of `docs/grammar_lab/SPEC.md`: an isolated, offline, file-based content
pipeline in `grammar_lab/` (own `pyproject.toml`, own tests) and
`docs/grammar_lab/`. It does not import app code, the app does not import it,
and app CI does not collect its tests; no app code, router, engine, migration or
runtime is involved. NEXT: human review of `docs/grammar_lab/PHASE0_DECISIONS.md`
(including how lab point IDs join the R5 Concept IDs, SPEC §8); phase 1 waits.
