# Orena Golden Home — H1 Implementation Brief

Baseline branch: `claude/integration-v2`  
Expected baseline commit before H1: `d263d42`  
Purpose: build the first real reusable Orena UI component layer and migrate the Home body away from the legacy Writing-dashboard composition without destabilizing the rest of the product.

## 0. Read first

Follow repository startup and governance. For this UI batch, additionally read:

1. `docs/project/DESIGN_CONTRACT.md`
2. `docs/ORENA_PRODUCT_DNA.md`
3. `docs/ORENA_DESIGN_TOKENS.json`
4. `docs/ORENA_COMPONENT_CONTRACT.md`
5. `docs/ORENA_RESPONSIVE_COMPOSITION.md`
6. `docs/ORENA_HOME_GOLDEN_SPEC.md`

Do not infer product direction from BECOMING names.

## 1. Audit facts already established

The current Home is not a suitable base for cosmetic tweaking:

- `static/becoming/screens/home.js` is ~46 KB and is still organized around Writing/dashboard evidence.
- It loads dashboard, essays, learning memory, practice recommendations, practice outcomes, reading history, speaking history, cross-skill cue, Library state, local Listening resume/habit, then renders many same-weight panels.
- `static/becoming/orena/home.css` explicitly describes the old composition as “current piece → writing loop → signals → written/kept”.
- The current Home still uses local `resumableLesson()` for Listening continuation even though D-049 established server-side real Continue Learning.
- The existing Listening library endpoint already provides a strong platform-neutral source:
  - lightweight items
  - discovery sections
  - rights/visibility filtering
  - `continue-learning`
  - durable PostgreSQL-backed `resume`
  - artwork/poster metadata
- Stable Home handoffs already exist and must not simply disappear:
  - personalized Writing practice
  - Grammar-practice handoff from latest practice outcome
  - Library due-review handoff
  - Listening habit/goal entry
  - Reading/Speaking/Listening continuation cues
  - cross-skill cue
- Current shell/navigation is older IA and has no true mobile bottom navigation. Shell migration is NOT part of H1 unless required to make the Home body function. Do not create fake Explore/Progress routes in this batch.

## 2. H1 product goal

Create the first actual reusable Orena “LEGO” layer and use it on Home.

H1 is successful when the Home BODY follows:

```text
JourneyHero
→ real Continue Journey when available
→ Explore Worlds
→ For You Today
→ Challenge / useful action
→ Continue Exploring
```

Detailed analytics are removed from Home.

The H1 screen must already adapt deliberately at:

- 1440
- 1024
- 390

The shell may remain the current shell for this batch; the Home body must not depend on desktop-only layout.

## 3. Migration strategy

Do NOT globally restyle every existing Orena screen.

Create an opt-in Orena UI v2 namespace for migrated product surfaces so stable Writing/Grammar/etc. do not visually regress while Home is being proven.

Recommended approach:

```text
Home root: data-orena-ui="v2"
new product component CSS uses a dedicated v2 namespace
existing shell remains intact
```

Do not rewrite the old shared token file in a way that changes every screen.

Use the values in `docs/ORENA_DESIGN_TOKENS.json` for the v2 migrated surface.

## 4. Required reusable product components in H1

Implement only components actually used by Home.

Required semantic components:

```text
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

Use functions/modules rather than duplicating markup in Home.

Suggested files (adapt if the repository architecture strongly prefers another split, but explain why):

```text
static/becoming/orena/product-components.js
static/becoming/orena/product-components.css
static/becoming/domain/home-model.js
```

A product component should receive semantic data, not page-specific HTML fragments.

Example shape:

```js
worldCard({
  id,
  title,
  description,
  artwork,
  progress,
  journeyCount,
  accentFamily,
  variant,
})
```

Do not make one giant `HomeTemplate()` component.

## 5. World data

Do not hardcode visual world cards directly inside `home.js`.

Establish one versioned semantic source for World definitions.

Preferred architecture:

```text
writing_coach/content/orena_worlds.v1.json
writing_coach/world_catalog.py
```

The catalog may contain:

- stable world id
- supported learning languages
- multilingual title/description OR stable localization keys
- topic/tag membership rules
- accent family
- artwork asset key/reference
- editorial order

The first version must derive availability from REAL current catalog content. Do not claim lesson/journey counts that do not exist.

It is acceptable for a language to expose fewer Worlds today because the real catalog is still small.

Do not create fake lessons to fill cards.

## 6. Listening data

Use `api.listeningLibrary(state.language)`.

The new Home must prefer the server's real `continue-learning` + `resume` contract from D-049.

Do not use local `resumableLesson()` as the canonical Listening continuation when server resume exists.

Opening a Listening continuation must preserve:

- lesson id
- selected segment id when valid
- existing lesson-autostart behavior
- server visibility rules

No transcript should be loaded merely to render Home.

## 7. Existing stable learning handoffs

Do not delete existing learner value because the old visual panel is removed.

Re-express stable handoffs inside `For You Today`, `Challenge`, or `Continue Exploring`.

At minimum preserve access to:

### Library due review
If a truthful due item exists:
- render a Recommendation/Challenge entry
- existing handoff to Library/Active Recall still works
- selected learning language remains correct

### Personalized Writing practice
If a backend practice recommendation exists:
- surface it as a recommendation, not as the Home hero
- preserve `nextPractice()` payload/context and Write handoff

### Grammar practice from latest outcome
If a safe latest outcome links to Grammar:
- surface as a recommendation if it is useful
- preserve exact evidence and parent essay lineage
- do not expose malformed outcome values

### Listening habit / goal
Do not make minutes/streak analytics the Home focal point.
A lightweight action such as “Continue your listening goal” may exist in Challenge/For You if based on real state.

### Reading / Speaking continuation
May surface as recommendation candidates using existing real histories.

## 8. Remove from Home

These old Home concepts must not remain as major sections:

- Writing dashboard
- Skill score dashboard
- Writing cycle as the dominant journey
- latest score analytics
- learning-memory analytics cards
- recent drafts as a major lower-page destination
- generic KPI strips
- “Insight of the day” analytics rail
- large streak analytics card

The underlying functions/data may remain elsewhere if used by Progress/Journey/Review, but Home must stop being their dashboard.

Do not delete backend data or persistence.

## 9. Continue Journey selection

Home should choose a continuation with truthful priority.

Recommended initial priority:

1. server-backed Listening Continue Learning if present
2. real local Writing draft if it genuinely has unsaved/in-progress learner work
3. otherwise no continuation card; Home becomes discovery-first

Do not invent 62%, episode numbers, timestamps or a journey.

A progress number appears only when a real contract supplies it.

If Listening progress cannot currently produce a meaningful percentage, show state such as:

```text
Continue where you left off
```

with lesson/segment context, not a fabricated percentage.

## 10. Hero

Hero is emotional, not analytics.

Required:

- contextual greeting may remain
- one strong question/invitation
- artwork-safe region
- one primary CTA
- CTA behavior:
  - Continue if truthful continuation exists
  - otherwise Explore
- no score, CEFR, accuracy, essay count or metric chart

For H1, if approved final Orena illustration assets do not yet exist:
- implement the real artwork container, aspect ratio, responsive crop and semantic asset API
- use a clearly temporary NON-TEXT visual placeholder/gradient only inside development
- do not bake marketing text into an image
- do not generate a random new mascot interpretation

H2 will replace temporary artwork with approved production artwork.

## 11. Responsive behavior

### 1440
Use the wide canvas to show meaningful sections simultaneously.

Target:
- wide hero
- Worlds visible as a strong row/mosaic
- For You + Challenge can share a row
- lower discovery visible without becoming a dashboard

### 1024
- compact hero
- 2–3 column/grid or rail for Worlds
- supporting columns may stack when needed

### 390
Order:

```text
Hero
Continue
World horizontal rail
For You
Challenge
Continue Exploring
```

Do not preserve desktop simultaneous visibility.

No horizontal page overflow.

Touch targets >= 44px.

## 12. EN/ZH

H1 is not complete unless both EN and ZH render.

Requirements:

- no English-length assumptions
- proper CJK font/line height
- no forced condensed Chinese
- world titles/descriptions have EN/ZH parity
- existing learner action handoffs remain language-scoped
- do not mechanically translate pedagogy

Vietnamese UI copy may remain supported where the existing interface supports it, but EN/ZH learning parity is mandatory.

## 13. Loading / partial error / empty states

Replace whole-screen all-or-nothing failure where practical.

Required behavior:

- Home shell and stable sections can render while optional data fails
- Listening catalog failure does not erase a real local Writing continuation
- practice recommendation failure does not blank Worlds
- Library failure does not blank Home
- empty history becomes discovery-first
- no fake metrics or fake progress

## 14. Tests

Do not simply delete old Home tests.

Classify each existing test:

- still-valid learner contract → adapt to new component markup
- behavior moved out of Home by accepted product direction → replace with a test at its new surface or explicitly document why it is no longer a Home contract
- stale visual/dashboard assertion → retire only the assertion, not learner functionality

Specifically inspect:

```text
scripts/test_home_library_review_handoff.mjs
scripts/test_home_personalized_practice_flow.mjs
scripts/test_home_practice_outcome_shape.mjs
scripts/test_r12_listening_habit_home.mjs
```

Add focused tests for:

1. server Continue Learning wins over local Listening resume
2. no fabricated progress
3. World availability/counts come from real content mapping
4. optional section failure does not blank Home
5. EN/ZH Home rendering
6. Home no longer contains Writing dashboard analytics
7. product components receive semantic data
8. 390 composition contract / no desktop-only assumptions where testable

## 15. Do not do in H1

- do not create fake Explore/Progress routes just to satisfy future navigation
- do not redesign all existing screens
- do not rewrite Listening catalog
- do not mutate production DB
- do not apply pending Listening migration
- do not touch or delete `l3_caption_audit.json` or `l3_import_report.json`
- do not start a second Docker runtime
- do not rebuild unless dependencies/image changed
- do not introduce a JS framework or package manager
- do not copy mobile UI code into Web
- do not claim Golden visual completion yet

## 16. Validation

Before coding, report:

```text
COMPOSITION_RECIPE=
REUSED_COMPONENTS=
NEW_COMPONENTS=
REAL_DATA_SOURCES=
1440_COMPOSITION=
1024_COMPOSITION=
390_COMPOSITION=
FILES_EXPECTED_TO_TOUCH=
```

Then implement.

After implementation run relevant contract tests plus:

```powershell
python scripts/validate_project_memory.py
python scripts/validate_architecture.py
node scripts/test_listening_ui.mjs
```

Run all affected Home `.mjs` tests.

If the shared Docker runtime is free, render the real Home at 1440/1024/390. Do not start a second runtime.

H1 completion report must distinguish:

```text
FUNCTIONAL_H1=
EN=
ZH=
1440_RENDER=
1024_RENDER=
390_RENDER=
VISUAL_GOLDEN=NO   # H2 owns final artwork/fidelity
REGRESSIONS=
DEFERRED=
```

## 17. Git

Stay on `claude/integration-v2`.

Do not create another branch.

Do not use `git add -A`.

The two existing L3 untracked files are unrelated and must remain untouched:

```text
l3_caption_audit.json
l3_import_report.json
```

Commit H1 as one coherent batch only after validation.

Suggested message:

```text
feat(ui): build Orena product components and migrate Home discovery
```
