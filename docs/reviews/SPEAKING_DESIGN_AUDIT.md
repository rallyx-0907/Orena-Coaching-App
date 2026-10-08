# Speaking / Pronunciation (with Free Talk) - design audit (D-129 batch)

Read-only audit, 2026-10-07, branch `codex/work`. Method is D-129 section 3 (scenario, same scenario on the app, deviation table);
the table is for the human to answer before any fix (D-129 section 3 "Send the table, then fix"). Nothing was changed in source.

- Design: `docs/design/canonical-ui/screens/Orena.dc.html` + `Compare-With-Model.dc.html` (pin of 2026-09-27), read from disk, served locally.
  Note for the pin: the runtime fetches `Compare With Model.dc.html` (spaces) but the pin is named `Compare-With-Model.dc.html`, so
  frame 16 renders as an empty box when the pin is served as-is. For this audit a scratch copy with the spaced name was served; the pin was not touched.
- App: `http://localhost:8021/next`, desktop 1920x1080 (also 1366x768 for the viewport rule), phone 390x844 with `hasTouch`/`isMobile`
  (light and dark). Interface language English. VI and ZH were not walked (VI strings seen below are the support layer).
- Evidence: `docs/reviews/evidence/speaking-audit/` (`d-*` design desktop, `m-*` design phone, `a-*` app desktop, `ap-*` app phone).
- No audio was recorded and no provider was called. States that need a real take are marked **code-read**.

Decisions respected, not re-opened: D-119 (one shared Compare/recorder room for Shadowing and Scripted Pronunciation), D-120/D-121 (original voice
is the model; truthful "unavailable"), D-137 L-02 (Shadowing stays the shared room), D-138 (Orena voice), D-067/D-068 (design copy is sample content),
D-093 (AA colour adjustments), D-101 H9 (coming-soon entries not drawn), D-076 (audio is not kept; rows from the server cannot be replayed), rules 40-50.

## 1. Prototype scenario (what the design does)

State script: `micGate` wraps `spRecord`, `shStart`, `ftStart`, `prMic`; first use shows the Mic state "permission" sheet, "Allow" runs the action.
Mic scenarios (`MS`): permission, blocked, notheard, noisy, provider, offline. Scripted recording is simulated 4 s, then "processing" 1.3 s, then result.

