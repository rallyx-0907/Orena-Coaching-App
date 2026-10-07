# Onboarding (Welcome, Account, Languages, Level, Meet Orena) - design audit (D-129 batch)

Read-only audit, 2026-10-07, branch `codex/work`, D-129 section 2 (after the skills, places and cross-skill flows: Onboarding). Method is D-129 section 3; the table is for the human to answer before any fix. Nothing in source was changed.

- Design: `docs/design/canonical-ui/screens/Onboarding.dc.html` (pinned sibling file, 64 KB), read from disk and served on 127.0.0.1:8810 (stopped). Five frames: 01 Welcome, 02 Account, 03 Languages, 04 Level (three phases: intro, 5-question check, result/adjust), 05 Meet Orena. Its state script (`STR`, `QS`, `LV`, `renderVals`, `finish`) was read. The prototype is **dark-only** (no light theme) and has Desktop/Mobile only; its support and interface choices are Vietnamese/English only.
- App: `http://localhost:8021/next#/welcome` (route `welcome`, bare: no rail, top bar, phone header or bar), 1920x1080, 1366x768, 390x844, 360x740 (browser_resize, no touch), interface English (all steps), Vietnamese (Languages), Chinese (Level), light and dark. Interface language was set through `localStorage orena.interface` in the one existing tab and restored to `en`; `data-theme` was toggled in the DOM only; `sessionStorage orena.onboarding.*` was used to jump to a step and cleared.
- **Onboarding was not completed.** Steps were walked with Continue only. No target, support-language or level control was pressed on the app (each writes to the account on tap, see O-08), the Level step's Continue (which saves `declared_level`) and "Go to Today" were never pressed. Step 5 was reached by setting the session step, not by completing step 4. No account setting changed.
- Evidence: `docs/reviews/evidence/onboarding-audit/` (`d-*` design, `a-*` app desktop, `ap-*` app phone; 1.7 MB).

Decisions respected, not re-opened: D-079 (three language layers), D-088/D-089/D-093 (design source, light/dark following the OS, AA accent), D-098 point 8 (self-chosen level; placement check deferred) and point 9 (entry routing), D-099 H2 / D-104 H-1 / D-105 H-19 (declared level stored per learning language; existing learner sees only the Level step via `#/welcome?step=level`; Today banner), HSK 7-9 as one band, D-139 HD-14 (system notes in the interface language), rules 40, 43, 44, 47, 49, 50, UI_BACKEND_GAPS "Onboarding ... Wave B".

## 1. Prototype scenario (5 steps, 11 states, all walked)

| # | Frame | State | Action / transition |
| --- | --- | --- | --- |
| D1 | 01 Welcome | idle | brand aside (desktop) + mark, headline, sub, "Get started", "I already have an account"; no top bar |
| D2 | 02 Account | sign up | top bar (back, 4 bars, "1 / 4"), title, Create account / Log in tabs, Continue with Google, "or with email", name, email, password with Show, hint, Create account (disabled until valid), terms line |
| D3 | 02 Account | log in / busy | tab switch; Google "Connecting to Google..." 1.4 s then step 3; email "Creating your account..." |
| D4 | 03 Languages | idle | two target tiles (En CEFR A1-C2, 中 HSK 1-6 with pinyin), Support language pills (Tiếng Việt, English), Interface language pills (English, Tiếng Việt), info note, Continue; all choices held in local state |
| D5 | 04 Level | intro | "Let's find your level": card "Take a 5-question check", card "I'll pick my level" |
| D6 | 04 Level | check | "Choose the right word", n / 5, 5 progress bars, level chip, sentence with blank (+ pinyin for zh), 3 options, per-answer feedback, Skip, Next / See my level |
| D7 | 04 Level | result with score | "Your level" card (B2, "4 of 5 correct"), "Doesn't feel right? Adjust it", 6-cell grid, description, Retake, Continue |
| D8 | 04 Level | pick (no score) | "Choose your level", 6-cell grid (A1..C2 / HSK 1..6), description, Continue |
| D9 | 05 Meet Orena | greeting | mark, title, sub, template greeting (interface language, level, support language), 3 starter chips, composer, "Skip for now - Go to Today" |
| D10 | 05 Meet Orena | after a question | scripted reply (+ optional lesson card), button becomes accent "Go to Today ->" |
| D11 | 05 Meet Orena | finish | "Setting up your Today..." then Today; chosen settings handed to Today through `localStorage orena.onboarding` |

Phone frames (390x844) are the same frames with the aside hidden and a top bar (back, bars, count) on steps 2-5.

