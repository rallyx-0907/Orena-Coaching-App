> **Historical/supporting implementation contract**
>
> This document contains useful learner-first implementation constraints from an
> earlier Orena presentation system.
>
> It is not the authoritative Orena product model.
>
> Current product direction is defined by:
>
> `docs/product/ORENA_PRODUCT_CONSTITUTION.md`
>
> Use this document only where its implementation guidance remains compatible
> with the current Constitution.

# BECOMING — Future Screen UI Contract

This contract is enforced in code by:

```text
static/becoming/domain/screen-contract.js
scripts/becoming_release_gate.py
```

For every new learner-facing route, declare:

```text
learnerGoal
dominantIdea
primaryAction
progressiveDisclosure
evidence
```

A new route must not pass release merely because it renders and compiles.

Before a future module is considered complete:

1. The route exists in the router.
2. The route exists in `SCREEN_CONTRACT`.
3. The screen uses the shared interface i18n layer.
4. User-triggered asynchronous work uses the shared busy/loading primitives.
5. English and Chinese learning mechanics are reviewed separately.
6. Desktop and mobile preserve the same learner goal.
7. The primary evidence comes from learner work/data, not decorative AI output.
8. Existing design tokens/components are reused before new visual primitives are created.
9. Any new motivational system must derive from learning evidence rather than XP/streak/activity.
10. The permanent BECOMING release gate passes.

North-star check:

```text
Learner is the protagonist.
Work is the evidence.
AI is the guide.

Bold in meaning.
Calm in presentation.
Human in guidance.
```
