// Guidance on a spoken response. The whole risk in this surface is a learner
// mistaking coaching for measurement, or a tutor quoting words they never said,
// so those are the things asserted here.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

// Both sides agree on the marker, and the evaluator only uses it when there was
// genuinely no line.
const evaluator = read('writing_coach/speaking_evaluator.py');
assert.ok(
  /"not_applicable"\s*\n\s*if not reference/.test(evaluator),
  'alignment is inapplicable only without a reference',
);

// `includes` rather than `match`: a failed regex against a 40KB file prints the
// whole file, which buries the one line that actually broke.
const server = read('writing_coach/media_interaction.py');
const inServer = (needle, why) => assert.ok(server.includes(needle), why);
inServer(
  '@contextual_router.post("/spoken-response")',
  'coaching must hang off the router the app actually includes',
);
// It reads a transcript. It never heard the audio, and it must not pretend to.
inServer('never comment on pronunciation, ', 'coaching must not describe how the learner sounded');
inServer('You did NOT hear the audio', 'the prompt must say what it is reading');
inServer('score, grade or estimate a level', 'coaching must not score');
inServer('quote not in transcript', 'a quotation the learner never said is dropped');
inServer('Never cite a source you were not given', 'no invented authority');

// The judgement vocabulary is the shared one, so a spoken problem is named the
// same way a written or a read one is.
const spokenSchema = server.split('def _spoken_base_schema()')[1].split('def ')[0];
assert.ok(
  spokenSchema.includes('"enum": list(USAGE_JUDGEMENTS)'),
  'coaching must reuse the shared judgement vocabulary',
);
assert.ok(server.includes('USAGE_JUDGEMENTS = (') && /USAGE_JUDGEMENTS = \([^)]*"possible_but_unnatural"/s.test(server), 'the shared vocabulary names an unnatural-but-possible usage');

// The learner UI asks for coaching after the take is safe, and tells it what was asked: the
// situation travels with the transcript, or coaching marks ordinary choices as omissions against
// a task it had to guess.
for (const screen of ['free-talk', 'conversation', 'react']) {
  const src = read(`static/orena/screens/${screen}/screen.js`);
  const call = src.slice(src.indexOf('api.spokenResponseCoaching('));
  assert.ok(src.includes('api.spokenResponseCoaching('), `${screen} requests coaching`);
  assert.match(call.slice(0, 500), /situation:/, `${screen}: coaching is told what was asked`);
}

console.log('Orena spoken coaching: server contract, shared judgements and situation carried: PASS');
