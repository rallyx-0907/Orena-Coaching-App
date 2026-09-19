# Orena Design Contract

## Governance

**Purpose:** preserve the approved Orena experience across responsive web and
native clients. **Authority:** fundamental principles are human-governed.
Agents may document an accepted mapping but may not change the design strategy
to fit an implementation.

**Change when:** an explicit human decision changes durable design direction or
an approved product surface establishes a new shared contract. **Do not store:**
page-specific polish lists, temporary defects, or generic framework guidance.

## Current human direction (D-046)

The historical learner product is retired. Current mainline UI is technical
history, not design authority. The Product Constitution, Content Architecture
and approved brand govern the new web foundation. Experience-centered does not
mean discovery-only; direct practice must converge with contextual practice.

Native mobile is frozen by explicit human scope update on 2026-09-06. No further
native work belongs to this mission. Its existing working-tree state is retained.
A future native mission follows coherent, human-approved web direction. Nothing
in the older full-port rule authorizes rebuilding the deleted product.

## Learner-facing experience rules (D-051)

Explicit human direction, 2026-09-12. These govern every learner surface on the
responsive web and therefore the native port. They sit under the Product
Constitution and Content Architecture; they do not change domain ownership,
evidence meaning or capability semantics.

1. **Every visible element earns its place.** It must help the learner
   understand the content or the task, do the task, understand the result,
   improve, or continue. Otherwise remove it, compress it, turn it into a
   symbol, lower its priority, or move it after the learning loop. Existing UI
   is evidence of what was built, not a reason to keep it.
2. **Desktop: the core learning loop is one frame.** The source needed now, the
   activity, the learner's work, its essential controls, the submit action, the
   immediate result and the primary feedback share one viewport-sized
   workspace wherever the experience can support it. Long content scrolls inside
   its own region; the page does not scroll just because feedback arrived, and
   the learner never loses their work to see its result.
3. **Narrow: sequential frames of the same loop.** Frame 1 is the activity with
   its controls; after submission the learner is placed at the start of Frame 2,
   the result and primary feedback, never halfway between the two, with a
   natural way back to edit or retry. Long results scroll inside Frame 2.
4. **Secondary material comes after the loop.** History, earlier attempts,
   deeper theory, extra examples, alternative starting points, related content
   and continuation shelves sit below the desktop frame (Frame 3+ on narrow
   screens) and never take space the activity or its immediate feedback needs.
5. **Rooms where the learner works open compactly.** Entry, discovery and empty
   states may carry full openings and approved artwork — permitted, never a
   default page template (amended by rule 13 below); an activity room's
   heading orients and yields the first viewport to the work. The way back sits
   above the heading and does not repeat it.
6. **Supplementary guidance is a symbol with words on demand.** Optional-field
   explanations, minor status (such as where a draft is kept), secondary
   annotations and minor warnings use a semantic symbol from Orena's icon
   language that reveals a short explanation on hover, keyboard focus or tap.
   The control is labelled for assistive technology, touch-sized on small
   screens, theme-safe, and never relies on colour alone.
7. **Essential instructions stay visible as text.** Anything the learner needs
   to understand or complete the task, and any consent or privacy statement that
   must be read before data leaves the device, is never hidden behind a symbol.
8. **Roles are distinguishable at a glance.** Title, learning material, task
   instruction, learner input, the learner's original error, correction,
   explanation, reusable rule, score or result, next action, optional help,
   metadata and secondary content each read differently through Orena's type
   scale, weight, semantic colour, surface, spacing and grouping. Supporting
   information recedes; not everything becomes an equally weighted card.
9. **One interface language.** Navigation, controls, headings, instructions,
   helper text, errors, feedback scaffolding and labels follow one language;
   the learning language governs the material learned or produced. Which
   language that is, is settled by "The learner language contract" below: it is
   the support language, not a separately chosen interface language.
   Learning, support and interface language remain distinct concepts
   internally, and coherence comes from the shared localisation architecture,
   never from a special case for one language.
