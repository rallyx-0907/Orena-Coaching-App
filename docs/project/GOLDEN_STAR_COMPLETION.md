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

- [ ] Shell and multi-entry orientation: `ui/reference.js`, `product/intent.js`,
  `app.js`, `reference.css`. Add Continue as a route using continuationLink;
  route tests must reject silent fall-through. All navigation links resolve to
  existing capabilities, including direct Reading/Listening/Speaking/Writing.
- [ ] Editorial Discover and Practice: `ui/world.js`, `reference.css`.
  Compose real content with contrasting scale, image, type and background;
  retain import, provenance, unavailable states and shared library filtering.
- [ ] Distinct learning rooms: `ui/reading.js`, `ui/speaking.js`,
  `ui/expression.js`, `rooms.css`. Preserve API and event contracts, use quiet
  content/work zones and purposeful illustration, no large mascot in editors.
- [ ] Deep journeys: media Follow -> Dictation -> understanding -> keep ->
  Recall; Reading -> selection -> understanding -> response -> Writing ->
  Continue; Speaking situation -> own turn -> coaching -> writing; Grammar ->
  example -> understanding -> My Language. Exercise available paths in browser;
  label provider/hardware-limited steps honestly rather than simulating success.
- [~] Completion findings: Recall answer exposure (P1) **closed**; Writing
  revision issue classification (P1) and long-turn contextual explanation (P2)
  open. See `CAPABILITY_DIRECTION_REVIEW.md`. They do not replace this mission.
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
- [ ] Validate Node contracts and ESM, project-memory and architecture gates;
  run CI-defined Python gate when Docker ownership is established. Evaluate
  light/dark, EN/ZH at 390, 800, 1440 and 1920 widths in the actual browser.
  Check keyboard, overflow, readable ink, truthful states and route restoration.
- [ ] Record evidence, extend ORENA_WEB_EXTENSION_GUIDE with reusable rails,
  update current status and checkpoint explicit files. Present browser-reviewable
  result. Only the human may establish Golden Star acceptance.

## Rulings

The human explicitly reprioritized Golden Star implementation over the review
findings. That supersedes the previous next-task ordering, without invalidating
the findings. This is one reference milestone; no capability breadth, native,
new learner persistence or external provider activation is introduced.