## 2. The same scenario on the app (5 steps; 8 states walked, 6 code-read only)

| # | App | Result | Status |
| --- | --- | --- | --- |
| A1 | Welcome | aside, mark, headline, sub, "Get started" only; matches D1 except the second button | walked |
| A2 | Account | identity card (initial, name, "Signed in on this device"/"with Google", email) + Continue; title "You're signed in" | walked |
| A3 | Languages | two tiles, 12 support pills, 3 interface pills, note, Continue; taps write to the account | walked (no control pressed) |
| A4 | Level | straight on the 6-cell grid ("Choose your level"), description in the support language, Continue (saves `declared_level`) | walked (Continue not pressed) |
| A5 | Meet Orena | mark, title, one template greeting in the support language, "Go to Today ->" | walked (reached by session step) |
| A6 | Level-only mode (`?step=level`) | opens at Level, Continue/Back return to Today | code-read |
| A7 | Chinese learning language: grid HSK 1-6 + HSK 7-9 | `levelsFor` / `LEVELS.zh` | code-read |
| A8 | Pick failure | toast `saveError`, no advance of the pick; 409 retried once | code-read |
| A9 | Level save failure | never blocks, never claims a save | code-read |
| A10 | Finish | clears session keys, `ctx.go(today)`; button disabled while busy, label unchanged | code-read |
| A11 | Entry | `entryRoute`: Welcome when the server says no profile or no learning language, else Today; Today banner opens A6 for a profile with no level | code-read |
| A12 | Back | step - 1; on step 1 Back is absent (no top bar on Welcome) | walked |

Rule 49 (workspace is the viewport): no page scroll or horizontal overflow at 1920x1080, 1366x768, 390x844, 360x740 on every walked step; the Languages step on phones scrolls only inside `[data-scroll-region]` (853 in 744 at 390x844, 903 in 640 at 360x740) with the Continue button pinned inside the viewport.

## 3. Measured parity (frame vs app, desktop, light/AA tokens aside)

Identical: Welcome headline 34/700, sub 16/400, primary button 396x52 radius 16 (font 16/600); step titles 30/700, subtitles 15/400; group labels 13/600, hints 13/400; target tile 48x48 radius 14, glyph 20/700, name 17/600, sub 13; pills 14/600, 42 high, radius 999; level code 17/700, name 12/400, description 13/400; Meet title 26/700; column 460 with 396 content; top bar "n / 4" and step list labels. Differences are the theme tokens only: the prototype is dark-only, the app ships light and dark (D-089), and the accent is the AA value (90,85,227 vs 125,120,245, D-093). The Vietnamese face is `Plus Jakarta Sans` through `:lang(vi)` (documented in `kit/boot.js`). The dark app screenshot (`a-05-meet-desk-dark.jpg`) matches the frame visually; the dark button colour was not re-measured after the repaint.

## 4. Deviations

Classes: MS missing step, WO wrong order, NC component not in the design, WS wrong Visual skin, MST missing state, DB different behaviour. **DEFECT** marks something the audit judges wrong whatever the answer to the decisions below.

