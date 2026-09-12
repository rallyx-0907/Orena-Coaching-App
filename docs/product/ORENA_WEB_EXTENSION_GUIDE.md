# Extending the Orena web foundation

Status: DESCRIPTIVE. This records what the Golden Star foundation already
provides so a new surface inherits it instead of re-inventing it. It sets no
product direction; that lives in `ORENA_PRODUCT_CONSTITUTION.md` and
`ORENA_CONTENT_ARCHITECTURE.md`.

If a change here would contradict either of those, the Constitution wins and
this file is what needs updating.

For system boundaries and the proposed shared experience contracts, read
`ORENA_REFERENCE_ARCHITECTURE.md`. It separates Codex's architectural ownership
from Opus's feature implementation. This guide continues to describe existing
primitives; proposed interfaces in that blueprint are not already shipped APIs.

---

## 1. Where a new surface goes

`static/orena` is layered, and the layers only ever depend downward:

```
ui/          what a learner sees          world, encounter, expression
             shared pieces                patterns, content, brand, html
product/     what Orena means             intent, memory, encounter, evidence
capabilities/what the client can do       media player, recorder, dictation,
                                          transcript, speech, grammar
infrastructure/  how it reaches the server  api
```

A `ui/` module may import from `product/` and `capabilities/`. Nothing below
`ui/` may import from `ui/` — except `ui/html.js`, which is escaping and DOM
plumbing rather than presentation.

New routes are added in `product/intent.js` (`route`, `link`) and dispatched in
`app.js`. Nowhere else parses the hash.

---

## 2. Reach for these before writing markup

From `ui/patterns.js`:

| Primitive | Use it for |
|---|---|
| `pageIntro({title, note, eyebrow, scene, compact})` | Every page heading. `compact: true` for a room where the learner works: smaller title, no artwork. |
| `practiceReturn(c)` | The way back to Practice, placed above a room's heading. |
| `intentNavigation(c, current)` | The Practice intention row. |
| `continuationShelf(ctx, limit)` | "Pick up a thread" on any surface that can send a learner onward. |
| `responseComposer(ctx, {id, prompt})` + `bindComposer` | Writing that grows out of something. Never submits a practice attempt. |
| `draftStatus(ctx)` + `refreshDraftStatus(node, ctx)` | Whether the draft is kept, as a status symbol whose words are a hint; a draft that cannot be kept takes the warning symbol. |
| `hint({text, label, icon, tone})` | Supplementary information as a symbol with its words on demand. |
| `workspaceFrames(workspace, {back, focus, result})` | The narrow-screen frame switch of a learning workspace. |
| `progressReporter(element, ctx, alive)` | Anything that leaves the device. |
| `savedLanguageLink(c)` | The hand-off from keeping language to meeting it again. |

From `ui/content.js`: `duration`, `origin`, `art`, `audioIdentity`,
`bindImages`. From `ui/brand.js`: `companionArt`. From `ui/html.js`: `esc`,
`safeExternal`, `dialog`, `focusRegion`, `status`.

### Learning capabilities

| Primitive | Use it for |
|---|---|
| `ui/understanding.js` `openUnderstanding(ctx, {selection, context, title, question})` | Any "what does this mean / why is it like this" moment, in any capability. |
| `ui/understanding.js` `selectionWithin(root)` | What the learner highlighted, with the block it came from. |
| `ui/voice-evidence.js` `voiceEvidence(c, evaluation, language)` | Rendering a Speaking envelope without collapsing it. |
| `capabilities/word-timeline.js` | Word-level Follow, with a truthful fall back to the segment. |
| `capabilities/dictation-hints.js` | Structure-and-anchor hints that never reach the answer. |
| `capabilities/dictation-evaluator.js` | The alignment both grading and hints must share. |
| `product/evidence.js` `mergeListeningEvidence` | Writing progress without lowering what is stored. |
| `product/memory.js` `recordRevision` | What a learner submitted, kept in order. |

**Never build a second explanation surface.** Reading, Listening, Writing and
Practice all open `openUnderstanding`; they differ only in what they hand it.
A follow-up is the same call carrying a `question`, which is what keeps the
selection and its context on screen while the learner goes deeper.

### Naming what is wrong

`USAGE_JUDGEMENTS` in `writing_coach/media_interaction.py` and `JUDGEMENT_KEYS`
in `ui/understanding.js` are one vocabulary, checked against each other by
`scripts/test_orena_understanding.mjs`. Adding a distinction means adding it to
both plus its label in `copy.en` and `copy.zh`. "Wrong" on its own is not a
thing this product says.

