# Cross-skill flows - design audit (D-129 section 2, "then the cross-skill flows the design draws")

Read-only audit, 2026-10-07, branch `codex/work`. Method is D-129 section 3; the table is for the human to answer before any fix. Nothing in source was changed.

- Design: `docs/design/canonical-ui/screens/Orena.dc.html` (pin of 2026-09-27), read from disk, served on 127.0.0.1:8804 (stopped). No sibling frame needed. Frames: React / Reuse (33), Respond to Content (45), Content Detail, Listening "Media completed" panel, Reading Complete (40), Speaking Summary (42), Lesson complete (63), Context Transfer (35), From Your Errors (50), Today / Practice Hub / Orena Home. Driven through the prototype's live instance (`__orenaLive`: `nav`, `setState`, `b4.rr`, `b6.rc`); state script read for `startReactHere`, `rrNext`, `rrSubmit`, `rrRetry`, `rrNewContext`, `rcSubmit`, `rcRevise`, `rcAsk`, `rcOpenSource`, `emRespond`, `dPrimary`, `dPrimaryLabel`, `dPractice`, `openRec`, `rcNext`, `rcBackOrigin`, `ssNext`, `lcClose`, `showLC`, `sessGrade`, `todayRecs`, `forYou`, `openMode`.
- App: `http://localhost:8021/next`, desktop 1920x1080 and 1366x768, phone 390x844 and 360x740 (`hasTouch`/`isMobile`), light and dark, interface English and Vietnamese (language set only through `localStorage` `orena.interface` in throw-away browser contexts). Learning language is the account's Chinese HSK3 (not changed), so every walked lesson is a Chinese one.
- **No provider was called and no learner record was written by the audit's own actions.** `/api/dictionary/spoken-response`, `/api/evaluate`, `/api/responses/*` and `/api/speech/*` were intercepted in the browser (mock or abort); "Ask Orena why" and the mic were never pressed; nothing was reviewed, graded, saved or imported.
- **One side effect, reported and reverted.** Opening a room records the learner's place on the account (`/api/continue`), so walking the rooms moved the saved place of two items and created one. I restored the two (`zh-culture-where-are-you-from` back to line :002 and `zh-culture-nationalities` back to :001, both "Pronunciation" places, by reopening their Compare rooms) and cleared the one I created (`article:1f87851c-...`, via the app's own clear call). Their "last opened" times are now today. No setting changed.
- Evidence: `docs/reviews/evidence/cross-skill-audit/` (`d-*` design, `a-*` app desktop, `m-*` app size matrix at 1920/1366/390/360).

Decisions respected, not re-opened: D-129, D-067/D-068, D-088..D-091, D-093 (AA colour adjustments: accent and ink values differ slightly from the design), D-098/rule 40 (no invented measurements), D-101 H9 (deferred modes not offered), D-104, D-119, D-136 (Reading approved: Reader, Check, Reading Transfer and Discussion internals not reopened; Reading Complete is audited only as a hand-off), D-137 (L-01 two modes, L-02 shared Compare room for Shadowing), D-139 (HD-2, HD-3, HD-8, HD-12, HD-14), D-141, Design Contract rules 43, 44, 47, 49, 50. Already recorded elsewhere and not repeated here: S-15 (Speaking Summary next action), W-03 / W-17 (Write hub: Continue draft, Respond entry), V-01 / V-21 / V-22 (Context Transfer and From Your Errors have no hub entry; Context Transfer is Coming soon), UI_BACKEND_GAPS "React / Reuse has no `available_modes` gate".

**Parked, listed without deviations (human instruction):** Orena Intelligence and the contextual Orena entry points. In this scope: "Ask Orena why" in Respond (agent bridge, not exercised), the contextual panel opened from Respond, Free Talk and the Listening line "Explain", Orena Home's action chips (the design's own path into From Your Errors, `openMode("From your errors")`), Orena Voice.

