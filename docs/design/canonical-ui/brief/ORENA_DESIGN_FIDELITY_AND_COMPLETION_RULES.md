# ORENA — DESIGN FIDELITY & COMPLETION RULES

The provided prototype / approved design is the visual and interaction source of truth.

Do NOT treat implementing the requested CSS/components as completion.

## Required workflow

For every UI implementation task:

1. Inspect the complete reference prototype first.
2. Identify every relevant screen, state, breakpoint, interaction and reusable component affected by the task.
3. Inspect the current implementation before editing.
4. Compare current implementation against the prototype.
5. Implement the missing or incorrect parts.
6. Run the actual application.
7. Open the implemented screens in the browser.
8. Compare the rendered result against the prototype.
9. Record visible mismatches.
10. Fix those mismatches.
11. Re-open and verify again.
12. Repeat until no material mismatch remains.

Do not stop after writing code.

---

# Prototype comparison is mandatory

You must actively compare:

* page composition
* information hierarchy
* component dimensions
* alignment
* spacing
* typography
* font weight
* font size
* line height
* corner radius
* borders
* surface treatment
* shadows
* visual density
* icon size
* icon placement
* navigation
* responsive behavior
* scroll behavior
* empty states
* loading states
* error states
* selected states
* hover states
* pressed states
* modal/sheet behavior
* interactions
* desktop layout
* mobile layout

Do not infer that one screen is correct because another similar screen is correct.

Inspect each relevant screen.

---

# Definition of Done

A UI task is NOT DONE merely because:

* code compiles
* tests pass
* the requested component exists
* CSS values were changed
* all files were edited
* there are no console errors
* the design "looks close"
* the first visible screen looks correct

A UI task may be reported as DONE only after:

1. The actual app has been rendered.
2. Relevant screens have been opened.
3. Desktop and mobile variants have been inspected.
4. The implementation has been visually compared with the approved prototype.
5. Remaining mismatches have been fixed or explicitly listed.
6. No known material mismatch is being hidden behind the word "done".

---

# Completion reporting

Never report:

"Done"
"Completed"
"Everything is implemented"
"Matches the prototype"

unless browser verification has actually been performed.

Instead, report using this format:

IMPLEMENTATION STATUS

Reference inspected:

* [prototype/screens inspected]

Browser verification:

* Desktop: checked / not checked
* Mobile: checked / not checked

Screens checked:

* ...

Remaining mismatches:

* ...

Status:

* VERIFIED
  or
* IMPLEMENTED BUT NOT YET VISUALLY VERIFIED
  or
* PARTIALLY MATCHED

If any material mismatch remains, status must NOT be VERIFIED.

---

# Never self-approve from code alone

Do not use source-code inspection as proof of visual correctness.

The browser-rendered application is the final authority.

If browser access is available, use it.

If browser access is unavailable, explicitly say:

"Implementation completed, but visual fidelity has not been verified."

Do not substitute assumptions for visual verification.

---

# Whole-flow verification

When a prototype contains multiple connected screens, do not verify only the screen currently being edited.

Check the complete affected user flow.

Example:

Home
→ Discover
→ Content detail
→ Learning view
→ exercise
→ result
→ Next

A mismatch at any stage means the flow is not fully matched.

---

# Existing prototype coverage

Before declaring the migration/application of a design complete, create a coverage checklist:

| Prototype screen/state | Implemented | Browser checked | Match  |
| ---------------------- | ----------- | --------------- | ------ |
| Screen A               | yes/no      | yes/no          | yes/no |
| Screen B               | yes/no      | yes/no          | yes/no |
| ...                    |             |                 |        |

All relevant rows must be checked.

---

# Important principle

The task is not:

"Implement this design."

The task is:

"Make the running product reproduce the approved design closely enough that an independent visual review would not immediately find missing or inconsistent parts."

Implementation is only one stage of the task.
Verification and correction are part of the task.
