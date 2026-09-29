# Orena Design Contract

## Governance

**Purpose:** say how the learner-facing UI is built and judged, so that what
ships is the approved design and nothing else. **Authority:** the human. This
file states the rules; the design itself is not in this file, it is in the
Claude Design project named below. Agents may document an accepted mapping but
may not change the design to fit an implementation, and may not add to it.

**Rewritten by D-067 (2026-09-21).** The rules that stood here from D-046, D-051
and D-057 (rules 1-8, 10-13, 15, 17-25) and the D-057 acceptance gates described
an older design language and were being used to overrule the baseline. They are
retired (see `LEGACY_TOMBSTONES.md`). Numbers that survive keep their number,
because code and tests cite them.

**Change when:** the human changes the design or the durable rules. **Do not
store:** page-specific polish lists, temporary defects, screenshots, or generic
framework guidance. What is left to build or fix lives in
`docs/project/UI_BACKEND_GAPS.md`.

**Re-pointed by D-088 (2026-09-27).** The design moved to a new Claude Design
project and the Dark Glass system (D-066) is superseded on learner surfaces.
Rules 30-38, 42, 46-48 below are rewritten for the new design; every other rule
keeps its number and its text.

## The authority: the Claude Design project (D-088)

The visual, interaction and data source of truth for every learner surface is
the design project `e6dc1cb2-72d0-40b4-a916-5dcd47e17cc0` in Claude Design,
**read at its source**, pinned at revision `1790473816124946`.

- The repository copy in `docs/design/canonical-ui/screens/` is a byte-for-byte
  pin of that revision (`SYNC_2026-09-27.md`, `PINS.tsv`): `Orena.dc.html` (the
  shell, 63 frames and the state script), `Onboarding.dc.html` and
  `Compare-With-Model.dc.html`. `DesignSync` (`list_files`, `get_file`; reads
  only) returns at most 256 KiB of a file, so `Orena.dc.html` (832 KB) is read
  from the pin or from a fresh human export, never from a truncated read. When
  the human revises the design, the new revision is pinned and diffed against
  `PINS.tsv` before any surface changes.
- Before a learner-facing task, read: the frame(s) for the surface, the state
  script's handlers for them (what opens it, what each action does, which
  routes are focus workspaces), `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`
  (where each frame lives in code), and the brief
  (`docs/design/canonical-ui/brief/ORENA_DESIGN_SPEC.md`) for intent.
- Within the design: the frame, then the state script, then the brief. A screen
  the brief names that no frame draws is not designed. The script's prototype
  internals (simulated audio and scores, demo attempts, canned data, a browser
  pitch tracker) are not product behaviour; the product's real services are
  shown in the design's components.
- The human's current instruction outranks all of it. Every existing UI rule in
  this repository, in code comments and in older decisions is subordinate to the
  design; a rule that conflicts with it is void, not "balanced" against it -
  except rules 49 and 50, which the human reaffirmed for the new design: where
  a frame breaks them, the surface is recomposed and the deviation recorded.
- Platform Admin keeps `screens/Orena-Admin-Control-Center.dc.html` (project
  7a5604ca) until the human opens Admin (D-088 point 6).

## What "the same as the design" means (D-067)

42. **Measured, not eyeballed.** A surface is compared with its source frame
    number by number: size, radius, gap, padding, weight, letter-spacing,
    colour, type stack, icon, in both themes, taken from the frame's own
    computed style at true scale (the desktop frame fills the window below the
    48px prototype strip, so a 1920x1080 window draws it 1:1; the phone frame is
    390x844, 1:1). A surface is not `REVIEWABLE` while a deviation is unlisted,
    and a deviation is either removed or recorded as a human decision. Looking
    similar is not a result.
43. **No invention.** The screen carries what the source draws and nothing
    else: no extra button, chip, badge, hint, notice, heading, empty or loading
    visual, animation, confirmation, or explanatory line, and none of the
    source's pieces missing. Behaviour the source gives no place to is either
    put where the source's own patterns say (behind the "⋯" button, in a sheet)
    or reported to the human; it is never quietly surfaced as new UI.
44. **Old interaction is old UI.** An interaction the source does not draw is
    removed, not restyled: a row of icon buttons where the source has chips and
    a "⋯", a tap that acts before a choice is offered, a practice group in the
    rail, a destination sheet on a phone. The code is deleted, not hidden.
45. **The source's words are sample content (D-068).** The design fixes how a
    surface looks and behaves - colour, layout, type, component style, pattern -
    not what its mockup text says. Every name and label (destinations, skills,
    chips, actions) is in the learner's language setting, translated, whatever
    the frame's sample shows; lessons, numbers and states in a frame are not
    copied as data. A piece of copy the frame draws where the product has none
    is still written, in the support language, to the learner language
    contract below.
