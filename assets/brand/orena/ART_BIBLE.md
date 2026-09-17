# Orena Art Bible

Part of this package, not an authority beside it. `README.md` names
`assets/brand/orena/` the canonical owner of Orena's art direction; this file is
where that owner says *how*. `BRAND_MASCOT_GUIDE.md` keeps the mascot's identity
and `AGENT_GENERATION_CONTRACT.md` keeps the generation procedure — neither is
restated here. Where this file and those two disagree about the mascot, they
win. Where this file and `docs/project/DESIGN_CONTRACT.md` disagree about how a
surface must be built, the Design Contract wins (rules 13-18, D-057).

Visual authority is `references/00_MASTER_REFERENCE_APPROVED.png`. Colour values
are `tokens/brand-tokens.json`. Nothing here licenses a new style; it describes
the one already approved so another agent can extend it without drifting.

---

## A. Overall visual language

What makes an image read as Orena, in one line:

> **Flat vector, warm light, rounded organic shapes, few elements, one clear
> subject, soft controlled shading — never outlines, never gradient haze.**

| Property | Orena | Not Orena |
| --- | --- | --- |
| Shape language | Rounded, geometric-organic. Curves meet at soft tangents; the curled tail, the leaf and the arc of the mark are the family silhouettes. | Sharp corners, hard geometry, spiky stars, perfect circles used as "bubbles". |
| Corner radius | Small elements 8-12px, cards 14-18px, covers 9px (16:9) / `5px 9px 9px 5px` (3:4, spine on the left), pills fully round. One step of radius per size class, never a mix inside one card. | 0px hard rectangles, or 28px+ blobs. |
| Softness | Soft. Edges are clean but forms are pillowy. | Rigid technical illustration; or mush with no edge at all. |
| Depth | Two or three planes: subject, mid ground, sky/ground wash. Depth by overlap and value, not by drop shadow. | Long drop shadows, bevels, glassmorphism, 3D renders. |
| Texture | Almost none. A faint paper tooth is allowed in full scenes only. | Noise overlays, grunge, halftone, photographic texture on UI art. |
| Saturation | Warm and confident in artwork — the orange really is orange. Cool tones (sage, teal, sky) sit lower in saturation and carry the distance. | Neon, fluorescent, or everything desaturated into pastel mush. |
| Contrast | Subject clearly separated from ground by value, not by stroke. | Outlined shapes; or subject and ground at the same value. |
| Lighting | One warm key, usually low and from the side — late afternoon. Shadows are a warmer or cooler hue, never grey or black. | Flat ambient light with no direction; hard black shadow; rim-light glow. |
| Density | Sparse. A scene has one subject and a handful of supporting masses. | Busy collages; twelve floating objects around a headline. |
| Playful | Present in pose, expression and small props. | Slapstick, wacky faces, exaggerated squash. |
| Editorial | Present in composition, palette restraint and generous negative space. | Corporate stock illustration; "tech startup" isometric people. |

**Palette, by role.** Values live in `tokens/brand-tokens.json`.

- `#FF7A3D` Orena Orange and `#E24A2D` Sunset Red — the subject. Fur, the key
  accent mass, the one thing the eye lands on first.
- `#0E2A47` Forest Ink — the anchor. Limbs, dark detail, deep sky, type.
- `#F8F3E9` Paper Ivory — air. Ground, page, negative space.
- `#8CA8A1` Sage — distance and calm. Foliage, mid ground, secondary mass.
- `#F2C572` Warm Ochre — light. Sun, warm ground, highlight mass.

Roughly 60% neutral (ivory, sage), 25% anchor (ink), 15% warm accent (orange,
ochre). An image where orange covers half the frame is off-model.

**The forbidden list** is `tokens/brand-tokens.json` `visual_rules.avoid`, plus:
purple/blue "AI" gradients, neon, glassmorphism, drop shadows as depth, outline
strokes on illustration, stock isometric people, emoji standing in for icons,
and `pattern/color-pallate.png` treated as a palette — it is exploratory
reference only and its gradients are not approved.

---

## B. Mascot

Identity, invariants, props and the generation procedure stay in
`BRAND_MASCOT_GUIDE.md` and `AGENT_GENERATION_CONTRACT.md`. This section only
governs **placement**.

**Use the mascot when it has a job:**

- onboarding and first-run;
- an empty state, where it explains what is missing;
- encouragement after real learner effort;
- a completion or celebration backed by real evidence;
- a recovery or error state that needs warmth;
- a page hero for a room that is *about* orientation (Discover arrival, Practice
  entry), at most one per page.