## 1. Prototype scenario (31 steps, all walked on the prototype)

| # | Frame | State | Action / transition |
| --- | --- | --- | --- |
| D1 | Listening Workspace, selected line | idle | pills Vocabulary Focus, Dictation, Explain, Shadowing, React / Reuse (`startReactHere`, segment = selected line) |
| D2 | Practice Hub, Listen | idle | tile "React / Reuse - Understand -> reveal -> reuse in a new context" (opens segment 8) |
| D3 | React / Reuse | Listen | header "React / Reuse", "title - segment n"; 5-step bar Listen / Understand / Reveal / New context / Result; "Audio first..."; round play + waveform; "I've listened" |
| D4 | React / Reuse | Understand | "What does the speaker mean?", 3 translation options |
| D5 | React / Reuse | Understand, answered | green / red options, "Correct" or "Not quite...", Reveal |
| D6 | React / Reuse | Reveal | transcript with the phrase marked, translation, "Useful phrase" callout, "New context" |
| D7 | React / Reuse | New context | chip, prompt, textarea, Speak + "mic is simulated..." note, Check |
| D8 | React / Reuse | Result | echo of the answer, tiles "Intent achieved?" / "Phrase reused?" (Yes / Say a bit more / Not this time), "One natural alternative", Retry / New context / Finish |
| D9 | React / Reuse | Retry, New context, Finish | Retry and New context return to step 3 (New context on the other prompt); Finish -> Practice Hub (`go.practice`); Back -> previous |
| D10 | Respond to Content | edit | header "Respond to content / source - source stays linked to your writing"; chips Opinion / Summary / Reaction / Continuation; prompt; textarea "Write 60-150 words..."; "n words"; Get feedback; right column "Source - Video transcript" with 3-4 lines and "Open source" |
| D11 | Respond to Content | kind switch | another kind is another task: prompt changes, result cleared |
| D12 | Respond to Content | result | tiles Words / Uses the source / Fixes; fix rows; "Next step"; Revise / Ask Orena why / Done |
| D13 | Respond to Content | Revise, Open source, Done | Revise -> edit; Open source: video -> Listening room, text -> back; Done -> back |
| D14 | Respond to Content | phone | same frame stacked: source under the card |
| D15 | Entries to Respond | idle | Listening "Media completed" -> "Write a response to this video" (`emRespond`); Reader More menu -> "Write a response"; Reader bottom (`rdWrite`); Practice Hub Write -> "Respond to Content" |
| D16 | Content Detail | media, started | hero, progress + "Resume at 0:44", primary "Continue watching - 0:44" (`openMain(44)`), Save, Transcript preview, Related |
| D17 | Content Detail | article, unstarted | primary "Start reading" / "Read" (+ "Practice this text" when `pt`), Save, Related |
| D18 | Content Detail | all kinds | draws only primary, "Practice this text", Save: no Dictation, Shadowing, Write or Vocabulary entry |
| D19 | Listening, "Media completed" | idle | 3 tiles, "Write a response to this video", next recommendation (-> Content Detail), Replay / Dictation / Review saved / Discover |
| D20 | Reading Complete | idle | "Session complete", 3 tiles, "Next - same theme" (-> Discover, Read tab), Review saved words, Reading Transfer, "Back to {origin}" |
| D21 | Speaking Summary | list | one next-task button ("Try Timed Reaction" / "Scripted pronunciation") + Back to Practice Hub |
| D22 | Lesson complete | modal | after the last review grade (350 ms) and after Check Understanding; score, XP, words, min; Continue only dismisses (`lcClose`) |
| D23 | Writing | review / compare | the design draws no "done -> next" for Writing |
| D24 | Context Transfer | input, result | hand-off only: Practice Hub Vocabulary "Context Transfer", Library Active use, Orena action map |
| D25 | From Your Errors | question, result, done | hand-off only: Orena action map (`openMode`); the `focused` list in the state script is drawn nowhere |
| D26 | Today | Recommended, For you | hero rows (Dictation, Review, Read) open their room; For you "Video - Continue - 0:44 left" -> Content Detail; "Write - Continue: Describe your ideal weekend" -> Writing |
| D27 | Practice Hub | Continue learning | rows with a place open the room (Listening 0:44, Writing draft) |
| D28 | Loading | lesson routes | "Preparing your lesson" skeleton before a lesson route (700 ms) |
| D29 | React / Reuse, Respond | phone 390 | stacked frames; Done wraps under the secondary buttons |
| D30 | Light / dark | all | same frames in both themes |
| D31 | Rail and focus | rule 47 | React, Respond, Reading Complete, Speaking Summary are focus rooms (rail only) |