46. **Icons are Lucide at one pinned release, official paths only (D-088).**
    Each icon the design draws is identified by name and rendered from the
    official `lucide-static` package at the release pinned in
    `static/orena/kit/icons.js`; the design's hand-typed variants of the same
    icons are replaced by the package's paths. Paths are never typed or
    adapted, and an icon the design uses but the app lacks is added from the
    package. The brand marks (`ol-mark`, `ol-intel` and its states) are brand
    artwork, not icons (D-090).
47. **The shell belongs to the browsing places.** The desktop rail is always
    present; the desktop top bar, and the phone header and five-item bar, exist
    on Today, Discover, Orena
    Home, Practice Hub (and a skill's hub), My Library, Progress, Profile,
    Content Detail, Collection Detail, Word Detail, Grammar Library and Coming
    soon. Every route
    in the design script's focus list (reader, listening, dictation, the
    speaking and writing rooms, reviews, check understanding, grammar, search,
    settings and the rest) is a learning workspace: no top bar, no phone
    header, no tab bar; its template starts at its own bar.
48. **Two frames.** Desktop (the frame fills the window; verified at 1920x1080)
    and phone 390x844. The layout switches between them at one width
    (`static/orena/kit/device.js`); there is no intermediate breakpoint, and the
    tablet is a recorded gap in the design.

49. **A learning workspace is the viewport, never a long page (D-078).** "Learning workspace
    không được trở thành một page dài. Workspace shell phải nằm trong viewport. Chỉ những vùng nội
    dung có bản chất dài mới được scroll nội bộ bên trong workspace. Primary learning controls và
    primary actions phải luôn nằm trong vùng thao tác của viewport." This binds every learning
    workspace - Reading, Listening, Speaking, Dictation, Writing, Vocabulary, Grammar and any added
    later - on a desk and on a phone, and no agent may loosen it for an implementation reason
    (a large legacy component, a backend that returns a lot, a screen that used to scroll).
    - *The shell is bounded.* Once the learner is in a task, the page never scrolls: not to play,
      record, stop, answer, submit, retry, go on, change step, read the main feedback or reach an
      action the task needs.
    - *Only long content scrolls, inside its own region.* A passage, an essay, a transcript, a word
      or sentence or error list, detailed results, long feedback, history, an attempts list: each is
      a bounded region with its own scroll. Things of a known size - player, recorder, prompt,
      current sentence, score summary, current feedback, the action bar, navigation - sit in the
      layout directly; they are not wrapped in scroll boxes, and scroll regions are not nested.
    - *Primary controls stay in view.* Play, record, stop, submit, retry, next, a save the task
      needs and the room's main action are never pushed below long content.
    - *When it does not fit, recompose.* Re-lay rows and columns, rebalance panels, remove spare
      space, move detail into a sheet, popover or panel, disclose progressively, change the layout
      between desk and phone. Shrinking everything until it fits is not a fix.
    - *What gives way first* when space is short: 1 the content being learned, 2 the primary
      interaction, 3 the task's state, 4 the main feedback, 5 submit/retry/next, 6 support
      information, 7 detail and advanced information - the later items yield first.
    - *Browsing is exempt.* Home, the Library, catalogues, discovery and history may scroll as pages.
    - *Verified sizes.* The two frames of rule 48, and also a short desk (1366x768) and a small phone
      (360x740): no page scroll, no horizontal overflow, primary controls inside the viewport, long
      regions scrolling inside. For a learning workspace this replaces rule 48's "scrolling area on
      a phone".
    - *One flow per capability.* Where a capability has its current flow, every way in - navigation,
      Home, Continue, Library, deep links, cross-capability actions, old addresses - arrives in it;
      an old address redirects (`static/orena/product/legacy-routes.js`) and the old screen is never
      rendered.