**Do not use the mascot:**

- to fill an empty hero, a short column or a gap in a grid;
- on a content card, cover or thumbnail — those belong to the content;
- inside Reader, the Listening player, the Writing editor, dictation input or a
  dense feedback surface (`BRAND_MASCOT_GUIDE.md`, "In-app philosophy");
- more than once on a screen;
- as decoration next to a headline that already says the same thing.

**Scale.** Companion 40-72px, inline moment 96-160px, page hero
`clamp(72px, 8vw, 112px)`, full scene hero up to 264px wide framed. The mascot
is never the largest element on a content surface.

**Pose and expression.** Reuse `actions/` and `expressions/` first — that is the
rule in `tokens/action-index.json`. Match the pose to the moment, not the page
title: `learn` for entering something to read, `listen` for audio, `explore` for
discovery, `celebrate` only after real achievement, `care` for recovery, `hello`
for an empty state. A mascot looking at the learner asks for attention; a mascot
looking into the scene gives attention to the content. On a content surface,
prefer the second.

**Relation to content.** The mascot never overlaps a cover, a transcript, a
learner's own text or a control. If the layout forces an overlap, the mascot is
the element that goes.

---

## C. Scene and world illustration

The six approved scenes are in `scenes/`, addressed semantically by
`static/orena/content/brand-library.js`. `references/02_POSES_AND_SCENES_REFERENCE.png`
shows the approved treatment.

- **Style.** Painterly-flat: flat vector construction with soft airbrushed
  value transitions inside the masses. No linework.
- **Perspective.** One-point or simple over-the-shoulder, horizon in the upper
  third, subject small against a large world. The learner looks *with* the
  mascot at something, rather than at the mascot.
- **Lighting.** Warm low key — sunrise or late afternoon. Atmospheric
  perspective: distant masses lift toward the sky hue and lose contrast.
- **Detail.** High in the foreground silhouette, dropping sharply with distance.
  A distant town is roof shapes, not windows.
- **Composition.** Subject on a third. Foreground framing element (leaves, a
  rock edge) in one corner. Large calm area kept free so a heading can sit over
  it if needed.
- **Saturation.** Warm subject, cooler distance. The orange mascot is the only
  fully saturated mass.
- **Brand colour.** Sky carries ochre-to-sky gradient light; land carries sage
  and ink; the subject carries orange. Do not repaint a scene to match a theme.
- **Foreground/background.** Three planes minimum. Never a subject floating on a
  flat colour field.
- **Relation to UI.** A scene carries its own painted daylight, so it is always
  shown **inside a frame** (`.brand-art[data-kind="scene"]`), never bled to the
  page edge and never used as a page background. A character on transparency
  needs no frame. This is a contract, not a preference: an unframed painted
  rectangle is what makes a light image read as broken in a dark theme.

---

## D. Content thumbnails

The rule that decides everything here:

> **If the content is a real thing in the world, show the real thing. If the
> content is Orena's own, show Orena's artwork. If it is a learning action,
> show a graphic mark. Never show a letter.**

| Content | Visual | Ratio | Notes |
| --- | --- | --- | --- |
| Real-world video | The source's own thumbnail (`poster_url`) | 16:9 | Never re-cropped to square. Duration bottom-right, play affordance on hover/focus. |
| Real-world audio / podcast | Source artwork if it exists, otherwise the audio cover system (§D.1) | 16:9 | An audio item with no artwork gets a cover, never a waveform doodle standing in for one. |
| Orena story | Illustrated cover (§D.1) | 3:4 | Reads as a book spine-and-face, warm. |
| Book | Real cover if the edition supplies one, otherwise a designed cover (§E) | 3:4 | |
| Article / passage | Designed cover (§D.1) | 3:4 | Material (`fable`, `classical_excerpt`, …) chooses the motif. |
| Conversation | Designed cover with the conversation motif | 3:4 | Two-mass composition, no faces. |
| Generated learning content | Designed cover, plus the quiet provenance the surface already shows | 3:4 | Never dressed up as a published book. |
| Learning action (dictation, shadowing, recall…) | Icon from the icon family (§F), not a thumbnail | — | An action is not content and gets no cover. |

### D.1 The designed-cover system

When no real image exists, a cover is **generated deterministically from the
content's own identity**, so the same item always draws the same cover and two
items never collide by accident. It is one system with parameters, not a style
per card.

A cover is composed of exactly three things:

1. **Ground** — one flat colour from the cover palette (warm ivory, sage, night
   ink, ochre, coral, teal), chosen by a hash of the content id.