## 2. The same scenario on the app (28 steps; 7 code-read only)

| # | App | Result | Status |
| --- | --- | --- | --- |
| A1 | Listening line "Work on this line" -> "..." -> "React / Reuse" | opens `#/listen/:id/react?seg=` with the selected line | walked |
| A2 | Practice Hub, Listen | "Listening comprehension", "Dictation" only; no React / Reuse tile | walked (absence) |
| A3 | React, steps 1-5 | 5-step bar; Listen (play control, waveform), Understand (translation choices), Reveal, New context (chip, prompt, textarea, Speak, Check), Result; Understand skipped for a 2-line lesson | walked (check mocked) |
| A4 | React, Retry / New context / Finish / Back | Retry and New context return to step 3 (second prompt for New context); Finish -> `#/practice`; Back -> history | walked |
| A5 | React, Understand choices | not reachable on the walked lesson (2 lines, no distractors) | code-read (`react/model.js`) |
| A6 | React, error / mic states | "coachingError" text; mic sheets `provider` / `notheard` | code-read |
| A7 | Respond, edit / kind switch / result | chips, prompt, textarea, count, Get feedback, source column with "Open source"; result with 3 tiles, fixes, Next step, Revise, Ask Orena why, Done | walked (evaluation mocked) |
| A8 | Respond, Done / Back / Open source | Done and Back -> where it came from (Listening room from the end panel; Today on a direct load); Open source (media) -> `#/listen/:id` | walked |
| A9 | Respond, "Ask Orena why", error toast | agent bridge (parked); "feedbackError" toast | code-read |
| A10 | Respond entries | Listening end panel (walked), Reader More menu and Check Understanding (code-read, `reader/screen.js`, `check/screen.js`); Practice Hub Write: absent (W-17) | mixed |
| A11 | Content Detail media / article / started / finished / own import | primary, "Shadowing" (media), "Practice this text" (when a set exists), Save, "..." (own import); no Dictation, Write or Vocabulary entry | walked |
| A12 | Content Detail -> Start listening / Shadowing / Start reading and Back | `#/listen/:id`, `#/listen/:id/shadow`, `#/read/:id`; Back returns to Content Detail every time | walked |
| A13 | Content Detail, media with a saved place | "Start listening", no progress strip (3 items checked, all with a saved place) | walked (defect, X-14) |
| A14 | Listening "Media completed" | reached by playing the last line to its end; tiles, Write a response, next row, Replay / Dictation / Review saved / Discover | walked (desktop); phone code-read (card scrolls inside its own region) |
| A15 | End panel actions | Write a response -> Respond (Back returns to the room); Replay in place; Dictation -> `#/listen/:id/dictation`; Review saved -> `#/library`; next -> Content Detail; Discover -> `#/discover` | walked (next / Discover code-read) |
| A16 | Reading Complete | tiles, Next, Review saved words, Reading Transfer, "Back to Today" | walked |
| A17 | Reading Complete actions | Next -> Content Detail of the next article; Review -> `#/review?words=`; Transfer -> `#/read/:id/transfer`; Back -> origin | walked |
| A18 | Speaking Summary | "Practice more" -> Skill Hub Speak + Back to Practice Hub (S-15) | code-read |
| A19 | Lesson complete (Review, Check) | centred modal, measured facts only, Continue dismisses (no `next`) | code-read (needs real grades) |
| A20 | Writing done | no "next" in the app and none in the design | code-read |
| A21 | Context Transfer, From Your Errors | Coming soon route, hidden entries; From Your Errors reviewable with no learner entry (V-21, V-22) | code-read |
| A22 | Today Continue | cards open the room at the saved place: a Compare place -> `#/speak/:id/compare?segment=`; a Listening place -> `#/listen/:id` (restores the saved line); grammar / conversation by id | walked |
| A23 | Today For you, reading and writing | no card for an unfinished article, book or writing draft (5 unfinished articles exist; Practice Hub "Continue learning" shows them) | walked (reading), code-read (draft) |
| A24 | Today hero "Read" | `#/read/:id?rec=...` | walked |
| A25 | Size matrix | React (4 steps), Respond (edit, result), Content Detail, Reading Complete at 1920, 1366, 390, 360 x en, vi x dark, light: no page scroll, no horizontal overflow, primary buttons inside the viewport | walked |
| A26 | Measurement | React and Respond main components against the frames | walked (section 4) |
| A27 | Loading skeleton | design draws "Preparing your lesson" on lesson routes; the app shows its own load state (Places audit D27) | not repeated |
| A28 | Rule 47 | React, Respond, Reading Complete, Summary show the rail and no top bar / phone bar | walked |

