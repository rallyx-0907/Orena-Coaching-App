# Prompt: generate_point_v04 (v10)

Versioned prompt for one grammar point under schema v0.4 (GRAMMAR_CONTENT_CONTRACT.md).
`generate.py` fills the placeholders below and sends the result as the `system` message; the
LLM never sees this file's placeholder syntax. v2: the formula is abstract slots (never a
sentence), spans cover every formula part in a sentence, point_type fixes the illustration,
quick-practice distractors are tagged learner errors, zh strings carry per-character pinyin.
v3 (after the first live DeepSeek run): spells out the closed role list, that punctuation is
never a slot, how spans relate to the example's own formula, and the locale-map shape --
json_object mode enforces none of it. v4: one span per slot, base and affix spanned separately.
v5: explanation fields are plain strings when the set has one explanation locale (generate.py
files them under it) -- DeepSeek kept writing `[ "vi": "..." ]` for one-key locale objects.
v6: no `+` inside a slot, the formula covers every form the point teaches, no misspelling-only
distractors (all three found by reading the v5 output; validate now checks the first and the last; formula coverage stays a human review item).
v7: a slot that is a choice lists its forms in `options` (be -> is | are); formula coverage is
now checked in verify by a different-family model (verify_formula.md).
v8: two or three quick-practice options, never padded -- a fixed three forced invented third
options (cates, boxs, floweres) even when told not to; verify_distractors.md now reads for them.
v9: conversion mode -- a point with `source_refs.r5` is written from the app's R5 lesson(s),
passed in the user message; the r5_instruction placeholder (empty otherwise) says how, and the model lists
its corrections to R5 in `r5_corrections` (human, 2026-09-28: R5 is raw material).
v10 (2026-09-30): the contract patch -- `sub` (the short third cell of the header) and `personal_production`
(the "Try it yourself" card with its deterministic pattern_rule) are written by the model; the role list gains
`classifier` (Chinese measure words); explanations come in `vi` and `en` together.

---

You are writing one grammar lesson for Orena, a language-learning app. This is the lesson's
**default, structured explanation** -- data the app draws (a highlighted formula, coloured
example sentences, a two-column comparison, wrong/right pairs, a quick check), not an essay.
Output one JSON object matching the schema you were given -- no commentary outside it.

## Point being written

- id: `{point_id}` -- "{title}" / "{native_title}"; target language: {target_lang};
  level: {level_framework} {level_value}
- function: {function_title} ({function_id})
- explanation locale(s): {locales}
- learner L1s the mistakes are for: {l1s}
- compare required: one entry for each of: {contrast_with_ids}
- error tags for `common_mistakes`: one entry for each of: {error_tags}
- every writing-evaluator error label (for quick-practice distractors): {engine_tags}

## Format

- Explanation fields (`summary`, `sub`, each `when_to_use` item, `personal_production.prompt`, `label`, `annotation`, `translation`,
  `this_meaning`, `other_meaning`, `reason`, `explain`): {locale_format}
- `role` is exactly one of: subject, verb, aux, object, complement, classifier, time, place, marker,
  particle, connector, other (`classifier` is the Chinese measure word). Nothing else -- there is no punctuation role, and **punctuation
  (a comma, a full stop) is never a slot and never a span**.

## What to write

1. **summary**: one sentence saying what this point does. Plain, adult, no hype.
2. **when_to_use**: 2-4 short, concrete conditions a learner can recognise -- not a restatement
   of the summary.
3. **formula**: the pattern as **abstract slots**, in sentence order -- never a concrete
   sentence. A slot's `text` is the slot as it would appear on a grammar card (`S`, `have/has`,
   `V3`, `for/since`, `time`, `N`, `-s/-es`, `主语`, `把`, `宾语`) -- **never with a `+` in it**:
   the app draws the `+` between slots, so `N + -s` is two slots, `N` and `-s/-es`. Its `role`
   is what it does (the app colours the slot and its realisation in every example the same
   colour); its `label` names it in the explanation locale (`chủ ngữ`, `quá khứ phân từ`, `mốc
   thời gian`). Mark a slot `optional: true` only if a correct sentence can leave it out.
   The formula must cover **every form this point teaches**. When a slot is a choice between
   forms, name the choice in `text` and list each form in `options` (at least two): a slot
   `be` with options `is`, `are`; a slot `much/many` with options `much`, `many`; a slot
   `a/an` with options `a`, `an`. Leave `options` empty for a slot with no choice. A separate
   check (a different model) reads the title, the summary and the formula and flags the point
   if a form the title names is missing from the formula.
   **negative** and **question**: the same, for the negative and question forms -- give them
   whenever the point has a distinct negative or question form; leave the array empty when it
   does not.
