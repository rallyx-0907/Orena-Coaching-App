# Writing (with Compare Versions, Prompt Setup, Context Rewrite, Timed Writing) - design audit (D-129 batch)

Read-only audit, 2026-10-07, branch `codex/work`. Method is D-129 section 3 (scenario, same scenario on the app, deviation table);
the table is for the human to answer before any fix (D-129 section 3 "Send the table, then fix"). Nothing was changed in source.

- Design: `docs/design/canonical-ui/screens/Orena.dc.html` (pin of 2026-09-27), read from disk and served locally on 127.0.0.1:8797 (server stopped at the end).
  No sibling frame is needed by the Writing frames, so no scratch copy was made. Frames: Writing (18), Compare Versions (19), Prompt Setup (61, a sheet),
  Context Rewrite (37), Timed Writing (38), Practice Hub / Skill Hub "Write" (`SK.Write`, `writeModes`), and `Respond to Content` only at its hand-off.
- App: `http://localhost:8021/next`, desktop 1920x1080 and 1366x768, phone 390x844 (and 360x740 for the viewport rule) with `hasTouch`/`isMobile`,
  dark and light, interface English and Vietnamese (the stored `orena.interface` was `vi`; it switched to `en` from localStorage and was restored to `en`).
  The account's learning-language chip read "English - B1" during the audit; Writing content follows `context.language`. ZH was not walked.
- **The account has no evaluated essay** (`GET /api/essays` is `[]`), and submitting would be a provider call. The result, revision and compare states were therefore
  walked with the **repository's captured API fixtures served through a browser-side route mock** (`scripts/fixtures/api/writing_essay_*.json`, real
  captured responses; no server call, no write, no provider). Those states are labelled **mock-walked** below. Apply / Accept (which rewrite the stored draft),
  Review / Review again (`POST /api/evaluate`) and Ask deeper were **not clicked** and are **code-read**.
- Evidence: `docs/reviews/evidence/writing-audit/` (`d-*` design desktop, `m-*` design phone, `a-*` app desktop, `ap-*` app phone).

Decisions respected, not re-opened: D-129, D-067/D-068 (design copy is sample content), D-079/rule 50 (sparse copy, language layers), D-098.6 (Review disabled
with a countdown of the missing words), D-101 H9 (coming-soon entries not drawn in the hubs), D-103.5 and `ZH_WRITING_EVALUATOR_RECALL` (the evaluator),
AGENTS 7 / D-104 (drafts are device memory today, server records are a reviewed proposal), D-093 (AA colour adjustments), rule 49 (workspace is the viewport),
rule 47 (the rail is always present, workspaces have no top bar), `UI_BACKEND_GAPS` N-22 (no measured duration exists for any mode).

## 1. Prototype scenario (what the design does)

State script: `wr` = `{text, prompt, level, register, target, versions[], review, reviewing, mode edit|review, finding, fTab why|how, kept, tab draft|review, setup, cvTab}`.
Review is simulated 1.3 s, then `FINDINGS` (5 sample findings) are matched by exact span against the text; versions accumulate (v1, v2 ...); `Apply` replaces the span
and asks for a re-review; `Dismiss` hides a finding ("it won't count as an open issue"). Phone shows one pane at a time under a Draft / Review tab.