## 3. Deviations

Classes: missing step, wrong order, component not in the design, wrong Visual skin, missing state, different behaviour. **DEFECT** marks a broken or wrong destination, a lost return or a lost place.

| ID | Flow | Class | Design | App | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| X-01 | React / Reuse, entry | missing step | tile "React / Reuse" in Practice Hub, Listen | no hub tile; the only entry is Listening's selected-line "..." -> "React / Reuse" (the design also puts it beside Shadowing; D-137 L-01 keeps line actions behind "Work on this line"). No `available_modes` gate (UI_BACKEND_GAPS) | d-practice-hub, a-practice-hub | HUMAN DECISION HX-1 |
| X-02 | React / Reuse, steps | missing step | always 5 steps | Listen is skipped when the media cannot be played and Understand when fewer than two other translated lines exist (the walked 2-line lesson went Listen -> Reveal); the 5-label bar is still drawn | a-react-1-understand | keep (honest; documented in `react/screen.js`, rule 40) |
| X-03 | React / Reuse, Result | different behaviour | "Intent achieved?" Yes / Say a bit more | the tile shows a bare "0" (no endpoint measures intent) | a-react-4-result | HUMAN DECISION HX-2 |
| X-04 | React / Reuse, Result | component not in design | "One natural alternative" only | adds "What carried", "What would land differently" (with "instead"), "Try next time" blocks from the coaching payload | a-react-4-result | HUMAN DECISION HX-3 |
| X-05 | React / Reuse and Respond | missing state | no error state drawn (the global Load error frame only) | React draws a one-line "coachingError" / "not prepared" text in the result; Respond keeps the text and shows a toast | code-read | keep, recorded (truthful, no invented chrome beyond one line / the drawn toast) |
| X-06 | React / Reuse, phone 360 | wrong Visual skin | step labels on one line | "Understand" breaks mid-word ("Understan / d") at 360 in English; the other 4 labels fit | m-react-result-360 | **DEFECT (visual)**: shrink the label or let the bar wrap by word; also check Vietnamese "Hiểu" labels |
| X-07 | React / Reuse, measure | wrong Visual skin | Finish 14px / 46 high; "I've listened" 61 high (full-row) | Finish 15px / 45 high; "I've listened" 45 high | section 4 | fix with the batch (no decision) |
| X-08 | Respond to Content, Result | different behaviour | "Uses the source" Yes / Barely / No | bare "0" (no endpoint measures it); "Fixes" and "Words" are measured | a-respond-result | HUMAN DECISION HX-2 |
| X-09 | Respond to Content, Result | different behaviour | "Ask Orena why" always | shown only when the evaluation returned an id (parked with the Orena entries) | code-read | parked |
| X-10 | Content Detail, media | component not in design | primary, "Practice this text", Save only | adds a "Shadowing" secondary button for transcript-backed media (D-119 offers Shadowing from the media; the frame does not draw the button) | a-detail-media | HUMAN DECISION HX-4 |
| X-11 | Content Detail -> Listening | missing state | saved place: progress strip, "Resume at 0:44", primary "Continue watching - 0:44" | media with a saved place show "Start listening" and no strip: `placeFor` needs `place.within`, media places carry only a segment. The copy "Continue watching / listening" exists and is never reached for media. Today / Practice Hub call the same item "Continue" | a-detail-media, a-detail-media-youtube | **DEFECT (lost place)**: derive "Resume at" from the saved segment's start; no decision |
| X-12 | Content Detail, finished article | missing state | no finished state drawn | "Continue reading", strip "100% complete", label "Resume" | a-detail-article-fin | low; follows X-11's fix (show "Read again" or no strip) |
| X-13 | Today / Discover "Continue" -> room | different behaviour | "Continue - 0:44 left" opens Content Detail, whose primary resumes at 0:44 (2 steps) | the card opens the room directly at the saved place (a Compare place opens Compare, a Listening place the Listening line); exact line restore verified | a-cont-compare, a-cont-listen-wiki | HUMAN DECISION HX-5 |
| X-14 | Today, For you | missing step | "Write - Continue: Describe your ideal weekend" -> Writing | no card for a writing draft (`mapContinuationEntry` has no draft branch); reading places are not drawn on Today in the design either | code-read | follows W-03 (Continue draft); add with it, no decision |
| X-15 | Listening "Media completed", next row | different behaviour | "Next - because you finished a Daily life video" (one language) | the eyebrow is in the support language (Vietnamese under an English interface: "Tiep theo - vi ban vua hoc xong mot bai ve culture") and the topic is a raw slug ("culture"); everything else on the panel follows the interface language | a-listen-ended | HUMAN DECISION HX-6 |
| X-16 | Reading Complete (hand-off only) | different behaviour | "Next - same theme" -> Discover (Read tab); Review saved words always drawn | Next opens the next article or chapter's Content Detail; "Review saved words" only when this text kept words; "same theme" only when real | a-rcomplete | recorded under D-136, not reopened |
| X-17 | Speaking Summary, Lesson complete, Writing done | no deviation | next action / Continue dismisses / none | Summary next action is S-15; Lesson complete and Writing match | code-read | none |
| X-18 | Content Detail -> Dictation / Write / Vocabulary | no deviation | none drawn | none built (no invented entry) | a-detail-media | none |
| X-19 | Context Transfer, From Your Errors (entries) | missing step | entries in Practice Hub Vocabulary / Library Active use (Transfer) and Orena (Errors) | Transfer hidden (HV-6 A); Errors reviewable, no learner entry | code-read | V-21, V-22; Orena entry parked |

