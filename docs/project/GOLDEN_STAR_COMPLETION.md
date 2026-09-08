# Golden Star reference completion

Status: IMPLEMENTING. Authority: current human instruction, Product Constitution,
Content Architecture and approved Orena brand. This is execution scope and its
completion ledger, not a new product constitution. Human acceptance is pending.

## Experience design

Complete the reference product by extending committed primitives. The existing
uniform headings, paragraphs and cards do not meet the Golden Star bar.
Use a persistent orientation shell with immediate Discover, intentional
Practice, Reading, Listening, Writing, Speaking, My Content, My Language and
Continue entry. Keep contextual understanding attached to the source.

Discover is an editorial spread: an invitation into the world, one prominent
real encounter, a contrasting reading invitation, purposeful practice paths,
and actual continuation. Reading is a shelf and a quiet page; Listening is a
stage with synchronized text and optional work; Practice is an intention
workbench; Writing is a desk with source and revision; Speaking is a situation
and exchange; My Language is a collection; Recall is retrieval; Continue is an
actual thread history. Different compositions share navigation, typography,
color pairs, content identities, explanations, evidence and state primitives.

Use approved illustration through the semantic brand library. No invented
content availability, progress, upcoming-feature buttons or mastery. Future
capabilities inherit explicit experience identities and composition contracts,
not a separate skill application. Motion explains arrival, selection and focus,
and respects reduced motion. EN/ZH use the same structure. Existing local-device
memory, PostgreSQL contracts and all operational holds remain unchanged.

## Implementation plan and completion ledger

- [x] Shell and multi-entry orientation: `ui/reference.js`, `product/intent.js`,
  `app.js`, `reference.css`. Add Continue as a route using continuationLink;
  route tests must reject silent fall-through. All navigation links resolve to
  existing capabilities, including direct Reading/Listening/Speaking/Writing.
- [x] Editorial Discover and Practice: `ui/world.js`, `reference.css`.
  Compose real content with contrasting scale, image, type and background;
  retain import, provenance, unavailable states and shared library filtering.
- [x] Distinct learning rooms: `ui/reading.js`, `ui/speaking.js`,
  `ui/expression.js`, `rooms.css`. Preserve API and event contracts, use quiet
  content/work zones and purposeful illustration, no large mascot in editors.
- [~] Deep journeys (Speaking blocked on ASR; explanation content on the
  provider hold): media Follow -> Dictation -> understanding -> keep ->
  Recall; Reading -> selection -> understanding -> response -> Writing ->
  Continue; Speaking situation -> own turn -> coaching -> writing; Grammar ->
  example -> understanding -> My Language. Exercise available paths in browser;
  label provider/hardware-limited steps honestly rather than simulating success.
- [x] Completion findings: all three **closed** - Recall answer exposure (P1),
  Writing revision classification (P1), long-turn contextual explanation (P2). See `CAPABILITY_DIRECTION_REVIEW.md`. They do not replace this mission.
  Correct within the relevant experience and validate before acceptance.
  - Recall: `blankContext` returned the passage split on the phrase and rejoined
    with it, so every occurrence after the first was printed back; it now
    returns the segments between occurrences and a surface renders a blank at
    each boundary. Separately the say/reuse/meaning branch printed the source
    sentence whole while the heading above it was hidden, which handed over the
    answer it was concealing. Both paths now share one `withheld()` renderer, so
    the sentence is masked whenever it contains the phrase and restored on
    reveal, in EN and ZH. Verified against the finding's own input in the
    running module, and through the reveal cycle in the browser.
  - Writing revision: `revision_delta` paired issues by category using `next()`
    over a set, before exact matches were preserved - so with previous grammar
    A/B and current A/C it could report A removed and A new while pairing A to
    C. Exact common issues are now settled first, and a revision is claimed only
    where the correspondence is unambiguous: exactly one unmatched issue on each
    side of a category. Several on either side are reported as gone and arrived
    rather than paired on a guess. The finding's own case now returns A
    persistent and B changed to C, identically under PYTHONHASHSEED 0/1/2/3/42.
  - Conversation context: asking about a turn sent the first 2400 characters of
    the preceding and current turns joined, so a preceding turn long enough to
    fill the budget evicted the very turn holding the selection, and the server
    refused it. `turnContext()` now budgets around the selection: its own turn
    is never trimmed, and the room left goes to the end of what came before,
    nearest the selection. Verified against the running server - the old
    construction returns 422 "Selected text must come from the supplied learner
    context", the new one returns 200.
- [x] Validate Node contracts and ESM, project-memory and architecture gates;
  run CI-defined Python gate when Docker ownership is established. Evaluate
  light/dark, EN/ZH at 390, 800, 1440 and 1920 widths in the actual browser.
  Check keyboard, overflow, readable ink, truthful states and route restoration.
  Done: all gates green; 390/800/1440/1920 swept with no overflow, nothing
  escaping the viewport and no sub-24px target; 800 swept across all eleven
  routes in both themes (22 combinations, zero problems, body ground painted in
  both); EN and ZH both exercised.
- [ ] Record evidence, extend ORENA_WEB_EXTENSION_GUIDE with reusable rails,
  update current status and checkpoint explicit files. Present browser-reviewable
  result. Only the human may establish Golden Star acceptance.

## Functional core: what is real, and where the boundary is

Established by driving the running product in a browser, not by reading code.
Each line below was exercised as a learner would.

**Real end to end, no provider required.**