10. **One design language, distinct compositions.** Writing, Reading,
    Listening/Follow, Speaking, Dictation, Grammar, Recall and Vocabulary keep
    their own attention shapes and learning logic; they share Orena's
    primitives, tokens, themes and the single Understanding surface. Solve a
    repeated problem in the shared layer; do not copy one room's markup into
    another or build page-local design systems.
11. **Learning content is the protagonist during active learning.** Brand
    atmosphere belongs to discovery, entry, transitions, completion and empty
    states, and never displaces the learner's text, media, work or feedback.

12. **Phone: the screen belongs to the learning (D-052, D-053).** Priority is learning
    content and learner work, then controls, then navigation and secondary
    chrome. The narrow layout is adapted, not the desktop shrunk:
    - the header is expanded on arrival, near the top and while navigating,
      and compacts while the learner scrolls into the room - to the smallest
      state that still reaches every destination - releasing real viewport
      height rather than overlaying content; a deliberate scroll up, the top,
      or tapping the navigation expands it again;
    - a phone has its own scale, not the desktop's carried over (D-053): type
      a step smaller and still readable (body 15px, nothing the learner reads
      below 12px, the line being learned the largest text in its frame);
      controls tappable at 36px, quiet inline controls at 32px, inline targets
      such as words at least 24px by height and spacing, never widened to a
      thumb; a checkbox or radio sized to its text, its label the target; rows,
      labels, selectors, media controls and cards take only the room they need;
    - learning content itself is set denser - type, line height, paragraph and
      block spacing, media and transcript framing - while staying comfortable
      to read, so a spoken line wraps into two to four lines, not six;
      decorative margins go first;
    - a sticky source, a result frame or any destination the learner is moved
      to clears the header at its current height, never sits underneath it;
    - Listening shows the current line, its meaning and a run of the transcript
      together; Writing gives the editor the frame; Reading keeps a readable
      line and loses oversized framing; action rooms keep activity, input and
      action in Frame 1, the result in Frame 2, secondary material after.

How the current web implements these rules is described, not governed, in
`docs/product/ORENA_WEB_EXTENSION_GUIDE.md`.

## Learner-facing experience rules, continued (D-057)

Explicit human direction, 2026-09-17, continuing the numbering above. Rules
1-12 stand unchanged except where rule 13 amends rule 5. Product authority for
this direction is `docs/product/ORENA_PRODUCT_CONSTITUTION.md`; this section
governs how a surface must be built, not what Orena is for.

13. **Less words, more life.** Show first; say only what is needed. A full
    opening with a headline and approved artwork remains permitted where it
    earns its place, but it is not the default template for a page, and the
    sequence *eyebrow + giant headline + slogan + paragraph + mascot* must
    never be repeated across surfaces simply because the primitive exists.
    Headlines and slogans do not substitute for hierarchy, artwork, content or
    interaction. Every screen has a copy budget, spent in this order: content
    title, action, essential context, metadata, optional explanation, and
    marketing or slogan prose last. If a screen needs two or three sentences to
    say where the learner is, the hierarchy or the artwork is not doing its
    work. If a screen feels empty, fix composition, content density, imagery or
    hierarchy before adding copy, a slogan or a mascot. This amends rule 5: it
    removes the default, not the permission.

14. **Artwork is a system, not decoration.** All production artwork belongs to
    one Art Bible, owned by `assets/brand/orena/` (see "Art direction owner"
    below). Do not mix unrelated rendering styles without an explicit system.
    A piece of artwork must do at least one job: identify content, create
    curiosity, communicate mood, support navigation, create continuity, explain
    meaning, or reinforce a learning action. Artwork placed only to fill an
    empty hero fails. Artwork with no narrative, navigational, emotional or
    semantic role is removed rather than rebalanced. The mascot's own placement
    rules stay where they already live, in
    `assets/brand/orena/BRAND_MASCOT_GUIDE.md`.

15. **Content imagery carries the visual authority.** On Discover, Library,
    Reading and Listening surfaces, covers, thumbnails, scenes and meaningful
    imagery are normally more prominent than metadata: the learner sees
    something worth entering before reading information about it. Cards lead
    with the image and a title, carry minimal metadata, and leave author,
    level, description, chapter count, progress, source, rights and related
    content to the detail view. Generic placeholders — a single letter, a
    repeated `Aa 字` tile, repeated abstract rectangles, geometric filler — are
    development-only and must not stand as the product's visual language.

