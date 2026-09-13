# Orena Writing Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a real EN/ZH Writing workspace with Guided and Journal entry modes, target-free AI evaluation, immutable reviewed submissions, truthful insufficient-evidence handling and viewport-safe Write/Review composition.

**Architecture:** Extend the existing Writing evaluator and device-memory seams instead of adding a new engine or persistence layer. A language-neutral workspace model binds authored prompt context to each submission; the server normalizes mode-specific results; the existing review renderer displays only the immutable snapshot returned for that submission.

**Tech Stack:** FastAPI/Pydantic, existing writing evaluator and learning repository, browser-native ES modules, HTML/CSS, Node contract gates, pytest, CUA browser verification.

**Spec:** `docs/superpowers/specs/2026-09-10-orena-writing-workspace-design.md`

## Global Constraints

- Do not modify I2, migrations, account persistence, themes, global shell, typography, navigation or brand assets.
- English and Chinese ship together through language-neutral contracts.
- Canonical web evaluation requests omit `target_cefr`; older target-bearing callers remain valid.
- No score, band, correction, rule, confidence or evidence may be invented.
- Evaluated evidence binds to the exact submitted text and context.
- Requested length affects the invitation only and never the demonstrated band.
- Mobile layout uses dynamic viewport behavior and must remain keyboard/focus accessible.
- Stage only files in this plan; Opus brand WIP remains reserved.

---

### Task 1: Target-free, mode-aware evaluator contract

**Files:**
- Modify: `app.py`
- Modify: `writing_coach/writing_evaluator_contract.py`
- Modify: `writing_coach/writing_evaluation.py`
- Test: `tests/test_writing_evaluator_contract.py`
- Test: `tests/test_writing_evaluation.py`

**Interfaces:**
- Consumes: `EssayIn`, active language profile, `build_writing_evaluator_request`, provider JSON.
- Produces: optional `EssayIn.target_cefr`; `writing_mode: "guided" | "journal"`; structured `writing_context`; normalized `band_status: "estimated" | "insufficient_evidence"`; optional `band_confidence`; mode-applicable `dimensions`.

- [ ] **Step 1: Write failing request-contract tests**

Add tests proving a target-free Guided request names its prompt/length without asking the provider to score toward a target, a Journal request contains no task-adherence instruction, and a legacy target-bearing request still validates.

- [ ] **Step 2: Run the focused contract tests and confirm failure**

Run the evaluator-contract test module in the hermetic Docker recipe. Expected: failures for required `target_cefr`, missing mode/context and missing band-status schema.

- [ ] **Step 3: Implement the request and schema contract**

Make `target_cefr` optional, validate `writing_mode`, accept a bounded context object, tell the evaluator to estimate only demonstrated evidence, define the insufficient-evidence result, and omit task achievement for Journal. Preserve legacy target context only when an older caller supplies it.

- [ ] **Step 4: Write and pass normalization/API tests**

Cover EN CEFR, ZH HSK, insufficient evidence with grounded issues, Journal without `task_achievement`, provider failure, and older target-bearing requests. Assert requested length never enters level calibration instructions.

- [ ] **Step 5: Commit the evaluator contract**

Stage only the backend and test files above and commit `feat(writing): infer sample level without a target`.

---

### Task 2: Authored prompts and immutable workspace snapshots

**Files:**
- Create: `static/orena/content/writing-prompts.js`
- Create: `static/orena/product/writing-workspace.js`
- Modify: `static/orena/product/memory.js`
- Test: `scripts/test_orena_writing_workspace.mjs`

**Interfaces:**
- Produces: `WRITING_TOPICS`, `WRITING_LENGTHS`, `writingPrompt(language, topicId, lengthId)`; `submissionContext(state)`; `captureWritingSnapshot({text, context, language, result})`; `reviewMatchesDraft(snapshot, draft)`.
- Snapshot fields: `submitted_text`, `context`, `language`, `submitted_at`, `essay_id`, `series_id`, `revision_no`, `parent_id`, `evaluation`.

- [ ] **Step 1: Write failing prompt and snapshot tests**

Assert stable IDs and complete EN/ZH authored copy, no generated label, mode/context changes preserve text, Prompt A stays in Snapshot A after the workspace selects Prompt B, and snapshot data does not mutate when the editor/result objects mutate.

- [ ] **Step 2: Run the Node test and confirm failure**