| Id | Class | Deviation | Recorded decision / note |
| --- | --- | --- | --- |
| O-01 | MST | Welcome has no "I already have an account" | UI_BACKEND_GAPS (rule 44: no destination behind it); see HO-2 |
| O-02 | DB, NC | Account step is an identity card ("You're signed in", provider line, no credential form, no create/log-in tabs, no Google button, no terms line); the design draws a sign-up/log-in form | production auth is a human gate; the card is not drawn by any frame; HO-2 |
| O-03 | MS | Level has no placement check: no intro (check or pick), no 5-question check, no result card with score, no Retake, no "Adjust it" label | D-098 point 8 (deferred); HO-1 |
| O-04 | MST | Meet Orena has no sub line, no starter chips, no composer, no scripted reply or lesson card; the button is "Go to Today ->" in the accent colour from the start instead of "Skip for now - Go to Today" turning accent after a question | rule 40 (the prototype's regex replies are not behaviour); Orena Intelligence lane; HO-3 |
| O-05 | MST | Finish has no busy label ("Setting up your Today...") | button is disabled only; low |
| O-06 | DB | Support language shows all 12 backend languages as pills (4 rows on a phone) and Interface 3; the design draws 2 and 2 | D-079; D-098 point 3 (a picker above 4) is written for Settings only; HO-6 |
| O-07 | DB | The Chinese tile says "HSK 1-9" where the design says "HSK 1-6"; the level grid ends with one "HSK 7-9" cell | human decision 2026-09-30; accepted, sample copy (D-068) |
| O-08 | DB | Tapping a target or support-language control writes to the account at once (`selectLearningLanguage`, `PATCH learner-profile`) and the Level Continue writes `declared_level`; the design keeps every choice in local state until "Go to Today". Leaving or pressing Back mid-way keeps the changes; a learner who replays Welcome (not reachable from any control today) would change their languages | writes are consistent with the entry rule keying on the profile; HO-4 |
| O-09 | DB, DEFECT | The Level descriptions (and the Meet greeting) follow the **support** language: with an English or Chinese interface and Vietnamese support the grid names are in the interface language and the one-line description under them is Vietnamese (`a-04-level-zh.jpg`). The design draws both in the interface language and its greeting also follows `iface` | `copy.js` classes them as support (explanation); D-139 HD-14 sets the analogous rule that system text is wholly in the interface language; HO-5 |
| O-10 | NC | Level-only mode (`#/welcome?step=level`, back to Today) and the Today banner that opens it are not drawn in Onboarding.dc.html | D-105 H-19 (the banner is Orena.dc.html's); recorded, no action |
| O-11 | NC | Account on the sandbox reads "Local user / Signed in on this device" with an "L" initial | development artefact (authentication disabled on :8021); not a design item |
| O-12 | - | Theme: the pinned onboarding frames are dark-only; the app follows light/dark with the aside always dark as drawn | D-089, not a deviation |

Parity found: step order, step list and labels, top bar (back, 4 bars, "n / 4", absent on Welcome), brand aside (desktop only), phone layout, Languages layout, Level grid, button geometry, title/sub type, 360 and 390 fit, EN/VI/ZH copy of every walked step (no overflow in VI or ZH).

## 5. HUMAN DECISION items

**HO-1 Placement check (O-03).** (a) Keep the self-pick permanently, as D-098 point 8 decided (recommended: the design's questions are sample content and there is no item bank or scoring; shipping them would be invented pedagogy, rule 40). (b) Build a real 5-question check per language (authored items, adjacent-level scoring, EN and ZH) behind an architecture proposal. (c) Offer a check later from Settings, not in onboarding. Recommendation: (a); record the deviation as closed.

**HO-2 Welcome second button and Account form (O-01, O-02).** (a) Keep the identity card and the single button until the production auth decision (recommended). (b) Draw the full credential form and "I already have an account" once the provider and sign-up flow exist. (c) Drop the Account step (4 steps; the design's 5-step list changes). Recommendation: (a); revisit with auth.

**HO-3 Meet Orena (O-04, O-05).** (a) Keep the greeting and one button until the Orena agent has an onboarding surface id and a message path (recommended; matches the "mark and an opening line" brief). (b) Wire the starters and composer to the agent when that exists. (c) Remove step 5 and finish on Level. Recommendation: (a) now, (b) with the Intelligence lane; either way label the button "Skip for now - Go to Today" only if a chat exists.

**HO-4 When choices are saved (O-08).** (a) Keep immediate writes (recommended: nothing is lost, the profile is consistent at every step, and the entry rule depends on the profile existing). (b) Hold target, support and level in the session and write once at the Level Continue, as the design's local state behaves. (c) Write at the Languages Continue. Recommendation: (a); revisit if Welcome ever becomes replayable from Settings.

**HO-5 Language of the Level descriptions and the greeting (O-09, defect).** (a) Interface language for the level descriptions and the greeting, as the frame draws and as HD-14 does for system text (recommended). (b) Keep the support language (the explanation layer). (c) Show both. Recommendation: (a) for the descriptions (they label a choice on a chrome screen); the greeting is Orena speaking and may stay (b) if the human wants the first explanation in the support language, but then the step should say so once.

**HO-6 Length of the support and interface lists (O-06).** (a) Keep wrapped pills for all languages. (b) Pills for the 4 most relevant and a "More" row opening the kit sheet/picker, as D-098 point 3 does in Settings (recommended: same component the design's patterns give, keeps the step short on a phone). (c) Show only the two languages the design draws. Recommendation: (b).

## 6. Code-read only (not reachable without writing to the account or finishing)

A6 level-only mode, A7 the Chinese grid and HSK 7-9 cell, A8 and A9 failure and 409 paths, A10 finish, A11 entry routing, the Chinese-target Meet greeting, offline behaviour, and the interface pill on the Languages step (it calls `chooseInterface`, a device change that was avoided here; the interface was switched through storage instead). Sources: `static/orena/screens/onboarding/{screen,model,copy}.js`, `static/orena/shell/routes.js` (`entryRoute`), `static/orena/screens/today/{screen,model}.js` (level prompt).
