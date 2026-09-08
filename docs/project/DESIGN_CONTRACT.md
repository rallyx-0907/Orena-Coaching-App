# Orena Design Contract

## Governance

**Purpose:** preserve the approved Orena experience across responsive web and
native clients. **Authority:** fundamental principles are human-governed.
Agents may document an accepted mapping but may not change the design strategy
to fit an implementation.

**Change when:** an explicit human decision changes durable design direction or
an approved product surface establishes a new shared contract. **Do not store:**
page-specific polish lists, temporary defects, or generic framework guidance.

## Source of truth

```text
APPROVED RESPONSIVE ORENA WEB
→ shared product semantics + Orena UI contracts
→ adaptive native implementation mapping
→ SAME ORENA PRODUCT EXPERIENCE
```

Responsive web is the approved product design source of truth. Web is composed
for the space it has; native is a full native port, not a redesign, simplified
version, WebView shell, or generic Expo/Material/iOS reinterpretation.

For learner-facing UI/native work, read in this order after this contract:

1. `docs/ORENA_PRODUCT_DNA.md`
2. `docs/ORENA_DESIGN_TOKENS.json`
3. `docs/ORENA_COMPONENT_CONTRACT.md`
4. `docs/ORENA_RESPONSIVE_COMPOSITION.md`
5. the relevant `docs/ORENA_*_GOLDEN_SPEC.md` when one exists

For a screen explicitly migrated to the Orena Product UI System, these
`ORENA_*` documents govern its UI/product grammar. Legacy BECOMING visual
documents may remain implementation/history evidence, but they do not override
the migrated Orena screen contract.

## Required parity

Native must preserve, where the web experience exists:

- product meaning, feature access, learner outcomes, information architecture,
  content identity, progress identity, and cross-skill handoffs;
- Orena design tokens, visual DNA, typography hierarchy, surface grammar,
  interaction intent, focus/selection behavior, and semantic component roles;
- loading, empty, degraded, error, retry, offline, and authentication states;
- accessibility, reduced motion, system text sizing, keyboard/safe-area
  behavior, EN/ZH parity, and light/dark parity.

Parity does **not** require the same number of objects to be visible at the same
time. Desktop may show more useful information simultaneously. Tablet/mobile
may change columns, rails, stacking, chrome placement, artwork crop, or reveal
order while preserving access and priority.

Platform mechanics may differ when native APIs require it: permissions, secure
storage, audio/microphone, deep links, system navigation, and equivalent
accessibility controls. Those differences must preserve the same learner
outcome and truthful state.

Golden learner surfaces are reviewed at:

```text
1440px desktop
1024px tablet
390px mobile web
```

The goal is not pixel identity across these widths. The goal is one product
with deliberate composition at each width.

## Home and Progress boundary

- Home is motivation + discovery + continuation.
- Progress is reflection + learning analytics.
- Progress attached to a specific journey may appear on Home when it helps the
  next action.
- Analytics walls, skill radar charts, weekly KPI panels, and equivalent
  reflection surfaces belong to Progress, not Home.

## Product-component rule

Agents do not design learner pages from a blank canvas when an approved Orena
component/recipe exists.

Required reasoning order:

```text
tokens
→ primitives
→ Orena product components
→ approved composition recipe
→ page content
```

Before implementing a migrated screen, the agent must state the composition
recipe, reused product components, any genuinely new component, semantic backend
data, and 1440/1024/390 adaptation.

## Review rule

Native review asks whether the implementation faithfully ports approved Orena
web behavior and meaning—not whether a reviewer prefers a different mobile
design. A native-only flow, reduced feature set, contradictory navigation, or
separate state/domain model is a product-memory regression.

A major migrated learner screen is not visually complete from source inspection.
It must be rendered, compared against its Golden Spec, have the three largest
visual gaps corrected at the highest shared level possible, and be rendered
again.