| # | Screen / frame | State | Learner action | Transition | Shot |
| --- | --- | --- | --- | --- | --- |
| D1 | Practice Hub (Speak section) | idle | opens Practice Hub | 9 Speak modes in a 3x3 grid, each with label, one-line description, duration (Situation Reaction, Conversation, Free Talk, Pronunciation, Shadowing, Sound / Tone, Timed Reaction, Retell, Mock Interview) | d-01, m-01 |
| D2 | Skill Hub "Speak" (frame 09) | idle | (phone only: `phTiles` is not rendered in this revision, so the frame is not reachable by tapping; read from source) | header, "Recommended - ~2 min" card with Start, 3 groups (Speak naturally / Improve pronunciation / Challenge yourself), each row label + duration + chevron; "not built" rows dim to "Soon" | source only |
| D3 | Scripted Pronunciation (frame 15) | idle | taps Pronunciation | header: back, title, "From 'A Morning in the City' - segment 8 - B2", "Compare" (when attempts exist); card "Target sentence" with word buttons (24/600), IPA line, Model / big mic / Mine, waveform strip | d-02, m-03 |
| D4 | Mic state sheet | permission | taps the mic | desktop right panel / phone bottom sheet: "Allow microphone" + "Not now" | d-03, m-04 |
| D5 | Scripted Pronunciation | recording | Allow | pill "Recording 00:01 / 00:04", red mic, 4 s | d-04, m-05 |
| D6 | Scripted Pronunciation | processing | (auto) | "Scoring / Processing..." and "Assessing pronunciation..." | d-05 |
| D7 | Scripted Pronunciation | result | (auto) | tokens underlined green/amber by score; tip for the weakest word with Retry / Hear model; result card: ring 86, "Attempt 3 - Just now", verdict, "Best attempt", Accuracy / Fluency / Completeness bars, "ASR heard ...", [Compare with model] [Retry] [Where am I going wrong?] | d-06, m-06 |
| D8 | Scripted Pronunciation | word detail | taps a word | panel: word, score, "Expected /ipa/", issue, Hear model | d-07 |
| D9 | Compare With Model (frame 16, embedded component) | empty / record | taps Compare (or Compare with model) | record card: tag "English - your script", Hear model, speed, tokens with IPA above, stress hint, mic + "Ready when you are", "Use demo attempt"; below: attempt pills, header "Attempt history" | d-08 |
| D10 | Compare With Model | result | records / demo | summary (ring 90, headline, chips, metric line), model-vs-you pitch tiles per word, Word detail (Pitch / Timing / Pronunciation tabs, Details rows, Hear model / Hear yours), sticky playback bar (Play, Model->You / Word by word / Model only / Yours only, Speed, Try again), embedded Attempt history card | d-09 |
| D11 | Attempt History (frame 41) | list | taps "Attempt history" | stats Attempts / Best / Change, rows (score tile, "Attempt n", Best/Current, accuracy, fluency, pauses), each opens Compare for that attempt; one privacy note | d-10 |
| D12 | Free Talk (frame 29) | setup | Practice Hub -> Free Talk | Topic input + 3 suggestions, Duration 1/2/3 min, "Useful phrases - from your library", Start speaking | d-11 |
| D13 | Free Talk | mic gate, recording | Start -> Allow | clock, wave, "Mic on", round stop button "Tap to finish" | d-12, d-13 |
| D14 | Free Talk | transcript | Tap to finish | editable transcript, Record again / Get feedback | d-14 |
| D15 | Free Talk | result | Get feedback | summary, Words / Pace / Linking, Strengths, Fixes (max 3), "Retry this sentence", Talk again / Ask about this / Finish | d-15 |
| D16 | Speaking Summary (frame 42) | list | Finish | "Speaking session", N tasks, "Use items / Transfer" evidence line, Tasks completed, "Key improvement", next-task button + Back to Practice Hub; empty text "No speaking task finished in this session yet." | d-16 |
| D17 | Conversation (frame 30) | setup | Practice Hub -> Conversation | subtitle "Pick a scenario ...", Scenario cards (label + role), Difficulty B1/B2/C1, Start conversation | d-17 |
| D18 | Conversation | chat | Start | partner speaks first, learner types or taps mic, "..." thinking, "How did that land?" on each learner turn | d-18, d-19 |
| D19 | Conversation | coaching | taps "How did that land?" | Contextual Orena panel opens with "Your turn - Conversation coaching" | d-20 |
| D20 | Conversation | complete | after 4 turns | "Conversation complete" + summary, New scenario / Finish | d-21 |
| D21 | Situation Reaction (frame 31) | input | Practice Hub -> Situation | context chip, scenario (24/700), textarea, Speak (mic, simulated), Submit | d-22 |
| D22 | Situation Reaction | listening / transcribed | Speak | "Listening..." 2 s then transcript in textarea | d-23, d-23b |
| D23 | Situation Reaction | result | Submit | the answer, Intent achieved? / Clarity cards, One useful improvement, Natural alternative, "Transfer evidence recorded", Retry / Try another context / New scenario / Finish | d-24 |
| D24 | Mic state | blocked, notheard, noisy, provider, offline | scenario switch (prototype setting) | each a sheet with title, body, actions (read from the `MS` table; only "permission" walked) | source only |
| D25 | Shadowing (frame 28) | idle, model, speak, result | Practice Hub -> Shadowing | Start lag / Timing match / Speed, One thing to fix, Mine / Phrase rehearsal / Retry, prev / next line (Listening-owned, D-137) | d-25 |
| D26-D29 | Sound / Tone, Timed Reaction, Retell, Mock Interview | idle (first step walked) | open from the hub | frames exist in the prototype; the app has none of them (D-101 H9) | d-26..d-29 |

