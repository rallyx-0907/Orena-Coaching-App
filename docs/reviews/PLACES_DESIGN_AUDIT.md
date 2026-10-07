# Browsing places (Today, Discover, Content Detail, Filter, Search, Notifications, Import, Profile, Settings, Coming soon, Banner / Loading / Load error, shell) - design audit (D-129 batch)

Read-only audit, 2026-10-07, branch `codex/work`, ROADMAP item 4. Method is D-129 section 3; the table is for the human to answer before any fix. Nothing in source was changed.

- Design: `docs/design/canonical-ui/screens/Orena.dc.html` (pin of 2026-09-27), read from disk, served on 127.0.0.1:8802 (stopped). No sibling frame needed. Frames: Today, Discover, Content Detail, Filter Sheet, Search, Notifications, Import (4 steps), Profile, Profile - Today's progress, Settings (5 tabs), Coming soon, Loading, Load error, Banner, desktop rail and top bar, phone header and bottom bar. Driven through the prototype's live instance (`__orenaLive`: `nav`, `setState`); state script read for `todayRecs`, `STT`, `notifDefs`, `FILTERS`, `TABS`, banner rules (line ~2173), `profileActions`, import steps.
- App: `http://localhost:8021/next`, desktop 1920x1080 and 1366x768, phone 390x844 and 360x740 (`hasTouch`/`isMobile`), light and dark, interface English (all screens), Vietnamese and Chinese (text dump of Today, Discover, Profile, Settings, Coming soon, Notifications). The interface language was set only through `localStorage` `orena.interface` in throw-away browser contexts; no account setting was touched, nothing to restore.
- Content account: the account default (Chinese HSK3, 15 due words, 32 reading items, 4-day streak, admin). Learning language was not changed.
- **No learner state was changed.** No import was submitted (Text, URL and File steps opened, Back only; the File chooser opened and was not used), no setting toggled, no review graded, no provider call. Offline was simulated per browser context.
- Evidence: `docs/reviews/evidence/places-audit/` (`d-*` design, `a-*` app desktop, `ap-*` app phone 390).

Decisions respected, not re-opened: D-129, D-067/D-068, D-089..D-091, D-093 (AA colour adjustments, so accent and ink values differ slightly from the design), D-097 (theme row in Settings), D-101 H9 (coming-soon entries not drawn in hubs), D-104, D-139 HD-14 (system notes in the interface language), rules 40, 43, 47, 49, 50, UI_BACKEND_GAPS N-10, N-18, N-21, N-22, N-28, N-29, N-30, N-31, N-32 (goal ring, level/XP, weekly goal, achievements, notification preferences, quota bars, learner-audio delete are recorded gaps and not repeated as deviations). The Accent row in Settings is the approved Visual Skin palette (commit 7857d435), not an invented component.

## 1. Prototype scenario (36 steps, all walked on the prototype)

| # | Frame | State | Action / transition |
| --- | --- | --- | --- |
| D1 | Today | idle | greeting with name eyebrow, date pill, goal ring + 3 skill rings, streak card, level/XP card, Recommended (hero + 2), For you, See all |
| D2 | Today | banner | "Streak at risk." with Start review and dismiss (rule at `rt==="today"&&!met`) |
| D3 | Today | Another (phone only) | cycles the hero |
| D4 | Discover | idle | title + sub, Filters, + Import, search field, 5 tabs, "n items", cards (cover, type chip, duration, progress, source, level, topic) |
| D5 | Discover | banner "New." | info banner with Try it (opens Import) |
| D6 | Discover | filtered / empty | Clear filters; "Nothing matches these filters yet." |
| D7 | Filter Sheet | open | Level, Topic, Content type chips, Clear, "Show n results" |
| D8 | Content Detail | media, started | hero, progress + "Resume at", primary "Continue watching", Practice this text, Save, description, Transcript preview, Related |
| D9 | Content Detail | article, unstarted | primary "Read", description, Related |
| D10 | Search | empty | Recent chips, scope sentence |
| D11 | Search | results | count, groups with kind, title, meta |
| D12 | Search | none | "Nothing found for ..." |
| D13 | Notifications | open | 4-5 rows with kind, time, title, sub, unread dot; Mark all read; close |
| D14 | Import | type | URL / Media, Text, File (not built) |
| D15 | Import | Text | title, paste, language + counts, too-short note, Back, Import to Reader |
| D16 | Import | URL | media URL, error state, demo line, Back, Preview |
| D17 | Import | preview | thumbnail, title, host, "English detected", captions note, Edit, Import and process |
| D18 | Import | processing | stages with status, no-percentage note |
| D19 | Profile | idle | progress hero (4 tiles), identity card, weekly goal, stats, achievements, 6 action rows |
| D20 | Profile - Today's progress | hero | Open Progress, Daily goal, Streak, Due review, This week |
| D21 | Settings | Languages | target, support, interface segmented choices |
| D22 | Settings | Learning | text size, auto-scroll, translation, word highlight, autoplay |
| D23 | Settings | Review | modes, session length |
| D24 | Settings | Notifications | 4 toggles |
| D25 | Settings | Plan & privacy | plan + Manage, 3 quota bars, mic toggle, learner audio, History |
| D26 | Coming soon | idle | icon, chip, title, body, optional "Would resume at", footnote |
| D27 | Loading | lesson routes | skeleton, "Preparing your lesson" |
| D28 | Load error | offline / server | title, text, Back, Retry |
| D29 | Banner | offline / upload failed / goal reached | glyph, title, text, action, dismiss |
| D30 | Rail + top bar | desktop | rail 4 items with badges, Ask Orena card, learner card; top bar breadcrumb, Search, language pill, bell |
| D31 | Phone header + bar | browsing places | logo, search, bell, avatar; Today / Discover / Orena / Practice / Library |
| D32 | Focus (rule 47) | Settings, Search | rail stays, no top bar, no phone header and bar |
| D33-D36 | Phone | Today, Discover, Profile, Settings | same frames at 390 |