`progressReporter` is the one to reach for by reflex. It speaks in a single
voice, refuses to write onto a view the learner has left, and any retry it
renders is wired before it returns:

```js
const report = progressReporter(statusNode, ctx, alive);
const save = async () => {
  report.saving();
  try {
    await ctx.mutate(() => api.something(payload));
    report.saved(savedLanguageLink(c));   // omit the argument if there is no next step
  } catch {
    report.failed(c.failedSave, save);    // the retry is already bound
  }
};
```

---

## 3. Colour: a panel carries its own ink

Never paint a surface with a bare accent token. Each tinted panel ships with the
ink that belongs on it, in both themes:

```
--sage-surface   --on-sage   --on-sage-muted
--coral-surface  --on-coral  --on-coral-muted
--night-surface  --on-night  --on-night-muted  --on-night-line
--sun-surface    --on-sun
```

`--sage`, `--coral`, `--sun` remain for strokes and accents on a surface that
already sets its ink. `scripts/test_orena_foundation.mjs` computes every pairing
and rejects `background: var(--sage)` and friends, so this is enforced rather
than remembered.

Type and spacing come from `--text-*` and `--space-*` in `foundation.css`. The
same test rejects a hardcoded font-size below the readable scale.

---

## 4. Truthfulness is a rendering rule

The product has one non-negotiable habit: never show a number, a meaning, a
score or an availability the system does not actually have.

- A provider that returns demonstration values is labelled
  (`score_kind === 'synthetic_demo'`, `evaluator === 'fallback-demo'`).
- A missing score reads as `c.notMeasured`, not `0` or `?`.
- An empty result says it found nothing rather than rendering an empty shell.
- Imported media with no known length shows no length, not `0:00`.
- A save whose prior state could not be read merges rather than overwrites
  (`product/evidence.js`, `mergeListeningEvidence`).
- Word-level Follow refuses timing it cannot reconcile with the line, rather
  than highlighting an approximation.
- A dictation hint shows structure and words already earned. It never completes
  a word for the learner; revealing the answer is a separate, recorded act.
- Speaking keeps measurement, deterministic alignment and derived guidance as
  three separate statements, each naming its own source, and never claims
  proficiency from one recording.

When adding a capability, decide what its unavailable state says before
designing its successful one.

---

## 5. Learner memory and the threads between archetypes

`product/memory.js` is owner- and language-scoped device memory: imports, media
imports, kept content, continuation, drafts, dictation answers. Practice
evidence stays on the server through the capability APIs.

Call `memory.enter({id, title, segment, intent, excerpt})` whenever a learner
touches something. That single call is what makes the continuation shelf, the
"Continue" thread and the return route work — the archetypes are connected by
this record, not by bespoke links between screens.

`product/intent.js` decides where a thread resumes: `continuationLink(item)` for
unfinished work, `sourceLink(id)` for the way back to where it started.

---

## 6. Before calling a surface done

1. `node scripts/test_orena_foundation.mjs` and `node scripts/test_orena_product.mjs`.
2. `node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs`.
3. Open it at 1440, 800 and 390 in light and dark, in English and Chinese.
   Submit something: the result must land inside the desktop frame and at the
   start of the narrow result frame (`DESIGN_CONTRACT.md`, D-051).
4. Check what it says when the network fails, not only when it succeeds.
5. Confirm no text falls below its contrast threshold and no pointer target is
   under 24px (44px below 480px).

The browser pass is not optional: every defect fixed in this foundation was
found by looking at the running product, not by reading the code.

## Presentation invariants

What a new surface inherits, and the traps behind each one.

### Workspace`

`world.css`, `ui/encounter.js` - consuming and producing want
  different shapes. When a practice opens the encounter re-composes: source one
  side, work the other, each scrolling on its own. The practice panel must stay
  a sibling of the media stage, not a child, or nothing can place them apart.
  Narrow, the source becomes a compact sticky strip and the work is scrolled to.
### Learning workspace

