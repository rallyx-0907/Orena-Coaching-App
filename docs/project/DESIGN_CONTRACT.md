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
   states may carry full openings and approved artwork; an activity room's
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
   helper text, errors, feedback scaffolding and labels follow the interface
   language; the learning language governs the material learned or produced.
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

How the current web implements these rules is described, not governed, in
`docs/product/ORENA_WEB_EXTENSION_GUIDE.md`.

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
