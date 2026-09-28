# Prompt: verify_formula (v2)

Blind check of one v0.4 point's formula coverage (GRAMMAR_CONTENT_CONTRACT.md §2), run by a
model from a **different family** than the one that generated the point (SPEC §9) -- the same
reason blind-solve uses a second model. `verify.py` fills the placeholders and sends the result
as the `system` message. Written after reading the first v0.4 output (and the human's review of it) found formulas
that dropped a form the title names (articles without `the`, there is/are with only `is`,
much/many with only `many`) -- validate cannot see that; only reading the title can.
v2: v1 reported concept names ("Plural nouns", "experience") as missing forms on the first
live run -- a form is now a concrete word or ending, never the point's name.

---

You are checking a grammar card for a {target_lang} lesson, level {level_framework} {level_value}.

Title: {title}
Summary: {summary}

The card's formula (slots in order; a slot written as `name (a | b)` can take any of the
listed forms):

{formula}

Question: does the formula cover **every concrete word form the title or summary lists
as part of this pattern**? A "form" here is an actual word or ending a learner would write --
`is`, `are`, `much`, `many`, `a`, `an`, `-s`, `-es`, `have`, `has`. For example, a title
"There is / There are" needs both `is` and `are` in the formula; a title "much / many" needs
both `much` and `many`.

Not forms, so never report them as missing: the name of the grammar point or concept
("Plural nouns", "Present perfect", "experience", "countable / uncountable"), a category
label, or the language's name. A formula slot that names a category (`N`, `V3`, `be`) covers
every word of that category unless the title singles out specific words.

Answer `covers_all_forms: true` if no listed word form is missing. Otherwise answer `false`
and list each missing word form in `missing_forms`, exactly as the title writes it.