16. **Vivid, but one colour owner.** Content artwork, covers, thumbnails,
    scenes and illustration may use a rich authored palette: warm, vivid,
    playful, editorial, memorable. That licence belongs to artwork, and it
    creates no second colour owner. UI chrome, components, surfaces, text and
    interactive states still read their colour only from the semantic tokens in
    `static/orena/theme.css`; no component re-invents the brand palette and no
    second `:root` colour block appears anywhere. Icons used as UI controls may
    carry colour, fill, shape, active/inactive states and small tactile motion,
    through those same semantic tokens. Nothing here exempts anything from
    accessibility: body text, secondary text, controls, links, tinted panels
    and any UI or text overlaid on artwork must still pass AA, as
    `scripts/test_orena_foundation.mjs` enforces for every registered theme.
    Vivid does not mean arbitrary — saturation, contrast and palette
    relationships are governed by the Art Bible.

17. **Discover is not a list of skills.** Skill labels are valid navigation
    vocabulary and Reading, Listening, Speaking, Writing, Vocabulary, Library
    and Practice remain valid doors and shortcuts. But a discovery surface must
    not be organised primarily as those modules: it uses content, topic, theme,
    mood, context, person, situation and continuity, and it may mix media
    within one rail. Level, type and duration are secondary metadata.
    Horizontal rails remain valid when they stay compact, reveal the next card
    on narrow screens, never capture vertical scrolling, and lead with imagery
    and title. Library may be the practical, searchable surface; search and
    filter are secondary controls on a discovery surface, not its opening move.

18. **UI speaks sans. Stories speak serif.** The interface is set in the sans
    family; story, book and editorial reading content may be set in the serif
    family. Serif and sans are not chosen per component by taste.

Rule 11 already gives the focused-learning direction; under this section it
reads as **world recedes, content comes forward**: entering Reader, Listening,
Writing, Speaking or another focused experience reduces navigation and shell
noise, keeps the learning tools and explanations within reach, and adds no
decorative immersion that competes with the task.

## Learner-facing experience rules, continued (2026-09-18)

Explicit human direction after a learning-surface review. Rules 1-18 stand.

19. **The core learning viewport.** Everything the immediate learning task needs
    at the same time stays available in one learning viewport. A learner never
    page-scrolls to trade the media for the transcript, the prompt for the
    recording, the recording for its immediate result, or the audio for the
    dictation input. Secondary material - earlier attempts, deeper analysis,
    measurement detail, history - may scroll inside its own region, collapse,
    or open progressively. On a desktop the width is used before core elements
    are stacked; a wide empty area beside vertically stacked learning content is
    the defect this rule names. A phone recomposes the workspace rather than
    receiving the desktop columns end to end.

20. **No duplicated learning stage.** Before adding a panel, ask whether the
    information already exists in a visible learning object. If it does, that
    object is enhanced instead. The line being spoken is the active transcript
    row, opened in place - not a second card above the list repeating it. The
    same applies to a source title stated three times, or a mode label the
    navigation already carries.

21. **The card wall is not a layout.** Repeated equal bordered rectangles are
    not the default shape of a learner surface, and changing their border,
    radius, shadow or background does not fix one - the composition has to
    change. A container is earned when it carries real content identity, an
    interaction boundary, an active or selected state, a bounded scroll region,
    a continuation object, or a form control. Ordinary text does not become a
    group by being wrapped in a white rounded rectangle. Compose with content
    imagery, source artwork, typography, spacing, rails, active state, icons,
    semantic colour, progress and relationships first; reach for a border when
    one of those is genuinely what is meant.

22. **Composition order.** Actual learning content, then the source's own visual
    identity, then active state, then typography, then spatial grouping, then
    semantic colour, then icons, then progress - and only then a container. A
    surface that begins from a card for every piece of content has started in
    the wrong place.

