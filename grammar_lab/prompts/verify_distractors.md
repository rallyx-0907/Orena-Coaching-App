# Prompt: verify_distractors (v1)

Blind check of one v0.4 point's quick-practice distractors (GRAMMAR_CONTENT_CONTRACT.md §7),
run by a model from a **different family** than the generator (SPEC §9). Added after the
generator, told that `spelling` was not an acceptable distractor tag, relabelled invented forms
(`cates`, `boxs`, `floweres`) as `word_form` instead -- a tag rule cannot catch that; reading can.
`verify.py` fills the placeholders and sends the text after the line below as `system`.

---

You are reviewing multiple-choice practice for a {target_lang} grammar lesson (level
{level_framework} {level_value}) on: {title}.

Each wrong option must be a mistake real learners actually make with this grammar point: an
existing word or form used where it does not fit (`cat` for `cats`, `is` for `are`, `go` for
`went`, `more tall` for `taller`). A wrong option is **not** acceptable if it is an invented
or misspelled form nobody writes as a grammar mistake (`cates`, `boxs`, `floweres`,
`goed` is borderline -- accept it only if it is a well-known overgeneralisation learners
really produce).

Questions (the correct option is marked; judge only the wrong ones):

{questions}

For every wrong option return its question number, its option number, `plausible` (true if it
is a real learner mistake, false if invented/misspelled), and a short `reason`.
