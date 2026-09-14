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
| **Interface language** | System chrome: navigation, menus, Settings, system-level labels/actions, account/app management UI | `en`, `zh` (`account_profile.py: interface_language`, `ctx.ui`) |
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

### AUDIT-1 - Compliant: interface layer is correctly isolated

`static/orena/ui/copy.js` is indexed only as `copy[ctx.ui]`
(`static/orena/app.js:112,289`); nothing else reads it. `referenceCopy[ctx.ui]`
follows the same pattern in `collection.js`, `discovery.js`, `reference.js` and
`world.js`. No UI file was found reading `ctx.language` or `ctx.support` to
select chrome copy. Interface language is currently limited to `en`/`zh`
(`account_profile.py:80`, matching `CURRENT_HANDOFF.md`'s P1 note) - a scope
limit, not a coherence violation, since it does not leak into the other two
layers.

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
