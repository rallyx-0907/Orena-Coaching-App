# Phone layout sweep, 2026-10-07 (Claude UI lane)

Scope: the whole learner UI at `/next` on phone sizes. Local execution only (Chromium via Playwright, one tab, no
provider calls, no Docker). Chromium cannot emulate an iPhone safe area, so safe-area findings are reasoned from CSS.

## Method

- Automated DOM checks per screen: sibling text/control overlap (after ancestor clipping), clipping by an `overflow:hidden`
  ancestor, horizontal overflow, page scroll, fixed/sticky overlap, touch targets under 32px, wrapped rows with an orphan
  control, nowrap truncation, last-word orphans. Screenshots read for the key screens and every flagged one.
- Sizes: 390x844, 393x852, 375x667, 360x740, 320x568 (Listening). Themes: dark and light. Languages: EN, VI, ZH.
- Screens (45 routes): Today, Discover, Content Detail (article, book, video, YouTube long title, imported), Search, Orena,
  Practice Hub and its Skill Hubs, Library, Collection, Grammar, Progress, Profile, Settings, Coming soon, Reader, Check,
  Reading Complete, Transfer, Discussion, Listening (+ line panel, Dictation, questions, shadow, React), Respond, Attempts,
  Speak Summary, Free Talk, Conversation, Situation, Writing, Review, Feed, From your errors, Welcome (steps 1-4).
- Sheets: Up next, Filters, Import (steps 1-2 for URL and Text; File chooser cancelled), Writing setup.
- Stress: every title, name, label and pill given a very long string, on 14 browsing screens.
- Inset simulation: 44px and 47px top padding injected on every workspace at 390x844 and 375x812.

## Defects found and fixed

| # | Screen | Before | After | Commit |
| --- | --- | --- | --- | --- |
| 1 | Collection hero, long title or pill | fixed 16:8 ratio with `overflow:hidden` cut the pill: pill top 37 against hero top 126 (89px above the hero) | hero grows to its content (170 to 343px with a long title), pill inside it | ee51a1b3 |
| 2 | Review, word whose blank is 14 marks | blank 494px wide at x -35..459 in a 350px card, bleeding past both edges | blank 48..342, inside the card (20..370) | ee51a1b3 |
| 3 | Listening, a line selected, 375x667 | media column content 477px in a 371px box: the card's actions ran 106px under the Transcript | Transcript yields to 96px, the media column scrolls its own 62px, nothing covered. 390x844 and 360x740 unchanged (no scroll) | ee51a1b3 |
| 4 | Listening transport, 371 to 389px wide | the More button dropped to its own row at 375px only (tight spacing applied at 370px and below) | tight spacing up to 389px, one row | ee51a1b3 |
| 5 | Today "Another" link and other section links | touch area 53x18 | touch area 69x44, drawn size unchanged | ee51a1b3 |
| 6 | Discover search, Discussion input, Import sheet, Orena panel, Quick sheet, Writing setup | 15px text fields: iOS Safari zooms the page when they take focus | 16px on phone | 65bc7a48 |
| 7 | Learning workspaces and Welcome on an iPhone with a top inset | no header, so the first row sat under the status bar | `.o-main` padding-top `env(safe-area-inset-top)` on phone focus and bare routes (0 where there is no inset) | 65bc7a48 |
| 8 | Phone bottom sheets | foot buttons 20px from the edge, inside the home-indicator zone | foot and last body row use `max(drawn padding, env(safe-area-inset-bottom))` | 65bc7a48 |

Already fixed before this sweep (b4b00026): Content Detail no-cover tile overlap and the bottom bar height.

## Checklist (zero hits unless listed)

Overlap, horizontal overflow, page scroll, fixed overlap: zero on all 45 routes at every size, theme and language above,
after the fixes. The only automated hits left are listed under Residuals.

## Safe-area audit (reasoned from CSS)

- `viewport-fit=cover` is set (`templates/orena/next.html`), so insets apply on a real iPhone.
- Phone header: `padding-top: 10px + env(safe-area-inset-top)`: clears a 47-59pt top inset.
- Phone bar: `margin-bottom: max(18px, inset - 10px)` (b4b00026): sits just above the 34pt indicator, no double add.
- Orena dock: browsing `78px + max(18px, inset - 10px)`, workspace `12px + inset`: consistent with the bar.
- Toast and the reader selection toolbar: `--toast-b: 108px` is above the bar (96px at a 34pt inset): 12px clear.
- Workspaces (no header, no bar): top clearance added (fix 7); bottom is the screens' own 32px, above the `inset - 10`
  rule (24px at 34pt). Onboarding CTA keeps 24px bottom.
- Sheets: fix 8. Desk (right panel) is unaffected.
- Workspaces tolerate a 44-47px top inset: no vertical overflow, no control pushed below the viewport (injected test).
- No double-adding: every new rule uses `max()` or a single `env()` term; old-UI files (`static/orena/shell.css`,
  `experiences.css`) are not used by `/next`.

## Residuals and decisions needed

- Text tabs (Discover, Library, Progress) are 36-38px high and the Collection word play button is 26x26: design-drawn
  sizes. Raising them is a product call.
- Practice tile descriptions end in an ellipsis so the duration stays visible (existing, deliberate rule).
- The selected-line Listening card on a 375x667 phone scrolls 62px in its own region: the only way to hold player,
  transport, card and Transcript at that height without removing something the design draws.
- Native scrollbars on the Discover tab strip and the Feed carousel show in desktop Chromium; iOS draws none.
- iOS keyboard behaviour (layout viewport shift when a field in a no-scroll workspace takes focus) cannot be checked
  in Chromium: needs a real-device pass on Writing, Respond, Situation and Free Talk.
- The level step of Welcome writes the profile on Continue (existing behaviour). During this sweep that step was
  advanced once with the stored defaults (B1, English with Vietnamese support), so the profile may have been re-saved
  with the same values. Nothing else was written.
