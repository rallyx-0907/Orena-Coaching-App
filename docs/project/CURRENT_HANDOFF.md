# Current Handoff

## Governance

Purpose: compact verified recovery context. Authority: agent updates after
verified evidence under current human direction. Change when ownership, stage,
blockers or the next checkpoint changes. Do not store secrets or unverified success.

Current execution state on `codex/work`; durable product authority is the
Product Constitution, Content Architecture, approved brand, and D-046.

## Current branch / lane

`codex/work` / Orena product-layer reset and experience foundation.
Starting integrated HEAD: 5827f6a1c72213aa41c2d4ba2c684711aec24ee6.
Current HEAD: b28254e, plus the working tree described below.
Do not restore deliberately removed learner implementations. Git is the archive.

## Last verified batch

Local execution on the working tree over b28254e. No CI evidence is claimed.

- `validate_project_memory.py`, `validate_architecture.py`: OK.
- `validate_browser_esm_graph.mjs`: OK, 21 modules (`content/patterns.js` linked).
- The eleven `.mjs` scripts CI now runs: all pass on the host.
- `pytest -q test_app.py tests`, ephemeral container, sqlite: **753 passed /
  20 failed** — exactly the inherited baseline below.
- Browser at `http://127.0.0.1:8011/`: Explore, every Practice intent, Grammar
  list and pattern detail render in EN and ZH; a ZH media encounter shows
  synchronized original text, contextual Pinyin and Vietnamese meaning, all six
  rates, and opens Shadowing. No console errors.

## DONE

- Human-authorized Constitution / Content Architecture clarification and D-046.
- Independent extraction: Dictation comparison/alignment, transcript timeline,
  media player, recorder, speech comparison, grammar pedagogy, API adapter.
- Old web product tree and seven obsolete product specifications physically
  deleted; no legacy directory.
- New web product model: encounter, practice intention, owner-scoped content
  relationships/continuation/drafts, adapters to existing evidence APIs.
- New Explore, Practice, collections, Follow, contextual Dictation/voice,
  expression, saved-language/recall and grammar surfaces coded.
- Learner-imported media is durable content: `memory.addMedia` records a `url:`
  encounter under owner and language, and imported media now appears on Explore,
  Your collection and every Practice intent beside the curated catalog
  (Constitution §30, Content Architecture §3).
- Authored grammar notes (`static/orena/content/patterns.js`) joined onto the
  canonical catalog by stable Concept ID, labelled generated, EN/ZH at parity.
- Truthful evaluation: `evaluator === 'fallback-demo'` and
  `score_kind === 'synthetic_demo'` read as demonstration values; an absent
  score reads as a translated "not measured" rather than `?`.
- Correctness repairs: writing corrections read the real `fragment`/`suggestion`
  fields; grammar examples read `meaning_vi || vi`; practice captures its own
  segment target; voice feedback is discarded when its take was replaced.
- CI's Node gate repaired: it named seven `.mjs` scripts the reset deleted, so
  every CI run would have failed at that step.

## IN PROGRESS

Test/validator migration to the new product boundary, and full EN/ZH plus
narrow-viewport browser acceptance.

## PENDING

Narrow-viewport (≤800px, ≤480px) visual pass over the new Practice list and
Grammar pattern surfaces. The rules exist and the wide layout is verified;
window resizing was unavailable in the last browser session.

## NEXT EXACT TASK

1. Check current diff; continue without recreating old product code.
2. Native is frozen by the current human scope update. Do not change, test,
   restore or extend native code. Existing completed changes remain.
3. Resolve the Platform Admin question in OPEN P1, then migrate or retire
   `scripts/test_product_activity_contract.mjs` and
   `scripts/test_r17_readiness_contract.mjs` per that decision.
4. Retire the old product-only gates describing no shipped surface:
   `scripts/r8|r10|r11|r13|r14|r20_release_matrix.mjs`, and the three admin
   `.mjs` scripts failing on `window is not defined`.
5. Fix outstanding new-layer issues: continuation routes for free Writing and
   Grammar, direct practice lifecycle, degraded save/feedback states,
   translation recovery, keyboard focus and EN/ZH mobile presentation.
6. Run real browser journeys, regression suites and project-memory validators.
7. Update verified state and final status; commit; stop once for human review.

## Runtime / safety

Isolated `orena-foundation-web` on 127.0.0.1:8011; separate
`orena-foundation-postgres` and `orena-foundation-review` network. Database is
temporary, no production volumes or credentials. Mount is this workspace, read
only. Restart only this review container after Python/asset-route changes.
Production on 8000 and preview on 8010 were not operated. No provider
activation, deployment, schema migration or data mutation.

Dependency-heavy tests ran through `docker run --rm`, not Compose, so no shared
lane was touched. A read-only mount cannot start the app, which creates `data/`;
point `WRITING_DB`, `AUTH_DB`, `PLATFORM_DB`, `PRODUCT_DB` at `--tmpfs
/rundata:rw` alongside the environment CLAUDE.md documents.

## BLOCKED

No current tool blocker. Do not treat partial checks as REVIEWABLE.

## OPEN P0

None identified.

## OPEN P1

**Platform Admin is unreachable, and the decision is the human's.** `b28254e`
deleted `templates/index.html`, which was the old learner shell *and* the only
host for the operator dashboard (`#adminProductActivity`, "Operational readiness
evidence", `<script src="/static/admin.js">`). `static/admin.js` and every
`/api/admin/*` route still exist, but nothing loads them. D-046 authorised
removing learner-facing product; AGENTS.md §12 protects production
infrastructure, so whether Orena keeps a Platform Admin page, and where, is a
product call. `test_product_activity_contract.mjs` and
`test_r17_readiness_contract.mjs` are left failing as the evidence; do not
delete them first.

Grammar now lists only the three authored patterns per language that
`content/patterns.js` defines, where it listed the whole catalog before. If that
narrowing is curation it is done; if it is an unfinished authoring pass, the
remaining Concept IDs still need notes.

Reset is incomplete until the obsolete gates are retired and full EN/ZH browser
acceptance passes.

## HUMAN GATES

Production operations, data, credentials, paid providers, migrations, release,
billing, OAuth/DNS/Cloudflare, destructive history and store publishing remain
gated. Ordinary local reset/deletion and recovery commits are authorized.

## Baseline test evidence

Before reset, the full Python run and pristine starting HEAD both produced
753 passed / the same 20 failed governance or source-format assertions. Those
are inherited; do not weaken assertions to hide them. The working tree is back
at exactly that baseline, all twenty in `test_governance_contract.py`,
`test_media_ingestion.py`, `test_media_learning.py`.

A twenty-first failure existed briefly and is fixed: the JavaScript formatting
pass rewrote `if(!user.is_admin)` as `if (!user.is_admin)`, breaking a literal
substring assertion in `tests/test_public_skill_release_architecture.py`. It now
matches the gate by pattern instead. Expect other source-shape assertions to
break the same way.

The reset intentionally retires tests tied only to removed product behavior.

## Current scope update

Human explicitly froze native mobile / Expo / React Native on 2026-09-06.
Continue exclusively on WEB from the current state; do not undo completed work.

## Working-tree note

The uncommitted diff is large mostly because a Prettier-style pass reformatted
`static/orena/{app,content,product,ui}`, `world.css` and
`templates/orena/index.html`; `texts.js`, `evidence.js` and `intent.js` changed
by formatting only. `capabilities/` and `infrastructure/` were **not**
reformatted, so the tree is mixed. Decide deliberately whether to finish or
revert that pass.