Scenario step count: 29 (D1-D29), of which the 23 listed in D1-D23 are the Speaking flow proper.
Phone (390x844) was walked on the design for D1 and D3-D7 only (m-01..m-06); the other design frames are laid out by the same component at phone width and were not separately captured.

## 2. The same scenario on the app (`/next`)

| # | Route | State seen | Walked? | Shot |
| --- | --- | --- | --- | --- |
| A1 | `#/practice` (Speak section) | 4 tiles: Free Talk, Conversation, Situation Reaction, Pronunciation; name only, no description or duration | walked | a-01-practice-hub |
| A2 | `#/practice/speak` (Skill Hub) | flat list of the same 4 rows with chevrons; no Recommended card, no groups; breadcrumb "Discover > Practice Hub" on direct load | walked | a-05-skillhub-speak, ap-skillhub |
| A3 | Pronunciation tile -> `#/discover?tab=listen&practice=pronunciation` | media chooser "Choose media to practise speaking." (4 results) | walked | a-02-pronunciation-entry |
| A4 | `#/listen/:id/shadow` = `#/speak/:id` = `#/speak/:id/compare` | one room "Shadowing / Pronunciation" in its idle/record state | walked | a-03-scripted-idle, a-04-route-speak, a-04-route-compare, ap-pron |
| A5 | same room, recording / processing / result / error | recorder, assessment, summary, tiles, word detail, playback bar | **code-read, not walked** (`screens/compare/screen.js`, `product/speaking-recorder.js`) | - |
| A6 | Mic state | "permission" sheet from Free Talk Start speaking (desktop panel, phone bottom sheet 390x366); other five states | permission walked; blocked / notheard / noisy / provider / offline **code-read** (`screens/mic/model.js`, all six exist) | a-08-freetalk-after-start, ap-micsheet-dark |
| A7 | `#/speak/:id/attempts` | stats 0 / - / -, no rows, two notes | walked (empty only); rows **code-read** | a-04-route-attempts, ap-attempts |
| A8 | `#/free-talk` | setup (topic, duration, phrases, Start) | walked | a-06-freetalk-setup, a-07 |
| A9 | Free Talk recording / transcript / feedback / result | | **code-read** (`screens/free-talk/screen.js`; no mic device in the test browser, and recording ends in transcription + AI coaching) | - |
| A10 | `#/speak-summary` | "Speaking - last 7 days", 2 tasks from the account record | walked (with data); empty state **code-read** | a-04-route-summary, ap-summary |
| A11 | `#/conversation` | setup (scenario cards + Start) | walked | a-10-conv-setup, ap-conv |
| A12 | Conversation chat / coaching / complete | | **code-read** (a turn calls the AI partner) | - |
| A13 | `#/situation` | input (scenario, textarea, Speak, Submit) | walked | a-11-situation, ap-situation |
| A14 | Situation transcribing / feedback / result | | **code-read** (`screens/situation/screen.js`) | - |
| A15 | Shadowing / Sound-Tone / Timed Reaction / Retell / Mock Interview | no entry in the app (Shadowing is the same room reached from Listening) | walked (absence) | - |

Viewport rule (rule 49), measured on the walked states: at 1920x1080, 1366x768 and 390x844 the document does not scroll vertically or horizontally
on the room, Free Talk, Conversation, Situation, Attempt History and Speaking Summary (scrollHeight equals innerHeight, no horizontal overflow).
Result states of the room, Free Talk, Conversation and Situation were not measured (they need a real take or AI call).

## 3. Deviations

Classes: missing step, wrong order, component not in design, wrong Visual skin, missing state, different behaviour.