Run `node scripts/test_orena_writing_workspace.mjs`. Expected: module-not-found or missing exported contracts.

- [ ] **Step 3: Implement pure prompt/workspace primitives**

Create the authored catalogue and deep-copy/freeze snapshot boundary. Extend the existing device memory value with bounded `writingWorkspaces` and `writingReviews` maps while preserving older stored values and limits.

- [ ] **Step 4: Pass workspace and existing memory gates**

Run the new workspace gate plus `test_orena_learner_memory.mjs`, `test_orena_continuation.mjs` and `test_orena_writing_review.mjs`.

- [ ] **Step 5: Commit the workspace model**

Stage only Task 2 files and commit `feat(writing): bind reviews to immutable submissions`.

---

### Task 3: Recompose the Writing route into one bounded workspace

**Files:**
- Modify: `static/orena/ui/expression.js`
- Modify: `static/orena/ui/writing-review.js`
- Modify: `static/orena/ui/copy.js`
- Modify: `static/orena/rooms.css`
- Modify: `static/orena/experiences.css` only if an existing conflicting Writing rule cannot be overridden coherently in `rooms.css`
- Modify: `scripts/test_orena_writing_review.mjs`
- Test: `scripts/test_orena_writing_workspace.mjs`

**Interfaces:**
- Consumes: Task 1 API shape and Task 2 prompt/snapshot primitives.
- Produces: Guided/Journal controls, topic/length selectors, explicit changed-context notice, target-free submit payload, desktop split workspace, narrow Write/Review views, immutable review display and insufficient-band explanation.

- [ ] **Step 1: Add failing UI contract assertions**

Assert no target selector or `target_cefr` in the canonical web request; both modes and EN/ZH labels exist; the submit payload carries explicit context; feedback renders the captured snapshot; insufficient evidence renders no band; and narrow view controls expose Write/Review semantics.

- [ ] **Step 2: Run the Node gates and confirm failure**

Run Writing Review and Writing Workspace gates. Expected: missing mode controls, target still present, no snapshot binding and no insufficient-band presentation.

- [ ] **Step 3: Implement the route recomposition**

Keep `pageIntro`, existing paper styling, revision workbench and shared Understanding/Register actions. Move invitation controls into the companion pane, remove the task/target form controls, bind each submit to a fresh immutable context snapshot, replace invitation with Review after success, and visibly mark a review stale when the editor or context diverges.

- [ ] **Step 4: Implement responsive viewport behavior**

Use `min(100dvh, ...)`, safe-area padding, internal `overflow:auto`, `min-height:0`, focus-visible controls and narrow Write/Review view switching. Add a visual-viewport CSS variable only when needed to keep focused controls above the keyboard; retain document scrolling as the constrained-height fallback.

- [ ] **Step 5: Pass all browser-module gates**

Run Writing Review, Writing Workspace, Foundation and the 51-module ESM graph gate.

- [ ] **Step 6: Commit the learner-visible workspace**

Stage only Task 3 files and commit `feat(writing): deliver the guided and journal workspace`.

---

### Task 4: Browser acceptance and project truth

**Files:**
- Modify: `docs/product/ORENA_STATUS.md`
- Modify: `docs/project/CURRENT_HANDOFF.md`

**Interfaces:**
- Consumes: completed backend and frontend slices.
- Produces: exact browser evidence and the next truthful human/provider gate.

- [ ] **Step 1: Run fresh backend regressions**

Run Writing evaluator, benchmark, revision, grammar-transfer and analytics pytest modules. Record only the actual count.

- [ ] **Step 2: Verify EN/ZH and both modes in the browser**

At narrow, desktop and wide widths, exercise Guided and Journal, context changes after text, target-free requests, insufficient evidence, provider failure, successful injected-provider review and immutable Draft 1 feedback after Draft 2 edits.

- [ ] **Step 3: Verify dynamic mobile viewport behavior**

Reduce the visual viewport to a keyboard-like height and confirm the active line, context, submit/retry controls and Write/Review switch remain reachable with no scroll trap. Confirm long feedback scrolls inside Review.

- [ ] **Step 4: Update product truth and validate memory**

Record exact results and limitations, keep `CURRENT_HANDOFF.md` below 8 KiB, run `validate_project_memory.py`, and make no live-provider quality claim.

- [ ] **Step 5: Commit the evidence**

Stage only the two project-truth files and commit `docs(orena): record writing workspace evidence`.

