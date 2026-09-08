# Orena Product DNA v0.1

Status: ACTIVE FOUNDATION  
Scope: learner-facing Orena product surfaces  
Primary launch platform: Web  
Portability target: Mobile without rethinking the product

## 1. Product identity

Orena is not a Writing app with extra modules.

Orena is a language-learning world where learners explore content they care about and Orena quietly turns that exploration into listening, understanding, speaking, writing, remembering, and improvement.

Core loop:

```text
Explore → Understand → Practice → Produce → Remember
```

Skills are learning mechanisms. They are not required to be the primary navigation metaphor.

## 2. Emotional north star

A learner should open Orena and feel:

1. There is something here I want to explore.
2. I can start without needing discipline first.
3. The product feels alive, warm and intentional.
4. Once I start learning, the interface becomes focused and calm.
5. Finishing gives me a small sense of progress and reward.

New UX principle:

> The learner should always see something they want to do next.

This complements, but does not replace, usability clarity.

## 3. Product modes

### Explore mode

Purpose: create curiosity and voluntary entry into learning.

Allowed:
- rich artwork
- varied card sizes
- world imagery
- character presence
- meaningful color
- featured content
- discovery rails
- light motion

Avoid:
- KPI-first layouts
- sterile tool menus
- identical white card grids
- skill taxonomy dominating the page

### Learning mode

Purpose: protect attention.

Characteristics:
- fewer competing objects
- clear primary action
- quieter surfaces
- restrained decoration
- strong content hierarchy
- precise feedback

### Reward mode

Purpose: make completion emotionally meaningful.

Allowed:
- mascot reaction
- stronger color
- motion
- collectible or milestone treatment
- clear recap of what was learned

Rhythm:

```text
Excite → Focus → Reward
```

## 4. World-first information architecture

Primary content graph:

```text
Language
→ World
→ Zone
→ Journey
→ Lesson
→ Activity
```

Example:

```text
Chinese
→ Food & Culture
→ Night Market
→ Ordering Food
→ Lesson 01
→ Listen / Comprehension / Vocabulary / Grammar Notice / Shadow / Speak
```

World examples:

English:
- Daily Life
- Study & Work
- Travel
- Stories & Media
- Social English
- Thinking & Ideas

Chinese:
- Everyday Chinese
- Food & Culture
- City Life
- Festivals
- Real Conversations
- Characters & Expressions

Worlds are product experiences, not folders.

## 5. Web-first, platform-neutral underneath

Orena launches on Web first.

Architecture principle:

> Shared meaning, adaptive composition.

Share across platforms:
- domain models
- API contracts
- progress semantics
- activity contracts
- content graph
- design tokens
- component semantics
- interaction states
- EN/ZH learning rules

Do not require identical rendering across platforms.

Desktop may show more useful content simultaneously because it has more space. Mobile may sequence the same meaning vertically or behind gestures.

Do not shrink desktop into mobile.

## 6. Home vs Progress

### Home

Home exists to create motivation, discovery and continuation.

Home may show lightweight progress cues when they help the next action, for example:

```text
Night Market Adventures · 62%
```

Home must not become an analytics dashboard.

### Progress

Progress is a separate destination for reflection and learning analytics.

It owns:
- time trends
- skill trends
- journey completion
- review consistency
- learned phrases / vocabulary / patterns
- strengths
- weak points
- AI learning insights
- weekly / monthly reflection
- milestones

Rule:

> Progress indicators are allowed on Home. Progress analytics are not.

## 7. Visual identity

Working art direction:

> Warm Language Adventure

Orena should feel:

```text
Warm
×
Curious
×
Illustrated
×
Tactile
×
Modern
×
Human
```

Not:
- corporate SaaS
- generic AI app
- Duolingo clone
- cyberpunk
- default component-library demo
- empty minimalist productivity tool

Visual model:

> travel journal + illustrated learning world + modern product interface

## 8. Red panda character

The Orena red panda is a brand character, not random decoration.

Use for:
- discovery moments
- guidance
- empty states
- daily challenge
- completion
- streak/milestones
- onboarding
- seasonal moments

A future production mascot library must lock:
- head/body ratio
- eye shape
- muzzle
- ear shape
- tail rings
- fur treatment
- palette
- lighting
- facial language
- pose system

Do not generate a new interpretation per screen.

Do not use the mascot to fill empty space without purpose.

## 9. Color philosophy

Orena Orange remains the brand anchor.

The product may use semantic world/skill color families so the experience is richer than orange + white + gray.

Suggested semantic families:
- Listening: jade / teal
- Speaking: coral
- Writing: plum / violet
- Reading: indigo / blue
- Grammar / culture: amber / gold
- Review / retention: mint / green

Color must preserve hierarchy. Rich does not mean every object is saturated.

## 10. Anti-AI-aesthetic rules

Forbidden defaults:
- generic SaaS dashboard
- identical feature-card grids
- arbitrary purple-blue gradients
- glassmorphism without product meaning
- pills everywhere
- outline icons as the main personality
- huge empty hero with slogan only
- analytics blocks on every page
- nested cards without hierarchy
- decorative sparkles as AI identity
- emoji as production iconography
- stock-illustration look
- AI-generated text baked into artwork
- one-off visual systems per screen

A page should feel composed, not assembled.

## 11. Page grammar

Orena does not use one giant template.

It uses reusable composition recipes built from approved product components.

Examples:

```text
Hero + Mosaic + Rail
Hero + Two Column + Rail
Feature Card + Grid + Story Strip
Focused Content + Side Context
```

Pages may vary in composition while preserving shared visual DNA.

## 12. Backend philosophy

Backend returns meaning, not layout.

Backend owns:
- content identity
- learning semantics
- ordering / relevance
- learner state
- progress
- availability
- permissions
- personalization

Frontend owns:
- columns
- card width
- rail vs grid
- responsive placement
- visual density

Reliability rules:
1. User work must be durable.
2. AI failure must not equal product failure.
3. Mutations must be idempotent.
4. Resume must always work.
5. Content versioning must not corrupt learner history.
6. Loading / empty / error states are product states, not afterthoughts.

## 13. English and Chinese parity

English and Chinese are first-class.

They share structural product models but may require language-specific metadata and UI behavior.

Chinese may require:
- hanzi
- pinyin
- tone
- word segmentation
- classifier
- grammar pattern

English may require:
- lemma
- pronunciation
- stress
- collocation
- grammar pattern

Do not translate English pedagogy mechanically into Chinese.

## 14. Implementation precedence

For screens migrated to the Orena Product UI System, the ORENA_* foundation documents define UI/product behavior.

Existing BECOMING release gates, persistence rules, auth rules, security rules and functional contracts remain valid unless explicitly superseded.

If a legacy BECOMING visual rule conflicts with an ORENA_* visual/product rule on a migrated screen, ORENA_* wins for UI/UX only.

## 15. Product acceptance questions

Before a learner-facing screen is approved, ask:

Brand:
- If the logo were hidden, does this still feel like Orena?

Emotion:
- Is there something the eye wants to stop on?
- Is there something the learner wants to click?

Hierarchy:
- Is the first useful action obvious?

Distinctiveness:
- Could this be mistaken for a generic SaaS template?

Density:
- Does it feel rich without becoming exhausting?

Production:
- Can this be expressed with reusable components and responsive rules?

Storefront test:
- Would this screenshot make someone want to see the next screenshot?

## 16. Foundation principle

> Surface abundance, structural simplicity.

The learner may perceive a rich world.

The engineering system underneath should remain small, reusable and predictable.