## 2. The same scenario on the app (30 steps; 5 code-read only)

| # | App | Result | Status |
| --- | --- | --- | --- |
| A1 | `#/today` | greeting, date, streak card (real, 4 days), hero + 2, For you; no goal ring, level card, name eyebrow | walked |
| A2 | Today banners | none drawn; only the offline banner exists | walked |
| A3 | `#/discover` | header, Filters, + Import, search, tabs, "32 results", cards | walked |
| A4 | Discover filtered / empty | tabs and filters combine (code-read: `model.js`) | code-read |
| A5 | Filter sheet | Level, Topic, Content type, Clear, "Show n results" | walked |
| A6 | `#/content/:id` article | hero (no cover), progress + Resume, Continue reading, Save, Related | walked |
| A7 | Content Detail media | Start listening, Shadowing, Saved, "...", Transcript (Captions - 6 segments) | walked |
| A8 | `#/search` empty / results / none | blank when no recents; "1 result for ..." group; "Nothing found ..." | walked |
| A9 | Notifications sheet | due review + continue-reading rows; no time, dot, Mark all read | walked |
| A10 | Import type / Text / URL | steps and buttons present; File opens a file chooser | walked (not submitted) |
| A11 | Import preview / processing / error | not opened (would call the server) | code-read |
| A12 | `#/profile` | hero, identity (no name), stats, 6 rows | walked |
| A13 | Profile actions | Platform admin, Settings, History, Progress, Plan & privacy, Sign out present; Sign out handler | code-read |
| A14 | `#/settings` Languages | target segmented, support dropdown, interface 3 options | walked |
| A15 | Settings Learning / Review / Notifications / Plan & privacy | all four tabs walked (no toggle pressed) | walked |
| A16 | `#/coming/:key` | icon, chip, title; no body | walked |
| A17 | Offline banner | "You're offline." with dismiss, no Retry | walked |
| A18 | Load error | offline and server texts, Back, Retry | walked |
| A19 | Loading | `kit/states.js loadingMarkup`, "Preparing your lesson" (a throttled run hit the boot screen, not the state) | code-read |
| A20 | Rail, top bar | rail present on all places; top bar on browsing places only | walked |
| A21 | Phone header + bar | present on Today, Discover, Profile; absent on Settings, Search | walked |
| A22 | 360x740 and 390x844 | no horizontal overflow, no document scroll on Today, Discover, Search, Profile, Settings, Coming soon | walked |
| A23 | VI and ZH interface | text dump of 6 places and Notifications | walked |
| A24 | Dark theme | measured | walked |

