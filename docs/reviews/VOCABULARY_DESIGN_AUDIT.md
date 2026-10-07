# Vocabulary / Review (with Word Detail, Quick Sheet, Feed, Collections, Timed Recall, Context Transfer, From Your Errors, Stroke Practice) - design audit (D-129 batch)

Read-only audit, 2026-10-07, branch `codex/work`. Method is D-129 section 3 (scenario, same scenario on the app, deviation table); the table is for the human to answer before any fix. Nothing in source was changed.

- Design: `docs/design/canonical-ui/screens/Orena.dc.html` (pin of 2026-09-27), read from disk, served on 127.0.0.1:8800 (stopped). No sibling frame needed. Frames: Review Session (13), Word Detail (22), Word Quick Sheet, Vocabulary Focus, Vocabulary Daily Feed (36), Timed Recall (34), Context Transfer (35), Stroke Practice, From Your Errors (50), My Library vocabulary tabs (12), Collection Detail (21), Practice Hub Vocabulary tiles and Skill Hub Vocabulary (`SK.Vocabulary`). Driven through the prototype's live instance (`__orenaLive`).
- App: `http://localhost:8021/next`, desktop 1920x1080 and 1366x768, phone 390x844 and 360x740 (`hasTouch`/`isMobile`), light and dark, interface English and Vietnamese (set through `localStorage` `orena.interface` in throw-away browser contexts; the account setting was not touched, nothing to restore).
- Content language: the first browser profile showed English B1 (3 saved items, 0 due); fresh contexts showed the account default, Chinese HSK3 with 15 real due words. Both were used. Learning language was not changed.
- **No learner state was changed.** Review grades were never sent: `POST /api/library/vocabulary/{word}/review` was answered by a browser-side route mock (0 requests reached the server). On the English profile (0 due) the due list was also mocked in the browser (real saved items marked due) to walk question, hint, answer, grade and done states; labelled **mock-walked**. No provider call, no generation.
- Evidence: `docs/reviews/evidence/vocabulary-audit/` (`d-*`, `m-*` design desktop / phone; `a-*` app English profile; `z-*`, `dv-*`, `pv-*`, `s1366-*`, `s360-*` app Chinese profile; `ap-*` phone).