| # | Frame | State | Learner action | Transition | Shot |
| --- | --- | --- | --- | --- | --- |
| D1 | Practice Hub, Write section | idle | opens Practice Hub | "Continue" card for "Writing draft - 142 words - 3 d ago" (Continue learning row) and a Write section of 7 tiles with label + one-line meta + duration: Continue draft, Prompt, Free Writing, Your Topic, Respond to Content, Context Rewrite, Timed Writing | d-01, m-01 |
| D2 | Skill Hub "Write" (frame 09) | idle | (phone only; `phTiles` is not rendered in this revision, so it is not reachable by tapping; read from source) | "Recommended - Fix the tense finding, then re-review" card with reason, then 3 groups: Write freely (Continue draft, Prompt, Free Writing, Your Topic), Respond (Respond to Content, Context Rewrite), Under pressure (Timed Writing) | source only |
| D3 | Writing (frame 18) | draft, unreviewed | Continue draft | header: back, prompt title, "Prompt - B2 - Informal - ~150 words - unreviewed", [Setup], [Review]; word / character count, "Saved - autosave on"; a plain textarea (rows 16); right pane "No review yet for this draft. Press Review when you want feedback - findings will be anchored to your exact sentences." Phone: Draft / Review tab | d-02, m-02 |
| D4 | Prompt Setup (frame 61, sheet) | open | Setup, or Prompt / Your Topic tile | desktop right panel / phone bottom sheet: Prompt input, Level B1/B2/C1, Register Informal/Neutral/Formal, Target length 100/150/250, helper line "Level and register shape the review...", [Write] closes it | d-03, m-06, d-20, m-09 |
| D5 | Writing | reviewing | Review | button "Reviewing...", pane "Reviewing your draft..." (1.3 s) | d-04 |
| D6 | Writing | review (marked) | (auto) | draft becomes a marked card: wavy red underline on priority spans, amber on others, green fill on strengths; legend (priority / other / strength), [Edit draft]; right pane: "Review - v1 - Today 09:12", overall sentence, [Keep review], Strengths, "Priority issues - 3" rows (kind, span, open/fixed), "Other issues - 2" disclosure, Feedback summary (score /100 and 4 dimension bars with "Strong" / "n fix(es)"), "Estimated range: B1+ - based on this draft only.", [Next - open the first priority issue and apply the fix] | d-05, d-09, m-03, m-04 |
| D7 | Writing | finding popover | tap a marked span | popover under the span: category, struck old -> new, first sentence of the why, [Accept] [Dismiss] [Orena icon] | d-06, m-05 |
| D8 | Writing | finding detail | (same tap, or a row in the pane) | pane shows kind - dimension, old, new, WHY / HOW tabs (HOW adds "Reusable pattern" and "Another example"), [Apply suggestion] [Ask deeper] [Related grammar] (only when the finding has a grammar link) [Practice this]; close X returns to the summary | d-06, d-07, m-05b |
| D9 | Writing | applied | Apply suggestion / Accept | span replaced in the text, toast "Applied - re-review to update the findings", row turns "fixed" (struck, green) | d-08 |
| D10 | Writing | dismissed | Dismiss | finding removed from the marks, toast "Dismissed - it won't count as an open issue" | source |
| D11 | Writing | kept | Keep review | label becomes "Kept" | source |
| D12 | Writing | review v2 | Review again | version label v2; [Compare versions] appears in the header | d-10 |
| D13 | Compare Versions (frame 19) | two versions | Compare versions | header "Compare versions" + prompt; three columns: Version 1 (marks), Changes (Fixed n / Still present n / New n with items; "Grammar 62 -> 69 - range B1+ -> B1+"), Version 2 (marks). Phone: Earlier / Revised tab, legend above the draft | d-11, m-07, m-08 |
| D14 | Writing | edit after review | Edit draft | back to the textarea, review pane stays | d-12 |
| D15 | Writing | Free Writing | Practice Hub -> Free Writing | blank draft, title "Free writing", no sheet | d-13 |
| D16 | Writing + Prompt Setup | Your Topic | Practice Hub -> Your Topic | blank draft with the Prompt Setup sheet open, empty prompt | d-14 |
| D17 | Context Rewrite (frame 37) | input | Practice Hub -> Context Rewrite | "Core message - I can't make it.", 3 steps (A Friend / B Manager / C Invitation), context prompt, textarea, [Check] | d-15 |
| D18 | Context Rewrite | result | Check | the answer, 4 check tiles (Intent preserved? / Register fit / Politeness / Clarity), "One language fix", "Natural in this context", [Retry] [Next context] [Finish] | d-16 |
| D19 | Timed Writing (frame 38) | idle | Practice Hub -> Timed Writing | clock "90 s", prompt kind chip, prompt, context line, [Start - 90 s] | d-17 |
| D20 | Timed Writing | input | Start | countdown bar (green, amber under 30 s, red under 10 s), textarea, [Submit]; auto-submits at 0 | d-18 |
| D21 | Timed Writing | result | Submit | answer, "Communication worked?" / "Register fit" tiles, "One important fix", "Submitted with 89 s left - 12 words", [Retry] [Next prompt] [Finish] | d-19, m (phone, seen) |
| D22 | Respond to Content (frame 36) | hand-off | Practice Hub -> Respond to Content | opens the Respond room with a source article (Opinion / Summary / Reaction / Continuation, "Write 60-150 words...", Get feedback, Revise, Ask Orena why, Open source); owned by the Reading / Listening skill, not walked further | source |
| D23 | Orena entry from a finding | contextual | Ask deeper (`openOrena({writing:F})`) | Contextual Orena panel with the finding as context | source |
| D24 | Related grammar / Practice this | link | on a finding with a grammar link | Related grammar opens Grammar; Practice this opens Grammar or a toast "Targeted drill would be generated from this finding" | source |

