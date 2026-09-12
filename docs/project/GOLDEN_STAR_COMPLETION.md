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

## Reference architecture packages

- **A. Context and transition seam - done.** Late-answer rejection at both named
  consumers. The explanation panel gives each ask a ticket so a slow earlier
  answer cannot land against a newer question; forced ordering proves the stale
  answer arrives last and is dropped. Reading to Writing already carried source,
  draft, context and a resolver-built return path, verified rather than assumed.
- **B. Capability outcomes - done.** `capabilities/outcome.js` adds the
  discriminated outcome. An `available:false` payload is real news and becomes
  unavailable with no retry; a thrown request becomes failed and offers one.
  The two now read differently in the panel, and keeping a phrase survives both.
- **C. Reference compositions - journeys verified, one break fixed.** All ten
  canonical journeys of section 6 were walked. `sourceLink` sent a phrase kept
  from the learner's own writing to the Practice room, dropping its work
  reference and reopening unrelated content; it now resolves to that writing
  with the draft intact. Everything else held, including Dictation opening on
  the same line the learner selected, in EN and ZH.
- **D. Continuation integration - done, three breaks fixed.** `enter()`
  carried `segment`, `source_url` and `excerpt` forward from a previous visit
  but reset `intent`, so any later arrival that did not name one erased what
  the learner had been doing: reopening a passage they had been writing about
  relabelled their draft "You opened this" and sent Resume back to the passage.
  The shelf displayed the draft and then declined to open it. Intention now
  survives a visit that stays silent, while a stated one - including the
  deliberate `null` of closing a practice panel - still wins, and an intention
  the product no longer has is dropped on restore rather than routed.
  Conversations are kept to twelve and continuation to twenty, so the oldest
  conversation threads offered a return to work that was gone; the shelf no
  longer offers a thread it cannot open. Continue counted rows instead of
  asking the shelf, so a filtered shelf left a blank room under a heading
  promising otherwise, and it alone among memory-backed rooms stayed silent
  when the device could not remember. Both fixed.

Evidence for D: the story-to-draft-to-return journey verified in the browser -
the thread names the draft, shows it, opens it, and offers the way back to the
source. Language scope holds live: switching the learning language resets the
route and the English draft does not appear in the Chinese session, which
carries its own threads with every shelf string localized. Forcing localStorage
to throw makes both the composer and Continue say so. `#/continue` clean at 800
with no horizontal overflow. New CI gate `test_orena_continuation.mjs` (32
registered). No new persistence: device memory still reaches no API, and
`persisted` remains the account's word alone.

The `#/language` flake was measured before and after this package with the
recorded reproduction - 13 rooms x 2 themes at 750ms dwell, five repetitions -
and did not reproduce either time: 0/130 at `f68f31a` and 0/130 after. No
increase and no deterministic trigger, so nothing was handed to Codex; the
flake remains OPEN P1 on the conditions already recorded.

Evidence for C: 26 room/theme combinations clean at 390, 1440 and 1920 in EN
and at 1920 in ZH; 800 covered at the same HEAD. No room repeats the practice
map. The only sweep flags were the known `#/language` flake below and one false
positive in the probe itself, where a page shorter than the viewport reports a
negative overflow.

## Multi-theme visual system

Approved and implemented: Orena carries a registry of named themes, not a
light/dark switch. Identity (`paper`, `night-ink`, `deep-forest`, `sage-field`)
and appearance (`light`/`dark`) are separate attributes on the root element.

Palette extraction preceded implementation and was reviewed. Every image under
`assets/brand/` was decoded and sampled; the canonical six come from the Color
Palette block of `references/01_ACTIONS_AND_SYSTEM_REFERENCE.png`, agreeing
exactly with `tokens/brand-tokens.json`. Fifteen further values were sampled
from approved artwork and grouped by family - Forest, Sky, Ink, Earth/Moss,
Paper/Ember. `pattern/color-pallate.png` was ruled exploratory reference, not
the canonical palette: it holds eight glossy gradient tiles, four of them the
purple/blue that `visual_rules.avoid` names, and none of the Orena neutrals.
No colour was taken from it.

Colour now has one owner, `static/orena/theme.css`, in two layers: a foundation
layer naming the approved palette, and a semantic block per theme. The two
competing `:root` blocks in `foundation.css` and `reference.css` are gone -
which one won had been decided by `<link>` order, and that is why `--paper` was
on-brand while `--sage` was still a pre-brand mint. Components were not changed:
they already read semantic names, so all four themes run one component set.

Paper and Night Ink reproduce their previous values exactly, captured live
before the change. Orena Orange stays canonical at `#FF7A3D` and is now
reachable as `--brand` for fills; it measures 2.34 on Paper Ivory, so
`--accent` keeps the contrast-safe partner it already had.

