# Prompt: verify_story (v1)

Three blind-judgment checks for one story block (STORY_SPEC.md §6), all run by a model from a
**different family** than the one that generated the story -- the same reason blind-solve for
`check` items uses a second model (SPEC §9). `verify.py` reads the section named by the check
it is running and fills the placeholders; each section is a complete, standalone system prompt.

## meaning_match

A story alternative sentence turned out to be grammatically correct, so it must mean something
different from the story's main sentence -- that difference is the point. Read it the way the
character in the scene would, with no more context than they have.

Scene: {scene}

Sentence: {sentence}

What do you understand this sentence to imply, on its own, in this scene? State it plainly.
Then say whether your reading matches this stated consequence:

Declared consequence: {consequence}

## no_historical_claim

Read this story about a grammar point. Does any part of it make a claim about the historical
origin or etymology of a word, a grammatical form, or an expression (for example: where a word
came from, an older meaning it used to have, which language it was borrowed from, when a
structure came into use)? A claim can be right or wrong -- either way, it does not belong here;
this is a scene about a learner today, not a history lesson.

Story text:

{story_text}

## rubric

Rate this story block for a language lesson against three criteria, each 0.0 (fails) to 1.0
(excellent):

- `vivid`: can a reader picture the scene and the characters concretely, or is it generic and
  forgettable?
- `correct_when_to_use`: after reading it, would a learner know when to use this grammar point
  and when the alternatives fail -- is the contrast actually clear?
- `concise`: does every sentence earn its place, or does it pad, repeat itself, or over-explain?

Story text:

{story_text}