23. **Active state does not restructure.** On a transcript, timeline, list or
    any surface where the current item changes while the learner is reading,
    becoming current must not change a row's height, padding, container or the
    number of controls it holds. Every row carries the slots it can ever show;
    which of those are shown is a property of the surface, so it is true of all
    rows at once. Mark the current one with ground, edge, typography, state
    text and non-layout transition - visual emphasis before structural
    expansion. A list that grows where the voice is and collapses behind it is
    the defect this rule names.

24. **Reusable learner actions live in a shared toolbar.** An action that
    repeats across items - replay, practise, show meaning, show reading, colour
    the word classes, and the deeper intentions behind an overflow - belongs to
    one compact bar with a stable place in the workspace, acting on the current
    or selected item. It is not duplicated inside each content row, and each
    surface adopting it extends the shared primitive rather than building its
    own. A menu or popover is placed by measuring against the viewport and its
    pane, opens inward at an edge, and on a phone becomes a sheet; it never
    creates page scroll and never carries a hard-coded coordinate.

25. **Icon first for shared actions, text carries the meaning.** Where a stable
    semantic icon exists, a reusable learner control uses it, and the support
    language supplies the tooltip, the accessible name, and a compact companion
    label or menu item where the icon alone would be ambiguous. Oversized
    text-only buttons are not the default shape of an action. Nothing depends
    on the symbol alone.

26. **No silent support-language fallback.** A supported learner locale owns
    every interface string its surfaces ask for. A locale with no pack at all
    falls back to English rather than showing keys, but a supported locale that
    quietly renders English is a defect, not a shortfall: the gap is detected
    by regression, recorded, and visible to whoever can close it. Learner
    material is never translated by this rule - a target-language line, title
    or passage is content.

27. **The writing revision loop.** A writing surface keeps the learner's own
    text and the feedback about it in one working context: reviewing never
    replaces the editor, and a quoted phrase is findable in the learner's text
    rather than something to hunt for by eye. Feedback leads with the few
    things worth doing now and keeps the rest whole behind progressive
    disclosure - a full report shown at once is not feedback a learner can act
    on. A review offers revision; it never substitutes generated text for the
    learner's writing, and a whole-piece rewrite is one way to say it, never
    the answer. Review is one primary action named in one word; the settings
    that steer it are secondary controls, because a learner should not have to
    understand model configuration to be read. A review that cannot be produced
    is one compact line beside the action, not a pane.

28. **Bounded before it is spent on.** Learner content is untrusted input.
    Every surface that accepts it states one product bound - shared by the
    browser, the request model, the route, the repository and the evaluator -
    and refuses what exceeds it before anything is spent: before a row, a
    tokenizer pass, a prompt or a provider call. A refusal carries the
    measurement, never the content, so an oversized request cannot put a
    learner's work into a log. Nothing is silently truncated and no encoding is
    cut mid-character: refusing a piece whole is the honest answer, keeping
    part of it is not. A database column type is not a product limit.

29. **A valid evaluation is reused, never recomputed.** Generated work that
    costs money and is deterministic in its inputs - a writing review, and
    anything like it - carries the identity it was produced under: the content,
    both languages, the relevant settings, and the version of the agreement
    that produced it. A request for the same identity is answered from what is
    stored. Reopening a piece, pressing the action again, a second tab and
    concurrent duplicates cost nothing; only a genuine change earns a new call.
    A stored answer is never served past the contract that produced it.

## The Orena Design System (D-059)

Explicit human direction, 2026-09-19: the approved Orena Design System is the
visual source of truth for the learner web. Rules 1-29 stand; this section says
how a surface looks, not what it is for. Colour values live only in
`static/orena/theme.css`; non-colour tokens (type, radius, motion, layers) in
`static/orena/foundation.css`.

30. **Three greys, one hairline.** Ground, surface and raised surface on cool
    ink; separation is a hairline. Depth on Ink is a light pool, never a drop
    shadow; Paper replaces the pool with a faint wash and a soft shadow.
31. **Violet acts, amber records.** Violet is action, navigation and
    selection; amber is progress, completion and anything earned. One filled
    violet pill per screen - the primary action. Everything else is a hairline
    surface.