Scenario step count: 24 (D1-D24); 19 walked on the prototype, D2, D10, D11, D22, D23, D24 read from source. Phone (390x844) was walked on D1, D3, D4, D6, D7/D8, D13.

## 2. The same scenario on the app (`/next`)

| # | Route | State seen | Walked? | Shot |
| --- | --- | --- | --- | --- |
| A1 | `#/practice` (Write section) | one tile, "Writing", name only (no description, no duration); Continue learning shows only conversation rows | walked | a-10, ap-08 |
| A2 | `#/practice/write` (Skill Hub) | "Recommended - Clear Expression" with a real reason from `GET /api/practice-recommendation` and [Start]; one row "Writing" with a chevron; no groups | walked | a-11, ap-07 |
| A3 | `#/write` | new draft: title "Untitled draft", "B1 - unreviewed", [Setup] [Review] (Review disabled), counts, "Write 2 more words to request a review.", "Saved on this device", empty textarea, review pane note | walked (EN dark, VI light, phone) | a-01, a-02, ap-01 |
| A4 | Setup (sheet inside Writing) | Prompt, Level, Register, Target, [Write]; no helper line | walked | a-14, ap-06 |
| A5 | Review requested / failed | "Reviewing..." and a failed-review toast ("Could not get a review. Try again.") | **code-read, not walked** (provider call) | - |
| A6 | `#/write/:id` marked review | marked card, legend, Edit draft, Keep review, Strengths, Priority issue, Other issues disclosure, Feedback summary, range, Next | **mock-walked** | a-03, a-06, a-07, ap-02 |
| A7 | finding popover and pane | popover (Accept, Dismiss, Orena icon), pane WHY / HOW with Apply suggestion and Ask deeper; no Related grammar / Practice this | **mock-walked** | a-04, a-05, ap-04 |
| A8 | Apply, Accept, re-review, Ask deeper | `applyFix`, "Review again", agent bridge | **code-read, not walked** | - |
| A9 | Keep review | label becomes "Kept" | **mock-walked** (the keep call was answered by the mock) | a-07 |
| A10 | Edit draft after review | textarea, review pane stays | **mock-walked** | a-08 |
| A11 | `#/write/:id/compare` | three columns, Fixed 4 / Still present 1 / New 1, "Grammar 48 -> 71 - range B1 -> B1"; phone Earlier / Revised | **mock-walked** | a-09, ap-05 |
| A12 | `#/rewrite`, `#/timed-writing` | a "Coming soon" page with the mode name; the hubs do not list them | walked | a-12, a-13 |
| A13 | Free Writing, Your Topic, Respond to Content, Continue draft | no entry in the hubs; Respond is reachable only from Listening's end / Reader with a content id | walked (absence) | - |
| A14 | rail while in Writing | "Practice Hub" selected when opened from the hub; "Today" on a direct load of `#/write` or `#/write/:id` | walked | a-15, a-03 |
| A15 | VI interface | chrome in Vietnamese; the empty-pane note, review text, range line and the Recommended card text are not in the same language (see W-09) | walked | a-20 |
| A16 | ZH writing | Hanzi counter, `tooShortHan`, ZH review refresh (D-103.7) | **code-read, not walked** | - |

