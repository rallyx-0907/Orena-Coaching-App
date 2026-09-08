# Orena Home Golden Spec v0.1

Status: DESIGN BASELINE  
Route: Home  
Launch surface: Web  
Reference widths: 1440 / 1024 / 390  
Composition recipe: Hero + Mosaic + Rail

## 1. Home job

Home exists to make the learner want to begin or continue something.

It is not:
- a KPI dashboard
- a feature directory
- a skill taxonomy wall
- an admin overview
- a progress analytics page

Home product statement:

> Where do you want your language journey to take you today?

The exact copy may change through localization/product writing. The emotional role must remain.

## 2. Desired first impression

Within a few seconds the learner should experience:

```text
This feels alive.
→ There are interesting places to explore.
→ I know what I can continue right now.
→ I want to click something.
```

## 3. Visual baseline

Direction:

```text
Warm Language Adventure
```

Home is:
- light-first
- warm neutral canvas
- orange brand anchor
- rich artwork concentrated in discovery surfaces
- varied visual rhythm
- one dominant hero
- no analytics wall
- tactile but not glassy
- playful without becoming childish

Red panda presence is welcome in hero/challenge moments, using approved character assets only.

## 4. Desktop 1440 composition

Target structure:

```text
┌──────── OrenaSidebar ────────┬────────────────────────────────────┐
│                              │ JourneyHero                         │
│ Home                         │ + Continue Journey                  │
│ Explore                      ├─────────────────────────────────────┤
│ Practice                     │ Explore Worlds                     │
│ Review                       │ [world][world][world][world][world]│
│ Progress                     ├──────────────────────┬──────────────┤
│                              │ For You Today        │ Challenge    │
│                              │ recommendations      │              │
│                              ├──────────────────────┴──────────────┤
│                              │ Continue Exploring / Orena's Pick   │
└──────────────────────────────┴─────────────────────────────────────┘
```

Desktop should intentionally let several meaningful sections be visible at once.

Do not reduce card sizes merely to force every possible item into one screen.

## 5. Tablet 1024 composition

Expected:
- compact shell/sidebar
- hero remains dominant but shorter
- worlds become 2–3 columns or compact rail
- For You and Challenge may remain two-column if readable
- lower discovery may stack
- no desktop-only dead space

## 6. Mobile Web 390 composition

Expected order:

```text
OrenaTopBar
JourneyHero
ContinueJourneyCard
Explore Worlds horizontal rail
For You Today
Challenge
Continue Exploring / Orena's Pick
OrenaBottomNav
```

Mobile does not need to show all Home sections in one viewport.

No attempt should be made to shrink the desktop layout into 390px.

## 7. Required sections

### A. JourneyHero

Purpose:
Emotional entry point + one primary action.

Content:
- contextual greeting optional
- one strong learner-facing question/statement
- cinematic world artwork
- red panda optional
- primary CTA: Continue journey or Explore

Rules:
- one dominant CTA
- no metrics
- no feature checklist
- no empty marketing-only space
- artwork and copy must feel integrated

### B. Continue Journey

Purpose:
Resume real learner state.

Example semantics:

```text
Night Market Adventures
Episode 3
62%
Continue
```

Data must be learner-backed.

If there is no current journey:
- replace with a discovery-oriented starting state
- do not invent fake progress

### C. Explore Worlds

Purpose:
Make Orena feel explorable.

Minimum useful initial world set should be editorially coherent for the selected language.

Examples for Chinese:
- Everyday Chinese
- Food & Culture
- City Life
- Real Conversations
- Festivals
- Characters & Expressions

Examples for English:
- Daily Life
- Travel
- Study & Work
- Stories & Media
- Social English
- Thinking & Ideas

Each WorldCard should feel like entering a place, not clicking a folder.

### D. For You Today

Purpose:
Offer low-friction entry points based on real availability and, when available, learner relevance.

Possible items:
- 3-min Listen
- New Phrases
- Shadowing
- Quick Challenge
- Story
- Grammar in Context

Do not expose raw skill taxonomy as a boring menu.

### E. Challenge

Purpose:
Create one small, concrete reason to act now.

Examples:
- collect/use 3 useful phrases
- complete one short shadowing attempt
- finish one quick comprehension set

Challenge should relate to meaningful learning evidence.

Avoid gambling/casino reward patterns.

### F. Continue Exploring

Purpose:
Keep the lower page emotionally alive.

