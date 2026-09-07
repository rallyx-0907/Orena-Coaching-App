// One contextual explanation system serves reading, listening, writing and
// practice. These assertions hold the parts a capability inherits by using it:
// the vocabulary for naming a problem, and the promise that going deeper never
// costs the learner the thing they were looking at.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  JUDGEMENT_KEYS,
  judgementLabel,
} from '../static/orena/ui/understanding.js';

// The client and the server have to mean the same thing by a judgement, or the
// UI silently drops one the model is allowed to return.
const server = readFileSync('writing_coach/media_interaction.py', 'utf8');
const declared = [
  ...server
    .split('USAGE_JUDGEMENTS = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
assert.deepEqual(
  [...JUDGEMENT_KEYS].sort(),
  [...declared].sort(),
  'the judgement vocabulary must match on both sides of the API',
);

// "Wrong" is not one thing. Every distinction the API can return is a
// distinction the learner can actually read, in both languages.
for (const ui of ['en', 'zh']) {
  for (const judgement of JUDGEMENT_KEYS) {
    const label = judgementLabel(copy[ui], judgement);
    assert.ok(label, `${ui}: no label for judgement "${judgement}"`);
    assert.ok(
      label.length > 2,
      `${ui}: the label for "${judgement}" says nothing useful`,
    );
  }
}
assert.equal(judgementLabel(copy.en, 'not_a_judgement'), '', 'unknown stays silent');

// A judgement label must distinguish, so two different judgements must not
// carry the same words.
for (const ui of ['en', 'zh']) {
  const labels = JUDGEMENT_KEYS.map((k) => judgementLabel(copy[ui], k));
  assert.equal(
    new Set(labels).size,
    labels.length,
    `${ui}: two judgements share a label, which defeats the distinction`,
  );
}

const understanding = readFileSync('static/orena/ui/understanding.js', 'utf8');

// A follow-up is the same call carrying a question; it must send the original
// selection and context, not a fresh lookup of the question alone.
assert.match(
  understanding,
  /text: source,[\s\S]{0,200}context: passage,[\s\S]{0,120}question:/,
  'a follow-up must carry the original selection and its context',
);
// The server refuses a selection its context does not contain; keeping the
// question out of that pair is what makes the refusal meaningful.
assert.match(
  server,
  /if source\.casefold\(\) not in context\.casefold\(\)/,
  'an explanation must stay about something the learner can see',
);

// Nothing may be invented to fill a gap.
assert.match(
  understanding,
  /understandingUnavailable/,
  'an unavailable explanation says so',
);
for (const ui of ['en', 'zh'])
  assert.ok(copy[ui].understandingUnavailable, `${ui}: missing unavailable copy`);
assert.match(
  server,
  /Never cite a source, rule number, dictionary or corpus you were not/,
  'explanations must not manufacture authority',
);

// Every capability opens the one surface rather than growing its own.
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
const expression = readFileSync('static/orena/ui/expression.js', 'utf8');
for (const [name, source] of [
  ['encounter', encounter],
  ['expression', expression],
]) {
  assert.match(
    source,
    /from '\.\/understanding\.js'/,
    `${name}: must investigate language through the shared surface`,
  );
}
assert.doesNotMatch(
  encounter,
  /sheet\.querySelector\('#phraseForm'\)/,
  'the bespoke inspect sheet is retired, not living alongside the shared one',
);

/* A judgement sits on its own tinted surface and carries the ink paired with
   it. The sheet's ambient prose rule scores higher than a bare component
   class, so without an explicit exclusion it paints the pill --muted against
   that surface - 4.35:1 in dark, below AA, in every capability that opens this
   surface. Specificity is not observable from a stylesheet's text, so this
   asserts the exclusion that keeps the pairing intact. */
const world = readFileSync('static/orena/world.css', 'utf8');
assert.ok(
  world.includes('.sheet p:not(.notice):not(.judgement)'),
  'the sheet prose colour must not outrank a panel that carries its own ink',
);

console.log(
  'Contextual understanding: shared judgement vocabulary EN/ZH, context-preserving follow-ups, and no invented authority PASS',
);