Viewport rule (rule 49), measured: at 1920x1080, 1366x768, 390x844 and 360x740 the document never scrolls (scrollHeight equals innerHeight, no horizontal overflow)
on new draft, a 1,900-word draft (Review stays at y 17-51 desktop, 66-100 phone), the mock review, an open finding and Compare Versions.

## 3. Deviations

Classes: missing step, wrong order, component not in design, wrong Visual skin, missing state, different behaviour.

| Id | Frame | Class | Design | App | Evidence | Proposed fix |
| --- | --- | --- | --- | --- | --- | --- |
| W-01 | Practice Hub / Skill Hub Write | missing step | 7 modes in 3 groups (Write freely: Continue draft, Prompt, Free Writing, Your Topic; Respond: Respond to Content, Context Rewrite; Under pressure: Timed Writing) | one row "Writing" | d-01, a-10, a-11 | HUMAN DECISION HW-1 |
| W-02 | Practice Hub / Skill Hub Write | wrong Visual skin | tile / row with label, one-line description and duration, group titles | "Writing" with the name only, no group title, no description | d-01, a-10, a-11 | add the description (translated, D-068); duration stays out (N-22: no measured duration exists); covered by HW-1 |
| W-03 | Practice Hub, Continue learning | different behaviour | one "Writing draft - n words - age" Continue card | with no draft the card is absent (correct); not observed with a draft. The row shows the same Conversation card three times | a-10 | code shows a Writing continuation mapping (`practice/model.js` `essay:` / `expression:`); the triple Conversation row is Speaking's bug, report to that lane |
| W-04 | Prompt Setup | wrong order | Prompt and Your Topic open the Prompt Setup sheet first, then the room | every entry is the room itself; Setup is reached only from the room's [Setup] | d-03, d-14, a-01 | HUMAN DECISION HW-2 |
| W-05 | Writing header, Prompt Setup | missing state | "Prompt - B2 - Informal - ~150 words - v1" and the helper line "Level and register shape the review..." | "B1 - v2" (level and version only); no helper line. Register and target are not sent to the evaluator (`reviewPayload`), so they live for the visit only; the helper line was cut because it is false for register | a-02, a-03, a-14 | HUMAN DECISION HW-3 |
| W-06 | Writing, draft | different behaviour | "Saved - autosave on" | "Saved on this device" / "Saved to your account" (truthful: drafts are device memory, AGENTS 7) | a-02 | keep; the label follows D-104 once the server draft record lands |
| W-07 | Writing, draft | component not in design | Review always enabled, no hint | Review disabled under the minimum with "Write 2 more words to request a review." | a-02, a-01 | none (D-098.6) |
| W-08 | Writing, empty review pane | different behaviour | "No review yet for this draft. Press Review when you want feedback - findings will be anchored to your exact sentences." in the one language | cut to one clause (rule 50) and rendered in the **support** language, so an English interface shows "Chua co nhan xet..." in Vietnamese; the estimated-range line "Trinh do uoc tinh: B1 - chi dua tren bai viet nay." likewise | a-02, a-03 | HUMAN DECISION HW-4 |
| W-09 | Writing, review pane | different behaviour | one language | the overall sentence, strength notes, finding WHY / HOW are AI text in the support language under any interface language; in a VI interface the Skill Hub Recommended card (focus label and reason, server text) stays English | a-03, a-20, ap-07 | HUMAN DECISION HW-4 |
| W-10 | Writing, marked draft | different behaviour | the finding popover sits under the start of the span and is fully visible | the popover is anchored to the end of a span that wraps, positioned at x=1048 on a card ending at x=1086, so it is clipped by the card's overflow and a horizontal scrollbar appears; the open finding is only readable in the right pane | d-06, a-04 | anchor the popover to the span's first line and keep it inside the card (a defect, no decision) |
| W-11 | Writing, finding pane | missing step | [Related grammar] (when the finding has a grammar link) and [Practice this] | neither (R5 grammar content retired 2026-09-28; documented in `screens/writing/screen.js`) | d-06, a-05 | HUMAN DECISION HW-5 |
| W-12 | Writing, feedback summary | different behaviour | each dimension shows "Strong" or "n fix(es)" | note only when there are open fixes or the score is 80+; Coherence and Naturalness at 69-78 show nothing | a-03 | HUMAN DECISION HW-6 |
| W-13 | Writing, finding dismissed | different behaviour | toast "Dismissed - it won't count as an open issue" | toast "Dismissed" (copy trimmed, rule 50) (code-read) | source | none |
| W-14 | Writing, rail | different behaviour | Practice Hub stays selected in the room | correct from the hub; a direct load or reload of `#/write*` selects "Today" | a-03, a-15 | when no origin is known the Writing fallback origin is Practice Hub (rule 47), as S-28 for Speaking |
| W-15 | Context Rewrite | missing step | the whole flow (core message, 3 contexts, Check, 4 check tiles, One language fix, Natural in this context, Retry / Next context / Finish) | "Coming soon" page; no hub entry | d-15, d-16, a-12 | HUMAN DECISION HW-7 |
| W-16 | Timed Writing | missing step | the whole flow (90 s clock and bar, Start, auto-submit, Communication worked? / Register fit, One important fix, Retry / Next prompt / Finish) | "Coming soon" page; no hub entry | d-17..d-19, a-13 | HUMAN DECISION HW-7 |
| W-17 | Respond to Content (hand-off) | missing step | a Write mode that opens the Respond room with a source | the room exists but is only reachable from Listening's end / Reader with a content id; no Write entry | d-01, a-10 | part of HW-1 (UI_BACKEND_GAPS: no generic "which content" id source) |
| W-18 | Free Writing | missing step | its own mode: blank page titled "Free writing" | a new draft with no prompt is the default room ("Untitled draft"); no named entry | d-13, a-02 | part of HW-1 / HW-2 |
| W-19 | Writing, Orena entry | different behaviour | Ask deeper opens the Contextual Orena panel with the finding | Ask deeper goes through `askOrena` (agent bridge); the panel itself was not exercised (code-read) | source | covered by the cross-skill Orena pass (D-129 section 2) |