This section replaces Home analytics.

Candidate editorial labels:
- Continue Exploring
- Orena's Pick
- Recently Discovered
- Try Something Different
- From This World
- Popular Journeys

Detailed progress statistics belong to /progress.

## 8. Explicitly forbidden on Home

Do not place a large analytics block containing combinations such as:

```text
Lessons
Minutes
Streak
Accuracy
Weekly chart
Skill radar
Monthly trend
```

A lightweight streak cue may appear in global chrome when useful.

A progress percentage may appear on the specific journey it belongs to.

Detailed analytics belong to Progress.

## 9. Navigation

Desktop primary navigation:

```text
Home
Explore
Practice
Review
Progress
```

Secondary account destinations:
- Profile
- Settings
- Help where needed

Prefer account/avatar access for secondary destinations.

## 10. Backend semantic data

Home should be able to render from semantic data shaped approximately like:

```json
{
  "language": "zh",
  "continue_journey": {
    "journey_id": "night-market-adventures",
    "title": "Night Market Adventures",
    "subtitle": "Episode 3",
    "progress": 0.62,
    "artwork": "asset-ref",
    "resume_target": "lesson-or-activity-ref"
  },
  "worlds": [],
  "recommendations": [],
  "challenge": null,
  "discoveries": []
}
```

This is a semantic example, not a frozen API schema.

Backend must not send pixel layout decisions.

## 11. Resilience behavior

### Loading

- Hero may show a stable skeleton/placeholder composition.
- Sections may load independently.
- Avoid replacing the whole Home with a spinner.

### Partial API failure

- Keep successfully loaded sections.
- Show a scoped retry state for the failed section.
- Do not erase durable continue/progress data because recommendations fail.

### AI/provider failure

- Home still functions.
- Curated/default discovery remains available.
- Learner progress remains visible.

### Empty learner history

Home becomes discovery-first:
- strong hero
- Worlds
- starter recommendations
- beginner challenge if appropriate

Do not fake historical activity.

## 12. EN / ZH rules

Home structure is shared.

Content is not a mechanical translation.

Chinese:
- CJK typography
- Chinese world naming
- language-specific learning metadata where surfaced
- pinyin only when pedagogically useful, not on every decorative card

English:
- natural English category/content naming
- avoid school-textbook jargon where emotional labels work better

Both:
- equal visual quality
- equal route functionality
- equal state coverage

## 13. Artwork production rules

World/hero artwork:
- no baked-in UI text
- no random stock-photo mixture
- consistent art direction
- stable scene language
- controlled palette
- reusable asset IDs
- responsive safe zones

Mascot:
- approved asset only
- no one-off generated reinterpretation
- expression/pose must match context

## 14. Interaction rules

WorldCard:
- clear click target
- subtle hover lift on pointer devices
- visible keyboard focus
- pressed feedback

Recommendation:
- one primary action
- duration/type metadata stays secondary

Continue:
- navigates to persisted resume target
- no progress mutation merely from rendering Home

Challenge:
- opens challenge context or activity
- mutations idempotent

## 15. Production-realism check

Before coding, confirm:

1. Every visible block maps to an approved component.
2. Artwork has a real aspect-ratio container and crop rule.
3. 1440 / 1024 / 390 composition is defined.
4. Loading / empty / partial error states are defined.
5. Backend data is semantic.
6. No Home analytics block remains.
7. No new visual token is needed without review.

## 16. Implementation scope for Golden Home v0.1

Implement only what this Home requires.

Expected first product-component scope:

```text
OrenaAppShell
OrenaSidebar
OrenaTopBar
OrenaBottomNav
JourneyHero
ContinueJourneyCard
WorldCard
WorldRail
RecommendationTile
RecommendationRail
ChallengeCard
DiscoveryCard
DiscoveryRail
```

Do not pre-build the complete future Orena component library.

## 17. Visual QA gate

Required screenshots:
- 1440 desktop
- 1024 tablet
- 390 mobile web

Review dimensions:

```text
Emotional pull
Hierarchy
Brand distinctiveness
Artwork integration
Composition rhythm
Typography
Density
Responsive adaptation
Interaction clarity
Production fidelity
```

The three largest gaps must be fixed before Home is called Golden.

Source inspection alone is not visual approval.

## 18. Golden rule

> Home is not where Orena proves how many features it has.

> Home is where Orena makes the learner want to start something.