32. **Domain hue in small doses.** Reading, Listening, Speaking, Dictation,
    Writing and Vocabulary each have a hue at equal weight. It appears in a
    tile, a label, a timeline fill or a transcript highlight - never as a card
    background, never as the only signal.
33. **A light pool marks the live thing.** An in-progress or selected card
    carries the bloom; everything else stays flat, so the glow itself says
    where the learner left off. At most one page-level bloom per screen.
34. **Type (D-061).** Three faces, three jobs, as the mockup draws them:
    Nunito 800 for display and headline figures, Nunito Sans for interface and
    reading copy, DM Mono for data and the small uppercase labels (Roboto Mono
    in a Vietnamese interface, which DM Mono cannot set). Han characters fall
    back to Noto Sans SC; stories keep the serif (rule 18).
35. **Radius by size.** Inline chips and covers 10px, rows and icon buttons
    14px, cards and sheets 20px, anything pressable that holds a label a pill,
    a sheet's top corners 24px.
36. **Feedback: number, then detail.** A graded surface opens with one score
    and one word, lists what went wrong as tappable items, and keeps
    dimensions, phonemes and explanations one step deeper. Wrong is never
    colour alone: it carries an underline, a dash, a glyph or a label too.
37. **Artwork is the brightest object.** Covers are 2:3, media artwork 16:9 in
    rails and 21:9 on detail pages. Until real artwork exists, content uses the
    design system's artwork slot - dark ground, domain-hued bloom, dot field -
    at the real geometry, so real artwork drops in with no layout change
    (D-060). Artwork keeps its own light in both themes.
38. **Navigation.** Exactly the approved rail: Home, Library, Vocabulary,
    Progress, then Practice with Reading, Listening, Speaking, Dictation and
    Writing, then the learner's card; each destination carries the top bar
    (global search, language pair, due chip). A phone has the five-tab bar.
    Nothing is removed to fit: Continue, Recall, Grammar, bringing your own
    content and Admin each keep a named home one step away (D-060).
39. **Designed states.** Empty is an icon, one line and one action; loading is
    a skeleton at the real geometry, never a centre-screen spinner; a failing
    service degrades one panel with two ways forward, never the whole screen.
40. **The mockup decides the interface.** The approved mockup is reproduced,
    not reinterpreted. When the backend lacks what a component shows, the
    component keeps its place and shape in the design system's unavailable
    state, and the gap is recorded in `docs/project/UI_BACKEND_GAPS.md`
    (D-060). No component is removed, hidden or redesigned because of a
    backend gap, and none shows invented data.

## The learner language contract

Orena has two learner language roles, and only two.

**Learning language** owns the material: lesson and book text, media
transcripts, target vocabulary, practice sentences, target-language prompts and
the source content itself.

**Support language** owns everything Orena itself says: navigation, labels,
controls, instructions, guidance, feedback, explanations, errors, tooltips,
status and system messages.

Learner output keeps whatever language the learner actually produced.

Generated guidance - a writing review, an explanation, a coaching note - is
**requested** in the support language, not translated around afterwards. A
stored one carries the language it was written in: a surface that cannot
establish that a saved answer matches the learner's current support language
does not replay it.

There is no third, independently chosen learner-facing interface language. A
stored legacy preference may remain for compatibility, but it no longer decides
what language the product speaks; the support language does. A mixed interface
is a defect unless the content itself deliberately contains those languages -
and a target-language title or passage appearing in target language is content,
never leakage.

A locale with no copy pack at all falls back to English rather than showing
keys. A **supported** locale is a different promise: it owns every interface
string the learner surfaces ask for, and English arriving silently in its place
is a defect. Rule 26 states it; `scripts/test_orena_learner_language.mjs`
enforces it against the surfaces themselves, and the shell reports any
shortfall where it can be fixed rather than letting it reach a learner untold.

## Art direction owner

`assets/brand/orena/` is the canonical owner of Orena's art direction and is
the Art Bible referred to by rule 14. There is no second artwork authority, and
any future `ART_BIBLE.md` belongs inside that package rather than beside it.

Its governed scope is: mascot and character, world and scene illustration,
content thumbnail, book cover, icon, badge, empty state, background and
pattern, and motion. Where that package does not yet specify part of the scope,
that is a recorded gap to be closed by an explicit art-direction task, not an
invitation for a surface to invent its own style.