Returns checked and correct: React Back and Finish (Practice Hub, as `go.practice`), Respond Back and Done, Content Detail -> Listening / Shadowing / Reader and Back (all return to Content Detail), end panel -> Respond -> Back (the room, panel closed), Reading Complete -> Review / Transfer / Back to origin. Place restore checked: Compare opens at the saved line (:001 = "Line 2 / 2"), Listening opens on the saved line.

## 4. Measurements (dark, 1920x1080, English; computed style, design against app)

Main components of React / Reuse (frame 33, steps Listen, Reveal, New context, Result) and Respond to Content (frame 45, edit and result):

| Component | Design | App | Difference |
| --- | --- | --- | --- |
| React header title | 16 / 600 | 16 / 600 | none |
| React step label ("New context" chip) | 12 / 600 | 12 / 600 | none |
| React Check button | 15 / 600, 45 high, radius 16, pad 13/22 | same | none (fill is the AA-adjusted accent, D-093) |
| React Speak button | 14 / 600, radius 14 | 14 / 600, 46 high, radius 14 | none |
| React Retry / New context | 14 / 600, radius 14 | same | none |
| React Finish | 14 / 600, 46 high, pad 13/20 | 15 / 600, 45 high, pad 13/22 | X-07 |
| React "I've listened" | 61 high | 45 high | X-07 |
| Respond title | 17 / 600 | 17 / 600 | none |
| Respond kind chip | 14 / 600, outline pill | 14 / 600, 36 high, radius 999, pad 0/14 | none by button box; colour is the AA value |
| Respond Get feedback / Done | 15 / 600, 48 high, radius 14, pad 0/20 | same | none (fill AA-adjusted) |
| Respond Revise / Open source | 14 / 600, 44 high, radius 12, 1px border | same | none |
| Respond source lines | Literata + Noto Serif SC, 15 / 25.5 | same | none |
| Respond tiles label | 12 / 400 | 12 / 400 | none |