Not deviations (measured or checked): the textarea (17/400, line 28.9, radius 20, padding 22 24, 822x508 at 1920), Setup sheet (all controls), Compare Versions
(three columns, Changes cards, delta line, phone Earlier / Revised tabs; compared by eye and title size), Feedback summary (score 28/700, dimension bars), Strengths / Priority / Other rows,
Keep review, Edit draft, Next, popover actions (Accept, Dismiss, Orena icon), WHY / HOW panel, kept and dismissed states, the 1.3 s "Reviewing" state and failure toast
(a drawn toast pattern), phone Draft / Review tabs, viewport rule. The real recommender card is the design's Recommended card with a real reason.

### HUMAN DECISION items (options only; * = recommended)

- **HW-1 (W-01, W-02, W-17, W-18) Which Write modes the hubs list.** A) keep only "Writing" (D-101 H9); B)* list the built modes the design draws as rows in the design's three groups with description and no duration: Continue draft (when a draft exists), Prompt and Your Topic (open the setup sheet, see HW-2), Free Writing (blank room); Respond to Content, Context Rewrite and Timed Writing stay hidden until built; C) also draw those three as dimmed "Soon" rows.
- **HW-2 (W-04) Prompt Setup as an entry.** A) keep the room only; B)* Prompt and Your Topic open the room with the Prompt Setup sheet already open (as the design), Free Writing and Continue draft open the room without it; C) a first-use sheet only.
- **HW-3 (W-05) Register and target length.** A)* keep them as the learner's own intent for the visit, show "Prompt - B1 - Informal - ~150 words - vN" in the header from the chosen values and keep the helper line out; B) wire register and target into the evaluator (backend, `UI_BACKEND_GAPS`) and restore the design's helper line; C) drop the Register and Target groups from the sheet until B.
- **HW-4 (W-08, W-09) Language layers in Writing.** D-139 HD-14 made mic sheets and system notes wholly interface-language. A)* the same here: the empty-pane note, range line and notices follow the interface language; the AI review text and the recommender text follow the support language but a hub card's server text is localised (or hidden when it cannot be); B) keep the two-layer rule (D-079) as built; C) interface language by default with a support line under it.
- **HW-5 (W-11) Related grammar and Practice this.** A)* keep absent until the Grammar Lab contract exists (current record); B) show Related grammar only when the finding carries a concept id, opening that concept; C) Practice this as a drill generated on request and cached (D-130 pattern).
- **HW-6 (W-12) "Strong" on every dimension.** A)* show the note only when it is earned (open fixes, or 80+), as built; B) always show "Strong" or "n fixes" from the score bands; C) show the band label from the value (Strong / Solid / Needs work).
- **HW-7 (W-15, W-16) Context Rewrite and Timed Writing.** A)* keep coming-soon and hidden (they need their own evaluator contract: intent / register checks and a 90 s window); B) Timed Writing first, as the Writing room with a 90 s countdown and the existing review (no new backend), Context Rewrite stays hidden; C) both, with new evaluator prompts and a cost decision.

