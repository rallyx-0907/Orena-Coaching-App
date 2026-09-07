// Guidance on a spoken response. The whole risk in this surface is a learner
// mistaking coaching for measurement, or a tutor quoting words they never said,
// so those are the things asserted here.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { spokenCoaching } from '../static/orena/ui/spoken-coaching.js';
import { voiceEvidence } from '../static/orena/ui/voice-evidence.js';
import { JUDGEMENT_KEYS } from '../static/orena/ui/understanding.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const result = {
  available: true,
  claim: 'spoken_response_coaching_from_transcript',
  carried: [
    { quote: 'the old market near the river', why: 'A specific place makes an invitation real.' },
  ],
  landed_differently: [
    {
      quote: 'it is very interesting for me',
      why: 'This gives your own reaction rather than a reason to come.',
      instead: 'you would love how noisy it gets',
      judgement: 'possible_but_unnatural',
    },
  ],
  another_way: 'I think you would really like it there.',
  next_attempt: 'Say one thing you would do together when you arrive.',
};

for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  const html = spokenCoaching(c, result, 'en');
  // The heading and the note must say what kind of claim this is, in both
  // languages. A learner who cannot tell guidance from measurement can judge
  // neither.
  assert.ok(html.includes(c.coachingTitle), `${ui}: coaching is not titled`);
  assert.ok(html.includes(c.coachingNote), `${ui}: coaching does not say what it is`);
  assert.ok(html.includes(c.coachingCarried) && html.includes(c.coachingLanded), `${ui}: sections missing`);
  assert.ok(html.includes('the old market near the river'), `${ui}: the learner's words are missing`);
  assert.ok(html.includes('you would love how noisy it gets'), `${ui}: the alternative is missing`);
}

// Nothing is shown when nothing came back, and no rewrite is invented.
assert.equal(spokenCoaching(copy.en, { available: false, carried: [], landed_differently: [] }, 'en'), '');
assert.equal(spokenCoaching(copy.en, null, 'en'), '');
assert.equal(
  spokenCoaching(copy.en, { available: true, carried: [], landed_differently: [] }, 'en'),
  '',
  'an empty answer renders nothing rather than an empty shell',
);
assert.ok(
  !spokenCoaching(
    copy.en,
    { ...result, carried: [{ quote: '<img src=x onerror=alert(1)>', why: 'x' }] },
    'en',
  ).includes('<img'),
  'coaching text is escaped',
);

// A dimension that does not apply is a different claim from one that could have
// been measured and was not.
const free = {
  dimensions: { transcription_confidence: 0.91, content_match: null, pronunciation: null },
  provenance: { transcription_confidence: 'speech_asr', content_match: 'not_applicable', pronunciation: null },
  evidence: {},
};
for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  const html = voiceEvidence(c, free, 'en');
  assert.ok(html.includes('data-inapplicable'), `${ui}: an inapplicable dimension is not marked`);
  assert.ok(html.includes(c.notApplicable), `${ui}: "does not apply" is not said`);
  assert.ok(html.includes(c.sourceNotApplicable), `${ui}: the reason it does not apply is not given`);
  assert.ok(c.notApplicable !== c.notMeasured, `${ui}: the two states read identically`);
}
const measured = voiceEvidence(
  copy.en,
  {
    dimensions: { content_match: 72 },
    provenance: { content_match: 'deterministic_reference_alignment' },
    evidence: {},
  },
  'en',
);
assert.ok(!measured.includes('data-inapplicable'), 'a measured dimension is not inapplicable');
assert.ok(!measured.includes('data-unmeasured'), 'a measured dimension is not unmeasured');

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
const spokenSchema = server.split('def _spoken_schema()')[1].split('def ')[0];
assert.ok(
  spokenSchema.includes('"enum": list(USAGE_JUDGEMENTS)'),
  'coaching must reuse the shared judgement vocabulary',
);
assert.ok(JUDGEMENT_KEYS.includes('possible_but_unnatural'));

// Guidance is a separate request, made after the take is safe, and it never
// blocks the transcript or the evidence.
const voice = read('static/orena/ui/voice-response.js');
assert.ok(voice.includes('void loadSpokenCoaching('), 'coaching must not be awaited in the result path');
assert.ok(
  voice.includes("loadSpokenCoaching(result.querySelector('[data-coaching]')"),
  'coaching fills its own host, not the evidence panel',
);
assert.ok(
  voice.includes('<div data-coaching></div>') &&
    voice.includes('voiceEvidence(c, value.evaluation, language)'),
  'measurement and coaching are rendered as separate panels',
);
// The situation the learner answered travels with the transcript, or coaching
// marks ordinary choices as omissions against a task it had to guess.
assert.ok(voice.includes('situation: prompt'), 'coaching is told what was asked');

console.log('Orena spoken coaching, inapplicable evidence and shared judgements: PASS');