Measured (dark, desktop, same text styles frame vs app; colour differences are the D-093 adjustments): Today h1 40/700/-1px, p 15/400, h2 20/600, hero 578x216 radius 22, rest cards radius 20, See all 14/600; Discover h1 40/700, sub 16/400, Filters 14/600 radius 14, + Import 90x44 radius 16, search 15/400, tabs 15/600 and 15/500 height 36, cards radius 20; Content Detail primary 728x48 radius 14 16/600, Save radius 14 15/600; Profile Open Progress 14/600 radius 12, Due review tile radius 18, rows 1040x58 radius 16; Settings h1 40/700, tab pills 14/600 radius 999 height 42, choice buttons 13/600. Differences: Today rest cards 131 vs 143 high and For you cards 215 vs 219 (the design's duration and meta lines are not drawn); Discover cards 252 vs 298 (no cover).

## 3. Deviations

Classes: missing step, wrong order, component not in design, wrong Visual skin, missing state, different behaviour. "DEFECT" = fix without a decision.

| Id | Frame | Class | Design | App | Evidence | Proposed fix |
| --- | --- | --- | --- | --- | --- | --- |
| P-01 | Today | missing step | goal ring + skill rings, level/XP card, name eyebrow ("Calis,"), streak card beside the ring | none of the three; streak card full width; no eyebrow | d-today, a-today | none (N-21); eyebrow follows HP-5 |
| P-02 | Today | different behaviour | one language | subtitle "Co 3 viec dang lam ..." and the hero reason "15 tu can on tap" are in the support language under an English or Chinese interface (support-layer keys in `today/copy.js`) | a-today, a-zh-today | HUMAN DECISION HP-1 |
| P-03 | Today, For you / Recommended | missing state | cover photo (or tinted tile), meta "Continue - 0:44 left", duration "~3 min" | cards with no cover draw an empty block under a "Continue" chip; no meta line, no duration | a-today, d-today | cover: HUMAN DECISION HP-3; duration: none (N-22) |
| P-04 | Today | missing step | banner "Streak at risk." | absent (no daily goal to measure) | d-today | none (N-21) |
| P-05 | Discover, cards | missing state | cover, source line, level and topic chips | no cover (blank block), no source line, no topic chip (data), "100%" chip shown as progress | a-discover, d-discover | cover: HP-3; source and topic: none (no data) |
| P-06 | Filter Sheet, Topic | different behaviour | 4 curated topics, capitalised | topics are raw content tags: "conversations", "culture", "sandbox-test", "technology" | a-filter | DEFECT: test tag reaches learners; humanise or hide tags outside a curated set |
| P-07 | Discover | different behaviour | "14 items - Read" count line | "32 results" (no tab name) | a-discover | none |
| P-08 | Discover | missing step | banner "New." with Try it | absent (prototype promo) | d-notif | none (sample content, D-068) |
| P-09 | Content Detail | missing state | description paragraph, "Resume at 0:44", "Practice this text", cover hero, Related with thumbnails | no description (no data), "Resume" without a position, no Practice button on articles, dark placeholder hero, Related rows without thumbnails | a-detail, d-detail | cover: HP-3; rest none (N-10, no data) |
| P-10 | Content Detail, media | different behaviour | "Transcript - Generated - 12 segments" with 3 lines | "Captions - 6 segments" with lines; adds Shadowing, "..." | a-detail-media | none (real source) |
| P-11 | Search | missing state | empty state: Recent chips + scope sentence | blank page when there are no recent searches (the scope sentence is cut by rule 50 and N-18) | a-search-empty, d-search | none (rule 50) |
| P-12 | Notifications | different behaviour | typed events (Writing, Review, Speaking, Media, System) with time, unread dot, Mark all read | due review + a "Continue reading" row for every started item, including items at 100%; no time, no dot, no Mark all read | a-notif, d-notif | HUMAN DECISION HP-2 |
| P-13 | Notifications | different behaviour | one language | "Hoan thanh 100%" (Vietnamese) in the English and Chinese interface | a-notif, a-zh | DEFECT under HD-14, scope in HP-1 |
| P-14 | Import, type step | different behaviour | one language | option descriptions and the Text step's counts and too-short note ("0 tu - 0 cau", "Dan it nhat hai cau ...") in Vietnamese under an English interface | a-import-light | DEFECT under HD-14, scope in HP-1 |
| P-15 | Import, File | different behaviour | "PDF, EPUB, audio. Not built in this round." | "Audio or video from your device." (built) | a-import-light | none |
| P-16 | Import, Text | wrong order | "language - sentences - words" | "words - sentences" | a-import-text | none |
| P-17 | Profile, hero | missing step | Daily goal and This week tiles, "Counted from this session", weekly goal bar, achievements | omitted; two tiles (Streak, Due review) | a-profile, d-profile | none (N-32) |
| P-18 | Profile, identity | missing state | name "Calis", initial in the avatar, "Steady Walker - Level 7 - Plus plan" | name h1 renders empty (height 0), avatar and rail card have no initial or name; "Free" plan label not translated in VI and ZH | a-profile, ap-profile | name: HUMAN DECISION HP-5; "Free": DEFECT (translate the plan name) |
| P-19 | Settings, Languages | component not in design | support language is a segmented choice (Tieng Viet, English) | a dropdown with one option "Vietnamese"; the label stays English in the VI and ZH interface | a-settings, ap-settings | control: HUMAN DECISION HP-4; label: DEFECT (translate the language name) |
| P-20 | Settings, phone | wrong Visual skin | segmented choice, no scrollbar | at 390 and 360 the segmented groups scroll horizontally: a grey scroll track under the control and "Chinese - 中文" / "中文" clipped | ap-settings | DEFECT: let the choice wrap or shrink so no scroll track shows |
| P-21 | Settings, Learning | component not in design | text size, auto-scroll, translation, highlight, autoplay | adds Appearance (D-097), Accent (Visual Skin), Orena's voice | a-settings | none for Appearance and Accent; "Orena's voice" belongs to the parked Intelligence lane, noted only |
| P-22 | Settings, Notifications | different behaviour | 4 working toggles | drawn but inert | a-settings-Notifications | none (N-28) |
| P-23 | Settings, Plan & privacy | component not in design | plan, quota bars, mic toggle, learner audio, History | adds a "Licences and data sources" row; mic toggle is a sentence; quotas 0 / 0 (N-29, N-30), Delete audio inert (N-31) | a-settings-Plan | licences row: HUMAN DECISION HP-4 (with P-19) |
| P-24 | Coming soon | different behaviour | body paragraph, "Would resume at", footnote | icon, chip, title only; an unknown key repeats "Coming soon" as chip and title | a-coming, d-coming | none (rule 50, N-3) |
| P-25 | Banner | missing step | warn "You're offline. Downloaded lessons still work" + Retry; error "Upload failed" + Retry; ok "Goal reached" | only the offline banner, title only, no Retry | a-offline-banner | HUMAN DECISION HP-6 |
| P-26 | Loading | missing state | skeleton + "Preparing your lesson" | the markup exists; not reproduced in a browser | code-read | verify in the cutover QA |
| P-27 | Load error | different behaviour | "Couldn't load this story / lesson", offline vs server text | same texts; a missing content id shows the same generic text | a-loaderror-* | none |
| P-28 | Rail, top bar | different behaviour | badges Practice Hub 2, Library 6; learner card with name | one badge (Library 15, the real due count); learner card shows only "Chinese - HSK3" | a-today | none (real data); name follows HP-5 |
| P-29 | Docs | different behaviour | - | `IMPLEMENTATION_MAP.md` still lists Filter Sheet (and Stroke Practice) as `planned`, but both are built | map | DEFECT (documentation) |

Shell rule 47 checked: rail always present; top bar on Today, Discover, Content Detail, Profile, Coming soon; absent on Settings and Search; phone header and bar on the browsing places only. No page scroll or horizontal overflow at 390x844 and 360x740.

### HUMAN DECISION items (* = recommended)

- **HP-1 (P-02, P-13, P-14, P-19 label) System copy language.** A)* every system note and learner-facing label follows the interface language (as D-139 HD-14): Today subtitle and reason, notification progress text, Import descriptions and counts, language names; only the content stays in the content language; B) keep the support language for Today's explanatory sentence only; C) interface language with a support-language second line.
- **HP-2 (P-12) Notifications.** A) keep the current derived list but drop finished items and add the time of the activity; B)* draw the design's typed events only where a real event exists (due review now; writing review and media ready when their records carry a time), with an unread dot and Mark all read kept per device; C) remove the bell sheet until a notification record exists.
- **HP-3 (P-03, P-05, P-09) Content without a cover.** A)* a type-tinted tile with the type icon (the pattern Today's hero already uses) in place of the blank block; B) collapse the cover so cards are shorter; C) keep as built.
- **HP-4 (P-19, P-23) Settings controls.** A)* support language as the design's segmented choice listing the supported support languages, and keep the licences row (legal) as a quiet link; B) keep the dropdown, translate the label; C) remove the licences row until the legal surface exists.
- **HP-5 (P-01 eyebrow, P-18, P-28) Account without a name.** A)* use the part of the account email before the "@" for the eyebrow, profile name, avatar initial and rail card; B) show only the initial and the level, no name; C) ask for a name in Settings.
- **HP-6 (P-25) Banners.** A)* add Retry (re-checks the connection) to the offline banner and keep the goal banners out until a goal is measured (N-21); B) leave the offline banner as built; C) add the full set with a measured goal first.

