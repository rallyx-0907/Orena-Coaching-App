# Orena language coherence

Status: AUTHORITATIVE. This document states a durable human product decision
and records the current implementation's conformance to it. It does not own
account/schema architecture (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md`), content
domains (`ORENA_CONTENT_ARCHITECTURE.md`) or evidence (`ORENA_EVIDENCE_ARCHITECTURE.md`)
- read those for how a given surface stores or scores what it produces. This
document owns only which of the three language layers below a piece of text
belongs to, and the rule that they never collapse into each other.

## 1. The three layers

Every learner-facing string in Orena belongs to exactly one of three
independent layers. None may be inferred from another.

| Layer | What it governs | Example values today |
| --- | --- | --- |
| **Interface language** | System chrome: navigation, menus, Settings, system-level labels/actions, account/app management UI | `en`, `zh`, `vi` (`account_profile.py: interface_language`, held on the device; `ctx.ui` via `product/languages.js`) |
| **Support/native language** | Explanation, annotation, instruction, hint, guidance, grammar/vocabulary explanation - the learner's chosen support language | 12 languages: `en`, `vi`, `zh`, `ja`, `ko`, `es`, `fr`, `de`, `pt`, `ru`, `id`, `th` (`writing_coach/core/support_languages.py`, `ctx.support`) |
| **Target learning language** | Reading content, vocabulary target word/expression, exercises, examples - the language being learned | `en`, `zh` (`ctx.language`, `writing_coach/languages/{english,chinese}`) |

Worked example: interface = English, support = Vietnamese, target = Chinese ->
menus render in English, explanations render in Vietnamese, reading/vocabulary/
exercises render in Chinese. Changing any one of the three must never change
either of the other two. There is no dependency, default-cascade or inference
between them - each is its own stored preference, resolved independently.

`writing_coach/core/support_languages.py` already states the technical form of
this rule in comment form ("LEARNING_LANGUAGE, SUPPORT_LANGUAGE and UI_LOCALE
are three distinct concepts"); this document is the durable, product-level
version of that same rule, and the one future capabilities are reviewed
against.

## 2. Terminology note: `target_language` is an overloaded name

Media translation and understanding code (`writing_coach/media_translation.py`,
`writing_coach/media_meaning.py`, `static/orena/ui/spoken-coaching.js`,
`static/orena/ui/understanding.js`) calls its translation-destination parameter
`target_language`. In that call, `target_language` resolves to the learner's
**support** language (the language a passage is translated *into* for the
learner), and `source_language` is the **target learning** language (the
language being translated *from*). This is internally consistent within those
modules and is not a functional defect, but it is the opposite of this
document's "target learning language" layer. Do not read a `target_language`
identifier in code as evidence of which product layer it serves - check what
it is assigned from (`ctx.support` vs `ctx.language`) instead of what it is
named.

## 3. Invariants

- A surface that renders chrome (nav labels, buttons, Settings, account
  management) reads only the interface language. It must never read the
  support or target language to decide what script or wording to render.
- A surface that explains, annotates, defines, translates or coaches reads
  only the support language the learner has chosen, with a documented fallback
  order when a translation does not exist for that language (see `AUDIT-2`
  below for the current, incomplete state of that fallback).
- A surface that presents content to be read, heard, written or spoken - the
  material being learned itself - reads only the target learning language.
- Expanding the set of available interface languages, support languages or
  target learning languages are three independent product decisions. Adding
  one must never be treated as adding, or implying parity for, either of the
  others.
- No capability may hardcode a specific support language (e.g. Vietnamese) as
  the explanation language. `support_languages.py` names the full capability
  boundary; a capability that does not yet honor a learner's chosen support
  language is a known gap to close, not a second, competing default.

## 4. Audit of current surfaces (2026-09-14)

Scope: `static/orena/ui/*.js`, `static/orena/product/*.js`,
`writing_coach/languages/*`, and the interface-locale handling summarized in
`CURRENT_HANDOFF.md`'s "Language coherence" P1 entry. This audit does not
change behavior; it records what the entry above only summarized, so the gap
is traceable to file and line rather than to a paragraph.

### AUDIT-1 - Was not compliant; fixed 2026-09-24 (D-079)

The 2026-09-14 reading of this entry ("interface layer is correctly isolated")
was wrong. `copy[ctx.ui]` was indexed correctly, but `ctx.ui` itself was
*derived from the support language*: `static/orena/app.js` set
`ctx.ui = uiLocale(ctx.support)` at profile load and in the preferences sheet,
and booted from a device cache of the support language (`orena.support`). The
interface layer therefore never existed on its own. Its visible failure: a page
booted with one support language while the account's support language had
changed elsewhere showed chrome, guidance and generated text in three languages
on one screen (found in the Speaking word sheet).

The source of truth is now `static/orena/product/languages.js`:

- interface - the learner's choice, kept on the device under `orena.interface`
  (the account setting `interface_language` is declared but not stored: its
  column is a gated migration), else the browser's language when Orena is
  written in it, else English; `en`, `zh`, `vi`;
- support - the account's `support_language`, else `native_language`;
- target - the learning language the server reports active.

`app.js` assigns each `ctx` layer only through its resolver; the preferences
sheet offers the interface language as its own choice; the old `orena.support`
cache is neither read nor written. `scripts/test_orena_language_layers.mjs`
locks it (acceptance cases A, B and C; every combination; reload; stale cache;
no chrome picked by support or target).

### AUDIT-1b - Closed 2026-09-24 (D-080): every copy string is read by its declared layer

Until D-079 the interface language equalled the support language, so static
hints and explanations read correctly by coincidence. With the layers apart,
each string must come from the pack of its own layer. It now does, app-wide:

- Every key of every learner copy table - the product copy (`ctx.c`), the shell
  and shared screens (`referenceCopy`), Speaking - is declared `interface`,
  `support` or `target` in `static/orena/ui/copy-layers.js` (1,572 keys, 315
  support). There is no default layer.
- `static/orena/ui/layered-copy.js` builds the copy a screen reads: interface
  keys from the interface pack, support keys from the support language's pack,
  else English (the fallback) - never the interface language instead. `ctx.c`,
  `refCopy(ctx)` and `speakCopy(ui, support)` are all built by it; no surface
  indexes a copy table directly.
- Content explanations follow the same rule: grammar pattern names, grammar
  notes and contrast explanations read the support language with an English
  fallback (they used to fall back to the interface language); prepared
  meanings already did.
- `scripts/test_orena_copy_layers.mjs` fails on an undeclared key, a stale
  declaration, a declaration against the plain rule without a recorded reason
  (an explanation declared interface, a button declared support), a guidance-
  named key declared interface, a key read from the wrong pack (all keys, cases
  A/B/C), direct indexing of a copy table, and content picked by, or falling back
  to, the interface language.

Still true and deliberate: date and time formats follow the interface language
(metadata), and a language is named in its own language where one is chosen
or shown as a pair (endonyms).

### AUDIT-2 - Gap: Writing evaluator hardcodes the support language to Vietnamese

`writing_coach/languages/english/profile.py:63` and
`writing_coach/languages/chinese/profile.py:74` instruct the evaluator model
directly: "All explanations, summaries, strengths, priorities and mini-rules
MUST be written in Vietnamese" / "must be primarily in Vietnamese". Neither
profile's `SYSTEM_PROMPT` reads `ctx.support` or
`writing_coach/core/support_languages.py` at all. A learner whose stored
support language is, say, Spanish or Japanese still receives Vietnamese
writing feedback. This is the mechanism behind `CURRENT_HANDOFF.md`'s P1 note
("evaluator ... explanations follow the support language (12; sandbox profile
vi)") - it currently reads correctly only because the sandbox's one exercised
profile happens to be `vi`, not because the evaluator is support-language
aware.

The evaluator's JSON contract also names its own fields for that one language:
`summary_vi`, `strengths_vi`, `priorities_vi`, `explanation_vi`,
`mini_rule_vi` (`writing_coach/writing_evaluator_contract.py:26-38,222-261`,
consumed the same way in `writing_coach/writing_evaluation.py:79-282`). The
field names encode an assumption, not just a historical label.

### AUDIT-3 - Gap: Grammar lesson generation hardcodes the same assumption

`writing_coach/languages/runtime.py:112-128` (`grammar_lesson_prompts`) builds
its system prompt as "You create ... grammar lessons for Vietnamese learners
... Explain in Vietnamese" for both the English and Chinese course, and its
user prompt is labelled `VIETNAMESE-LEARNER TRAPS` (line 142) sourced from
`lesson['objective_vi']` (line 136). `writing_coach/grammar_catalog.py:9,62`
and `writing_coach/grammar_knowledge.py:67,79-80` require and store
`objective_vi`, `summary_vi`, `explanation_vi`, `production_task_vi`,
`writing_tip_vi` as the only explanation fields - there is no per-support-
language variant. `active_grammar_provider()` is selected by target learning
language (`current_language_code()`) only; nothing in this path reads
`ctx.support` or a learner's `support_language`.

`static/orena/ui/expression.js:539,550` (grammar pattern detail) reads
`note?.title[ctx.ui]` for the heading and
`contrast.why[ctx.support] || contrast.why[ctx.ui] || contrast.why.en` for the
explanation - a fallback chain that already prefers `ctx.support`, but has
nothing to fall back *to* beyond `en`/`ui` because the data these read from
(`grammar-shelf.js` notes) is only ever populated in Vietnamese upstream. The
UI-side fallback is correctly designed; the data source behind it is not yet
support-language aware.

### AUDIT-4 - Compliant model to converge on: Media translation and understanding

`writing_coach/media_translation.py` and `writing_coach/media_meaning.py`
resolve their destination language through
`writing_coach.core.support_languages.normalize_support_language` /
`resolve_support_language`, which validates against the full 12-language
roster and falls through profile -> explicit request -> configured neutral
default (`support_languages.py:103-118`) rather than a hardcoded value.
`static/orena/ui/spoken-coaching.js:66-67` and
`static/orena/ui/understanding.js:165-166` pass `source_language: language,
target_language: support` - i.e., translate out of the target learning
language, into whatever the learner's actual support language is. This is the
reference implementation the writing evaluator and grammar generation
(AUDIT-2, AUDIT-3) should be brought in line with.

### AUDIT-5 - Compliant: target learning language scoping

`static/orena/product/memory.js` (`learnerMemory`) scopes its entire storage
key and every collection inside it (`imports`, `mediaImports`, `keptLanguage`,
`conversations`) by `language` (the target learning language), and filters out
records whose stored `language` does not match on read
(`memory.js:32,61,78`). No file under `static/orena/product/*.js` was found
reading `ctx.ui` or `ctx.support` to decide which content set a learner sees.

### AUDIT-6 - Observation: date/time formatting follows the interface language

`static/orena/ui/voice-response.js:86` calls
`new Date(x.created_at).toLocaleString(ctx.ui)`. Treating timestamp formatting
as system chrome (interface layer) is consistent with this document's model;
noted here only so a future audit does not mistake it for a target/support
mix-up.

## 5. What this audit does not do

This document records the gap; it does not close it. Closing AUDIT-2 and
AUDIT-3 (making the writing evaluator and grammar generation honor a learner's
actual `support_language`, per the AUDIT-4 pattern) is implementation work
against an existing tracked P1 (`CURRENT_HANDOFF.md`, "Language coherence")
and is out of this document's scope.
