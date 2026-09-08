# Orena Responsive Composition Contract v0.1

Status: ACTIVE FOUNDATION

## 1. Core principle

> Shared meaning, adaptive composition.

Responsive Orena does not mean shrinking desktop until it fits mobile.

The same product meaning, state and action hierarchy must survive across viewports, while composition changes to use each screen well.

## 2. Why Web is first

Web is the first launch surface because it can ship without a mobile-store dependency.

The Web implementation must still protect future mobile portability by keeping:
- domain logic platform-neutral
- API contracts semantic
- component semantics reusable
- responsive mobile-web behavior deliberate
- product decisions independent of desktop-only layout

## 3. Three reference widths

Every Golden learner screen must be reviewed at:

```text
Desktop:    1440px
Tablet:     1024px
Mobile Web: 390px
```

These are review anchors, not the only supported widths.

Layouts must interpolate safely between them.

## 4. Desktop principle

Desktop has more space, therefore it may increase simultaneous visibility.

Goal:

> Let the learner understand more of the useful product landscape without unnecessary navigation.

Desktop may show at the same time:
- hero / continuation
- worlds
- recommendations
- challenge
- discovery

This is a strength of Web and should be used.

Do not fill desktop merely because space exists.

## 5. Tablet principle

Tablet is the transition composition.

Expected behavior:
- sidebar may compact
- multi-column regions reduce columns
- secondary panels may stack
- rails may replace large grids
- hero proportions reduce
- text remains readable without desktop-scale empty space

Tablet must be intentionally composed, not treated as a broken desktop.

## 6. Mobile Web principle

Mobile optimizes progressive discovery.

Goal:

> Show the most desirable next thing first, then let the learner discover more by scrolling or tapping.

Typical Home sequence:

```text
Hero
→ Continue
→ Worlds
→ For You
→ Challenge
→ Continue Exploring
→ Bottom navigation
```

Not every desktop section needs to be visible in the first mobile viewport.

That is correct behavior.

## 7. Information parity vs simultaneous visibility

Required:
- same core learner goal
- same primary action semantics
- same content identity
- same progress identity
- same permissions
- same durable state

Not required:
- same number of cards visible at once
- same navigation chrome
- same section side-by-side relationship
- same card dimensions
- same artwork crop
- same number of columns

Rule:

> Preserve information access, not simultaneous visibility.

## 8. Navigation composition

### Desktop 1200+

Default:
- persistent OrenaSidebar
- content canvas to the right
- optional compact OrenaTopBar

Primary destinations:

```text
Home
Explore
Practice
Review
Progress
```

Profile / Settings normally live under account/avatar controls.

### Tablet 640–1199

Allowed:
- compact sidebar
- icon + label rail
- collapsible navigation
- top navigation when better for the route

Do not let navigation consume disproportionate learning space.

### Mobile <=639

Default:
- compact top bar for brand/context
- bottom navigation for primary destinations
- drawers/sheets for secondary controls

## 9. Grid and rail behavior

### WorldRail

Desktop:
- 4–6 useful worlds visible depending on available width
- may use a mosaic or consistent art-card row
- avoid tiny cards merely to show all worlds

Tablet:
- 2–3 columns or compact horizontal rail

Mobile:
- horizontal rail preferred when it preserves artwork scale
- a View all route is allowed

### RecommendationRail

Desktop:
- row, 2-column panel, or mixed strip
- may appear beside ChallengeCard

Tablet:
- compact row/grid

Mobile:
- list or horizontal rail
- one clear tap target per recommendation

### DiscoveryRail

Desktop:
- may expose several discovery cards at once

Mobile:
- progressively revealed below primary sections

## 10. Hero adaptation

### Desktop

Hero may:
- span wide
- use cinematic artwork
- place copy and character in separate safe zones
- include compact ContinueJourneyCard within or adjacent to hero

### Tablet

Hero:
- reduces visual height
- protects text legibility
- may bring ContinueJourneyCard below primary copy

### Mobile

Hero:
- may use 4:3 artwork
- copy may move over a safe darkened area or below artwork
- CTA remains obvious
- continuation may become its own block

Never crop the mascot/subject blindly.

Use the safe subject inset from design tokens.

## 11. Typography adaptation

Do not scale every text token linearly.

Desktop:
- strong display hierarchy is allowed

Tablet:
- reduce display size before reducing body readability

Mobile:
- prioritize line length and scanning
- avoid oversized hero text that consumes the viewport
- keep body at accessible size

Chinese:
- preserve appropriate CJK line-height
- do not condense characters to mimic Latin display treatment

## 12. Spacing adaptation

Use tokens only.

General intent:

```text
Desktop → more breathing room and stronger section separation
Tablet  → compact but still editorial
Mobile  → tighter horizontal spacing, deliberate vertical rhythm
```

Do not collapse every gap to the minimum on mobile.

## 13. Interaction adaptation

Desktop may use:
- hover previews
- pointer affordances
- keyboard focus
- wider contextual surfaces

Mobile must not require hover.

Mobile may use:
- horizontal swipe
- bottom sheet
- progressive disclosure
- tap-to-open
- sticky bottom action in focused learning flows

Interaction semantics must remain equivalent.

## 14. Artwork rules

Artwork is content, not background filler.

Required:
- alt/semantic labeling where appropriate
- stable aspect-ratio containers
- safe subject zone
- controlled crop
- no baked-in UI text
- no unique mascot generation per viewport

Desktop may reveal more of the scene.

Mobile may crop tighter while preserving the focal subject.

## 15. Loading, empty and error composition

Responsive states are part of the screen contract.

Loading:
- skeletons preserve section rhythm
- avoid layout jumps where possible

Empty:
- explain what can happen next
- use character/art sparingly and intentionally

Error:
- keep already loaded durable learner data visible
- isolate failed section when possible
- AI/provider failure must not blank the whole page

## 16. Future mobile-portability gate

Before a Web screen is declared Golden, review:

1. Does business logic depend on DOM layout?
2. Does the API return layout-specific values?
3. Are semantic components separable from HTML-specific implementation?
4. Does the 390px composition already define content priority?
5. Would React Native need to rethink the page, or only re-render it?

Desired answer to #5:

> Re-render it.

The mobile client may use native primitives and different composition. It must not have to rediscover the product.
