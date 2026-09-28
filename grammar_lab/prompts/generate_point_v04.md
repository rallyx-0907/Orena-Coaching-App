# Prompt: generate_point_v04 (v1)

Versioned prompt for generating the six fixed content blocks of one grammar point under
schema v0.4 (GRAMMAR_CONTENT_CONTRACT.md), replacing `generate_point.md`'s free-form
`blocks` for points on this schema version. `generate.py` fills the placeholders below and
sends the result as the `system` message; the point's own data goes in the `user` message.
The LLM never sees this file's placeholder syntax.

---

You are writing one grammar lesson for Orena, a language-learning app. Output one JSON
object matching the schema you were given via structured output — do not add commentary
outside it.

## Point being written

- id: `{point_id}`, target language: {target_lang}, level: {level_framework} {level_value}
- function: {function_title} ({function_id})
- explanation locales (write every field in ALL of these): {locales}
- learner L1s this point must cover mistakes for: {l1s}
- compare required: one entry for each of: {contrast_with_ids}
- error tags required: one `common_mistakes` entry for each of: {error_tags} (the writing
  evaluator's own error labels — use each exactly once, as the `error_tag` value)

## What to write

1. **when_to_use**: 2-4 short, concrete conditions for using this grammar point — not a
   restatement of the summary, situations a learner can recognise.
2. **pattern**: the formula broken into ordered `parts`, each with a `role` (for the app
   to colour consistently with `examples[].spans[].role`). Pick `illustration_kind`:
   `timeline` if the point is fundamentally about *when* something happens relative to
   now (then also fill `timeline_shape` from the closed list you were given); `word_order`
   if the point is fundamentally about the *order* of a fixed sequence of parts (the app
   draws `parts` itself — you do not need to repeat that ordering anywhere else);
   `none` if neither applies. Fill `timeline_shape` with any value even when
   `illustration_kind` is not `timeline` — the field is required by the schema, but the
   app ignores it unless the kind is `timeline`.
3. **examples**: exactly {num_examples} clean, grammatically correct sentences in
   {target_lang} that use this point naturally. For each, `spans` marks the exact
   character range(s) in `text` that demonstrate the point — `start`/`end` are 0-based
   character offsets (`end` exclusive), not a repeated substring. `annotation` is a short
   note on what that span does (e.g. "started in the past, still true now"), and
   `translation` is the natural {locales} translation.
4. **compare**: one entry per id listed above under "compare required" (only that many —
   omit entirely if none are required). `this_meaning`/`this_example` describe this point;
   `other_meaning`/`other_example` describe the point named in `with`, contrasting the two
   so a learner sees exactly where they diverge.
5. **common_mistakes**: one entry per error tag listed above. `wrong` must be a mistake
   this L1 speaker actually makes for this grammar point (not a random typo), and `right`
   must be the same sentence with only the grammar point's own error fixed. `reason`
   explains the actual mechanism that makes `wrong` wrong, not just "this is incorrect."
6. **quick_practice**: exactly 3 cloze questions (`q` contains `___`), each with 2-4
   `options` and exactly one that is correct at `answer` (0-based index) — genuinely one
   correct answer, not two options that could both be defended.

## Rules

1. **Never copy source text** from any catalogue (English Grammar Profile, HSK 3.0,
   JLPT) — write original examples and explanations.
2. **Vocabulary stays inside the point's level** ({level_value}).
3. **Examples must be clean.** Every sentence in `examples`, `compare`, and the `right`
   side of `common_mistakes` must be grammatically correct target-language text with no
   other errors — the verify step re-checks this against the writing evaluator.
4. **Every locale map needs every declared locale**, independently written, never a
   machine-translated near-duplicate of another locale's text.

Write for a self-taught adult learner who has never had a classroom explanation of this
point. Prefer a plain sentence over a linguistic term where both would be understood.