50. **Learning-first copy: every visible sentence must earn its place (D-087).**
    Orena is a learning workspace, not a marketing surface. Persistent UI copy
    exists only when it helps the learner understand, decide, act, stay safe, or
    interpret learning feedback. Delete copy that merely decorates, motivates,
    restates what is already visible, explains an obvious control, or describes
    a feature the interface already demonstrates. In particular, do not invent
    slogans, inspirational headings, marketing-style subheads, "journey /
    mastery / unlock your potential" language, reassurance filler, or routine
    celebration. This applies equally to human-written and AI-generated UI copy.

    - **Default to absence.** Page subtitle: none unless necessary. Card
      description: none unless it changes a decision. Persistent explanatory
      paragraph: none unless a reasonable learner could misunderstand or make a
      consequential mistake without it.
    - **Keep controls terse.** Prefer 1-3 words for a button when unambiguous.
      Status text is the shortest clear phrase. An empty state gets at most one
      short sentence plus one action. Routine success feedback confirms the
      result; it does not celebrate the act.
    - **Never duplicate meaning.** A title such as "Vocabulary review" does not
      get a subtitle such as "Review your vocabulary words." A label does not
      need a sentence explaining the same label.
    - **Prefer evidence over prose.** Show "12 due today", "Tone accuracy +8%"
      or the actual next action instead of a generic progress or encouragement
      sentence when the measured state already says more.
    - **Learning content wins attention.** On a learning screen, material being
      learned, the primary interaction, task state and actionable feedback have
      visual priority over product copy. Support text yields before learning
      content when space or attention is constrained.
    - **Sentence justification.** Every new or changed learner-visible sentence
      must be justifiable by comprehension, safety, task completion or learning
      feedback. Labels and essential data do not need a prose justification.
      If removing a sentence changes none of those four, remove it.
    - **Scope.** This rule governs persistent learner UI and unsolicited product
      copy. It does not remove lesson material, user-requested explanations,
      substantive error/safety messages, necessary pedagogical feedback, or an
      Orena Intelligence conversation the learner deliberately opened. Those
      still follow the same preference for concise, useful wording.

## The design's visual rules (D-088, D-089)

30. **One system, two themes.** The design's light and dark token sets, both
    shipped, following the operating system by default (D-089). The learner can
    choose Light, Dark or System in Settings (D-097), and the Reader's light/dark
    button sets the same device preference. Colour
    values live only in the new UI's token file (`static/orena/kit/tokens.css`;
    the old `theme.css` serves only the old UI until the cutover, D-091), taken
    from the design exactly except the AA adjustments of D-093; no component
    invents a colour.
31. **Semantic colour is the design's.** Good, warning, error, support and AI
    colours appear as the design draws them - as ink, and as their `-soft`
    fills on chips, badges and result blocks where the frame fills them - and
    never as the only signal. Diffs follow the design.
32. **Skill hue** belongs to artwork, icons and small markers, as the design
    draws it, and is never the only signal.
33. **Explanations open in place.** In the design's sheet: a panel docked at the
    right on a desk, a bottom sheet on a phone; opening one pauses audio at its
    position and the learner never changes page to ask. Disclosure is
    progressive: the first layer answers the commonest question, everything
    deeper is behind one button.
34. **Type.** Outfit for the interface, Fredoka for the wordmark, Literata for
    reading text, JetBrains Mono for figures and labels, Noto Sans SC and Noto
    Serif SC for Chinese; sizes, weights and letter-spacing are the frame's. A
    face with no glyphs for a locale falls back technically, never by redesign:
    Outfit has no Vietnamese subset, so Vietnamese interface text is set in a
    Vietnamese-complete face of the same family (recorded deviation).
35. **Geometry is the design's.** Radii, spacing, the 232px rail, the 64px top
    bar, the 72px floating phone bar with its raised Orena action, the 440px
    desk sheet and the phone sheet's radius and height are read from the frames
    and their device variables, not chosen.
36. **A card carries what the design's card carries** - no more: no invented
    metadata, and no field the backend cannot supply shown as sample text.
37. **Artwork.** Until real artwork exists, content uses the placeholder the
    design draws for a missing image, at the real ratio; real artwork replaces
    it with no layout change. The mascot, scenes and real artwork stay under the
    Art Bible (see "Art direction owner").
38. **Navigation** is the design's (rule 47): Today, Discover, Practice Hub and
    My Library in the rail with the Ask Orena card and the account row; Today,
    Discover, Orena, Practice and Library in the phone bar. Nothing is added to
    it.
39. **States.** The design draws a banner, a loading skeleton, a load error, a
    Coming soon screen, its empty states and the microphone states; those are
    used as drawn. A state the design still does not draw shows only what is
    functionally necessary in the nearest drawn pattern, with no new visual and
    no new copy beyond a plain statement, and is recorded as a gap.
40. **The design decides, the backend adapts.** No component is removed, moved
    or redesigned because a backend cannot supply it. A metric with no measured
    value shows **0** in its canonical component and never an invented figure;
    the 0 is a fallback for the layout and never data (D-066). Gaps are
    tracked in `docs/project/UI_BACKEND_GAPS.md`.
41. **Accessibility never redesigns.** A token that fails AA is replaced by the
    smallest technical change that keeps the visual intent, and the deviation
    is documented.

## Rules that are not about how it looks

9. **One interface language.** Navigation, controls, headings, instructions,
   helper text, errors and labels follow one language; the learning language
   governs the material learned or produced. Which language that is, is
   settled by "The learner language contract" below.
14. **Artwork is one system.** All production artwork belongs to one Art Bible,
   owned by `assets/brand/orena/`. A piece of artwork must do a job
   (identify content, communicate mood, support navigation, explain meaning);
   artwork with no role is removed. The mascot's placement rules live in
   `assets/brand/orena/BRAND_MASCOT_GUIDE.md`.
