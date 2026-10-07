# Canonical UI ↔ backend tracker

## Governance

Purpose: the single tracker of what the Canonical UI Baseline needs from the
backend, API, data and business logic, and where each need stands. Authority:
D-066. The baseline (`docs/design/canonical-ui/`) decides the interface and the
data it shows; the backend adapts. A gap is worked, never a reason to remove,
move or redesign a component. Change when a requirement, a contract or a status
changes. Do not store secrets, screenshots or unverified claims. This file
replaces the D-060 backlog (GAP-001..052) and absorbs the 2026-09-21 audit; it
is the only tracker, so no audit file may run beside it.

Rules:

- **Metric rule (D-066 rule 4).** A metric the baseline draws that has no
  measured value renders `0` in its canonical component. The `0` is a UI
  fallback and is never stored, sent or counted as a measurement; the read model
  carries `measured: false`. Demo figures never ship.
- **Status.** `READY` = the slice meets every point of D-066 rule 13 (canonical
  visual on desktop and phone, real data, no production mock, state kept over a
  reload, auth, loading/empty/error/retry, fallback correct, tests pass, no
  duplicate implementation). `IN_PROGRESS` = in scope now and unfinished.
  `BLOCKED` = waits on a gate named in the row. Nothing is `READY` until it has
  been run in a browser against the real backend.
- **Gates.** `[REVIEW]` a schema or migration for learner-owned data needs a
  recorded independent architecture review before it is applied to a shared or
  sandbox runtime. `[PROVIDER]` credentials are a human gate. `[CONTENT]` the
  work is supplying content or metadata, not code. `[DEF]` a measurement or rule
  needs an official definition before it is built.
- **Slice.** S1 Word and Sentence Sheet, S2 Writing review and revision, S3
  Listening and Dictation, S4 Reading comprehension per question, S5 catalogue
  Search, L later (learner persistence, progress measurement, pronunciation).
- Every schema field must trace to a row here or to a real business need.

Baseline pin: 2026-09-21, design project
`7a5604ca-1e11-4d8e-8305-7d0cb32d552d`; files and SHA-256 in
`docs/design/canonical-ui/PINS.tsv`. Audit facts below were read from code and
schema on that date at `76e69b9`; none has been run against the baseline UI.

**Since 2026-09-27 the learner design is project `e6dc1cb2`, revision
`1790473816124946` (D-088), built as the new UI at `/next` (D-091).** Its rows
are in "N. The new learner design" directly below; the sections after it
describe the superseded Dark Glass UI still served at `/` until the cutover and
stay as history.

## N. The new learner design (D-088), 2026-09-27

Deviations from the pinned frames, each with its reason. A row leaves this
table when the human decides it or the design changes.

| #   | Where                     | Deviation                                                                                                                                                           | Why                                                                                                                                                                                                                                                      |
| --- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| N-1 | Every Vietnamese string   | Set in Plus Jakarta Sans (via `:lang(vi)`), not Outfit                                                                                                              | Outfit has no Vietnamese subset (latin, latin-ext only); letters like ế ạ ữ would fall back glyph by glyph inside a word. Plus Jakarta Sans is the face this design project used before its skin, and has the subset. Technical fallback, D-088 point 5. |
| N-2 | Icons                     | The package's path for each icon, not the frame's hand-typed variant (x, mic, search, volume-2, inbox, pencil, clock and ~20 more)                                  | Rule 46: official paths only, `lucide-static@0.525.0` (the release matching the most frame icons byte for byte, 45 of the design's icons).                                                                                                               |
| N-3 | Coming soon               | The frame's footer line ("Kept in the navigation so the Orena information architecture stays complete.") and its sample "Would resume at" block are not shown       | The footer is a note to the reviewer, not learner copy (rule 50); the resume block shows only when a real resume position exists.                                                                                                                        |
| N-4 | Prototype strip           | Desktop / Mobile / Light / Dark buttons above the frame are not built                                                                                               | Prototype chrome. Device follows the window (rule 48), theme follows the system (D-089).                                                                                                                                                                 |
| N-5 | Tablet                    | One switch between the desk and phone layouts (below 900 px the phone layout)                                                                                       | The design has two frames and no tablet (rule 48).                                                                                                                                                                                                       |
| N-6 | Phone learning workspaces | Recomposed to the viewport where a phone frame scrolls as a page (Listening Workspace on a phone first)                                                             | Rule 49, reaffirmed by the human for this design.                                                                                                                                                                                                        |
| N-7 | Rule 50                   | Decorative subtitles and taglines in the frames are not carried (e.g. "Your study companion", "Find something worth learning from.")                                | Rule 50 / D-087; listed per surface as it is built.                                                                                                                                                                                                      |
| N-8 | Colour contrast           | **Applied (D-093).** The design's own tokens failed AA 4.5:1 for small text in 13 pairs; the smallest lightness-only change below is in `kit/tokens.css` and gated. | Rule 41; the human chose the minimal adjustment.                                                                                                                                                                                                         |

**N-8, measured and applied (D-093).** Lightness only, hue and saturation kept
(the applied values differ from the first proposal by at most one step, taken to
clear 4.5 with margin):

| Theme | Pair (where it shows)                                                          |             Design | Applied                                                                                   |              After |
| ----- | ------------------------------------------------------------------------------ | -----------------: | ----------------------------------------------------------------------------------------- | -----------------: |
| dark  | `--text3` on bg / surface / surface2 (placeholders, meta, inactive phone tabs) | 4.40 / 4.07 / 3.77 | `--text3` #77778E → #858599                                                               | 5.32 / 4.92 / 4.56 |
| dark  | `--accent` on `--accent-soft` (active rail item, language pill)                |               4.19 | `--accent` #7D78F5 → #847FF6                                                              |               4.53 |
| dark  | white on `--accent` (primary buttons)                                          |               3.57 | a filled-control token `--accent-fill` #6862F3 (hover #5E58EA, pressed #544EDC)           |               4.54 |
| dark  | white on `--red` (count badges)                                                |               2.77 | badge numbers in a dark `--badge-ink` #0E0E16 (moving the red alone would change its hue) |               6.94 |
| light | `--text3` on bg / surface / surface2                                           | 2.95 / 3.21 / 2.93 | `--text3` #8E8EA2 → #6E6E86                                                               | 4.56 / 4.96 / 4.52 |
| light | `--green` / `--red` / `--amber` on their `-soft` (result tags)                 | 3.90 / 3.91 / 3.62 | #138A5A → #117E52, #D93D42 → #D0292E, #B86E00 → #A16000                                   | 4.55 / 4.55 / 4.56 |
| light | white on `--red` (count badges)                                                |               4.47 | the same `--red` #D0292E                                                                  |               5.20 |

Contract gaps for the agent surfaces: `docs/project/AGENT_CONTRACT_V2_PROPOSAL.md`
(awaiting approval). One backend gap it names: **N-9** - a speaking attempt's
audio-free record (`POST /api/speech/attempts` returns its id) cannot be read by
id; the list filters only by `asset_id` / `segment_id`. An owner-scoped read by
id (repository method, optionally `GET /api/speech/attempts/{id}`) needs no
schema change.

**N-10** - Content Detail's Related rail (`static/orena/screens/content/screen.js`,
frame 05, D2 "Data the backend must provide: ... a related-items list"). No
endpoint answers "what else is like this one" for any content kind; there is no
similarity, co-occurrence or curator-picked relation anywhere in the schema.
Built conservatively rather than invented: for an article or a shared-library
book, Related is a capped page of the same listing Discover already reads
(`GET /api/reading/articles` / `GET /api/reading/library/books`), minus the
current item - real content, not a relevance ranking. For a Listening lesson it
is the same against `GET /api/listening/library`. A learner's own upload or
imported text has no shared catalogue to draw from at all, so Related is simply
absent there (rule 40 - an absent list is empty, never invented), matching the
"a section disappears with no items" precedent Practice Hub's In-Progress list
already sets. A real "related to this one" signal needs its own field or query,
which is a content/relevance decision, not a frontend one.

**N-11** - Word Detail's "Mark known" footer link (`static/orena/screens/word/screen.js`,
frame 22, D7 §2/§4 `wdWC.onKnown`/`knownLabel`). The pinned script's own handler
for this control (`orena-script.js` `wordCard()`, `onKnown`) only flips a local
prototype flag (`this.state.known`) that nothing else in the app reads - one of
the prototype's own simulated internals the brief marks as not behaviour to
copy, not a real product concept. The real scheduler (`becoming_library.py`)
has no "known" state distinct from `review_stage`: three review grades
(`again`/`unsure`/`got_it`) advance or hold the stage; there is no fourth
"graduate out of review entirely" action. Built conservatively: the control is
not drawn (rule 40/44 - nothing invented over a control with no real backend
action), the rest of the card footer (mastery bars, stage, due date) renders
from the real saved item as before. A real "mark known" needs a product
decision (does it stop scheduling the word entirely, and how does that differ
from grading `got_it` enough times) before it is a backend field.

**N-18** - Search (`static/orena/screens/search/screen.js`, `model.js`, frame 27).
No global search endpoint exists anywhere in the API (grepped `writing_coach/`
for a free-text, cross-domain search route; none). Built conservatively from
what does exist rather than invented: `GET /api/vocabulary/catalogue/search`
(server-searched) for Words, `GET /api/collection?query=` for the learner's own
"My Library" items, `GET /api/reading/articles` and `GET /api/listening/library`
client-filtered by title/topic (neither route takes a free-text query) for
Content, and the learner's device-memory imports (`product/memory.js`). Three
sources the design's own placeholder names ("media, collections, saved items,
imported files and every transcript line") have no backend at all, so the
placeholder was shortened rather than promising a source that is not searched:

- No route searches inside a shared-library book chapter's or a published
  article's own text (transcript lines / article sentences) - same absence
  N-10 already names for Content Detail's Related rail.
- No route searches the admin-curated vocabulary _collections_ themselves
  (`vocabulary_collections` - distinct from the per-word catalogue search
  above, which already is composed in).
- Recent searches are device-only (`localStorage`, bounded to 8, this session's
  `model.js` `readRecent`/`pushRecent`), matching how device-memory
  continuation already works elsewhere (Architecture holds §7: learner-data
  persistence/schema is GPT-6's open decision) - not a per-account, cross-device
  history. A real search history needs the same persistence decision before it
  can move server-side.

**N-19** - Collection Detail (`static/orena/screens/collection/screen.js`,
`model.js`, frame 21, D2 §6). Three fields the frame draws have no backend
source at all:

- The cover image. `VocabularyCollection` (`writing_coach/persistence/models.py`)
  carries no image/asset column, so `heroMedia()` is called with `image: ''`
  (rule 40) and the cover renders as the plain scrim gradient with no photo.
- The collection's own curated description (`col.desc`). Same table, no
  description column. Rendered as absent (rule 43 - nothing shown where the
  frame's markup would otherwise sit), not an empty paragraph.
- "`{{n}}` met in your sources" (`colProgress`). No aggregate anywhere counts
  how many of a collection's words the learner has met in their own reading or
  listening content (the closest real thing, `progress.learned_count`, is a
  saved/review relationship, not a source-encounter count). Always `0`.
  Fourth: `colSave` (save/bookmark a whole collection). No endpoint or
  device-memory concept saves a curated collection as a unit (concept A) -
  `POST /api/library/vocabulary` and `DELETE /api/library/vocabulary/{word}`
  only ever address one word. Built conservatively: the button is drawn (the
  frame draws it) but its handler shows an honest "not available yet" toast
  instead of inventing a client-only bookmark that would silently not persist.
  A real implementation needs either a `vocabulary_collections`-level saved-set
  table or a new relationship on the existing per-word save, plus a cover-image
  and description field on the collection record and a word-to-source-encounter
  index (the same shape RD-8/VC-10 above already need for a single word).

(The `copy/index.js` `fill()`-drops-zero bug this surface hit while building is
consolidated with its four sibling screens' own hits of the same bug, and a
second copy-engine bug, into **N-34** below - resolved centrally, not repeated
per screen here.)

**N-20** - Grammar Library and Grammar Concept (`static/orena/screens/grammar/`,
`static/orena/screens/grammar-concept/`, frames 44/47, E5). Content gap, not a
UI bug: `GET /api/library/grammar/{id}`'s `learning_model` explanatory prose
(`meaning.summary`, `common_mistake.why`, `personal_practice.prompt`) and every
lesson's `examples[]` translation field (`meaning_vi`/`vi`) are authored in
Vietnamese only, for both the English-target and the Chinese-target catalogue
(confirmed live against both; no `meaning_en`/`meaning_zh` field and no
`en`/`zh` key on those `learning_model` fields exists anywhere in the content
pipeline or its migration script, despite the schema's `_text()` validator
supporting an arbitrary locale key plus the literal `"default"`). Built
conservatively: the example translation line is shown only to a vi-support
learner and left off for every other support language (`model.js`'s
`examplesOf`, gated on `guidanceLocale(support, ['vi'])` - the field the
previous pass of this surface had gated on nothing, showing the Vietnamese
gloss unconditionally to every learner regardless of support language, a real
EN/ZH parity bug fixed in this pass); the explanatory-prose fields keep their
existing locale-map fallback (`pickLocale`, now checking the schema's own
`default` key explicitly rather than accidentally landing on it via object key
order) and so still surface the Vietnamese text via `default` for a non-vi-
support learner, since these fields carry real prose worth keeping over
blanking most of the Concept card's teaching content for the majority of
learners - a difference from the flat, non-schema `examples[]` field, recorded
as a question for the human below, not resolved silently. Needs English and
Chinese authoring of this prose (and, ambitiously, per-support-language
example glosses) to close for real. **See also N-33**: the lesson `title`
field itself - the primary heading on both screens - has the same
Vietnamese-only gap but no locale-map shape at all to fall back through,
unlike the fields above.

**N-21** - Today (`static/orena/screens/today/screen.js`, `model.js`, frame
10-Today.html, D1 §5). Three cards the frame draws have no cross-activity
backend at all:

- The daily-goal ring and its 3 skill mini-rings (`pgGoal.pct/dash`,
  `tdSkills[3].dash`). No endpoint measures "percent of today's goal" or a
  per-skill daily percent for any of Reading/Listening/Speaking together - the
  closest real thing, `GET /api/learner-summary?window=7d`, is a 7-day
  activity-count read, not a daily goal or a percent of anything. Always `0`
  (rule 40); the sub-caption uses the real 7-day evidence when any exists,
  naming its own window ("This week: …") rather than claiming "today"/"this
  session" the way the frame's own sample text does.
- The streak card (`pgStreak.n/days`). No cross-activity streak exists
  anywhere in the schema; the only stored streak is Writing's own,
  `GET /api/dashboard`'s `streak_days` field, scoped to writing submissions
  alone - reusing it here would misrepresent a single-activity number as an
  all-activity one, so it is not reused. Always `0`, all 7 days undone.
- The level/XP card (`pgLevel.badge/name/xp/pct/next`). No gamified level/XP
  system exists anywhere in the domain (checked `writing_coach/persistence/
  models.py` and the API surface) - `badge` renders a placeholder glyph ("–")
  rather than the learner's real level (`B2` in the frame's own sample is a
  target-language proficiency label, a different concept, already shown
  correctly in the shell's own language pill).
  A real daily goal, per-skill percent, cross-activity streak and level/XP
  system are each a product-and-schema decision (Architecture holds §7), not
  something this surface can measure.

(This screen's own hit of the `copy/index.js` `fill()`-drops-zero bug - the
streak count, skill percents and XP value - is consolidated into **N-34**.)

**N-22** - Practice Hub / Skill Hub (`static/orena/screens/practice/`, frames
08-Practice-Hub.html, 09-Skill-Hub.html, D2 §3-4).

**Corrected by independent review, 2026-09-27**: this entry previously claimed
Listen and Reading had no backend at all ("no endpoint answers 'the next
listening item' or 'the next reading item' for a learner generically"). That
was factually wrong, and checkable from files already in this working tree:
`GET /api/listening/library` (`api.listeningLibrary`, already called by
`screens/today/screen.js` and `screens/discover/screen.js`) returns real
catalogue items, each carrying `available_modes`
(`listening_catalog.py`'s `PRACTICE_MODES`: `listen`/`active`/`dictation`/
`shadowing`); `GET /api/reading/practice/next` (`api.readingPracticeNext`,
also already called by `screens/today/screen.js`) is literally "the next
reading item for a learner, generically" and answers `{"available": bool,
"next": …}` - `available: false` in this sandbox is a real, honest empty (no
article published here yet), not a missing endpoint. Both are now wired the
same way `speakModes()` already consumed the Speaking library:
`model.js`'s `listenModes()` gates a Dictation and a Shadowing tile on
whether the Listening library currently has an item carrying that mode, and
`readingModes()` gates a Start-Reading-Practice tile on the queue's own
`available` flag. `SKILL_ORDER`/`buildSkillSections` are now data-driven (a
skill's section renders only when its builder actually returned a mode this
visit) rather than the previous hardcoded four-skill list - Listen's and
Reading's sections appear or disappear with the real data, the same way the
design's own Continue section disappears when it is empty.

What remains a genuine gap, after the correction above: Listen's "React /
Reuse" and "Retell" (its own "Use what you hear" group) have no
`available_modes` value in the schema to gate on at all (`PRACTICE_MODES` is
exactly `listen`/`active`/`dictation`/`shadowing` - no react/retell entry),
and Reading's "Paraphrase"/"Inference"/"Context Shift" (its own "Transfer"
group) have no id source either - both stay out (rule 40). Both skills' own
"Continue listening"/"Continue reading" groups are device-memory
continuation, already surfaced separately by `continuationRows()`, not a
catalogue-backed mode, so they were never part of this gap. **Write silently
dropped three of the design's modes, now recorded rather than left implicit
in a code comment**: "Respond to Content" (`shell/routes.js` already has
`{ id: 'respond', path: 'respond/:id', screen: 'respond', crumb:
'respondToContent' }`, but `respond` is not registered in `shell/screens.js`,
and - unlike Listen/Reading above - no generic "which content to respond to"
id source exists anywhere to supply it even once the screen is built), and
"Prompt"/"Your Topic" (Writing's own entry setup for a fresh draft - a
screen-internal choice for `writing`'s own compose flow to make once it
branches, not a Practice Hub fork). No mode of any skill carries a real
duration estimate anywhere in the schema (the frame's own `~3 min`/`~8 min`/
`~10 min` per mode is the prototype's invented sample data, not a measured
field) - every mode row/tile omits it rather than fabricating one. No
"locked"/"not yet available" signal exists for a mode that is real but
conditionally gated (the frame's `pi.op`/`SOON` dimming, Skill Hub's `md.op`)

- since nothing here is drawn at all unless it is fully real and addressable
  today, that state is never needed, not missing. Vocabulary's Due Review count
  and Speaking's/Listening's/Reading's per-mode level are the only real
  per-mode metadata fields that exist; Writing's recommendation
  (`GET /api/practice-recommendation`) is the only real per-skill recommender -
  Speak/Listen/Vocabulary/Grammar/Reading Skill Hubs correctly show no
  recommendation card rather than one with no real reason behind it.

(This screen's own hit of `copy/index.js`'s second bug - `plural()` reading
English's own `_one` form, backfilled into the merged object, for a Vietnamese
or Chinese interface at n=1 - is consolidated into **N-34**, alongside My
Library's identical hit.)

**N-23** - My Library (`static/orena/screens/library/`, frame 12, D2 §5). The
pinned copy's compact export mis-hints `libTabs` at 4 entries
(`hint-placeholder-count="4"`, a truncated-export placeholder guess, not real
sample data); the live design script (`orena-script.js`'s `LIBT` array and
`libIsActive`) proves 5 real tabs - Saved content, Saved language, Collections,
**Active use**, Due Review - so this surface was corrected to build all five,
not the four an earlier pass had inferred from the cache alone. Three real
backend gaps found while building the fifth tab and the rest of the room (the
third added on independent review - a real navigation defect the room's own
first pass shipped, not just a documentation gap; see below):

1. **Active use's four cards are a fixed shortcut menu, not fetched rows**
   (`orena-script.js`'s `activeUse` array is static demo data, not a per-user
   list): Due review → `#/review`, Context Transfer → `#/transfer`, Situation
   Reaction (context variant) → `#/situation`, Timed Recall → `#/timed`. All
   four are real focus routes in `shell/routes.js` with no screen registered
   yet, so today each correctly lands on the router's own Coming-soon fallback
   - the same place the Due tab's own "Start review" button already sends a
     learner. No duration estimate exists for any of them, the same absence
     N-22 already documents for Practice/Skill Hub's own mode tiles (this tab is
     effectively Vocabulary's own mode list, reached from a second place); `dur`
     is simply not carried rather than showing N-22's same invented "~3 min".
2. **A saved word/phrase's tap-to-jump-to-source (`ll.onSource` in the frame,
   "jump to the source context where a word/phrase was met") has no general
   target.** `SavedWord` (`writing_coach/persistence/models.py`) carries
   `source_essay_id` only for words saved from a writing essay, and a bare
   `source_kind` category (`manual`/`dictionary`/`feedback`/`strength`/
   `reading`/`feed`/`collection`) for the rest - no reading/listening source id
   at all for the common cases. `screens/word/model.js` already reads the same
   two fields for Word Detail and treats them as a display label only, never a
   link, which this screen follows: the text block is not made clickable
   rather than wiring a jump that would work for a minority of saved words and
   silently do nothing for the rest. A real "open where this was met" needs a
   source id/type recorded per saved word (reading article, listening lesson,
   collection card, essay) at save time, for every `source_kind` that can be
   opened.
3. **Collections tab: no detail screen exists yet for either backend concept
   it lists** (`static/orena/screens/` has no such folder; `shell/routes.js`
   defines only the one `collection/:id` route, and that is reserved for a
   third, unrelated concept - a curated vocabulary pack, `GET
/api/vocabulary/library/collections/{id}`, reached from Discover, not from
   a learner's own library). The room's first pass sent every Collections-tab
   card (both a My Library collection, `GET /api/library/collections`, and a
   Vocabulary deck, `GET /api/vocabulary/decks`) into that same wrong route,
   which independent review caught 404ing 100% of the time
   (`{"detail":"Vocabulary collection not found."}`) the moment a real card
   exists to click - the sandbox account had zero of either, so the room's own
   verification journey never actually clicked one. Fixed: both card kinds now
   land on the design's own Coming-soon (`#/coming/collection`, reusing the
   existing `collection` shellCopy title rather than inventing new copy) until
   a real "My Library collection detail" and "Vocabulary deck detail" screen
   exist - each needs its own route, screen and, for the deck case, its own
   review-launch action (`shell/routes.js` currently has neither).

(This screen's own hits of both `copy/index.js` bugs - `fill()` dropping the
Due tab's `{min}`/count placeholders at `0`, and `plural()` reading English's
`_one` form under vi/zh for `collectionItems` - are consolidated into
**N-34**.)

**N-24** - Progress (`static/orena/screens/progress/screen.js`, `model.js`,
frame 17, D8). Consolidated record of this surface's rule-40 zero/honest-empty
fallbacks (full detail already lives in `model.js`'s own doc comment; listed
here per this section's own precedent, since Progress has more distinct
no-backend-source items than any sibling screen recorded above): no domain
tracks study time or a streak (Overview hero's time readout and 7-day bar
chart, dropped for an honest note rather than a fabricated "0 hr 0 min"); no
domain has a proficiency percentage or trend delta (`learner_summary.py`'s
`growth.status` is universally `"unavailable"` - the Skills card's five rows
always render `pct: 0`/`delta: null`); nothing generates a "this week's story"
headline or a "next, based on evidence" recommendation; no owner computes any
of the five Knowing → Using stages (Recognized/Recalled/Used/Transferred/Fast
retrieval - both the Overview mini-card and the full tab are always zero); the
whole Trends tab is a detection/generation feature with no backend owner at
all; the Evidence "Review" filter always empties honestly because vocabulary
recall has one lifetime aggregate count, not a dated per-event log; and no
milestone/achievement data exists for the Rank tab's Milestones list. All
eight render their rule-40 zero or an honest empty state, none fabricated. A
real implementation of any of these needs the same backend measurement (study
time, per-domain proficiency scoring, a recommendation engine, KU-stage
instrumentation, or a milestone table) before the frontend has anything real
to bind to.

Settings (`static/orena/screens/settings/`, frame 26, E1 "Data the backend must
provide"). Every row the frame draws is built and shown; a row with no real
source behind it is drawn disabled with its honest fallback value (rule 40),
never removed (rule 43) and never wired to pretend. Seven such gaps:

**N-25** - Learning tab, "Word highlight (estimated)". No mechanism anywhere in
the app (grepped `capabilities/`, `product/`, every `screen/`/`ui/` module)
estimates or highlights the word currently being spoken inside a transcript
segment. The toggle is drawn off and inert. A real implementation needs either
word-level timing in the transcript data or a heuristic over segment duration
and word count, neither of which exists today.

**N-26** - Learning tab, "Autoplay next segment". No stored preference or
playback behaviour anywhere continues to the next transcript segment
automatically; the Listening room's own toolbar (`ui/encounter.js`,
`product/transcript-stage.js`) has no `autoplay` field. Drawn off and inert.
Needs a third field in the transcript-stage shape and the Listening room's own
playback loop to honour it.

**N-27** - Review tab, "Session length". No stored field means "items per
sitting" anywhere; `product/recall-modes.js`'s own review settings carry
`newPerDay` and `limitPerDay` (daily caps), neither of which is a per-session
item count. Drawn with the middle option (10) selected and inert, per the same
never-invented-edge convention `SESSION_LENGTH_FALLBACK` documents. Needs a
third field in `recall-modes.js`'s settings shape and the Review room reading
it to size a sitting.

**N-28** - The whole Notifications tab (4 rows: due review, writing review
ready, media ready, system and account). No notification-preference storage
exists anywhere in the app - no device key, no profile field, no table - and
there is no notification-sending mechanism to gate in the first place. All four
toggles are drawn off and inert. Needs a real notification channel (push,
email or in-app) before a preference for it means anything.

**N-29** - Plan & privacy tab, "Orena messages" quota bar. No entitlement key
for AI-tutor conversation turns exists in `writing_coach/product/catalog.py`'s
plan catalogue (`writing.evaluate`, `writing.improve`, `library.grammar`,
`dictionary.lookup`, `vocabulary.save`, `analytics.*`, `practice.personalized`,
`export.report` - no `orena.messages` or equivalent). Drawn as 0/0 and inert.
Needs a catalogue entitlement plus a counter on `agent-bridge.js`'s Ask-Orena
calls.

**N-30** - Plan & privacy tab, "Pronunciation minutes" quota bar. Same absence:
no entitlement key measures pronunciation practice time anywhere in the
catalogue. Drawn as 0/0 and inert. Needs a catalogue entitlement plus a
duration counter over Speaking/Shadowing attempts
(`POST /api/speech/pronunciation`, `POST /api/speech/attempts`).

**N-31** - Plan & privacy tab, "Learner audio" ("Delete audio"). No route
deletes a learner's stored audio or media anywhere in the API (`speech_*.py`,
`media_*.py`, `library_api.py` grepped) - only `DELETE
/api/library/vocabulary/{word}` and `DELETE /api/library/items/{id}` exist, and
neither touches stored audio bytes. The row is drawn with its real retention
sentence and an inert "Delete audio" button. Needs a deletion route over
whatever store keeps Speaking/Compare recordings and imported media.

(The "Plus plan" row's "Manage" action is inert too, but is not a new gap here:
`docs/product/ORENA_COMMERCE_ARCHITECTURE.md` §2 already documents
`billing_ready=False` everywhere, which is why no plan action anywhere in the
app has a real destination yet.)

**N-32** - Profile (`static/orena/screens/profile/screen.js`, `model.js`, frames
24-25 "Profile" / "Profile · Today's progress", D8/E1). Five real backend gaps,
each already rule-40 zeroed/honestly-empty in the built screen, none fabricated:

1. **Day streak** (the stats card's flame number and the hero's Streak tile).
   No cross-activity streak table exists anywhere in the schema - the only
   stored streak is Writing's own, `GET /api/dashboard`'s `streak_days` field,
   scoped to writing submissions alone, so it is not reused here (the same
   reasoning N-21 already applied to Today's identical streak card). Always
   `0`; the 7-cell day strip shows no day as done.
2. **This-week minutes** (the hero's "This week" tile and the stats card's
   clock stat). No domain aggregates study time per day or per week anywhere
   in the schema. Always `0`; the design's own `weekDelta` line ("+N min vs
   last week") is dropped rather than comparing two unmeasured numbers.
3. **Weekly-goal done-count** (the identity card's 5-segment bar, "0 / 5").
   The segment _count_ itself (5) is the design's own fixed constant
   (`WEEKLY_GOAL_TARGET`, a rendering parameter, not a claimed measurement,
   the same way Today's 3 skill rings are a fixed set) - no configurable
   weekly-goal-in-days feature exists to measure a real done-count against it.
4. **Daily-goal tile** (the hero's 4th tile, a 60x60 ring). No per-day
   study-time aggregate exists to fill the ring (always drawn at a real,
   honest 0% via `kit/components.js`'s `progressRing()`, the same pattern
   Today's own goal ring already ships for the identical gap, N-21); the
   design's own "15 minutes" target is a constant living only inside the
   prototype's fake session-stopwatch function (`orena-script.js`'s
   `sessVals()`), with no standing as a real setting anywhere, so the tile's
   value line reads an honest "Not tracked yet" rather than a fabricated
   "0 / 15 min" against a target that does not really exist. A real daily-goal
   ring needs both a per-day study-time measure and a real daily-goal-minutes
   setting.
5. **Achievements** (the identity card's 4-badge row: "First article", "10
   videos", "Speak 7 days · 4/7", "C1 writer"; `screens/profile/screen.js`'s
   own top comment cites this item as "N-25" - stale from before this
   section's renumbering, this **N-32** item 5 is the current id). Omitted
   entirely, not drawn at a zero state, because there is no catalogue to read
   even a zero from -
   `learner_summary.py`'s own achievements object is
   `{status:'unavailable', reason:'no_approved_policy'}`, unlike the four
   items above, which each have a real (always-zero) field to bind to.

All five need the same class of backend work as their Today/Progress
counterparts (N-21, N-24): a cross-activity study-time aggregate, a
cross-activity streak table, a configurable weekly-goal setting, and an
achievements/milestone catalogue, before the frontend has anything real to
bind to.

**N-33** - _(R5 content; R5 is being retired - see CURRENT_HANDOFF.md.)_ Grammar Library and Grammar Concept, found on independent review of
N-20 (`static/orena/screens/grammar/`, `static/orena/screens/grammar-concept/`,
frames 44/47). For the **Chinese-target (HSK) catalogue**,
`GET /api/library/grammar` and `GET /api/library/grammar/{id}` return `title`
as a **flat Vietnamese string** - e.g. `"SVO cơ bản"` (HSK1), `"过: kinh
nghiệm"` (HSK2), `"把字句: nền tảng"` (HSK3) - confirmed against both the live
API and the source content
(`writing_coach/languages/chinese/grammar_curriculum.json`: every lesson's
`title` field is a plain string, no `title_en`/`title_zh` key and no
locale-map shape at all). This is a different and more severe gap than N-20's
already-disclosed one: N-20's `learning_model` prose fields and `examples[]`
at least have somewhere to look for a non-Vietnamese value (the prose fields
via a documented `"default"`-key locale map; the frontend now honestly omits
`examples[]`'s translation line for a non-vi-support learner because that
field has no map to fall back through). `title` has no locale mechanism to
select from, English or Chinese, so it is not fixable in the frontend at all

- there is no field to `pickLocale` between.

By contrast, every **English**-target lesson's `title` is genuine English at
every level A1-C2 (spot-checked; confirmed via
`writing_coach/languages/english/grammar_curriculum.json`), so this is
specific to the Chinese track's content authoring, not a general quirk of the
`title` field.

Impact: `title` is the **primary heading** on both screens - the Library
row's bold title (`screen.js`'s `listRow({ title: item.title, ... })`) and
the Concept screen's header (`pageHeader({ title: lesson.title, ... })`,
`ctx.setCrumb(lesson.title)`). For a Chinese-target learner without
Vietnamese support, this heading, plus the N-20 prose fields shown via
`default`, is Vietnamese text they cannot read; only the raw Chinese example
sentences and the Latin pattern-chip letters (S/V/O) are genuinely theirs
across most of the 239-lesson HSK catalogue. Needs an English/Chinese
`title` authored per lesson (or a locale-map shape matching `learning_model`'s
own `_text()`/`"default"` convention) in the Chinese grammar curriculum before
the frontend has anything to select.

**N-34 - RESOLVED (2026-09-27).** Two `copy/index.js` bugs, each hit
independently while building several screens above and previously recorded as
a separate note on each one (Collection Detail N-19, Grammar N-20, Today N-21,
Practice Hub N-22, My Library N-23): (1) `fill()` dropped a `{n}`/`{min}`-style
placeholder whenever the interpolated value was exactly `0`, leaving the
literal token in the rendered string - hit by every rule-40 zero that a
screen tried to interpolate; (2) `plural(key, n)` chose the singular form by
checking the _merged_, English-backfilled copy object, so a Vietnamese or
Chinese interface read the English `_one` string at `n === 1` instead of its
own `_other` form. Both are now fixed centrally in `copy/index.js`: `fill()`
fills a real `0`, and `plural()` picks the form with `Intl.PluralRules` of the
language the key actually renders in, so vi/zh always read `<key>_other` and
English reads `<key>_one` only at `n === 1`. The five screens' own local
workarounds (`zeroSafe()`, the presence-based `fillSafe()`, bare ranked keys
in place of `_one`/`_other`) are being removed now that the shared fix covers
them - nothing left for a screen to work around locally.

**N-35** - Language-of-parts audit (languages-4/5, `SCRATCH/reports/verify-languages.md`), three
raw-backend-value findings across Wave A. Two of the three were a closed value space and are now
fixed in the frontend (mapped to real interface copy, en/vi/zh); the third is genuinely open and
stays a backend gap:

1. **Word Detail's part-of-speech chip - fixed, not a gap.** `card.pos`
   (`POST /api/dictionary/word-detail`'s `partOfSpeech`) is mostly the shared local tagger's closed
   fifteen-value set (`writing_coach/linguistic_annotation.py` `ALLOWED_POS`), reached through
   `word_detail.py`'s own lookup path - confirmed against the live source, not assumed. Mapped to
   real copy (`screens/word/copy.js`'s `pos*` keys, `model.js#posLabel`). A value the fifteen-value
   map does not recognise (a saved item's own free-text `part_of_speech` -
   `vocabulary_source_import.py` - or an external monolingual dictionary's own wording,
   `reading_lookup.py`, neither of which is validated against `ALLOWED_POS`) cannot be honestly
   translated and is shown exactly as the backend gave it, marked `lang="en"` as untranslated
   content metadata rather than silent unlabelled English inside a vi/zh sentence.
2. **Grammar Library's level-group heading - fixed, not a gap.** `library.level_names[level]`
   (`writing_coach/languages/grammar_registry.py` `GrammarProvider.level_names`) is the backend's
   own English label for a closed, nine-label space shared by both providers (English A1-C2,
   Chinese/HSK1-7-9). Backend code is out of scope for this pass, so the mapping lives in the
   frontend instead, keyed by the level _code_ (the one thing both providers already return
   verbatim) rather than the backend's own English text: `screens/grammar/copy.js`'s `level*` keys,
   `model.js#levelName`/`LEVEL_NAME_KEY`. A level code neither provider currently uses falls back to
   the raw code rather than guessing a label.
3. **Discover's (and Search's) topic chip - a real, open gap.** `entry.topic`
   (`reading_articles.topic`/vocabulary topic, surfaced identically in `screens/discover/model.js`'s
   card tag and its Filter Sheet's own topic group, and in `screens/search/model.js`'s meta line) is
   free-text content metadata set per item by whoever published it - an open, ever-growing
   taxonomy (`finance`, `shipping`, `human-resources`, `daily-life`, `technology`, `culture`, … and
   growing), not a closed enum a frontend table could honestly cover, and per D-080 a topic chip is
   interface-layer metadata that does need to be in the learner's interface language once it can be.
   Kept, marked `lang="en"` as honest, untranslated content metadata (the conservative option: it is
   real information about the card, and blanking it would lose that rather than fix the mismatch).
   Needs the backend to own topic localization: either (a) a closed, stable taxonomy with a slug and
   a per-language label, returned by `/api/reading/articles`/`/api/vocabulary/...` so the frontend
   can map slug -> `t()` the same way `typeLabel()`/`levelName()` above now do for a closed enum, or
   (b) the API returning an already-localized label for the requesting interface language. This is
   the same underlying gap N-33 already names for Chinese-track lesson titles - a systemic
   backend-taxonomy-localization absence surfacing on more than one screen, not independent bugs.
   Search's own meta line (`[topic, level].join(' · ')`) had the identical unmarked-topic issue
   (review issue 1 on this pass); it is now split the same way as Discover's card tag -
   `screens/search/model.js`'s `articleItems`/`listeningItems` keep `topic` out of the joined
   `meta` string, and `screen.js#resultRow` renders it in its own `lang="en"` span - so both
   screens are honest in the interim the same way. The backend gap itself (no closed taxonomy)
   still covers both.

Separately, the same audit found no saved-vocabulary item anywhere in this build carries a
per-item language field back to the frontend: `SavedWord.language_code`
(`writing_coach/persistence/models.py`) exists in the schema only to scope the
`GET /api/library/vocabulary` query server-side - `becoming_library.py`'s `_row_to_item` never
returns it. Every screen that reads this route (Word Detail, My Library's Saved-language tab)
therefore marks its `lang` from the request's own active learning language (a real, server-enforced
scope: `current_language_code()` filters the query itself) rather than a genuine per-word field,
except Word Detail, which additionally falls back to the backend's own Han-range script check
(`word_detail.py` `script_of`) for a word whose saved language may predate the learner's current
one. Returning `language_code` on the saved-vocabulary item itself would remove the one remaining
script-check fallback in this build.

**N-36** - API shape audit (2026-09-28): every new-UI reader was checked against real payloads
captured from the running app (`scripts/fixtures/api/`). Field reads the API never satisfied were
fixed in the UI (Search, My Library, Progress, Grammar Concept); three things only the backend can
change remain:

1. **RESOLVED (2026-09-28).** Progress's Evidence row for an essay could not show the excerpt the
   frame draws: `GET /api/essays` (the list route) dropped `text` (`app.py` `row_to_dict`,
   non-detail branch) with nothing put in its place, so the row showed its title only.
   `row_to_dict()`'s non-detail branch now derives a short, bounded `excerpt` field
   (`ESSAY_LIST_EXCERPT_MAX_CHARS = 160`, `essay_list_excerpt()`) from the stored text at
   serialization time - whitespace collapsed to one line, cut on a Unicode code-point boundary (safe
   for Vietnamese and Chinese), an ellipsis appended only when actually cut, never the full text.
   `GET /api/essays/{id}` (detail=True) is unchanged and still carries the full `text`.
   `static/orena/screens/progress/model.js` `buildWritingEvidence()` now reads `e.excerpt` into the
   row's `responseText`, and marks it with the essay's own `e.language_code` rather than the
   screen's generic active learning language. History's row has no excerpt/response slot in the
   design (D8-progress-profile-onboarding.md: title + trailing meta only) and needed no change.
   Verified with a pytest that failed before the change
   (`tests/test_essay_list_excerpt.py`) and live on the isolated stack (`GET /api/essays` after
   `POST /api/evaluate` via the sandbox's Ollama fallback).
2. No curated vocabulary collection is published in this build, so `GET
/api/vocabulary/library/collections` and `GET /api/vocabulary/catalogue/search` answer empty for
   every language (the packs exist in `writing_coach/vocabulary_library.py`; the routes serve
   published packs only). Collection Detail and Search's word results stay empty until packs are
   published - a content decision, not a UI defect.
3. **RESOLVED (2026-09-28).** `GET /api/library/vocabulary/{word}/audio` answered 500 for a
   catalogued word (`health`, `vacancy`): the route found real audio, then its cache write failed
   (`OSError` on a read-only store) and nothing caught it. `writing_coach/word_audio.py` now
   answers no audio (`available: false`) when the clip cannot be stored - the route serves audio
   from the store, so an unstored clip has nothing to serve - and logs the storage failure;
   `tests/test_word_audio.py` covers it.

**N-37** - Orena (`static/orena/screens/orena/` - Home #/orena frame 11, the Contextual panel frame
55, full-screen voice frame 56; D1 §6, E5 §6-7). Built against AGENT_CONTRACT v5 and the contract
mock (`agent/mock.js`, D-086 - the intelligence lane is not integrated yet). Gaps the frames or the
contract leave open, each already filled the conservative way (rule 40) rather than guessed:

1. Frame 11's header subtitle reads "Knows your `{{ tlLabel }}` · last active: Listening, 2 h ago" -
   only `tlLabel` is a binding; "last active: …" is literal sample text in the export (D1 §6 own copy
   audit already flags this). No device or server record of "which capability the learner last used,
   and when" exists anywhere in this build (`product/memory.js`'s `continuation` entries carry no
   timestamp or capability field at all) - the clause is dropped, not shown with an invented time
   (`screens/orena/model.js` `homeSubtitle()`). Needs a real per-learner "last active capability +
   time" record before it can ship.
2. Frame 55 (Contextual Orena) draws no action-handoff or evidence card of its own - E5's own
   inventory for this frame finds neither component exists in its export, unlike frame 11 which draws
   both (OA3/OA4) inline in its thread. An offered action must still be tappable wherever it is
   returned (AGENT_CONTRACT §7), so the panel reuses frame 11's one measured OA3 action-card shape
   rather than inventing a second, undrawn one (Design Contract rule 7's conservative fill;
   `screens/orena/cards.js`). Confirm with the design whether the panel should eventually draw its
   own, narrower card for its ~440px sheet width. An action whose `display` carries nothing to draw
   (the mock never sends one; a real server sends `display` only when it read a domain record) is
   drawn as the card's own button alone, not an empty card around it. `display.kind` is an enum
   (reading | listening | ...) written out in the learner's interface language, `duration_s` as
   "~N min"; an action this client cannot run right now (`play_model`, `say_again` ... with no
   workspace mounted) is not drawn at all (§7 "ignored and logged").
3. Frame 11's own OA4 "source" card (`hm.sources`: optional thumbnail, title, kind, one-line meta,
   trailing chevron - a tappable reference, implicitly navigable) has no full match in the real
   `evidence` event (`{id, source, ref, excerpt, display?}`, AGENT_CONTRACT §5.3/§5.5). §5.5's
   `display` can carry a real `title` and `kind` for an evidence item, but never a thumbnail, a
   navigable `ref` (`ref` is an evaluation/attempt locator such as `{attempt_id, path}`, not a route)
   or a chevron's implied "tap to open" - so even a fully-populated `display` could not make the
   frame's card function as the frame draws it. Built instead as a plain, non-interactive card
   (kind and title, from `display`) or, with no `display`, a small note naming the source in the
   interface language (`screens/orena/cards.js` `evidenceMarkup()`). The evidence `excerpt` (§5.3:
   the UI "may offer" a "why?" affordance by rendering it) is not drawn: no frame draws one, and its
   keys are machine names (`pinyin`, `flagged`, ...) that are not learner copy. If evidence is ever
   meant to open something, its event needs a real navigable target, not only `display.title`.
4. The coach-notes sheet (`screens/orena/memory-sheet.js`, `openAgentMemory()` - AGENT_CONTRACT §10
   "the privacy exit") has no entry point in the frames (D1/E5 read only Home, the Contextual panel
   and full-screen voice; Settings' Plan & privacy tab draws no row for it). It is built, exported
   and exercised against the real app (notes list with delete, the address note first with its own
   line; deleting it returns Orena to the default address), ready for Settings to call from a
   "What Orena remembers" row in Plan & privacy. `agent/intents.js` maps `preferences.agent_memory`
   to `#/settings?tab=privacy&section=orena`, which Settings does not read (its tabs are
   languages/learning/review/notifications/plan): the intent lands on Settings' first tab. No
   button is invented here (rule 43); the Settings owner needs to decide the row and the tab.
5. Full-screen voice (frame 56) is reachable only from the desk rail's mic - E5 §7.1's own review of
   the export found no mobile trigger for it anywhere. None is invented; a phone learner reaches
   voice mode only through Home's or the panel's inline voice row. Confirm this is intentional for
   this revision (mobile voice is meant to stay inline, never full-screen) or a gap in the export.
6. AGENT_CONTRACT §9's real-time voice session (a provider audio stream, `mode` chosen server-side)
   is explicitly provisional and unbuilt. Voice mode in this build is the cascade the Wave B brief
   names instead: the shared mic sheet gates the microphone, `capabilities/audio-recorder.js`
   records, `POST /api/speech/transcribe` turns the clip into text (no `language` is sent: the
   learner may speak their support language or the one they are learning, and the endpoint accepts
   only en|zh when it is named), the text becomes an ordinary turn, and a finished reply's segments
   (skipping `reference`-style ones, and nothing at all on a metered turn, §12 S12) are read aloud
   with the browser's own `speechSynthesis` (`screens/orena/voice.js`). No server audio_chunk is
   ever played. This is a placeholder for §9's real session, not a claim that a live provider voice
   session exists.
7. The shared Mic state sheet (frame 62) has no state for "Orena could not turn your voice into
   text": its `provider` state is Speaking's ("Assessment is unavailable", "Retry assessment",
   "Continue without score", "Your recording is kept") and would say things that are false here (no
   score, no recording kept). Voice mode answers a failed transcription with one toast line instead
   (`voiceTranscribeFailed`); permission, blocked and "we didn't hear you" use the shared sheet as
   drawn. If the design wants a sheet for it, it needs its own state.
8. Rule 50 (D-087) drops, all restating a control or filling a state the screen already shows: the
   panel header's subtitle "About your selection · closing returns you to the same place" (it also
   wraps to two lines in the 440px sheet and says "selection" when the context is a whole video or a
   grammar point - the context pill below it already names what Orena is attached to); the voice
   row's fixed lines ("Tap the mic and ask your question", "Say your question…", "Answering out loud
   · reply is in the chat") and the status suffix ("Ready · tap the mic to speak" is "Ready"); the
   voice screen's context line ("Ask anything about your learning"); frame 55/56's sample starter and
   suggestion chips (only the reply's own `suggestion` events are drawn, rule 40); the voice screen's
   "Microphone isn't available here, so a demo question is used" (a prototype-only simulation).
   The rail card's "Your study companion" is N-7.
9. Literal colours the source draws on the voice controls, the composer's shadow and the immersive
   voice screen have no token yet: `orena.css` keeps them in one `:root` block at its top
   (`--sh-composer`, `--mark-glow-hero`, `--voice-*`), marked KIT REQUEST. Until that block moves to
   `kit/tokens.css` (a cut and paste; nothing below it changes) `scripts/test_orena_kit.mjs` reports
   those lines and nothing else.

### Open design questions for the human

**Answered 2026-09-29 (D-098):** 1 - as the frame draws, nothing added; 2 - File wired to
`POST /api/media-learning/upload` with that endpoint's own type/size limits; 3 - overtaken
(R5 retired); 4 - open, the human answers after looking; 5 - segmented control up to 4
languages, a picker from the kit's sheet and rows beyond; 6 - authorised with the kit's
existing tokens and components, modelled on the timeline, reviewed by eye.

Real product/content decisions this section's entries above could not resolve
by building conservatively - each already has its own no-invented-data
fallback in place; these ask which fallback should become the real feature.

1. **Today** (frame 10-Today.html, N-21) - the brief's own spec,
   `docs/design/canonical-ui/brief/ORENA_DESIGN_SPEC.md` §7, lists parts **D**
   ("review reminder pill", "N mục cần ôn" linking to My Library's Due Review)
   and **G** (practice entry shortcuts) as part of Today's structure, with no
   phasing note - but the pinned frame itself draws neither. Built as the
   frame draws it (rule 43/44): neither is on the screen. Is their absence
   from this particular export intentional for this revision, or should a
   future revision add them?
2. **Import** (`screens/import/sheet.js`, frame 58-Import.html) - the design's
   own script toasts "Text and File import are not built in this round" for
   both; this build already goes further than the design for Text (a real
   device-memory path into the Reader), matching the design's toast for File
   only. `infrastructure/api.js` does carry a real learner-facing upload route
   (`api.mediaUpload`, `POST /api/media-learning/upload`, already used
   elsewhere for a learner's own media file) - it is not yet known whether
   that route fits whatever "File" in Import is meant to accept (a document
   for Reading vs. a media file), so wiring it was not assumed. Wire File to
   it now, ahead of the design's own phasing, or wait for a design revision
   that specifies File's real shape?
3. **Grammar Concept** (N-33) - _Overtaken (2026-09-28): the human is retiring R5;
   Grammar Lab becomes the only grammar source, rendered from a grammar content
   contract not yet written. This question will not be answered for R5._ The
   Chinese-target (HSK) curriculum's
   explanatory prose and, worse, its lesson titles exist only in Vietnamese,
   with no English/Chinese field or locale-map to select from. A learner
   whose support language is not Vietnamese currently sees a Vietnamese
   heading and (for the prose fields) Vietnamese explanation text. What
   should that learner see instead until the content is authored in English
   and Chinese - blank the field (rule 40's honest-empty, losing the teaching
   content entirely), keep the Vietnamese text as the closest thing to real
   content (today's choice for the prose fields, not available for `title`),
   or something else?
4. **Grammar Concept template** (`SCRATCH/reports/primitives.md`, design
   inventory E5) - the pinned design carries two structurally different
   source frames for this one screen, `23-Grammar-Concept.html` (hand-built)
   and `47-Grammar-Concept.html` (a generic template), with no note on which
   is canonical. `kit/components.js`'s `pageHeader()` currently defaults to
   the generic frame's numbers. Which frame is the real one?
5. **Settings, Support language** (`screens/settings/`, frame 26) - drawn as
   a segmented control, which reads as a design assuming a short list; the
   real backend list is about a dozen languages, kept usable today with
   horizontal scroll inside the control (rule 49). Worth a picker/sheet
   instead if the support-language list keeps growing?
6. **Grammar on Grammar Lab content (2026-09-28, before the content contract's
   PR).** Reading the pinned design for what the rebuilt Grammar screens need
   (review checklist kept for the PR review) found four things the design
   itself does not settle: (a) only the **timeline** illustration is drawn
   (frame 23); **word_order** and **morphology**, which the human listed, are
   named in the brief but drawn nowhere, so building them needs a design or an
   explicit direction (rule 43); (b) the design's own router sends a Chinese
   learner straight to one fixed concept, so **no Chinese Grammar Library** is
   drawn; (c) **no Chinese-specific structure** (measure words, 把/被, aspect
   了/过/着, complements) is drawn on a Grammar screen - "measure word" appears
   only as a Writing finding; (d) the example highlights and the formula's
   role colours are **not linked** in the design (two fixed highlight slots),
   so whether the contract should carry matching roles is a choice. Item 4
   above (frame 23 or 47) decides which of these fields are required.

# CHỜ NGƯỜI QUYẾT ĐỊNH — sổ đăng ký mở (cập nhật 2026-09-22)

Đây là **danh sách duy nhất** cần anh duyệt. Mỗi mục ghi rõ đang làm gì và hai lựa chọn, để chỉ
cần chọn chứ không phải đọc lại code. Các mục bên dưới sổ này là **bằng chứng đo đạc theo từng
màn** - số liệu, cái gì đã sửa, sửa theo frame nào - không phải việc đang chờ.

Human, 2026-09-22: "phần này chưa có chức năng thì note lại và tôi sẽ review lại sau và quyết định
các hành động cho nó." Mọi việc dưới đây **đã dừng lại đúng chỗ này**, không tự quyết, không bịa dữ
liệu. Các mục ở trên là ghi chép chi tiết theo từng màn; phần này là danh sách gọn để duyệt.

## A. Nút đã vẽ nhưng chưa có hành vi

| #   | Ở đâu                                                            | Tình trạng                                                                                                                                | Cần anh quyết                                                                    |
| --- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| A1  | Reader · "Lưu bài" và "Đọc tiếp sau"                             | Frame cho hai nút **cùng icon bookmark** và không nói hành vi. Đang làm: "Lưu bài" bật/tắt đánh dấu; "Đọc tiếp sau" đánh dấu rồi rời bài. | Hai hành động hay một? Nếu một thì thanh còn 5 nút.                              |
| A2  | Reader · "Nghe"                                                  | Disabled, có title "sắp có". Văn bản chưa có audio đọc. Frame vẽ nút này bật.                                                             | Đọc bằng TTS, hay bỏ nút khỏi thanh cho tới khi có audio?                        |
| A3  | Reader · "Kiểm tra hiểu"                                         | Disabled khi bài không kèm câu hỏi (sách nhập không có).                                                                                  | Sinh câu hỏi bằng AI, hay ẩn nút khi không có?                                   |
| A4  | Listening · "Kiểm tra hiểu"                                      | Cùng câu hỏi, đã treo từ trước.                                                                                                           | Như trên.                                                                        |
| A5  | Book detail · 3 nút icon (bookmark, tải về, ⋯)                   | Disabled, "sắp có". Frame **không vẽ** chúng.                                                                                             | Xoá theo frame, hay giữ và làm chức năng?                                        |
| A6  | Profile · "Chia sẻ", "Chỉnh sửa", huy hiệu kim cương trên avatar | Frame vẽ cả ba; app chưa có hành vi nào cho chúng nên chưa dựng.                                                                          | Chia sẻ cái gì và sửa được những gì? Huy hiệu kim cương là bậc, hay là thứ khác? |

## A2. Hồ sơ (Profile) — đã dựng 2026-09-22

Thiết kế **có** màn này, ở `Orena Hạn mức sử dụng.dc.html` (human chỉ chỗ; file **không nằm trong cache**
ghim, phải đọc từ nguồn). Trước đó Profile chỉ là một dialog; nay là một điểm đến `#/profile`, tab thứ năm
trỏ tới nó thay vì mở sheet.

Dựng theo số đo frame, đã verify trong app: hero padding 30 / r20 / gap 30, avatar 132, tên Nunito 34/800,
panel hạn mức rộng 560 padding 26; mobile 390: avatar 96, tên 24, hai cột xếp dọc, không tràn ngang.

**Dữ liệu thật**: gói và hạn mức đọc từ `/api/product/me` - tên gói, giới hạn tháng và số đã dùng cho từng
tính năng. Không mock, không phần trăm bịa.

**Chưa có, nên để trống và nói rõ** (rule 4): **XP** và **chuỗi ngày** - frame vẽ "15 840 XP" và "128 ngày
liên tiếp" nhưng Orena không đếm cái nào. **Khung rank** chờ `tier`. Nút **Chia sẻ / Chỉnh sửa** và huy hiệu
kim cương trên avatar: frame có vẽ, app chưa có hành vi cho chúng - xem A6 bên dưới.

**Mâu thuẫn trong chính thiết kế, cần anh chốt**: `Orena Hạn mức sử dụng` vẽ avatar bằng **vòng
conic-gradient + huy hiệu kim cương**, còn `Orena Rank Frame Master v2` vẽ **khung pha lê nhiều mặt cắt**.
Brief của anh nói rõ là pha lê, nên tôi dựng component pha lê; màn Profile hiện đang để avatar trơn cho tới
khi có `tier`. Hai file vẽ hai thứ khác nhau cho cùng một chỗ.

## B. Thành phần frame vẽ mà app chưa dựng

| #   | Ở đâu                               | Tình trạng                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | **Progress**                        | **Dựng lại theo frame MỚI** (2026-09-22, sau khi re-pin - frame cũ trong cache đã lệch 22 KB). Frame mới **bỏ hẳn** hàng "Bằng chứng gần nhất", thay bằng **thang cấp bậc 20 bậc** (lưới 4 cột, ô 227x56 r14, ba trạng thái: mở / hiện tại / khoá) + **thẻ CẤP BẬC** (102 cao, pad 16/18, r18). Cột phụ 600 giữ heatmap, hàng kỹ năng **có thanh**, và "Việc nên làm tiếp" là **thẻ có mũi tên** (78 cao, r17, kính tiêu điểm). Ngưỡng 20 bậc lấy từ chính frame: 50 · 150 · 300 · 500 · 700 · 950 · 1200 · 1450 · 1600 · **?** · 3000 · 4500 · 6000 · 8000 · 10000 · 13000 · 16000 · 20000 · 25000 · 30000 từ. **Bậc 10 (Virtuoso) frame không ghi số** - nó vẽ "BẬC HIỆN TẠI" đè lên - nên app hiển thị "—" và không đoán. Còn thiếu so với frame: **hàng 4 panel thứ hai** (Vừa học xong · Từ đang ôn · Kiểm tra hiểu · Nhớ lại) vì cần số liệu ôn tập/hiểu mà backend chưa có (C4). |
| B2  | **Hệ cấp bậc (rank)**               | **Component đã dựng** (`ui/rank-frame.js`, port từ "Rank Frame Master v2": 20 bậc, 5 chặng, một nguồn sáng −48°, SVG sinh từ toạ độ cực, không raster; gate `test_orena_rank_frame.mjs`). **Chưa hiện ở đâu** vì `ProgressOverview.tier {name, level, current, target}` chưa ai phục vụ - cần **ngưỡng mỗi bậc**, là quyết định sản phẩm. Ngày có `tier`, khung pha lê hiện luôn, không cần sửa code. Frame: "CẤP BẬC · Virtuoso · bậc 4 · 1 994 / 3 000 từ". Anh muốn rank là **khung avatar** pha lê SVG+CSS, nhiều họ màu.                                                                                                                                                                                                                                                                                                                                                           |
| B3  | Book detail · dải từ đã lưu ở hero  | Frame đặt "BẠN ĐÃ LƯU TỪ ĐÂY" + chip từ trong hero; app có dữ liệu nhưng để ở cột phải.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| B5  | **Progress · tab "Xu hướng"**       | **ĐÃ DỰNG** (2026-09-22): tab Tổng quan / Xu hướng ở `#/progress?tab=trends`, ba khối _Đang tốt lên · Dựa trên gì · Lỗi lặp lại_. **Mọi con số là 0 / "—"** vì chưa có mô hình xu hướng, mô hình lỗi lặp lại, hay lịch sử theo từng thước đo - `ProgressTrends.json` chưa ai phục vụ. Frame gốc: `Progress trends` (`data-screen-label="Progress trends"` + bản mobile) với các hàng xu hướng và thẻ độ khó. App **chưa có tab nào** để tới đó, và chưa dựng màn. Cần dữ liệu xu hướng theo thời gian (`ProgressTrends.json`) mà backend chưa phục vụ.                                                                                                                                                                                                                                                                                                                                  |
| B6  | **Progress · hàng 4 panel thứ hai** | **ĐÃ DỰNG** (2026-09-22), 4 panel 375x147 pad 16/18 r18 gap 20. _Vừa học xong_ và _Từ đang ôn_ chạy bằng số thật từ kho từ của học viên; _Kiểm tra hiểu_ và _Nhớ lại_ render **0** vì chưa có số liệu (C4). Vị trí: **nằm giữa** hàng 3 số lớn và thang cấp bậc, chạy hết chiều ngang: _Vừa học xong_ (14 từ · HSK 2 · trong 3 ngày + chip từ) · _Từ đang ôn_ (42 từ · 18 chữ tới hạn hôm nay + thanh 24/42) · _Kiểm tra hiểu_ (9/11 · câu đúng · 3 bài đọc + dải ô đúng/sai) · _Nhớ lại_ (86% · 312 thẻ trong 7 ngày + thanh + 268 nhớ / 31 chưa chắc / 13 quên). Chưa dựng vì cần số liệu ôn tập và hiểu backend chưa có (C4).                                                                                                                                                                                                                                                        |
| B4  | Reader · panel bên                  | Padding 26 / gap 20 của frame chưa khớp (app 22 / 16). Chưa chỉnh vì **nội dung** panel chưa phải của frame.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

## C. Thiếu dữ liệu backend — UI không được bịa

| #   | Thiếu gì                                                          | Hệ quả thấy được                                                                                                                                                              |
| --- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | CEFR level + ước lượng **số phút đọc** cho từng mục catalogue     | Thẻ thư viện thường trống dòng meta; frame luôn in `B1 · tiểu thuyết · 22 phút`.                                                                                              |
| C2  | Thời gian đọc theo chương                                         | Hàng chương in **số từ**, frame in **số phút**.                                                                                                                               |
| C3  | Cấp độ theo từng kỹ năng (`profile.skill_levels`)                 | Rail không in được level cho Đọc/Nghe/Nói/Viết.                                                                                                                               |
| C4  | Chuỗi ngày, thời gian học 90 ngày, hoạt động 18 tuần, ngưỡng rank | Các ô Progress sẽ phải in "—" nếu dựng theo frame ngay bây giờ.                                                                                                               |
| C5  | Câu hỏi hiểu cho sách nhập                                        | A3 ở trên.                                                                                                                                                                    |
| C6  | **Ngưỡng bậc 10 (Virtuoso)**                                      | Frame vẽ "BẬC HIỆN TẠI" đè lên số của chính nó, nên 19/20 ngưỡng có số, riêng bậc 10 không. Learner ở giữa 1 600 và 3 000 từ sẽ bị tính là bậc 9. Cần anh cho **một con số**. |

## C. Dữ liệu backend cần cho UI đã dựng sẵn (2026-09-22)

Human: _"Backend chưa có thì note lại làm sau. UI phải có hoàn chỉnh đã."_ Các màn dưới đây **đã dựng đủ
component**, đang render 0 / "—" đúng rule 4, và sẽ tự có số khi backend phục vụ:

| Ô đang trống                             | Cần gì                                               |
| ---------------------------------------- | ---------------------------------------------------- |
| Progress · Kiểm tra hiểu                 | số câu đúng / tổng, theo 7 ngày                      |
| Progress · Nhớ lại                       | số thẻ đã chấm 7 ngày + tách nhớ / chưa chắc / quên  |
| Progress · Chuỗi ngày, Thời gian học     | đếm ngày liên tiếp, thời gian học 90 ngày            |
| Progress · heatmap 18 tuần               | hoạt động theo từng ngày                             |
| Progress · thời gian 7 ngày theo kỹ năng | thời gian theo kỹ năng (chép chính tả tính vào Nghe) |
| Xu hướng · Đang tốt lên                  | 4 thước đo so với 4 tuần trước                       |
| Xu hướng · Dựa trên gì                   | đếm thẻ / bản viết / câu hỏi / phiên nói / bài đọc   |
| Xu hướng · Lỗi lặp lại                   | mô hình lỗi lặp: tên lỗi, số lần, ví dụ, nguồn       |
| Hồ sơ · XP và chuỗi ngày                 | điểm kinh nghiệm và chuỗi ngày                       |
| Hồ sơ · khung rank trên avatar           | `ProgressOverview.tier` + ngưỡng bậc 10 (C6)         |

## D. Quyết định quy tắc, không phải quyết định code

| #   | Việc                                 | Hai lựa chọn                                                                                                                                                                                               |
| --- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Chip lọc thư viện                    | Frame liệt kê **11** loại; app chỉ hiện chip cho loại **thực sự có nội dung** (nay là 4). Hiện đủ 11 thì có chip bấm vào không ra gì.                                                                      |
| D2  | Ghi công nguồn & bản quyền           | Frame **không vẽ ở đâu cả**. Nút đã bỏ theo yêu cầu; khối ghi công hiện nằm dưới bài đọc vì văn bản đã xuất bản buộc phải có. Đặt ở đâu là của anh.                                                        |
| D3  | Màu chữ                              | Frame dùng `rgba(255,255,255,0.72 / 0.55)`; app đọc token `--text-secondary` / `--text-muted`. Component chỉ được đọc token, nên nếu phải khớp tuyệt đối thì sửa ở `theme.css`, không sửa trong component. |
| D4  | DM Mono → Roboto Mono cho tiếng Việt | Đã treo từ trước; mọi nhãn mono tiếng Việt đang rơi về Roboto Mono.                                                                                                                                        |
| D5  | Ink / Paper                          | Anh nhắc trong yêu cầu, nhưng D-066 đã khai tử và code đã gỡ theme picker. Đang làm **một** hệ Dark Glass. Muốn hai theme trở lại thì là quyết định sản phẩm mới.                                          |

## S. Speaking — nhánh `feature/speaking` (2026-09-23)

Dựng theo `Orena-Speaking.dc.html` **đọc tại nguồn** (DesignSync, re-pin 7 → 18 frame,
`docs/design/canonical-ui/SYNC_2026-09-23.md`). Quyết định của anh: D-084 ("Đạt" = cờ của provider;
thư viện Speaking riêng + luồng từ Listening), D-075, D-076 (câu cần luyện lại = câu có cờ; audio chỉ
trong phiên, tuỳ chọn giữ 5 bản/câu trên máy; free talk chỉ chấm số đo thật; làm đường thanh điệu đo
thật và nghe nhại; hoãn cài đặt Speaking và SRS). Những chỗ dưới đây frame vẽ nhưng chưa có dữ liệu
hoặc quyết định, nên **không bịa**; mục đã được anh trả lời ghi rõ.

| #   | Ở đâu                                                                                                  | Đang làm gì                                                                                                                                                                                                                                                                                                                                                                                                             | Cần anh quyết                                                                       |
| --- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| S1  | Thư viện · chip loại luyện                                                                             | Chỉ hiện chip cho loại có nội dung thật: "Nhại theo clip" (bài Listening có shadowing) và "Nói tự do". Catalogue Speaking riêng (`writing_coach/content/speaking_catalog.v1.json`) **rỗng** - không seed nội dung giả (quyết định 10).                                                                                                                                                                                  | Nội dung cho Đọc theo câu / Luyện âm / Kể lại / Phỏng vấn mô phỏng (việc nội dung). |
| S2  | Sóng âm của mẫu                                                                                        | **Đã làm:** sóng và cao độ của câu mẫu đo từ audio thật, lấy cùng origin qua `/api/speaking/model-audio/...` (host catalogue không có CORS). Lúc chưa ghi, cột phẳng.                                                                                                                                                                                                                                                   | -                                                                                   |
| S3  | Câu nhận xét kiểu "Thanh 3 bị đọc thành thanh 2"                                                       | Không viết: Azure không chấm thanh; đường cao độ đo thật được vẽ, **không kèm lời phán** (D-076). Đo khoảng hở tiếng Trung: lệch thanh làm điểm âm tiết giảm 6/7 lần thử nhưng Azure chỉ cờ 2/7; 3↔2 không bị cờ (`docs/operations/SPEAKING_AZURE_E2E_2026-09-23.md`). **Known gap (D-077):** Azure chưa đủ tin cậy để chấm thanh; chưa thêm SpeechSuper.                                                               | Provider chấm thanh trả phí - cổng của anh, chưa làm.                               |
| S4  | Chi tiết một chữ · "BẠN ĐỌC"                                                                           | **Đã làm:** đường cao độ của lượt thu, đo từ audio (YIN), cắt theo mốc thời gian của từ. Ô "MẪU" vẫn vẽ hình thanh từ pinyin của bài (hình chuẩn), còn so sánh với mẫu đo thật ở màn "So với mẫu".                                                                                                                                                                                                                      | -                                                                                   |
| S5  | Giá trị LƯU LOÁT màu hổ phách                                                                          | Để trắng: không có ngưỡng lưu loát (quyết định 6: không đặt ngưỡng).                                                                                                                                                                                                                                                                                                                                                    | -                                                                                   |
| S6  | Từ "Đạt" nhưng một âm rất thấp                                                                         | Hàng ghi "Đạt" theo cờ provider; âm yếu hiện trong chi tiết, không đè verdict (quyết định 7).                                                                                                                                                                                                                                                                                                                           | -                                                                                   |
| S7  | "Luyện riêng chữ này"                                                                                  | **Đã làm** (quyết định 8): có nút gợi ý quay về cả câu (`data-sp-back-line`).                                                                                                                                                                                                                                                                                                                                           | -                                                                                   |
| S8  | "Câu trước"                                                                                            | Không thêm (quyết định 9).                                                                                                                                                                                                                                                                                                                                                                                              | -                                                                                   |
| S9  | "Chạm vào một chữ để nghe riêng"                                                                       | Giọng đọc của thiết bị (speechSynthesis) như lớp tra từ; clip mẫu không có mốc theo từ.                                                                                                                                                                                                                                                                                                                                 | Chấp nhận TTS thiết bị?                                                             |
| S10 | Free talk · "CỤM CÓ THỂ DÙNG", dịch câu bạn vừa nói, cấp độ, nhãn loại lỗi ("NGỮ PHÁP · V2")           | Không có dữ liệu → không vẽ. Thẻ sửa lấy từ coaching (`landed_differently`), nhãn là nhận định của coaching.                                                                                                                                                                                                                                                                                                            | Nội dung cụm từ; có dịch câu học viên nói không.                                    |
| S11 | Thư viện · "Chủ đề của bạn"                                                                            | Giữ ở nút hành động của thanh thư viện. Frame Speaking không vẽ nút này.                                                                                                                                                                                                                                                                                                                                                | Giữ ở đó, hay chuyển vào "⋯"?                                                       |
| S12 | "Ghi âm của tôi · ĐÃ LƯU", "Lưu vào Thư viện" (04, 05)                                                 | Không dựng (D-076: không lưu server/thư viện). Tóm tắt bài ghi "Đã lưu kết quả vào lịch sử luyện" (điểm, không audio).                                                                                                                                                                                                                                                                                                  | Sau review schema + privacy.                                                        |
| S13 | Chuỗi ngày trên thanh workspace                                                                        | Hiện **0** (chưa đo), như Dictation.                                                                                                                                                                                                                                                                                                                                                                                    | Như C4.                                                                             |
| S14 | Free talk result (04) · "Xem kỹ hơn · Phát triển thành bài viết · Bắt đầu trò chuyện"                  | **Quyết (D-077):** giữ cả ba, một bước vào trong: nút "⋯" trên thanh của màn kết quả mở sheet "luyện sâu" dùng chung với Listening.                                                                                                                                                                                                                                                                                     | -                                                                                   |
| S15 | Free talk · "NÓI LẠI CÂU NÀY"                                                                          | **Quyết (D-077):** trường `say_again` của hợp đồng `spoken-response` được duyệt: bắt buộc trong schema, chỉ trả về khi là chữ viết của ngôn ngữ đang học, không thì rỗng. Frame tô tím chữ đã sửa; app chưa tô (cần so khớp câu nói với câu sửa) - gap còn mở.                                                                                                                                                          | Có cần tô chữ đã sửa không.                                                         |
| S16 | Nghe nhại · câu tô dần theo mẫu ("请给我们" tím, phần sau mờ)                                          | Chưa làm: câu mẫu không có mốc thời gian theo từ.                                                                                                                                                                                                                                                                                                                                                                       | Có cần không (cần mốc theo từ của clip).                                            |
| S17 | Nghe nhại · "không tai nghe"                                                                           | Ghi chú cố định của frame "Đeo tai nghe…" luôn hiện. Frame ghi "nếu phát hiện loa ngoài thì gợi ý, ghi chú dưới điểm" - trình duyệt không phân biệt loa/tai nghe đáng tin cậy, nên không phát hiện và không ghi chú dưới điểm.                                                                                                                                                                                          | Chấp nhận?                                                                          |
| S18 | Nghe nhại · 3-2-1                                                                                      | Frame ghi "đếm 3-2-1" nhưng không vẽ chỗ đặt; app viết số vào dòng gợi ý dưới nút. Trong lúc ghi, tốc độ và thu lại **bắt đầu lại lượt** (tốc độ mới / cùng tốc độ).                                                                                                                                                                                                                                                    | -                                                                                   |
| S19 | Micro bị chặn (09 A) · "Mở Cài đặt"                                                                    | Trang web không mở được cài đặt hệ thống; nút là "Thử lại" (xin quyền lại), chữ hướng dẫn chỉ biểu tượng ổ khoá.                                                                                                                                                                                                                                                                                                        | -                                                                                   |
| S20 | Tóm tắt bài (05) · "Luyện lại 2 câu dưới 80"                                                           | Theo D-076: "Luyện lại N câu có chữ bị đánh dấu". Chip "CHỮ HAY SAI" ghi pinyin + số lần, **không** ghi "thanh 3" (không đo thanh). Không đưa vào SRS (hoãn).                                                                                                                                                                                                                                                           | -                                                                                   |
| S21 | So với mẫu (06) · dòng "想: mẫu xuống rồi lên, bạn đi ngang" và "Giữ 5 lần gần nhất… lưu vào Thư viện" | Không có lời phán (D-076); dòng giữ bản thu thay bằng ô chọn "Giữ bản thu gần đây trên máy này" (D-076). "Nghe xen kẽ" phát mẫu rồi lượt thu, theo câu.                                                                                                                                                                                                                                                                 | -                                                                                   |
| S22 | Cài đặt Speaking, trạng thái rỗng (09 D)                                                               | Cài đặt hoãn (D-076). Trạng thái rỗng không tới được: thư viện luôn có bài Listening có shadowing.                                                                                                                                                                                                                                                                                                                      | -                                                                                   |
| S23 | Nhận dạng tiếng Trung trong free talk                                                                  | ASR (Groq Whisper) đôi khi trả chữ phồn thể ("英國人"); hiện đúng như nhận được.                                                                                                                                                                                                                                                                                                                                        | Có ép giản thể không?                                                               |
| S24 | Grammar · trang của nó (`#/practice?intent=grammar`)                                                   | Lối vào duy nhất trước đây là trang Practice cũ, nay đã bỏ (D-078: `#/practice` về Home). Vẫn mở được từ một mục Continue và từ trong Grammar; thiết kế không vẽ chỗ nào cho Grammar.                                                                                                                                                                                                                                   | Grammar vào từ đâu (Home, Library, một kỹ năng)?                                    |
| S25 | Speaking · bố cục theo D-078 (khác frame có chủ ý)                                                     | Hàng hành động của kết quả thành một hàng: "Nghe bản của bạn", "So với bản mẫu" (chỉ còn icon khi panel hẹp, vẫn có tên cho trình đọc màn hình), "Câu tiếp" là hành động chính; nút "Thu lại" thứ hai trong panel bỏ (thu lại là micro và nút quay lại bên cạnh). Hai panel khép cùng một đáy (dải điều khiển = dải hành động). Dòng từ gọn hơn (≈56px). Clip mẫu co theo chiều cao còn lại (16:9) và nhường chỗ trước. | - (quyết định của anh ở D-078)                                                      |

## E. Cổng kích hoạt (không phải việc của lane này)

| #   | Việc                                                                                                                                                                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1  | `reading.discussion_turn` hiện **đếm usage, không chặn ai**. Bật enforcement Free/Premium là cổng kích hoạt thương mại, cần anh mở, và khi mở thì phải đi qua quota ledger chứ không phải `usage_events`. |
| E2  | Tầng fallback thứ ba cho AI router: chỉ cần thêm một trường config, không cần code.                                                                                                                       |

## F. Nợ kỹ thuật thấy được trong phiên

| #   | Việc                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1  | `scripts/test_orena_vocabulary_theme_tokens.mjs` và `scripts/test_orena_writing_workspace.mjs` **fail sẵn từ `3deab1e`**, kiểm chứng trên cây sạch. Chưa sửa vì ngoài phạm vi.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F4  | **Sandbox `:8011` mất sạch dữ liệu học viên sau khi Docker engine treo và được khởi động lại (2026-09-22 05:51).** Bảng còn nguyên, schema vẫn ở `20260922_0012`, nhưng `essays`, `reading_sessions`, `text_discussions`, `usage_events` đều **0 dòng**; sáng cùng ngày có 10 bài viết, một luồng thảo luận và các dòng usage. Nguyên nhân **không xác định được** từ đây. Điều xác minh được: container `orena-foundation-postgres` có `Mounts: []` - **không gắn volume nào**, dữ liệu nằm trong lớp ghi của container, nên runtime này chưa bao giờ bền vững. Volume của production và preview (`ai-writing-coach-data`, `ai-writing-coach-postgres-data`) vẫn còn nguyên, không bị đụng tới. |
| F2  | Sandbox `:8011` đang có 1 EPUB thử ("Kafka pa stranden", 5 chương, id `ce71a298…`) tôi nhập để đo màn Book detail. Giữ để anh xem, hay archive?                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F3  | Chưa đo lại Reader và Library ở **390 mobile** sau các thay đổi hôm nay; đã đo desktop 1920.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

---

## Summary by canonical screen

| Canonical UI                      | Required contract                          | Backend implementation                                                                                                                                   | Data source / DB                                      | Tests                                                                                                                                                       | Status                                               |
| --------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Quick Sheet, word                 | `WordDetail`                               | `/api/dictionary/word-detail` (projection in `word_detail.py`) over `reading_lookup` and the contextual explanation; `ui/quick-sheet.js`                 | vocabulary catalog, tagger, AI capability             | `tests/test_word_detail.py` (held to the pinned contract), `test_orena_reading_room.mjs`, `test_media_interaction`                                          | IN_PROGRESS (S1 built; see log)                      |
| Sentence sheet                    | `SentenceSheet`                            | `/api/dictionary/sentence-sheet`; parts and vocabulary in `ui/quick-sheet.js`                                                                            | as above                                              | as above                                                                                                                                                    | IN_PROGRESS (S1 built; see log)                      |
| Writing review                    | `WritingReview`                            | `GET /api/essays/{id}/review` (`writing_contract.py`); `example` in the evaluator contract (v2.5), English `register` category; `ui/writing-feedback.js` | `essays`                                              | `tests/test_writing_contract.py` (held to the pinned contract), `test_writing_evaluation`, `test_orena_writing_review.mjs`                                  | IN_PROGRESS (S2 built; see log)                      |
| Writing revision                  | `RevisionCompare`                          | `GET /api/essays/{id}/revision`; `revision_delta` judged by the words                                                                                    | `essays` chain                                        | `test_writing_revision_contract`, `test_writing_contract`                                                                                                   | IN_PROGRESS (S2 built; see log)                      |
| Writing entry, workspace          | `ContentCard`, draft                       | `/api/drafts`, `/api/tasks/generate`; prompt library                                                                                                     | account backbone, catalogue                           | `test_work_api`, `test_orena_writing_workspace.mjs`                                                                                                         | BLOCKED (`[CONTENT]` prompts; drafts past sandbox)   |
| Listening library, workspace      | `ContentCard`, `AudioPlayer`, `Transcript` | `listening_api`, `media_*`; `content_type` derived; library `ui/library-browse.js`; workspace details open (see log)                                     | catalogue JSON, `listening_progress`, device memory   | `test_listening_*`, `test_orena_library.mjs`, `test_orena_pure_listening.mjs`                                                                               | IN_PROGRESS (S3a built, S3b open)                    |
| Dictation                         | `DictationResult`                          | `capabilities/dictation-result.js`, `ui/dictation-screen.js`; `pinyin_alignment.py`; the evaluator and evidence save unchanged                           | outcomes, catalogue JSON                              | `test_orena_dictation_screen.mjs`, `test_pinyin_alignment.py`, `test_dictation_evaluator.mjs`                                                               | IN_PROGRESS (S3b built; DC-5 needs a decision)       |
| Reading library, book detail      | `ContentCard`, `Chapter`                   | `reading_library_api`; add kind, level, duration                                                                                                         | `reading_books`, `reading_book_chapters`              | `test_reading_library_api`, `test_orena_reading_library.mjs`                                                                                                | BLOCKED (`[REVIEW]` catalogue schema)                |
| Reading workspace                 | `ReadingChapter`                           | `libraryBookChapter`, `readingTranslate`; whole-chapter translation                                                                                      | book assets, translation cache, device `place.within` | `test_reading_translation`, `test_orena_reading_room.mjs`, `test_orena_reader_place.mjs`                                                                    | IN_PROGRESS (S4: whole-chapter translation)          |
| Reading comprehension             | comprehension                              | per-question check endpoint (landed: `POST /api/reading/session/{id}/answer/{index}`); per-chapter generation                                            | `reading_sessions`, `reading_attempts`                | `test_reading_answer_per_question`, `test_orena_comprehension.mjs`                                                                                          | READY for the check; per-chapter generation still S4 |
| Search (all libraries)            | `ContentCard[]`                            | catalogue search API, read-only                                                                                                                          | books, listening, vocabulary, collections             | add                                                                                                                                                         | IN_PROGRESS (S5)                                     |
| Speaking library                  | `ContentCard`                              | `/api/speaking/library`: Speaking catalogue (empty) + shadowable Listening lessons                                                                       | catalogue                                             | `test_speaking_library`                                                                                                                                     | IN_PROGRESS (built; catalogue `[CONTENT]`)           |
| Speaking workspace                | `PronunciationResult`                      | provider seam + Azure adapter built; SpeechSuper / tone contour not built                                                                                | `speaking_attempts` (no raw audio)                    | `test_speech_pronunciation`, `test_speech_pronunciation_api`, `test_m3_pronunciation_contract.mjs`, `test_speaking_take.mjs`, `test_speaking_workspace.mjs` | IN_PROGRESS (built); E2E `[PROVIDER]`                |
| Vocabulary library, card, strokes | `VocabularyCollection`, `WordDetail`       | `vocabulary_library`, stroke order                                                                                                                       | `vocabulary_*`                                        | `test_vocabulary_library*`, `test_chinese_stroke_order`, `test_orena_vocabulary_library.mjs`                                                                | IN_PROGRESS (L)                                      |
| Vocabulary context clips          | `ContextClip`                              | word to clip index over listening transcripts                                                                                                            | new index                                             | add                                                                                                                                                         | BLOCKED (`[REVIEW]`/index design)                    |
| Vocabulary review                 | `VocabularyCard`                           | three-grade scheduler and interval preview                                                                                                               | `saved_words`                                         | `test_vocabulary_cards`, `test_orena_vocabulary_card.mjs`; add SRS tests                                                                                    | BLOCKED (`[REVIEW]` rule change)                     |
| Progress overview, trends         | `ProgressOverview`, `ProgressTrends`       | read model over the domain owners; every metric carries `measured`                                                                                       | LearnerSummary, events (new)                          | `test_learner_summary`, `test_orena_growth_summary.mjs`                                                                                                     | BLOCKED (`[DEF]`, `[REVIEW]`)                        |
| Home / Discover                   | `AppShell`, `ContentCard`                  | shared card serializer; Continue read model                                                                                                              | catalogues, device continuation                       | `test_orena_discover_layout.mjs`                                                                                                                            | IN_PROGRESS (L)                                      |
| App shell                         | `AppShell`                                 | profile fields; metric fallback                                                                                                                          | profile, LearnerSummary                               | `test_orena_foundation.mjs`                                                                                                                                 | IN_PROGRESS (foundation with S1)                     |

## Requirements

Legend for each table: **Have** is what the backend does today; **Need** is the
change. Group headers name the contract, data source and tests once.

### Shell — `AppShell` · profile, LearnerSummary · `test_orena_foundation.mjs`

| ID    | Canonical UI                               | Have → Need                                                                     | Slice | Status             |
| ----- | ------------------------------------------ | ------------------------------------------------------------------------------- | ----- | ------------------ |
| SH-1  | Display name and avatar                    | `/api/me` gives email and mode → profile fields                                 | L     | BLOCKED `[REVIEW]` |
| SH-2  | Level next to the language ("B1", "HSK 2") | CEFR `declared_level`, not stored, no HSK → stored level per language framework | L     | BLOCKED `[REVIEW]` |
| SH-3  | Language ("NORSK" in the mock)             | `/api/platform/languages` is en and zh → none; Norwegian is demo data           | -     | IN_PROGRESS        |
| SH-4  | Rank label ("Virtuoso · bậc 4")            | none → rank definition and ladder; shows `0` until measured                     | L     | BLOCKED `[DEF]`    |
| SH-5  | Streak in the top bar and headers          | none → streak definition and measurement; shows `0`                             | L     | BLOCKED `[DEF]`    |
| SH-6  | Level per skill in the rail                | none → stored level per skill                                                   | L     | BLOCKED `[REVIEW]` |
| SH-7  | Search field, desktop and phone            | none server-side → S5                                                           | S5    | IN_PROGRESS        |
| SH-8  | Active nav and skill, five-item phone bar  | client routing → none                                                           | -     | IN_PROGRESS        |
| SH-9  | Loading, empty, error                      | baseline draws none → keep the existing skeleton and degraded panel             | -     | IN_PROGRESS        |
| SH-10 | Auth                                       | Google OAuth, session guard, admin guard → none                                 | -     | IN_PROGRESS        |

### Home — `AppShell`, `ContentCard` · catalogues, device continuation · `test_orena_discover_layout.mjs`

| ID   | Canonical UI                                                               | Have → Need                                                                                                             | Slice | Status              |
| ---- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ----- | ------------------- |
| HM-1 | Continue strip: kind, title, 68%, "còn 4 phút", resume                     | device `continuation`; progress only where a place is recorded → a `ContinueLearning` read model; cross-device is gated | L     | BLOCKED `[REVIEW]`  |
| HM-2 | "Mới cho bạn · phù hợp trình độ"                                           | nothing ranks content → level-based ordering (needs SH-2)                                                               | L     | BLOCKED `[REVIEW]`  |
| HM-3 | Reading, Listening, Vocabulary rails                                       | separate shapes per domain → the shared `ContentCard` serializer                                                        | L     | IN_PROGRESS         |
| HM-4 | Speaking rail                                                              | no Speaking library → SP-1                                                                                              | L     | BLOCKED `[CONTENT]` |
| HM-5 | Writing rail "Gợi ý viết mỗi ngày"                                         | only AI task generation → WR-2                                                                                          | L     | BLOCKED `[CONTENT]` |
| HM-6 | Card: 17 types, skill, hue, badge (ĐANG LUYỆN, ĐÃ LƯU, TẠO RIÊNG, ĐÃ NHẬP) | per-domain fields; hue is artwork → one serializer                                                                      | L     | IN_PROGRESS         |
| HM-7 | Populated rails                                                            | 7 listening lessons, books only after admin import → supply content                                                     | L     | BLOCKED `[CONTENT]` |

### Reading — `ReadingChapter`, `Chapter`, `ContentCard` · `reading_books`, `reading_book_chapters`, assets · `test_reading_library_api`, `test_reading_translation`, `test_orena_reading_library.mjs`, `test_orena_reading_room.mjs`

| ID    | Canonical UI                                                                                       | Have → Need                                                                                                                                      | Slice | Status                          |
| ----- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | ------------------------------- |
| RD-1  | 11 type chips (books, excerpts, articles, news, essays, stories, dialogues, quotes, own, imported) | books carry no kind, level or topic → catalogue metadata                                                                                         | L     | BLOCKED `[REVIEW]`              |
| RD-2  | Card: author, level, kind, minutes                                                                 | author and word count only → level, kind, and an owned reading-speed rule for minutes                                                            | L     | BLOCKED `[REVIEW]`              |
| RD-3  | Search inside the library                                                                          | none → S5                                                                                                                                        | S5    | IN_PROGRESS                     |
| RD-4  | "Nhập văn bản", TẠO RIÊNG / ĐÃ NHẬP                                                                | import exists, device memory → wire the badge                                                                                                    | L     | IN_PROGRESS                     |
| RD-5  | Paged cover grid                                                                                   | cursor and `/cover` exist → none (real art is supply)                                                                                            | -     | IN_PROGRESS                     |
| RD-6  | Book hero: continue chapter, 34%, time left                                                        | `libraryBook`; percent from continuation → `Chapter.progress`                                                                                    | L     | IN_PROGRESS                     |
| RD-7  | Chapter state read / reading / unread                                                              | only the current chapter (device) → durable chapter state                                                                                        | L     | BLOCKED `[REVIEW]`              |
| RD-8  | "Bạn đã lưu từ đây … + 83 từ"                                                                      | saved words carry no book link → word-to-book link                                                                                               | L     | BLOCKED `[REVIEW]`              |
| RD-9  | Book bookmark, menu, listen                                                                        | none; device speech for words → saved items, audio                                                                                               | L     | BLOCKED `[REVIEW]` `[PROVIDER]` |
| RD-10 | Position inside a chapter                                                                          | chapter only → exact position                                                                                                                    | L     | BLOCKED `[REVIEW]`              |
| RD-11 | Bilingual layer                                                                                    | `readingTranslate`, first 12 paragraphs → whole chapter, batched and cached                                                                      | S4    | IN_PROGRESS                     |
| RD-12 | Panel tabs Word, Grammar, Notes                                                                    | Word only → grammar notes and notes                                                                                                              | L     | BLOCKED `[REVIEW]`              |
| RD-13 | Action bar: save, listen, check, discuss, write a response, read later                             | check, discuss (`conversation-turn`) and response (`practice_context`) partly exist; save and read-later do not → wire and add saved items       | L     | IN_PROGRESS                     |
| RD-14 | Comprehension: one question, verdict and "đoạn giúp bạn trả lời", skippable                        | generated sessions hold answer, explanation and evidence, but `/answer` grades the whole set → per-question check; sessions for library chapters | S4    | IN_PROGRESS                     |
| RD-15 | "Bỏ qua vẫn tính đã đọc"                                                                           | no completion record → part of RD-7                                                                                                              | L     | BLOCKED `[REVIEW]`              |

### Quick Sheet — `WordDetail`, `SentenceSheet` · vocabulary catalog, tagger, AI capability · `test_media_interaction`, `test_reading_lookup`, `test_orena_understanding.mjs`, `test_r16_contextual_dictionary.mjs`

| ID    | Canonical UI                                                                           | Have → Need                                                                                                                                        | Slice  | Status                           |
| ----- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------- |
| QS-1  | Layer 1: headword, IPA or pinyin, part of speech, speaker, save                        | lookup returns all of it → serializer                                                                                                              | S1     | IN_PROGRESS                      |
| QS-2  | "Nghĩa ở câu này" in layer 1                                                           | dictionary meaning only; contextual meaning is an AI explain → a contextual-meaning request through the provider abstraction, distinct from lookup | S1     | IN_PROGRESS                      |
| QS-3  | Seven usage levels                                                                     | `USAGE_JUDGEMENTS` are the same seven → rename to the contract values                                                                              | S1     | IN_PROGRESS                      |
| QS-4  | "Vì sao ở đây?": verdict, reason, examples, common mistake, grammar note, related      | `judgement`, `judgement_reason`, `examples`, `counter_examples`, `grammar_notes`, `vocabulary` → map                                               | S1     | IN_PROGRESS                      |
| QS-5  | Core idea, mental model, contrast                                                      | not in the schema → extend the explanation schema                                                                                                  | S1     | IN_PROGRESS                      |
| QS-6  | "Hỏi tiếp" chips and free question                                                     | `follow_ups`, `question` → none                                                                                                                    | S1     | IN_PROGRESS                      |
| QS-7  | Where you met it; your own sentences                                                   | provenance is device memory; essays not indexed by word → `learnerSentences` read model; sources gated                                             | S1 / L | IN_PROGRESS / BLOCKED `[REVIEW]` |
| QS-8  | "Lưu giải thích"                                                                       | no saved explanation → saved explanations                                                                                                          | L      | BLOCKED `[REVIEW]`               |
| QS-9  | Chinese variant with pinyin                                                            | annotate and explain cover it → none                                                                                                               | S1     | IN_PROGRESS                      |
| QS-10 | Writing-feedback variant                                                               | same contract plus `errors[].suggestion` → S2                                                                                                      | S2     | IN_PROGRESS                      |
| QS-11 | Sentence sheet: translation, short explanation, structure, vocabulary with saved state | all but structure → `structure[{chunk, role}]`, language-neutral roles                                                                             | S1     | IN_PROGRESS                      |
| QS-12 | Audio pauses and resumes                                                               | client → none                                                                                                                                      | -      | IN_PROGRESS                      |

### Listening, Dictation — `ContentCard`, `AudioPlayer`, `Transcript`, `DictationResult` · catalogue JSON, `listening_progress`, `shadowing_progress`, outcomes · `test_listening_*`, `test_orena_pure_listening.mjs`, `test_dictation_evaluator.mjs`, `test_orena_dictation_*.mjs`

| ID   | Canonical UI                                                     | Have → Need                                                                                                                                                                                                                        | Slice | Status                                                                 |
| ---- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------------------------------------------------------------------- |
| LS-1 | Nine type chips                                                  | `content_type` derived from playback, topic and tags (`listening_catalog.content_type`, served in `lesson_metadata`); chips only for types some item has; a lesson that says nothing gets none; imported = the learner's own media | S3a   | IN_PROGRESS (built; see log)                                           |
| LS-2 | Card: duration, level, time left, video badge                    | duration on the cover, level, "time left" and a progress bar from the place in device memory, video and provenance badges                                                                                                          | S3a   | IN_PROGRESS (built; see log)                                           |
| LS-3 | Library search                                                   | the bar's search filters the room's own items (title, level, type); catalogue-wide search stays S5                                                                                                                                 | S5    | IN_PROGRESS                                                            |
| LS-4 | Player: scrubber, transport, speed, loop                         | scrubber violet with a white knob and a played part that follows the position; transport, speeds and "replay line" as before                                                                                                       | S3b   | IN_PROGRESS (built; see log)                                           |
| LS-5 | Transcript with pinyin, translation, active word, autoscroll     | header chips (auto-scroll, the reading, the support language); auto-scroll is a kept preference that really stops the list following; a tapped line is picked ("Tua tới đây", "Nghe lại dòng") and the voice does not move         | S3b   | IN_PROGRESS (built; see log)                                           |
| LS-6 | Listening comprehension                                          | none → items and scoring                                                                                                                                                                                                           | L     | BLOCKED `[CONTENT]`                                                    |
| LS-7 | Bookmark                                                         | none → saved items                                                                                                                                                                                                                 | L     | BLOCKED `[REVIEW]`                                                     |
| LS-8 | Deep actions: dictation, shadow, read line, keep phrase, inspect | one "⋯" button and a sheet (`ui/line-sheet.js`); the five ways run the practices that already existed                                                                                                                              | S3b   | IN_PROGRESS (built; see log)                                           |
| DC-1 | Line 2 of 5, clip range, replay                                  | its own screen: segmented progress, the clip with its range and a bar of where the voice is, replay                                                                                                                                | S3b   | IN_PROGRESS (built; see log)                                           |
| DC-2 | Hint level 1-3, "5 / 11 ký tự"                                   | three levels, leading units, never the whole line (held by a gate); typed-earned units also shown                                                                                                                                  | S3b   | IN_PROGRESS (built; see log)                                           |
| DC-3 | Pinyin per revealed character                                    | `pinyin_alignment.py` cuts the reviewed reading into one syllable per character; served as `pinyin_chars_by_segment`; a line that does not agree draws none                                                                        | S3b   | IN_PROGRESS (built; see log)                                           |
| DC-4 | Result: score, count, wrong / missing / extra                    | `capabilities/dictation-result.js` maps the evaluator to `DictationResult`; a substitution is one wrong place; the count under the ring is the count the score is made of                                                          | S3b   | IN_PROGRESS (built; see log)                                           |
| DC-5 | "Đã dùng gợi ý — không tính vào chuỗi"                           | `used_hint` + hint level stored with the attempt (D-068); no score effect                                                                                                                                                          | L     | BLOCKED (migration chain awaiting authorization + architecture review) |
| DC-6 | Keep a word from the result                                      | "Lưu <term>": the lesson's own vocabulary term found in the line, else the whole line, into device memory                                                                                                                          | S3b   | IN_PROGRESS (built; see log)                                           |

### Speaking — `PronunciationResult` · `speaking_attempts` (no raw audio, D-066 rule 7) · `test_speech_pronunciation`, `test_speaking_evaluator`, `test_m3_pronunciation_contract.mjs`

| ID    | Canonical UI                                    | Have → Need                                                                                                                                                                                                  | Slice | Status                                                                            |
| ----- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | --------------------------------------------------------------------------------- |
| SP-1  | Six practice types, "2/5 câu"                   | `/api/speaking/library`: Speaking catalogue (empty, `[CONTENT]`) + Listening lessons with `shadowing`; chips only for types with items (S1)                                                                  | L     | IN_PROGRESS (built 2026-09-23, `feature/speaking`; catalogue content `[CONTENT]`) |
| SP-2  | "Ghi âm của tôi" library                        | no durable audio by policy → not drawn (S12); durable audio needs its own review                                                                                                                             | L     | BLOCKED `[REVIEW]`                                                                |
| SP-3  | Clip, sentence, waveform, mic controls          | built: model clip (line-bounded), line + reading + meaning, live mic level, 3 round controls; the model's waveform is measured from its audio (same-origin `/api/speaking/model-audio`), idle bars flat (S2) | L     | IN_PROGRESS (built)                                                               |
| SP-4  | Transcribe                                      | `/api/speech/transcribe` (free talk); Groq ASR on the sandbox, real E2E 2026-09-23                                                                                                                           | L     | IN_PROGRESS (built; production credentials `[PROVIDER]`)                          |
| SP-5  | Score panel: overall, accuracy, fluency, passed | provider seam + Azure adapter (words, phonemes, syllables, offsets) → `PronunciationResult`; passed = provider flag (D-084); 0 with no attempt; silence is 'not heard', never a score                        | L     | IN_PROGRESS (built; Azure E2E real 2026-09-23)                                    |
| SP-6  | Timing note                                     | learner speech span (provider word offsets) vs the model line's span                                                                                                                                         | L     | IN_PROGRESS (built)                                                               |
| SP-7  | Per-word note in words                          | provider's error type + weakest phoneme/syllable; no tone sentence without a tone measurement (S3)                                                                                                           | L     | IN_PROGRESS (built)                                                               |
| SP-8  | Tone curve, target and actual                   | target from the lesson reading; actual = the take's pitch measured from its audio (YIN), no written verdict (D-076); a tone _score_ needs a tone provider (S3)                                               | L     | IN_PROGRESS (contour built; tone score `[PROVIDER]`)                              |
| SP-9  | Compare, hear your take                         | built: model line, then the take (this tab's copy only); hear one word from the take by its offsets                                                                                                          | L     | IN_PROGRESS (built)                                                               |
| SP-10 | Free talk: topic, what you said, result (04)    | built: ASR + unscripted Azure (pronunciation, fluency) + coaching fixes and `say_again` (S15); grammar/vocabulary 0, no overall, no 'last time' (D-076); phrases, translation, level absent (S10)            | L     | IN_PROGRESS (built; real E2E)                                                     |
| SP-11 | Recording state                                 | built: pill + timer, live level, stop, cancel (✕ / Esc), auto-stop at 60 s                                                                                                                                   | L     | IN_PROGRESS (built)                                                               |
| SP-12 | Compare with the model (06)                     | built: measured waveforms and (zh) pitch contours of model and take, flagged-word bands, attempts list (session; optional 5 per line on device, D-076), interleave                                           | L     | IN_PROGRESS (built)                                                               |
| SP-13 | Lesson summary (05)                             | built: lines with best measured take, 'practise again' = lines with flags (D-076), missed characters with reading and count; no SRS (deferred)                                                               | L     | IN_PROGRESS (built)                                                               |
| SP-14 | Shadowing (07)                                  | built: 3-2-1, model and microphone together, auto stop at model end + 0.8 s, speed 0.75/0.85/1 kept per lesson, lag from the first word's offset; speed and again restart a take                             | L     | IN_PROGRESS (built)                                                               |
| SP-15 | States (09 A-C)                                 | built: microphone blocked (listen-only), not heard (twice → skip), offline (take kept in the tab, graded when back online)                                                                                   | L     | IN_PROGRESS (built)                                                               |

### Writing — `WritingReview`, `RevisionCompare`, draft · `essays`, `essay_revisions`, account drafts · `test_writing_evaluation`, `test_writing_review_completeness`, `test_writing_review_reuse`, `test_writing_revision_contract`, `test_writing_evaluator_contract`, `test_work_api`, `test_orena_writing_review.mjs`, `test_orena_writing_workspace.mjs`

| ID    | Canonical UI                                                              | Have → Need                                                            | Slice | Status              |
| ----- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ----- | ------------------- |
| WR-1  | Entry: continue draft, "lưu 6 phút trước"                                 | account drafts (sandbox) and device → `updated_at`                     | L     | BLOCKED `[REVIEW]`  |
| WR-2  | "Theo gợi ý": prompt list by kind, level, target words                    | AI task generation only → curated prompt library                       | L     | BLOCKED `[CONTENT]` |
| WR-3  | Four modes                                                                | free, own prompt, `practice_context` exist → wire                      | L     | IN_PROGRESS         |
| WR-4  | Workspace: autosave, word count, target                                   | limits, count, `saveDraft` → none                                      | S2    | IN_PROGRESS         |
| WR-5  | Review: summary, strengths, three issues, rule, related grammar, ask more | `summary_vi`, `strengths_vi`, `errors[]`, `grammar_links` → serializer | S2    | IN_PROGRESS (built) |
| WR-6  | Example sentence per issue                                                | no such field → add to the evaluator contract, versioned               | S2    | IN_PROGRESS (built) |
| WR-7  | Issue kind: register, grammar, punctuation, vocabulary, naturalness       | categories are rubric keys → extend the taxonomy, EN and ZH together   | S2    | IN_PROGRESS (built) |
| WR-8  | Four dimensions, 0-100                                                    | five rubric keys → serialize the four drawn; keep `task_achievement`   | S2    | IN_PROGRESS (built) |
| WR-9  | "Lưu nhận xét"                                                            | every review is stored as an essay → none                              | S2    | IN_PROGRESS (built) |
| WR-10 | "Lưu khái niệm"                                                           | no saved concept from a review → saved concept                         | L     | BLOCKED `[REVIEW]`  |
| WR-11 | Apply a fix                                                               | client, uses `anchored` → none                                         | S2    | IN_PROGRESS (built) |
| WR-12 | Revision: v1 and v2, fixed / remaining / new, headline                    | `revision_delta` → titles, details and headline from the data          | S2    | IN_PROGRESS (built) |
| WR-13 | Dimension change "72 → 88"                                                | delta is a difference → return `from` and `to`                         | S2    | IN_PROGRESS (built) |
| WR-14 | Done, edit again                                                          | client → none                                                          | S2    | IN_PROGRESS (built) |

### Vocabulary — `VocabularyCollection`, `VocabularyCard`, `WordDetail`, `ContextClip` · `vocabulary_collections`, `vocabulary_entries`, memberships, `saved_words` · `test_vocabulary_library*`, `test_vocabulary_cards`, `test_chinese_stroke_order`, `test_orena_vocabulary_*.mjs`

| ID    | Canonical UI                                                              | Have → Need                                                                                                                | Slice | Status              |
| ----- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------- |
| VC-1  | Collections with language, size, percent                                  | `vocabularyLibraryCollections` → shared card                                                                               | L     | IN_PROGRESS         |
| VC-2  | Real packs                                                                | catalog gated until a pack is published → supply                                                                           | L     | BLOCKED `[CONTENT]` |
| VC-3  | Search words or collections                                               | inside one collection only → S5                                                                                            | S5    | IN_PROGRESS         |
| VC-4  | Card front and back, mastery 0-3                                          | entries, `review_stage` → define mastery mapping once                                                                      | L     | IN_PROGRESS         |
| VC-5  | Deep card: senses, collocations, contrast, mistake, mental model, related | free-text fields → structured entry or on-demand explain                                                                   | L     | IN_PROGRESS         |
| VC-6  | "Lấy từ đâu"                                                              | device provenance → durable source link                                                                                    | L     | BLOCKED `[REVIEW]`  |
| VC-7  | "Câu của bạn"                                                             | essays not indexed by word → read model (as QS-7)                                                                          | L     | IN_PROGRESS         |
| VC-8  | Han strokes: radical, components, order, animation                        | offline stroke pack → check the pack for decomposition                                                                     | L     | IN_PROGRESS         |
| VC-9  | Trace along, free write                                                   | no canvas → client capability                                                                                              | L     | IN_PROGRESS         |
| VC-10 | Context clips for a word                                                  | no word-to-clip index → inverted index over listening transcripts                                                          | L     | BLOCKED `[REVIEW]`  |
| VC-11 | Review: three grades with intervals, 3 / 24                               | `again` / `got_it` → three-grade scheduler, interval preview, server-chosen queue; map old states, add tests, keep history | L     | BLOCKED `[REVIEW]`  |
| VC-12 | Tier, 87/150, "chưa thuộc", show all                                      | progress and filters exist; tier does not → tier definition                                                                | L     | BLOCKED `[DEF]`     |
| VC-13 | Han or Latin script                                                       | `orthography` → none                                                                                                       | L     | IN_PROGRESS         |

### Progress — `ProgressOverview`, `ProgressTrends` · LearnerSummary, `saved_words`, `reading_attempts`, `essays` · `test_learner_summary`, `test_orena_growth_summary.mjs`, `test_writing_analytics`

Every value below renders `0` (a chart, its zero state) until measured.

| ID    | Canonical UI                                  | Have → Need                                                                                         | Slice | Status                     |
| ----- | --------------------------------------------- | --------------------------------------------------------------------------------------------------- | ----- | -------------------------- |
| PG-1  | Streak                                        | none → definition and measurement                                                                   | L     | BLOCKED `[DEF]`            |
| PG-2  | Study time and per-skill time                 | no duration is recorded → official rule (time of completed work, never app-open time) and telemetry | L     | BLOCKED `[DEF]` `[REVIEW]` |
| PG-3  | Words mastered                                | `review_stage` → one threshold                                                                      | L     | IN_PROGRESS                |
| PG-4  | Just learned, with samples                    | `saved_words.added_at` → none                                                                       | L     | IN_PROGRESS                |
| PG-5  | Reviewing, due, done today                    | due from `next_review_at`; no event → review events                                                 | L     | BLOCKED `[REVIEW]`         |
| PG-6  | Comprehension 9/11 and sequence               | `reading_attempts` for generated passages → chapter quizzes (S4)                                    | L     | IN_PROGRESS                |
| PG-7  | Recall accuracy, cards, got / unsure / forgot | cumulative counters only → review event table; needs VC-11                                          | L     | BLOCKED `[REVIEW]`         |
| PG-8  | Recent evidence per skill                     | LearnerSummary latest observations → `EvidenceItem` projection                                      | L     | IN_PROGRESS                |
| PG-9  | Rank panel                                    | none → SH-4                                                                                         | L     | BLOCKED `[DEF]`            |
| PG-10 | 18-week heatmap                               | none → per-day activity                                                                             | L     | BLOCKED `[DEF]` `[REVIEW]` |
| PG-11 | Next action                                   | due words, then `crossSkillCue` (coaching order) shown; listening cue opens no lesson; no duration  | L     | IN_PROGRESS                |
| PG-12 | Improving over four weeks                     | only comparable measures may show a trend → series where comparable, `0` otherwise                  | L     | BLOCKED `[DEF]`            |
| PG-13 | Recurring errors                              | `error-memory` covers Writing → cross-domain read model                                             | L     | IN_PROGRESS                |
| PG-14 | "Dựa trên gì" counts                          | derivable → after PG-7                                                                              | L     | IN_PROGRESS                |

## Progress log

**S1 Quick Sheet** (2026-09-21, `codex/work`). Built: `word_detail.py` and two endpoints
(QS-1..6, 11); `context_meaning`, `core_idea`, `mental_model`, `contrast`,
`common_mistake`, `structure` in the explanation schema; `ui/quick-sheet.js` and
`quick-sheet.css` (layer one, ask, deeper, sentence and its parts) called from
Reading and the Listening transcript through `ui/lexical.js`; the old lookup panel,
selection toolbar and reader panel styles removed. Checked in a browser on the
sandbox (:8011), vi interface, English text: docked in the reader, popover in
Listening, phone sheet with scrim. Local: pytest 1148 passed / 118 skipped, all CI
`.mjs` gates pass except `test_m3_pronunciation_contract.mjs`, which has failed
since D-065 removed the score from the report (it is a Speaking-slice item).

Not READY yet - what is left before S1 can be called READY:

- Chinese in a browser (hanzi, pinyin, the grammar-word label) and the zh interface.
- Phone: the ask, deeper and sentence views, not only layer one.
- Save from the sheet end to end with a reload, and the provider-down and retry states.
- Speaking still mounts the layer (`ui/speaking.js`): check it.
- The explanation and summary come back in English when the support language is
  Vietnamese on the sandbox's provider; the request names Vietnamese, so this is the
  provider's output (handoff: local model quality), to be checked with the live one.
- `QS-7` `sources` / `learnerSentences` are empty until their read models exist;
  `QS-8` "Lưu giải thích" keeps its place, disabled and saying so.
- Writing feedback, Vocabulary and Practice still open the older Understanding
  surface (`ui/understanding.js`); it is retired when S2 and the Vocabulary work
  move onto the sheet.
- Found on the way, fixed: the Listening transcript's words could not be tapped
  (a stale `.media-encounter` root); `.media-encounter` selectors remain as dead
  CSS to remove in S3.

**S3a Library** (2026-09-21, `f75991f`). Built: the baseline's library for Reading and
Listening as one surface (`ui/library-browse.js`): a bar with the room's name, a search and
the import action; one row of single-choice type chips offered only for types some item
really has; a grid of ContentCards with the length on the cover, a progress bar and "time
left" from the place the learner reached (device memory), a video badge and a provenance
badge (said once, not repeated in the line), and an authored "3 min" shown in the interface
language. Backend: `content_type` for listening lessons, derived and tested
(`test_every_lesson_carries_a_type_the_baseline_names_or_none`). The D-060 facet layout and its
CSS are deleted; a new gate `scripts/test_orena_library.mjs` (in CI) holds the contract and the
copy for every catalogue type in en, zh and vi. Checked in a browser on the sandbox (vi):
desktop Reading and Listening, phone Listening with touch (chip tap filters, no horizontal
overflow, chips scroll). Local: pytest 1160 passed / 118 skipped; every CI `.mjs` gate passes
except `test_m3_pronunciation_contract.mjs`.

Not READY yet - S3 as a whole:

- The Listening workspace has the baseline's structure (player, scrubber, transport, speeds,
  comprehension button, bookmark, transcript with VI) but not its details: the transcript
  header is the shared learning toolbar's row of icon buttons where the baseline draws
  "Tự cuộn", PINYIN and VI chips and puts the deep actions (dictation, shadow, read the
  line, keep, inspect) behind one "⋯"; the scrubber is amber where the baseline's is violet
  with a white knob. `learning-toolbar.js` is shared with Reading, so it changes in one pass.
- The catalogue's lesson `en-travel-rainy-day-taxi` is a single 71 s segment (one very long
  transcript line): a content-segmentation gap `[CONTENT]`, not code.
- Dictation is a panel beside the player; the baseline draws its own screen (segmented
  progress, the player inside a centred card with the hint-level pill, hint shape with pinyin,
  a result column with the score ring, marks and actions). The evaluator, hint levels, score,
  wrong/missing/extra and save already exist and are reused. DC-3 (pinyin per character) and
  DC-5 (assisted flag kept) are still open.
- Search (S5) and the catalogue-wide result page are untouched; the Library page
  (`#/content`, all kinds) uses the same component with type chips only.
- Browser checks of the zh interface and of imported items in the library.

**S3b Listening workspace and Dictation** (2026-09-21, `8bdb649`, `3c70516`, `3df3aee`). Built from
the pinned frames (Orena Listening 02, 03, 04), not from the previous implementation:

- Workspace: header chips (Tự cuộn, the reading, the support language) and one "⋯"; a tapped
  line is picked and offers "Tua tới đây" and "Nghe lại dòng", the voice stays where it is; the
  deep ways (dictation, shadow, read the line, keep, look closer) are a sheet over the workspace
  (popover on a desk, bottom sheet on a phone, closes on navigation); an audio lesson has a poster;
  the identity line is level · type · length; the scrubber is violet with a white knob. Word-class
  colours have no switch on the baseline, so they are off and their legend is gone.
- Dictation: its own screen - segmented progress, the clip, the pills (hear again, speed, hint
  level), the shape of the line with a reading under each character, the field, and a result
  column (ring, what was typed with each wrong, missing and extra place marked and tappable, the
  right line with the missed characters lit, the reading and the meaning, next line / try again /
  replay / keep). The comparison, score, hint module and evidence save are the ones that existed;
  `capabilities/dictation-result.js` only puts them in the baseline's shapes. The streak pill
  shows 0 (not measured). A used hint says "Đã dùng gợi ý." and nothing more.
- Backend/data: `pinyin_alignment.py` and `pinyin_chars_by_segment` in the lesson payloads;
  the aligner is verifiable (pypinyin only says where a syllable ends), left a line unaligned
  rather than wrong, and caught two real typos in the reviewed readings (`zhǎodào`, `Bǎikē`),
  corrected in the catalogue. Every Chinese line the catalogue ships aligns (a test holds it).
- Chinese and localization: keys are in parity across en, zh and vi in both copy packs; the
  library, the workspace, the deep sheet, Dictation, the Quick Sheet (word, deeper, typed
  question) and the Writing review with its finding sheet were run in a browser in a Chinese
  interface with Chinese text and real answers (Gemini): second person, Chinese throughout.
- Checked in a browser on the sandbox with real touch: Dictation and the workspace on a phone (no
  horizontal overflow, the deep sheet is a bottom sheet with a scrim, the result follows the task),
  the library on a phone (two columns, the item in progress leads). Local: pytest 1171 passed /
  118 skipped; every CI `.mjs` gate passes except `test_m3_pronunciation_contract.mjs`; new gates
  `test_orena_library.mjs`, `test_orena_dictation_screen.mjs`, `test_orena_listening_workspace.mjs`.
- Deleted: the old Dictation panel's CSS and code (`revealAnswer`, `.dictate-*`, `.hint-line`,
  `data-mode='dictation'`), the audio identity block, the D-060 library layout.

Decisions the human closed (D-068, 2026-09-21):

- **DC-5.** Approved: the used-hint state is stored with the attempt, and no scoring effect is
  inferred without a scoring rule. Storing it means two columns on `listening_progress` (the last
  attempt's `used_hint` and hint level), a schema change for learner-owned data: it is authored as a
  migration after the chain still awaiting human authorization (`20260916_0008` and
  `20260916_0009`, sandbox at `20260912_0007`) and needs a recorded independent architecture review
  before it is applied. Until then nothing about it is built and the screen says nothing about
  hints used.
- **The lesson `en-travel-rainy-day-taxi` is removed** from the catalogue (six lessons remain); its
  source `commons-taxi-dialogue-1` goes with it.
- **Reveal in Dictation.** The baseline draws no "show the answer", and a hint never shows the whole
  line, so the screen has none; the recorded `revealed` evidence path is now unreachable from the UI.

Not READY yet - what is left of S3:

- LS-6 (comprehension) and LS-7 (bookmark as a saved item) stay `BLOCKED` as before; the bookmark
  is device memory.
- The workspace on a phone stacks the poster, the transport and the transcript; the baseline's
  phone puts a top bar (back, the reading and support chips, bookmark) over a longer transcript with
  the transport at the bottom. Functional and touch-checked, not yet the same composition.
- Word-class colouring code (`closeLook`, annotation of the current line) has no UI; delete it.
- The two `verify_writing_*_browser.mjs` scripts still wait for the deleted `.review-headline`.
- The library's chips show only types that exist; the baseline draws the full fixed set.

**S2 Writing review and revision** (2026-09-21). Built: `writing_contract.py` and two
endpoints (WR-5..9, 11..14); `example` per finding and the English `register`
category (evaluator contract `writing-evaluation-v2.5`); one table maps every
category of both languages to the baseline's five kinds; `ui/writing-feedback.js` and
`writing-feedback.css` (overview, findings, dimensions, the finding sheet with apply,
the version comparison) replace the old report renderer, the revision workbench and
the locate helper. Checked in a browser on the sandbox with the real provider
(vi interface, English text, desktop): review, opening a finding, applying it (draft
changed, count fell), a second version and its comparison. Two root causes found and
fixed on the way: the comparison was handed an unparsed earlier review and saw none of
its findings; and it matched findings by identical wording, so it called a reworded
finding fixed and new at once - it now asks the words. Local: pytest and every CI
`.mjs` gate pass except `test_m3_pronunciation_contract.mjs`.

Not READY yet:

- Chinese (zh text, zh interface) and the phone in a browser; the provider-down state.
- WR-1..4 (entry with four modes, prompt library, workspace top bar) and WR-10 (save a
  concept) are untouched; the room's frame is still the earlier composition.
- Dead styles from the old review (`.review-*` overview/issue/dimension rules,
  `.correction*`) and now-unused copy keys (`reviewFocus`, `reviewDeeper`,
  `reviewLocate`, ...) remain to be removed; they share names with the Vocabulary review
  session's classes, so they need a careful pass.
- `ui/understanding.js` is still used by comprehension, conversation, the encounter,
  voice response and grammar; it goes when those move onto the Quick Sheet.
- The comparison shows the two drafts side by side only when the frame is 820px or
  wider; in the room's result column it shows the banner and the changes, as the
  baseline's phone does.

## Old tracker (GAP-001..052) mapped

Carried into a row above: GAP-001 SH-5 PG-1 · 002/003/008 PG-2 · 004 SH-2 SH-6 ·
006 HM-1 · 011/026 SH-7 · 012 HM-6 RD-5 · 013 SH-1 · 014 PG-5 · 019 superseded
by VC-11 (three grades) · 020 VC-12 · 021 SP-5..8 · 022/027/029 RD-1 RD-2 LS-1 ·
025 LS-6 · 028 (per-word only) DC-3 · 032/034 RD-9 RD-13 · 035 RD-7 RD-15 · 036/039
RD-12 · 040 RD-10 · 043 VC-11 · 044 RD-1 · 045 RD-11 · 047 VC-12 · 048 SH-4 PG-9 ·
049 PG-10 · 051 DC-3 · 052 HM-2.

Not drawn by the baseline, so no longer tracked (git history keeps them): GAP-005,
007, 009, 010, 015, 016, 017, 018, 023, 024, 028 (whole-text pinyin), 030, 031,
033, 037, 038, 041, 042, 046, 050. Profile, My Content, Admin, Onboarding, states,
Modal/Drawer and tablet have no canonical design; their current implementation
stays until the human supplies one (D-066).

**Bug pass on S1/S2** (2026-09-21, commits `fb9a9ec`, `3651ed0`). Six reported defects,
each with its root cause:

- The ask-more input looked dead: a repaint on every state change rebuilt the sheet and
  erased the question being typed. The draft and its focus now survive a repaint, and the
  newest answer scrolls into view. Checked: a 52 s repaint kept text and focus.
- A sheet outlived the screen it was opened from. Every sheet (word, sentence, finding) now
  closes on a route change. Checked with `history.back()` and a hash change, for the word
  sheet and the Writing finding sheet.
- Feedback spoke about "the learner". `VOICE_POLICY` in the writing evaluator and the tutor
  prompts sets second person (bạn / you / 你); the evaluator contract is `writing-evaluation-v2.6`,
  so stored reviews in the old voice are retired. The answer language is now named in the last
  line of the tutor prompt, naming `judgement_reason` and `follow_ups`, which a model otherwise
  leaves in the text's language. Checked live in vi: gloss, verdict, follow-ups and a typed
  question all in Vietnamese; zh word (`终于`) gives pinyin, no IPA, Vietnamese explanations.
- Rails could not be swiped on a phone: `touch-action: pan-y` blocked horizontal panning.
  Checked with a real touch swipe (touch-enabled mobile context, CDP touch events): the
  For-you rail moved from 0 to 217 px. Not a resized mouse viewport.
- The reader's back link went to a route that answered `{"detail":"Not Found"}`; it now
  returns to the book, or to Practice when there is none.
- The For-you cards were unequal (a legacy `align-items:start` in `rooms.css`): now one height (183 px).

Also: the first-layer gloss is no longer replaced when the full explanation loads (for Chinese
the full answer can be a sentence translation). Deleted the old Writing review layout's CSS
(`.review-*`, `.correction*`, ~250 lines across four files), including a legacy
`.review-bar` box that also clipped the vocabulary session's header. Phone sheet checked with
touch (bottom sheet, scrim, no horizontal overflow, closes on navigation).

Still open from S1/S2: the zh _interface_ on the sheets and the phone views of ask/deeper
for zh; provider-down states are covered by unit tests, not a browser pass; the two
`verify_*_browser.mjs` scripts (cited in docs) wait for the deleted `.review-headline` and
must be rewritten for the new markup; unused copy keys (`reviewFocus`, `reviewDeeper`,
`reviewLocate`, ...); WR-1..4, WR-10, QS-7, QS-8; `ui/understanding.js` stays for its other
callers. The provider's 15-50 s latency for the full explanation and about 40 s for a review
is provider speed, shown by the loading states, not fixed here.

## Writing workspace, measured against "Writing workspace" and "Writing review" (D-067)

Built to the frame: a 76px top bar (back, title, saved, word count, one "Nhận xét" pill), a 920px column
with the prompt card (the intention field lives in it) and the piece as a 24px serif document; a review
makes two panes (994 : 820, radius 20, padding 28/30). Removed because the frame draws nothing for
them - decisions for the human, not guesses:

- **The level control.** Decided (D-068 follow-up): no selector; the review aims at the level the learner
  declared in their profile (`declared_level`), else the level of the text answered, else nothing.
- **Register exploration and the revision history** are kept and now sit behind the top bar's menu (three
  lines), the design's pattern for "everything deeper behind one button".
- **The "Cần một điểm bắt đầu?" starters** are legacy of the old entry and stay below the room until the
  Writing entry frame (ContentCard / SectionRail of prompts) is built.
- The prompt card's second line ("B1 · ≈150 từ · giọng thân mật") and the "/ ≈150 từ" target in the count
  need a task with a level, a length and a tone; the free-writing room has none, so the card is one line
  and the count is the words written.
- Still not the frame: the review pane's own content (overview, "làm tốt", "ba chỗ cần sửa" cards with
  three chips each, "các mặt" bars), the top bar's "Lưu nhận xét" / "Sửa lại" pair, the revision
  compare frame, the error sheet, and the entry.

## Bugs 7-13 (2026-09-21) - what changed and where

| #   | Result                                                                                                                                                                                                           | Where                                                                                         |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 7   | PASS: a replaced or closed sheet is cancelled; only the latest tap is answered; the last tap's own selection no longer reads as a drag; words in any visible line are askable (the line becomes current, paused) | `ui/lexical.js`, `ui/quick-sheet.js`, `ui/encounter.js`, `scripts/test_orena_lookup_race.mjs` |
| 8   | PASS: follow-ups go to a contextual tutor (answer first, never restated, short by default, earlier turns carried)                                                                                                | `media_interaction.answer_learner_question`, `word_detail.py`, `tests/test_word_detail.py`    |
| 9   | PASS: Previous / Next on the Dictation rail, in step with the progress                                                                                                                                           | `ui/dictation-screen.js`, `dictation.css`                                                     |
| 10  | PASS: hear, line, field and check fit 390x844 (check at y 572-622); a long line scrolls in its own pane                                                                                                          | `dictation.css`                                                                               |
| 11  | PASS as built in S3b (ring, count, marks, right line; no invented number); no new deviation found                                                                                                                | `ui/dictation-screen.js`                                                                      |
| 12  | PASS: a tap on a line goes to it and plays it; the half-way picked state is deleted                                                                                                                              | `ui/encounter.js`, `listening.css`                                                            |
| 13  | PASS: the overflow is the menu icon (three lines)                                                                                                                                                                | `ui/encounter.js`, `ui/symbols.js`, `ui/expression.js`                                        |

"Ink + Paper": the Paper theme was retired by D-066; there is one theme, so the check is desktop and phone
in one theme.

## Bugs 14-15 and the design sync (2026-09-22)

| #   | Result                                                                                                                                                                                                                    | Where                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 14  | PASS: a word typed with an extra letter ("breack") is still wrong and the hint never shows it whole - the place where it parts from the target stays masked; the old test that expected the word revealed is re-expressed | `capabilities/dictation-hints.js`, `scripts/test_orena_dictation_hints.mjs` |
| 15  | PASS: on a desk the task is one screen (check button at 979/1080, 720/768, 686/720; with or without a result); the picture takes what the height allows, the line scrolls in its own pane                                 | `dictation.css`, `scripts/test_orena_dictation_screen.mjs`                  |

Design sync: tokens and the contracts checked are unchanged; the rules documents were read for the first time and
are recorded in `docs/design/canonical-ui/SYNC_2026-09-22.md`. From them: the Writing review is a Draft / Review tab
pair on a phone and the revision is three columns with a banner - both built now. Still to build from the templates:
the Writing entry, Home (top bar with search, level and streak, the Continue strip, section rails at 300x170 / 232x132),
Reading (library, book detail, workspace) - each read from the source when it is worked on.

## Writing entry and the ground (2026-09-22)

Built to "Writing entry": `ui/writing-entry.js`, `writing-entry.css`, route `#/writing`. The draft card is drawn only when
the device holds a continuation for Writing; the prompt rail is the texts' own prompts (badge = the text's kind, meta =
its level and length); "search" filters the prompts; "See all" opens the rail into a grid. Not drawn because the
app holds no such data: "saved N minutes ago" on the draft card, a category badge for prompts that have no kind,
a target length. The error sheet is the finding sheet (`issueSheetHtml`), already the frame's: fragment struck,
correction, kind, why, rule well, example, ask / save concept / apply.

## Writing review and revision, second pass (2026-09-22)

Built to "Writing review" and "Writing revision" (desktop and phone): the findings are marked in the draft itself
(`ui/draft-marks.js`), the pane labels are drawn, the top bar's one primary action follows the room (Review / Revise /
Done), and a revision is the banner, the legend, the two versions marked and the changes with the dimension deltas at
their foot. The phone's revision bar is "Revise more" beside "Done".

- **A mark is earned.** The contracts carry the words of a finding (`fragment`; a change's `title`), not where they
  are. A mark is drawn only where the words occur exactly once in the text, the rule apply-fix uses; otherwise the
  finding stays guidance and marks nothing. The revision marks what was fixed and what is still there in the earlier
  version, what is still there and what is new in the later one; it cannot mark the words that replaced a fix
  (`detail` carries the evaluator's suggestion, not the learner's words). Positions in the contract would end both limits.
- **"Lưu nhận xét" (save the review) is not drawn.** A review is already kept with the piece; saving it as something
  else needs a place in learner data that is held for the account architecture (AGENTS.md, holds). Decision needed:
  what "saved" means here (a kept set of rules in My Language?), then it is one button.
- **Where the findings of a revision went.** The revision frame draws no findings, so a version with a version before
  it opens on the comparison and its findings are one menu item away ("Review of this version"), and back. The frame
  gives no button to revise again from the desktop comparison; it is behind the same menu (the phone has it in the bar).
- **The design's Vietnamese sentences are sample text.** The changes list shows the evaluator's own words (the
  fragment, its kind, the correction and reason), not the frame's "Giọng văn đã thân mật".

## Home, built to its frames (2026-09-22)

`ui/home.js` + `home.css` replace `discoverySpread`: the baseline's top bar (the one search, the level, the
streak), the Continue strip, then the rails the frames draw - what is new for you, Reading, Listening,
Speaking, Writing, Vocabulary - and what the learner kept. Every card is a real item; a rail with nothing
in it is not drawn. The old composition (greeting, hero pair, "for you"/"saved" only) and its stylesheet
are deleted (rule 44).

- **The frames' sidebar draws an account card and per-skill levels; the app's rail does not.** The shell is
  already built to `AppShell` (D-066) and the human kept the current logo; the account lives in the profile
  sheet. Per-skill levels have no source (`skillLevels` in `AppShell.json` is unserved). Decision needed
  before the rail grows a card.
- **The streak is still unmeasured (GAP-001).** The chip keeps its place and shows "—", as everywhere else.
- **"For you" is the catalogue's own order (GAP-052).** There is no recommender; the rail alternates
  listening and reading so the phone's first two cards show both, and says nothing about why.
- **The frame's phone tab bar holds Home / Library / Vocab / Progress / Profile**, which the shell already
  draws; Home draws no navigation of its own.
- **Not drawn because nothing supplies them:** a per-card "ĐANG LUYỆN / ĐÃ LƯU" badge (`badge` in
  `ContentCard.json` is unserved), the frame's "còn 4 phút" (a thread records a place, not a remaining time).

## Reading workspace, to its frame (2026-09-22)

"Reading · bilingual + panel" is one screen, and now so is the room: a 4px hairline of the learner's place
across the top, a 72px bar, the text at its 780px measure beside the 440px panel, each scrolling on its own,
and the frame's floating bar under the text. What used to sit under the text - the prepared notes, the
optional check, the response, the rights - is reached from that bar and opens as a sheet (D-068: a function
is not deleted because the mockup omits it; it goes where the design's patterns put it).

- **The frame's bar has six pills; the app draws what exists.** Lưu bài (keep), Nghe (unavailable, as
  before), Kiểm tra hiểu (disabled with no questions, D-068), Viết phản hồi (the response composer, primary),
  the prepared notes when the text has them, and the rights. **"Thảo luận" is not drawn**: there is no
  discussion over a whole text, only the per-selection understanding surface. Decision needed: either a
  thread against a text (learner data, so the account architecture holds it) or the pill leaves the design.
- **"Đọc tiếp sau" is not drawn either.** The frame draws both "Lưu bài" and a primary "Đọc tiếp sau"; the app
  has one bookmark and remembers the place by itself, so a second one would be the same action twice.
- **The sheet is the app's existing dialog, not the design's sheet pattern.** The Quick Sheet's glass is not
  yet a shared primitive; restyling every sheet is its own slice.

## The rail's learner card and per-skill levels (2026-09-22, human decision)

The human asked for both (answer (c) to the five points). Built: the card at the foot of the rail - who this
is, the level they declared and the language they are learning - opening the profile and settings sheet, as
the frames draw it; hidden on a phone, where the Profile tab is that door.

**Per-skill levels are drawn only when the profile carries one** (`profile.skill_levels[skill]`). Nothing
serves that field today (`skillLevels` in `AppShell.json` is unserved), so no level prints. Repeating the one
declared level on all four skills would be a figure nobody measured. **Backend needed:** a per-skill level on
the learner profile, derived from real evidence, before those slots can fill.

## Reviews read back (2026-09-22, D-072.1, no schema)

The Writing room lists the pieces that were reviewed (`GET /api/essays`, this learner and this language,
eight most recent) with the version, the level the evaluator estimated and the date the row states. A row
opens the review stored with that piece (`GET /api/essays/{id}/review`) in a sheet: nothing is copied and
nothing new is written. **The bookmark ("Lưu nhận xét", `essays.review_kept_at`) is approved but not built:**
it waits on the independent architecture review, so the list is every reviewed piece, not a curated set.

## Book detail, measured against the source (2026-09-22, D-067)

Measured `[data-screen-label="Book detail · chapters"]` in `Orena Reading.dc.html` against
`#/book?id=…` at 1920x1080. **Corrected to the frame** (each verified in the running app):
book title 40→38, the chapters heading from a mono `ds-label` to the frame's Nunito 24/800 section
heading, the cover 176→220 wide with radius 14→18, chapter rows padding 12/14→16/20 and radius
13→15, list gap 7→9, chapter title 14→18, chapter number →15, chapter meta →13.5.

Reading Library needed nothing: at 1920 it already measures the frame exactly (bar 84 / padding
0 40, title Nunito 26/800, cover 236x315 radius 16 with the glass ring, grid gap 28, cover-to-text
13, card title Nunito 18/700). The per-skill CSS (`.lib[data-skill='reading']`) is what carries it.

**Not resolved here, because the design and the implementation differ in composition and rules 43-44
make that a decision, not a fix:**

- **The frame draws neither the chip row nor the stat tiles.** The app's hero carries
  `Đọc · EN · 5 chương · 1,200 từ` as chips and four `book-stat` tiles (words saved, reading time,
  average score, audio) that mostly render an honest dash. The frame carries one DM Mono line -
  `B1 · tiểu thuyết · 12 chương · 22 phút còn lại` - and no tiles at all.
- **The frame draws one action.** The app draws a primary plus three disabled icon buttons
  (bookmark, download, more). The disabled-placeholder question is already open for
  "Kiểm tra hiểu"; this is the same question on this screen.
- **The frame puts the saved words in the hero**, under `BẠN ĐÃ LƯU TỪ ĐÂY`, as word pills with a
  `+ 83 từ` overflow. The app has the same data but in a right-hand aside, beside an "About" section
  and a "Similar" note the frame does not draw.
- **The frame has no "chỉ chương chưa đọc" filter.**
- **A chapter row is one line in the frame** (number · title · `18 phút`), 56px tall. The app stacks
  the meta under the title, so the row is ~90px, and the meta is a **word count**, not minutes -
  minutes would need a per-chapter reading-time estimate the catalogue does not carry.
- **Cover proportion.** The frame's cover is 220x300; the app's artwork keeps its own ratio and
  renders 220x322.
- **Colour.** The frame's chapter text is `rgba(255,255,255,0.72)` and its number/meta
  `rgba(255,255,255,0.55)`; the app reads `--text-secondary` / `--text-muted`. Components may only
  read semantic tokens (`AGENTS.md`, Theme), so if these must match exactly it is a token question
  for `theme.css`, not a component override.

## Reading library, re-checked against the source (2026-09-22, D-067)

Re-read `Orena Reading.dc.html` from the design project itself. It is **byte-identical to the
pinned cache** (94 122 bytes, sha256 `fc7f7640…`, the hash `PINS.tsv` records), so the cache was
not stale - the earlier "Reading library matches its frame" claim was simply too broad: it covered
the bar, the grid and the card box, not the whole composition.

**Corrected to the frame:** the cover badge ("ĐÃ NHẬP", "TẠO RIÊNG") was 10.5px / 0.1em tracking in
plain white with no ring; the frame draws 11px / 0.08em in the accent ink `#D5C0FF` with the glass
ring and 6/12 padding. The badge now reads from `--accent-ink` and `--glass-ring`, so no literal
colour entered a component. Verified in the running app after a cache-busted stylesheet reload.

Also confirmed, against an earlier misreading of mine: `TẠO RIÊNG` / `ĐÃ NHẬP` are **cover badges on
cards**, not section headings - the frame has one grid of twelve. The app's per-card badge is the
right shape.

**Still different, and each needs a decision or a backend fact rather than a CSS change:**

- **Card meta is often absent.** The frame prints `B1 · tiểu thuyết · 22 phút` on every card -
  level, type, minutes. The app prints that only where the catalogue carries it: an imported book
  shows nothing, `Kafka pa stranden` shows `sách` alone. **Backend needed:** a CEFR level and a
  reading-time estimate per catalogue item; the app refuses to invent either.
- **Four filter chips where the frame draws eleven.** The frame offers Tất cả, Sách, Chương trích,
  Bài báo, Tin tức, Tiểu luận, Truyện, Hội thoại, Trích dẫn, Tạo riêng, Đã nhập. The app offers a
  chip only for a type some item in the room actually has (`library-browse.js`), so today it shows
  four. Offering a filter that can only ever return nothing is the opposite trade; **which rule
  wins is the human's call**, and nothing here changes until it is made.

## Reading workspace, measured against the source (2026-09-22, D-067)

The human reported the layout is wrong when a source is opened to read. Measured
`[data-screen-label="Reading · bilingual + panel"]` against `#/encounter?…&intent=reading` at
1920x1080.

**The skeleton was already the frame's**: the 4px hairline across the top, the 72px bar with
`0 40px` padding, the 780 reading measure, the 440 aside with its Từ / Ngữ pháp / Ghi chú tabs, and
the floating action bar (radius 999, 12 padding, 10 gap, six 48px pills, the last one primary and
ringless).

**Corrected:** the app drew a **second progress bar** in a band across the whole window
(`.reader-foot`, 1905 wide, with its own `.reader-progress`). The source draws the place **once as a
bar** - the top hairline - and repeats the figure only as text (`34% · còn 9 phút`, DM Mono 13) at
the **foot of the 780 column**, beside the way on to the next chapter. The second bar is deleted and
the row now sits exactly on the column (measured x=343 w=780, identical to `.reader-page`). A code
comment claiming the frame "draws the same figure twice" as two rails is corrected in place.

**Still different, and each is a decision rather than a value:**

- **The bar's controls.** The frame draws a "Song ngữ" pill (121x40) and one 40x40 icon button
  (radius 13, ringed). The app draws a back arrow (32), the support-language chip (`VI`, 35x32) and
  `Aa` (34x34, radius 10). Same purpose, different controls.
- **The six actions are named differently.** Frame: Lưu bài · Nghe · Kiểm tra hiểu · Thảo luận ·
  Viết phản hồi · **Đọc tiếp sau** (primary). App: Giữ lại để sau · Nghe · Điều bạn thu được ·
  **Câu trả lời của bạn** (primary) · Những từ đáng chú ý · Nguồn & bản quyền. The count, the sizes
  and the shape match; which six, and which one is primary, is product wording.
- **Spacing:** bar gap 20 in the frame against 14; aside padding 26 / gap 20 against 22 / 16. Left
  alone in this pass because the aside's contents are not yet the frame's, so matching its padding
  alone would not make it the frame.

## Reading workspace, three faults the human found (2026-09-22)

- **The end-of-chapter sheet is deleted.** `chapter-complete` (a D-059 composition) rendered the
  moment any book chapter opened - not when one was finished - and took about half the desktop
  viewport, more on a phone. The source draws no such sheet, so it is deleted with its markup, its
  repaint and its CSS (rule 44), not restyled. What it reported lives on where the source puts it:
  the words kept here in the side panel, the way on in the foot row.
- **"Nguồn & bản quyền" has left the action bar.** The source draws no such action (human,
  2026-09-22). Attribution itself is not a design choice - a published text owes its credit - so the
  block now sits quietly under the text instead of behind a bar action. **Open for the human:** the
  frame draws no attribution anywhere; where it should live is still the call recorded in the
  fidelity notes.
- **The way out of a book was a loop.** The book page's back was `history.back()` while the reader's
  back _navigates_ to `#/book`, so back from the reader pushed the book page, and back from there
  returned to the reader: a learner could not leave the book. The book page's back is now a link to
  the reading library, so library → book → reader unwinds one step at a time. Verified:
  `#/encounter…` → `#/book?id=…` → `#/practice?intent=reading`.

## Reading workspace, matched to the frame's bar and actions (2026-09-22)

The human asked for the layout, the button count, their wording and their places to match the source
exactly. Measured `[data-screen-label="Reading · bilingual + panel"]` and built to those numbers.

**The six actions, in the source's order, with its icons and sizes** - each width verified in the
running app against the frame: Lưu bài 120 (`bookmark-simple`) · Nghe 107 (`speaker-high`) ·
Kiểm tra hiểu 162 (`check-square-offset`) · Thảo luận 139/140 (`chats-circle`) · Viết phản hồi 163
(`pen-nib`) · **Đọc tiếp sau 166, the primary** (`bookmark-simple`, the violet gradient, Nunito 800).
All 48 tall, Nunito Sans 16/400 on the ringed glass. The prepared-notes action left the bar: the
frame draws no seventh pill and the side panel's third tab is where notes belong.

**The bar**: the way back and the title are one link with an arrow (Nunito Sans 16), the place line
is 13px sentence case rather than a 10.5px uppercase tag, and the right cluster is the "Song ngữ"
pill (40 tall, radius 999, translate glyph) with the 40x40 radius-13 type-size button. Bar gap 20.

**"Thảo luận" is now real.** It opens the thread this lane built for D-072.2 and talks to
`/api/texts/discussion`: the learner's questions and the tutor's answers are kept with the account,
one `request_id` per submission so a retry cannot double-answer, and when no provider can answer the
question stays in the box with a retry - no invented reply. Verified end to end in the sandbox
against Gemini.

**Two inferences, recorded for the human rather than decided:**

- The frame gives "Lưu bài" and "Đọc tiếp sau" the same bookmark glyph and no behaviour. Built as:
  "Lưu bài" toggles the bookmark; "Đọc tiếp sau" keeps it _and leaves the text_, which is what its
  words say. If they are meant to be one action, the bar drops to five.
- "Nghe" stays unavailable with its "coming" title: a text has no audio to read aloud yet. The frame
  draws it enabled. Same open question as the disabled "Kiểm tra hiểu".

## Progress: the bar, the two screens, and what no backend can fill (2026-09-22)

Measured against the re-pinned `Orena-Progress.dc.html`, all four frames: `Progress overview`,
`Progress overview mobile`, `Progress trends`, `Progress trends mobile`.

**The bar.** Progress draws no search. Its bar is the destination name (26/800), the window its
numbers cover in mono 13 - "bảy ngày gần đây" on Tổng quan, "so với 4 tuần trước" on Xu hướng - and
the streak chip, which the overview bar carries and the trends bar does not. The search form the app
used to draw there is deleted (rule 44), and with it the screen fits one viewport at 1920x1080:
nothing on Tổng quan or Xu hướng needs scrolling any more.

**The two tabs.** The frame draws the tab pair only on its _trends_ frames - `Tổng quan` inactive,
`Xu hướng` solid - and the overview frames draw none. Taken literally that leaves Xu hướng
unreachable, so the pair is drawn on both screens: it is one component with two states, and the
inactive `Tổng quan` pill the trends frame draws is that component's other half. **Open for the
human:** if the overview really is meant to carry no tabs, the way into Xu hướng needs to be drawn
somewhere.

**Xu hướng has no data at all.** Every figure on it renders 0 or a dash in its canonical component
(D-066 rule 4), because nothing serves it:

- **GAP-P1 · no trend model.** The frame draws each measure as the move it made ("72 → 88") against
  four weeks ago. Orena stores no per-measure history, so neither end of that move exists. The rows
  keep their place and say nothing. The frame draws no bar on these rows, so the app draws none
  either - and no trend arrow, which would be a direction nobody measured.
- **GAP-P2 · no repeated-error model.** "Lỗi lặp lại" lists a mistake, how many times it came back,
  why, and where. Nothing counts a mistake across sessions, so the block carries its empty line.
- **GAP-P3 · no comprehension or recall figures.** Row two's third and fourth panels - "Kiểm tra
  hiểu" and "Nhớ lại" - have no source; they render 0 and say what they would count.
- **GAP-P4 · no time on task.** "Thời gian học" and every per-skill row measure time. Orena records
  none, so those tracks are the unavailable hatch and every value is a dash.
- **GAP-P5 · the tier-10 threshold.** The ladder's own tiles state every threshold except tier 10,
  where the frame draws "BẬC HIỆN TẠI" over the number. That tile shows a dash rather than a guess.
  The number is the product's to state.

**The phone.** The desktop bar is not drawn below 600px, so the page draws the frame's own head
there instead - the name at 24/800 (22 on Xu hướng), the window beside it, and the two tabs as a
full-width row of 38 at radius 13 - and both stat rows stay rows, three tiles then four, at the
frame's 8px gap and 11/10 padding. Without that head the phone could reach Tổng quan and never
Xu hướng.

## Hồ sơ, measured against "Orena Hạn mức sử dụng" (2026-09-22)

Read at the source with `DesignSync` - the screen is **not** in
`docs/design/canonical-ui/`, so it has no pin and must be read there each time.

**What now matches the frame.** Hồ sơ is a destination in the rail rather than a
sheet, and it carries the bar the frame draws - "Hồ sơ" at 26/800, the global
search at 46 tall, the streak chip. The hero is the frame's: the ring at 168
(126 on the phone), the name at 34/800 with the rank and plan pills beside it,
the XP line, and **Chia sẻ then Chỉnh sửa at the hero's far right**, in that
order, at 46 tall. The settings card is "Cài đặt" with the frame's six rows, in
its order and with its glyphs - Ngôn ngữ đang học, Mục tiêu mỗi ngày, Nhắc học,
Gói, Nội dung riêng tư, Giao diện. Five Phosphor 2.1.1 icons the app lacked
(`target`, `credit-card`, `moon-stars`, `lock-key`, `share-network`) were
fetched from the package and inlined; none was typed from memory.

**What no backend can fill:**

- **GAP-H1 · XP and the rank.** The frame draws "15 840 XP", "Virtuoso · bậc
  10 / 32" and "CÒN 6 160 → LUMINARY". Nothing counts XP and nothing serves a
  tier, so the XP line says it is not counted, its bar is the unavailable one,
  and the ring stays the plain well until a tier arrives.
- **GAP-H2 · Nhắc học.** There is no study reminder: no schedule, no store, no
  notification. The row keeps its place and says so, and does not open.
- **GAP-H3 · Nội dung riêng tư.** Nothing counts a learner's imported texts for
  this row. Same treatment.
- **GAP-H4 · the reset date.** The frame's quota head reads "PLUS · ĐẶT LẠI
  12/10". `account_state()` carries the plan and each feature's limit and use,
  but no period or reset date, so the head carries the plan alone.
- **GAP-H5 · the joined date and the streak in the hero's meta line.** Neither
  is served; the line carries the language pair it does know.
- **GAP-H6 · the rail's foot.** The frame draws the rank crystal, the day's
  goal (18/30′) and the streak there. Orena measures none of the three, so the
  rail keeps the learner card it has.

**One conflict, for the human rather than for this lane (rule 7).** The frame
closes the quota card with a **"Lên Pro"** button.
`docs/product/ORENA_COMMERCE_ARCHITECTURE.md` §2 and §4 say the opposite:
`billing_ready` is false everywhere upstream and "read-only UI badges are not
access enforcement" - no price, upgrade action or provider identifier belongs
in the interface yet. The button is therefore **not drawn**, and the decision is
recorded here rather than made: either commerce opens, or the frame's button
waits for it.

## The rank system, re-read at the source (2026-09-22, later)

`Orena Rank Frame Master v2` is the current master and the app is now a
faithful port of it: **thirty-two ranks in eight bands of four** - Amethyst,
Sapphire, Orchid, Amber, Aquamarine, Carnelian, Moonstone, Prismatic - one
generator, one light at −48°, no raster anywhere. What the earlier port was
missing and now has: the two-hue split from Amber up (so a high band reads
multi-coloured rather than pale), the band's three extra rings, the second
star from rank 17, the orbit's glow dots, the master's own aura pair, and its
**three** levels of detail rather than two (`min` at 96px and under, `mid` up
to 170, the full crystal above).

**The conflict, recorded rather than decided (rule 7).** Two design sources
count ranks differently:

| Source                                                                    |  Ranks | States thresholds?         |
| ------------------------------------------------------------------------- | -----: | -------------------------- |
| `Orena Rank Frame Master v2` (and `Orena Hạn mức sử dụng`: "bậc 10 / 32") | **32** | no - it is a material spec |
| The Progress frame's ladder ("THANG CẤP BẬC · 20 BẬC")                    | **20** | yes, a word count per tile |

Taken as newest-wins the master is current, and the app follows it: the ladder
draws thirty-two. The Progress frame's numbers are kept **by name**, not by
position - its first sixteen names are the master's first sixteen, and
Archivist, Aurora, Celestial and Paragon are the master's 25th, 28th, 29th and
32nd - so a number the design states for a rank stays with that rank.

- **GAP-R1 · fourteen ranks have no threshold.** Virtuoso (which the frame drew
  "BẬC HIỆN TẠI" over), Navigator, Cartographer, Wayfinder, Chronicler,
  Rhapsode, Orator, Vesper, Ember, Curator, Lumen, Empyrean and Zenith have no
  stated word count, so their tiles show a dash and no one can be counted into
  them. Fourteen numbers are the product's to state.
- **GAP-R2 · is the ladder twenty or thirty-two?** If the Progress frame is the
  current one, the ladder is twenty and the master's other twelve ranks are not
  yet in play. One line from the human settles it; nothing else in the code
  needs to change, because both read `static/orena/product/rank.js`.

**Where the rank comes from.** Not from a backend - `tier` is still unserved.
It is derived from the one thing Orena really counts, the learner's mastered
words (past review stage three), against the thresholds above, in
`static/orena/product/rank.js`. Progress and Hồ sơ both read it, so they cannot
disagree. At zero words nobody holds a rank: Hồ sơ draws the plain well and the
Progress card says "Chưa có bậc", and the crystal appears at the first fifty
words rather than being shown for a rank nobody earned.

**One layout consequence.** Thirty-two tiles do not fit the Progress screen at
1920x1080, and that screen must stay inside one viewport. The page now takes
exactly the room the bar leaves and the **ladder scrolls inside its own panel**
(the side column too, if it ever runs longer). Nothing is clipped away and the
screen itself never scrolls.

## GAP-H7 · the usage bars can only ever read zero (2026-09-22)

Found while seeding a learner to review Hồ sơ. The plan's limits are real -
`account_state()` answers with each feature's `monthly_limit` - but **nothing
records a use**. `record_usage` has exactly one caller in the whole codebase,
`writing_coach/text_discussion.py`, and `reading.discussion_turn` is not one of
the features a plan lists. So after 1 600 saved words and a dictionary lookup,
`/api/product/me` still reports `used: 0` for `vocabulary.save` and
`dictionary.lookup`, and the panel draws six bars at zero.

This is a backend gap, not a surface one: the panel is the component the source
draws and the numbers it shows are the ones the product reports. Metering the
endpoints that a plan charges for - writing evaluation and rewriting, lookups,
saved words - is what makes the panel say anything. Until then the bars are
honest and uninformative.

`scripts/seed_sandbox_learner.py` fills the sandbox learner through the app's
own endpoints so the rank, the ladder and the vocabulary panels can be
reviewed with real data; it cannot fill these bars, for the reason above.

## Vocabulary is read by the page, and counted in the database (2026-09-22)

The three-minute listing was one symptom; the architecture was the disease.
`GET /api/library/vocabulary` answered with **every** word a learner had ever
saved, and Vocabulary, Tiến độ, Hồ sơ, Home, Search, the recall queue and the
book page all read it - to show a count, three words, a due queue or a filtered
list. Every one of those screens cost what the whole library cost, and one slow
vocabulary request made all of them wait.

**What each screen asks for now**

| Surface              | Before                                            | Now                                                                      |
| -------------------- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| Hồ sơ                | whole library, counted in the browser             | `/api/library/vocabulary/summary`                                        |
| Tiến độ              | whole library                                     | the summary, plus `?limit=3&order=recent`                                |
| Home ("what is due") | whole library, `.filter(due)`                     | the summary's `due`                                                      |
| Recall queue         | whole library, `.filter(due)`                     | `?status=due&order=due&limit=60`                                         |
| My Language          | whole library                                     | `?limit=50`, then `?cursor=…`; search, status and order go to the server |
| Saved panel          | whole library, searched and sorted in the browser | the same paged query                                                     |
| Search               | whole library, filtered per keystroke             | `?query=…&limit=40`, debounced                                           |
| Book page            | whole library, matched on the note                | `?focus=<title>&focus=<chapter>…`                                        |

`summary` (and the learner's rank) travels with every page, counted by
aggregate queries, so no screen adds items up and Hồ sơ and Tiến độ cannot
disagree. The rank ladder moved to `writing_coach/product/rank_ladder.py`: the
product states the thirty-two ranks and their thresholds, the browser reads the
answer, and `static/orena/product/rank.js` holds no thresholds any more.

**Indexes, measured rather than guessed.** At ten thousand saved words the
counts took fourteen seconds, because `saved_words` joins `vocabulary_learning`
on `lower(word)` and a function over a column cannot use the primary key - so
every row met every row. `SQLiteSpecializedLearningRepository.initialize()` now
creates expression indexes on `lower(word)` for both tables, plus
`saved_words(added_at DESC, word)`, `vocabulary_learning(next_review_at)` and
`vocabulary_learning(review_stage)` for the orders and filters the screens ask
for. Nothing else was added.

**Measured, on the schema the runtime creates** (best of five, in the app
image; the learner has that many saved words):

|                         |      0 |     12 |  1 600 |  10 000 |
| ----------------------- | -----: | -----: | -----: | ------: |
| summary (counts + rank) | 0.2 ms | 0.3 ms | 0.8 ms |  3.9 ms |
| first page (50)         | 0.3 ms | 0.6 ms | 1.5 ms |  7.6 ms |
| recent three            | 0.5 ms | 0.3 ms | 1.3 ms |  7.4 ms |
| due queue (25)          | 0.3 ms | 0.3 ms | 2.9 ms | 13.5 ms |
| search one page         | 0.3 ms | 0.3 ms | 1.9 ms |  7.9 ms |

Over HTTP in the sandbox, with the seeded 1 612-word learner: the summary is
6 ms and 2.4 KB, a 50-word page 20 ms and 23 KB, the due queue 24 ms, three
recent words 20 ms. The old full listing was **185 s** and would have been
~1.5 MB.

**What this does not change.** The endpoint keeps its name, its payload's
`items` and `summary`, and its save/review/delete siblings; it gained `limit`,
`cursor`, `query`, `status`, `order` and `focus`, and `next_cursor`,
`has_more` and `total`. A caller that passes nothing now gets the first fifty
words instead of all of them - which is the point, and is why every caller in
this repository was changed in the same commit.

## Four decisions closing the vocabulary paging work (2026-09-22)

**1. Sorting by level is not a global sort, and no longer pretends to be.** A
level is not in the learner's database - it comes from the curated catalogue
and is attached when a word is read - so the server cannot order by it, and a
cross-store sort would mean denormalising level onto every saved word, which is
a schema decision, not a UI one. The option is therefore offered only when the
list in front of the learner is the whole set it claims to cover (`has_more` is
false); while there is more to load it is disabled, and the order falls back to
the one the server actually applied. The level **filter** on a collection is
unaffected: that one has always been the server's, through the collection
endpoint's own `level` parameter.

**2. What a search matches is now stated, not left open.** The server matches
the word, its definition and the translation kept with it - every field the
learner's own database holds. It does not match the catalogue's
`support_translations`, which are attached at read time. This is not a loss in
practice: every way of keeping a word writes the meaning the learner was
looking at into `definition` or `translation_vi` (`vocabularyKeepPayload`, the
reader's keep, Quick Sheet's keep, Understanding's keep), so the words a
learner can search by meaning are the words whose meaning is stored. The
contract is written in `library_page`'s docstring, in the route, in the browser
client, and pinned by
`tests/test_vocabulary_paging.py::test_search_matches_the_fields_the_learner_database_holds`.
Searching the shared catalogue and intersecting would put a second store in the
search path for a case the keep paths already cover; if that ever becomes real,
it is a bounded change - the catalogue can be asked for matching terms and the
page filtered by them.

**3. The cursor belongs to the question it came from.** Every ordering ends in
a unique tie-breaker (`word`, which is unique per learner and language), so
`(added_at, word)`, `(next_review_at, word)` and `(lower(word), word)` are
total orders and no two rows share a key. The cursor carries the order and a
fingerprint of the filters (`query`, `status`, `focus`) alongside the key:
change any of them and the cursor is ignored rather than read against a
different ordering, so the caller gets that question's first page. A damaged
cursor is a first page too, never an error a learner has to read. What this
promises, and what the tests hold: a word whose sort key does not change is
seen exactly once; a word saved, rescheduled or graded mid-walk moves to where
its new key belongs and is met there.

**4. TRACKED · mobile `listLibraryVocabulary` owes pagination.** `mobile/` is
frozen (`AGENTS.md` §5), so it was not touched, and this is the item to pick up
when it thaws:

- `mobile/src/api/client.ts` → `listLibraryVocabulary()` calls
  `GET /api/library/vocabulary` with no parameters. The endpoint no longer
  answers with the whole library: it returns the first fifty words, plus
  `total`, `has_more` and `next_cursor`.
- `mobile/src/query/useReadingLibrary.ts` → `useLibraryVocabulary` holds that
  one response as a whole list.
- What it needs: `limit`/`cursor` in the client, an infinite query (or an
  explicit page) in the hook, and `summary` read for counts instead of the
  items being counted. `librarySchema` should gain the three new fields.
- Nothing is broken today - mobile is not shipped - and the mobile contract
  test mocks its own response, so it still passes.

**No other caller relies on the old behaviour.** Every browser caller asks for
a bounded page (held by `scripts/test_orena_vocabulary_paging.mjs`), and the
four server-side callers that used to read the listing to answer "is this word
saved?" - the word sheet, the collections list, a collection's cards and the
daily feed - now ask about the words they are drawing, through
`saved_vocabulary_words` and `saved_vocabulary_state`.

## GAP-H7, checked: the meter works, nothing a plan sells is wired to it (2026-09-22)

Asked to verify before closing, rather than assume. What is there:

- **The machinery is real and tested.** `record_usage` writes a `usage_events`
  row; `monthly_usage` sums this calendar month's rows; `account_state` reads
  that for each feature a plan lists. Six tests cover it end to end - an
  accepted turn is metered exactly once, nothing is metered when no provider
  answers, nothing when the cap refuses, and a repeated `request_id` is not
  metered again (`tests/test_text_discussion.py`, `tests/test_product_account_state.py`).
- **One caller.** `writing_coach/text_discussion.py` meters
  `reading.discussion_turn`, and that feature is in no plan's entitlements
  (`writing_coach/product/catalog.py`), so it can never appear on Hồ sơ.
- **Live sandbox, 2026-09-22**: `/api/product/me` reports `used: 0` for all
  nine features with `usage_state: "known"` - the meter was read and it is
  genuinely zero, not unreadable.

**Deferred, and left at zero.** The features a plan charges for - writing
evaluation, rewriting, lookups, saved words - do not call `record_usage` yet.
That is backend work with a human gate on it (commerce is not open;
`billing_ready` is false), not something a surface can fix, and nothing here
will be seeded or faked to make the bars look alive: a bar that reads zero
because nothing has been metered is telling the truth. The panel is the
component the source draws, and it will start saying something the day those
endpoints meter.

## Viewport check: 1920 is the reference, and what breaks below it (2026-09-22)

The source draws these screens at **1920x1080** and at **390x844**, and nothing
in between. 1920 is the reference and was not touched. The other widths were
tested for defects only - things that disappear, get crushed or run off the
edge - not treated as a brief to invent a layout.

**What was wrong, and is fixed** (neither changes 1920, both verified there):

- **Progress collapsed below its own width.** Holding the page to one screen is
  right at 1920, where the composition fits. Narrower, row two's four panels no
  longer fit across, the rows above grow, and the clamp crushed what was under
  them: at 1440 the rank ladder came out 40px tall, at 1024 the ladder and the
  rank card had **no height at all** - thirty-two rungs and the learner's own
  rank, invisible. The clamp now applies at 1600 and up, which is the
  composition it came from; below that the page scrolls like any page and
  everything is present (1440: all 32 rungs, ladder 1046px; 1024: all 32,
  ladder 1292px).
- **The Profile hero crushed its own copy.** The hero may wrap, but without a
  floor the copy simply got thinner instead: at 1024 the name, the rank pill,
  the plan pill and the XP line shared **94px** while the two actions kept
  their 267. The copy now has a floor of 320px, so the actions wrap under it
  instead (1024: copy 391px, actions on their own line). At 1920 the copy is
  990px and nothing moves.

**Verified clean**: Progress overview and Xu hướng, and Hồ sơ, at 1920, 1440,
1024 and 390 - no horizontal page scroll, nothing clipped outside the viewport,
the phone head and tabs intact at 390. Vocabulary, Library and Search were
swept at 1024 with nothing clipped; Home's card rail is `overflow-x: auto` by
design and is not a defect.

**For human review - the design does not define these, so nothing was
invented:**

- **What Progress is between 390 and 1920.** At 1440 and 1024 row two wraps
  from four panels to three and the screen becomes a scrolling page rather than
  one screen. That is the honest fallback, not a decision: whether the panels
  should shrink to stay four across, whether the ladder should stay a scrolling
  panel, and whether "one screen" is a rule at those widths, are design calls.
- **What Hồ sơ is at those widths.** The hero wraps its actions below the copy
  and the two panels stack. The source draws neither state.
- **Between 601px and about 900px** the phone composition has already been left
  behind (the phone rules stop at 600) while the desktop one has no room. No
  frame covers it; it is not currently drawn for any device Orena targets, so
  it was left as it falls out.

## One of the two "inherited failures" was the CRLF checkout, not the code (2026-09-22)

`scripts/test_orena_writing_workspace.mjs` has been failing on this machine for
weeks and passing in CI. It asserts `/showActivity\(\);
\s+const retry/`
against `ui/expression.js`. Git stores that file with LF and checks it out with
CRLF here, so the `
` sits where the pattern expects `
` and the match
fails - the source is identical either way. It now passes locally only because
this lane rewrote that file with LF endings.

So the local expectation is **one** inherited failure, not two:
`scripts/test_m3_pronunciation_contract.mjs`, which is a real content
mismatch (a pronunciation projection that no longer carries the score the test
expects) and fails on a clean HEAD tree as well. Same family as the CRLF note
already recorded for `test_orena_grammar.mjs`: an environment failure, not an
application regression - and the gates that are written against source text
would be steadier matching `?`.

## Vocabulary review, rebuilt on its frame (2026-09-22)

The next flow on the checklist. Measured against `Orena Vocabulary.dc.html`
frames "Vocabulary review", "Vocabulary review mobile" and "… mobile hidden"
(the cached copy is byte-identical to the source today).

**The blocker was a data contract, and it is fixed.** The source has always
drawn three grades - Quên · Chưa chắc · Nhớ rồi - while the API accepted two,
so the middle button sat on the screen disabled (GAP-019). `VocabularyReviewIn`
now takes `unsure`: it neither promotes the card nor sends it back, counts
neither a recall nor a lapse, and brings the card round tomorrow - between
`again`'s ten minutes and `got_it`'s next step. Seven tests hold that behaviour
and the schedule.

**Each grade says what it will do.** The source prints an interval under every
grade. Rather than writing those numbers on the buttons, every saved word now
carries `schedule` - the scheduler's own answer for that card at its own stage

- and the buttons print it. A card at stage 0 shows 10m / 1d / 1d; at stage 1,
  10m / 1d / 3d.

**The screen is the card.** 420x560 at 1920, the violet ring and the bloom when
it is open, the plain glass when it is closed; the word in Noto Serif 54 (39 on
the phone), the reading, the rule, the meaning at 21/800, the sentence in
italics; one caret back, one segment per card, the count; three grades of 64
under it, and on a closed card the line that says the grades come after it is
opened. Measured and matching at 1920.

**Deleted with the old panel** (rule 44): the two grades the scheduler could
not take, the separate reveal button (the card turns instead), the second way
back while a card is up, and the review room's own "ask about this word"
control.

**Kept, and recorded as differences from the frame - for human review:**

- **The question still fits the word's origin.** The frame draws one card
  (word → meaning); the product decides the question from how the word entered
  the learner's life (`product/recall.js`: in context, by meaning, by saying
  it, to reuse), which two gates pin as learner memory. The composition is the
  frame's; the question inside it is the product's. **DESIGN DECISION NEEDED:**
  whether the four question shapes stay.
- **The landing step stays.** The frame opens straight on the card; the product
  shows what is waiting first, so a learner is not dropped into card one
  without knowing whether this is three words or thirty. **DESIGN DECISION
  NEEDED.**
- **Where the word was met** is said on the back of the card, under the
  sentence. The frame draws the sentence but not its title.
- **"Nghe phát âm"** on the closed card is not drawn: nothing stores audio for
  a saved word, and a button that plays nothing is worse than no button.
  **BACKEND GAP.**
- **The collection panel** (560px, cover, tier, "TỪ TRONG BỘ", "Xem cả 150 từ")
  belongs to reviewing a collection. This review is of the learner's own saved
  words, which have no collection, so the panel is not drawn. **DESIGN DECISION
  NEEDED:** what that side carries for a saved-words review.
- **The "ask about this word" capability** moved rather than disappeared: the
  line that says where a word was met is now the way to ask about it, on the
  saved list - a screen the design's own matrix marks INCOMPLETE, so nothing is
  contradicted.

**Viewports**: 1920 (card 420x560, grades 420x64, word 54, meaning 21, flip 44,
rail gap 6 - all the frame's numbers), 1440 and 1024 (the same card, the page
scrolls at 1024), 390 (the card fills the screen above the grades, word 39,
grades 58). No horizontal scroll and nothing clipped at any of the four.

**Vocabulary Library (frame 01) is not migrated yet.** It draws a grid of
collection covers; the sandbox has no published collection (packs are gated),
so the screen would be an empty state. Left for the human to decide whether to
build it now against an empty catalogue.

## Vocabulary Library, rebuilt on its frame (2026-09-23)

**The design was re-read at the source first.** `Orena Vocabulary.dc.html` on
claude.ai is byte-identical to the pinned copy - 106 480 characters, the same
sha as `PINS.tsv`, the same ten frames - so there is no newer Vocabulary design
to load; what was missing was the part of it Orena had not built yet.

`#/language` now opens on "Vocabulary library" instead of the D-059 home panel:
the filter chips (42 tall, 10/18, radius 999, the selected one in the accent
gradient), then the collections themselves - a cover of 290x186 at radius 16
with the frame's own material (a dotted field, a lit corner, a diagonal fall),
its progress along the bottom inset 14, the name at 18/700 and one mono line at
12.5 saying the language, the size and how far through it the learner is. The
phone frame is the same thing at two columns, covers of 150 and chips of 13.5.
Measured: cards 290, gap 26, cover 186 at radius 16, name 18/700, line 12.5.

**Deleted with the old home** (rule 44): the domain tile and its two figures,
the bounded two-collection preview, the "browse the catalogue" button, the
`vocab-collection` tile and the tier chip that said "—" because nothing defined
a tier (GAP-020 goes with it - the frame's card has no tier).

**Two rows the frame does not draw, kept and recorded.** Under the catalogue:
what is due (only when something is) and the way to everything saved. The
design's own matrix marks "My Content (bộ của tôi)" INCOMPLETE, so it draws no
screen for a learner's own set, and their 1 615 words must stay reachable.
**DESIGN DECISION NEEDED:** where the learner's own words live in the Library -
a card in the same grid, a row under it as now, or a screen of their own.

**The catalogue is empty in the sandbox** (packs are rights-gated), so the room
shows the empty state and the two rows. The grid was measured by injecting six
throwaway cards into the DOM, reading their geometry and discarding them on
reload - nothing was seeded or stored.

**One shared component was wrong and is fixed**: `.state-panel--empty` is a
column, but its text kept the 14rem _basis_ the row layout gives it, which in a
column is a height - so every empty state in Orena drew a 224px box under two
lines of text. Upright it now takes what it needs (the Vocabulary empty state
went from 348px to 151px).

**Also corrected**: the bar over Vocabulary said "Ngôn ngữ của tôi" while the
rail and the tab bar said "Từ vựng". The frame's bar carries the destination's
name, so the bar now says what the navigation says.

**Viewports**: 1920 (the frame's numbers), 1440, 1024 and 390 - no horizontal
scroll, nothing clipped, chips and rows at the phone frame's sizes. At 1920 the
grid fits five covers across exactly as the frame does, unless a scrollbar is
present, which costs 15px and drops it to four.

## Four designs arrived; what each one needs before it can be built (2026-09-23)

The source gained two screens and grew two more (inventory and measurements:
`docs/design/canonical-ui/SYNC_2026-09-23.md`). This entry says only what each
one needs, and which of them this lane may not build at all. Nothing here is a
decision.

**Vocabulary (32 frames, was 10) - buildable, one frame at a time.** The only
one of the four whose needs the backend already meets or can meet inside this
lane. Built so far: **Review summary** (frames 18-19), measured at 1920, 1440,
1024 and 390. Not built, in the order the room needs them:

- Search (frames 20-21) - server-side search already exists behind
  `GET /api/library/vocabulary?query=`; this is UI only.
- Add word (23-24), create deck (25), save-to-deck sheet (22) - a learner's own
  deck has no contract. **DESIGN DECISION NEEDED is not the blocker; a
  persistence decision is** (AGENTS §7: no new persistence or schema decisions
  for learner-owned data). Recorded, not chosen.
- Four review modes the app does not have - typing (11-12), listen-and-choose
  (13), dictation (14), cloze (15), speaking (16-17). Typing and cloze need
  nothing new. Listen-and-choose and dictation need audio per word; speaking
  needs grading, which is a provider credential (human gate).
- Review settings (27-28) - needs a stored per-learner setting; same
  persistence hold as decks.
- States (29-32) - empty, nothing due, offline, load error. Buildable now.
- Card deep view (3-4), strokes (5), context clips (6-7) - strokes and clips
  need per-word data Orena does not hold.

**Speaking (18 frames, was 7) - gated.** Free-talk result, lesson summary and
compare-with-model all show a grading Orena cannot produce without a speech
provider credential, which is a human gate (AGENTS §10). The frames that need
no grading - settings (14), mic blocked (15), not heard (16), offline grading
(17), empty (18), shadowing (13) - are buildable now.

**Thư viện của tôi (26 frames, new) - blocked on a contract, not on UI.** It is
one library over _every_ kind of thing a learner kept: words, writing, speaking
takes, reading, grammar, books, and collections across them. Orena has no
cross-type "kept" contract; each capability keeps its own. Building one is a
learner-data persistence decision, which AGENTS §7 reserves. **For the human:**
this screen also answers the open question left by the Vocabulary Library entry
above ("where do the learner's own words live"), so it should be decided with
that one rather than separately.

**Admin Control Center (21 frames, new) - held.** _Overtaken 2026-09-29 (D-099): the console was
merged by PR #63 and runs at `/#/admin`; it keeps its own address through the cutover, and the
Admin wave builds on the pinned `Orena Admin.dc.html`, which supersedes this Control Center._ AGENTS §7 keeps Platform
Admin inert: its APIs and `static/admin.js` survive, the historical shell was
removed, and the hold says not to restore a host for it. The design now draws
that host in full. **This lane will not build it until the human lifts the
hold.** Nothing in the design changes the hold; only the human does.

**Stale in the source, for the human:** `screens/screen-matrix.md` still marks
Profile, My Content, Admin and Loading/Empty/Error INCOMPLETE while canonical
screens for them now exist in the project. The matrix belongs to the design
project; this lane does not edit it.

## The human decided what Vocabulary and My Library each own (2026-09-23)

Instruction of 2026-09-23, which closes three of the questions this file was
holding open:

- **Vocabulary is the shared content library** - the catalogue a learner takes
  words from. The new frames draw it that way: packs, filters, progress per
  pack, and no learner rows.
- **Thư viện của tôi is the learner's own library** - everything they kept and
  everything their learning produced, across kinds. The data contract prefers a
  **reference to the source content plus the learner's own state and metadata**
  over copying content.
- **Admin Control Center: not this lane.** Another lane has it.
- **Speaking: not this lane.** Another lane is doing its backend and its UI.
- **Per-word audio for Vocabulary** is wanted: real pronunciation from
  Wiktionary / Wikimedia Commons first, local TTS (Kokoro preferred) as
  fallback, cached so nothing is generated twice, with source, licence and
  attribution stored; for Chinese and any word with several readings the audio
  binds to the reading, not to the raw text.

The backend audit against that instruction, what already matches it, the three
real disagreements and the order they are closed in:
**`docs/project/MY_LIBRARY_DATA_CONTRACT_AUDIT.md`**.

This settles the "DESIGN DECISION NEEDED" left above about where a learner's
own words live: in Thư viện của tôi, not in the Vocabulary room. The Vocabulary
room's own-word rows are deleted only once My Library can reach them.

## Thư viện của tôi, first slice: the library itself (2026-09-23)

The room exists and is reachable: `#/collection`, a destination in the rail and
a tab on the phone, as the frame draws it between Vocabulary and Progress. It
reads `GET /api/collection` - the typed query over the owners that already
exist - and owns nothing. The old "Saved" room (four device-memory tabs) is
deleted with it (rule 44).

**Built, measured against "Thư viện của tôi · desktop" and "· mobile":** the
bar (title 26/800, the count in mono 13, one search 380x44 at radius 12), the
kind chips (40 tall, radius 12, 14.5, the count in mono 12) and the item rows
(18/22 at radius 18, title 20/600 - serif for a word, a passage or a take -
gloss 14.5, meta 13.5, the date in mono 12 in a 130 column). Each row opens
where it came from, through that owner's own route. Verified at 1920, 1440,
1024 and 390, in English, Vietnamese and Chinese: no clipping, no horizontal
scroll, six tabs fit the phone.

**Two kinds have no owner, so they are not chips:** a note is stored nowhere in
this repository, and a book is catalogue only (`reading_books` records who
imported it, not whose library it is). Neither is faked with an empty tab.

**What the frame draws that this slice does not, and why.** Every one of these
needs the kept-item relation described in
`docs/project/MY_LIBRARY_DATA_CONTRACT_AUDIT.md` §3, which is a schema decision
reserved for the gate:

- the "CẦN ÔN HÔM NAY" card and the merged review session across kinds - only
  saved words have a review schedule today;
- the row's next-due column and its state pill (đến hạn / cần ôn / đang học /
  đã thuộc) - three of the four states exist for no kind;
- the mark button ("đánh dấu cần ôn", which the frame's own spec calls
  `PATCH item {pinned}`) and the add-to-collection button;
- collections themselves (the frame's right-hand column, "mỗi bộ một loại"),
  create-collection, multi-select and delete;
- the item detail overlay with its original context, its history and its
  collections. The one thing that panel does which this slice can do - open the
  source - is what a row does when tapped.

**One measured deviation, recorded rather than resolved.** The frame's kind
chip is 40 tall; every control in Orena has a 44px touch floor
(`foundation.css`). The chip declares `min-block-size: 40px` and the floor
raises it where it applies. Accessibility is not redesigned to match a frame.

**One limit the learner can see.** The collection query reads each owner in
full up to a bound (200 for saved language) and merges in memory, so a library
larger than that is `partial` and the bar says "ít nhất N" rather than a total.
Search is not limited by it: an owner that holds more than the read is handed
the query and searches all of what it holds - without that, searching a
3 000-word library would have searched 200 words and answered "nothing found".
Paging the merge itself is the Collection Architecture §3 work (owner cursors
plus a stable merge boundary) and has not been done.

## The sandbox database was temporary by design, and that cost a test learner (2026-09-23)

`orena-foundation-postgres` keeps PGDATA on **tmpfs**. That was a deliberate
choice once - `scripts/start_orena_sandbox.ps1` said "the database is temporary
by design" - and it has a real cost: Docker Desktop recreates that container on
its own after a crash or an update, and everything in it goes. On 2026-09-23 it
emptied a seeded learner of 1 619 words mid-session, and the emptiness looked
exactly like an application fault (the app answered 200 with zero rows) until
the container was inspected.

`scripts/persist_orena_sandbox_db.ps1` fixes it: dump, recreate that one
container on the new named volume `orena-foundation-sandbox-data`, restore,
restart the web container. It is idempotent, it keeps the dump, it creates no
volume but that one and removes none, and it goes nowhere near
`ai-writing-coach-data` or `ai-writing-coach-postgres-data`, which belong to
production and preview.

**It needs a person to run it.** Recreating a container is a shared-runtime
change this lane's harness is not permitted to make, so the script is written,
syntax-checked and committed, and the run is the human's:

```
powershell -ExecutionPolicy Bypass -File scripts\persist_orena_sandbox_db.ps1
```

Until then the sandbox behaves as before, and `start_orena_sandbox.ps1` now
says which of the two states the container is in rather than assuming tmpfs.

## Thư viện của tôi, second slice: marking, sets, the queue and the panel (2026-09-23)

On the reviewed contract (`20260923_0013`, D-074), so the four things the first
slice had to leave out now exist:

- **The mark** ("đánh dấu cần ôn"): the row's first button, `pinned_at` on the
  item. Keeping is implicit in marking - the first mark records the
  relationship, then marks it.
- **Sets, one kind each**: the right-hand column at 420, the picker that offers
  only sets of the item's own kind (which is also all the database will take),
  and naming in a field in the room.
- **"CẦN ÔN HÔM NAY"**: marked items first, oldest mark leading, then what the
  words owner says is due. Nothing invents a schedule for a kind that has none:
  a passage is in the queue because the learner marked it, or not at all.
- **The detail panel**: 560 from the right, the word at 34/600, the context box,
  the three-state control (marked / learning / known), the history, the sets it
  is in, and the way back to where it came from.

**Measured** against "Thư viện của tôi · desktop" at 1920 (panel 560, title 34,
gloss 17, state segments 40, history in three), and checked at 1024 (the sets
column falls under the list - see below) and 390 (the due card stacks, the
panel fills the width, the buttons are the 44 touch floor). English, Vietnamese
and Chinese: no clipping, no horizontal scroll, the panel opens and closes
without moving the page.

**Two deviations, recorded rather than resolved:**

- **The sets column stacks under the list below 1100px.** The frame draws two
  columns at 1920 and a single column on the phone; it draws nothing between.
  At 1024 a 420 column would leave the rows too narrow to read, so they stack.
  **DESIGN DECISION NEEDED** if the intermediate width is meant to look
  otherwise.
- **The history is drawn only for a word.** Recalls, last review and next
  review are the saved-language owner's record; no other kind has one, and
  three dashes would be three measures nobody took (rule 4). The frame draws
  the block for every kind.

**Still not built from this frame**, and still waiting on something:

- multi-select and delete (the frame's "My library multi-select" and "delete
  confirm"): the repository can forget an item, the room offers no way to;
- reordering a set, and opening a set as a filtered list;
- notes on an item (`library_items.note` exists and nothing writes it);
- the kinds with no owner, unchanged: a note is stored nowhere, a book is
  catalogue only.

## Per-word audio, bound to the reading (2026-09-23)

`writing_coach/word_audio.py`, on the identity the entry work put in the
runtime: the cache key is `(identity_key, reading)`, so xíng and háng are two
recordings of 行 and neither can be served for the other.

**The rule that outranks coverage:** a word whose reading is still ambiguous
gets no audio, and no source is even asked. A recording of the wrong reading
keeps teaching the wrong word every time it is played, and nothing in the row
says so; silence is recoverable.

**No schema, and no contract moved.** The clips and their licence live in the
existing `BookAssetStore` seam (`data/word_audio`), not in a table. Nothing
here writes to `saved_words`, `library_items` or `vocabulary_entries`, and
neither Vocabulary nor My Library answers anything differently.

**Coverage, measured against Wikimedia Commons** with
`scripts/measure_word_audio_coverage.py` (crosses the network, so it is an
operator tool, not CI):

|                                                    |           |
| -------------------------------------------------- | --------- |
| English, 30 ordinary words                         | **30/30** |
| Chinese, 15 readings of 8 multi-reading characters | **12/15** |

Missing and recorded rather than worked around: 行 háng, 重 chóng, 差 chāi.
Commons has no clip named for those readings, and a clip named only 行 could
be either, so they are refused. A local voice would answer them once one is
configured.

**Two things that measurement caught**, both of which had made coverage look
like zero: a free-text search for an ordinary word returns harbours and folk
songs rather than pronunciation, so files are now asked for **by name** (the
conventions Commons actually uses) with a narrow Lingua Libre search behind
it; and Commons appends campaign parameters to the url it hands back, so the
file type has to be read from the path - `rsplit(".")` over the whole url read
`…&utm_content=original` as the extension and rejected every real recording.

**The fallback is a seam, not a running voice.** `KokoroVoice` speaks through
`KOKORO_TTS_URL`; unconfigured - which is every environment here - it reports
itself unavailable and the library answers "no audio" rather than substituting
another voice. **Nothing is generated locally today**, and the coverage above
is Commons alone.

**No surface plays it yet.** `GET /api/library/vocabulary/{word}/audio` says
whether there is a clip, under what licence and with what attribution, and
`GET /api/library/audio/{key}` serves the bytes. Putting a play control in
Vocabulary or My Library is UI scope nobody has opened, and the attribution the
licence obliges has to be shown wherever it lands.

## Playback, where the frame draws it - and where attribution has nowhere to go (2026-09-23)

**Wired into the surface the design already has.** "Vocabulary review mobile
hidden" draws a pill under the word - 32 tall, 0/13, radius 999, the filled
speaker at 12 and the words at 10 - and that is the control, in the review card
the app already has. Nothing new was invented: My Library's frames draw no
speaker at all, so My Library got none.

The pill is inside the card's own button, so hearing a word does not flip it:
hearing is not answering.

**Drawn only when there is a clip.** The room asks once per word, when its card
comes up, and draws the pill when the answer is available. The frame draws the
pill on a card whose word has a recording; a pill that played nothing would be
worse than no pill. **Recorded rather than decided.**

**The attribution has no place in the design, and the licence requires one.**
Every Commons clip here is CC BY-SA or CC BY: playing it obliges naming the
author and the licence. The frame draws the pill and nothing else. So for now
the attribution travels on the control itself - `title` and `aria-label`, so it
reaches both a pointer and a screen reader - and **this is not a decision, it
is a placeholder.** _DESIGN DECISION NEEDED:_ where a learner sees "Dvortygirl
· CC BY-SA 3.0 · Wikimedia Commons" - a line under the card, the word's detail
sheet, or a credits screen in Settings. Until then the obligation is met
minimally rather than visibly, and that is a compromise the human should settle
rather than the lane.

**Why the sandbox catalogue was empty:** nothing had ever been imported into
it. Catalogue content is admin-imported (`POST /api/admin/vocabulary/import`),
not seeded, and the sandbox database has been recreated twice this week. It is
not a defect and nothing was lost.

**A small dataset now exists** for end-to-end audio, imported through that same
admin route rather than written into the database:
`scripts/sandbox_audio_dataset/` - six English words, and six Chinese entries
of which five carry two readings each (行, 重, 长, 乐, 还). Both collections are
published, which `find_entry` requires.

**Verified end to end through the API, against the real Commons:**

|                    |                                                                                   |
| ------------------ | --------------------------------------------------------------------------------- |
| `harbour`          | available, CC BY-SA 4.0, "Speaker: Vealhurl"                                      |
| `winter`           | available, CC BY-SA 3.0, "Dvortygirl"                                             |
| 行, no reading     | refused, `reading_ambiguous`, and the two readings offered                        |
| 行 `?reading=xíng` | available, CC BY 2.0 fr, "Wei Gao, Vion Nicolas"                                  |
| 行 `?reading=háng` | `not_found` - the gap the coverage measurement named                              |
| cache              | first 0.84s, second **0.05s**; the bytes route serves 10 138 bytes of `audio/ogg` |

## The fallback works; the voice behind it is the human's to run (2026-09-23)

Commons is complete end to end, so the fallback was the next thing to check.
The **path** is verified, with a stand-in that speaks the protocol
`KokoroVoice` uses (a local service returning a valid WAV - not a voice, and
not in the repository):

|                            |                                                                                                    |
| -------------------------- | -------------------------------------------------------------------------------------------------- |
| 行 háng, 重 chóng, 差 chāi | Commons has none; the fallback answered each, and was told **the reading**, not just the character |
| `harbour`                  | Commons answered; the fallback was asked **0 times**                                               |
| cache                      | every one of them: first ~1.6s, second 0.000s                                                      |

**What is missing is a voice, not wiring.** The application image has no
Kokoro, no ONNX runtime and no espeak, and putting one there is not this
lane's call: it means either a model in the image or a new container on the
shared runtime, and both are the human's gate (AGENTS §10). The seam is ready -
set `KOKORO_TTS_URL` to a service that answers
`POST {text, reading, language}` with audio bytes, for example a
kokoro-fastapi container on the sandbox network, and the three readings above
are covered on the next request.

Until then `KokoroVoice` reports itself unavailable and the library answers "no
audio", which is the correct behaviour and the reason the Chinese coverage
figure is 12/15 rather than 15/15.

## Where a Commons recording is credited: the human decided (2026-09-23)

The design draws the pill and no place for the credit it obliges, so this is a
human decision, recorded as one rather than read out of a frame:

- **Author, licence and source go in the word's detail panel** - My Library's,
  which is the app's word detail panel today. The source is a link, because
  "where it came from" is the part a licence asks to be reachable.
- **The recall card gets no attribution line.** It keeps `title` and
  `aria-label` as an accessibility layer, which is now a supplement rather than
  the whole of the obligation.

My Library still plays nothing - its frames draw no speaker - so the split is:
the review card plays, the word panel credits. The gate holds both halves.

## The fallback may not guess a reading, and a plain Kokoro cannot be told one (2026-09-23)

Standing the real service up made the limit plain, so the adapter now says it
out loud instead of discovering it in production.

A Kokoro server is told **text** and speaks it in its own voice. Given 行 it
produces that character's default reading; its request has no field that says
"the háng one". Answering anyway would attach a confident recording of the
wrong sound to a learner's word - the one thing this whole feature exists to
prevent - so `KokoroVoice` **refuses a word whose reading is in question** and
is not even asked.

What that means for the three gaps the coverage measurement named:

|                                         |                                      |
| --------------------------------------- | ------------------------------------ |
| Words with one reading and no recording | the fallback covers them             |
| 行 háng, 重 chóng, 差 chāi              | **still uncovered**, and honestly so |

A deployment that _can_ honour a reading - a grapheme-to-phoneme override in
front of the voice - declares itself with `KOKORO_READING_AWARE=1`, and then it
is asked and told the reading. That override does not exist here, and building
one is its own piece of work, not something to assume.

`KokoroVoice` also speaks the real protocol now (`POST .../v1/audio/speech`
with an OpenAI-compatible body and a per-language voice) rather than the shape
the first draft invented, and a generated clip is recorded as `generated`, with
no author, so a surface can say it was made rather than imply a recording.

## Vocabulary, checked frame by frame against the source (2026-09-23)

Asked for by the human: compare the Vocabulary room with the design and sync
it, inventing nothing, and say which frames have no screen. The design project
was read at its source (`DesignSync`, read-only) and the frames were rendered
from the pin taken this morning; all 32 frames are listed below.

### Synced in this pass

| What the frame says                                                            | What the app had                                                | Now                                                                                                                                        |
| ------------------------------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| "Vocabulary library" body is **the chips and the pack grid, and nothing else** | a third block under them: the learner's due row and "Từ đã lưu" | **removed** - Vocabulary is the shared catalogue, and a learner's own words are Thư viện của tôi's (D-074). Rule 44: deleted, not restyled |
| chip 40 tall, 10/18, 15px, radius 999                                          | 46 tall (the page's 1.7 line-height inflating it)               | **40**, with the line-height set after `font: inherit`, which was putting it back                                                          |
| review card word 54, weight **600**, serif                                     | 54 at weight 700                                                | **600**                                                                                                                                    |
| the "Nghe phát âm" pill is as wide as its words                                | stretched the card's width                                      | centred at its own width                                                                                                                   |

The saved-word management view inside the Vocabulary room is now unreachable:
its only entry was the row that went. Its code is still there and still pinned
by the paging gates (`test_orena_vocabulary_paging.mjs`), so removing it is a
second, larger change - **recorded, not done**.

### Verified as already matching

pack grid 290 columns at gap 26; cover 186 at radius 16; phone two columns of
158.5 with covers of 150 and chips of 13.5; review card 420x560 at radius 26;
the flip pill 44 at 15; the three grades 64 tall with their own interval under
each - "Quên · Chưa chắc · Nhớ rồi", which is the frame's own set; Review
summary as measured this morning.

### One difference left, for the human

The frame draws a **490x44 search inside the Vocabulary bar**; the app uses the
shared top bar's search, which is 362x44 at 13.5px. The top bar is one
component across every destination and is pinned from its own baseline, so
widening it for this screen alone would change every room. **DESIGN DECISION
NEEDED:** is the Vocabulary bar's search a screen-specific control, or is the
shared bar's search simply narrower than the baseline says?

### The 32 frames, and what exists

Read this table with the dated sections below it: each one says how a frame was
built, what it is fed by, and what was recorded rather than decided.

|   # | Frame                           | App                                                                        |
| --: | ------------------------------- | -------------------------------------------------------------------------- |
|   1 | Vocabulary library              | **yes** - `#/language`, with the head frames 01-02 draw (2026-09-23)       |
|   2 | Vocabulary library mobile       | **yes** - the same room at 390                                             |
|   3 | Vocabulary card deep            | **yes** - the dictionary's half of the word (2026-09-23)                   |
|   4 | Vocabulary card deep scrolled   | **yes** - the learner's half                                               |
|   5 | Vocabulary strokes              | **yes** - on the stroke capability vendored 2026-08-26 (2026-09-23)        |
|   6 | Vocabulary context clips        | **yes** - real timestamped moments in the listening catalogue (2026-09-23) |
|   7 | Vocabulary context clips mobile | **yes**                                                                    |
|   8 | Vocabulary review               | **yes** - `#/practice?intent=recall`                                       |
|   9 | Vocabulary review mobile        | **yes**                                                                    |
|  10 | Vocabulary review mobile hidden | **yes** - including the listen pill                                        |
|  11 | Review typing retry             | **yes** - two tries, the hint, marks not required (2026-09-23)             |
|  12 | Review typing mobile            | **yes**                                                                    |
|  13 | Review listen choose mobile     | **yes** - offered only where there is a recording and neighbours           |
|  14 | Review dictation mobile         | **yes**                                                                    |
|  15 | Review cloze mobile             | **yes** - offered only where the sentence really holds the word            |
|  16 | Review speaking mobile          | **no screen** - speech grading is the Speaking lane's                      |
|  17 | Review speaking mic blocked     | **no screen** - same lane                                                  |
|  18 | Review summary                  | **yes**                                                                    |
|  19 | Review summary mobile           | **yes**                                                                    |
|  20 | Vocabulary search               | **yes** - the room's own search, both halves server-side (2026-09-23)      |
|  21 | Vocabulary search mobile        | **yes**                                                                    |
|  22 | Save to deck sheet mobile       | **yes** - over Thư viện của tôi's own sets (2026-09-23)                    |
|  23 | Add word modal                  | **yes** - the same fields as 24, widened                                   |
|  24 | Add word mobile                 | **yes**                                                                    |
|  25 | Create deck mobile              | **yes** - name and language; the colour chooser needs a column (below)     |
|  26 | Vocabulary deep desktop         | **yes** - both halves at once, with the strokes column (2026-09-23)        |
|  27 | Review settings desktop         | **yes** - device memory, no schema (2026-09-23)                            |
|  28 | Review settings mobile          | **yes**                                                                    |
|  29 | Vocabulary empty mobile         | **yes** - measured against this frame (2026-09-23)                         |
|  30 | Deck nothing due mobile         | **yes** - both numbers counted, and the second door to the settings        |
|  31 | Review offline mobile           | **yes** - answers wait on the device and sync (2026-09-23)                 |
|  32 | Deck load error mobile          | **yes** - with the code a learner can quote                                |

**Thirty of the thirty-two have a screen, and the other two are not this
lane's**: frames 16 and 17 are Speaking's. Every Vocabulary frame is built.

## Choosing several, and deleting with a way back (2026-09-23)

Built from "My library multi-select" (desktop and mobile) and "My library
delete confirm", including the frames' own spec panel.

- **In and out**: a box on each row that appears with the pointer, Shift-click
  for a range, a long press on a phone where there is no hover. Escape, the
  cross, or un-choosing the last one leaves.
- **The bar replaces the header**: a way out, "Đã chọn N", select-all - and the
  foot becomes the frame's four actions at 56 with 21 icons and 11.5 words.
- **Into a set** is on only when everything chosen is one kind, which is also
  all the database will accept; otherwise it is dimmed and says why.
- **Delete always asks**, names what is lost and what survives, and counts
  itself on the button. Afterwards a toast offers **Hoàn tác for ten seconds**.

**One thing had to be built for undo to be honest.** Deleting a word takes its
review schedule with it, and re-saving would hand back a new card due today.
`restore_library_record` (both repositories) and
`POST /api/library/vocabulary/restore` put the word back as it was - stage,
recalls, lapses, last and next review, and where it was met. Four tests hold
the difference between restoring and saving again.

Verified in the browser against the sandbox: choose one, Shift-click a range,
"Đã chọn 3"; delete two; both gone; Hoàn tác; both back.

## The saved-words view leaves Vocabulary (2026-09-23)

Vocabulary is the shared catalogue; a learner's own words are Thư viện của tôi's
(D-074). The room's `saved` view is deleted rather than restyled (rule 44),
together with the three handlers only it used, its paging function, its search
debounce and the `vocabularyManage` copy key.

**Nothing was lost.** Checked capability by capability before deleting: listing
saved words, searching them (server side, cursor-paged), opening one, marking it,
filing it into a set, deleting with ten seconds of undo — all are in Thư viện của
tôi. The route in is the tab bar, which the design gives it.

Three controls the old view carried are **not drawn by any canonical frame** and
were not rebuilt anywhere:

| Control                                                                    | Where it was       | Decision                                                    |
| -------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------- |
| Status filter chips over saved words (all/new/learning/due/mastered/saved) | Vocabulary → saved | Not drawn. Thư viện của tôi draws "cần ôn hôm nay" instead. |
| Sort (recommended / alpha / level / due) over saved words                  | Vocabulary → saved | Not drawn.                                                  |
| Choosing words to start a study session from the list                      | Vocabulary → saved | Not drawn. Recall decides its own queue.                    |

They survive on the **collection** views, where `management()` still serves the
catalogue, and whether the canonical collection frames draw them is measured in
the frame work, not assumed here.

Two gates moved with the behaviour rather than being weakened:
`test_orena_vocabulary_paging.mjs` now pins the cursor on `ui/collection.js` and
pins that `ui/expression.js` holds no `saved` view at all;
`test_orena_vocabulary_experience.mjs` pins the same absence.

## One word, opened all the way (2026-09-23)

Frames **03 Vocabulary card deep**, **04 Vocabulary card deep scrolled** and
**26 Vocabulary deep desktop** — built, measured, and fed by real reads.

Each section has one source, and a section with nothing in it is **absent**
rather than filled:

| Section                    | Where it comes from                                                                                                                                             |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nhiều nghĩa · từ loại      | the catalogue entry's `detailed_definitions` / `short_meanings`, its part of speech and its examples                                                            |
| Kết hợp thường gặp         | **new**: `VocabularyRepository.find_neighbours` — published entries that contain this word and are longer, shorter first                                        |
| Cụm liên quan              | the same neighbours, kept only where one carries a meaning                                                                                                      |
| Đối chiếu · Mô hình tư duy | the explanation capability, **cached in the asset store** under `blake2s(identity, reading, support)`, so a word opened twice costs one call and says one thing |
| Lỗi thường gặp             | the catalogue's own `usage_notes` first; the explanation only where the catalogue is silent                                                                     |
| Lấy từ đâu                 | the provenance the saved word already carries (`source_kind`, `source_fragment`) — one row, because one place is what the app recorded                          |
| Câu của bạn                | **new**: `sentences_using` on both repositories — the learner's own writing, narrowed by the database and cut to sentences here                                 |

No schema: the explanation cache is a `BookAssetStore` key, as per-word audio
is. `GET /api/library/vocabulary/{word}/deep` is the whole screen in one read.

**Two things the frames do not settle**, recorded rather than decided:

1. **No canonical frame draws a way in.** The desktop frame's own note says the
   screen opens "từ mặt sau thẻ, từ kết quả tìm hoặc từ màn tổng kết", but
   frames 08–10 and 18–19 draw no control for it. The word on the back of a
   card opens itself — an attribute and a keyboard role, no pixel added. Search
   and the summary will open it when those frames are built. A drawn
   affordance is the human's decision.
2. **The desktop frame draws no way to keep or unkeep** from this screen, and
   no "ask more"; both are in the phone frames' foot. The foot is therefore
   hidden at desktop width, so keeping is done where the desktop draws it — on
   the card and in the list.

The frame's strokes column (right, 640px) is frame 05's work and is not in this
slice; the desktop screen is one column-pair until it lands.

## The four other ways a card asks (2026-09-23)

Frames **11 Review typing retry**, **12 Review typing mobile**, **13 Review
listen choose mobile**, **14 Review dictation mobile**, **15 Review cloze
mobile**, **27 Review settings desktop** and **28 Review settings mobile** —
built and measured.

**A mode is offered only when the card can honestly be asked in it.** No
recording, no listening task, and none is synthesised to make one; no sentence
that really contains the word, no cloze; too few neighbours to tell apart, no
chooser. `product/recall-modes.js` decides that per card, and the choices are
deterministic, so a learner who answers "2" and comes back finds the same "2".

- **Distractors** are the learner's own due queue — words worth telling apart,
  not strings.
- **A typed answer** is judged exactly as the frame says: any of the answers
  written in the meaning counts, and the marks may be left off ("chấp nhận
  thiếu dấu"), with the full spelling shown afterwards. Two tries, then the
  answer.
- **What a task is worth**: right first time is `got_it`, right on the second
  try is `unsure`, not getting there is `again` — the three answers the
  scheduler already takes. No new grade, no new schedule.

**Review settings are device memory, by design.** The sheet writes
`newPerDay`, `limitPerDay` and which modes are on into the learner's own
device memory, beside the kept-language provenance that AGENTS "Architecture
holds" already names as device memory. No new column, no persistence decision
for learner-owned data, and the numbers are clamped on the way in and out.

Two things recorded rather than decided:

1. **"Nói to" is drawn and not operated.** The settings frame lists it; saying
   a word aloud is the Speaking capability's, which is another lane's work. The
   row is drawn with the frame's own off state and a title saying where it
   lives, and cannot be switched on here.
2. **Turning every mode off leaves the flashcard, which draws no settings
   control** (frames 08-10 draw none, and nothing was added). The second door
   the frames draw is the sliders control on **frame 30 Deck nothing due
   mobile**; until that frame is built, a learner who turns every mode off
   reaches the sheet again from the next session that sets a task.

## Nothing due, no network, and a set that would not load (2026-09-23)

Frames **30 Deck nothing due mobile**, **31 Review offline mobile** and **32
Deck load error mobile** — built and measured.

- **Frame 30** is what pressing "review" on a set gives when none of its words
  are due. Both numbers are counted, never estimated: what comes back tomorrow
  is the library's own `due_next_day`, and what is left to learn is this set's
  own arithmetic. It carries the **second door to the review settings** the
  frames draw (the sliders control), which the flashcard shell does not have.
- **Frame 31** is the sitting with no network. An answer that cannot reach the
  server **waits on the device**, in the order it was given, and goes up on the
  next connection — `product/review-queue.js`, with the rules a queue needs to
  be trustworthy: order is kept, a failure holds the ones behind it (they are
  later events in the same schedule), and a _refusal_ is dropped rather than
  retried forever. Every grade in the room now goes through that one place,
  flashcard and task card alike.
- **Frame 32** is the set that would not load, with the code a learner can
  quote. The old inline notice bar it replaces is deleted (rule 44).

One thing recorded rather than decided: **"Luyện tự do · không tính lịch"**.
The frame draws the button and names what it does; no frame draws the free
pass itself. It opens the set's own cards and writes nothing to the schedule,
which is what the label says. If the human wants a distinct screen for it, that
is a design decision, not an implementation one.

## Adding a word, and the set it lands in (2026-09-23)

Frames **22 Save to deck sheet mobile**, **23 Add word modal**, **24 Add word
mobile**, **25 Create deck mobile** and **29 Vocabulary empty mobile** — built
and measured.

**The set is a Thư viện của tôi collection** (D-074), of the `word` kind. No
deck model was rebuilt: a new set is `POST /api/library/collections`, a word
joins one by the library item that keeping it already made, and nothing about
a set is kept on the device. The gate refuses a second store.

The add screen fills itself from the catalogue as the learner types — the
frame's "đã điền sẵn" — and never overwrites what they have already written. A
word the catalogue does not know says nothing rather than accusing them of
inventing it.

Two things recorded rather than decided:

1. **No populated Vocabulary frame draws a way to add a word by hand.** The
   `+` and "Tự thêm từ" are on frame 29, the empty room, and that is where they
   are. Frame 23's own title — "Thêm từ vào Norsk hverdag" — says the other
   door is on a _set_, which belongs to the Thư viện của tôi frames, not to
   these. Until that door is drawn there, a learner with words reaches the add
   screen through the set picker on frame 22.
2. **Frame 25 draws a cover-colour chooser and nothing stores a chosen
   colour.** `library_collections` has `title`, `kind` and `language_code`; a
   colour is a column, and a column is a schema change under independent
   review. The set's cover is therefore the app's own, drawn from the set's
   identity exactly as every other cover in the room is drawn, and the chooser
   is not faked. **Proposed:** `library_collections.cover` (a short token, not
   a hex value, so the palette stays the theme's) — for the next review round.

## The room's own search (2026-09-23)

Frames **20 Vocabulary search** and **21 Vocabulary search mobile** — built and
measured, together with the **head frames 01 and 02 draw** and the room did not
have: its name, and the way into this search.

It is the room's search, not the shared top bar's. The top bar searches the
whole app; this searches words, so it is a view of this room and the top bar is
untouched, exactly as the human asked.

**Both halves are searched where they live.** The learner's own words go
through the read that already pages and searches them in the database. The
catalogue half is **new**: `VocabularyRepository.search_entries` and
`GET /api/vocabulary/catalogue/search`, which names its own bound (default 20,
never more than 50) and orders shorter matches first, because the shorter match
is the likelier word. The browser searches nothing and holds neither list
whole; the only thing the screen does with the query is pick it out inside a
word it has already been handed.

A catalogue word that the learner has already kept says so rather than offering
to keep it twice. A result opens the word all the way — which is one of the
three doors the deep desktop frame names.

## The word, heard where it is said (2026-09-23)

Frames **06 Vocabulary context clips** and **07 Vocabulary context clips
mobile** — built and measured, with the way in the desktop deep frame draws
("N clip có từ này trong ngữ cảnh · Xem ngữ cảnh"), which appears only when
there are clips.

**Every clip is a real moment in real media.** A clip is a timestamped segment
of a listening-catalogue lesson whose _own transcript_ contains the word — the
lesson's vocabulary list is not evidence that the word is in any particular
moment of it. Nothing is generated and nothing is stitched: the gate refuses a
voice import in that module, and a word the catalogue has never said has no
clips and says so.

`GET /api/library/vocabulary/{word}/clips` is a read over what the catalogue
already holds — the line, its pinyin, its translation in the learner's support
language, when it starts and ends, and the lesson's own rights-reviewed
playback reference. No store, no column. Playing one starts where the segment
starts and stops where it ends; an embed is not seeked inside, because the
rights review that admitted it did not admit that.

## Nét chữ, on the capability that was already here (2026-09-23)

Frame **05 Vocabulary strokes** — built, and the right-hand column of frame 26
with it.

**Correction.** An earlier note in this file said this frame needed stroke data
Orena does not hold, and proposed importing Make Me a Hanzi behind a rights
decision. That was wrong, and it was wrong because it was written without
auditing the code. The audit:

| What exists                                                                    | Where                                                       |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| The Make Me a Hanzi pack, vendored with `ARPHICPL.TXT` beside it               | `writing_coach/languages/chinese/stroke_data/` (2026-08-26) |
| Deterministic lookup: stroke count, paths in writing order, medians, glyph box | `writing_coach/languages/chinese/stroke_order.py`           |
| A route with an ETag and immutable caching                                     | `GET /api/chinese/stroke-order`                             |
| A client for it                                                                | `api.chineseStrokeOrder`                                    |
| The shared orthography contract, with `radical` and `components` facts         | `writing_coach/orthography.py`                              |

So the rights decision was taken long ago and nothing needed importing. What
was actually missing was a **surface**: the only thing any screen had ever
drawn from this capability was the stroke _count_ (`orthographyMarkup` in
`ui/vocabulary-card.js`). The paths and medians reached the browser and were
thrown away.

Frame 05 now draws them:

- **13 nét** — `stroke_count`.
- **Thứ tự nét** — five cells, each the character after the first _n_ strokes,
  built from the real paths; the strip always ends on the finished character.
- **Xem animation** — one stroke a time from the same paths.
- **Tô theo** — judged against the **medians**, which are the one piece of the
  data that says which way a stroke runs. Direction and order are what the
  frame's own note penalises ("sai hướng hoặc sai thứ tự thì nét rung nhẹ"), so
  a wobbly line still counts and a backwards one does not; drawing a later
  stroke is told apart from a scribble. Reduced motion gets the warning without
  the shake.

**One thing is still genuinely absent, and it is not stroke data.** The frame's
"BỘ THỦ · THÀNH PHẦN" cards want each part of the character and what it
contributes — 心 bộ thủ "tim, ý nghĩ", 相 âm "gợi cách đọc". The Chinese
adapter refuses to infer this by design, in its own words: it "does not infer
readings, radicals, components, or etymology; callers must supply those facts
with their own provenance". The shared contract already has `radical` and
`components` facts for exactly this, so the section is drawn from the catalogue
entry's orthography when a curator has supplied them, and is **absent** when
they have not — never guessed from the glyph. Filling them is a content task
against a contract that exists, not a schema or a rights question.

## A Deck is not a Collection (2026-09-23)

The human's decision, after `4f7b197` shipped frames 22–25 on the wrong domain:
**a Deck is a learning/review set that belongs to Vocabulary; a My Library
Collection only organises items inside My Library.**

That earlier pass used `library_collections` with `kind='word'` as the deck
store. Two contracts say independently that this is wrong:
`ORENA_COLLECTION_ARCHITECTURE.md` §1 calls Collection "a query/projection …
not a new authoritative copy", and `vocabulary_collections` says in its own
docstring that collections there are content read by many learners, with no
owner column.

**The correction, and where it stands.**

- `vocabulary_decks` + `vocabulary_deck_members` — proposed in
  `migrations/proposed/20260923_0014_vocabulary_decks.py`, **not applied
  anywhere**. Independent architecture review is required
  (`docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md`), and an implementer
  may not self-approve its own schema change.
- `DeckRepository`, `/api/vocabulary/decks`, and frames 22–25 are wired to the
  Deck contract. Until the tables exist the routes answer `503
decks_unavailable` and the screens say so. They are deliberately **not**
  wired back to `library_collections`: shipping the wrong domain again to keep
  a screen green would be the worse failure.
- A set holds a **reference** to the learner's saved word and no copy, and
  touches no review field — a gate and a test both refuse it.
- **The cover a learner picks now persists**, as a token (`sea`, `violet`,
  `ember`, `moss`, `amber`, `rose`) under a check constraint, never a hex
  value: `theme.css` stays the one owner of what a colour is.

**Open for the reviewer**, stated in the request: whether undo should restore a
restored word's memberships (the proposal's author prefers carrying them in the
undo payload, which is code, and did not build it because the choice is the
reviewer's), and whether the word-kind collections `4f7b197` created in the
sandbox should be carried over or left as My Library collections.

## Three smaller things finished with it (2026-09-23)

- **A set in My Library opens.** The rows have been drawn since the sets column
  landed and were never clickable; the read already existed. Opening one filters
  the room to its items, which is what a Collection is.
- **Free practice is real and cannot touch the schedule.** Three things were
  wrong: `practiceOnly` was set on the way in and never cleared, so a learner
  who used it once was silently no longer recorded in the _next_ real session;
  the grade buttons were drawn and did nothing; and nothing said the pass was
  not counted. Now the flag is a parameter of starting a session, the grades are
  not drawn in a free pass because they belong to the scheduler, and the bar
  says what the session is.
- **Radical and components have content with provenance.**
  `character_parts.json` (42 characters) fills the shared orthography
  contract's `radical` and `components` facts. It is labelled
  `structural-decomposition` — never etymology, which
  `ORENA_VOCABULARY_ARCHITECTURE.md` §4 requires to be told apart — and every
  declared radical is **checked against the verified stroke pack**: the
  radical's own stroke count must equal how many strokes the pack marks as the
  radical's. That check caught three wrong radicals in the first draft. 89
  characters of the static Chinese catalogue still have no curated parts, and
  their section is simply absent.

## The Deck landed, and Vocabulary closes (2026-09-23)

`migrations/versions/20260923_0014_vocabulary_decks.py` — **APPROVED** by
independent architecture review (Claude Sonnet 5 as Delegated Architecture
Reviewer, reviewed commit `9f94ad54`), human-authorized for **dev and sandbox
only**, and applied to the sandbox at `20260923_0013 → 20260923_0014`. The
full record is `docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md` §7.

Two of the reviewer's three P3s were taken before landing (`version >= 1`, and
the tie-break column in each index); the third — title uniqueness is not
case-folded — was left, because `uq_library_collection_title` has the identical
property and changing one alone would make two sibling tables disagree.

**P2, and the human's instruction, are done: undo restores deck memberships.**
Membership cascades with the word, so the sets are read _before_ the delete,
carried in the undo payload, and re-filed after the word is restored — the
word first, because a membership has nothing to attach to until the row is
back. No schema change. My Library may read decks and put a word back into one
for exactly this reason; it may not create, rename or delete one, and the gate
refuses that.

**The sandbox rows: nothing to convert.** Both word-kind `library_collections`
pre-date `4f7b197` by hours (06:14 and 09:03 UTC against a 17:16 local commit),
so they were made through My Library's own "new set" and are ordinary
Collections. Per the human: generic Collections stay Collections.

**Frames 22–25 verified end-to-end against the migrated sandbox**: a deck
created with a chosen cover persists it (`Tiếng biển:ember` read back from the
server); an unknown cover is refused `422`; keeping a word from the deep screen
opens frame 22 titled with that word, over the learner's real decks, and saving
files it — confirmed by reading `/api/vocabulary/decks?word=…` back. The
verification decks were deleted afterwards and the 3010 saved words are
untouched.

**Vocabulary is closed.** 30 of the 32 frames are built and run against real
data; frames 16 and 17 are the Speaking lane's.

One door is still the human's to draw, unchanged from the earlier note: no
populated Vocabulary frame draws a way to add a word by hand, so frames 23–24
are reached from frame 29 (the empty room) and through frame 22's set picker.

## Reading, slice A — the library (frames 01–02), 2026-09-23

Measured at 390x844 against the pinned frame (hash verified against `PINS.tsv`).
**Most of this surface already matched**, which the measurement is how we know:
title 24/800/-0.02em, chips 9x15 at radius 999 and 13.5px, cover 222 at radius
14, card title 15/700, meta 11px mono, grid gap 18, and — at phone width — the
two 42x42 radius-13 controls the mobile frame draws. The card template already
carries the author and the progress bar the frame draws; they are absent only
when the data is.

**One real defect, and it was a behaviour, not a pixel.** The library's control
is labelled "Nhập văn bản" / "Import text" and opened the _passage generator_:
a sheet asking which form, level and topic to **invent** a passage about, with
no field to paste anything into. A learner could not bring their own text in
from Reading at all. It now opens the learner's own import (`ctx.import` — a
title and a body, into device memory), which is what the label says and what
the frame draws. Asking for a generated passage keeps its own door
(`[data-read]`), so nothing was removed. A gate refuses the old wiring.

### Ownership audit, done before touching anything

| Owner           | Modules                                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Admin lane**  | `reading_admin_api`, `reading_content_engine`, `reading_source_import`, `reading_worker`, `reading_processing`, and `reading_content_repository` |
| **This lane**   | `reading_articles_api` (published only), `becoming_reading`, `/api/reading/session*`, and the learner half of `reading_library_api`              |
| **Shared file** | `reading_library_api` holds admin EPUB import _and_ the learner catalog/chapter reads. Nothing in it was changed.                                |

### Dependencies on the Admin lane — recorded, not worked around

1. **The frame's chips are `Tất cả · Sách · Bài báo · Tin tức`.** Books have a
   type. Published articles do not: `reading_articles` carries `topic` and
   `subtopic` but **no field that separates an article from a news item**, and
   the nearest column (`reading_sources.source_type`) is an ingestion concept
   two joins away that means something else. Adding one is a change to what
   ingestion records and publish approves, which this lane does not own.
   **Needed from Admin lane:** a learner-facing kind on a published article.
   Until then the room derives its chips from the data it really has, so the
   missing chips are simply absent rather than drawn over nothing.
2. **`/api/reading/articles` exists, is learner-facing, and the app never calls
   it.** Only the admin console reads the `/api/admin/reading/*` side. In the
   sandbox the route answers `503 reading_articles_unavailable` — the engine is
   not configured there — so wiring it in could not be verified end-to-end and
   was not done blind. It is the obvious next step once either the sandbox has
   the engine or the kind field lands.

### Not done, and why

The phone search that expands on focus, and the library's "load more", are
**already on the human's open-decision list** in this file and in
`CURRENT_HANDOFF.md`. They were left alone.

## Reading, slice B — Book detail (frames 03–04), 2026-09-23

The screen existed and was **richer than its frames**, which is the opposite of
the usual gap. Measured against both pinned frames, then brought to them.

**Deleted, because the source draws neither** (rule 44, and D-067 over D-060):
the four statistic tiles that all read "—" with a "not measured" note, and the
"similar level" shelf whose entire content was a sentence explaining it had
none. A panel whose only content is an apology for having no content is not a
panel. Eight copy keys went with them, in all three languages. D-060's rule —
keep the component, show the honest blank — predates 2026-09-21 and is void
where the design disagrees; `test_orena_shared_reading_library.mjs` was pinning
it and now pins the deletion instead.

**Kept, because frame 03 does draw it**: the words the learner saved from this
book ("BẠN ĐÃ LƯU TỪ ĐÂY"), and the book's own description.

**New, from data that already existed**: one meta line (chapters, and time
left), "n / t đã đọc" beside the chapter heading, and a duration on every
chapter row.

### The duration: a learner projection, not a column

The frames draw a time per chapter. `word_count` was already stored on the book
and on every chapter, and the product already had a reading pace for a learner
— `reading_processing.EN_WORDS_PER_MINUTE` (180) and `ZH_CHARS_PER_MINUTE`
(260), chosen deliberately slower than a native skimmer's. Only the learner
response was missing the derived field.

So `reading_library_api` gained `reading_seconds()` and `_with_reading_time()`
in its **learner half**: the pace constants are read, never redefined, so a
book and an article tell a learner the same thing about the same length of
text; nothing is stored; the repository is untouched; and a gate plus a test
both refuse the projection any reach into `asset_store`, `create_book`,
`UploadFile` or `_admin_guard`. **The admin EPUB import path and its failure
semantics are exactly what they were.**

### Cross-lane dependencies, recorded not worked around

1. **Level and form.** The frames draw "B1 · tiểu thuyết · 12 chương". The
   chapters and the time are there; `reading_books` stores **no level and no
   form**, and both are decisions ingestion and publishing make. The meta line
   therefore reads "12 chương · còn 22 phút" and says nothing it cannot.
   **Needed from Admin lane:** a level, and a form, on an imported book.
2. **Progress inside a chapter.** Frame 04 draws a bar and "còn 9 phút" on the
   chapter in progress. Device memory records which chapter the learner is in,
   not where in it, so the row shows the chapter's full duration and the
   "continue" affordance the desktop frame draws. Position within a chapter is
   learner state this lane could add later; it is not an Admin dependency.

### Verified

12 tests for the projection (pace not forked, Chinese counted in characters,
nothing to count is no duration, the repository's dict never mutated, the
import path never referenced). The screen rendered against a book shaped by the
contract: meta "6 chương · còn 56 phút", "2 / 6 đã đọc", rows "01 · … · 18
phút", tiles and shelf gone. Measured at 390: cover 106x144 at radius 13, title
21/800/1.2, byline 14.5, meta 11.5, chapter row 13x15 at radius 14, its number
mono 13 in a 20px column — all the frame's numbers.

The sandbox holds no books (import is EPUB behind the admin guard, which is not
this lane's), so this could not be exercised against stored data.

## Reading, slice C — the reader keeps its place (frames 05–06), 2026-09-23

Measured both pinned frames against the running reader. Most of the workspace
already matched: the hairline of the learner's place, the six-action bar on the
wide frame, the Từ / Ngữ pháp / Ghi chú panel, the word and sentence sheets
(frames 07–10, checked against the Quick Sheet and left alone — they were built
to it and nothing has drifted). What did not match was small and one thing was
missing entirely.

**The missing fact.** The reader measured how far into the chapter the learner
had read every time they scrolled — that is what the hairline is — and threw it
away on unload. So slice B's cross-lane note #2 ("position within a chapter is
learner state this lane could add later") is closed: `place` now carries an
optional whole `within`, clamped where every other kept figure is clamped. The
reader reports it only when the whole number moves **forward**, so rereading a
paragraph does not un-read the chapter, and only for a chapter of a book.

Book detail spends it: the row in progress says what is left of that chapter
("còn 9 phút") instead of its whole length, and the book's remaining time
subtracts the part already read. A chapter opened and not yet scrolled has no
`within` — that is "not measured", not 0%, and it is drawn as the chapter's own
length, the same as every chapter the learner has not reached.

**Brought to the frames:** the hairline is 3px, not 4px. The bar's meta line
says "chương 3 · còn 9 phút" — where this is, and what is left of it — where it
used to say how many words the text has; the phone frame has room for only the
time, so the chapter is put away there. `chapterLabel` is now the chapter
alone; `readerChapterOf` ("Chapter 2 of 3") went with the old line, in all
three languages.

**The phone bar is now the phone frame's** (it was the wide frame's, scrolling
sideways): five tiles of equal width, an icon over a 10px label, radius 14 at
48px, with the way on to the next chapter last and in the accent. Discussion
and "đọc tiếp sau" are drawn only in the wide frame, so they appear only there,
and each label the phone frame shortens has its shorter form in all three
languages. The phone's chapter dock was **deleted, not restyled** — neither
frame draws one; the bar's primary turns the chapter and the back arrow returns
to the book, where the whole list is.

**Verified** at 390×844 and 1920×1080, in all three interface languages:
rail 3px; five tiles Lưu · Nghe · Hiểu bài · Viết · Chương sau (Save · Listen ·
Check · Write · Next chapter; 收藏 · 朗读 · 理解 · 写 · 下一章), each 48px at
radius 14 with a 19px icon and a 10px label; six on the desktop with their long
labels; the foot row reads "34% · còn 9 phút". Book detail drawn twice against
a three-chapter book: with no measurement "02 Hai 30 phút" and "3 chương · còn
45 phút"; at 70% of chapter two, "02 Hai còn 9 phút" and "3 chương · còn 24
phút" — the frame's own figure. `test_orena_reader_place.mjs` pins all of it.

## Reading, slice D — the check answers back (frames 11–12), 2026-09-23

The two frames are one flow: a question with plain option cards, a line saying
it can be skipped and one button ("Trả lời"), and then the answer to **that**
question — the verdict, the lines in the passage that settle it, why — before
the next question is offered. The implementation was the D-059 quiz: an
invitation card, a rail, lettered options, every answer collected and sent as a
set, and only then a walk back through the verdicts with a running score.

**The backend need was real, and it is learner-side.** A verdict per question
means the server must score one answer as it is given: `grade_reading_answer`
and `POST /api/reading/session/{id}/answer/{index}`, returning the same result
shape one element of the set always had (both now build it through
`_question_result`, so the two cannot drift). It **records nothing** — the
attempt is still the whole set, written once through the route that always
wrote it, when the learner has been through every question. What is stored
about a learner's reading means exactly what it meant before. Four tests hold
that line, including "scoring one question writes no attempt".

**Deleted (rule 44):** the invitation card and its "n câu hỏi · không bắt
buộc", the progress rail, the lettered option marks, the question-type chip,
the running score and the claim under it, the "your answer" tag and the
paragraph number under the evidence. Fourteen copy keys went with them, in all
three languages. The check opens from the bar under the text, at question one.

**Built to the frames:** option cards at 17/18 in radius 15 with the chosen one
brighter and ringed; the verdict as a filled mark in semantic **ink** (never a
fill on the glass) beside "Đúng rồi" / "Chưa đúng"; the evidence quoted in the
paragraph it stands in, in the serif at 16.5/1.8, with the words themselves
marked in the success tint; the reason at 15.5/1.65; "Xem lại trong bài" (which
shows the words in the text and closes the check) and "Thảo luận" (which opens
the discussion the reader already has) at 50px; the primary at 54px.

**Verified against real data** in the sandbox — a generated session, four
questions, answered right and wrong: the verdict in #9EE6B4 / #F58A8A ink, the
evidence paragraph with its fragment marked, the Vietnamese reason, "Câu tiếp
theo" walking to question 2, and "Xem lại trong bài" closing the sheet onto the
marked words in the text. Sizes measured in place: 25/800/-0.02em question,
17/18 radius-15 options, 16.5/1.8 evidence, 15.5 reason, 13.5 skip line, 50px
quiet actions, 54px primary.

---

## The learner rail on the Platform Admin console (2026-09-23, DECIDED)

**Resolved by the human on 2026-09-23: the rail is removed from `#/admin`.**
Platform Admin is a full-width workspace inside Orena - not a learner room and
not a separate site - and it carries one named way back, "Back to Orena", in
its own header.

This matches `DESIGN_CONTRACT.md` rule 47, which gives the rail to Home,
Library, Vocabulary and Progress only, and the canonical Admin frame
(`Orena Admin Control Center.dc.html`), which draws no learner rail at all and
lays its tables out for the whole width.

Implemented in `static/orena/admin/admin.css`
(`body:has(#main[data-experience='admin'])` stands the shell down and sets
`--rail-width: 0`) and `static/orena/admin/shell.js` (the back link). The
console went from 885px of usable width to 1199px on a 1280px window.

The reader's precedent - a room may quiet the shell but never removes a
destination - is honoured by the back link rather than by keeping the rail:
Admin is not a learner room, and the one destination it needs is the way out.

## Speaking slice, measured (2026-09-23, `feature/speaking`)

Built on `Orena-Speaking.dc.html` frames "Speaking library", "Speaking workspace", "… mobile",
"Speaking · recording", "Speaking · char detail", "Speaking · free talk", read from the cache (the
design project could not be read in this session: `DesignSync` was not authorised). Open decisions are
S1-S13 in the register above.

- **Desktop 1920 (measured in the running app, computed style):** bar 84 / pad 0 36 / gap 18; name
  Nunito 24/800 -0.02em; where DM Mono 13 .60; streak 42 high, 14.5; panes pad 20 36 36, gap 22; task
  pad 40, gap 26, r20, ring .18 + 0 8 28 .42; result pane 640, r20; clip 560x315 r18 (clamped to 29dvh
  on a shorter window), play 86; badge DM Mono 11.5 .08em; line Noto Serif 36/600 lh 1.4; reading DM
  Mono 18 .04em .72; meaning 16.5 .60; mic 104, sides 56; hint 14.5 .60; head pad 24 28 gap 20; ring 92,
  number 27/800, count DM Mono 10; headline 23/800; metrics DM Mono 13 .75; body pad 22 28 gap 16;
  label 10.5 .14em; action pills 15/700 pad 13 18. Matches the frame after two fixes found by measuring:
  action pills were 400 (a `.sp-room button {font: inherit}` rule outranked them) and the back link .68
  instead of .70.
- **Phone 390x844, touch (Playwright, `hasTouch`, `isMobile`):** workspace, recording and char detail
  sheet as their frames; the recording level draws the frame's 34 bars; no horizontal overflow in EN,
  VI, ZH.
- **Flow checked in a browser** on the private sandbox :8013 (throwaway Postgres, migrations applied
  there): record (Chromium fake microphone) → processing → result → word detail, desk and phone, EN/VI/ZH
  interface over zh and en lessons; an old `#/encounter?…&intent=speaking|shadowing` link lands in the
  workspace on the line; Listening's line sheet "Shadow" opens it on the chosen line and back returns to
  the lesson. **No pronunciation provider was configured on :8013**, so the pronunciation route was
  answered in the browser test by a provider-shaped stand-in: this verifies the rendering and the
  lifecycle, not Azure. Azure itself is covered by mocked-response tests only.
- **Library and free talk, browser-checked** after the Docker engine came back (sandbox :8013 rebuilt),
  desk and phone with touch, VI/EN/ZH interface over zh and en: library chips only for real types
  ("Nhại theo clip", "Nói tự do"), 7 zh / 5 en cards, meta "nhại theo clip · HSK2 · 3 câu", rail on;
  free talk record → result with duration and comment, rail off, "Xem gợi ý sâu" sheet with the
  three kept actions. Recognition and coaching were browser stand-ins (no ASR/AI provider on :8013);
  evidence and the attempt record were the real routes. One fix from the phone check: the two side
  buttons no longer overflow 390px.
- **Deviation shared with the other libraries, not changed here:** the frame's desktop grid is four
  362px columns; the shared library (`media-library.css`, `#main > *` capped at 1480px) shows three at 1920. The phone library is the shared two-column grid, where the frame draws one large card then
  pairs. Both belong to the library template, not to Speaking.
- `scripts/test_m3_pronunciation_contract.mjs` is rewritten to `PronunciationResult` and passes (it
  held the D-065 "no score" report). Six `.mjs` gates fail locally on a clean `3bf2c3f` tree as well,
  with the same first assertion: `test_orena_admin_console`, `test_orena_admin_entry`,
  `test_orena_continuation`, `test_orena_product`, `test_orena_reference`,
  `test_orena_writing_workspace` - inherited, not this slice.

## Speaking, the re-pinned frames measured and run against Azure (2026-09-23, later)

Read at the source (DesignSync, 18 frames; `docs/design/canonical-ui/SYNC_2026-09-23.md`) and served
from the re-pinned cache to measure: frames "Compare with model" (+ mobile), "Lesson summary mobile",
"Shadowing mobile", "Free talk result" (+ mobile), "Speaking mic blocked / not heard / offline
grading mobile". The paragraph above ("no pronunciation provider was configured on :8013") is
superseded: the sandbox now runs the real providers (Azure Speech, Groq ASR, Gemini coaching), loaded
from the main checkout's `.env` by name, values never printed.

- **Differences found by measuring and fixed** (computed style / box, app vs frame):
  - Shadowing (07), phone: recording borrowed the plain recording frame (✕, "ĐANG GHI" pill, hint,
    no side buttons). It now keeps its own frame: back + title, mode switch, card, 22px to the
    headphones note, speed and again (50) either side of an 84 stop with the white `stop` glyph
    (Phosphor fill).
  - Compare (06), phone: the attempts list shrank to its content (`align-self: start` in a flex
    column); now the full 350.
  - Summary (05), phone: the body shrank to 384 (auto margins with `inline-size: auto`) and the side
    column to 79; now x 20 / 350 as drawn; the secondary action is primary ink, not white.
  - Free talk result (04): criteria rows 22 → 19 high (27 apart as drawn), labels .85 → .84
    (`--ink-84`); phone primary/secondary label sizes were swapped (now 15/800 and 14.5/700 primary
    ink); the top row 24 → 22; the phone-only fix card leaked onto the desktop.
  - States (09), phone: mic blocked and offline centred everything and put a 286 button inside the
    message; now the message is centred in the space above with 60 clear, the actions a foot bar with
    the full 350 button, no line count, the title on a 28 line, the text link a 24 target (WCAG 2.2
    minimum; the frame's line is 19). Not heard was a box inside the result card with a stray hint
    under it; now its own box.
  - Lesson name ink: primary in shadowing and the states, .9 in the workspace - as each frame draws.
  - A phone result card with no flagged word no longer says "tap a row".
- **Kept deviations, each recorded:** S14-S23 above (old free-talk actions, `say_again`, no
  progressive highlight, no loudspeaker detection, the countdown's place, "Thử lại" for "Mở Cài đặt",
  "under 80" → flagged lines, no written tone verdict, settings deferred, Traditional characters from
  ASR). The Vietnamese interface sets mono labels in Roboto Mono (DM Mono has no Vietnamese glyphs;
  `foundation.css`, D-061) - a documented fallback, not a difference.
- **Real end-to-end runs on :8013 (Chrome, fake microphone fed with real native speech):**
  - Scripted, 6 runs (desk 1920 and phone 390 with touch × zh-lesson/en-UI, zh-lesson/vi-UI,
    en-lesson/zh-UI): Azure 200 on every take; listen take 96-99, 6/6 passed; word detail with the
    measured "yours" curve (zh); compare with 40 model bars and 40 take bars and both contours (zh);
    shadowing lag 0.5-0.6 s; every run, desk and phone, reaches the lesson summary; no horizontal
    overflow, no page errors.
  - Shadow restart (phone, zh/vi): countdown visible; again mid-take → idle → recording; speed
    mid-take → 1× and recording again; only the final take is sent (one Azure call), graded 99.
  - States A/B/C in vi, en, zh, desk and phone: blocked → listen-only; not heard → skip on the right;
    offline → kept, graded when back online, the offline screen lifted.
  - Free talk, 6 runs: Groq ASR + Azure unscripted (fluency 77-89, pronunciation 81-92) + Gemini
    coaching; grammar and vocabulary 0, ring 0 (no overall); `say_again` pure target language
    ("其实我是英国人。你呢？"); "Nói lại câu sửa" opens the workspace on that line with no clip.
- **Gates (local execution):** every `.mjs` gate in `ci.yml` except the six inherited ones (same first
  assertion on a clean `3bf2c3f`); ESM graph OK (107 modules); memory and architecture validators and
  the Python contract scripts OK; `pytest -q test_app.py tests` in the application image, SQLite
  backend: 1775 passed, 118 skipped. `test_orena_learning_stage.mjs` asserted the deleted four-ways-in
  landing; its Speaking section is retargeted to the library that replaced it, and the landing's
  styles and copy are deleted.

## Speaking, second review run on `a5c7172` (2026-09-23, D-077)

Everything below ran on `a5c7172` (the code under review; the commit after it is documentation only),
with the sandbox :8013 recreated from that tree and the rotated Azure key. No result from an older
commit is reused.

- **Credentials.** The old Azure key is in no Git object (all refs and stashes), neither checkout,
  no scratch file and no sandbox log; its only copy is the Claude Code transcript of the session
  where the probe printed it (the key is revoked). The current key appears only in the main
  checkout's `.env`. Checked by count, no value printed. Cause fixed in `f3eac72`.
- **Scripted, 6 runs** (desk 1920 / phone 390 touch × zh-en, zh-vi, en-zh): Azure 200 on every
  take; 99 / 99 / 96 with 6/6 passed; compare 40 + 40 bars, contours for zh only; shadowing lag
  0.5-0.6 s with speed and again live during the take (56 / 50) around a 104 / 84 stop, no pill;
  every run reaches the lesson summary; no overflow, no page error.
- **Shadow restart** (phone): countdown shown; again and speed restart the take; one assessment
  sent for three starts, graded 99.
- **States, 18 checks** (vi, en, zh × desk, phone): A blocked → listen-only; B silence → not heard,
  skip on the right; C offline with real speech → kept, and graded when the network returns
  (72-76; the looping fake microphone starts mid-line).
- **Free talk, 6 runs** (zh-vi, zh-en, en-zh × desk, phone): transcribe, pronunciation, coaching and
  attempts 200; fluency 86-89, pronunciation 88-92, grammar and vocabulary 0, no overall; no row
  of old actions on the result; "⋯" opens the deep-ways sheet with the three ways inside the
  viewport; "look closer" opens its sheet; "say the corrected line" opens the workspace on that
  line with no clip.
- **Gates (local execution):** `pytest -q test_app.py tests` in the application image, SQLite
  backend: 1787 passed, 118 skipped; every `.mjs` gate in `ci.yml` passes except the six inherited
  ones (same first assertion on a clean `3bf2c3f`); ESM graph OK (107 modules); memory and
  architecture validators and the Python contract scripts OK.

## Speaking under D-078 (rule 49), measured on `4d83552` (2026-09-23)

- **Viewport law, real takes:** 12 Speaking screens (workspace idle, recording, result; compare;
  shadowing; summary; a 32-character line idle and scored; its word sheet; free talk idle, spoken and
  its result) at 1920x1080, 1440x900, 1366x768, 390x844 and 360x740, in VI, EN and ZH: 180 of 180
  checks with no page scroll, no horizontal overflow, no clipped content, primary controls inside the
  viewport. The long regions scroll inside (word list up to 572/1915px on a desk, the phone card's
  flagged words 289/924).
- **Long content:** a 7-line lesson's summary, five real takes on one line, a 25-second free-talk
  take: 16 of 16. **Stress** (the DOM filled past anything a take produces today: 28 lines, 15
  attempts, a long transcript): the page never grows, the region scrolls, the actions stay in view;
  on a 1920x1080 desk the long transcript still fits without scrolling.
- **Old routes, in a browser (desk, phone):** `#/practice`, `?intent=shadowing`, `?intent=dictation`,
  `?intent=writing` and old encounter links to shadow or speak a lesson land in the current flows,
  with a mutation observer seeing no old screen on the way; Home, Library, the Speaking and Listening
  libraries, Progress and History link to no retired address: 24 of 24.
- **Functional E2E again on this HEAD:** scripted 6 runs (Azure 200, 96-99, compare, shadowing with
  live speed/again, summary), shadow restart (one assessment for three starts), states 18 of 18
  (offline takes graded when back: 71-99), free talk 6 runs ("⋯" sheet with three ways; the
  corrected line appears whenever the coaching gives one in the learning language).
- **Gates (local):** pytest 1787 passed, 118 skipped; every CI `.mjs` gate passes but the six
  inherited ones (same first assertion as a clean `3bf2c3f`); the new
  `test_orena_legacy_routes.mjs` passes; memory and architecture validators OK.
- **Not re-measured here:** Reading, Listening, Dictation, Writing and Vocabulary workspaces. Rule 49
  binds them; each owner measures them against it (D-078).

## Language layers (D-079) and the merge-blocker run on `4540efb` (2026-09-24)

- **Root cause of the mixed screens:** `app.js` derived the interface language from the support
  language (`ctx.ui = uiLocale(ctx.support)`) and booted from a device cache of the support language,
  so a page opened with one support language kept that chrome while guidance and generated text
  followed the account's newer support language (changed, here, by test runs on the shared sandbox).
  Now `static/orena/product/languages.js` resolves interface, support and target from their own
  sources; `scripts/test_orena_language_layers.mjs` locks it (fails on the old `app.js`).
- **In a browser, cases A/B/C** (desk and phone; boot with a stale `orena.support` cache, reload,
  profile load, a real preference change through Profile, navigation, the Speaking workspace with a
  real Azure take, the word sheet on desk and phone, a mid-visit support change): 92 of 92.
- **Found and fixed on the way:** Profile's setting rows did not open the preferences (their buttons
  were drawn after the shell bound its handlers); one delegated listener now serves every way in.
- **Same HEAD:** viewport 180/180 (VI/EN/ZH x 5 sizes x 12 screens), long content 16/16, stress 14/16
  (the two 1920 lines are a transcript that fits without scrolling), legacy routes 24/24, scripted 6,
  shadow restart, states 18/18, free talk 6; pytest 1787 passed / 118 skipped; CI `.mjs` gates pass but
  the six inherited ones; Grammar's route (`#/practice?intent=grammar`) renders, back link Home.
- **Still open:** S24 (Grammar's official way in) for the human; AUDIT-1b (static guidance outside
  Speaking still reads the interface pack); storing the interface language on the account (gated
  migration).

## Shared overlays (D-088 frames 53/57/62/63), Wave B first phase, 2026-09-28

Built `static/orena/screens/quick-sheet/` (`openWordSheet`/`openSentenceSheet`), `screens/mic/`
(`openMicState`/`micGate`), `screens/lesson-complete/` (`openLessonComplete`). Gaps found while
wiring these to the real backend, for the ten workspace agents that call them and for the human:

- **No backend representation for a saved sentence/highlight.** The Sentence Quick Sheet's frame
  (57) draws a "Save highlight" bottom action (`toggleSave("highlight", qss.t, null)` in the
  source); the real `POST /api/library/items` only accepts a content-domain `kind`
  (`word | grammar | reading | listening | writing | speaking`, one row per content item a learner
  is engaged with, `writing_coach/becoming_library.py` / `static/orena/ui/collection.js`'s own
  `ITEM_KIND` map) - there is no grain for "this one sentence inside that content." **Not built**
  (rule 40): the Sentence Quick Sheet ships with "Ask deeper" only in its bottom actions, no "Save
  highlight". Needs a product/schema decision (a new item kind? a sub-row under the content item?)
  before it can be built for real. The per-word saves inside the same sheet's Vocabulary tab are
  unaffected (real, `POST /api/library/vocabulary`, same as the Word Quick Sheet).
- **No "mark as known" action.** The Word Quick Sheet's mastery row (frame 53, `qsHasWC` branch)
  draws a text "Mark as known" toggle (`onKnown`) beside the mastery bars. The real vocabulary
  contract only exposes incremental SRS grading (`POST /api/library/vocabulary/{word}/review
{result: again|unsure|got_it}`, `writing_coach`'s own schedule), which advances a word one step,
  never jumps it straight to the mastered/"Available" stage. **Not built** - no safe real mapping
  from a single tap to "known" exists without inventing a scoring rule the backend does not have.
- **`deeper.whyHere` needs a provider.** The Word Quick Sheet's "Why here?" row is always drawn
  (measured live against the source: it shows a generic fallback prompt, "Ask Orena for the reason
  it appears here," when no real reason is prepared yet, rather than being hidden - a real finding
  from driving `window.__orenaLive`, not in the static frame export alone) - built that way here.
  With no AI provider key in this sandbox, `deeper.whyHere`/`judgement_reason` is always empty, so
  every word currently shows the fallback; verify the real-reason path once a provider is
  configured.
- **`source.title` is caller-supplied, optional.** The frame's "Source sentence · {{time}}" binding
  turned out, measured live, to show the _content's title_ (e.g. an article's), not a timestamp as
  the static export's own placeholder name suggested. `openWordSheet`'s `source` therefore accepts
  an optional `title` field; a caller with a real one (content_id already resolves to a title in
  most rooms) should pass it, or the sheet falls back to the bare "Source sentence" label - never a
  guessed title.
- **`screens/word/model.js#restorePayload` is missing `next_review_at` (and the newer
  `entry_identity_key`/`entry_id`/`reading_key` fields `RestoreVocabularyIn` also accepts,
  `writing_coach/becoming_library.py`).** Found while writing this pass's own equivalent
  (`screens/quick-sheet/model.js#wordRestorePayload`, which includes all of them) - an Undo after
  unsaving a word from Word Detail currently restores without its schedule's `next_review_at`,
  losing the due date on undo. **RESOLVED (2026-09-28):** `restorePayload` now carries every string
  field `RestoreVocabularyIn` accepts; `scripts/test_orena_screen_word.mjs` reads the model's fields
  from the backend source and fails if one is missing.

## Check Understanding / Discussion / Reading Transfer (D-088 frames 20/46/39), Wave B, 2026-09-29

Built `static/orena/screens/check/` (route `checku`), `static/orena/screens/discussion/` (route
`discussion`) and `static/orena/screens/reading-transfer/` (route `rtransfer`), all registered in
`shell/screens.js`. An earlier pass of this section (2026-09-28) left Reading Transfer on Coming
soon on the ground that no backend exists for it; that is corrected below - the honest coaching
endpoint the other Speaking/Listening rooms already read serves it.

- **RT-1. Reading Transfer stands on the coaching endpoint, and the frame's two verdict tiles are
  replaced by its real lists.** `POST /api/dictionary/spoken-response`
  (`writing_coach/media_interaction.py#coach_spoken_response`) takes what the learner wrote or said
  and a `situation` (what they were asked to do) and answers `carried` / `landed_differently`
  (each item a quotation of the learner's own words with its reason, the backend drops any quotation
  that is not in the transcript), `another_way`, `next_attempt`, `say_again`, `available`. The screen
  sends the mode's plain-English task plus the source sentence as the `situation`, and draws: the
  learner's answer, two tiles - "What carried" and "What would land differently" (a tile with no
  points is not drawn) - and the frame's "One useful improvement" callout = `next_attempt`
  (falling back to `another_way`, nothing when both are empty). **Not drawn:** "Meaning preserved?"
  and "Missing important idea?" - the frame's own scoring is a client-side content-word overlap and an
  answer-length check, the endpoint's own prompt forbids it to "score, grade or estimate a level",
  and no backend measures meaning preservation, so any verdict there would be invented (rule 40).
  `say_again` is not drawn either (the frame has no such element); `another_way` is drawn only as the
  callout's fallback. The tiles stack on a phone (real points are quotations with reasons, not the
  frame's one-word values - a recomposition, recorded).
- **RT-2. What the frame's verdicts would need.** A purpose-built, versioned grading contract that
  measures rather than coaches: source sentence + mode + answer -> meaning preserved
  (yes / partly / no), the important idea missing, one improvement - server-side, with the
  deterministic part (a copy that is not a paraphrase) separate from the model's judgement. Until it
  exists the two tiles are coaching lists, honestly labelled.
- **RT-3. Nothing is recorded.** There is no Reading Transfer evidence contract: a check writes
  nothing to the learner's record, Progress does not count it, and "Finish" only leaves. (Check
  Understanding is the one Reading activity that writes evidence.)
- **RT-4. The text must be in the learning language.** The endpoint answers 409 unless
  `source_language` is the learner's _current learning language_; the screen passes it from the
  learner's context, never from the text. A text in another language fails with the generic
  "Coaching isn't available right now" toast - the frame draws no distinct state for it.
- **RT-5. Which sentence.** No "where I stopped reading" signal reaches this screen, so it starts at
  the first _workable_ sentence of the text (at least 4 words, or 6 Han characters for Chinese; at
  most 400 characters so it fits the request's `situation` beside its task) and "Another sentence"
  moves on in reading order, wrapping. The frame starts at a fixed demo index. With a single workable
  sentence "Another sentence" is not offered (it would only repeat Retry).
- **RT-6. Observed on the isolated stack.** With `target_language: vi` the local model
  (`ollama` / `qwen3:8b`) returned its `why` lines in English. A model-following quirk, not a shape
  difference - the screen marks the coach's lines with the learner's support language and does not
  second-guess it.
- **Check Understanding's grading is off by default, and the disabled state must be honest.**
  `POST /api/reading/practice/sets/{id}/questions/{id}/grade` and `POST
/api/reading/practice/attempts` both 503 (`reading_submit_disabled`) unless
  `ORENA_READING_PRACTICE_SUBMIT=on` (`writing_coach/reading_practice_api.py`) - confirmed live on
  the isolated stack, where the flag is unset. Rather than let a learner tap an option and hit a
  503 mid-quiz, the screen reads the `submit_enabled` flag `GET
/api/reading/practice/articles/{id}` already returns alongside the question set, before showing
  any interactive card, and shows the honest "Practice answers aren't being saved yet" empty state
  instead when it is false. Separately, **no article in this sandbox has an approved comprehension
  set at all** (`scripts/fixtures/api/reading_practice_article_set.json` - the real, captured 404
  every article currently answers), so the interactive quiz/grading/score-summary path is exercised
  against a set built from `reading_evidence_repository.py`'s own serializer shape
  (`scripts/fixtures/api/reading_practice_article_set_approved.json`,
  `reading_practice_grade_result.json` - both "built, not captured", per the fixtures README) with
  only the network answer substituted in a real browser; re-verify once an approved set and
  `ORENA_READING_PRACTICE_SUBMIT=on` exist on a runtime that has both.
- **A question's evidence may be empty, and is never quoted by the backend.** `evidence_fragment` is
  the stored `evidence_text`: words copied exactly from the article body
  (`reading_evidence_repository.py` verifies `body[evidence_start:evidence_end] == evidence_text`),
  so it carries no quotation marks of its own (the screen adds the frame's curly ones), and it is `""`
  for a `main_idea` / `authors_purpose` question that has none - the evidence block and "Show in
  text" are then not drawn. The hand-built fixture of the earlier pass wrongly gave the fragment its
  own quotation marks (two layers of quotes on screen); corrected.
- **Check Understanding's "Go deeper" chips only include Discuss/Reading Transfer.** The frame's
  `cuDeeper` list (D3 §2.4) is inferred, not specified, to also cover "review saved words" and
  "next chapter" - neither has a real per-document data source this screen can read honestly (a
  saved-word count scoped to _this_ document does not exist anywhere, the same absence N-10/N-23
  already name for a related concept; a book chapter's own "is there a next one" needs the book's
  chapter list). Left out rather than shown with a guessed destination (rule 40).
- **Check Understanding's "Show in text" has no addressable evidence location.** The frame's own
  action (`cuShowInText`, D3 §2.4) returns to the Reader and opens the Sentence Quick Sheet on the
  evidence sentence; the Reader (now built, `screens/reader/`) accepts no anchor for a sentence, and
  the backend stores the evidence as a character span (`evidence_start`/`evidence_end`) that
  `GET /api/reading/practice/articles/{id}` does not return. Built conservatively: the button opens
  the Reader for the same text, without scrolling to or opening the evidence sentence. Needs the span
  on the served set and an anchor the Reader accepts.
- **Discussion's source-kind mapping is a judgment call, recorded, not resolved by any spec.** The
  backend's real source kinds (`writing_coach/persistence/discussion_repository.py` `SOURCE_KINDS`:
  `story | media | reading_session | book_chapter`) were written for the old content model; the new
  "<kind>:<id>" content-id scheme every screen shares has no `article` kind. This screen maps an
  article or a learner's own imported text to the generic `story` kind (the same fallback
  `static/orena/ui/discussion.js#discussionSource`'s old mapping used for anything it did not
  special-case) and a book chapter to `book_chapter` with source id `"<bookId>:<chapterId>"`. This
  is the conservative reading of the existing enum, not a new endpoint or schema need - flagged so
  a reviewer who expects a dedicated `article` kind knows why there isn't one.
- **Discussion: the frame's first Orena bubble is dropped (rule 50).** The design seeds every new
  thread with an Orena message ("I'm attached to “{title}”. Ask what a part means, why the author
  says something, or how you'd interpret it - the thread stays with this text."). It restates the
  header's own subtitle and the five starter chips, so a new thread shows only the chips and the
  input bar. (The earlier pass recorded this as "the frame draws none"; the frame does draw it, and
  the drop is a rule-50 decision, not an absence.) A human decision may reverse it.
- **The isolated stack answers real AI calls** (local model, `ollama` / `qwen3:8b`, roughly 2-40 s a
  call): `POST /api/texts/discussion/turns` and `POST /api/dictionary/spoken-response` both succeed
  there, which supersedes this section's earlier note that they always 503. Real payloads are now
  captured in `scripts/fixtures/api/` (`text_discussion_thread.json`,
  `text_discussion_turn_response.json`, `spoken_response.json`); the "built, not captured"
  Discussion thread fixture is replaced.
- **Screen-level: a route's own height rule must not apply to an empty screen element.** Each of
  these three screens needs the router's `.o-screen` to have real height (a percentage height only
  resolves against a sized ancestor). Scoped by route id, the rule made the still-empty element
  fill the viewport while the text loaded or after a failed load, pushing the router's loading
  skeleton and load error (appended after it) out of the viewport - a blank screen. Scoped with
  `:has(> .s-...)` (as the Orena home does) it applies only once the screen has mounted. Verified:
  skeleton and Back / Retry visible at 1440x900 and 360x740 on all three routes.
- **For the lead (not in this pass's files):** `kit/html.js` renders `false` as nothing, so
  `aria-pressed="${flag}"` / `aria-selected="${flag}"` becomes an empty attribute when the flag is
  false, which is not valid ARIA. Most screens already write `'true' : 'false'` or `String(flag)`;
  as of 2026-09-29 these still build it bare: `screens/compare/screen.js:322,333,371,501,518`,
  `screens/quick-sheet/sheet.js:332`, `screens/speak/screen.js:249,328`. A kit-level fix (stringify
  a boolean in an `aria-*` position)
  would close it everywhere. Also: `kit/base.css` `button:disabled { background: ... !important }`
  overrides any state colour an inline style gives a disabled button (Check's graded options lost
  their green/red that way) - a control that carries a verdict look must use `aria-disabled`, not
  `disabled`.

## Writing / Compare Versions (D-088 frames 18, 61, 19; 37, 38 left unbuilt), Wave B, 2026-09-28

Built `static/orena/screens/writing/` (routes `writing` `#/write`, `writingDraft` `#/write/:id`;
frames 18 Writing + 61 Prompt Setup, the latter a sheet, no frame draws it as its own route) and
`static/orena/screens/writing-compare/` (route `wrcompare`, `#/write/:id/compare`; frame 19), both
registered in `shell/screens.js`. `rewrite` (`#/rewrite`, frame 37 Context Rewrite) and
`timed-writing` (`#/timed-writing`, frame 38 Timed Writing) were **not** built - see below.

- **Context Rewrite and Timed Writing have no real backend at all**, confirmed by a full read of
  `infrastructure/api.js` and a grep of `app.py`/`writing_coach/*` for anything matching either
  drill's shape. Both frames' underlying logic in the current app is **entirely client-side**: the
  old prototype's `cwSubmit`/`twSubmit` (state script) grade with regex heuristics
  (`must`-pattern arrays, a hand-rolled `regOf()` register classifier) against a **hardcoded**
  core message ("I can't make it.") and three hardcoded audience contexts / a hardcoded 3-prompt
  bank - sample content per D-068, not data. `POST /api/tasks/generate` generates a single essay
  prompt (`TaskGenerateIn`: task_type/topic/target_cefr/word_target), not a message-to-preserve
  plus N audience-register variations, and grades nothing; `POST /api/evaluate`/`/api/improve` are
  Writing's own full-draft endpoints, not a per-sentence "intent preserved? / register fit /
  politeness / clarity" or "communication worked? / register fit" contract, and repurposing either
  for a different, un-designed grading shape is a product decision this pass has no standing to
  invent. Per the Wave B brief's own instruction for these two ("real backends only, else Coming
  soon"), both routes were left **unregistered** in `shell/screens.js` - `shell/router.js
#loadScreen`'s existing, already-tested fallback serves the design's own Coming soon screen,
  titled from each route's own `crumb` (`contextRewrite` / `timedWriting`, both already real
  `copy/shell.js` keys - no new key needed). No `screen.js`/`model.js`/`copy.js`/test gate was
  written for either folder: there is no real behaviour to implement, and shipping an interactive
  drill scored by a client-side heuristic is exactly the invented-behaviour rule 40 forbids. Needs
  a real single-sentence/short-response grading contract (register/politeness/clarity for Context
  Rewrite; a timed "did this land" judgement for Timed Writing), server-side and versioned, plus a
  real content source for the core message/contexts and the timed prompt bank, before either can be
  more than Coming soon.
- **A finding's `priority` is real, but this build only ever marks one "high" per essay.**
  `GET /api/essays/{id}` (`app.py#row_to_dict`, `detail=True`) computes
  `"priority": "high" if index == 0 else "medium"` - i.e. exactly the _first_-listed finding, never
  more than one, regardless of how severe the others are. The Writing screen uses this real field
  as-is for the frame's Priority/Other split (rule 40: use the real signal, do not re-derive a
  better one client-side) rather than inventing its own ranking - but this means "Priority issues"
  will show at most 1 item today even when the frame's own placeholder count suggests up to 3.
  Needs a real multi-issue severity ranking server-side (`writing_contract.py`/the evaluator
  itself) if more than one finding should ever be able to surface as priority.
- **Register and Target length (Prompt Setup, frame 61) have no field of their own in `EssayIn`**
  (checked in full: `prompt`, `text`, `target_cefr`, `writing_mode`, `writing_context`
  {topic_id/length_id/prompt_id/prompt_text/journal_context}, `parent_essay_id`,
  `practice_context`, `learning_language` - no register, no word-count target). An earlier pass
  folded the pick into `writing_context.journal_context` as a "real-effect note"; re-reading
  `evaluate_with_ai` (`app.py`) end to end during finishing found that function never reads
  `payload.writing_context` at all - only `prompt`, `text` and `target_cefr` reach the evaluator - so
  a `journal_context` note would have been silently discarded server-side and would only have looked
  like an effect. The finished build (`model.js#reviewPayload`) sends only the three fields the
  evaluator actually reads; Register and Target length stay real, visible state for the pieces this
  screen is open on this visit (the header meta line, the setup sheet's own pills, an in-memory
  `intentions` map keyed by draft/essay), never sent to the server and never claimed as an effect on
  the review. Nothing is persisted across a reload (no device-memory or server field exists, and
  AGENTS.md §7 reserves new persistence decisions for learner-owned data). Needs a real
  `EssayIn` field (and an evaluator that reads it) before Register/Target can affect a review, or a
  product decision to persist the pick without one.
- **"Writing mode" (which of Prompt / Free Writing / Your Topic / Respond to Content / Context
  Rewrite / Timed Writing an essay started from) is not persisted at all** - `create_essay()`
  (`app.py`) never writes a `writing_mode` column, so `GET /api/essays/{id}` cannot answer it. The
  frame's own header meta line reads `Prompt · {{ wrLevel }} · {{ wrRegister }} · ~{{ wrTarget }}
words · {{ wrVersionLabel }}`, where the literal word "Prompt" appears to name the entry mode,
  not a bound value; with no real field to bind it to, this build's meta line omits that word
  entirely rather than show a permanent, possibly-wrong "Prompt" label on every piece regardless of
  how it was actually started.
- **"Related grammar" and W8B "Practice this" are both left out of the finding detail, for two
  different reasons.** An earlier pass built a real "Related grammar" chip from `grammarRef`
  (`GET /api/essays/{id}/review`'s per-issue R5 concept link, `writing_contract.py`), opening
  `#/grammar?id=...`. R5 is being retired (human decision, 2026-09-28) and Grammar Lab will own
  grammar content under a `GRAMMAR_CONTENT_CONTRACT.md` not yet written, so the finished build reads
  no `grammar_links`/`grammarRef` at all and shows no "Related grammar" affordance - per the Wave B
  instruction to build no new R5-specific grammar rendering or reads. "Practice this" (a targeted
  drill launched from one finding) was already unbuilt before that decision: the backend has the
  natural primitive (`GET /api/grammar/{grammar_id}/practice`, confirmed unused by any frontend
  code), but no route or screen exists to receive it, and none of this pass's five frames draws what
  that screen looks like. The finding-detail action row is Apply / Ask deeper only. Needs Grammar
  Lab's contract before either affordance has anywhere real to point.
- **W8A "Kept Review" has no list of its own anywhere in the design export** - only the inline
  Keep/Unkeep toggle on the review card the Writing screen already has (wired to the real,
  previously-unused `POST`/`DELETE /api/essays/{id}/keep`). A "kept reviews" browsing screen (the
  spec names it; no frame was captured for it in this pass's scope) is not built.
- **Register exploration (`ui/registers.js`, `POST /api/dictionary/registers`) has no home in any
  of this pass's five frames** - confirmed absent from `18-Writing.html` (no "explore other
  registers" affordance is drawn anywhere the review or the editor). Not carried into the new
  screen; the real backend endpoint remains unused. A product/design decision, not resolved here.
- **Compare Versions' summary line shows only the Grammar dimension's movement, matching the frame
  literally.** An earlier pass repeated the delta card once per scored dimension (naturalness,
  grammar, vocabulary, coherence), reasoning that hiding three other real, measured movements read
  as closer to a rule-40 violation than following the sample literally. On finishing, `19-Compare-
Versions.html` was re-read against that choice: the frame draws exactly one summary line with the
  literal word "Grammar" typed in - not a name-bound repeating card - so the finished build
  (`writing-compare/model.js#mapCompare`) reads only `dimensionDeltas`' `grammar` entry and drops the
  rest, matching rule 43 (nothing the frame does not draw) instead of rule 40's "show every real
  number" reading. The other three dimensions' real deltas remain unused by this screen. Reversible
  in one place (`model.js#mapCompare`'s `grammar` line) if showing every dimension is confirmed
  intentional instead.
  **Answered 2026-09-29 (D-098): follow the frame** - one Grammar line, as built; closed.
- **Compare Versions' summary line's "range" (CEFR band) delta is now shown for real, when both
  sides have one.** `RevisionCompare` itself carries no `app_cefr`/range and no id for the earlier
  revision, but the _current_ essay's own `GET /api/essays/{id}` answer carries a `revisions[]` list
  (id + revision_no + created_at) for the whole series, including the earlier one being compared;
  the finished build (`writing-compare/screen.js`) reads the earlier revision's id off that list
  (`model.js#revisionIdOf`) and fetches its own `GET /api/essays/{id}` for its `cefr_estimate`, then
  pairs it with the current essay's own range. The line is shown only when both sides answered a
  real estimate; when the earlier fetch fails or either side's range was too thin a sample to state,
  the range half of the line is simply omitted (rule 40), never a placeholder.

## Onboarding (D-088 Onboarding.dc.html frames 01-05), Wave B, 2026-09-29

Built `static/orena/screens/onboarding/` (route `welcome`, `#/welcome`, bare - no rail, top bar,
phone header or bar), five steps: Welcome, Account, Languages, Level, Meet Orena. Reviewed once,
then fixed against that review (independent review P1 and every P2 closed; see the dated "Fixes"
section of `SCRATCH/reports/onboarding.md` for the full account). Two human gates were respected,
not worked around:

- **Production auth is a human gate.** The app requires sign-in before `/next` is ever reached, so
  Account shows the identity already established (name, avatar/initial, email when the account has
  one, "Signed in with Google" / "on this device") with only Continue - not the frame's credential
  form (create/log-in tabs, Google button, name/email/password, terms line), which this build cannot
  show for real. No frame draws the identity card built here (it cannot be measured against the
  source); it is a recomposition in the frame's own card language, not an invention of new
  behaviour (rule 43/50 - its only action is Continue).
- **`declared_level` is learner-owned data with no schema yet** (`writing_coach/account_profile.py`:
  `stored=False`, AGENTS.md §7 "Architecture holds" reserves new persistence/schema decisions for
  learner-owned data). No backend storage or migration was added for this unit. The Level step's
  Continue still PATCHes a CEFR pick (it answers 501 "not_yet_stored" - a documented, non-blocking
  gap, tracked as **SH-2**) but never an HSK pick (the field's `allowed` tuple is CEFR-only, so an
  HSK code would 400 on every attempt, forever - not sent at all, fixed in the review pass). The UI
  is honest about this: the pick is real state for this visit (the shell's in-memory `level`, Meet
  Orena's own line) and is never shown as if the server had saved it; a reload restores the step and
  the unsent pick together (session-only, `sessionStorage`), never a completion flag.

Other gaps, each already filled the conservative way (rule 40) rather than guessed:

- **No placement check exists anywhere in the backend** (no items, no scoring). The frame's frame 04
  draws a 5-question placement check with hand-authored sample questions (the prototype script's
  `QS`); shipping those would be invented pedagogical content. Only the frame's own `noScore` branch
  is built - "Choose your level", the CEFR/HSK grid, real standard frameworks. **Question for the
  lead:** build a real placement-check backend (items + scoring), or keep the self-pick permanently.
  **Answered 2026-09-29 (D-098):** keep the self-pick; a placement check is deferred.
- **Entry routing and the declared level (2026-09-29, D-098, open for the human).** The human's
  rule: `/next` opens `#/welcome` when the profile has no learning language **or no level**, Today
  otherwise, with no new stored field. Built: `shell/routes.js` `entryRoute` sends the empty address
  to Welcome when the server answers `exists: false` or names no learning language. **Not built,
  the level half:** `writing_coach/account_profile.py` declares `declared_level` with `stored=False`
  (CEFR values only; an HSK pick is never sent), so every learner reads `declared_level: ''`, and the
  rule as written would send every learner to Welcome on every visit. Storing it is new learner-owned
  persistence (AGENTS section 7 hold). Options for the human: (a) store `declared_level`, with HSK
  values, under an architecture review, then turn the level half on (recommended); (b) read "has a
  level" from evidence the backend already keeps, which exists only after some activity; (c) keep
  the entry rule without the level.
- **Meet Orena draws starter chips, a free-text composer and simulated replies** (the prototype
  script's own fake-timer, regex-matched `answer()` - explicitly not behaviour to copy). No chat
  capability exists yet (`orena` is still Coming Soon; `shell/agent-bridge.js`'s `askOrena()` has no
  message field and AGENT_CONTRACT.md §6.1 names no onboarding surface id), so this build keeps only
  the mark, one greeting line (a template from real, already-known state - the learner's account
  name, picked target/support/level, never an AI call) and "Go to Today →". **Question for the
  lead:** wire the starters/composer to `askOrena()` once a surface id and a message path exist.
- **Nothing routes a learner who has not onboarded to `#/welcome` yet.** `GET /api/learner-profile`
  already carries `exists`, the natural signal; deciding where that check lives (shell boot, a route
  guard) is shell/main routing, out of this unit's files.
- **`scripts/fixtures/api/platform_languages.json` is stale**: it holds 3 support languages and 3
  levels per learning language; the running sandbox answers 12 support languages and 6 real
  CEFR/HSK levels. The gate asserts `en`/`vi`/`zh` are present and checks the model's level-filtering
  logic against the fixture's own (smaller) real shape, so a re-capture only strengthens the
  coverage, never breaks the gate. Re-capture belongs to the fixtures owner.
- **Kit token gaps remain open on the largest surface** (not this unit's files to fix -
  `static/orena/kit/tokens.css` is shared): the desktop aside's background is `--mark-disc` (two
  stops) where the frame draws a third `#0E0E16` stop (`radial-gradient(120% 140% at 0% 0%, #2B2158
0%, #150F2E 62%, #0E0E16 100%)`), the big hero mark's shadow is `--mark-glow-strong` (`0 4px 12px`)
  where the frame draws `0 20px 50px rgba(122,92,246,.35)`, and the aside's ink is `--toast-ink`
  (`#fff`) where the frame's dark-only text is `#F3F3F8`. **For the lead:** add theme-independent
  tokens for the aside gradient, a stronger hero glow and the aside ink, then this screen swaps them
  in - no literal colour was added locally to approximate them (product invariant).

## Speak more: Free Talk, Conversation, Situation Reaction, and Retell / Timed Reaction / Mock Interview / Sound-Tone (D-088 frames 29-32, 43, 48-49), Wave B, 2026-09-28

Built for real, against a real backend: `screens/free-talk/`, `screens/conversation/`,
`screens/situation/` (routes 'freetalk'/'conv'/'situation'). **Deliberately left unregistered**,
falling through to the design's Coming soon screen (`shell/screens.js`'s own documented-omission
pattern, matching `rewrite`/`timed-writing`'s precedent): `retell/:id`, `timed-reaction`,
`interview`, `sounds`. None of the four has real backend content to build against - not a styling
gap, a content one:

- **Retell** (frame 32) scores against 5 fixed key-point checkpoints and a 10-phrase reuse list,
  both hand-authored for one specific video in the source (`RETELL_POINTS`/`REUSE`,
  `orena-script.js`). No field anywhere in the schema carries a "key points to cover" or "phrases
  worth reusing" list for a piece of content - not on a Listening lesson, not on a Speaking
  catalogue item (`writing_coach/speaking_library.py`'s `SpeakingItem`/`SpeakingLine` carry only
  `{line_id, text, reading, translations}`). Real semantic-coverage scoring against arbitrary
  content needs its own content/schema decision, not a per-screen invention.
- **Timed Reaction** (frame 43) draws from a 3-item inline prompt bank (`TRE`, Vietnamese prompts
  with English `must[]` regex checkpoints) with no backend equivalent at all - no prompt-bank
  endpoint, no per-language-pair content table.
- **Mock Interview** (frame 48) draws from a 4-question fixed bank (`MOCK_Q`) with model answers
  and STAR-structure detection hand-tuned to one of the four questions. No interview-question
  catalogue exists.
- **Sound / Tone** (frame 49) draws from a 7-pair English IPA minimal-pair bank (`PAIRS`) with **no
  Chinese tone-pair dataset at all**, despite the frame's own Chinese copy promising one ("tone
  pairs... pick the character") - the clearest case in this set of the frame promising content the
  data model has never had (E2 §10's own finding, confirmed again here).

All four practice types exist as _names_ in `speaking_library.py`'s `PRACTICE_TYPES`
("retell"/"interview"/"sounds"), but the Speaking catalogue ships empty by product decision
(`content/speaking_catalog.v1.json`, `{"items": []}`, UI_BACKEND_GAPS SP-1) - so even once
authored, an item of one of these types would still carry no checkpoint/question/pair data, only a
title and lines. A real build of any of the four needs a content/schema decision first (what a
"key point", an "interview question bank", or a "tone pair" is, as a real field), not a client-side
regex/heuristic reproduction of the frame's own prototype scoring - which is exactly what Wave B's
brief asked this pass not to build. Their routes (`shell/routes.js` 'retell'/'timedreact'/'mock'/
'sound', already wired by an earlier pass) render the design's Coming soon screen, titled from
their own real `shellCopy` crumb, until that content exists.

### Free Talk, Conversation, Situation Reaction - real data, recorded deviations

All three replace the frames' own prototype content and scoring with real sources: the recording
pipeline (`capabilities/audio-recorder.js`, the shared Mic state sheet's `micGate`/`openMicState`),
real ASR (`POST /api/speech/transcribe`), and real coaching
(`POST /api/dictionary/spoken-response`, `writing_coach/media_interaction.py#coach_spoken_response`

- the same "carried / landed_differently / another_way / next_attempt / say_again" shape the
  current Free Talk's own `ui/speaking-free.js` already calls, reused as the real contract, not
  duplicated). Conversation additionally reuses `product/conversation.js`'s existing turn state
  machine and `POST /api/dictionary/conversation-turn` whole. Scenario/topic content for all three
  comes from `content/voice-invitations.js` (3 real, Orena-authored situations per learning
  language) - the same bank the current Free Talk already draws from - in place of each frame's own
  fixed prototype set (Free Talk's `ftSuggest`, Conversation's 4-scenario `CONV` script, Situation
  Reaction's 2-item `SITUATIONS`).

Deviations recorded, not silently resolved:

- **Free Talk's three result stat tiles keep the frame's own labels (Words / Pace / Linking), but
  only two are real.** Words and Pace are computed from the real transcript and the real elapsed
  recording time (language-aware: Han characters for `zh`, whitespace words otherwise) - genuine
  derived numbers, not the frame's own regex `analyze()` estimate. Linking has no real detector
  anywhere in this build and always renders `0` (rule 40's UI fallback, never stored or sent as a
  measurement) - relabeling it to a different, unrelated real metric under the same name was
  considered and rejected as a bigger invention than showing an honest zero under the frame's own
  label. Under 5 s of recording there is not enough to say a pace, and the tile draws the frame's
  own "—" (`wpm: fb.wpm == null ? "—" : fb.wpm` in the source), never a made-up 0; a transcript the
  learner typed instead of speaking (the mic sheet's "Continue"/"Type instead") is measured against
  no time at all, so it shows the dash too.
- **Free Talk's "Ask about this" uses `speaking.free_talk`** (AGENT_CONTRACT.md §6.1's one real
  Speak surface id for this screen). No equivalent surface id exists for Conversation or Situation
  Reaction, so neither gets an "Ask Orena" chip; adding one would be a contract change (§6.1: "a
  new id is a contract change, bump version"), out of this pass's scope. Situation Reaction draws
  no per-answer coaching UI beyond its own Improvement/Alternative cards (already covered above).
  Precision correction (found on this resumed pass): Conversation's per-turn "How did that land?"
  is NOT coaching-UI-free - the source's own handler (`orena-script.js`'s `onCoach`) actually opens
  the Orena panel with a _simulated_ regex analysis (`analyze()`'s fake fix/strength), one of the
  prototype's own internal simulations this build must not copy (brief §1, "NOT behaviour to
  copy"), not a real design pattern to reproduce literally. Real content exists instead
  (`POST /api/dictionary/spoken-response`, the same endpoint/shape Free Talk and Situation Reaction
  already use) but no real Orena surface id to carry it through, so it renders inline under the
  learner's own bubble (`.s-conv__coach`) - real data, but genuinely new UI the frame does not
  draw, kept as the more real, more useful choice for this contract gap rather than dropping
  "How did that land?" outright. Recorded here in full rather than left implied.
- **Conversation opens with the learner's own first line, never a seeded partner opener.** The
  frame's own `cvStart` seeds a fixed partner line before the learner has said anything; the real
  contract cannot do that - `ConversationIn` (`writing_coach/conversation.py`) requires the last
  turn to be the learner's pending one, and `product/conversation.js#conversationRequest` throws
  without one. A real conversation therefore always starts with the learner speaking. The
  situation the learner is answering (the chosen card's own `prompt`) is drawn as the frame's
  partner-style first bubble so the chat does not open blank; it is presentation only and is never
  sent as a turn. **Decision for the human:** the frame ends a chat only when its 4-line partner
  script runs out ("Conversation complete" with New scenario / Finish). An open-ended AI partner has
  no such end, so a single "End" text button sits in the header (where a page's own action sits in
  the design; the current UI had "End conversation" too), and the 24-turn cap
  (`MAX_CONVERSATION_TURNS`) leads to the same card. It is the one control here the frame does not
  draw; if the design should place it differently (a "⋯" menu, the composer row), that is a design
  call.
- **Conversation drops the frame's B1/B2/C1 difficulty picker entirely** (E2 §3: cosmetic even in
  the source - "nothing in `cvSend`/`CONV` branches on `diff`") rather than keeping an inert
  control, and drops the partner reply's own `meaning` (support-language gloss) line - real data
  `product/conversation.js#partnerTurn` already carries, but no element in frame 30 draws it (rule
  43: nothing added the source does not draw).
- **A failed partner reply or coaching call leaves the learner's own words on screen and offers a
  real Retry**, rather than the silent client-only failure the frames don't model at all (neither
  frame draws a "processing"/service-failure state for what was, in the prototype, a synchronous
  regex call - E2 §11 Contract gap 9). Retry resends the exact same request.
- **Situation Reaction's Intent-achieved / Clarity result grid is not built.** The frame's own
  `srSubmit` counts regex-hit ratios against `SITUATIONS[].must` and buckets a word count into a
  "clarity" label - E2 §4's own words: "not a real clarity judgement." Nothing in the real backend
  measures either. "One useful improvement" and "Natural alternative" instead bind to the real
  coaching's own `next_attempt` and `say_again`/`another_way` - the two blocks the frame already
  draws in that shape, now carrying real content instead of a fabricated verdict.
- **"Try another context" is dropped** together with its amber context-variant pill and the
  "Transfer evidence recorded" line - all three depend on the frame's own `.variant` sub-object,
  which no real scenario carries (only 3 real situations exist, none with a second "context"
  variant). Cycling through the 3 real scenarios ("New scenario") is kept.
- **The small delivery-mode pill above the scenario ("Chat message to a colleague", "Walking into
  the room") is also dropped** (found and corrected on this resumed pass, not recorded by the
  interrupted attempt): every `SITUATIONS[]` entry in the source carries this as its own top-level
  `context` field, always shown, separate from the `.variant.context` the bullet above already
  covers. `content/voice-invitations.js`'s real items carry no equivalent field (only
  `title`/`prompt`/`cue`) - inventing a delivery-mode label per situation was rejected as content
  the source's own author never wrote, not merely gated by a variant toggle. Left undrawn (rule 40),
  not filled with a placeholder.
- **Situation Reaction's "Finish" is reproduced as the frame's own outline button**, not the
  filled accent CTA every other frame in this family uses - a real, already-flagged inconsistency
  in the source itself (E2 §11 Contract gap 8, still unresolved by the human as of this pass) -
  not silently "fixed" here.
- **`ctx.go(ctx.href('spsummary'))`** is what "Finish" calls in all three - the real route
  (`shell/routes.js` 'spsummary', crumb `speakingSummary`) another Wave B pass owns (`screens/
speak-summary/`, registered in `shell/screens.js` while this pass was running). At the time of
  this pass's own browser verification that folder had no `screen.js` yet (a live, in-progress
  sibling build, confirmed via `git status` - not this pass's file), so "Finish" showed the
  router's own load-error screen rather than a real summary; expected to resolve once that sibling
  pass finishes, not a defect of this one. **Update (resumed pass):** `screens/speak-summary/`
  exists now and reads `product/speaking-session.js`, the session's own speaking ledger (written by
  `screens/speak`; its header invites "any later speaking screen" to log to it). "Finish" therefore
  writes one entry before it navigates, like the source's `spFinish` (`[Free Talk, summary]`,
  `[Conversation, "n turns"]`): `kind: 'free_talk'` with the measured Words/Pace as strings,
  `kind: 'conversation'` with the turn count, `kind: 'situation_reaction'` with no facts (nothing was
  measured). The facts are strings on purpose: the summary's "key improvement" reducer reads numeric
  facts as low scores, and a word count is not a score. **Integration item for the lead:**
  `screens/speak-summary/screen.js` labels a task through `TASK_LABEL_KEY`, which knows only
  `scripted_pronunciation`; any other `kind` is printed as its raw key ("free_talk"). Three entries
  (`free_talk`, `conversation`, `situation_reaction`) and their en/vi/zh labels
  (`shellCopy` already holds "Free Talk" / "Nói tự do" / "自由说", "Conversation" / "Hội thoại" /
  "对话" and "Situation Reaction" / "Phản xạ tình huống" / "情景反应", so the labels can reuse those
  three keys) belong in that screen's map - not edited here, it is another agent's file.
- **Per-turn coaching in Conversation composes the Free Talk result's own drawn patterns** (green-soft
  strength rows, surface fix cards with a struck-through original and its `judgement` label,
  accent-soft "Another way to say it" / "Next attempt" rows) instead of the Orena panel the frame
  opens - see the "How did that land?" paragraph above. To be replaced by a real "Ask Orena"
  hand-off if the contract ever gains a Conversation surface id (§6.1 has none; `activity_type`
  already has `conversation_practice`).
- **The Mic state sheet's buttons are wired to real behaviour** in all three screens: Retry sends the
  same recorded take to `POST /api/speech/transcribe` again (or asks for the microphone again from
  the "blocked" state), "Try again" after nothing was heard records again, and "Continue" / "Type
  instead" leave the learner in the typing surface the screen already has (Free Talk opens its
  editable transcript empty). An outage while the browser is offline opens the sheet's own "offline"
  state instead of "provider".

See `scripts/fixtures/api/README.md`'s "Not captured (speak-more pass)" note for the one route this
pass could not capture a success for: `POST /api/speech/transcribe` (`GET /api/speech/status` →
`configured: false`, the route answers a real 503 `speech_asr_unconfigured`, captured as
`speech_transcribe_unavailable.json`); its success body is read from
`writing_coach/speech_api.py#transcribe_speech` in the screens' gate. The text-generation routes DO
answer on the isolated stack (a local model): `POST /api/dictionary/spoken-response` and
`POST /api/dictionary/conversation-turn` are real captures
(`spoken_response*.json`, `conversation_turn.json`) that the three gates read, so a renamed field
fails a gate rather than a browser. (An earlier version of this section said the sandbox carried no
AI provider; that was wrong for text generation - only speech is unconfigured.)

## Dictation + Shadowing (D-088 frames 07/28), Wave B, 2026-09-29

Built `static/orena/screens/dictation/` (`#/listen/:id/dictation`) and
`static/orena/screens/shadowing/` (`#/listen/:id/shadow`), both against
`GET /api/listening/library/{id}` and real per-segment progress
(`GET`/`POST /api/listening/progress`, `GET`/`POST /api/listening/shadowing-progress`). Read from
the frames AND the pinned state script (`Orena.dc.html`, the `dLiveOn`/`hintNote`/`tok`/`shPhase`
bindings), not from the compact frames alone. Gaps and decisions for the human:

- **Dictation's "Live check" strip is built** (`dLiveOn` is `dHint > 0 && no result`, so it appears
  the moment a hint is taken - an earlier note here saying nothing ever sets it was wrong). The
  design's hint ladder is three taps: word shapes, first letters, "some words revealed". The
  prototype's own level 3 reveals _every_ word, which contradicts its own note and the brief (LS5:
  "a wrong word is not fully exposed merely because the learner asks for a hint"); this build reveals
  every third word the learner has not earned and did not type wrong, and never confirms a word the
  learner has not reached (`capabilities/dictation-hints.js#wordProgress`). Chinese groups
  characters into words with `Intl.Segmenter` (a runtime without word data degrades to one
  character per chip, where level 2 shows nothing new) so a hint is never a single character given
  away whole. Decision for the human: is "some words revealed" every third word, or a different rule?
- **Chinese reading (pinyin) under characters is not drawn in Dictation.** The frame's result and
  live chips carry only a flat string per token (D4 §6) although the spec (LS5) asks for a reading
  under each character "when enabled"; adding it is a frame change, not built. Chinese compares Han
  characters as before (`listeningUnits`); note that shared evaluator joins a Latin run and the Han
  character next to it into one unit (`"Vector版"` in `zh-technology-search-wikipedia`).
- **Result colours come from the state script's `tok()`**: a matched token is plain, a wrong token
  on "You wrote" is `--red-soft`/`--red` with a wavy underline (`dMine`), an unmatched transcript
  token is `--accent-soft`/`--accent-text`. The score is `matched/total` and its note has three
  tiers (every word / close at 0.7 or better / replay), as the script draws them.
- **Dictation's "Finish" (last segment, checked) leaves the room via `ctx.back()`**, not a forced
  navigation to Listening or a Lesson-complete modal - the frame draws no terminal screen for
  Dictation, and inventing one (even reusing the shared `screens/lesson-complete/` sheet) would be
  adding UI the source does not draw.
- **Both rooms show the kit's disabled state on an unavailable Previous / Next** (the first and last
  segment); the frame draws only the enabled control and its script simply ignores the tap.
- **The typed answer is device memory** (`memory.answers[<asset>:<segment>]`, the key the old
  Dictation used), so leaving the room and coming back keeps a draft. Checks are real records
  (`POST /api/listening/progress`); a blank check is not an attempt and is neither saved nor counted.
- **Shadowing's "Start lag"/"Timing match"** come from the provider's own per-word offsets
  (`capabilities/pronunciation-result.js` `offsetMs`/`durationMs`, `screens/shadowing/model.js#lagMs`/
  `matchPercent`); the old prototype's retry-count formula (`shTries`) is not reproduced. Each
  renders "—" (rule 40) when the provider measured nothing. The "Speed" tile is the rate the round
  was shadowed at (the frame's own binding, `speed + "x"`), not a measured pace. The bars are the
  microphone's real level while the learner speaks and the frame's resting shape otherwise.
  Verified end to end with a fake microphone and a verification-only stub of the provider envelope
  (no speech key in the sandbox); never shipped.
- **Shadowing's "Phrase rehearsal"** routes to `speak/media:<lessonId>?segment=<line>`;
  `product/speaking-source.js#segmentOf` (the Speak room's) reads `segment`. Dictation and
  Shadowing read `seg` (what the Listening Workspace passes) and also accept `segment`.
- **The shared mic sheet's "Microphone is blocked" state offers "Type instead"**, which Shadowing has
  no meaning for (there is nothing to type). It is raised by `screens/mic/sheet.js#micGate`'s own
  blocked branch, which takes no `textFallback` option (`openMicState` does); request: `micGate(ctx,
start, { textFallback: false })`. Every other mic state is used as the sheet draws it.
- **The offline sheet says the recording "will be assessed automatically when you're back online"**;
  Shadowing keeps that promise while the room is open (the take is held in this tab and re-assessed
  when the browser reports online) and only then - a take is never stored (D-076).
- **The speed ladder is the design's shared one** (1, 0.75, 0.5, 1.25) in both rooms; the Listening
  Workspace keeps its own local ladder and the speed is not carried between rooms.
- **No AGENT_CONTRACT §6.1 surface id exists for Shadowing** (`SURFACES` names `listening.dictation`
  only); the frame draws no Explain/AI action for it, so nothing is asked of the agent. Shadowing
  registers `play_model`, `play_user` and `say_again` while mounted; Dictation registers
  `play_model`. Shadowing does not log to the Speaking Summary session ledger (its kinds are the
  Speak room's, and the frame draws no path from Shadowing to that summary, E2 §1).

## Review Session, Vocabulary Daily Feed, From Your Errors (D-088 frames 13/36/50; 34/35 left unbuilt), Wave B, 2026-09-29

Built `static/orena/screens/review/` (route `review`, `#/review`; `?word=` / `?collection=`),
`static/orena/screens/feed/` (route `feed`, `#/feed`) and `static/orena/screens/errors/` (route
`errfix`, `#/from-your-errors`), each registered by one line in `shell/screens.js`. `timed`
(`#/timed-recall`, frame 34) and `transfer` (`#/transfer`, frame 35) are **not** built - see below.
Node gates (`test_orena_screen_review.mjs`, `_feed.mjs`, `_errors.mjs`) pass. Measured against the
pinned design (rule 42) in every state each frame draws, desktop dark/light and phone light/dark: the
remaining differences are the D-093 accent/AA tokens, sample content, and the items recorded here.
Verified live on the isolated app: real journeys, the four rule-49 sizes with the longest content
the API accepts, en/vi/zh interface, a zh learning language, real touch (swipe, tap) on a phone
context.

- **Timed Recall and Context Transfer have no real backend at all**, confirmed by a grep of
  `app.py` and `writing_coach/*` for anything of either drill's shape (`timed_recall`,
  `context_transfer`, `fast_retrieval`, `transfer_count`, ...) and of the old UI (nothing in
  `static/orena/ui` draws either). Both frames' logic in the design's own state script is client-side
  over a hardcoded six-word list (`DUE_SEED`); Progress's "Fast retrieval" / "Transferred" stages have
  no owner either (`screens/progress/model.js#buildKuStages` is the rule-40 zero). Per the Wave B
  brief ("real backends only, else Coming soon") both routes stay **unregistered**, and
  `shell/router.js#loadScreen` serves the design's Coming soon titled from each route's `crumb`
  (`timedRecall` / `contextTransfer`, present in en/vi/zh; checked in all three, and the workspace is
  the viewport at 390x844 and 360x740). What a build needs: a timed-retrieval contract (word, prompt,
  shown / first-keystroke / submit timestamps, a server-graded fast / slow / miss that feeds
  Progress) and a situational-prompt use/transfer grading contract (plural prompts per word, not a
  fixed 2). A client-only timer graded by a UI constant, feeding the existing review endpoint, would
  be possible but is product behaviour this pass has no standing to invent (see the report's
  questions).
- **Review Session: three real grades, never the frame's four** (rule 40). The frame draws
  Again / Hard / Good / Easy with four fixed intervals. The real scheduler
  (`becoming_library.py#review_schedule`, on every item as `item.schedule`) accepts exactly three
  (`again` / `unsure` / `got_it`, `VocabularyReviewIn.result`) and reports a real interval per grade
  for _this_ card's own stage. Three buttons, each labelled with the number `item.schedule` carries
  for that card ("10 min / 1 day / 1 day" verified live); `unsure` takes the frame's "Hard" amber,
  `got_it` its "Good" fill; "Easy" has nothing to bind to and is dropped, not merged.
- **Review Session: the frame's two ways of asking are both built** (`rvMode`, D7 §1.5), on real
  data only. "Target -> meaning" (the word; cue = reading + part of speech; hint = the learner's
  own-language gloss, and no Hint button when the card has none) and "Source-aware cue" (the sentence
  the learner met the word in with every occurrence taken out; hint = first letter and length). A
  card is source-aware exactly when its saved `source_fragment` really contains the word (the old
  product's `recall.js` rule), so the same card is always asked the same way. The frame's cue
  "... - A Morning in the City - 0:24" is drawn without the title and time: a saved item carries no
  source title or timestamp, only `source_kind` (reading / feedback / strength name a source; the
  rest draw none).
- **Review Session: offline answers use the device review queue** (`product/review-queue.js`,
  `memory.reviewQueue`, brief). A grade that cannot reach the server waits there and is sent, oldest
  first, on the next connection - at the start of the next Review and on the `online` event while
  Review is open - and still counts in that session's summary. The pinned frame draws no offline
  state, so the only signal is one toast in the nearest drawn pattern (support copy, "No connection -
  saved on this device, ..."). A server refusal (4xx) is not kept (it would be refused again) and
  toasts the existing "couldn't save that grade" line; a card unsaved mid-grade (`{found:false}`) is
  not counted. Flushing while the learner is elsewhere in the app would need a shell-level `online`
  handler (kit/shell request, not built here).
- **Review Session: `?word=` and `?collection=` now actually scope the session.** The router hands a
  room its query as a `URLSearchParams`; the first build read it as a plain object, so Collection
  Detail's "Start review" quietly reviewed the whole due queue. Fixed and gated. "Mark known" (the
  Word Card's `onKnown`) is still not built in Review or Feed - no real backend action (same as Word
  Detail).
- **Review Session / Feed: the Word Card's Hanzi block is drawn as Word Detail draws it** - "Stroke
  order", a tile per character from `GET /api/chinese/stroke-order` (`product/hanzi-strokes.js`), then
  "Practise strokes"; a character the pack does not carry gets no tile.
- **Rule 50 drops.** Review: "Items marked Again come back sooner. Nothing else to schedule by
  hand." (obvious scheduler behaviour). Feed: the front-card caption "Tap to reveal meaning and
  example" (the header already says "tap to flip"; E4 §3 flags it). From Your Errors: the header
  prefix "Fix sentences you actually said" (a description of the screen the title already names - and
  "said" is not even true, the evidence is Writing).
- **Vocabulary Daily Feed: no per-word image and no measured mastery - both drawn as the design's
  own fallbacks** (rules 37 and 40; the first build had removed the region, which left the card
  half empty). The front card keeps the frame's image region as the design's missing-artwork
  placeholder (`.o-art`, at the real ratio, replaced with no layout change when a word gets real
  art: `VocabularyCard` carries no image field) and its mastery meter at the measured value - no bar
  filled and the real stage-0 label "New" - never the frame's sample "Recalled". The front Play label
  is "Play", not the frame's "Hear in context" / "No audio": the payload carries no per-card
  audio-availability, and the frame's label depends on a transcript segment the feed does not have.
  A flip or save keeps the rail where the learner swiped to (a repaint used to send it back to the
  first card).
- **From Your Errors is Writing-only by construction.** `GET /api/practice-outcomes`
  (`becoming_outcomes.py`) is the only endpoint that names which of the learner's own targeted
  attempts had a real recorded issue, and it covers Writing only; the design's sample drills also
  draw from Speaking (Free Talk, Conversation, E4 §6), which has no equivalent to join against an
  essay's `issues[]`. No R5 grammar read anywhere (2026-09-28 decision). A sentence with no matching
  issue or no real correction is never turned into a drill card.
- **From Your Errors: drawn as the frame draws it, including where it differs from its siblings.**
  Its back button (`radius:12px`, icon `19`), title (`17px`) and progress bar (`5px`) differ from the
  sibling drill frames' `14px / 21 / 16px / 4px` (E4 §6 flags it as a possible export artefact).
  The previous build normalised them to the siblings; this one follows the pinned frame, because
  "normalise" is a decision the brief reserves. One line to change if the human prefers the sibling
  signature (`errors.css`: `.s-errors-back`, `.s-errors-head__name`, `.s-errors-bar`).
- **From Your Errors: the result box draws the sentence as it was (struck), the correction and the
  reason in every state, as the frame does**, so a wrong check also shows the correction next to
  "Try again". Hiding it until "Show answer" would be a pedagogical choice the frame does not draw
  (recorded as a question). A right answer is only ever the real correction (case, spacing and
  punctuation in any script are forgiven, words are not): another valid fix of the sentence is
  "Not quite yet" until the learner asks for the answer - a limit of grading against one AI
  suggestion, not something to loosen by guessing. "Fixed after a retry" is built as the frame's
  copy says it; the prototype's own `efCheck` can never reach it (its first line credits a first try
  on any right answer).
- **From Your Errors' real entry point is a screen outside this pass's scope.** E4 §6: the frame's
  only entry in the design's script is a practice-rail item ("!", red) beside Dictation / Grammar /
  Pronunciation / Retell / React-Reuse. The route is reachable through `ctx.href('errfix')`; wiring
  the rail item is the other surface's job.
- **Live coverage note.** The isolated app's learner has no practice outcomes
  (`GET /api/practice-outcomes` -> `{items:[],latest:null}`), so From Your Errors was driven live on
  payloads shaped by the two serializers (`derive_practice_outcome`, `row_to_dict(detail=True)`),
  intercepted in the browser (test scaffolding, never shipped): the whole edit -> check -> retry ->
  show answer -> next -> done -> run again -> re-enter journey ran, at four sizes with the longest
  sentence, explanation and pattern name, in en/vi/zh. The empty state renders on the real API.
- **Observation for other lanes (not fixed here).** `LibraryVocabularyIn.source_kind` only accepts
  `manual|dictionary|feedback|strength|reading|feed|collection` (`becoming_library.py`), so
  `POST /api/library/vocabulary` with `source_kind: 'listening'` answers **422** (checked live), yet
  `screens/listening/vocab-sheet.js` and `screens/quick-sheet/model.js` (which also maps `writing` /
  `speaking`) send those kinds - a word saved from a Listening, Writing or Speaking context would
  fail. Either the UI maps to an accepted kind or the backend adds them; a contract decision, not an
  implementation detail.
- **Shell observation.** After a route paints, `router.js` focuses `<main tabindex="-1">`; with no
  prior pointer input Chromium draws its focus ring around the whole column (visible in the
  screenshots of every focus route). `.o-main:focus { outline: 0 }` in `shell.css` would remove it.

## Listening Workspace, React / Reuse, Respond to Content (D-088 frames 06/54/33/45), Wave B, 2026-09-28

Resumed session: `screens/listening/` and `screens/react/` were already built by an interrupted
earlier attempt and kept (verified, not rebuilt); `screens/respond/` was built fresh. Full detail,
gates run and every rule-40 fallback: `SCRATCH/reports/listening.md`. Summary here:

- **Three real cross-screen bugs found in the resumed code and fixed, not merely re-verified:**
  (1) `api.listeningLibrary({ language })` called a wrapper that takes a positional string
  (`listeningLibrary:(language,filters={})`), so the end-of-media "next recommendation" row could
  never match - fixed to `api.listeningLibrary(language)`. (2) Listening's "Write a response" sent
  `ctx.href('respond', { id: lessonId }, { source: 'media' })` while Reader's own, already-built
  entry sends `ctx.href('respond', { id: realContentId })` (the one real "<kind>:<id>" scheme,
  `screens/content/model.js#contentIdFor`) - fixed Listening to send
  `ctx.href('respond', { id: contentIdFor(lessonId) })` so both entries agree, and built
  `respond/model.js#parseContentId` around that one real scheme instead of a second query flag.
  (3) Listening's "Dictation"/"Shadowing" actions and the Shadowing-mode tap sent a `segment` query
  key, but `screens/dictation/screen.js` and `screens/shadowing/screen.js` (a different Wave B
  agent's build) both read `ctx.query.get('seg')` - confirmed by reading their source directly, not
  assumed. Fixed all three Listening call sites to `{ seg: id }`; without this, "start Dictation/
  Shadowing here" from a selected line silently landed on segment 1 every time.
- **`react.css`: white ink directly on `--accent`** (`.s-react__mark`, the Reveal step's highlighted
  phrase) - D-093/the kit gate forbid this (`--accent-fill` for filled controls with ink text).
  Fixed. The full kit gate (`scripts/test_orena_kit.mjs`) currently aborts before reaching this
  file's alphabetical position on an unrelated pre-existing `rgba(` literal in
  `screens/orena/orena.css` (a different Wave B agent's file, not touched here); the gate's own
  three checks were replayed standalone against `listening/`+`react/`+`respond/` only, clean after
  this fix.
- **Save Phrase has no home.** The Listening frame draws a `savePhrase` button (saves the _selected
  segment/phrase_ as a whole), but no endpoint exists at that grain - only
  `POST /api/library/vocabulary` (a single word) and `POST /api/library/collections/{id}/items`
  (an already-kept item). Left out entirely (rule 40) rather than wired to the wrong-grained
  endpoint. A real sentence/phrase-grain save endpoint would close this.
- **Respond's "uses the source?" result tile is not built.** The source script computes it with a
  client-side keyword-overlap heuristic against the learner's answer - no real endpoint measures
  whether a response draws on its source (`POST /api/evaluate` grades grammar/vocabulary/coherence/
  task-achievement/naturalness only). The Result state keeps the frame's three tiles - Words (real),
  Uses the source (an honest rule-40 "0"), Fixes (real) - plus the evaluator's own first priority
  as "Next step", omitted, not guessed, when the evaluator named none.
- **Verification gap - RESOLVED (finish pass, 2026-09-29).** The prior session's `docker`/sandbox
  unreachability was environment-level, not a defect; the isolated app (`127.0.0.1:8021/next`) and
  the design pin (`127.0.0.1:8765`) were both reachable this pass, and the brief's §5 verification
  was completed against them:
  - **Rule 49, all four sizes, real content, both device kinds.** `workspaceCheck` at 1920x1080,
    1366x768 (Listening Workspace) and 390x844/360x740 (mobile, `hasTouch`/`isMobile`) all report
    `pageScrolls:false`, `horizontalOverflow:false`, no primary control outside a
    `[data-scroll-region]` - on the real, longer B2 video lesson, not a short fixture. React/Reuse
    and Respond checked the same way at 1440x900 and 390x844, same result. Confirms the code-level
    reasoning the prior session recorded, now measured.
  - **The three cross-screen navigation fixes hold live**: a word tap on a real transcript row opens
    the shared Quick Sheet; switching to Active mode really presses the pill
    (`aria-pressed="true"`); React/Reuse's own step CTA really advances the flow.
  - **Both AI-backed calls this group uses succeed on this sandbox, live, end to end** -
    `POST /api/evaluate` (Respond's "Get feedback") and `POST /api/dictionary/spoken-response`
    (React/Reuse's Result) both answered `200` with real generated content (not the documented
    failure path) via this sandbox's own local Ollama model (`qwen3:8b`) - the prior session's "no
    AI provider key, the route always fails here" note was **incorrect** for these two
    text-generation routes specifically (it is correct for `word-detail`/`sentence-sheet`/
    `translate`/speech, which genuinely have no provider here); corrected in
    `screens/react/model.js`'s and `screens/respond/model.js`'s own header comments. Respond's
    Result rendered real tiles/fixes/next-step from a real graded response; React/Reuse's Result
    rendered the real (honest, rule-40) tile fallbacks for a segment whose catalogued phrase the
    typed answer did not reuse. Both calls took several seconds to tens of seconds (shared local
    model, consistent with the documented 17-54s Ollama latency, longer under concurrent load from
    other agents' sessions in the same pass) - a verification script with too short a wait
    (15s) read this as a timeout on first try; a longer wait (90s) showed the real success path.
  - **Respond, article-sourced entry** (`#/respond/article:<id>`) verified separately from the
    media-sourced entry already covered above: real title, 4 real sentences, "Source · Article".
  - **EN/VI/ZH interface, and a real Chinese learning-language lesson**: Listening screenshotted in
    all three interface languages; a real HSK1 Chinese lesson (`zh-daily-what-is-this`, switched via
    `POST /api/platform/language {"language":"zh"}`, switched back to `en` afterward, per the brief)
    rendered 42 real Han-character tokens with 42 real pinyin readings from the backend's own
    `pinyin_chars_by_segment` alignment - no fallback plain-split was needed for this capture.
  - Console (`pageerror`) was clean across every page in this pass.
  - Screenshots: `SCRATCH/shots/listening-*.png`, `react-*.png`, `respond-*.png` (desktop/phone,
    light/dark, en/vi/zh, the zh-content capture, the get-feedback and react-result outcomes).
- **New gap found in this pass: Respond's live word/character counter now reads in the request's
  own floor unit, but the frame still draws no "why is the button off" notice.** The counter beside
  "Get feedback" used to show a plain `Intl.Segmenter` word count, which can disagree with the real
  gate (`capabilities/writing-limits.js#measureMinimum`: Han characters for a Chinese response, not
  Segmenter words) - a learner could see a non-zero count while the button stayed disabled for a
  reason the number did not reflect. Fixed: the live counter (pre-submission only - the Result
  state's own "Words" tile is unchanged, since that one answers "how long is this piece", the same
  split `screens/writing/model.js` already draws) now reads `measureMinimum(text, language).count`,
  confirmed live: one Han character shows "1" and keeps the button disabled, two shows "2" and
  enables it, matching the real per-language floor of 2. What is still missing, and is not this
  screen's to invent (rule 43): the frame draws no equivalent of Writing's own `tooShortNotice` (the
  "N more needed" line Writing's frame does draw), so a learner under the floor still has no on-screen
  text saying why - only a smaller number than they expected and a disabled button. Needs either a
  design answer (does Respond's frame gain a notice like Writing's) or a product decision that none is
  wanted here.

## Reader and Reading Complete (D-088 frames 14/40), Wave B, 2026-09-29

`screens/reader/` (`#/read/:id`) and `screens/reader-complete/` (`#/read/:id/done`). Resumed from an
interrupted attempt: its moves out of `ui/reading-room.js` into `product/reader-text.js` were kept
(old gates re-run, green); the screen itself was rebuilt against the frame. Full detail, the final
measurement diff and every rule-40 fallback: `SCRATCH/reports/reader.md`. What the frame draws and the
backend cannot yet serve:

- **Summary has no backend.** No endpoint summarises a text (checked: no route in `app.py` or the
  reading APIs). The "Summary" item in the Reader's "⋯" menu answers with the design's own
  "not prepared" toast (frame 14's own state for an imported text) instead of a panel of invented
  bullets. Needs an endpoint that returns bullets with a provenance (source-provided / deterministic /
  generated on request - spec R3) before the docked panel can be drawn.
- **The vocabulary lens shows only words kept from this text's own sentences.** The frame underlines
  words the learner knows; the backend has no bulk "which of these words are saved" route
  (`saved_vocabulary_words()` in `writing_coach/becoming_library.py` exists and serves the sentence
  sheet, but is exposed by no route, and `api.libraryVocabulary` must never read the whole
  vocabulary). The lens - and the amber tint the frame gives a saved word - are drawn from the
  learner's most recent 100 saves whose `source_fragment` is a sentence of this text. A membership
  route (`POST /api/library/vocabulary/membership { words: [...] }`) would show every saved word.
- **No link from a saved word to its document.** `POST /api/library/vocabulary` carries no content id.
  Reading Complete's "saved from this text" counts saved words whose `source_fragment` equals a
  sentence of this text (exact, not a guess from the word appearing somewhere) - correct for words
  saved through the Quick Sheet, blind to words saved elsewhere and to saves older than the 100 most
  recent. A `source_ref` on the saved word would make it exact.
- **Notes and highlights are device memory.** Notes are the Sentence Quick Sheet's own
  (`orena.quicksheet.notes.v1`); highlights (frame 14's "Highlight" and the green rows of "Notes &
  highlights") are the Reader's, sentence-level, in `orena.reader.highlights.v1`. Both are
  learner-owned data with no server schema (AGENTS section 7 hold): they do not follow the learner
  to another device. The frame's mock also filed a highlight into My Library (`s.saved`); no
  endpoint has a sentence grain (the same gap as the Sentence Quick Sheet's "Save highlight", above),
  so a highlight is not in My Library.
- **Read-aloud is the browser's own speech synthesis.** No server voice exists for reading texts. A
  device with no voice for the text's language (Chinese on many desktops) gets a toast, not a silent
  button. Chunked one paragraph at a time from the learner's position.
- **Translation needs the AI provider.** `POST /api/reading/translate` answers `status:
"unavailable"` here (captured, `reading_translate.json`); the Reader asks in turns of 12
  paragraphs (the route's own comment: a chapter is "sent in turns") and, when nothing comes back,
  switches the aid off with a toast. The `ready` rendering was verified with a route-intercepted
  response of the serializer's own shape, never shipped.
- **"Next" on Reading Complete has no relatedness signal.** The frame says "Next - same theme"; the
  row names a real next chapter or the first unfinished article of the same language (the
  catalogue's own order), labelled "Next" only - the "same theme" claim is not made.
- **"Understood" reads `GET /api/reading/practice/evidence`** (latest attempt at this article). No
  article has an approved set here and submission is off, so it shows the frame's em dash; the
  payload shape is `reading_practice_evidence_attempt.json` (built from `list_evidence()`).
- **Progress links the Reader with a bare article id.** `screens/progress/screen.js`
  (`ctx.href('reader', { id: item.articleId })`) passes the article's UUID, not the content id
  `article:<uuid>` every screen shares (`screens/content/model.js#contentIdFor`); the Reader shows
  its load error for it. One-line fix in Progress: `contentIdFor('article', item.articleId)`.
- **Check's "Show in text" still cannot land on the evidence sentence** (unchanged from the Check
  entry above): the Reader takes no anchor and the served set carries no span.
- **`capabilities/lexical.js` still builds the OLD Reader's sheet** (it imports `ui/html.js`,
  `ui/quick-sheet.js`, `ui/reading-room.js`). The Reader therefore has its own small pointer layer
  (`screens/reader/lexical.js`: tap a word, tap a sentence, select text) over the new quick-sheet
  overlay. When the old rooms go, that layer moves to `capabilities/` so Reading and Listening share
  one. (Finish pass, 2026-09-29: the two files had drifted into two copies of `plainWordAt` - the
  no-tagger word-span rule both use for a tap. Moved to one shared, DOM-free module,
  `product/word-span.js`, imported by both; no behaviour change.)
- **Not a defect: word roles/pinyin 409 on the one Chinese article unless the learning language is
  zh.** `POST /api/media-learning/annotate` enforces the same rule as Reading Transfer's RT-4 above:
  `source_language` must equal the learner's _current_ learning language (`current_language_code()`,
  set from `POST /api/platform/language`), not merely the text's own language. Discover/Library only
  ever surface an article in the learner's active learning language, so under normal navigation
  `doc.language` and the learner's learning language already agree and this never fires; it only
  fires when a route is opened directly for content in a language the learner has not activated (as
  a reviewer testing the Chinese article without first switching the sandbox's learning language to
  zh will see). Verified directly against the sandbox (2026-09-29): the same annotate call 409s with
  the learning language left at `en` and answers 200 with real annotations once switched to `zh`
  (`POST /api/platform/language {"language":"zh"}`, per the brief). The Reader's request
  (`source_language: doc.language`) is correct and needs no change; `fetchAnnotations`'s existing
  catch already leaves the paragraph plain on any failure, so a genuine mismatch degrades gracefully
  rather than breaking the room.
- **Overlay defect - RESOLVED (2026-09-29):** the Sentence Quick Sheet's repaint after "Add note" used
  to drop focus to the page, so Escape (bound on the sheet element) no longer closed it. The shared
  overlays' fix keeps focus inside the sheet on every repaint; verified on the Reader.
- **Phone recomposition (N-6, rule 49).** The frame stacks the Notes & highlights panel below a long
  article on a phone, where it is unreachable in a workspace that scrolls only inside the text; the
  panel opens as the design's bottom sheet on a phone and stays docked beside the text on a desk.

## Grammar Library and Grammar Concept on the grammar content contract (frames 44/47, D-100), 2026-09-29

`screens/grammar/` (`#/grammar`) and `screens/grammar-concept/` (`#/grammar/:id`) no longer read R5
(`/api/library/grammar*`); they read `GRAMMAR_CONTENT_CONTRACT.md` (schema v0.4) through one seam,
`static/orena/product/grammar-source.js`. R5 modules, contracts, Concept IDs and gates are untouched
(D-100 point 5). What could not be resolved inside the lane:

- **G-1 · No content is served, by design.** No API exists (`/api/grammar/v1/*` waits for its own
  architecture review, D-100 point 4) and Grammar Lab's sample points (PR B) have not arrived. The
  seam reads static JSON at `/orena-assets/content/grammar/catalog.<lang>.json` and
  `/orena-assets/content/grammar/points/<id>.json`; nothing is there, so each read is a clean 404 =
  "no content": the Library draws its heading and the design's empty state, the Concept draws its
  header and "This grammar point is not available." When PR B arrives its files go at those paths (or
  the seam's two readers point at the API); no screen changes. The seam applies the contract's
  "only `approved` reaches the UI" rule because it is the feeder until the API exists. The node gate
  and the browser check use a TEST-ONLY fixture (`scripts/fixtures/grammar/`, built from the
  contract's own examples; never shipped - the gate asserts `static/orena/content/grammar` does not
  exist).
- **G-2 · Every existing grammar link carries an R5 id.** Search, Today, Practice continuation, From
  Your Errors and Writing's `grammar_links` open `#/grammar/<r5-id>`. The Concept resolves an R5 id
  through the catalogue's `aliases` and replaces the address (contract §9 rule 1); until content
  with `aliases` exists every such link lands on "not available". Those surfaces are not changed in
  this slice.
- **G-3 · Learner state has no source (§9).** Frame 44 draws four groups (recent errors, at your
  level, saved, recommended) and a status tag per card ("Open", "In progress", "New"); the contract
  carries none of it and no route joins learner state to Grammar Lab ids. The Library groups by
  level (`level.rank`), counts `function` topics per level, and draws no status tag (the R5
  `completed` flag keys R5 ids). **Decision for the human:** keep the tag out until a learner-state
  source exists, or draw it from R5 progress through `aliases`.
- **G-4 · The quiz writes nothing.** The old screen called the R5 completion endpoint on "Finish";
  it does not know Grammar Lab ids and was removed. No evidence route exists for the new ids.
- **G-5 · "Try it yourself" has no verdict (D-100 point 3).** Drawn as frame 47 draws it (prompt,
  one-line input, Check, a result line). The frame's result line is a green/red verdict ("The
  pattern is right. Recorded as Use evidence…"); the screen instead shows the contract's `sample`
  ("Sample: …") in the frame's neutral well (surface2, text) and records nothing. The button keeps
  the frame's label "Check" although nothing is checked. **Decision for the human:** keep "Check",
  or relabel; and whether the sentence goes to the Writing engine once PR A adds the recognition
  rule.
- **G-6 · Contract content frame 47 gives no place (rule 43).** Not drawn, kept in the data:
  `when_to_use` (§3), `compare` (§5), example `translation` and `annotation` (§4), every
  `common_mistakes` entry after the one chosen (§6), `pattern.variants` as chips, and each formula
  cell's `label` except in the word-order illustration. Candidates are "⋯" or a sheet; the human
  decides.
- **G-7 · Illustrations built under D-098 point 4, for the human's eye review.** Timeline, word order
  and word form are drawn from frame 23's timeline track and pattern boxes (surface2 well, radius
  16, padding 18; 2px axis, 10px accent bar at .75, 12px green dot, 12px muted marks, one 12px/700
  accent line) under a frame-47 eyebrow. The marks and the line are UI copy generated from
  `timeline.shape` (en/vi/zh); an authored `relevance` replaces the shape's line when present. The
  line sits under the track instead of inside it, so a long Vietnamese line cannot run out of the
  well. The "+" joiner between formula cells is frame 23's (text3, 600); an optional cell is drawn
  in parentheses, as the design's own "(now)" chip. Role colours: aux/marker/particle/connector/
  classifier accent, verb/complement green, subject/object/other neutral, time/place amber - the same
  bucket colours the example's spans take.
- **G-8 · Chinese.** A Chinese Library is frame 44 with HSK 3.0 levels (headings "HSK 3 · 初等",
  tile "HSK3"). Pinyin (§8) is drawn with the design's Hanzi-over-Pinyin stack (`data-py`/`data-hz`,
  kit/base.css; on only when the learning language is Chinese and the pinyin preference is on) on
  the title, examples, mistake, quiz, morphology and sample; not in the pattern chips, which the
  frame draws as plain chips. A reading whose length differs from the text is not guessed: the text
  is drawn plain. Contract ambiguity for Grammar Lab: §7 says quick-practice options carry
  "`_pinyin`" while §8 says "`pinyin` beside `text`"; the screen reads `options[].pinyin` (§8).
- **G-9 · Recorded deviations (rule 41).** The quiz letter dot: frame 47 draws white on
  `--surface3`, which fails AA; the ink is `--text`. The mistake and answered-option glyphs use
  `--badge-ink` instead of white (unchanged from the previous build).
- **Measured (rule 42), 2026-09-29.** Computed styles of frames 44 and 47 at the pin vs the app
  (fixture-fed), desktop 1920x1080 and phone 390x844, light and dark. What is left: the kit's token
  values, not this screen's (text3 `#8E8EA2`/`#6E6E86` light, red `#D93D42`/`#D0292E` light, dark
  accent `#7D78F5`/`#847FF6`, dark accent fill `#7D78F5`/`#6862F3` - D-093's AA values); the glyph
  inks of G-9; heights that follow the sample text. Font size, weight, family, letter-spacing,
  radius, padding, gap and fill of every other element match. Browser-checked in en/vi/zh, both
  themes, at 1920x1080, 1366x768, 390x844 and 360x740 (touch): no page scroll or horizontal
  overflow on the Concept (the card column scrolls in its own region), no shell on it, no page error.

## Current Admin reconciliation — 2026-10-03

The dated slice records below remain historical evidence. Their staging-only
exclusion of Overview/Users/Operations and AD-G's missing media processing stages
are superseded: these now use the existing Admin APIs in `/next`, and media import
and detail refresh actual processing stages/outcomes. Encrypted credential flow
and capability configuration were already implemented, not rebuilt. Sandbox
provisioning and deferred routing activation are repaired on :8021 only (D-117).
Current acceptance/limits: `docs/reviews/ADMIN_BASIC_CONTROL_BROWSER_CHECKPOINT.md`.
Speech capability routing and Practice generation remain explicitly unavailable;
canonical Grammar needs its supported runtime. Public activation stays gated.

## Platform Admin in the new UI: shell, No access, AI & Models (`Orena-Admin.dc.html` A2-A5, D-101 E slice 1), 2026-09-30

Built on the existing Admin backend and its client, moved to shared modules the old console also
imports (`capabilities/admin-api.js`, `admin-format.js`, `admin-ai.js`); no admin API was added. The old
console at `/#/admin` is unchanged and its gates pass. What the design draws that the control plane
cannot answer is left out, not invented; what the design does not draw but the truth needs is listed
for the human.

- **AD-1 · Key fingerprint and age.** The design's provider row and detail say "Key …4f2a · updated 6d
  ago". No admin endpoint returns a fingerprint or an updated-at for a stored credential (the brief
  says a saved key is never shown again). Not drawn: the row says where the credential comes from
  (stored key / server environment / none needed). Needs a backend decision to store and return
  `last4` and `updated_at`.
- **AD-2 · Test history.** The design's provider detail has a "Test history" block. Provider tests are
  audited (`admin.ai.provider.test`) but no endpoint reads them, so there is no history. Not drawn; the
  Connection test block shows this session's last result. Needs an audit-read endpoint.
- **AD-3 · Header environment pill.** The design draws a "Staging" pill. No admin API names the
  environment. Not drawn.
- **AD-4 · Test primary / Test standby test the SAVED route.** `POST /api/admin/ai/test/{key}` has no
  body; the design tests the draft. The buttons are disabled while the draft differs from what is saved
  ("Save the route to test it").
- **AD-5 · Usage is a recent sample, not "last 24 h".** `/api/admin/ai/operations` returns a bounded
  sample of events (`sample_limit`); per-provider requests, failure rate and mean latency are counted
  from it and labelled "Recent usage - counted from the latest N recorded operations". P95 is "Not
  available - not collected yet", as the design itself says.
- **AD-6 · A notice the design does not draw (decision).** While the learner runtime is `legacy`, a saved
  route does not change what learners use. The routing tab and a capability page therefore show one info
  banner (the design's banner component) - "Routes are saved, not live yet". The design draws no such
  text; without it the page implies a saved route is live. Keep, reword or delete?
- **AD-7 · Provider tile colour (decision).** The design colours each provider's two-letter tile with a
  brand hex. Colour has one owner (the tokens), so every tile is `--accent-fill`. A per-provider token
  set is a design decision.
- **AD-8 · Leaving Admin on a phone (decision).** The design's phone frame has no "Back to learner app"
  and no account block (both live in the desktop rail only). Built as drawn; on a phone the only way out
  is the browser's back. A chip or a header action would be an addition.
- **AD-9 · Header filter.** The design's "Filter this page…" is real on the AI list (providers, routes)
  and disabled elsewhere (detail pages have nothing to filter), with the design's own tooltip.
- **AD-10 · Save vs Save & test.** The server verifies a key against the live catalog itself and wants
  the default/allowed models from it, so both buttons try the draft key first and store nothing if it
  cannot connect. "Save & test" keeps that passing test as the provider's result; "Save" leaves the
  provider untested. Following the design, a key is required on every save (a provider that needs none,
  such as Ollama, edits its endpoint only).
- **AD-11 · Remove key** is offered for a key stored in the encrypted store (and an unreadable one). A
  key that comes from the server environment cannot be deleted by the app; only "Update key" (which
  stores an override) is offered.
- **AD-12 · Non-routable capabilities** (deterministic, reserved) are listed with a pill ("Local
  processing", "Not routable yet") and no Edit, so the list matches the registry; the design lists only
  routable ones.
- **AD-13 · Access, three ways (tests).** Profile entry: `scripts/test_orena_screen_admin.mjs` (present
  only for an admin, opens `#/admin/ai`). Direct address: the same gate stubs `fetch` and asserts the
  No access frame and zero requests for a learner, an unknown account and a non-boolean `isAdmin`, on
  every admin route; verified in a browser (12 combinations, en/vi/zh, both themes, desktop and touch
  phone) with `/api/me` intercepted: no request to `/api/*admin*`. `main.js` shows the frame to a
  non-admin at an admin address and keeps the internal-review notice everywhere else. Server:
  `tests/test_admin_authorization_matrix.py` enumerates every admin route from the app (60) and asserts
  401 anonymous, 403 learner, admin reaches it; the node gate cross-checks that every endpoint the AI
  screens call is one of them; one case added tying `/api/me` `is_admin` to the guard.
- **Measured (rule 42), 2026-09-30.** Computed styles of the pin (`Orena-Admin.dc.html`) vs the app,
  desktop 1920x1080, light and dark for the No access frame, light for the pages; phone 390x844 for the
  list. Left: the kit's token values (text3, green, red, dark accent, dark accent fill: D-093's AA
  values), the body font stack (the kit appends Noto Sans SC), content-driven widths and heights, the
  provider tile colour (AD-7), the toggle knob's shadow (`--sh1` instead of a literal), and the search
  field's font (the pin's input inherits nothing and renders Arial; the app inherits Outfit). The pin's
  tab buttons are unreset browser buttons, so their 1px 6px padding is drawn as the pin renders it.
  Every other radius, padding, gap, size, weight, letter-spacing and fill of the shell, page header,
  tabs, rows, pills, buttons, banner, blocks, key/value, state, metric, form, seg, toggle and No access
  frame matches. Browser-checked in en/vi/zh, both themes, at 1920x1080, 1366x768, 390x844 and 360x740
  (touch): no page scroll or horizontal overflow on any of the five pages, no page error.

## Platform Admin slice 2: Reading pipeline, Imports, Content (Orena-Admin.dc.html A8-A17, A21-A23, A28-A30, D-101 E), 2026-09-30

Built on the existing Admin backend and client; no admin API was added. The shared rules moved out
of the old console into `capabilities/admin-reading.js`, `admin-imports.js`, `admin-content.js` and
`admin-tray.js`; the old console imports them (`admin/reading.js`, `imports.js`, `content.js`,
`tray.js`) and its gates pass. D-104 is applied to slice 1 as well (see below).

- **The real loop, on :8021 (2026-09-29/30), through the new Admin UI, real endpoints, real AI.**
  1. Add: `#/admin/reading/add`, text, English, rights answered "Allow" (the Townsend translation of
     _The Lion and the Mouse_, Aesop's Fables, Project Gutenberg eBook #21, public domain in the
     United States; source URL and licence note entered). `POST /api/admin/reading/jobs` -> 202, job
     `889c0ac8-b84c-4aec-9f2e-77f11a39b1ff`; the tray followed it to completed / `article_created`.
  2. Review: article `b483bd10-e42a-4f42-8dd4-d60a84465e5e` (`needs_review`, level C1, 133 words),
     rights pills Republish Allow / Adapt Unknown / Automation Unknown / Attribution Unknown. Two
     targets kept (`POST .../articles/{id}/targets/{target}` x2).
  3. Publish: `POST .../articles/{id}/status` `published`. Attribution was never confirmed, so the
     dialog listed that warning; Publish stayed enabled and the audit records the override
     (`publication_warnings`). Status then `published`.
  4. Comprehension set: `POST .../articles/{id}/comprehension-sets` (`support_language` vi) -> set
     `996f0f65-a107-477b-b515-195d11d31284`, 4 questions, model `gemini-3.5-flash-lite` (the bench's
     configured provider; one article, one generation). `POST .../comprehension-sets/{set}/status`
     `needs_review`, `POST .../questions/{q}` `approve` x4, `POST .../status` `approved`. A decided set is
     frozen (the database's rule, shown as disabled controls).
  5. Learner: `GET /api/reading/practice/articles/{id}` serves the approved set (`status: approved`,
     4 prompts, `support_language: vi`). `#/content/article:{id}` opens the article (Aesop (trans. George
     Fyler Townsend), C1, 1 min, "Practice this text"); `#/read/article:{id}/check` is Check Understanding.
  6. **Caveat, for the human.** The bench answers `submit_enabled: false` (the runtime flag
     `ORENA_READING_PRACTICE_SUBMIT` is off on :8021), and Check Understanding then draws its "Practice
     answers aren't being saved yet" notice instead of the questions. With only that one field overridden
     in the browser (the questions are the server's), Check Understanding shows "question 1 of 4 - What woke
     the Lion up from his sleep?" with its four options, desktop and phone. The bench needs the flag on to
     show the quiz without an override; I did not restart it (Docker was limited to the admin pytest).
  7. Vocabulary: no importable word-list source exists in the repository (`scripts/fixtures/**` are API
     fixtures and `languages/*/vocabulary_collections.json` are the built-in catalogue), so no collection was
     published. The importer's read side (preview and column mapping) was exercised on a two-row CSV that
     writes nothing; the publish path is covered by the node gate (fixture) and the old console's server tests.
     D3 notes: Reading `content -> do -> assess`: an admin can now take a real article to a served, approved
     comprehension set entirely from the new Admin; `store` / `come back` stay the learner side's. The learner
     surface for the loop is blocked by the runtime flag above, not by content.
- **Grammar Lab package import: not built, reported.** `docs/grammar_lab/INTEGRATION_DESIGN.md` is not in
  this repository (only `README.md`, `SPEC.md`, `PHASE0_DECISIONS.md` and a sample), the pinned Admin design
  draws no grammar frame, and there is no grammar store or `/api/grammar/v1/*` (D-100 point 4: it goes
  through its own architecture review). Missing, exactly: (1) the integration design document; (2) a grammar
  content store for approved points (schema, review status, provenance, alias table); (3) admin routes to
  validate an export, list and review points, and publish (with their rows in the authorization matrix);
  (4) the learner read API that replaces `CONTENT_BASE` in `product/grammar-source.js`; (5) an Admin frame
  from the design project for it. Nothing was drawn or stubbed.
- **AD-A · The queue list carries no source, rights or target count per row** (the design draws them).
  `GET /api/admin/reading/queue` returns title, language, topic, level, words, time, status; the review
  detail has the rest. Not drawn in the list; the overview's "Next in review" shows no rights pill for the
  same reason. Needs `source_name`, `rights_level` and `target_count` on `list_queue`.
- **AD-B · Rights are evidence, not a control.** The design's Rights card is an editable Unknown/Allow/Deny
  control. The engine records four answers at ingestion (`rights_state`) and has no route to change them on
  an article, so the card shows them as pills; the Add form's tri-state answers `can_republish` only
  (attribution, adaptation and automation are not asked there, so a fresh article always warns "attribution
  unknown" at Publish). A route to answer them, or two more questions on the form, is a decision.
- **AD-C · Learning targets' meaning is read-only.** The design edits a target's meaning inline; `POST
.../targets` adds a target with a meaning but no route edits one afterwards. Kept / dropped / order / add
  are real.
- **AD-D · Source pages are thinner than the design.** No per-source imported/published/rejected counts and
  no "articles from this source" list (no endpoint filters the queue by source). Rights are read-only (the
  source route changes state and polling only). Deny cannot be recorded at source level (booleans).
- **AD-E · Queue position ("3 of 7 in queue") is not drawn** (the detail has no neighbours); the back link
  names the tab the article belongs to.
- **AD-F · Books import asks for a language** (the design draws none; `POST .../imports/books` needs
  `learning_language`); media links and uploads ask the same. The design's sample-file shortcuts are
  prototype fixtures and are not drawn.
- **AD-G · A book's opening text and reader counts, a media item's pipeline steps and play counts** are not
  in the detail responses, so the design's "learner preview", "readers", "plays" and transcript-pipeline
  steps are not drawn; the learner link (built for `/next`, not the server's old-UI address) and the
  transcript segments are.
- **AD-H · Vocabulary publishing.** The design says publishing is blocked until every check passes. The
  server (`POST .../vocabulary/{id}/publish`) refuses only an unattested request; rights and completeness
  warn and are recorded with the decision. The page states the server's rule ("How publishing is decided"),
  shows the three checks as Pass / Warns / Required, and keeps Publish enabled once the attestation is
  ticked. If the human wants the design's hard gate, that is a server change.
- **AD-I · Curated media has no lifecycle actions** (`actions: ['preview']` only), so the bench's six
  curated items show details and transcripts with no buttons; imported media would show Unpublish, Archive
  and Reprocess.
- **AD-J · Jobs have no title or source** (the job list and detail carry the job type and stage only), so a
  job is named by its input kind. The tray keeps the title the operator typed, in memory, for the session.
- **AD-K · History is per domain** (Books, Media, Vocabulary); Reading jobs page separately. The design
  marks the unified timeline Future and the page says so.
- **D-104 applied to slice 1.** AD-6: the banner is now a compact status line, "Saved · learner evaluator
  still uses legacy routing." (en/vi/zh), shown only while `learner_runtime.mode` is not `capability` or
  `policy.learner_runtime_uses_capability_config` is false, and it disappears when learners consume the
  route; the save toast says the same while it is true. AD-7: approved (accent tiles). AD-8: the rail link
  reads "Back to Orena" and the phone header has a compact back button. AD-1/AD-2: no fingerprint or last
  four is stored or shown. Provider detail now shows last success, last failure and its error class from the
  recorded AI operation events when they carry a time. Still not available from any existing record: the
  credential's updated-at timestamp and provider connection-test history (a connection test is audited but
  not readable through an existing endpoint); nothing was added.
- **Tray.** Drawn as the design draws it (fixed bottom right on a desk, full width on a phone, collapsible,
  "Finished items clear themselves after a short while"). It follows Reading jobs, the only long-running
  admin work; comprehension generation is one request and shows its own "Generating..." state.
- **Measured (rule 42), 2026-09-30.** Computed styles of the pin vs the app, desktop 1920x1080, light:
  Content home tiles, Reading overview tiles and actions, queue head/rows/search/level chips/row actions,
  Add content frame. What is left: the kit's token values (text3, green), heights that follow the sample
  text, the mono tile colour (AD-7), the browser default font size on the pin's unreset buttons. The pin
  draws A8, A15, A16 and A21 by hand, so those pages carry its own h1 line-height and sub spacing, and A15's
  14px-padded actions. Browser-checked (desktop 1920x1080 and touch phone 390x844, en/vi/zh, light and
  dark) on 18 addresses: no page scroll or horizontal overflow, no page error; access: 17 addresses x
  desktop and phone for a non-admin, zero admin requests.

## I. Orena Intelligence (D-085) - after the merge (PR #69) and live on :8021, rewritten 2026-10-04

Source: `docs/project/INTELLIGENCE_RECONCILIATION_D4.md` (findings F-1..F-12, opportunities F-O1..F-O4) read against
`codex/work` after PR #69, and the live checks of `docs/reviews/ORENA_AGENT_LIVE_8021_CHECKPOINT.md` (D-125). The agent's
tool plan is `writing_coach/agent/tool_plan.py`; `tests/test_agent_capability_registry.py` fails if a gap tool below is
missing here. Nothing here is built by inventing a service.

**State.** The agent is merged into `codex/work` and LIVE on the lane runtime :8021 only (`AGENT_ENABLED=true`, Admin › AI
legacy selection Gemini `gemini-3.5-flash-lite`). The client follows `GET /api/agent/capabilities` (404 hides Orena; no
client switch). :8011 is deferred (D-102); production never serves the agent; public activation is a human gate.
14 capabilities answer; the agent writes nothing learner-owned (two usage rows per turn).

### I-A. Gap tools (no backing service)

| # | Tool | What is missing | Who decides |
| --- | --- | --- | --- |
| I-1 | `get_learning_weaknesses` | Built (counts only, Slice 3). Missing: strengths, trends, grammar (no mistakes per grammar point). | Product |
| I-2 | `get_tone_analysis` (zh-CN) | No measured tone; the provider's syllable tone is only the reference label (D-084). | Human: a tone provider [PROVIDER] |
| I-3 | `get_stress_analysis` (en) | No per-word stress; one overall prosody score, off by default. | Human [PROVIDER] |
| I-4 | `get_grammar_mistakes_summary` | No store of mistakes per grammar point; essays keep heuristic categories. Waits for the canonical Grammar Store (F-3). | Product + Grammar Store |
| I-5 | `get_reading_mistakes` | No public read of wrong answers across attempts. | Reading owner |
| I-6 | `get_word_context_in_reading` | No sentence-around-a-word read by content id; the client may send the sentence as `selected_item.text`. | UI lane or Reading owner |
| I-7 | `get_listening_mistakes` | Dictation comparison runs in the client; no server mismatch list. | Listening owner |

### I-B. Reconciliation findings, current state

| # | Sev | Finding | State 2026-10-04 |
| --- | --- | --- | --- |
| F-1 | P2 | PostgreSQL agent test could not pass on D4 | Fixed: the test writes a server `score` (`tests/test_agent_tools_postgres.py`). |
| F-2 | P2 | Client-sourced dictation scores stated as facts | Fixed: `verified` from `score_source`; unverified numbers left out of counts and evidence. |
| F-3 | P2 | `navigate grammar.point` carried R5 ids | **Decided:** `grammar_id` is a Grammar Lab point id (D-100), contract §6.1. Until the canonical Grammar Store/API serves points the UI leaves `grammar.point` out of `supported_intents` (§3.1), so no grammar point is navigated to. The agent's grammar tools still read R5 knowledge; mapping to Grammar Lab ids lands with the store. |
| F-4 | P3 | "N words due" may exceed what Review shows | Watch: the agent says "due now"/"tomorrow"; it must not promise "N cards today" while the daily caps are client-side. |
| F-5 | P3 | Imported or personal media invisible to the agent | Open: Listening tools resolve curated catalogue lessons; an imported `media:<id>` answers "no such lesson". `stored_media_entry` could serve it. |
| F-6 | P3 | An agent session survives a language switch | Open: the session is keyed by learner only; each turn is still language-checked (409). |
| F-7 | P3 | Agent `usage_events` not in the deletion enumeration | Open for the deletion workflow (no content in the rows). |
| F-8 | P3 | Stored reviews may predate evaluator v2.7 | Open: the tool does not tell the model a review may be older than the current evaluator. |
| F-9 | P3 | Content-id namespaces unreconciled | **Decided and built:** `content_id` is `<kind>:<id>` (`article:`, `book:<id>:<chapter>`, `media:`), contract §6.1. Listening and Dictation send `media:<id>`; the agent's Listening tools accept it (a bare id still reads); the UI maps it back to its route id. |
| F-10 | P3 | Speaking persistence change (audio-free takes) | Watch: re-check `speaking_progress` and pronunciation history when it lands. |
| F-11/12 | Info | Shared-file footprint; working tree mid-change | Resolved by the merge (PR #69, `684b011`). |
| F-13 | P3 | "What is this screen for?" answered with recommendations | Open (Intelligence lane): live on :8021 2026-10-04, `listening.dictation` with its published purpose in `context.screen.purpose`, Gemini flash-lite called `get_recommended_next_activities` and described the app generally. The purpose reaches the server (`agent/prompts.py:_screen`); app-help routing/prompting should answer from it. |

### I-C. Contract actions and payloads

Resolved by contract v2 (D-092) and served: words are `{text, lang}`, takes are a client `take_ref`, `say_again` names the
line, `start_review` is `due` or one word, `add_word_to_collection` names a deck or library collection. Still missing: a
pronunciation attempt read by id (N-9) for `get_pronunciation_attempt`/`compare_with_model`; `play_user` plays only the
client's own recording (no take audio is stored, by design).

### I-D. Provider layer and activation

| # | Item | State |
| --- | --- | --- |
| I-17 | Capability keys `agent_turn_fast`, `agent_turn_deep` | Reserved; the agent routes on the Admin › AI legacy selection until a reviewed activation makes them configurable. On :8021 that selection is Gemini flash-lite; it never runs on a local model. |
| I-18 | Streaming and native tool calls | Verified live on Gemini (OpenAI-compatible stream, tool call → tool result → segments → done, usage reported) on :8021, 2026-10-04. |
| I-19 | Live speech, TTS, ephemeral tokens | Not approved; voice stays interfaces only [PROVIDER]. |
| I-20 | Metering | `agent.turn` and `agent.tokens` per turn; `budget_state` always `ok`, no `metered` event in V1. Telemetry prices each round (9 rounds, USD 0.008 on 2026-10-04). |
| I-21 | Provider fallback | None automatic; a failed provider ends the turn with `retry`. |
| I-22 | Legacy route health | No cooldown; a failing provider fails each turn with `retry` until the operator changes the selection. The plan's request quota is an activation decision. |
| I-23 | Identity answers | Resolved: who-are-you questions answered as Orena from copy, no provider named. |
| I-24 | Rate limit per learner | In process per worker: 12 turns and 60 capability reads a minute; verified live (429 `rate_limited`, `Retry-After`). A shared limit across workers is a deployment decision. |
| I-25 | Capability status | 14 capabilities served on :8021; `speaking.pronunciation.tone` and `.stress` stay pending (I-2, I-3). |

### Admin: Reading rights gate and queue (D-105 point 5, 2026-09-30)

Resolved by the human's D-105 decisions; AD-A, AD-B and AD-H above are closed by this section.

- **AD-A closed.** `list_queue` now returns `source_name`, `rights_level` (the effective `can_republish` answer:
  allowed / denied / unknown) and `target_count` (targets not rejected) per item. The review tab draws
  Article (source in the meta line) | Level | Targets | Rights, as A16 does.
- **AD-B closed, and copyright is a hard gate (D-105 a).** `POST /api/admin/reading/articles/{id}/status`
  refuses `published` with 409 `reading_rights_not_cleared` (context: the blocking questions) unless
  `can_republish` is allowed, and, for an adapted text, `can_adapt` is allowed. An unanswered question
  refuses as a denial does. Attribution stays advice (it is an obligation, not a permission) and is
  recorded beside the decision. A refusal is audited as `admin.reading_article_publish_refused`.
  New route `POST /api/admin/reading/articles/{id}/rights` (`can_republish`, `can_adapt`,
  `attribution_required`, `license_note`, `reason`; a field left out is untouched, `null` returns a question to
  unanswered). The source snapshot is immutable (a PostgreSQL trigger refuses a rewrite), so an answer is
  appended as a `rights_set` review event and the effective rights are the snapshot with those events
  folded over it; no schema change. `source.rights` stays as ingested, `source.rights_state` is the
  effective state, `rights_review` says who answered last. The review page states the refusal, disables
  Publish, and edits the three questions; the Add form now asks `can_republish`, `can_adapt` and
  `attribution_required`.
- **Effect on existing content.** Already-published articles are untouched. An article imported with no
  rights answers can no longer be published until its questions are answered; the earlier lane-runtime
  articles published with unknown attribution stay as they are.
- **AD-H closed (D-105 b).** The vocabulary page states the server's rule only (unattested is the one
  refusal; rights and completeness warn and are recorded). Nothing in the UI claims a stricter gate: the
  only disabled state is the missing attestation, which the server also refuses.
- **Still open.** `automation_allowed` is a source-level question and is not edited per article. The
  overview's "Next in review" rows show the source in their meta but no rights pill (the shared row list
  has no pill slot).

### D4 slice 1: account, profile, level (2026-09-30)

- **Stored now.** `declared_level` (per learning language, registry-validated, no English fallback), review settings
  (`review_new_per_day`, `review_limit_per_day`, `review_modes`), and the account scalars `learning_language`,
  `interface_language`, `weekly_goal_days` behind one opaque `settings_version` (`GET/PATCH /api/account-settings`).
  Bootstrap gains `language.stored`. The session is seeded from the stored language only when it has none.
- **H-19.** Today draws the design's Banner ("Choose level" / dismiss) for an existing profile with no level. The
  action opens the onboarding Level step alone (`#/welcome?step=level`) and returns to Today. Skipping lasts the visit
  (session storage); no dismissed marker is stored, as the proposal requires.
- **Decided (human, 2026-09-30): HSK 7-9.** One `HSK 7–9` cell after HSK 6 in the Level step (onboarding and the
  H-19 level-only step, the only places a level is chosen), code `HSK7-9`; never three HSK 7/8/9 cells. The grid's
  default stays the middle of the frame's six (HSK 3 / B1).
- **Decided (human, 2026-09-30): review modes.** Canonical identifiers are `typing`, `cloze`, `dictation`. The
  proposal's `target` is the Review frame's "Target -> meaning", i.e. `typing`; the Review screen's mode enum now says
  `typing`. `PATCH /api/learner-profile` refuses (400 `invalid_value`, field `review_modes`) any other key or a
  non-boolean value instead of dropping it silently.
- **No weekly-goal control yet.** `weekly_goal_days` is stored and served; the design draws no control to set it in
  Settings or Profile that this slice found. It is not invented (rule 43); slice 7 decides where it is read.

### Admin: Reading overview rights and automation override (D-106, 2026-09-30)

- **READING-1.** The overview's "Next in review" rows draw the same effective rights pill as the Review
  queue (same `list_queue` item, same `rightsPill`); the rights form is not duplicated there.
- **READING-2.** `automation_allowed` on a source is a default. `POST .../articles/{id}/rights` also takes
  `automation_allowed` (`true`/`false` sets the article override, `null` clears it), recorded as a
  `rights_set` review event and audited; no schema change. One computation, `effective_automation()` in
  `reading_content_repository.py`: the article override when present, else the source default. It feeds
  the article payload (`automation`: allowed, override, source_default, origin), `rights_state.automation_allowed`,
  the queue item (`automation_allowed`), and the publish audit record (`automation`). The review page
  edits it (source default / Allow / Deny) and states the effective value and its origin.
- **Open reading of "publish uses the effective value".** Publish records the effective value; it does not
  refuse on it (manual articles from a source whose default is "no" would otherwise never publish). If
  the human means a refusal, it is one line in `set_article_status`.

### D4 slices 2-7: what changed for the UI and what is still open (2026-09-30)

- **Streak (I14, H-5).** `GET /api/learner-activity?tz=&days=` derives the streak and the ISO week's active days from
  essays, speaking attempts and Reading attempts, by the learner's own calendar day; no table; a visit never counts.
  Dictation, Shadowing and vocabulary review are listed as `pending` (they keep only a last-update time). Profile
  and Today draw it; the daily-goal ring, the minutes tile and stat, Today's goal ring, skill rings and level card
  are **not drawn** (D-103.4), and Profile's weekly bar is drawn only against a target the learner set. No design
  control sets that target yet (`weekly_goal_days` is stored and served). H-16 stays open.
- **New token.** `--hero-day-done` (#A99BFF), the design's active-day colour on Profile's hero strip.
- **Dictation (I18).** The stored score is the server's; the screen replaces its instant mark with the acknowledged item.
- **Continue (I4).** Today, Discover, Content, Practice, Listening and Reader read the merged list (server places first,
  device entries the server lacks). A conversation entry now opens the Conversation room by id.
- **Backbone-dependent (I5, I6, I8-I10, I12).** Written only while `/api/account-backbone` is `active`. Not driven in a
  browser yet, because the backbone is off on the lane: the lead's flag flip is the gate.
- **Still open, no storage decision missing.** Register/target length (H-7); conversation coaching in the turn vs
  regenerated (H-8, the turn keeps `meaning`/`support` only); History listing typed responses (H-9); spoken Free
  Talk/Situation/React takes as audio-free speaking attempts (needs Progress to skip null pronunciation first); the
  Import sheet has no `url:` text flow; shadowing read-back on open (I16, D7).
- **Required Speaking follow-up (human, 2026-09-30).** Spoken Free Talk, Situation and React takes stored as typed
  responses are not the accepted Speaking model: spoken takes belong in speaking attempts. Reopening Shadowing must
  restore its saved result. Speaking persistence is not complete until both are done.
- **Grammar quiz progress** waits for the canonical Grammar API after PR #67; no temporary route (human, 2026-09-30).
- **Lane test residue (:8021, documented, not erased).** The D4 browser pass left the account's stored
  `learning_language` = `en` (it was empty; the API cannot store empty) and one continuation row for
  `media:en-science-cosmic-calendar`. Test evidence; the database is not hand-edited to remove it.

### D4 review follow-ups (2026-09-30)

- Saved is the `kept` relationship: opening content writes a place row that never reads as a bookmark (Reader and Content
  Detail read the `kept` row only).
- Opening an old Chinese essay draws the stored review at once; a refresh runs in the background and repaints the review.
- In authentication-disabled development `language.stored` is false until the first settings write creates the local
  account's row; the entry rule that keys on it therefore asks for Welcome once.
- Open for the human: per-account caps for place rows, responses, annotations and conversations (P2-4); a streak is per
  learning language, so a bilingual learner has two (P3-5).

### Imported media opens in Listening (D4 runtime acceptance 1, 2026-10-01)

- **Fix.** `product/media-source.js` resolves a media id the way the old Encounter did: `url:<link>` is re-acquired
  (`capabilities/media-acquisition.js`), `upload:<id>` is read by identity (`GET /api/media/my/<id>`), any other id is a
  curated or stored lesson (`GET /api/listening/library/<id>`, which also answers a bare personal `media_id`). Listening,
  Content Detail and Respond use it. No backend change.
- **Not drawn: a source with no transcript.** An uploaded file, or a link whose provider returns no captions, opens the
  player with an empty transcript region and no explanation, because the design draws no source-only state for Listening
  (the "Preparing transcript" copy belongs to the Import sheet's processing step). Human decision: a drawn source-only state.
- **Not drawn: unmeasured length.** A provider that reports no length shows the elapsed time without a total; the clip end
  is the last transcript line when there is one.
- **Done (D4 runtime acceptance).** The import membership (`mediaImports`) is kept with the account through `/api/imports`
  (forms `url` and `upload`, a record id minted when kept; removing removes every record of that link or file) and a new device lists it, per learning language. A personal upload is resolvable by its
  unguessable `media_id` only; the server does not check account or language on that read (listing is device-scoped per
  language). A `url:` item is re-acquired from its provider on every open (the Import sheet already did one), so it depends
  on the provider answering; Dictation, Shadowing and React for a `url:` item are not offered (no stored lesson id).

### D4 runtime acceptance, human-directed fixes (2026-10-01)

- **Removals hold across devices.** The account remembers up to 500 removed annotation ids per text (newest kept); a stale
  device loses them on open and cannot write them back (422 `annotation_tombstoned`, or a re-read and merge on 409). This also
  closes the quick-tap race (a highlight removed inside the push delay is not brought back by a pull). Consequence: an id
  that was cleared or removed is never reusable; ids are minted once, so no learner action meets it.
- **Review settings follow the language.** A partial review PATCH merges into the stored modes; the toggle sends only the mode
  it changed; switching the learning language brings the new language's profile, version and review settings over before the
  repaint (`adoptLearningLanguage`).
- **Kept words remember where they came from.** A word or phrase saved from the new sheets writes a provenance occurrence
  (source kind and id, sentence). The Listening vocabulary-sheet and phrase save paths belong to the parallel Listening work
  and are not wired yet.
- **Deleted legacy imports scrubbed (human-approved).** `scripts/scrub_deleted_imports.py` (dry run by default, idempotent,
  counts only). On :8021 it found 2 deleted imports, both already tombstoned: 0 scrubbed (backup taken first). Left untouched
  and reported: 2 saved place rows still name a deleted import; annotations and responses of a deleted import keep their
  excerpts (deleting an import does not delete what the learner wrote about it).
- **Import rows are bounded.** Live imports stay at 20; all import rows including tombstones are bounded by
  `ORENA_LIMIT_IMPORT_TOMBSTONES` (default 360, floor 52, refused at startup below it). A work cannot be created already
  deleted on the generic route. Imports (text, link, file) share this bound.
- **P3 follow-ups, not done:**
  - The Conversation End state is not persisted (it is rebuilt from the turns).
  - A stale cached deleted import can still be opened from a device that has not refreshed its list until it syncs.
  - Draft conflicts: `onElsewhere` is a no-op while `draft-sync.js` documents a chooser; no chooser is drawn.
  - The mic-blocked Free Talk copy is incorrect for a browser that blocks the mic by policy.
  - `media_thumbnail.py:32` hardcodes `_TEMP_ROOT` (an environment-specific path); belongs to the media agent.

### D4 delta review conditions (2026-10-01, review of 8c84100 / 39b9f12 / 9a7b190)

- **Decision for the human: media-import bound (review P2-1).** URL and upload media imports share the import
  bounds derived for text imports (20 live, 360 total incl. tombstones, `ORENA_LIMIT_IMPORT_TOMBSTONES`). At the
  bound a media import stays on the device only. Whether media imports count per form or the shared rails are
  confirmed is a learner-facing limit nobody has chosen; not decided by an agent.
- **Before :8000: deleting an upload import leaves the personal media (review P2-2).** The original file,
  thumbnail, transcript and store entry stay in the media library and no learner route deletes them. The file-based
  media store (`MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`) must join the D-055(b) deletion enumeration
  (`writing_coach/persistence/deletion_enumeration.py` lists database tables only today).
- **Owner-less personal uploads (review condition 3).** :8021 runs without sign-in (bootstrap `mode: local`). It
  holds 11 personal uploads, 8 created before 39b9f12 with no owner; all are lane test data and stay visible to the
  local account only. On a signed-in deployment such uploads are refused to every account (fail closed); none are
  known outside the lane.
- **P3 from the review, follow-ups:** the `upload` import form stores an unvalidated `url`; the scrub script's
  backup precondition is documentation only and `--url` takes a connection string on the command line; an empty
  `review_modes` map no longer resets modes; an annotation tombstone is forgotten after 500 further removals in one
  text (a long-offline device could then re-add it); keeping a word from Listening (vocab sheet, phrase save) does not
  yet record provenance.
- PostgreSQL-only test results in this work are local execution, not CI evidence (CI has no PostgreSQL service).

### D4 flag-on QA round 2 (2026-10-01, :8021 at 9a7b190)

- **Decision for the human: removing an imported item.** The server deletes an import (`DELETE /api/imports/{id}`,
  content-free tombstone), but the design draws no remove/delete action for imported content in Discover, Content
  Detail or My Library (its only "Removed from My Library" is for saved words and phrases). Not invented (rule 43);
  where removal lives is the human's call.
- **P3 (new): a device left open keeps drawing a highlight another device removed until it reloads.** The server and
  the device store are correct; only the open page is stale.

### Delete an import (D-107, 2026-10-01)

- **Where.** My Library > Saved content lists the learner's own imports (text, link, file) first, each with the design's
  "⋯" and its menu row (frame 14's overflow pattern, `kit/overflow.js`); the same "⋯" is in the import's Content Detail.
  Both hold one action, "Delete from Orena" (en/vi/zh). Discover offers none. A result toast ("Deleted from Orena") uses
  the design's toast.
- **Not drawn, recorded for the human.** The pinned design draws a "⋯" only in the Reader, and draws no "⋯" in My Library or
  Content Detail; it draws no destructive item style and **no confirmation** for any destructive action (the only
  deletion it shows, "Delete audio", answers with a toast "Audio deletion would be confirmed here"). None is invented:
  the action runs on the tap, in the neutral pill style, with no confirmation and no undo. A deletion of an uploaded file
  cannot be undone. Human decision: a drawn confirmation (or an Undo window) for a destructive delete.
- **Lifecycle.** The account keeps a content-free tombstone (id, form, and for a link or file a hash reference); an
  uploaded file's original, thumbnail and index entry are deleted for their owner in this language only (404
  otherwise); a link's external source is never touched. A deleted id is never reused or revived by a stale write. A
  device that learns of the deletion (every sync, and when My Library, Discover or Content Detail opens) drops it and
  never opens it again; a deletion made while offline is sent again at the next sync. The earlier P3 "stale cached
  deleted import" is closed. The file store is in the D-055(b) enumeration (`FILE_STORES`).
- **Left.** Notes and highlights the learner wrote on a deleted text stay in the device store and the account's
  annotations row (unreachable, but not erased); a deleted upload's per-take history (dictation/shadowing progress) is not
  erased. A link that cannot be re-acquired from its provider opens the load-error room, which offers no "⋯" - such an item
  can be deleted from My Library. Account-level removal of all media files on account deletion has its remover
  (`delete_all_owned_media`) but no workflow calls it yet (D-055).

- **Review f8f5c91 fixes.** A file removal that fails is retryable: the tombstone keeps the opaque stored-media id as
  `mediaPending` until the files are confirmed gone (files first, index entry last), and a repeated delete, a replay or
  the next `GET /api/imports` finishes it. `GET /api/imports` returns every tombstone (up to 2,500), not the newest 50.
  A device resends a deletion only for the account record ids it deleted (by record id and version); a record another
  device made later is never deleted and clears the device's removed marker. An upload that never synced is deleted from
  the server store too (owner-scoped; it stays while another live import of the account names it). The removed set is per
  owner and language. Still open: P2-5 (derived records) goes to the human; P3-1 (a link `ref` is a guessable
  fingerprint), P3-2 (receipts keep a content-derived digest until account deletion), P3-3 (tombstones made before
  `f8f5c91` have no `ref`), P3-5 (the Reader keeps its own overflow styles), P3-6 (an upload whose index write is refused
  leaves its files) and P3-8 (the server `kept` mark of a deleted import).

- **Delta check 02511cc.** A deletion made before the device's first list read of a session (offline at load, a failed
  first sync) is no longer reverted. A text import's own record is always owed; for a link or file, `GET /api/imports`
  now returns each record's change `sequence` and a `highWater` position, the device keeps the position of its last
  successful read, and at the next sync a live record made at or before the position at which it deleted is the one it
  deleted (resent), while a later one is another device's re-import (the import is the learner's again). A failed list
  read learns, settles and reinstates nothing. Reinstating keeps an older record's unconfirmed delete owed. An uploaded
  file's stored copy is retried until confirmed; `DELETE /api/media/my/{id}` answers 503 (not 404) for an index it cannot
  trust. A list read finishes at most five owed file removals. Limitation: a device that has never completed a list
  read has no position, so a record that exists only on the account is treated as a re-import. Left for the limits
  implementation: the 2,500 deleted-list cap should be derived from the configured text and media pool totals (360 +
  2,500), and the full list wants an ETag or a `since` (up to about 375 KB per sync); a missing `index.json` with files on
  disk is still read as a fresh start (P3-3).

- **Review 94da741 (D-109): blocking items closed.** (B-1) Deleting a text import erases, from the account's kept words in
  that language, every stored sentence that occurs in the deleted text (case and spacing ignored, 12 characters or
  more), whatever the word's provenance; the repository serves no sentence for a word whose only places are deleted
  imports (`PostgresSpecializedLearningRepository._served_fragment`), which every reader of a kept word goes through
  (library list and detail, word cards, collection snippet, review cloze, word deep dive - so a deleted import's
  sentence is never sent to the AI provider). A sentence shorter than 12 characters is not guessed at. (B-2) Notes and
  highlights filed under a link or file import's content id (`url:`, `upload:`, `media:`, `upload-<token>`) get the same
  404 on read and write and are erased at delete time.
- **Follow-ups recorded, not done (D-109):**
  - Two tabs of one browser can commit each other's open Undo window (the device store is last-writer-wins).
  - `pagehide` is not fired when a mobile tab is merely backgrounded; the staged deletion is then committed at the next
    load.
  - `highWater` should come from the first page of a multi-page read (a record created mid-read can advance the mark
    past one the device has not seen; benign today).
  - A narrow in-flight race: deleting within a network round trip of importing, before the push response records the new
    record id, can leave that record un-owed.
  - `language_provenance` is updated in place at delete time (it is an event table); note it in the schema docs.
  - The erase counts are logged only; there is no operator report of what a deletion removed.
  - The Intelligence agent tools (`/api/agent/*`, owned by that lane) must apply the same deleted-source mask when
    `codex/work` is merged forward, and `AGENT_CONTRACT` evidence excerpts must not carry a deleted source's sentence.
  - Words kept from a deleted import before this change keep their stored sentence unless a provenance row marks them
    (lane-only residue).

### Delete-import follow-ups after the 3247d02 delta check (APPROVE, 2026-10-01; secondary under D-109)

- The 12-character erase can remove a saved word's example sentence that also occurs verbatim in a live
  source; skip words that still have a live provenance row.
- Imports deleted before 94da741 keep provenance `availability = 'unknown'`, so such words still serve their
  sentence (lane data only); backfill with the scrub script before any wider deployment.
- After a link/file is re-imported, its notes cannot be kept with the account again (the erase tombstones the
  annotation row terminally); erase to an empty active payload instead.
- `_deleted_source_filter` reads every import row per annotation read/write for media ids; cache or index it
  before the media pool grows.
- The SQLite test twin does not mask fragments (test backend only); Intelligence agent tools must apply the
  same deleted-source rule when that lane next merges forward.

## Vocabulary localization (D-124), 2026-10-04

Architecture and proposed schema: `docs/project/proposals/VOCABULARY_LOCALIZATION.md`.

- **VL-1 — resolved on :8021 (2026-10-04).** `20261004_0025` promoted and applied to :8021 only
  (human authorization, pg_dump + restore check). Other runtimes must apply it before running this
  code. Original note: **Localization table not yet authorized.** `vocabulary_sense_localizations` is proposed
  (`migrations/proposed/20261004_0025_…`). Until review and authorization, support-language
  glosses can be added only to unpublished senses (in `short_meanings`); a published collection
  cannot gain a new support language.
- **VL-2 No direct bilingual data for → vi.** zh → en comes from the vendored CC-CEDICT; en → vi
  and zh → vi have no open dataset vendored. Candidates (Wiktionary/kaikki CC BY-SA, FreeDict
  eng-vie) are a human data/licence choice. Offline Marian pivot (`services/local_translation`)
  needs its models provisioned and its quality sampled before a pair is enabled.
- **VL-3 Visible CC-CEDICT attribution.** CC BY-SA 4.0 requires credit where its senses are
  shown; the pinned design draws no credit line on cards or Word Detail. Data carries
  `origin: dictionary` and provenance (source, release, licence). Placement is a design decision;
  required before public release.
- **VL-4 Unihan `kVietnamese` is not a Hán-Việt field.** It mixes Hán-Việt and Nôm readings in
  no stated order (森 → "chùm" before "sâm"), so it is not shown as Hán-Việt. A curated Hán-Việt
  source would be needed for that feature.
- **VL-5 Learner copies of a meaning.** `saved_words.translation_vi` / `definition` copy one
  language at save time and several new-UI models read them. For catalog-linked words (with
  `entry_id`) the meaning must be rendered from the sense's localization for the current support
  language (proposal §6); the columns stay as learner notes for free-typed words (D4 hold).
  Server readers checked 2026-10-04: library list, review queue/due/grading, collection
  `review_items`, save/restore all merge catalogue meanings (`_row_to_item`); learner summary,
  decks, admin metrics read no meaning; there is no server-side Agent tool or data-export endpoint
  on codex/work. Fixed: Collection retrieval snippet (now the sense's meaning for the support
  language) and PostgreSQL library search (also matches localization glosses). Accepted by the
  human: legacy `GET /api/vocabulary` (old UI) shows no meaning for such words; the SQLite test
  backend's library search covers the learner's own fields only.

## Admin: AI cost report (human request 2026-10-04)

The human asked for an Admin page with AI cost by day, by feature and by learner. The pinned
`Orena-Admin.dc.html` draws no such page: its AI area shows only a provider's "Usage · last 24 h"
(requests, failures, average latency). By CLAUDE.md rules 4 and 7, no page is invented.

- Built, backend only: `GET /api/admin/ai/costs?days=N` (1-90, admin-only). It reads the shared
  `ai.operation` ledger and returns totals by UTC day and by feature x provider x model, with a unit
  cost: per priced call, or per audio minute for speech recognition. It also returns its own gaps.
- Recorded since 2026-10-04: Groq speech recognition and Azure pronunciation scoring, with audio
  seconds and list-price cost (catalog 2026-10-04.v2).
- Open, needs a human decision or a design frame:
  - **AC-1** a design frame for the cost page;
  - **AC-2** cost per learner. The operation telemetry is anonymous by design; only Orena agent
    turns carry an account (`agent.turn`, Intelligence lane). Linking every provider call to a
    learner is a privacy decision. *Decided 2026-10-04; built 2026-10-05* (`proposals/AI_COST_PER_ACCOUNT.md`):
    code, page block and tests on `codex/work`; the table is migration `20261005_0026`, reviewed (APPROVE
    WITH CONDITIONS, conditions met) and **waiting for the human's authorization** to be promoted. Until
    then nothing is recorded and the page block says so;
  - **AC-3** the Azure pronunciation rate, to be checked against the bill;
  - **AC-4** infrastructure cost, which is not measured.

## Legal pages: terms, privacy, refund (completion plan item 5, D-128), 2026-10-05

Built at `/next#/legal/terms`, `#/legal/privacy`, `#/legal/refund` (`?lang=en|vi|zh` for review), from
the drafts `docs/legal/DRAFT_*.md` as data (`scripts/build_orena_legal.mjs` -> `static/orena/legal/content.js`;
`scripts/test_orena_legal.mjs` fails when the two differ). Drawn before sign-in, with no learner frame.
Kit pieces only (page header, section heading); "Note to counsel" and the codebase appendix are stripped;
every `[DECISION: ...]` / `[OPERATOR]` placeholder is shown as written. Open, for the human:

- **LG-1 the text** is a draft: the human approves it (a gate), then fills the placeholders in the drafts and
  rebuilds `content.js`.
- **LG-2 Chinese** has no approved text: a Chinese interface reads the English text (`lang="en"`), and the
  line under the title says so. Not machine-translated.
- **LG-3 links**: nothing links to the pages yet (after approval). The design draws no legal link; the
  candidates are the sign-in page, Profile/Settings ("⋯" or the account section) and the checkout step of
  billing. The learner router does not know `legal/*`: an in-app link must load the page (`/next#/legal/...`
  with a reload), or the router gains the routes when they are linked.

## Billing (completion plan item 4), 2026-10-05

Backend built and off (`proposals/BILLING_GATEWAYS.md`): payOS (domestic prepaid VietQR) and Polar (merchant
of record) behind one layer, order table proposed as migration `20261005_0027`.

- **BL-1 plans and checkout screen**: the design draws no plans, price or checkout page. Profile shows only
  "Plus plan" as text. A learner cannot start a checkout from the UI until a frame exists, or the human
  decides to build it from kit blocks (D-128). The API is ready (`GET /api/billing/offers`, `POST /api/billing/checkout`).
- **BL-2 renewal reminder**: domestic access is prepaid and does not renew itself. The design draws no
  reminder (a notice before the end, a new QR). It needs a frame, or a decision on where it lives.
- **BL-3 admin orders**: refunds of domestic payments are recorded through
  `POST /api/admin/billing/orders/{code}/refund`. The Admin design (`Orena Admin.dc.html`) has no orders page
  yet, so this has no screen.

## Reading batch to the design (D-129, D-130), 2026-10-05

- **RD-1 article description**: Content Detail shows an article's description only from its own metadata
  (D-130). `reading_articles` has no description field, and Admin import has no input for one, so the block is
  hidden for every article today. This needs a field and an Admin input (schema: a human gate).
- **RD-2 "Mark as known"** (Word Quick Sheet, frame 53): no endpoint marks a word known. The learning-state row
  shows for a word with a review schedule, without the action.
- **RD-3 on-request persistence**: translation, summary and contextual meaning are cached in process memory
  until migration `20261005_0028_reading_derived_texts` (proposed, `READING_ON_DEMAND.md`) is reviewed and
  authorized. They are regenerated after a restart.
- **RD-4 WordDetail `generalMeaning`** (LEX-018, D-133):
  - The server adds `generalMeaning` (string, may be empty) to WordDetail: the word's common meaning in the
    support language, beside `contextMeaning`.
  - The pinned `data-contracts/WordDetail.json` predates it and is not edited (it is design source). This
    entry is the record of the extension until a design revision carries it.
  - A gloss cached before this change has no `common_meaning`; it falls back to a support-language dictionary
    sense or stays empty until regenerated.

## Mobile QA (human iPhone report, 2026-10-06)

- **MQ-1 Continue places carry no language** (BUG-05, partly).
  - What happens: `GET /api/continue` lists the account's places without a language. On :8021 an English
    learner's Today "For you" therefore offers `怎么搜索维基百科` (a Chinese video) under Continue.
  - Why it is not fixed here: the place record is D4 learner-owned persistence (D-104, `AGENTS.md` §7
    architecture hold). Adding a language to it, or scoping the list by language, is a contract and schema
    decision for the human and an independent reviewer.
  - Rejected interim: a client filter would have to guess each place's language.
  - The rest of BUG-05 (Vietnamese copy with an English setting) did not reproduce in a fresh session. Every
    layer followed Settings, and `GET /api/account-settings` showed learning, interface and support set to en.
    It needs the device's steps to reproduce.
- **MQ-2 Microphone on a phone needs https.**
  - The app now says so instead of offering a permission loop (BUG-01).
  - A trusted https address for :8021 needs Tailscale Serve, which must be enabled for the tailnet. That is an
    admin action the lane cannot take.

## Speaking design audit (D-129), 2026-10-07

- **S-24 Conversation: the partner cannot speak first.**
  - Design (frame 30): the partner opens the chat, the learner then types or speaks.
  - What happens: the situation text stands in as the partner's bubble and the learner speaks first, because
    the conversation-turn request (`ConversationIn`) requires a learner turn; there is no way to ask for an
    opening partner turn.
  - Needed: a backend contract for an opening partner turn (no learner message) for a chosen scenario. No UI
    change until that exists; the UI must not fabricate a partner line.

## Speaking Compare: reviewing a past attempt (D-139), 2026-10-07

- **S-13a A stored attempt has no word timing and no audio.**
  - What the account keeps per attempt (`POST /api/speech/attempts`, `evidence.pronunciation`): each word's text,
    score, miscue type and sounds, plus accuracy, completeness, prosody and the heard text. It does not keep
    each word's offset/duration, the line's pace against the model, or audio (D-076).
  - Effect: an attempt only the account remembers opens in Compare with scores, word detail, sounds and the heard
    text, but its pitch plots, Timing tab and pace chip show "unavailable", and Play has nothing to play of "you".
    An attempt this tab still holds keeps all of it.
  - Needed (backend, not done): offset/duration per word in the stored evidence if past attempts should show
    timing. The UI draws nothing it does not have.
- **S-13b "Clear" on the embedded Attempt history card.** The frame's card has a Clear button for the prototype's
  browser-only history. Orena's attempts are the account's record and no delete route exists, so it is not drawn.
- **S-10a IPA alphabet is implied, not returned.** English sounds are IPA because the provider is asked for
  `PhonemeAlphabet: IPA` (en-US); the stored evidence does not carry the alphabet. A provider that labels sounds
  differently would show those labels. The stress hint line has no provider source and is not drawn.