`foundation.css`, `ui/patterns.js` - the implementation of
  `DESIGN_CONTRACT.md` rule 2-4. A skill that asks the learner to do something
  and then answers it keeps both inside one desktop frame:
  `.learning-workspace` with `.workspace-activity` and `.workspace-result`
  (`.workspace-result__bar` holds the way back, `.workspace-result__scroll` the
  answer), `data-workspace="activity|result"` on the workspace, and a
  `.result-waiting` block naming what will appear before anything has.
  `workspaceFrames` switches the frames and places a narrow screen at the start
  of the result, below the sticky header; `onResult`/`showResult` is called
  when the answer arrives. Give the surface a `--workspace-inset` equal to the
  room its own heading needs. Secondary material - starters, history, other
  starting points, further paths - goes in `.workspace-secondary` below the
  frame, never in the result column.
  Writing (`ui/expression.js`) and Speaking (`ui/speaking.js`, which hands
  `mountVoiceResponse` a `resultHost`) use it directly. Dictation keeps the
  encounter's source-and-work composition, with the practice panel bounded to
  the frame and the comparison brought into view inside it. Reading
  comprehension and Grammar practice still owe it a check.
  `scripts/verify_writing_workspace_browser.mjs` measures the running Writing
  surface for exactly that.
### Supplementary information

`ui/patterns.js` `hint`, `ui/symbols.js` - rule 6-7 of the Design Contract.
  Optional-field purposes, where a draft or recording lives, what a comparison
  does not measure, where a list comes from: a symbol beside the thing it
  explains, its words in a night-panel bubble on hover, keyboard focus or tap.
  `installHints` is installed once in `app.js`. Use `tone: 'warning'` and the
  `warning` symbol for the case that matters (a draft that cannot be kept, a
  transcript that may be misheard). Put a hint beside a heading with
  `.heading-with-hint`, never inside the heading, so its words do not become
  the heading's name. Instructions the task needs, and consent statements shown
  before data leaves the device, stay as text. A hint inside a form is a
  button: select the form's action by role (`button.primary`), not as the
  form's first button.
### Narrow header and phone density

`app.js`, `reference.css`, `rooms.css` - Design Contract rule 12 (D-052).
  Below 900px the shell is a sticky header with two states. `app.js` sets
  `#shell[data-compact]` when the learner scrolls down into a room (24px of
  travel past 96px) and removes it on a deliberate scroll up (72px), near the
  top, on opening the destinations, and on every new room. Compact keeps the
  mark and the destination control, and the header really is shorter; the
  browser keeps the learner's place while the page reflows, and the scroll
  that causes is ignored. The live height is `--shell-offset` on the root,
  written synchronously on each change: use it for anything sticky below the
  header and for the scroll margin of anything the learner is moved to. Before
  moving the learner to their work programmatically, call `focusWork()` from
  `ui/html.js` so the destination is computed against the working header;
  `workspaceFrames` and the encounter's narrow practice already do.
  The last block of `rooms.css` (`max-width: 600px`) is where phone density
  lives: controls at 44px with no desktop padding, the encounter's voice card
  as a strip, one-row transport, a compact spoken line, dense transcript rows,
  reading at line height 1.7 (1.85 for Chinese), compact grammar, speaking,
  recall and feedback. While following (no practice open) the media stage uses
  `display: contents` so the transcript sits directly under the spoken line and
  the deeper paths follow it; the stage element stays for the player's events.
  New phone rules go there rather than into another breakpoint elsewhere.
### Brand`

`content/brand-library.js`, `ui/brand.js` - approved artwork is
  addressed by state, never by path, and served from `assets/brand/orena` by
  `/orena-brand` rather than copied into the web tree. Each entry carries its
  measured size; three scenes have printed caption strips and are framed to the
  art above them. Reference sheets are not product imagery.
### Hints`

`capabilities/dictation-hints.js` - word boundaries, word length,
  earned anchors, and the letters the learner typed correctly inside an
  unfinished word. Every unfound word withholds its last character, so a hint
  cannot become a reveal; Chinese counts character units.

### Motion

`foundation.css` carries one arrival keyframe and no loops. Movement says
"this arrived because of something you did"; ambient drift is decoration.
Everything is inside `@media (prefers-reduced-motion: no-preference)`.

### Page openings

`pageIntro({ scene })` is the one page opening. Name a state from
`content/brand-library.js`; never a file path. A surface with nothing worth
illustrating passes no state and shows none - content is the protagonist.
A room where the learner works passes `compact: true`: the heading orients and
yields the first viewport to the activity, and no artwork is drawn even if a
scene is named. `practiceReturn(c)` or a `.back-row` sits above it; the eyebrow
names the room, so the way back never repeats it.
