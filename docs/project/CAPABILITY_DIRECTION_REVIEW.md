# Capability-direction review

Reviewed application commit: `aaded1e9237b44a34b333e541d045feb12b9bd57`.
Verdict: **REQUEST CHANGES**. No new P0 identified; two P1 findings and one P2.

## Scope and human ruling

The human explicitly authorized reconciliation of stale current-state claims
under REVIEW_POLICY.md, followed directly by this capability-direction review.
Completed foundation work was not re-audited or redone. Review inspected the
current Codex capability code against the Product Constitution and Content
Architecture, with an independent code reviewer. No other lane was inspected.

CURRENT_PRODUCT_STATE now recognizes the committed foundation and the review's
next corrections. Its old application verification SHA, batch, date and release
history remain intact; they are not fresh acceptance evidence. The current P1
list now reflects the handoff's holds plus these findings. Historical entries
remain in Git. No durable product principle or architecture decision changed,
so no Decision Log entry is required.

## Findings

### P1: Recall reveals the target before retrieval

`static/orena/ui/expression.js:188` hides the target heading for speaking-origin
Recall but prints its full source sentence before reveal. The sentence can
contain the answer. Separately, `static/orena/product/recall.js:23` masks only
the first occurrence of a term; subsequent occurrences remain visible.

Local execution of `blankContext('Say hello, then hello again.', 'hello')`
returned `after: ', then hello again.'`. The UI prints this unmasked remainder.
Both paths undermine the claimed meaning-first or withheld-phrase retrieval
task before the learner can self-grade. This shared behavior affects EN/ZH.
Withhold answer-bearing context for speaking Recall and mask all target
occurrences for sentence Recall; preserve the existing self-assessment model.

### P1: Revision comparison can misclassify an unchanged issue

`app.py:581` selects arbitrary old/new issues within a category from sets,
then removes those keys before computing the persistent intersection.
`static/orena/ui/writing-review.js:73` presents the resulting categories as
learning feedback. Category membership alone does not establish that two
different issues are revisions of the same issue.

An isolated local execution extracted the actual `_issue_key` and
`revision_delta` functions with Python AST, stubbing only rubric weights.
With previous grammar fragments A/B and current A/C, PYTHONHASHSEED=1 produced:
removed B, persistent none, new A, changed A -> C. A is actually persistent.
Preserve exact common issues first and require defensible correspondence for
changed issues. Verify multiple same-category errors in both languages.

### P2: A long preceding conversation turn excludes the selected text

`static/orena/ui/conversation.js:61` selects the current turn but builds context
by joining the previous and current turns, then taking the first 2400
characters. A permitted 2400-character previous turn excludes the selected
current text. `writing_coach/media_interaction.py:691` rejects that context.
Budget context around the selected text. Source-confirmed; no live provider
execution was attempted. This is a bounded follow-up, not a conversation
architecture redesign.

## Direction assessment

Reading, Writing, Grammar and conversation use the shared contextual
explanation/save path. Reading admits published text through rights metadata
and treats comprehension as optional. Conversation separates the simulated
partner from coaching on the learner's words. Revision works on the learner's
existing text. These relationships support the approved connected experience;
the findings concern truthful learning behavior within it.

Reading catalogue rights/breadth, Grammar breadth, device-only continuity and
the Platform Admin host remain human-held questions. This review neither
resolves those holds nor authorizes persistence, provider or release changes.

## Local evidence and limits

- Five existing Node gates passed, zero failed: `test_orena_conversation.mjs`,
  `test_orena_reading_library.mjs`, `test_orena_writing_review.mjs`,
  `test_orena_extension_patterns.mjs`, `test_orena_learner_memory.mjs`.
  These gates do not catch the findings above; passing them is not acceptance.
- Recall and revision reproductions above executed successfully and exposed
  the defects; they are diagnostic evidence, not passing regression tests.
- Project-memory validator passed using the bundled Codex Python executable.
  `python` was absent from PATH and `py -3` found no installed Python; neither
  attempt was an application failure. No validator was modified.
- No full pytest, Docker, browser, microphone, provider or CI execution in this
  review. The handoff's 787 passed / 20 inherited failures remains historical.
- Application code, protected UI, persistence, runtime, application/frontend
  versions, deployments and production operations are unchanged.
- `PROJECT_STATE.md` is unchanged; `CURRENT_HANDOFF.md` is updated. Only current
  state, handoff, product status and this review report belong to the checkpoint.

Next: correct the two P1 findings and validate their capability flows before
operator and human browser acceptance. Foundation work remains committed.