2. **Motif** — one shape from the approved brand vocabulary, chosen by what the
   content *is*, not by its id: `leaf` (nature, growth, everyday life), `arc`
   (the curled-tail arc of the mark — story, fiction), `mountain` (journey,
   place, travel), `line` (classical, essay, reference), `spark` (idea, science,
   surprise), `wave` (a voice, audio, video), `talk` (conversation — two masses,
   no faces).
3. **Light** — a single soft warm wash in one corner, always the same direction.

No text is drawn inside a cover. No letter, no `Aa`, no `字`, no repeated
abstract rectangle, no generic gradient block. The title already sits under the
cover, set in type.

Motifs are drawn as vector shapes in the same shape language as
`pattern/*.png`, so a cover and an approved pattern asset read as one family.

**Mixed shelves.** A shelf that deliberately mixes content kinds — "around five
minutes" holding both a passage and a clip — reads as one shelf: the shelf's own
ratio wins so the row shares a baseline. The 3:4 book ratio still governs
shelves that are actually books, and the spine cue keeps a text recognisable.

**Crop and overlay.** Covers are `object-fit: cover`, centred. Title text never
sits on top of the cover; it sits beneath it, where type is legible on a theme
surface. Duration, level and language are secondary metadata: small, quiet, and
never larger than the title.

---

## E. Book covers

- The cover is the primary object. A book card is a cover with a title under it,
  and nothing else competes.
- **Never** a single-letter placeholder (`A`, `S`, `T`, `M`) and never a
  coloured square with initials. If the edition has no cover, the book gets a
  designed cover from §D.1 with the motif its genre implies.
- **Title hierarchy on a designed cover:** the cover carries no text. The card
  carries title (one or two lines, clamped) then author or source, quieter.
- **Genre variation** comes from motif and ground, not from a different
  illustration style. Fiction leans arc and warm grounds; ideas and science lean
  spark and cooler grounds; classical leans line and ink grounds.
- **Consistency.** A shelf must read as one shelf. Ground colours vary; light
  direction, motif weight, radius and ratio do not.
- **Thumbnail behaviour.** 3:4 at every size. On a phone the cover keeps its
  ratio and the card narrows; the cover is never cropped to a square or reduced
  below 96px wide, because below that the motif stops reading.

---

## F. Icons

- **Family.** One geometric-humanist set, 24px grid, 2px stroke, round caps and
  round joins, matching the rounded shape language. Existing marks live in
  `static/orena/ui/icons.js` and `symbols.js`; extend that set rather than
  importing a second icon library.
- **Outline is the default.** Fill is reserved for the **active** state and for
  an icon that is itself the subject of a tile.
- **Shape.** Simple enough to read at 16px. One idea per icon. No icon contains
  text.
- **Colour.** Icons may carry colour, and should where it helps a learner tell
  destinations apart. Colour comes from the semantic tokens in
  `static/orena/theme.css` (`--accent`, `--brand`, `--on-sage`, `--on-sun`,
  `--on-coral`, `--on-night`, `--muted`) — never from a literal hex in a
  component and never from a second `:root` block. A decorative icon inside
  artwork may use the artwork palette.
- **Container.** A coloured tile behind an icon uses a semantic surface token
  (`--sage-surface`, `--sun-surface`, `--coral-surface`, `--night-surface`) with
  its matching `--on-*` foreground, so contrast holds in every theme. Tile
  radius 12px, icon at 55-60% of the tile.
- **Active state:** filled mark, `--accent` or the tile's `--on-*`, plus a
  non-colour cue (weight, fill, or an underline) — never colour alone.
  **Inactive:** outline mark at `--muted`, same geometry, same size — an
  inactive icon never changes shape.
- **Tactile feedback.** 90-140ms scale to 0.96 on press, opacity or background
  change on hover, a visible focus ring from the shared focus token. No bounce,
  no spin.
- **Constraint.** Every icon that acts as a control meets the same AA contrast
  and 36px (32px quiet, inline 24px) target rules as any other control; an icon
  with no text label carries an accessible name.

---

## G. Backgrounds and patterns

- Default background is the theme surface. Nothing else.
- A pattern is allowed only to **separate zones** (an entry band, an empty
  state, a completion moment) — at most one per screen, and never behind text
  the learner must read.
- Approved motifs are `pattern/*.png` (`leaf`, `line`, `mountain`, `star-blink`,
  `foot-mark`) and their vector equivalents. Opacity 4-10%, single colour drawn
  from a semantic token.
- **Forbidden:** generic gradient meshes, blurred blobs, floating particles,
  purple/blue AI gradients, animated backgrounds, full-bleed landscape behind a
  working surface, `pattern/color-pallate.png` used as art.