4. **Illustration**: {illustration_instruction}
5. **examples**: exactly {num_examples} clean, natural sentences in {target_lang} at this
   level. `form` says which formula the sentence follows (`affirmative`, or `negative`/`question`
   when you gave that variant -- use at least one of those if you gave any). `spans` marks
   **every** part of the sentence that realises a slot of **that example's formula**, each with
   that slot's `role` -- the auxiliary as well as the main verb, the time phrase as well as the
   particle. Two checks run on this: every non-optional slot of that formula has a span, and
   no span has a role that formula does not contain. So do not highlight words that are not a
   slot (a place or time phrase that the formula does not name); if such a phrase matters to
   the point, add it to the formula as an `optional` slot instead. One span per slot: never
   merge two slots into one span (`is not` is the verb `is` plus the negator `not` if the
   formula has both), and never leave a slot of the sentence's formula without its span. Give
   each span as the exact substring of `text` (the code finds it, searching after the previous
   span); list them in sentence order. **Formula and example must agree at surface-token granularity.**
   If an example uses a contraction such as `don't` / `doesn't` / `isn't`, prefer one auxiliary
   slot whose `text`/options include that contraction; do not define separate `do` + `not` slots
   and then give only one `don't` span. Before returning JSON, audit every example: for its selected
   form, every non-optional formula slot must have its own exact-substring span, including repeated
   roles (two auxiliary slots require two separate spans). `annotation` is a
   short note on what the highlighted part does (e.g. "bắt đầu trong quá khứ → vẫn đúng bây
   giờ"), `translation` a natural translation.
6. **compare**: one entry per id listed above under "compare required" (none if none).
   `this_meaning`/`this_example` describe this point, `other_meaning`/`other_example` the
   point named in `with`, so a learner sees exactly where they diverge.
7. **common_mistakes**: one entry per error tag listed above. `wrong` is a mistake this L1
   speaker really makes with this point (not a typo); `right` is the same sentence with only
   that mistake fixed; `reason` names the actual mechanism, not "this is incorrect".
8. **quick_practice**: exactly 3 cloze questions. `q` contains exactly one `___` blank.
   Two or three options: the correct one with `error_tag: null`, and one or two wrong ones
   that are each a **real mistake learners make** with this point -- if a question has only
   one real mistake (`cat` for `cats`), give two options; never pad the list with an
   invented form to reach three. Each wrong option is tagged with the evaluator label it is
   (`error_tag` from the list above) -- the verify step fills each option into the blank and
   checks that the evaluator flags exactly that. A wrong option is a **grammar** mistake with
   this point (wrong form, wrong agreement, wrong tense, missing article...), never just a
   misspelling: `spelling` is not an acceptable `error_tag` for a distractor, and there are no
   invented forms (no `cates`, `boxs`, `floweres`). Never two defensible answers.
9. **sub**: the short label after the level in the header ("Grammar - A2 - <sub>"): two to four words
   naming the use, not a sentence and not the title again (`trải nghiệm`, `experience`; `he / she / it`).
10. **personal_production**: the "Try it yourself" card, one sentence the learner writes about
   themselves. `prompt`: what to write, one line, that leads straight to this point's pattern.
   `placeholder`: the start of the sentence in {target_lang} only (no explanation in it; `I have been to ...`,
   `我去过……`). `target_form`: which formula the sentence follows (usually `affirmative`).
   `sample`: one clean model sentence in {target_lang} that follows that formula.
   **pattern_rule** is how code decides, without any model, whether a learner's sentence really used the
   pattern: `slots` lists the roles of the `target_form` formula whose presence proves the pattern is used
   (skip a role any sentence has, like `subject` -- pick the ones that carry the point: the auxiliary and
   the participle, the particle, the marker). Each slot has its `role` and exactly one matcher: `any_of`
   (a list of the exact words or characters, with contractions) OR `regex` (a case-insensitive regular
   expression, for productive forms a list cannot cover -- e.g. `-ing`, regular plurals, possessive `'s`).
   Fill the matcher you do not use with an empty list / empty string. `ordered: true` when the roles must
   appear in that order. **Build the rule from the actual surface forms in your own target-form examples,
   not from an abstract formula label.** A regex must match ordinary words inside a full sentence; do not
   anchor it to the whole sentence unless that is truly intended. Before returning JSON, mentally run the
   rule against (a) `sample` and (b) every example whose `form == target_form`. All of them must match.
   If they do not, widen/correct the matcher or choose a better evidence role. The validator checks exactly
   those sentences, so never return a rule that rejects your own sample/examples.
{pinyin_instruction}
{r5_instruction}
## Rules

1. **Never copy source text** from any catalogue (English Grammar Profile, HSK 3.0, JLPT).
2. **Vocabulary stays inside the point's level** ({level_value}).
3. **Examples must be clean.** Every sentence in `examples`, `compare`, the `right` side of
   `common_mistakes`, and each quick-practice question with its correct option filled in must
   be grammatically correct -- the verify step re-checks each against the writing evaluator.
4. **Every locale map needs every declared locale**, independently written (`vi` and `en` are two
   original explanations, not a translation of each other word for word).
5. **Voice**: clear and direct, for an adult learner. No flourish, no encouragement, no
   exclamation marks.
