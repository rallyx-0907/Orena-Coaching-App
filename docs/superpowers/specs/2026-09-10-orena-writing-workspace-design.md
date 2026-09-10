# Orena Writing Workspace

Status: approved in chat for specification; implementation pending written-spec review.

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

## Compatibility and migration

- `EssayIn.target_cefr` becomes optional rather than being deleted.
- Existing native/frozen and historical callers may continue sending a target;
  their behavior remains compatible.
- The canonical web path omits it, and tests prevent its return to the UI.
- Existing stored evaluations and revision lineage remain readable.
- No schema migration, account activation or provider activation is required.

## Verification

Contract tests cover target-free EN/ZH evaluator requests, inferred band output,
exact evidence, provider failures and compatibility with target-bearing callers.
Browser-module tests cover both entry choices, no target selector, prompt/length
state, the one-frame layout contract, review switching, actionable feedback and
retry behavior.

Fresh browser verification runs the Writing route at narrow, desktop and wide
widths in EN and ZH. It confirms that drafting and normal feedback need no page
scroll, overflow is internal when feedback is long, and the visible review shows
band, correction, reason, rule and next action from provider-returned evidence.
Successful live-provider quality remains a credential/activation gate; injected
providers verify the full result path without being presented as live evidence.