## 4. Code-read only

Discover filtered and empty states, Import preview, processing and error steps (they call the server; not run), Profile "Sign out" handler, the Loading state, and the Today "Another" button (phone only).

## 5. Learner state

None changed. No import was submitted, no setting or language was changed, no request that writes was sent (offline and 404 checks only read). No Orena Intelligence screen was opened.

## Lane defaults pending human confirmation

2026-10-07, reason: human: continue without asking; follows D-139 HD-14 / earlier audits. Provisional and reversible; the
human may override any of them. Implemented on `codex/work`.

| Id | Default | What was done |
| --- | --- | --- |
| HP-1 A (P-02, P-13, P-14) | system copy follows the interface language, learning content unchanged | Today subtitle (`subtitleBoth`, `subtitleOnly`) and the due-review reason, Notifications `percentComplete` and `empty`, Import option descriptions, counts, the length note and the "no percentage" line moved support to interface (`today`, `notifications`, `import` copy tables; gates `test_orena_copy`, `test_orena_copy_layers`). Import errors stay support (they explain). |
| HP-3 A (P-03, P-05, P-09) | a type-tinted tile with the type icon where there is no cover | `kit/cover-visuals.js` (skill hues and `--tint2`, no new colour) drawn by `mediaCard` (Discover, Today For you), the Content Detail hero and Related thumbnails. No source/topic line was added: Discover's cards already show author and the (now vetted) topic. |
| HP-4 A (P-19, P-23) | support language as the design's choice; licences a quiet link | Kept as the picker (12 support languages exceed a segmented control, D-098) with endonym labels; the licences row is a quiet text link under Plan & privacy. |
| HP-5 (P-18) | BUG-06 already decided: a local session has no name and no placeholder is shown | The empty profile h1 is omitted; the avatar ring stays (initial only when the account has a name). The lane default "email local part" was not applied, it would contradict BUG-06. |
| HP-6 A (P-25) | Retry on the offline banner; no goal, streak or upload banners | Retry re-checks the connection ("Still offline" toast, or the banner clears); the other banners are recorded in `UI_BACKEND_GAPS.md`. |
| HP-2 (P-12), safe part | drop finished items, show the time when known | Items at 100% leave the bell; "Continue reading - yesterday" shows `place_at` when the server holds it. Typed events, unread dot and Mark all read are recorded in `UI_BACKEND_GAPS.md` (D-104). |
| P-11, P-24 | keep | Search empty and Coming soon stay as built: the design's scope sentence, body line and footnote are sample or internal copy (N-18, N-3, rule 50), not truthful learner copy. |

