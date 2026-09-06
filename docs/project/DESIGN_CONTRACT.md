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