## 4. Measurements (computed style, design vs app, desktop dark, 1920x1080)

Colour differences are the recorded D-093 AA adjustments (accent text `#847FF6` for `#7D78F5`, accent fill `#6862F3`, muted note); not listed again.

| Component | Design | App | Result |
| --- | --- | --- | --- |
| Back button | 40x40, radius 14 | 40x40, radius 14 | same |
| Header title | 16 / 600 Outfit, h20 | 16 / 600 Outfit | same |
| Header meta | 13 / 400 | 13 / 400 (content differs, W-05) | same style |
| Setup button | h34, 13 / 600, radius 10, pad 0 13 | same | same |
| Review button | h34, 13 / 600, radius 10 | same (disabled fill when under the minimum) | same |
| Draft textarea | 17 / 400, 28.9, radius 20, pad 22 24, 822x508 | same | same |
| Words / saved line | 13 / 400, h16 | 13 / 400, h16 | same |
| Marked card | not measured (source style only) | radius 20, pad 24 26, h360 | not compared |
| Edit draft | h38, 13 / 600, radius 10, pad 10 14 | same | same |
| Keep review | h36, 13 / 600, radius 10, pad 9 12 | same | same |
| Strengths / Priority / Other labels | 13 / 600 | 13 / 600 | same |
| Finding row | h48, radius 14, pad 12 14 | same | same |
| Feedback summary title, score | 15 / 600, 28 / 700 | same | same |
| Dimension chip | h22, radius 5, 13 / 600 | same | same |
| Range line | 13.5 / 400 | 13.5 / 400 | same |
| Next button | h48, 14 / 600, radius 14 | same | same |
| Prompt Setup: input, level chip, Write | h46 radius 14 15px; h42 radius 999 14 / 600; h44 radius 16, 13.33 / 700 | same | same |
| Prompt Setup helper line | 13 / 400 grey | absent | W-05 |
| Compare title (design 16 / 600 h20) | 16 / 600 | 16 / 600, meta 13 / 400, legend card radius 16 | title same; legend card not measured on the design |
| Finding popover | under the span, inside the card | x=1048 of a card ending at 1086 (clipped) | W-10 |

Not measured: Context Rewrite and Timed Writing (no app counterpart); the phone layout of every frame except those in the shots; light theme beyond the shots (a-01, a-19, a-20, d-20, m-09).

## 5. What was not observed

