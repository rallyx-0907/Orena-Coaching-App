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

## The authority: the Claude Design project (D-066, D-067)

The visual, interaction and data source of truth for every learner surface is
the design project `7a5604ca-1e11-4d8e-8305-7d0cb32d552d`
("Orena visual direction analysis") in Claude Design, **read at its source**.

- An agent with the `DesignSync` tool reads the project directly
  (`list_files`, `get_file`; reads only, never a write). The repository copy in
  `docs/design/canonical-ui/` is a **cache** pinned on 2026-09-21, and an
  incomplete one: it lacks `Orena Quick Sheet.dc.html`, the design project's
  own `CLAUDE.md`, `UI_BASELINE.md` and the `ui-baseline/*.md` rules, and
  `ui-implementation/`. Where the cache and the source differ, the source wins.
  A lane that cannot read the source says so and asks the human to re-pin; it
  does not decide from the cache alone.
- Before any learner-facing task, read: the design project's `CLAUDE.md`,
  `UI_BASELINE.md`, `ui-baseline/components/components.md`,
  `patterns/patterns.md`, `templates/templates.md`, `states/states.md`,
  `responsive/responsive.md`, `screens/screen-matrix.md`, the canonical
  screen file for the surface, and `Orena Quick Sheet.dc.html` for any
  explanation layer. `ui-implementation/` (Home, Reading library and
  workspace) is reference for structure, not a second visual authority.
- Within the design: the canonical `.dc.html` frame, then the data contract,
  then the `.md` indexes (derived, corrected by the frames), then
  `ui-implementation/`. The design's own LEGACY list (Device Overview, Design
  Overview, Screens and Parts 2-9, Card Component, Visual Direction, Visual
  Grammar, Checklist, Recalibration) is never a visual source.
- The human's current instruction outranks all of it. Every existing UI rule in
  this repository, in code comments and in older decisions is subordinate to the
  design; a rule that conflicts with it is void, not "balanced" against it.

## What "the same as the design" means (D-067)

42. **Measured, not eyeballed.** A surface is compared with its source frame
    number by number: size, radius, gap, padding, weight, letter-spacing,
    colour, type stack, icon and its fill state, taken from the frame's own
    computed style at true scale (the desktop frame is drawn at 62% of
    1920x1080; the phone frame is 1:1). A surface is not `REVIEWABLE` while a
    deviation is unlisted, and a deviation is either removed or recorded as a
    human decision. Looking similar is not a result.
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
46. **Icons are Phosphor 2.1.1, official paths only.** Regular by default,
    fill where the source fills (active tab, earned state). Paths are taken from
    the official package, never typed or adapted, and an icon the source uses
    but the app lacks is added from the package.
47. **The shell belongs to four places.** The rail (desktop) and the five-tab
    bar (phone) exist on Home, Library (including each skill's library),
    Vocabulary and Progress. A room where the learner works - reader, player,
    Dictation, editor, a review - has neither; its template starts at its own
    bar.
48. **Two frames.** Desktop 1920x1080 and phone 390x844. There is no
    intermediate breakpoint; the tablet is a recorded gap in the design. Height
    budgets are the design's (936px of content on desktop, about 636px of
    scrolling area on a phone).

## The baseline's visual rules

30. **One system: Dark Glass.** Ground `#050310` with the cosmic field
    (`tokens.json`), flat glass with one inset ring (no bevel, no bright top
    edge), a shallow shadow, the violet accent gradient. There is no second
    theme; Paper and Ink/Paper are retired. Colour values live only in
    `static/orena/theme.css`, taken from the design's tokens; no component
    invents a colour.
31. **Light is light, not a coloured surface.** Semantic colour (good, warn,
    bad, info, the seven usage verdicts) colours text and icons and never fills
    a glass surface. The one recorded exception is the "chưa chắc" amber chip
    on a review grade. Diffs follow the design: wrong is amber, missing is blue,
    extra is red and struck through.
32. **Skill hue** belongs to artwork, icons and small markers, as the design
    draws it, and is never the only signal.
33. **Explanations open in place.** A popover on a desk, a bottom sheet on a
    phone; audio pauses at its position and resumes when the layer closes; the
    learner never changes page to ask. Disclosure is progressive: the first
    layer answers the commonest question, everything deeper is behind one
    button.
34. **Type.** Nunito 700/800 for display, Nunito Sans for interface, DM Mono
    for labels and figures (10.5-12px, letter-spacing 0.12-0.14em), Noto Serif
    for reading text and Han characters. The scale is the design's (page title
    44, section 26, card title 17, body 15.5, meta 12.5). A face with no glyphs
    for a locale falls back technically (Vietnamese labels set in Roboto Mono),
    never by redesign.
35. **Geometry is the design's.** Radii (sheet 26, panel 20, card 17,
    control 15), spacing, the 280px rail, the 84px top bar, the 88px phone bar
    and the sheet handle (42x4) are read from the frames, not chosen.
36. **A card carries only what decides.** Title, artwork, level or length when
    it changes the decision, progress if the learner is partway. No source,
    licence, description or model on a card.
37. **Artwork.** Until real artwork exists, content uses the artwork slot the
    design defines (dot field and a hue bloom at the real ratio); real artwork
    replaces it with no layout change. The mascot, scenes and real artwork stay
    under the Art Bible (see "Art direction owner").
38. **Navigation** is the design's: Home, Library, Vocabulary, Progress and
    Profile, the four skills under KỸ NĂNG, and the five-item phone bar. Nothing
    is added to it.
39. **States.** Loading, empty and error are **not drawn** in the design (it
    marks them incomplete). Until the human supplies them, show only what is
    functionally necessary in the existing pattern, with no new visual and no
    new copy beyond a plain statement, and record it as a gap. Do not invent
    skeletons, empty-state cards or reassurance text.
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

Orena has two learner language roles, and only two.

**Learning language** owns the material: lesson and book text, media
transcripts, target vocabulary, practice sentences and the source content.

**Support language** owns everything Orena itself says: navigation, labels,
controls, instructions, feedback, explanations, errors and status. Learner
output keeps whatever language the learner produced.

Generated guidance is **requested** in the support language, not translated
afterwards, and a stored one carries the language it was written in. There is
no third, independently chosen interface language: the support language decides
what language the product speaks. A mixed interface is a defect unless the
content deliberately contains those languages. A supported locale owns every string; English
arriving silently in its place is a defect (rule 26).

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
- every colour comes from the semantic tokens and contrast passes;
- no legacy implementation of the same surface remains: it is deleted.

## Native (frozen)

Native mobile is frozen (D-046, 2026-09-06). When it thaws, it ports the
approved web behaviour and the same design; it is not a redesign, a reduced
feature set, a WebView shell or an Expo/Material reinterpretation, and it keeps
tokens, hierarchy, navigation identity, states, accessibility and EN/ZH parity.
A native-only flow or a separate state model is a product-memory regression.