## Acceptance gates (D-057)

Both gates apply to every learner-facing surface before it may be called
`REVIEWABLE`. They are additional to `docs/project/REVIEW_POLICY.md`'s existing
completion evidence, not a replacement for it.

**Beginner clarity gate.** A new-user surface fails if:

- there is no obvious primary action;
- the learner must understand an Orena metaphor before acting;
- exploration overwhelms or obscures the guided start;
- labels are clever but unclear;
- a slogan stands where an instruction is needed;
- the first content is inappropriate for a true beginner;
- a phone's first viewport hides the start or continue action beneath copy;
- English or Chinese lacks the same beginner-safe entry.

**Art gate.** A redesigned surface fails if:

- its artwork does not follow the same Art Bible, or mixes unrelated styles;
- placeholder visuals survive into the reviewed build;
- text is compensating for weak artwork or composition;
- the screen cannot be understood without reading marketing copy;
- colour is arbitrary rather than authored, or a component invents colour
  outside the semantic tokens;
- contrast fails for text, controls, interactive states, or UI over artwork;
- the narrow layout loses the meaning the wide one carries;
- English and Chinese are not both verified.

## Source of truth

```text
APPROVED RESPONSIVE ORENA WEB
→ native implementation mapping
→ SAME ORENA PRODUCT EXPERIENCE
```

Responsive web is the approved product design source of truth. Native is a full
native port, not a redesign, simplified version, WebView shell, or generic
Expo/Material/iOS reinterpretation.

## Required parity

Native must preserve, where the web experience exists:

- design tokens, colors, typography, hierarchy, spacing, surfaces, cards,
  borders, elevation, and navigation identity;
- feature behavior, information architecture, interactions, animation intent,
  focus/selection behavior, progress, and cross-skill handoffs;
- loading, empty, degraded, error, retry, offline, and authentication states;
- responsive intent across supported phone/tablet layouts;
- accessibility, reduced motion, system text sizing, keyboard/safe-area
  behavior, EN/ZH parity, and light/dark parity.

Platform mechanics may differ only when native APIs require it: permissions,
secure storage, audio/microphone, deep links, system navigation, and equivalent
accessibility controls. Those differences must preserve the same learner
outcome and truthful state.

## Review rule

Native review asks whether the implementation faithfully ports approved Orena
web behavior—not whether a reviewer prefers a different mobile design. A
native-only flow, reduced feature set, contradictory navigation, or separate
state/domain model is a product-memory regression.

## Agent checklist (derived)

A convenience checklist for an agent about to touch a learner-facing surface.
It is **derived**, not a source of law: where it and the rules above differ,
the rules above win, and this checklist is corrected. It is not a second design
contract and must never grow into one.

Before starting, read `docs/product/ORENA_PRODUCT_CONSTITUTION.md`,
`docs/product/ORENA_CONTENT_ARCHITECTURE.md`, this contract, and
`assets/brand/orena/` for visual work. Legacy UI and screenshots are evidence
of what was built, never design authority.

Before calling the work done, ask:

1. Remove the slogans mentally — is the screen still clear and still alive?
2. Remove the labels Reading / Listening / Speaking / Writing mentally — does
   the surface still give the learner a reason to enter?
3. Can a complete beginner find the next action within a few seconds?
4. Does the artwork look like one product, with no placeholder surviving?
5. Are imagery, icons and interaction doing more work than prose?
6. Does the phone layout keep the same meaning without excessive scrolling?
7. Are English and Chinese both verified, in the same batch?
8. Does every colour still come from the semantic tokens, and does contrast
   still pass — including UI placed over artwork?

Do not: redesign from a blank canvas without reading the contracts and assets;
repeat the hero template; add copy to cover weak composition; turn "world" into
lore; rename clear navigation into poetic phrases; scatter unrelated artwork
styles; ship letter or geometry placeholders; add mascot art to fill space;
make every element a rounded white card; duplicate one content item into
per-skill copies; hide core learner actions below the fold; or regress phone,
English or Chinese.
