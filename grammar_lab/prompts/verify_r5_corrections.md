# Prompt: verify_r5_corrections (v1)

Conversion mode (human, 2026-09-28): a point generated from the app's R5 lesson(s) carries the
corrections the generator says it made to R5 (`provenance.r5_source.corrections`). A model from a
**different family** than the generator reads each claim and says whether R5 really was wrong,
so the human learns where R5 itself had errors -- without trusting the generator's own word.
`verify.py` fills the placeholders and sends the text after the separator as the `system`
message. The result is a report for the human, never a flag on the new point.

---

You are reviewing corrections made while rewriting a {target_lang} grammar lesson (level
{level_framework} {level_value}, "{title}") from an older version of the same lesson.

Each numbered item says what the older lesson contained that was wrong, and what was written
instead:

{corrections}

For each item decide whether the older lesson really was wrong as described -- a wrong rule,
an ungrammatical or unnatural example, a "mistake" that is not one, wrong level. Answer
`r5_was_wrong: false` when the claim is a matter of style or preference, or when the older
content was acceptable. Give a short `note` either way. Return one judgement per item, with its
`index`.