Decisions respected, not re-opened: D-129, D-067/D-068, D-124 (meaning is one localization; a meaning not in the support language says which language it is, hence the "English" chip), D-101 H9 (coming-soon entries not drawn in hubs), D-139 HD-14 (system notes in the interface language), D-093 (AA colour adjustments), rule 40 (no invented intervals), rule 47, rule 49, rule 50 (cut explainer lines: "Items marked Again come back sooner", Feed's "Tap to reveal", "Modes: ..." line, library subtitle), N-11 (no "Mark as known"), three-grade scheduler (DECISION_LOG D-100-era item 9; UI_BACKEND_GAPS: `again` / `unsure` / `got_it`, "Easy" dropped).

## 1. Prototype scenario (30 steps, all walked on the prototype)

| # | Frame | State | Action / transition |
| --- | --- | --- | --- |
| D1 | Practice Hub, Vocabulary | idle | 6 tiles with label, one-line meta, duration: Due Review, Timed Recall, Context Transfer, Daily Feed, Collections, Saved language |
| D2 | Skill Hub Vocabulary (phone) | idle | "Recommended - Review 6 due items" card + groups Recall / Use / Browse |
| D3 | My Library | tabs | Saved content / Saved language / Collections / Active use / Due Review - n, subtitle line |
| D4 | Due Review tab | idle | "Due now" panel, n items, words / phrases / source-aware, Start review - ~3 min, Modes line, "In this session" list of the due items |
| D5 | Saved language | list | word / phrase rows, source, mastery bars or NEW, play; empty state |
| D6 | Collections | list | curated collection cards |
| D7 | Active use | list | 4 stage cards (Recall, Use, Transfer, Fast retrieval) |
| D8 | Collection Detail | idle | cover, level, count, progress, Start review - n, Save, description, word rows |
| D9 | Review | question (target) | progress, 4 px bar, card with prompt, cue, Hint, Reveal |
| D10 | Review | hint | hint line on the card |
| D11 | Review | answer | card becomes the word card (play, save, meaning + vi, example, stroke order for ZH, stage, Mark as known) + Again 1 min / Hard 1 day / Good 3 days / Easy 8 days |
| D12 | Review | source-aware question | cloze sentence, "Which word did the speaker use here?" |
| D13 | Review | grade | next card |
| D14 | Review | session complete | Good / Hard / Again counts, explainer, Review again, Back to Library |
| D15 | Lesson complete | modal, 350 ms after the last grade | "Due review", score %, +XP, words reviewed, min, Continue |
| D16 | Word Detail | idle | card, Context clips + Open, Deep Word, Mastery evidence (5 stages) |
| D17 | Stroke Practice | sheet | character tabs, info, canvas, status, Watch / Write it / Next |
| D18 | Word Quick Sheet | sheet | word card, Save, Ask deeper, Why here, Full word detail |
| D19 | Vocabulary Focus | sheet | terms of a segment, play, save |
| D20 | Daily Feed | front | cards: word, ipa, stage, image, "Tap to reveal...", Hear in context / Save / Detail |
| D21 | Daily Feed | flipped | word card on the back |
| D22 | Timed Recall | question | clock, meaning prompt, input, Enter |
| D23 | Timed Recall | result | label, answer, start / total time, Retry / Next |
| D24 | Timed Recall | done | fast / slow / missed, Run again, Back to Library |
| D25 | Context Transfer | input | context prompt, textarea, mic, Check |
| D26 | Context Transfer | result | label, note, suggestion, Retry / New context / Next word / Finish |
| D27 | From Your Errors | question | pattern chip, source, edit the sentence, Show answer, Check |
| D28 | From Your Errors | result | verdict, struck bad, good, why, Try again / Next |
| D29 | From Your Errors | done | score, rows, Run again, Finish |
| D30 | Stroke Practice | write mode | see D17 |

Phone (390x844) walked on the prototype: D2, D4, D9/D11, D16, D20, D22, D18.

## 2. The same scenario on the app (23 steps; 4 code-read only)

| # | App | Result | Status |
| --- | --- | --- | --- |
| A1 | `#/practice` Vocabulary | 2 tiles: "Review 15 due", "Daily feed"; no meta line, no duration | walked |
| A2 | `#/practice/vocabulary` | 2 rows, no group titles, no Recommended card | walked |
| A3 | `#/library` tabs | same five tabs, no subtitle | walked |
| A4 | Due Review tab | Due now, count, words / phrases / source-aware, "Start review" (no minutes), empty "In this session" | walked |
| A5 | Saved language | rows with mastery bars; phrase rows repeat the phrase as subtitle and show bars | walked |
| A6 | Collections tab | blank (no empty state, no curated collection although one is published) | walked |
| A7 | Active use | 2 of 4 cards (Due review, Situation Reaction) | walked |
| A8 | `#/collection/:id` | cover (placeholder), count, progress, Start review, "Added to my words", rows with "English" chip | walked |
| A9 | `#/review`, 0 due | "Nothing due for review right now" | walked |
| A10 | Review question, hint, answer, grade, cloze | present, three grades with real intervals; Hint only when the card has a gloss | mock-walked (EN), real data (ZH, target mode only) |
| A11 | Review done | Session complete card, no explainer, no Lesson complete modal | mock-walked |
| A12 | Word Detail | card, Context clips, Deep Word, Mastery evidence (real events, not the 5 stages), no Mark as known | walked |
| A13 | Stroke Practice | from Word Detail styled; from Review unstyled | walked (ZH) |
| A14 | Word Quick Sheet, Vocabulary Focus | structure matches the frames (Save, Ask deeper, Why here, Full word detail; terms with play and save) | code-read, not walked |
| A15 | Daily Feed front / flipped | works, no "Tap to reveal" caption | walked |
| A16 | `#/timed-recall`, `#/transfer` | Coming soon; not in the hubs | walked |
| A17 | `#/from-your-errors` | empty state only (no Writing outcome on the account) | walked; active, result and done flows code-read |
| A18 | Grade write, Mark as known | `POST .../review` mocked; "known" has no action (N-11) | code-read |

Viewport rule (rule 49), measured at 1920x1080, 1366x768, 390x844, 360x740: Review (question, answer), Feed, Library and the Word page never scroll the document and never overflow horizontally; Word Detail scrolls inside its own region (a browsing place).

## 3. Deviations

Classes: missing step, wrong order, component not in design, wrong Visual skin, missing state, different behaviour.

| Id | Frame | Class | Design | App | Evidence | Proposed fix |
| --- | --- | --- | --- | --- | --- | --- |
| V-01 | Practice Hub / Skill Hub Vocabulary | missing step | 6 modes: Due Review, Timed Recall, Context Transfer, Daily Feed, Collections, Saved language | Review, Daily feed only | d-18, a-22, ap-skillhub | HUMAN DECISION HV-1 |
| V-02 | Practice Hub / Skill Hub Vocabulary | wrong Visual skin | label + one-line description + duration; group titles Recall / Use / Browse; Recommended "Review 6 due items" with a reason | name only (or "n due"), no description, no groups, no Recommended card | d-18, m-05, a-01 | HUMAN DECISION HV-1 |
| V-03 | Skill Hub | different behaviour | tile is named "Due Review" | "Review" | d-18, a-22 | rename with V-02 |
| V-04 | Review, session end | missing step | Lesson complete modal 350 ms after the last grade (score, words reviewed, min) | none; the Session complete card only (the sheet exists, Check Understanding uses it) | d-06b, a-18, `screens/lesson-complete/sheet.js` | HUMAN DECISION HV-2 |
| V-05 | Review, grades | different behaviour | Again / Hard / Good / Easy, 1 min / 1 day / 3 days / 8 days | Again / Unsure / Got it with the card's real intervals (10 min / 1 day / 3 days) | d-03, a-16 | none (recorded: scheduler has 3 grades, rule 40) |
| V-06 | Review, language layers | different behaviour | one language | cloze cue "Which word fits here?" is in the support language (Vietnamese) under an English interface; D-139 HD-14 made system notes interface-language | a-14 (EN profile) | HUMAN DECISION HV-3 |
| V-07 | Review / Word / Quick Sheet / Feed, stage row | component not in design | no language chip | "English" chip beside a meaning that is not in the support language | z-review-a, dv-review-a, a-21 | none (D-124) |
| V-08 | Review answer | missing step | "Mark as known" link | absent | d-03, a-16 | none (N-11 recorded) |
| V-09 | Stroke Practice from Review (and Feed / Quick Sheet) | wrong Visual skin | styled sheet (header, character tabs, canvas, buttons) | unstyled when reached from `#/review` on a fresh load: `.s-word-*` classes live in `word.css`, which only the Word screen loads (stylesheets loaded: `review.css` only) | z-stroke-sheet, d-25 | defect, no decision: each caller loads the sheet's own stylesheet |
| V-10 | Review, empty | missing state | none drawn (design marks states incomplete) | "Nothing due for review right now" with the shared empty pattern | a-03 | none (D-129 rule: existing pattern) |
| V-11 | Due Review tab | different behaviour | "Start review - ~3 min", "Modes: ..." line | "Start review" without minutes (no measured duration, N-22), no Modes line (rule 50) | d-07, a-13 | none |
| V-12 | Due Review tab | missing step | "In this session" lists the due items with source time and mode | list shows only pinned items, so it is empty with 15 due; "source-aware" counts pinned items | d-07, z-library-due | HUMAN DECISION HV-4 |
| V-13 | Collections tab | different behaviour | curated collection cards | blank, no empty state; the published curated collection is reachable only from Discover (UI_BACKEND_GAPS concept A) | d-09, a-11 | HUMAN DECISION HV-5 |
| V-14 | Active use | missing step | 4 cards incl. Context Transfer, Timed Recall | 2 cards | d-10, a-12 | follows HV-6 |
| V-15 | Saved language | different behaviour | phrase row: source line, no mastery bars | phrase row repeats its own text as subtitle and shows bars | d-08, a-10 | HUMAN DECISION HV-5 (with V-13) or fix as defect |
| V-16 | Word Detail, Mastery evidence | different behaviour | 5 stages (Recognized, Recalled, Used, Transferred, Fast retrieval) with done / not-done notes | real events only (Last reviewed, Recalled n times, Saved) | d-11, a-09 | HUMAN DECISION HV-6 |
| V-17 | Word Detail, context clips | missing state | clips with play and Open | "Context clips - 0 / No context clips yet" on every saved word (no word-to-clip index) | d-11, a-09 | none (BLOCKED index, UI_BACKEND_GAPS) |
| V-18 | Daily Feed | different behaviour | front caption "Tap to reveal meaning and example"; "Hear in context" | caption cut (rule 50); "Play" | d-13, a-05 | none |
| V-19 | Daily Feed, part of speech | different behaviour | one label | combined values such as "noun/verb" shown raw and lowercase in English and Vietnamese; "Adjective" / "Tính từ" translated | dv-feed, s1366-feed | defect: map combined POS through the POS copy |
| V-20 | Timed Recall | missing step | whole flow (clock, input, result, Fast retrieval evidence) | Coming soon, hidden in hubs | d-15, d-19, d-20, a-06 | HUMAN DECISION HV-6 |
| V-21 | Context Transfer | missing step | whole flow | Coming soon, hidden | d-16, d-21, a-07 | HUMAN DECISION HV-6 |
| V-22 | From Your Errors | different behaviour | drills from Writing and Speaking with pattern chips | Writing outcomes only (no Speaking source, recorded gap); empty state when none; no hub entry in Vocabulary / Grammar | d-17, a-08 | none (recorded) |
| V-23 | Collection Detail | different behaviour | "Save" button; description; cover photo | state label "Added to my words"; no description (none in data); placeholder cover | d-12, a-21 | none |
| V-24 | My Library | missing step | subtitle "Everything you've saved..." | absent (rule 50) | d-07, a-04 | none |

Not deviations (measured, dark desktop, colour differences are the D-093 adjustments): Review header 16/600 + 13/400, card 640x340 radius 24, prompt 36/700, Hint and Reveal 48 radius 14 15/600, grade buttons 60 tall radius 14 15/600 + 12 sublabel, word 32/700, meaning 16/400, example Literata 17 / 28.9, progress bar 4 px radius 99, Session complete card; Library tabs 36 / 15 / 500, Due now label 13/600, Start review 56 radius 16 16/600; Collection cover 820x410 radius 24, rows radius 16 pad 14 16; Feed card 300 radius 24 and buttons 38 radius 12; Word Detail card radius 24 pad 24, word 32/700. Phone Review, Library, Feed and Word fit 390x844 and 360x740.

### HUMAN DECISION items (* = recommended)

- **HV-1 (V-01, V-02, V-03) Vocabulary entries.** A) keep Review and Daily feed only; B)* list the built modes as the design draws them, in Recall / Browse groups with description, no duration (Due Review, Daily Feed, Collections, Saved language) and a Recommended "Review n due items" card from the real due count; C) also draw Timed Recall / Context Transfer as dimmed "Soon".
- **HV-2 (V-04) Lesson complete after a review.** A) none; B)* open the existing sheet after the last grade with measured facts only (score from Got it / total, words reviewed, no XP); C) after Back to Library only.
- **HV-3 (V-06) Language layers in Review.** A)* the cloze cue and system notes follow the interface language (as D-139 HD-14), the sentence stays in the content language; B) keep the support-language cue; C) interface cue with a support line.
- **HV-4 (V-12) "In this session".** A)* list the due words (word, and source line when known) from the queue the session will use; B) hide the block when empty; C) keep as built.
- **HV-5 (V-13, V-15) Collections tab and phrases.** A)* show the learner's published curated collections for the content language (and an honest empty state) beside decks; B) keep curated collections in Discover only; C) a separate "Curated" row.
- **HV-6 (V-14, V-16, V-20, V-21) Timed Recall, Context Transfer, 5-stage evidence.** A)* keep coming-soon and hidden until an evidence model exists (needs timing and use/transfer grading contracts); B) Timed Recall first on the existing review endpoint (client timer, no new backend); C) both with new contracts and a cost decision.