Everything else measured is equal or differs only by the D-093 AA accent. Size matrix (React 4 steps, Respond 2 states, Content Detail, Reading Complete; 4 sizes x en, vi x dark, light): no page scroll, no horizontal overflow, every primary button inside the viewport; one label issue (X-06). The end panel's phone sizes were not walked (it could not be reached again after the first run: the lesson's place was already at its last line); its card scrolls inside its own region by CSS.

## 5. Human decisions

- **HX-1 (X-01) React / Reuse entry.** A) add "React / Reuse" to Practice Hub Listen, opening the learner's last Listening line, the media chooser only when there is none (the HD-3 pattern); B) keep only the Listening line "..." entry; C) also offer it from Content Detail. Recommendation: A (the design draws the tile; the line entry stays).
- **HX-2 (X-03, X-08) The two unmeasured result tiles.** A) hide the tile until a real measurement exists (React "Intent achieved?", Respond "Uses the source"); B) keep the bare 0; C) derive a heuristic (term overlap for "Uses the source"). Recommendation: A (a bare 0 reads as a failed score; rule 40 forbids inventing a value).
- **HX-3 (X-04) React result detail.** A) keep the three blocks (the same coaching Free Talk and Conversation show inline, HD-12); B) remove them and keep only "One natural alternative"; C) put them behind "..." . Recommendation: A for consistency with HD-12, to be moved with Orena when its panel entry lands.
- **HX-4 (X-10) "Shadowing" on Content Detail.** A) keep as built; B) remove (Shadowing stays in Listening's mode switch and the Speak hub); C) move behind "...". Recommendation: C (rule 4: behaviour with no place in the source goes behind "...", and D-119 keeps the route).
- **HX-5 (X-13) "Continue" cards.** A) keep: the card opens the room at the saved place; B) as drawn: Content Detail first, then the room; C) room for in-progress items, Content Detail for the rest. Recommendation: A (one step fewer, exact line restore is verified, D-104 places); record it as the approved difference.
- **HX-6 (X-15) Language of the end panel's next row.** A) interface language for the eyebrow and a translated or omitted topic (HD-14); B) keep the support language. Recommendation: A.

## 6. Not walked

Lesson complete after a real review / check (grading writes learner data), Speaking Summary with data, React Understand choices and error states, Respond error toast, "Ask Orena why", the mic and its sheets, the end panel on phones, Reader menu and Check Understanding entries to Respond (code-read), Today's writing-draft Continue, Vietnamese and Chinese of the Reading Complete / Respond copy beyond the size matrix (Vietnamese walked; Chinese interface not walked in this batch).