Defects fixed without a decision: P-20 (Settings choices wrap, no scroll track, "中文" whole at 390 and 360), P-06 (topics vetted by a documented vocabulary, translated), P-19 label (endonyms), P-18 plan name ("Free" translated in VI / ZH, description too), P-29 (`IMPLEMENTATION_MAP.md` Filter Sheet reviewable, Stroke Practice building).

### Places review batch, 2026-10-07 (LEX-072..081), lane defaults

Provisional and reversible; the human may override any of them.

| Id | Default | What was done |
| --- | --- | --- |
| P-11 revised (LEX-074) | Search before typing shows recent searches when there are any, and one truthful line saying what Search covers | The design's sentence is sample copy; the line names only the sources Search really reads. Replaces the earlier "keep as built". |
| LEX-073 | Today leads with the learner's own unfinished item as the hero (kind Continue, its context as the reason); the streak card follows Recommended, before For you | The pinned frame draws the progress block before Recommended; the review asked for Continue first. The week strip marks today and dims days to come; only days the server reports active are ticked. |
| LEX-079 | The bell sheet is titled "Up next" (it holds due words and unfinished work); Appearance and Accent move to their own Appearance tab | The design draws no theme control and no notification feed (D-104); Reader text size stays in Learning. |
| LEX-080 | A browsing place's load error names the place; the page retries itself when the connection returns; Profile lights no bar tab | Rule 47: the bar has no Profile item. |
| LEX-077 | A draft with no words is never set aside and does not raise "Draft in progress"; Free writing never shows a prompt | A waiting prompt draft stays a prompt draft whatever entry opened it. |
| LEX-081 | A cover tile sits at the lower left of a card so it does not collide with the two pills; Import to Reader and Show 0 results are disabled when they cannot act | |