Three defects fixed on the way. The browser chrome colour was a hardcoded pair
still serving the pre-brand green against an ivory page; it now reads the
resolved token. `--space-5` was consumed by `rooms.css` and never declared. The
part-of-speech inks were keyed to `data-theme='dark'`, which stopped matching
once themes had names - they follow `data-appearance` now and so serve both new
themes without change.

Evidence: 2,072 rendered text elements measured across four themes and eight
rooms in EN, and 1,464 across six rooms in ZH - no WCAG AA failure at either.
No horizontal overflow at 390, 800 or 1440 in any theme. The theme chooser is
built from the registry and each row previews itself by carrying `data-theme`,
so a preview cannot drift from the theme it previews. Registering a theme is a
block in `theme.css`, an entry in `theme.js` and a name in `copy.js` for both
languages; `test_orena_foundation.mjs` now enforces the contrast pairings for
every registered theme rather than for two, and holds the single-owner rule.

Ember stays deferred with its extracted values recorded and unshipped.

## Phone navigation

Below 900px the rail becomes a header, and the eleven destinations were laid
out across it: three groups wrapping onto three lines, each line wider than the
screen. At 390x844 that header measured 228px - 27% of the viewport - and
Listening, Patterns & meaning and Recall rendered past the right edge, where
nothing could reach them. Three approved destinations were unreachable on a
phone.

The list now sits behind one control, and that control names where the learner
currently is rather than being an anonymous hamburger: closed it still answers
"where am I", open it shows every destination under its group heading, which
the flattened strip had dropped. It has its own full-width row because squeezed
beside the wordmark and the two utilities there was room for about four
characters, and "D.." is not an answer to that question.

Closed, the sheet is `display:none` rather than merely invisible, so its eleven
links are not in the tab order and not read out while it is shut. It closes on
Escape with focus returned to the control, and on choosing a destination -
the shell is rebuilt per route, so that needs no state of its own.

Desktop is untouched and verified so: the 224px fixed rail, eleven destinations
in a column, three group headings, `#main` still offset by the rail, and the
control `display:none`. Two composition bugs surfaced on the way: the mobile
grid sized the brand column last so "orena" broke across three lines, and
`world.css` still carried `margin-left:auto` on the actions cluster from the
pre-rail flexbox header, which cancels stretch on a grid item and pushed the
cluster off the right edge.

Header 228px -> 131px, content starting at 131px instead of 228px. Verified at
390, 430, 800 and 1440 across all four themes and in EN and ZH: no horizontal
overflow in any combination, all eleven destinations reachable, 44px minimum
touch target, one `aria-current` per route, and the control's label complete at
every width. Nothing was solved by shrinking type or touch targets.

## Brand asset set replaced

The approved artwork was replaced wholesale and the runtime library was remapped
to it. Twelve of thirty references pointed at files that no longer exist. The
new set is uniform where the old one was not - every scene 1672x941, every
character 1254x1254, no printed caption strips - so the caption-cropping frame
is no longer exercised. Six scenes now exist where ten states wanted one, so the
scenes went to the three editorial heroes and the three rooms composed around
one, and the remaining states took the character artwork that says the same
thing: `reading` to `learn` (with a book), `writing` to `take-notes` (with a
notebook), `perspective` to `discover` (with a telescope), `remembering` to
`grow`. Four expressions with no artwork were dropped rather than substituted;
`laughing` and `winking` keep their meaning and point at the renamed files.
27 approved assets are reachable, 2 unused.

`tokens/action-index.json` still lists assets that were removed (`travel`,
`rest`, `relax`, `write`, and four expressions). It is inside the brand
directory the human is editing, so it was left alone rather than edited under
them.

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

## R3 supplemental evaluator: local Ollama verification

Representative EN/ZH evaluator quality is verified live against the configured
local model (`qwen3:8b`, the `OLLAMA_URL`/`OLLAMA_MODEL` default when no `.env`
overrides them). `scripts/verify_live_writing_evaluator.mjs` replays the
application's structured schema and language prompts through Ollama's
`/api/chat` and asserts the returned results are grounded: every strength/error
fragment is a literal substring of the learner text, every category belongs to
the active language taxonomy, every suggestion differs from its fragment,
explanations and reusable rules are non-empty, and confidence stays within the
threshold. Both EN and ZH pass, and short samples correctly return
`insufficient_evidence` without a fabricated band.

This is local-model execution evidence, not a browser or CI claim. The final
Write → Evaluate → Review browser pass still requires the running app runtime;
the degraded 503-retry / 502-no-retry contracts remain covered by
`test_provider_failures_use_canonical_learner_safe_evaluation_envelope`.