A real review, a failed review, Apply / Accept / re-review (they change the stored draft or call the provider), Ask deeper and the Contextual Orena panel, a Writing
continuation card with a real draft, Chinese writing (Hanzi counter, ZH evaluator refresh), the Skill Hub Write on the design's phone (not reachable in the
prototype), Context Rewrite and Timed Writing on the phone, and any state with real account essays (the account has none; result states used the repository's
captured fixtures through a browser-side mock).


## Lane defaults pending human confirmation

2026-10-07, reason: human: continue without asking; follows D-139 precedent. Provisional and reversible; the human may
override any of them. Implemented on `codex/work` in the commits named below.

| Id | Default | What was done |
| --- | --- | --- |
| HW-1 B (W-01, W-02, W-18) | hubs list the built Write modes in the design's group, with the design's one-line description and no duration | Practice Hub tile and Skill Hub row: "Write freely" group with Continue draft (only while a draft waits; "title - n words"), Prompt, Free Writing, Your Topic; description translated EN / VI / ZH; Write has no measured duration (N-22), so none is drawn. Context Rewrite and Timed Writing stay hidden (not built, D-101 H9). Icons are the design's (`pen-line`, `notebook-pen`). Free Writing opens the room titled "Free writing" (an existing draft is never emptied, so a waiting draft is what opens). |
| HW-2 B (W-04) | Prompt and Your Topic open Prompt Setup first, then the room | `#/write?setup=prompt` / `setup=topic`: the room mounts, the sheet opens over it (Your Topic puts the cursor in the Prompt field), the query is removed from the address so a reload does not reopen it. Free Writing and Continue draft open the room without the sheet. Prompt and Your Topic differ only by that cursor: the design also empties the prompt for Your Topic, which here would delete a waiting draft's task. |
| HW-3 A (W-05) | register and target stay the learner's intent for the visit, shown in the header, not sent to the evaluator | Header meta is now "Prompt - level - register - ~n words - version" as the design draws, from the chosen values only (no invented defaults); `reviewPayload` is unchanged; the helper line stays out (false for register). |
| HW-4 A (W-08, W-09) | system notes follow the interface language; AI text stays as returned | `noReviewYet`, `estimatedRange`, `tooShort*`, `tooLong*`, `appliedToast`, `reviewFailed` moved support to interface (gates `test_orena_copy`, `test_orena_copy_layers`; `test_orena_screen_writing` now checks them per interface language). The Write Recommended card is composed in the interface language from the recommender's intent and focus category (it returns its own sentences in the learning language); a category with no interface label is not named. The evaluator's overall sentence, strength notes and finding WHY / HOW are unchanged. |
| HW-5 A, HW-6 A, HW-7 A | keep current behaviour | no work |
| W-17 | Respond to Content: no entry | recorded in `UI_BACKEND_GAPS.md` (needs a content source decision); the Respond group is absent. |

Defects fixed without a decision: W-03 (Continue showed one card per stored conversation record; same scenario now one
card, newest, with a node test), W-10 (finding popover hangs under the clicked line box of a wrapped span, kept inside the
card, re-placed when its own scrollbar narrows the card; measured inside the card with no horizontal scroll and no page
overflow at 1920x1080, 1366x768, 390x844, 360x740, EN dark), W-14 (a direct load of `#/write*` lights Practice Hub, as the
speaking rooms), W-13 (toast copy as the design, "Dismissed - it won't count as an open issue", translated; made true for
the visit by removing a dismissed finding from the lists, dimension counts and Next bar; it is not persisted, see
`UI_BACKEND_GAPS.md`). W-02 skin: group title (13 / 600 muted, 8px, 20px between groups) and tile / row skin reuse the Speak
measurement (same classes).

Left as they are: W-06 (truthful: "Saved on this device"), W-07 (D-098.6), W-11 and W-12 (HW-5 / HW-6 A), W-15 and W-16
(HW-7 A), W-19 (the cross-skill Orena pass; Orena parked). Test note: `test_orena_writing_workspace` still fails only on its
assertion that reads the human's uncommitted `DESIGN_CONTRACT.md`; with the committed contract it passes, so this change does
not alter it.
