# Orena Component Contract v0.1

Status: ACTIVE FOUNDATION

This document defines how agents build Orena interfaces.

The goal is not one universal template.

The goal is a small, reusable product UI kit plus composition recipes so an agent rarely designs from a blank canvas.

## 1. Required build hierarchy

Agents must think in this order:

```text
Design Tokens
→ UI Primitives
→ Orena Product Components
→ Composition Recipe
→ Page-specific content
```

Do not jump from requirements directly to custom page markup.

## 2. Rule of reuse

Before creating a new component:

1. Check whether an approved Orena component already expresses the same semantic role.
2. Check whether the difference is content, state or size rather than a new component.
3. Prefer a documented variant over a fork.
4. Add a new product component only when the semantic role is genuinely new.

Forbidden:
- local card styles copied and modified per route
- one-off spacing systems
- arbitrary shadows
- page-specific button grammar
- duplicated loading patterns
- duplicated progress semantics

## 3. UI primitives

Foundation set:

```text
Button
IconButton
Surface
Text
Heading
Badge
ProgressBar
Avatar
Divider
Tooltip
Popover
Modal
Drawer
Tabs
Skeleton
EmptyStateBase
ErrorStateBase
```

Primitives do not define page personality by themselves.

Production iconography must use the approved icon/asset system. Emoji are not production icons.

## 4. Product shell components

### OrenaAppShell

Owns:
- desktop sidebar placement
- tablet shell behavior
- mobile-web top/bottom navigation behavior
- global canvas
- safe content width
- global account controls
- theme application

Does not own page-specific hero or page-specific content order.

### OrenaSidebar

Desktop navigation surface.

Primary learner destinations:

```text
Home
Explore
Practice
Review
Progress
```

Profile and Settings should normally live under the account/avatar affordance.

### OrenaTopBar

Owns contextual/global actions such as:
- language identity
- notifications when applicable
- compact streak cue when useful
- account avatar

Do not turn the top bar into a metric strip.

### OrenaBottomNav

Mobile-web/mobile composition.

Must preserve the same primary destination semantics, but does not have to mirror desktop chrome pixel-for-pixel.

## 5. Home product components

These are the first approved product components to implement.

### JourneyHero

Purpose: create the dominant emotional entry point and expose one obvious continuation action.

Semantic props:

```text
eyebrow?
title
supportingText?
artwork
primaryAction
continueJourney?
themeVariant?
```

Rules:
- one dominant CTA
- artwork preserves subject safe area
- no KPI wall inside hero
- may include a compact continuation object
- desktop may use a wide cinematic composition
- mobile may stack text and continuation differently

### ContinueJourneyCard

Purpose: resume real persisted learner progress.

Semantic props:

```text
journeyId
title
subtitle?
artwork
progress
resumeLabel
lastActivity?
```

Rules:
- progress must be real learner state
- duplicate click/tap must not duplicate progress mutations
- ambiguous legacy progress must not be falsely reassigned
- continuation is not analytics

### WorldCard

Purpose: make a World feel like a place to enter, not a category menu.

Semantic props:

```text
worldId
title
description?
artwork
journeyCount?
progress?
accentFamily?
```

Variants:

```text
featured
standard
compact
```

Rules:
- artwork is primary
- title stays legible without text baked into the image
- avoid identical white icon cards
- journey count is supporting metadata, never the visual hero

### WorldRail

Purpose: expose multiple worlds while preserving rhythm and discovery.

May render as:
- desktop grid/mosaic
- tablet compact grid
- mobile horizontal rail

The semantic component remains WorldRail; composition adapts.

### RecommendationTile

Purpose: surface one personalized or editorially selected learning opportunity.

Semantic props:

```text
contentId
contentKind
title
subtitle?
artwork?
duration?
learningSignals?
reason?
```

Examples:
- 3-min listen
- new phrases
- shadowing
- quick challenge
- story

Do not expose implementation language such as “AI recommendation score”.

### RecommendationRail

Purpose: group RecommendationTile items.

May appear as:
- row on desktop
- multi-column panel on tablet
- list/rail on mobile

### ChallengeCard