| Id | Frame | Class | Design | App | Evidence | Proposed fix |
| --- | --- | --- | --- | --- | --- | --- |
| S-01 | Skill Hub | missing step | "Recommended - ~2 min" card (title, reason, Start) above the groups | no card | a-05, ap-skillhub | HUMAN DECISION HD-1 |
| S-02 | Skill Hub, Practice Hub Speak | wrong Visual skin | rows with label, one-line description, duration, chevron, under 3 group titles; desktop hub is a 3-column grid with description + duration | flat list or tiles with the name only; Situation icon is `puzzle` (design: `rotate-ccw`), Pronunciation icon `whole-word` (design: `audio-lines`) | d-01, a-01, a-05 | add group titles, description and duration per row from the design's data shape (labels translated, D-068); take the two icons from `lucide-static`; no new colour |
| S-03 | Skill Hub, Practice Hub Speak | wrong order | Situation Reaction, Conversation, Free Talk, then Pronunciation | Free Talk, Conversation, Situation Reaction, Pronunciation | d-01, a-01 | reorder to the design (`speakModes` in `screens/practice/model.js`) |
| S-04 | Skill Hub, Practice Hub Speak | missing step | also Shadowing, Sound / Tone (group "Improve pronunciation"), Timed Reaction, Retell, Mock Interview (group "Challenge yourself") | not offered (D-101 H9 hides deferred modes; Shadowing is only reachable from Listening, D-137) | d-01, a-01 | HUMAN DECISION HD-2 |
| S-05 | Pronunciation entry | different behaviour | Practice -> Pronunciation opens Scripted Pronunciation on a sentence at once | opens a media chooser first, then the room (D-119/D-121: a real segment, never a silent default) | d-02, a-02 | HUMAN DECISION HD-3 |
| S-06 | Scripted Pronunciation (frame 15) | missing step | its own screen: Target sentence card, per-word colour underline, weakest-word tip with Retry / Hear model, Model / Mine buttons, result card (ring, verdict, Best attempt, Accuracy / Fluency / Completeness bars, "ASR heard"), word-tap panel | no such screen; D-119 merges it into the Compare room, which after a take shows the Compare result (ring, chips, metric line, tiles, detail) | d-06, d-07, a-03 | none beyond D-119; listed so the human sees what the merge removed. Confirm the Compare room carries Completeness and "heard" (it does in code: `metricLineFor`, Pronunciation tab) |
| S-07 | Scripted Pronunciation / Compare | missing step | "Where am I going wrong?" Orena entry on the result card | no Orena entry in the room | d-06 | belongs to the cross-skill pass (D-129 section 2, Orena contextual entry points); add then via the existing agent bridge |
| S-08 | Compare room (frames 15/16/28 merged) | component not in design | none of: media title row, "Choose media", "Listen", prev / next line arrows, line dropdown, "Line 1 / 2"; frame 28 puts "Previous line / Next line" at the bottom and has no chooser | all of them stacked above the card (three rows on the phone before the sentence) | a-03, ap-pron | HUMAN DECISION HD-4 |
| S-09 | Compare room, record card | wrong Visual skin | tag is plain text 12.5/600 accent (`English - your script`, h16); header "Attempt history" button has no icon; word tokens 19/600; IPA under each word in JetBrains Mono 12, accent colour; punctuation stays on its word ("stop,") | tag is a filled pill (h28, radius 999, soft fill); header button carries a clock icon; word weight 400 (measured); IPA row shows grey "-" dashes; punctuation is its own token with a gap ("Anna , do you have a pen ?") and "?" wraps alone on the phone | a-03, ap-pron, section 4 | tag as plain text; weight 600; attach punctuation to the preceding word; drop the clock icon; the dashes go (see S-10) |
| S-10 | Compare room, record card | missing state | IPA per word (English) / pinyin (Chinese) and a one-line stress hint ("Stressed words carry the rhythm ...") | English has no IPA, shows "-" dashes; no stress hint | a-03 | HUMAN DECISION HD-5 |
| S-11 | Compare room, record card | component not in design | no translation line | support-language meaning under the tokens ("Anna, ban co but khong?") | a-03 | HUMAN DECISION HD-6 |
| S-12 | Compare room, idle | wrong Visual skin | compact record card: the card is as tall as its content, the mic row sits right under the sentence | the card stretches to the viewport and the record row is pinned to its bottom, leaving a large empty block (desktop 1920x1080 and phone) | a-03, ap-pron | keep the workspace inside the viewport but size the card to its content; scroll only a long result |
| S-13 | Compare room, result | missing state | the component draws an Attempt history card under the playback bar, in addition to the header button to frame 41 | pills + header button + the separate Attempt History route; no embedded card (code-read) | d-09 | HUMAN DECISION HD-7 |
| S-14 | Attempt History | component not in design | subtitle "Scripted pronunciation - tap an attempt to compare ..."; one note: "Raw audio for older attempts follows your privacy settings; scores and transcripts stay available."; every row opens Compare | subtitle is the media title; two notes (a scope note "Up to 50 recent server attempts ..." and a recording-location note), both in the support language (Vietnamese on an English interface); rows that only the account remembers are not tappable and have no chevron (audio is never kept, D-076) | d-10, a-04-route-attempts | drop the scope note (or fold into the one design note); subtitle as drawn; keep non-tappable server rows (D-076). Support-language question is HD-14 |
| S-15 | Speaking Summary | different behaviour | scope is "Speaking session"; evidence line "1 Use item - 0 Transfer - recorded in Progress"; "Key improvement" from the session; next action is the next speaking task ("Try Timed Reaction" / "Scripted pronunciation"); empty text "No speaking task finished in this session yet." | scope is the last 7 days from the account (two identical "Scripted Pronunciation" rows with Accuracy / Fluency); eyebrow "Speaking - last 7 days"; evidence line is "Recent speaking activity." in Vietnamese; next action "Practice more" -> Skill Hub; empty text "Nothing recorded in the last 7 days." | d-16, a-04-route-summary | HUMAN DECISION HD-8 |
| S-16 | Speaking Summary | wrong Visual skin | the tasks card is as tall as its list; the two buttons sit under the list | the card fills the viewport, the two buttons are pinned to the bottom, with a large gap under 2 rows | a-04-route-summary | size the card to its content; the task list scrolls only if long |
| S-17 | Free Talk, result | different behaviour | Words / Pace / Linking (count of linkers) | Linking is always 0 (no detector exists); Words and Pace are measured (code-read) | d-15 | HUMAN DECISION HD-9 |
| S-18 | Free Talk, setup | different behaviour | "Useful phrases" are short phrases from the learner's library | a whole sentence appears as a phrase chip ("With the big bang starting the year and as cheering ...") next to single words | d-11, a-06 | cap by length and unit (phrases and words only) when building `phrases` |
| S-19 | Free Talk, Situation, Conversation | component not in design | the prototype is instant, so draws no wait or failure visuals except "Assessing pronunciation..." in frame 15 | real "transcribing / getting feedback / coaching" and error lines (`s-ft__working`, `t('gettingFeedback')`, `serviceError`, `coachingWorking`) (code-read) | - | keep; restyle to the one drawn pattern (quiet caption + the existing progress treatment), no new component |
| S-20 | Conversation, setup | missing step | Difficulty chips B1 / B2 / C1 | no difficulty row (cosmetic in the prototype; no backend field) | d-17, a-10 | HUMAN DECISION HD-10 |
| S-21 | Conversation, setup | missing step | subtitle "Pick a scenario - partner replies naturally, coaching is separate"; chat subtitle "Cafe - role - level" | setup has no subtitle; chat subtitle is "title - cue" (code-read) | d-17, a-10 | add the setup subtitle (translated); chat subtitle with role and level once S-20 is decided |
| S-22 | Conversation, chat | component not in design | no end control; the chat ends after the scripted turns | an "End" text button in the header, plus a 24-turn cap (code-read) | d-18 | HUMAN DECISION HD-11 |
| S-23 | Conversation, chat | different behaviour | "How did that land?" opens the Contextual Orena panel | coaching renders inline under the turn (carried / landed / another way / next attempt) (code-read); no Conversation surface id in AGENT_CONTRACT | d-20 | HUMAN DECISION HD-12 |
| S-24 | Conversation, chat | different behaviour | the partner speaks first | the situation text appears as the partner bubble and the learner speaks first, because `ConversationIn` requires the learner's turn (code-read) | d-18 | backend gap (an opening partner turn); record in `UI_BACKEND_GAPS.md`, no UI decision needed |
| S-25 | Situation Reaction, input | missing state | context chip above the scenario ("Chat message to a colleague") | no chip (no delivery-mode field in content) (a-11) | d-22, a-11 | HUMAN DECISION HD-13 |
| S-26 | Situation Reaction, result | missing state | "Intent achieved?" and "Clarity" cards, "Transfer evidence recorded" line, "Try another context" | only the answer, "One useful improvement", "Natural alternative", Retry / New scenario / Finish; the grid was removed as a regex / word-count score, the transfer line and "Try another context" have no real source (code-read) | d-24 | HUMAN DECISION HD-13 |
| S-27 | Mic state | different behaviour | one language | title and buttons in the interface language, body in the support language (English title over a Vietnamese body); same for the Attempt History and Summary notes | a-08 | HUMAN DECISION HD-14 |
| S-28 | Shell, speaking rooms | different behaviour | the rail keeps "Practice Hub" selected inside the rooms | correct when opened from Practice Hub (checked on Free Talk), but a direct load or reload of any speaking route highlights "Discover" | a-04-route-*, a-06 | when no origin is known, a speaking route's fallback origin is Practice Hub (rule 47) |