- *Listening / Follow* - playback advances the active segment; seeking moves it;
  clicking a transcript segment seeks playback to it; changing speed keeps
  synchronisation (1.5x advanced 5.2 media-seconds in 3.5s wall time with the
  active segment still correct); replay returns to the line being worked on.
  Each segment is one block carrying its own support-language meaning.
- *Dictation* - hear, reconstruct, compare, see the perception gap, reveal.
  Dropping one word from the target line produced the hint
  `With the big **** starting the...` and a comparison reading 94% with
  "Not heard: bang". Reveal is a separate action. Evidence is recorded.
- *Learner continuity* - keeping a phrase from inside the reading explanation
  wrote provenance to device memory (origin, where, why, the exact sentence)
  **and** the word to the account library; My Language then showed it as "From
  something you read - The last train home" with a route back; Continue listed
  the real threads that activity produced; Recall withholds the phrase until
  reveal.
- *Reading* - a real passage, genuine text selection, and inquiry carrying the
  exact selection plus the sentence it sat in.
- *Writing* - draft persistence ("Draft kept on this device"), required level
  targeting, revision recording and truthful comparison.
- *Shell* - across all eleven entry routes, zero dead controls: every button
  has a handler. No horizontal overflow and no sub-24px target at 390, 800,
  1440 or 1920; at 800 all eleven routes were checked in both themes, 22
  combinations with nothing escaping the viewport; content occupies 88% of a
  1920 viewport, so there is no dead desktop margin.
- *EN/ZH parity* - the same Dictation flow in Chinese masks one unit per Han
  character: dropping 输 from 你可以输入你找的内容 gives 你可以*入你找的内容.

**Rooms given real structure or a stated boundary in this run.**

- *Grammar* - two layers instead of one flat wall. Six levels holding four to
  seven named families each, read from the syllabus the data already declares,
  with real counts and a real line from each family; entering one opens the
  catalogue narrowed to it. The catalogue keeps search and the level filter and
  stays closed until asked for. Nothing is recommended or marked as learned:
  `completed` is false throughout and every completion policy is named
  "not_mastery", so no such evidence exists to claim. Chinese resolves to its
  own seven levels and twenty families through the same contract.
- *Speaking and conversation* - both rooms ask `/api/speech/status` before
  inviting a take. Where no provider is attached the recorder is disabled with
  the reason stated, and the typed reply, sending and conversation paths stay
  open. The check fails open, so an unreadable answer never hides a working
  recorder.
- *Recall* - asks its own question ("Does it come back?") rather than repeating
  its navigation label, and its card holds the 760px measure it always asked
  for.

**Provider holds - implemented and wired, content unavailable in this runtime.**

These are not gaps in the product. Each path reaches its capability, and each
reports the boundary truthfully rather than simulating a result. Activating a
paid provider is a human gate, so they are recorded rather than resolved.

- *Contextual explanation* - `POST /api/dictionary/contextual` answers
  `{"available": false, "claim": "contextual_dictionary_unavailable"}` and the
  panel says "This explanation is unavailable right now. Nothing has been
  guessed in its place." This gates explanation **content** for Reading,
  Writing, Grammar and Vocabulary alike; the shared surface, the origin it
  carries and the follow-up questions are all real.
- *Writing evaluation* - `POST /api/evaluate` answers 503
  `evaluation_unavailable`, and the room renders "Feedback is currently
  unavailable. Your writing is still kept on this device." in EN and ZH.
- *Speech* - `GET /api/speech/status` reports `configured: false,
  provider: null`, so record -> ASR -> spoken evidence cannot run here. No
  pronunciation evidence or audio analysis is invented in its place.

The consequence worth stating plainly: the learning loops that need no provider
are genuinely usable now, and the ones that need one are complete up to the
provider call. What this runtime cannot show is generated language content, not
missing product.

## Rulings

2026-09-08 human role ruling: Codex owns the large Orena architecture; Opus
implements feature detail against it. `docs/product/ORENA_REFERENCE_ARCHITECTURE.md`
defines the proposed engineering boundaries and implementation packages.
The Golden Star mission continues; Codex does not take over small room fixes.

### Encounter WIP handed to Opus

Starting point: `8af067f07bc3b0ea1e1df3f979ea4779b16e647f` added token exploration.
Codex stopped feature work when the human clarified ownership. Follow-up files:
`ui/encounter.js`, `ui/annotated-line.js`, `ui/copy.js`, `rooms.css`,
`scripts/test_orena_close_look.mjs`, `.github/workflows/ci.yml` (UI paths under
`static/orena`). Preserve this partial work; it is not accepted completion.

Implemented in that follow-up: request the selected segment lazily, preserve
timed word spans and exact Unicode text, honor Pinyin-off, pause for inquiry,
and pair token ink with each theme. Add loading/unavailable/retry and role labels.
Local checks passed: close-look, word-follow, pure-listening, workspace,
foundation; ESM linked 50 modules. A bounded code review found no P0/P1.
EN browser verified two segments and token inquiry holding playback, retaining
context and reporting the provider boundary honestly. No fresh full suite.

Opus must finish: Chinese browser/Pinyin-on-off, dark and narrow/wide checks,
keyboard/focus continuity, unavailable/retry behavior, Dictation regression,
and the final visual pass. One measured desktop token width was 23.984px against
a 24px rule; inspect browser rounding before calling target-size acceptance.
Do not count this WIP as a completed Golden Star milestone.

The human explicitly reprioritized Golden Star implementation over the review
findings. That supersedes the previous next-task ordering, without invalidating
the findings. This is one reference milestone; no capability breadth, native,
new learner persistence or external provider activation is introduced.