Purpose: create one small, concrete motivational challenge.

Semantic props:

```text
challengeId
title
description?
current
target
rewardCopy?
primaryAction
mascotPose?
```

Rules:
- challenge must relate to meaningful learning activity
- avoid casino-like reward language
- progress must be durable
- mascot is optional and uses approved asset library only

### DiscoveryCard

Purpose: invite continued exploration after the primary Home sections.

Examples:
- Continue Exploring
- Orena's Pick
- Recently Discovered
- Story collection
- World spotlight

### DiscoveryRail

Purpose: keep the lower Home experience exploratory instead of analytical.

## 6. Future product components

Add only when their first real page requires them.

Expected future families:

```text
WorldHero
ZoneCard
JourneyCard
LessonCard
LessonHero
AudioPlayer
VideoPlayer
QuestionCard
TranscriptPanel
PhraseCard
GrammarNotice
ShadowCard
SpeakingResponse
WritingResponse
ReviewCard
LessonSummary
ProgressStory
SkillGrowthPanel
LearningInsight
MilestoneCard
```

Do not pre-build these merely because they are listed here.

## 7. Component states

Every interactive product component must define:

```text
default
hover
focus-visible
pressed
disabled
loading
empty where applicable
error where applicable
completed where applicable
selected where applicable
```

Loading should preserve layout where practical.

Do not hide asynchronous work without immediate state feedback.

## 8. Page composition recipes

Recipes are composition grammar, not rigid templates.

### Recipe A — Hero + Mosaic + Rail

Use for:
- Home
- World discovery
- campaign/season discovery

### Recipe B — Hero + Two Column + Rail

Use when:
- one dominant object needs supporting context
- desktop can benefit from simultaneous visibility

### Recipe C — Feature + Grid + Story Strip

Use for:
- discovery-heavy pages
- collections
- thematic worlds

### Recipe D — Focused Content + Side Context

Use for:
- learning mode
- lesson activity
- review
- speaking/listening work

Agents may not invent a new recipe casually. A new recipe requires a clear product reason.

## 9. Adaptive composition

The same product component may compose differently by viewport.

Example:

```text
WorldRail
desktop → 4–6 visible cards / mosaic
tablet  → 2–3 column grid
mobile  → horizontal rail
```

Do not create three unrelated product concepts for three viewport sizes.

## 10. Design-token compliance

Use ORENA_DESIGN_TOKENS.json.

No new:
- color
- radius
- shadow
- spacing
- motion timing

without a documented reason and review.

Page-specific artwork colors are allowed as content assets. They do not become interface tokens automatically.

## 11. Content vs presentation

Backend returns semantic content.

Components receive semantic props.

Avoid props such as:

```text
desktopColumnSpanFromServer
mobileCardWidthFromServer
leftPanelPixelWidthFromAPI
```

Allowed presentation hints should stay abstract, for example:

```text
priority = featured | standard
```

Frontend decides the actual composition.

## 12. EN / ZH component rule

Components must:
- survive both English and Chinese labels
- support CJK line-height and font mechanics
- not rely on English word length
- preserve semantic parity
- allow language-specific metadata where learning requires it

Do not force Chinese text into Latin typographic tricks.

## 13. Accessibility

Minimum:
- keyboard reachable interactive controls
- visible focus state
- semantic buttons/links
- 44px minimum mobile touch targets
- useful alt/label semantics for artwork and controls
- reduced motion support
- no critical meaning encoded by color alone

## 14. Agent implementation rule

An agent implementing a migrated Orena screen must state before coding:

```text
1. Which composition recipe is used?
2. Which approved product components are reused?
3. Which new product component, if any, is truly required?
4. Which backend semantic data feeds each component?
5. How does the composition change at 1440 / 1024 / 390?
```

If the agent cannot answer these, it is not ready to code.

## 15. Visual completion gate

A major screen is not visually complete from source inspection.

Required:

```text
implement
→ render at 1440
→ render at 1024
→ render at 390
→ compare to Golden Spec
→ identify top 3 gaps
→ fix shared causes first
→ render again
```

A screen that renders but violates Orena product grammar is not DONE.