Not deviations (checked): the Mic state "permission" sheet matches the design (desktop right panel, phone bottom sheet, same title, body, two actions);
Free Talk, Conversation and Situation headers, inputs, pills, durations, textarea and buttons match in size, weight and radius (section 4);
Free Talk result (Words / Pace, Strengths, Fixes, Retry this sentence, Talk again / Ask about this / Finish) follows the frame; "Demo ASR" and "simulated" are
prototype self-disclosure and rightly absent; all six Mic states exist in the app.

### HUMAN DECISION items (options only)

- **HD-1 (S-01) Recommended card.** A) show the learner's weakest recorded line or mode from real attempts (a real reason line); B) show "continue where you left" for speaking only; C) omit until a recommender exists and log it in `UI_BACKEND_GAPS.md`.
- **HD-2 (S-04) Modes the design draws that the app hides.** A) keep hidden (D-101 H9); B) draw them as dimmed "Soon" rows as the Skill Hub does for "not built" modes; C) show only Shadowing, opening the same shared room through the media chooser (D-137 L-02).
- **HD-3 (S-05) Pronunciation entry.** A) keep the chooser (D-119/D-121); B) open the learner's last line directly and put "Choose media" behind a "..." control; C) chooser only on first use, then remember the line.
- **HD-4 (S-08) Source bar in the room.** A) prev / next at the bottom as frame 28, line list and "Choose media" in a sheet behind "..."; B) prev / next only, no dropdown, chooser reached through Back; C) keep as built.
- **HD-5 (S-10) IPA / stress hint.** A) take IPA from the assessment provider's phonemes where it returns them and hide the row otherwise (no dashes); B) dictionary IPA per word; C) drop the IPA row and hint for English until a source exists (Chinese keeps pinyin).
- **HD-6 (S-11) Translation line under the sentence.** A) keep as a support aid; B) move behind a "..." / tap-to-reveal; C) remove (the design shows the stress hint there instead).
- **HD-7 (S-13) Attempt history inside Compare.** A) add the card as drawn (same takes plus account rows); B) keep the header button and frame 41 only; C) card on desktop, route only on the phone.
- **HD-8 (S-15) Summary scope.** A) this session only, as drawn; B) last 7 days (current); C) the session while it is open, the last 7 days when it is empty.
- **HD-9 (S-17) Linking tile.** A) hide the tile until a linker detector exists; B) count linking words from the transcript with a language adapter (English and Chinese); C) keep showing 0.
- **HD-10 (S-20) Conversation difficulty.** A) omit and record the gap; B) wire B1 / B2 / C1 into the conversation-turn prompt; C) derive the level from the learner profile and show it as the header subtitle only.
- **HD-11 (S-22) "End" control.** A) keep the text button; B) remove it, end by the turn cap or Back; C) put "End" in the composer row when at least one turn exists.
- **HD-12 (S-23) Conversation coaching.** A) keep inline; B) open the Contextual Orena panel with the turn as context once AGENT_CONTRACT gets a Conversation surface; C) inline now, panel entry added later.
- **HD-13 (S-25, S-26) Situation context chip and result cards.** A) omit (current); B) author a `context` field per scenario and show the chip; add Intent / Clarity cards only if the coaching response carries real judgements; C) generate the cards on request and cache them (D-130 pattern).
- **HD-14 (S-27) Two-language notes.** A) keep the two-layer rule (title in the interface language, explanation in the support language); B) show the whole sheet and notes in the interface language; C) interface language by default, with the support-language line as a second line.

