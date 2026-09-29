# New learner UI: staging to cutover roadmap

**Status: ACCEPTED 2026-09-29 (D-101, amended by D-102).** D-101 and D-102 are the authority. This file tracks its
milestones and holds what planning found; where the two differ, D-101 wins. The first version
of this roadmap (a proposal with H1-H10 open) is replaced in full. `ROADMAP.md` is untouched.

## Goal (D-102)

Finish the whole product on `codex/work`, QA it on the lane runtime (:8021 or another local port,
real backend, PostgreSQL where persistence is the acceptance), then one integration pass and a PR
`codex/work` -> `main`. After the human merges it, :8000 (the main runtime, its own auth and
configuration) is updated from `main`, migrations under the human's gate. `/` and :8000 are not
touched before that. Progress is counted in finished product flows. Staging complete is not public
release: content breadth is its own gate (`CONTENT_SCALE_READY`).

## Milestones

| # | Milestone | Status | Done when |
| --- | --- | --- | --- |
| A | Staging scripts `staging_update.ps1`, `staging_backup.ps1` (kept) | TOOLING_READY / DEPLOYMENT_DEFERRED (`788a54e`, D-102) | :8011 only if the human asks |
| D2 | P1: shared modules out of `ui/` into `capabilities/` or `kit/`; a gate against `/next` importing `ui/` | done: the new UI reached one `ui/` module (`ui/html.js` `esc`, via `capabilities/media-player.js`); both UIs now use `kit/html.js`'s; `test_orena_shell.mjs` walks `main.js`'s graph and fails on any `ui/` import. `capabilities/lexical.js` still imports `ui/` but `/next` does not load it: its reuse is a D3/D7 question | the gate is green, both UIs use one module, no behaviour change |
| D3 | The matrix: every skill and flow × content / do / assess / store / come back | done: `D3_PRODUCT_MATRIX.md` (no skill complete; D4, E and D7 inputs listed; six decisions asked) | sent to the human once |
| D4 | One persistence proposal (H2 included) → independent review → approval → rehearsed migrations | in progress | approved and rehearsed; the human runs the migration |
| E | Admin in the new UI, on the pinned `Orena Admin.dc.html`, existing logic and APIs | planned | real content is imported, reviewed and published, and a learner learns with it on `/next`; the three access tests pass |
| F | Grammar frames 44 and 47 on approved Grammar Lab content through Admin | frame built (`b83142d`) | approved points reach both screens by the Admin loop; `pattern_rule` after PR #67 |
| D7 | Every `MISSING` cell in D3, by reuse | planned | no `MISSING` in a non-deferred row |
| G | Orena Intelligence live (`AGENT_LIVE`), contract v5 checks, surface purposes | planned | the v5 checks pass on the lane runtime |
| QA | Integration QA on the HEAD of `codex/work`, EN and ZH, every non-deferred flow | planned | D3 has no `MISSING`; reload/new-session evidence recorded |
| PR | `codex/work` -> `main` | planned | the human reviews and merges; then :8000 is updated with migrations under the human's gate |
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
