# DESIGN_CONTRACT — 2026-09-17 direction patch
## Merge into `docs/project/DESIGN_CONTRACT.md`

> Durable UI/UX rules. This patch should become authoritative for new design work and design refactors.

## 1. Core experience law

Orena must satisfy:

> **Clarity first. Curiosity next. Depth over time.**

> **Simple front door. Deep world behind it.**

A screen can be visually rich without being conceptually complicated.

## 2. Less words, more life

Use:

> **Show first. Say only what is needed.**

Do not default every page to:

- eyebrow;
- giant headline;
- poetic slogan;
- explanatory paragraph;
- mascot on the side.

Headlines and slogans are not a substitute for hierarchy, artwork, content or interaction.

Screen copy priority:

1. content title;
2. action;
3. essential context;
4. metadata;
5. optional explanation;
6. slogan/marketing prose last.

If a screen feels empty, fix content density, composition, imagery or hierarchy before adding copy.

## 3. Artwork is a system, not decoration

All production artwork must belong to one shared Art Bible.

The Art Bible must govern:

- mascot/character;
- scene illustration;
- content thumbnail;
- book cover;
- icon;
- badge;
- empty state;
- background/pattern;
- motion.

Do not mix unrelated rendering styles without an explicit system.

Artwork must do at least one useful job:

- identify content;
- create curiosity;
- communicate mood;
- support navigation;
- create continuity;
- explain meaning;
- reinforce a learning action.

Do not add artwork only to fill empty space.

## 4. Content imagery has visual authority

On Discover, Library, Reading and Listening surfaces:

- covers;
- thumbnails;
- scenes;
- meaningful imagery;

should usually be more visually prominent than metadata.

Production UI must not rely on generic placeholders such as:

- single letters A/S/T/M;
- repeated `Aa 字`;
- repeated abstract rectangles;
- generic geometric thumbnail blocks.

Placeholders are development-only.

## 5. Color

The brand foundation remains coherent, but content artwork and icons may use vivid colors.

Allowed direction:

- warm;
- vivid;
- playful;
- editorial;
- memorable.

Do not force all content into muted beige/navy/sage if doing so makes the product lifeless.

Colorful does not mean random. Saturation, contrast and palette relationships must be controlled by the Art Bible.

## 6. Icons

Do not default all learner-facing icons to gray outline icons.

Icons may use:

- color;
- fill;
- shape;
- small illustration;
- active/inactive states;
- subtle tactile motion;

when it improves comprehension and personality.

## 7. Beginner clarity

A learner with no prior app experience must see an obvious next action.

Do not make beginner entry depend on understanding:

- "world";
- "journey";
- "intention";
- modality terminology;
- internal learning architecture.

Do not replace familiar navigation terms with poetic language if comprehension becomes worse.

Guided start and exploration must coexist.

## 8. "World" constraint

"World" is an internal design idea, not a requirement to create fantasy UI.

Forbidden interpretations include:

- learner-facing lore;
- "traveler/adventurer" framing by default;
- fantasy naming for basic navigation;
- decorative landscapes with no functional/content role;
- poetic copy everywhere.

Worldness should come from the richness and connectedness of actual content.

## 9. Discover

Discover is not required to hide Reading or Listening.

However, the entire surface must not be organized only as a list of skill modules.

Use content/topic/theme/context/mood/continuity where helpful.

Horizontal content rails are valid when:

- they remain compact;
- mobile reveals the next card;
- horizontal gestures do not block vertical scrolling;
- content imagery/title leads;
- metadata stays secondary.

## 10. Library

Library may be practical.

It should prioritize:

- cover/thumbnail;
- title;
- simple browsing;
- search/filter when needed.

Do not overload cards with metadata.

Detail belongs deeper in the flow.

## 11. Focused learning modes

When a learner enters Reader, Listening, Writing, Speaking or another focused learning experience:

> **world recedes, content comes forward.**

Reduce navigation noise.

Keep core learning assistance within reach.

Do not add decorative immersion that competes with the learning task.

## 12. Typography

Preferred high-level rule:

> **UI speaks sans. Stories/editorial content may speak serif.**

Do not apply serif/sans randomly by component.

## 13. Art acceptance gate

Before approving a redesigned screen, verify:

- artwork follows the same Art Bible;
- imagery is not a random mixture of styles;
- placeholder visuals are removed;
- text is not compensating for weak artwork;
- the screen is understandable without reading marketing copy;
- color is lively where useful but not arbitrary;
- mobile remains clear;
- English and Chinese remain first-class.

## 14. Beginner acceptance gate

A new-user screen fails if:

- there is no obvious primary action;
- the learner must understand an Orena metaphor before acting;
- exploration overwhelms the guided start;
- labels are clever but unclear;
- the first content is inappropriate for a true beginner;
- mobile hides the start/continue action below unnecessary copy.
