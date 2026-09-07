# Extending the Orena web foundation

Status: DESCRIPTIVE. This records what the Golden Star foundation already
provides so a new surface inherits it instead of re-inventing it. It sets no
product direction; that lives in `ORENA_PRODUCT_CONSTITUTION.md` and
`ORENA_CONTENT_ARCHITECTURE.md`.

If a change here would contradict either of those, the Constitution wins and
this file is what needs updating.

---

## 1. Where a new surface goes

`static/orena` is layered, and the layers only ever depend downward:

```
ui/          what a learner sees          world, encounter, expression
             shared pieces                patterns, content, brand, html
product/     what Orena means             intent, memory, encounter, evidence
capabilities/what the client can do       media player, recorder, dictation,
                                          transcript, speech, grammar
infrastructure/  how it reaches the server  api
```

A `ui/` module may import from `product/` and `capabilities/`. Nothing below
`ui/` may import from `ui/` — except `ui/html.js`, which is escaping and DOM
plumbing rather than presentation.

New routes are added in `product/intent.js` (`route`, `link`) and dispatched in
`app.js`. Nowhere else parses the hash.

---

## 2. Reach for these before writing markup

From `ui/patterns.js`:

| Primitive | Use it for |
|---|---|
| `pageIntro({title, note, eyebrow})` | Every page heading. |
| `intentNavigation(c, current)` | The Practice intention row. |
| `continuationShelf(ctx, limit)` | "Pick up a thread" on any surface that can send a learner onward. |
| `responseComposer(ctx, {id, prompt})` + `bindComposer` | Writing that grows out of something. Never submits a practice attempt. |
| `draftStatus(ctx)` | Whether the draft is on the device. |
| `progressReporter(element, ctx, alive)` | Anything that leaves the device. |
| `savedLanguageLink(c)` | The hand-off from keeping language to meeting it again. |

From `ui/content.js`: `duration`, `origin`, `art`, `audioIdentity`,
`bindImages`. From `ui/brand.js`: `companionArt`. From `ui/html.js`: `esc`,
`safeExternal`, `dialog`, `focusRegion`, `status`.

`progressReporter` is the one to reach for by reflex. It speaks in a single
voice, refuses to write onto a view the learner has left, and any retry it
renders is wired before it returns:

```js
const report = progressReporter(statusNode, ctx, alive);
const save = async () => {
  report.saving();
  try {
    await ctx.mutate(() => api.something(payload));
    report.saved(savedLanguageLink(c));   // omit the argument if there is no next step
  } catch {
    report.failed(c.failedSave, save);    // the retry is already bound
  }
};
```

---

## 3. Colour: a panel carries its own ink

Never paint a surface with a bare accent token. Each tinted panel ships with the
ink that belongs on it, in both themes:

```
--sage-surface   --on-sage   --on-sage-muted
--coral-surface  --on-coral  --on-coral-muted
--night-surface  --on-night  --on-night-muted  --on-night-line
--sun-surface    --on-sun
```

`--sage`, `--coral`, `--sun` remain for strokes and accents on a surface that
already sets its ink. `scripts/test_orena_foundation.mjs` computes every pairing
and rejects `background: var(--sage)` and friends, so this is enforced rather
than remembered.

Type and spacing come from `--text-*` and `--space-*` in `foundation.css`. The
same test rejects a hardcoded font-size below the readable scale.

---

## 4. Truthfulness is a rendering rule

The product has one non-negotiable habit: never show a number, a meaning, a
score or an availability the system does not actually have.

- A provider that returns demonstration values is labelled
  (`score_kind === 'synthetic_demo'`, `evaluator === 'fallback-demo'`).
- A missing score reads as `c.notMeasured`, not `0` or `?`.
- An empty result says it found nothing rather than rendering an empty shell.
- Imported media with no known length shows no length, not `0:00`.
- A save whose prior state could not be read merges rather than overwrites
  (`product/evidence.js`, `mergeListeningEvidence`).

When adding a capability, decide what its unavailable state says before
designing its successful one.

---

## 5. Learner memory and the threads between archetypes

`product/memory.js` is owner- and language-scoped device memory: imports, media
imports, kept content, continuation, drafts, dictation answers. Practice
evidence stays on the server through the capability APIs.

Call `memory.enter({id, title, segment, intent, excerpt})` whenever a learner
touches something. That single call is what makes the continuation shelf, the
"Continue" thread and the return route work — the archetypes are connected by
this record, not by bespoke links between screens.

`product/intent.js` decides where a thread resumes: `continuationLink(item)` for
unfinished work, `sourceLink(id)` for the way back to where it started.

---

## 6. Before calling a surface done

1. `node scripts/test_orena_foundation.mjs` and `node scripts/test_orena_product.mjs`.
2. `node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs`.
3. Open it at 1440, 800 and 390 in light and dark, in English and Chinese.
4. Check what it says when the network fails, not only when it succeeds.
5. Confirm no text falls below its contrast threshold and no pointer target is
   under 24px (44px below 480px).

The browser pass is not optional: every defect fixed in this foundation was
found by looking at the running product, not by reading the code.