16. **One colour owner.** Content artwork may use a rich authored palette; UI
   chrome, surfaces, text and states read colour only from the semantic tokens
   in `static/orena/theme.css`, and no second `:root` colour block appears.
   Text and controls pass AA (`scripts/test_orena_foundation.mjs`).
26. **No silent support-language fallback.** A supported learner locale owns
   every interface string its surfaces ask for. A locale with no pack at all
   falls back to English rather than showing keys, but a supported locale that
   quietly renders English is a defect, detected by regression, recorded and
   visible. There is no exception for the design's own words (rule 45).
   Learner material is never translated by this rule.
27. **The writing revision loop.** Reviewing never replaces the learner's
   editor, and a quoted phrase is findable in the learner's text. A review
   offers revision; it never substitutes generated text for the learner's
   writing. Feedback is addressed to the learner in the second person.
28. **Bounded before it is spent on.** Learner content is untrusted input.
   Every surface that accepts it states one product bound shared by the
   browser, the request model, the route, the repository and the evaluator, and
   refuses what exceeds it before anything is spent. A refusal carries the
   measurement, never the content. Nothing is silently truncated.
29. **A valid evaluation is reused, never recomputed.** Generated work that
   costs money and is deterministic in its inputs carries the identity it was
   produced under and is answered from storage for the same identity; a stored
   answer is never served past the contract that produced it.

## The learner language contract

Orena has three language layers, and none is inferred from another (D-079;
`docs/product/ORENA_LANGUAGE_COHERENCE.md` owns the full contract).

**Interface language** owns the chrome: navigation, buttons, menus, Settings,
section labels, titles, system states and errors. It is the learner's own
choice (on the device until the account can keep it - a gated migration), else
the browser's language when Orena is written in it, else English. It is never
taken from the support language.

**Support language** owns what explains: translations, hints, instructions,
feedback, guidance, grammar and vocabulary explanation. Generated guidance is **requested** in the support language, not translated afterwards, and a stored one carries the language it was written in. A support language Orena has no
written pack for reads its static guidance in English, never in the interface
language instead.

**Learning language** owns the material: lesson and book text, media
transcripts, target vocabulary, practice sentences and the source content.
Learner output keeps whatever language the learner produced.

The three are resolved in one place (`static/orena/product/languages.js`) and a
surface picks each string by its layer: chrome from the interface pack, guidance
from the support pack, material as it is. Changing one layer never changes the
other two; a reload, a stale cache or a profile read never moves one of them.
A supported locale owns every string it asks for; English arriving silently in
its place is a defect (rule 26). `scripts/test_orena_language_layers.mjs` locks
this contract.

## Art direction owner

`assets/brand/orena/` is the canonical owner of Orena's art direction and the
Art Bible referred to by rule 14. There is no second artwork authority. Its
scope: mascot and character, world and scene illustration, content thumbnail,
book cover, badge, background and pattern, and motion. Where it does not yet
specify something, that is a recorded gap for an art-direction task, not an
invitation to invent a style. The baseline decides the interface; the Art Bible
decides the artwork inside it; neither recolours the other.

## Acceptance: the fidelity gate

A learner-facing surface may be called `REVIEWABLE` only when all of these hold,
in addition to `docs/project/REVIEW_POLICY.md`:

- every deviation from its source frame, measured as in rule 42, is fixed or
  recorded as a human decision, on desktop and on a phone with real touch;
- nothing on it is invented (rule 43) and no interaction the design does not
  draw survives (rule 44);
- the source was read at its source (see the authority above), not from memory,
  a screenshot or the cache alone;
- English, Chinese and Vietnamese are each verified, in the same batch;
- every colour comes from the semantic tokens and contrast passes, in the light
  and the dark theme;
- no legacy implementation of the same surface remains: it is deleted;
- learner-visible copy passes rule 50's copy audit: no slogan/marketing filler,
  no redundant subtitle or duplicated meaning, learning content remains the
  visual focus, and every retained sentence has a functional reason;
- a learning workspace meets rule 49 at every verified size: the shell within the viewport, no page
  scroll to finish the task, long content scrolling only in its own region, primary controls and
  submit/retry/next always in view, no horizontal overflow, nothing overlapping or squeezed to fit,
  no blind scaling, a clear hierarchy, and no legacy learner route left for the same capability.

## Native (frozen)

Native mobile is frozen (D-046, 2026-09-06). When it thaws, it ports the
approved web behaviour and the same design; it is not a redesign, a reduced
feature set, a WebView shell or an Expo/Material reinterpretation, and it keeps
tokens, hierarchy, navigation identity, states, accessibility and EN/ZH parity.
A native-only flow or a separate state model is a product-memory regression.