## 4. Measurements (computed style, design vs app, desktop dark, 1920x1080)

Colour differences below are the recorded D-093 AA adjustments (`tokens.css`: accent text `#847FF6` for design `#7D78F5`, accent fill `#6862F3`,
muted note `rgb(133,133,153)` for `rgb(119,119,142)`); they are not listed again as deviations.

| Component | Design | App | Result |
| --- | --- | --- | --- |
| Back button | 40x40, radius 14, 1px border | 40x40, radius 14, 1px border | same |
| Header title (Free Talk, Compare) | 16 / 600 Outfit, h20 | 16 / 600 Outfit, h20 | same |
| Attempt History title | 17 / 600 | 17 / 600 | same |
| Header subtitle | 13 / 400, h16 | Free Talk 13 / 400 h16; Compare room 13 / 400 h19.5 | Compare room line-height 1.5 vs design 1.23 (S-09 family, minor) |
| Free Talk input | h46, radius 14, 16px, pad 0 18 | same | same |
| Topic suggestion pill | h36, 13 / 600, radius 999 | same | same |
| Duration pill (on / off) | h42, 14 / 600, radius 999 | same | same |
| Free Talk Start button | h56, 16 / 600, radius 16 | same | same |
| Conversation scenario card | h65, radius 14, 15 / 600 label | same | same |
| Situation scenario | 24 / 700 | 24 / 700 | same |
| Situation textarea | 17 / 400, radius 16, pad 18, h114.5 | same | same |
| Speak button | h46, 14 / 600, radius 14 | same | same |
| Submit button | h45, 15 / 600, radius 16 | same | same |
| Compare tag | 12.5 / 600, no fill, h16 | 12.5 / 600, filled, h28, radius 999, pad 0 12 | different (S-09) |
| Hear model button | h40, 14 / 600, radius 12 | same | same |
| Speed button | h40, w52, 13 / 600, radius 12 | same | same |
| Word token (record card) | 19 / **600** | 19 / **400** | different (S-09) |
| IPA / reading row | JetBrains Mono 12, accent colour, real IPA | JetBrains Mono 12, text3 grey, "-" | different (S-09, S-10) |
| Status title | 16 / 600 | 16 / 600 | same |
| Record button | 72x72 round | 72x72 round | same |
| Attempt History stat card | h70, radius 16, label 12 / 400, value 20 / 700 | same | same |
| Speaking Summary count | 40 / 700 | 40 / 700 | same |
| Summary eyebrow, task label | 13 / 600; 14 / 600 | same | same |
| Summary primary / secondary button | h48 radius 14 15 / 600; h44 radius 12 14 / 600 | same | same |

Design-only reference values for frame 15 (the app has no counterpart, S-06): title 16 / 600; word button 24 / 600 (h39, radius 6); Model / Mine h49, radius 16, 15 / 600;
record button 72 round; score 22 / 700; verdict 20 / 600; Compare with model h46 radius 16 14 / 600; Retry h46 radius 14; "Where am I going wrong?" h40 radius 12 on the soft Orena fill.
Not measured: the Compare result (needs a real take), the Practice Hub tile grid, the phone layout of every frame except the room's idle state, light theme (only seen in the phone captures).

## 5. What was not observed

Real recording, assessment and transcription results; Conversation turns; Free Talk and Situation feedback; Compare result and playback bar; Attempt History rows;
Speaking Summary empty state; five of six Mic states; VI and ZH rendering of the speaking rooms (support-layer Vietnamese text was seen incidentally);
the design frames on the phone beyond D1 and D3-D7. Each is described above only from source.
