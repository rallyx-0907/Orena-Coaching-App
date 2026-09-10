# Orena Writing Workspace

Status: approved for implementation, including the 2026-09-10 contract tightening.

## Purpose

Writing must help a learner express something, see what their own language
demonstrates, understand specific problems, and revise without leaving the
workspace. It is not a form for choosing the score the learner wants to receive.

The experience preserves Orena's current shell, themes, typography, editorial
voice, shared explanation surface, revision history and exact-evidence rules.
The change removes low-value controls and recomposes the existing Writing room
around drafting and feedback.

## Entry choices

Writing has two first-class entry choices inside the same route:

1. **Guided writing** — the learner chooses a topic family and an approximate
   length. Orena presents an EN- or ZH-authored prompt appropriate to those
   choices. Topic and length describe the writing invitation; they never set or
   bias the evaluation band.
2. **Journal** — a free personal entry for a thought, event or reflection. It
   needs no task description and is evaluated as reflective/free writing.

The first slice uses a small authored multilingual prompt catalogue so choosing
a prompt works without an AI provider. It must not label authored prompts as AI
generated. The catalogue has stable language-neutral topic and length IDs with
EN/ZH copy. Future content or provider adapters may extend it without changing
the Writing room contract.

### Changing context after writing begins

Topic, requested length and Guided/Journal mode never alter learner text. The
workspace associates the current evaluation context with the draft explicitly.
If the learner changes that context after entering text, the workspace marks the
draft as having changed context and shows the new context before evaluation. A
submission always carries the exact context visible at the moment it is made.

A draft begun for Prompt A therefore cannot silently become evidence for Prompt
B. Previously evaluated snapshots keep Prompt A even if the editable workspace
later moves to Prompt B. Changing context may change the invitation; it cannot
rewrite, clear or silently relabel the learner's words.

## Evaluation contract

The web client no longer asks for or sends `target_cefr`. The existing request
field remains optional for compatibility with older clients, but it is not part
of the canonical web flow.

Without a target, the evaluator receives:

- the active learning language and its assessment scale;
- the exact learner text;
- either the guided prompt plus requested length or the journal context;
- revision lineage when one exists.

The evaluator estimates the level demonstrated by this submitted sample: CEFR
for English and HSK for Chinese. The UI labels this as a sample-level estimate,
never overall proficiency or mastery. The result continues to require grounded
scores and exact learner evidence. A useful review exposes:

- demonstrated band and overall score when the provider returned them;
- dimension scores;
- strengths quoting the submitted text;
- categorized issues quoting the submitted text;
- a meaningful correction, why the wording is a problem, and a reusable rule;
- concrete next actions;
- revision comparison when a previous evaluated draft exists.

Requested length describes only the invitation and never biases the demonstrated
level. Insufficient evidence is a valid evaluation result. A sample that is too
short, repetitive or limited may return no demonstrated band while still
returning grounded language feedback. The result carries an explicit
`band_status` (`estimated` or `insufficient_evidence`); `app_cefr` is absent for
the latter. Confidence is displayed only when the provider contract supplies a
grounded confidence value. The UI explains that the sample did not support a
defensible band and does not manufacture precision.

Guided and Journal submissions use different evaluation contexts. Guided may
measure task achievement against its bound prompt. Journal has no task prompt,
is never penalized for prompt adherence, and omits `task_achievement` as not
applicable rather than assigning an artificial score. Journal may still assess
clarity, grammar, vocabulary, cohesion, expression, grounded strengths, issues,
corrections, reusable rules and next actions. Every evaluator request names the
submission mode explicitly.

Missing evidence remains missing. A provider failure produces no score, band,
meaning, correction or learning claim.

## One-frame interaction

At desktop and wide widths, the Writing route owns one viewport-height
workspace beneath the product shell. The drafting surface and one companion
panel sit side by side. Before evaluation, the companion panel contains the
entry choice and guided prompt. After evaluation, it becomes the review panel
while the learner's draft remains visible and editable.

The page itself does not require vertical scrolling for normal drafting or a
normal review. The editor scrolls internally for a long draft. The review panel
scrolls internally only when the amount of feedback exceeds the available
space. Revision actions update the visible editor in place.

At narrow widths, the same route remains one bounded workspace with two views:
**Write** and **Review**. Submitting moves focus to Review; the learner can return
to Write without navigation or losing state. Only the active view is displayed,
and excess feedback scrolls inside Review rather than extending the document.

Bounded does not mean a rigid `100vh`. The layout uses the dynamic viewport
(`dvh`) with safe-area insets and may observe the visual viewport where the
software keyboard requires it. When the keyboard opens, the focused line,
editing context and submit/retry controls remain reachable and visible. Editor
and Review surfaces own their overflow, focus is scrolled into the active
surface, and keyboard users cannot become trapped. Document scrolling is
avoided during normal use but remains a safe fallback when the actual visual
viewport is too constrained to preserve access.

No global shell, theme token or brand asset is redesigned. The existing Writing
paper treatment, Orena palette and editorial typography remain the visual base.

## State and lifecycle

The current device/runtime memory seam continues to own drafts, selected entry
choice, prompt parameters and revisions until the account backbone is activated.
This work does not create a new persistence system and does not touch I2.

Changing topic or length may replace an untouched guided prompt. It must never
replace learner-written text. Switching between Guided and Journal preserves
the current draft and makes the changed evaluation context visible.

Only a successful evaluation creates evaluated revision evidence. A failed or
unavailable request keeps the exact draft, prompt context and retry action.

### Immutable evaluated submissions

Each successful evaluation binds to an immutable submission snapshot containing
at minimum:

- exact submitted learner text;
- Guided prompt plus topic/length parameters, or the Journal context;
- active learning language and submission mode;
- evaluation timestamp or equivalent stable submission identity;
- revision ID, series ID, revision number and parent identity where available;
- the complete normalized evaluation and grounded evidence returned for it.

The editable workspace may change after submission. The review continues to
render its bound snapshot and visibly identifies when the editor has moved on.
Feedback from Draft 1 never appears to describe Draft 2. Revision comparison
uses two stored evaluated snapshots, never the current mutable editor value.

## Compatibility and migration

- `EssayIn.target_cefr` becomes optional rather than being deleted.
- Existing native/frozen and historical callers may continue sending a target;
  their behavior remains compatible.
- The canonical web path omits it, and tests prevent its return to the UI.
- Existing stored evaluations and revision lineage remain readable.
- No schema migration, account activation or provider activation is required.

## Verification

Contract tests cover target-free EN/ZH evaluator requests, inferred or
insufficient band output, mode-specific rubric applicability, exact immutable
submission evidence, provider failures and compatibility with target-bearing
callers.
Browser-module tests cover both entry choices, no target selector, prompt/length
state, the one-frame layout contract, review switching, actionable feedback and
retry behavior.

Fresh browser verification runs the Writing route at narrow, desktop and wide
widths in EN and ZH. It confirms that drafting and normal feedback need no page
scroll, overflow is internal when feedback is long, and the visible review shows
band, correction, reason, rule and next action from provider-returned evidence.
Narrow verification includes dynamic viewport resizing and a software-keyboard
equivalent viewport reduction, focus visibility, reachable submit/retry controls
and freedom from scroll traps.
Successful live-provider quality remains a credential/activation gate; injected
providers verify the full result path without being presented as live evidence.
