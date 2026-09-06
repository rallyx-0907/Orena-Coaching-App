# Current Handoff

## Governance

Purpose: compact verified recovery context. Authority: agent updates after
verified evidence under current human direction. Change when ownership, stage,
blockers or the next checkpoint changes. Do not store secrets or unverified
success. Durable product authority is the Product Constitution, Content
Architecture, approved brand, and D-046.

## Current branch / lane

`codex/work` / Orena product-layer reset and experience foundation. Starting
integrated HEAD 5827f6a; prior checkpoint a46351c; this checkpoint completes the
foundation slice. Do not restore deliberately removed learner implementations.

## Last verified batch

Local execution. No CI evidence is claimed.

- `validate_project_memory.py`, `validate_architecture.py`: OK.
- `validate_browser_esm_graph.mjs`: OK, 21 modules.
- CI's eleven `.mjs` gates: pass. Nine further capability gates: pass.
- `pytest -q test_app.py tests`, ephemeral container, sqlite: **753 passed /
  20 failed** — exactly the inherited baseline below, unchanged.
- Browser (Playwright, real viewports 1440 / 800 / 390): every route renders in
  EN and ZH with zero horizontal overflow and zero sub-30px tap targets.

## Browser journeys checked

Explore, Practice (all six intents), Grammar list and detail, Your collection,
Your language, Writing, story/imported-text and media encounters, EN and ZH,
against a real server: Follow synchronisation, Dictation compare/reveal/persist
and its degraded path, Shadowing segment transitions, continuation restore and
routing, unresolvable-import recovery, and dialog focus return. No microphone in
harness, so record/pronunciation/voice paths were not executed.

## DONE

- Human-authorized Constitution / Content Architecture clarification and D-046;
  capability primitives extracted; old web product tree and seven obsolete
  specifications physically deleted; no legacy directory.
- Product model: encounter, practice intention, owner-scoped content
  relationships/continuation/drafts, adapters to existing evidence APIs. Explore,
  Practice, collections, Follow, contextual Dictation/voice, expression,
  saved-language/recall and grammar surfaces coded.
- Learner-imported media is durable content and reaches every Practice intent
  beside the curated catalog (Constitution §30, Content Architecture §3).
- Authored grammar notes joined onto the catalog by stable Concept ID, labelled
  generated, EN/ZH at parity.
- **Learner evidence survives a failed read.** The server replaces a listening
  record wholesale; practice that began without the stored copy now folds into
  it via `mergeListeningEvidence`, never lowering a stored best score, and says
  so on screen. Verified live: read blocked at open → notice, no write; back
  online at save → attempts summed, best preserved.
- Truthful degraded states: demo scores labelled, unmeasured scores named,
  meaning-recovery failure distinguished from "no meaning yet", an empty writing
  review says so, a saved recall grade whose refresh fails is not reported as
  lost, Grammar has an empty state, and the waiting room no longer calls a
  catalog lesson an import.
- Practice lifecycle: take actions wired before the progress save is awaited,
  stale takes cannot overwrite fresher feedback, a live microphone disables the
  controls it would otherwise silently swallow, and a speech transcript no
  longer overwrites writing the learner already has.
- Navigation and interaction: "Skip to content" no longer rewrites the route
  back to Discover, re-entering the current route acts, dead routes offer a way
  out, play/pause announces its actual action, the seek handle is not fought by
  the clock mid-drag, and narrow tap targets reach 44px with no new visual
  system.

## IN PROGRESS

Nothing. This slice is complete and reviewable.

## PENDING

Microphone paths (record, pronunciation, voice feedback) need one manual pass
with a real microphone; their guards are covered by source contracts in
`scripts/test_orena_product.mjs`, not by execution.

## NEXT EXACT TASK

1. Human/Astra review of this checkpoint before any new milestone.
2. Native is frozen. Do not change, test, restore or extend native code.
3. Resolve the two OPEN P1 decisions; only then migrate or retire the gates
   blocked behind them.
4. One manual microphone pass over Shadowing and Speaking.

## Runtime / safety

Isolated `orena-foundation-web` on 127.0.0.1:8011, with its own postgres and
network. Database is temporary; no production volumes or credentials. Mount is
this workspace, read only. Production on 8000 and preview on 8010 were not
operated. No provider activation, deployment, migration or data mutation.
Browser state seeded during acceptance was cleared afterwards. No AI provider is
activated here, so writing review answers 503 and shows its truthful unavailable
state; pronunciation may return demo values, which the UI labels. The favicon
404s - no brand icon is wired into the shell.

Dependency-heavy tests ran through `docker run --rm`, not Compose, so no shared
lane was touched. A read-only mount cannot start the app, which creates `data/`;
point `WRITING_DB`, `AUTH_DB`, `PLATFORM_DB`, `PRODUCT_DB` at `--tmpfs
/rundata:rw` alongside the environment CLAUDE.md documents. The active learning
language is session-scoped (cookie), so switch it from inside the page.

## BLOCKED

No tool blocker.

## OPEN P0

None identified.

## OPEN P1

**Platform Admin is unreachable; the decision is the human's.** `b28254e`
deleted `templates/index.html`, the old learner shell and the only host for the
operator dashboard. `static/admin.js` and every `/api/admin/*` route still
exist, but `admin.js` bails at its `#page-admin` guard on every page, so it is
inert, not merely unrouted. AGENTS.md §12 protects production infrastructure,
so whether Orena keeps that page, and where, is a product call.

**Grammar breadth.** The list shows only the three authored patterns per
language in `content/patterns.js`. If that is curation it is done; if it is an
unfinished authoring pass, the remaining Concept IDs still need notes.

Non-CI gates left deliberately failing as evidence — do not delete them to make
a suite green. Blocked on Platform Admin: `test_product_activity_contract.mjs`
and `test_r17_readiness_contract.mjs` (read the deleted template);
`test_r13_admin_capability_matrix.mjs`, `test_r17_admin_retention.mjs` and
`test_r17_readiness_summary.mjs` (drive `admin.js`, which bails); and the r13
and r14 release matrices downstream. Blocked on the native freeze: r20. The r8,
r10 and r11 release matrices need scripts the reset deleted and do describe
removed learner surfaces, but `test_governance_contract.py` and the Decision Log
reference them, so retiring them is its own governance decision. None are in CI.

## HUMAN GATES

Production operations, data, credentials, paid providers, migrations, release,
billing, OAuth/DNS/Cloudflare, destructive history and store publishing remain
gated. Ordinary local reset and recovery commits are authorized.

## Baseline test evidence

Before reset, the full Python run and pristine starting HEAD both produced
753 passed / the same 20 failed governance or source-format assertions. Those
are inherited; do not weaken assertions to hide them. The tree is still at
exactly that baseline, all twenty in `test_governance_contract.py`,
`test_media_ingestion.py`, `test_media_learning.py`. The earlier formatting pass
broke one source-shape assertion, now matched by pattern; expect others to break
the same way if that pass is finished.

## Current scope update

Human froze native mobile / Expo / React Native on 2026-09-06. Continue on WEB
only; do not undo completed work.

## Working-tree note

`static/orena/{app,content,product,ui}`, `world.css` and the shell template were
reformatted by a Prettier-style pass; `capabilities/` and `infrastructure/` were
not, so the tree is mixed. Decide whether to finish or revert that pass.
