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

/* --- A late answer cannot land against a newer question ---

   The selection and its passage are fixed when the panel opens, so those cannot
   drift. The question can: asking "why this way" and then "when would I use it"
   puts two requests in flight, and without a guard whichever returns last owns
   the panel - which may be the answer to the question the learner already moved
   past. Each ask takes a ticket; only the newest may paint.

   This is the Package A boundary rule at a real consumer: a source focus is
   captured before the request, and a late response is dropped rather than
   applied to whatever happens to be current when it arrives. */
assert.match(
  understanding,
  /let asking = 0;/,
  'the panel must know which question it is waiting for',
);
assert.match(
  understanding,
  /const ticket = \+\+asking;/,
  'every ask takes a ticket',
);
assert.match(
  understanding,
  /const current = \(\) => alive\(\) && ticket === asking;/,
  'a paint is allowed only while its ticket is still the newest',
);
/* One gate covers both outcomes because the request no longer forks into a
   success path and a catch: it resolves to an outcome first, and the single
   ticket check guards whatever that outcome turns out to be. A late failure
   therefore cannot wipe a newer answer either. */
assert.equal(
  (understanding.match(/if \(!current\(\)\) return;/g) || []).length,
  1,
  'the ticket is checked once, after the outcome resolves',
);
assert.ok(
  !/if \(!alive\(\)\) return;\s*if \(!result\.available/.test(understanding),
  'the result path must not fall back to the bare liveness check',
);

/* --- Nothing coming and nothing arrived are different news ---

   A provider that is absent here will not answer however long the learner
   waits, so offering a retry would misdescribe what waiting can achieve. A
   request that failed on the way is worth asking again. These used to be one
   sentence with no way forward. */
const { attempt, isReady, canRetry, unavailable, failed } = await import(
  '../static/orena/capabilities/outcome.js'
);
const absent = await attempt(async () => ({ available: false, selected_text: 'x' }), {
  read: (r) => ({ ok: Boolean(r.available) }),
});
assert.equal(absent.state, 'unavailable');
assert.equal(canRetry(absent), false, 'an absent provider must not offer a retry');

const broke = await attempt(async () => { throw new Error('network'); });
assert.equal(broke.state, 'failed');
assert.equal(canRetry(broke), true, 'a failed request is worth asking again');

// A payload about different text is not an answer about this selection.
const mismatched = await attempt(async () => ({ available: true, selected_text: 'other' }), {
  read: (r) => ({ ok: r.available && r.selected_text === 'mine' }),
});
assert.equal(mismatched.state, 'unavailable');
assert.equal(isReady(mismatched), false);

const good = await attempt(async () => ({ available: true, selected_text: 'mine' }), {
  read: (r) => ({ ok: r.available && r.selected_text === 'mine' }),
});
assert.ok(isReady(good) && good.value.selected_text === 'mine', 'a real answer survives intact');
// A capability may say its failure is permanent.
assert.equal(canRetry(failed('gone', false)), false);
assert.equal(unavailable('no provider').reason, 'no provider');

// The panel must offer the retry only where retrying can help, and both
// messages must exist in both languages.
assert.match(understanding, /canRetry\(outcome\)/, 'the panel asks whether a retry is honest');
for (const ui of ['en', 'zh']) {
  assert.ok(copy[ui].understandingUnavailable, `${ui}: missing unavailable copy`);
  assert.ok(copy[ui].understandingFailed, `${ui}: missing failed copy`);
  assert.notEqual(
    copy[ui].understandingUnavailable,
    copy[ui].understandingFailed,
    `${ui}: the two outcomes must not say the same thing`,
  );
}

console.log(
  'Contextual understanding: shared judgement vocabulary EN/ZH, context-preserving follow-ups, late-answer rejection, and no invented authority PASS',
);