- A background never competes with content. If removing the pattern makes the
  screen clearer, it was decoration.

---

## H. Motion

Motion explains entering, leaving, continuation, hierarchy, state change and
cause. It never performs.

| Moment | Motion | Duration / curve |
| --- | --- | --- |
| Hover on a card | Lift 2px, cover scales to 1.02 inside its frame (the frame does not move) | 160ms `ease-out` |
| Press | Scale 0.98 | 90ms `ease-out` |
| Rail swipe | Native momentum, `scroll-snap-align: start` | browser |
| Rail control | Smooth scroll by one card plus gap | 240ms, browser smooth |
| Card enter | Fade plus 6px rise, at most 4 staggered by 40ms | 200ms `ease-out` |
| Section change | Cross-fade, no slide | 180ms |
| Icon feedback | Fill swap plus 0.96 press | 120ms |
| Mascot reaction | Only at a real learner moment, once, never looping | 300-500ms |

Semantics are named so haptics or sound can be attached later without new
vocabulary: `commit` (a save or submit), `advance` (moving to the next item),
`reveal` (an answer or explanation), `celebrate` (verified achievement).
Nothing plays sound or haptics today; nothing should fake them visually either.

**Reduced motion is a hard requirement.** Under
`prefers-reduced-motion: reduce`, transforms and staggers are removed, scrolling
becomes instant (`behavior: 'auto'`, as the rail binding already does), and no
information is carried by movement alone.

---

## I. Composition

- **Fewer words.** Content title, action, essential context, metadata,
  explanation, slogan — in that order, and the last two usually do not survive.
- **Artwork, image and icon carry the life.** If a sentence and an image say the
  same thing, the sentence goes.
- **No default giant header.** A page may open with a short title. A full
  opening with a scene is earned, not routine, and appears at most once in a
  learner's path through a surface.
- **The forbidden template:** `eyebrow + giant headline + poetic slogan +
  paragraph + mascot on the right`, repeated page after page. One page may use a
  full opening; five pages using the same one is a component, not a feeling.
- **Not everything is a white rounded card.** Vary surface, ratio and weight by
  role: a cover is an image, a word is type on a tinted ground, a prompt is a
  quiet sheet, a continuation is a small dense tile. Equal-weight cards in a
  grid is the SaaS grammar D-057 exists to correct.
- **Rhythm.** Alternate dense and airy. A rail of 3:4 covers next to a rail of
  16:9 thumbnails already creates rhythm without decoration.
- **Negative space is structure**, not an empty slot waiting for a mascot.

---

## J. Examples

**DO**

- A reading rail of 3:4 covers in six different grounds, each with its motif,
  titles beneath in two clamped lines, level and time small and quiet.
- A listening card that leads with the source's real 16:9 thumbnail, duration
  bottom-right, play mark appearing on hover and focus.
- An empty Continue shelf that shows `actions/hello.png` with one short line and
  one action.
- A colourful outlined icon tile row — Reading, Listening, Speaking, Writing,
  Vocabulary — each on its own semantic surface token, used as compact doors
  beneath the content, not as the page's structure.
- A completion moment using `actions/celebrate.png` once, after real evidence.

**DON'T**

- A shelf where every cover is the same tinted rectangle with a big letter.
- `Aa 字` repeated across a row of texts.
- A hero with an eyebrow, a 48px headline, a poetic line, a paragraph and the
  mascot — on every page.
- A mascot dropped into the corner of a card because the card looked empty.
- A purple-blue gradient behind a heading to make it feel "AI".
- A landscape scene bled full-bleed behind the Reader.
- Six equal white rounded cards in a grid, distinguished only by their text.
- An icon row where every icon is the same grey outline at the same weight, so
  no destination is recognisable.

---

## Known gaps

Closed by this file: thumbnail rules, book covers, the icon family, backgrounds
and patterns, motion. `README.md`'s "Known gaps" list is superseded by this
file for those five items.

Still open, and honestly named:

- **No real book-cover artwork exists** in the repository. Every book and text
  today draws a designed cover from §D.1. Real covers are an asset decision per
  edition, alongside the rights decision that governs the text itself.
- **No approved audio/podcast artwork** exists for curated listening items that
  arrive without a `poster_url`.
- **Icon set coverage** is partial: `icons.js` and `symbols.js` cover the
  current surfaces, and a new learning action may need a new mark drawn to §F.
- **No motion tokens** exist in `theme.css`; the durations in §H are stated here
  and implemented per surface until a shared token set is introduced.
