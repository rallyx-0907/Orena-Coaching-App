# New learner UI: staging to cutover roadmap

**Status: ACCEPTED 2026-09-29 (D-101).** D-101 is the authority. This file tracks its
milestones and holds what planning found; where the two differ, D-101 wins. The first version
of this roadmap (a proposal with H1-H10 open) is replaced in full. `ROADMAP.md` is untouched.

## Goal

One complete staging on :8011 running the latest `codex/work`: the old UI at `/`, the new UI at
`/next`, until the human says "cutover". Every existing skill works with real content: the learner
does the work, it is assessed where the domain defines assessment, the result is stored on the
server, and progress and history survive a reload or a new login. Staging also includes the Admin
needed to load that content, and Orena live. Staging complete is not public release: content
breadth is its own gate (`CONTENT_SCALE_READY`).

## Milestones

| # | Milestone | Status | Done when |
| --- | --- | --- | --- |
| A | Staging scripts: `staging_update.ps1`, `staging_backup.ps1`, a durable DB volume | in progress | the human runs `staging_update` and :8011/next serves `codex/work` at the migration head |
| D2 | P1: shared modules out of `ui/` into `capabilities/` or `kit/`; a gate against `/next` importing `ui/` | planned | the gate is green, both UIs use one module, no behaviour change |
| D3 | The matrix: every skill and flow × content / do / assess / store / come back | planned | sent to the human once |
| D4 | One persistence proposal (H2 included) → independent review → approval → rehearsed migrations | planned | approved and rehearsed; the human runs the migration |
| E | Admin in the new UI, on the pinned `Orena Admin.dc.html`, existing logic and APIs | planned | real content is imported, reviewed and published, and a learner learns with it on `/next`; the three access tests pass |
| F | Grammar frames 44 and 47 on approved Grammar Lab content through Admin | frame built (`b83142d`) | approved points reach both screens by the Admin loop; `pattern_rule` after PR #67 |
| D7 | Every `MISSING` cell in D3, by reuse | planned | no `MISSING` in a non-deferred row |
| G | Orena live on :8011 (`AGENT_LIVE`), contract v5 checks, surface purposes | planned | the v5 checks pass on :8011 |
| H | Cutover, on the human's word | not started | see D-101 H |
| C | Chinese evaluator: targeted re-grade, live benchmark (USD 0.50 cap) | waits for Docker to be free, after D3 | the approach is reported before any change; recall numbers reported |

Deferred until after staging: the eight Coming-soon screens and E1 (H3-H7; their entries are
hidden in `/next`, H9); Admin Overview, Operations, Users and the Practice generator.

## Found while planning (kept for the milestones)

- **D2 scope, found at `a40e64b`.** `capabilities/media-player.js` imports `esc` from
  `ui/html.js`. `capabilities/lexical.js` imports `ui/html.js`, `ui/quick-sheet.js` and
  `ui/reading-room.js`. Listening, Dictation, Shadowing and React use `media-player.js`. The ESM
  graph lists the full set.
- **Admin inventory.** 16 modules in `static/orena/admin/`, opened at `/#/admin` from the old
  `app.js`. They import four `ui/*` helpers and use 61 old CSS variables.
  - APIs: `/api/admin/console/*`, `/api/admin/reading/*`, `/api/admin/ai/*`, product-activity,
    readiness and vocabulary import.
  - Access: `require_admin`.
  - The Practice generator has no backend (new persistence), so it is deferred.
- **Cutover inventory (for H).**
  - Delete: `templates/orena/index.html`, `static/orena/app.js`, the `ui/*.js` modules that
    have replacements, the 18 root Dark Glass stylesheets, `theme.js` and the curled-tail mark.
  - Rewrite: `product/legacy-routes.js`.
  - Keep: `static/admin.js`, `superseded/**` and `docs/visual-references/**`.
  - Redirects: about 30 old addresses, running before the new router's `match()`. `#/practice`
    and `#/progress` exist in both UIs.
  - Gates: domain gates stay; each old-UI gate retires only after its guarantee is ported (lookup
    race, vocabulary paging). Python validators that assert the old UI are rewritten, not
    deleted.
  - Rollback: a tag, three layered commits, one `git revert -m 1`.
- **Coming-soon screens (deferred).** Suggested order: Sound/Tone, Timed Recall, Timed Reaction,
  Retell, Context Rewrite, Timed Writing, Mock Interview, Context Transfer.
  - Five of them share E1, a transient, versioned scoring contract.
  - Effort: about 10-13 sessions.
  - Content sources and persistence are human decisions.