## 4. Code-read only

Word Quick Sheet and Vocabulary Focus (structure matches the frames; not walked: no reader / listening content opened), From Your Errors active, result and done flows (no Writing outcomes on the account), grading write path and Mark as known.

## 5. Learner state

None changed. Review grades were mocked in the browser; no request reached `POST .../review`. No setting, language or interface change on the account.

## Lane defaults pending human confirmation

2026-10-07, reason: human: continue without asking; follows D-139 / Writing precedent. Provisional and reversible; the human may override any of them. Implemented on `codex/work`.

| Id | Default | What was done |
| --- | --- | --- |
| HV-1 B (V-01, V-02, V-03) | hubs list the built vocabulary modes in the design's groups, with descriptions; Recommended only from real data | Practice Hub tile and Skill Hub row: Recall (Due Review, with its real due count) and Browse (Daily Feed, Collections, Saved language, the last two opening the Library tabs). "Due Review" replaces the route name "Review". Icons are the design's (`panels-top-left`, `library-big`). No duration is drawn (none measured, N-22). Skill Hub Recommended card "Review n due items" exists only while n > 0, with the plain reason "They are due now." (the design's "Recall is climbing" has no measurement). Timed Recall / Context Transfer stay hidden (D-101 H9). The one-line descriptions of Collections ("Sets of words and phrases") and Saved language ("Words and phrases") are neutral copy: the design's are sample content. |
| HV-2 B (V-04) | Lesson complete sheet after the last grade, measured facts only | 350 ms after the last grade the existing sheet opens over the Session complete card: Got it share, cards reviewed, Got it / Unsure / Again counts, and the time until the soonest graded card returns (the server's `next_review_at`; omitted when offline grades give none). No XP, no minutes. |
| HV-3 A (V-06) | Review cue and system notes follow the interface language | `cueCloze`, `reviewKept`, `reviewSaveFailed` moved support to interface; the sentence stays in the content language. |
| HV-4 A (V-12) | "In this session" lists the due words | The due words of the queue Review builds (limit 50), each with "From your reading / writing feedback" when the saved kind names it; "source-aware" counts the cards that ask a sentence. Pinned items stand in only if the list cannot be read. |
| HV-5 A (V-13, V-15) | Collections tab shows published curated collections, honest empty state; phrase rows do not repeat themselves | Curated collections for the content language lead the tab and open `#/collection/:id`; with nothing at all, "No collections yet." (EN/VI/ZH). A source line equal to the row's own text is dropped. Bars were already shown only for a reviewed item (NEW otherwise), so no further change. |
| HV-6 A | keep Timed Recall, Context Transfer, 5-stage evidence | no work; V-14, V-16, V-17, V-20, V-21 kept. |
| V-05, V-07, V-08, V-10, V-11, V-18, V-22, V-23, V-24 | respected decisions | no change. |

Defects fixed without a decision: V-09 (Stroke Practice from Review loads `word.css` before opening, as Feed and the Quick Sheet already did; measured styled at 1920x1080 and 390x844), V-19 (a combined part of speech such as "noun/verb" is translated part by part and joined by each language's own join, `posJoin`: " / " EN and VI, "/" ZH; a value with any part outside the closed set stays raw, never half-translated; applies to Word, Review, Feed and Quick Sheet).

Test note: expectations in `test_orena_screen_practice` for `vocabularyModes` changed only because HV-1 B adds Collections and Saved language. `test_orena_vocabulary_theme_tokens` still fails as before (its CSS-scope assertion, unrelated to this work).
