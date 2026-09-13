// Speaking evidence has to keep the line between what a stack measured, what
// was computed against the reference, and what is only guidance. These
// assertions are about never letting one pass for another.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { voiceEvidence, sourceLabel } from '../static/orena/ui/voice-evidence.js';

// The dimensions the evaluator can report are the dimensions a learner can read.
const evaluator = readFileSync('writing_coach/speaking_evaluator.py', 'utf8');
const declared = [
  ...evaluator.split('DIMENSIONS = (')[1].split(')')[0].matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
for (const ui of ['en', 'zh'])
  for (const key of declared)
    assert.ok(copy[ui][`dimension_${key}`], `${ui}: no label for dimension "${key}"`);

const full = {
  dimensions: {
    transcription_confidence: 91,
    content_match: 78,
    pronunciation: 84,
    fluency: null,
    proficiency: null,
  },
  provenance: {
    transcription_confidence: 'speech_asr',
    content_match: 'deterministic_reference_alignment',
    pronunciation: 'azure-speech',
    fluency: null,
    proficiency: 'not_assessed',
  },
  evidence: {
    synthetic_demo: false,
    content: { missing_tokens: ['pen'], extra_tokens: ['the'] },
  },
  next_steps: [{ kind: 'focus_words', words: ['pen'] }, { kind: 'fluency', words: [] }],
};

for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  const html = voiceEvidence(c, full, 'en');
  // Measured, derived and guidance are three separate statements.
  assert.ok(html.includes(c.measuredHere), `${ui}: measurement is named`);
  assert.ok(html.includes(c.againstTheLine), `${ui}: alignment is named`);
  assert.ok(html.includes(c.whatToTryNext), `${ui}: guidance is named`);
  assert.ok(
    html.includes(c.guidanceNote),
    `${ui}: guidance must say it is not a measurement`,
  );
  // A dimension nothing measured says so instead of showing a number.
  assert.ok(html.includes('data-unmeasured'), `${ui}: unmeasured dimensions marked`);
  assert.ok(html.includes(c.sourceNotAssessed), `${ui}: proficiency is not assessed`);
  assert.ok(
    html.includes(c.proficiencyNote),
    `${ui}: one recording must not claim proficiency`,
  );
  // Provenance is stated per dimension, never implied.
  assert.ok(html.includes(c.sourceAsr), `${ui}: recognition is attributed`);
  assert.ok(html.includes(c.sourceAlignment), `${ui}: alignment is attributed`);
  assert.ok(html.includes('azure-speech'), `${ui}: an unknown provider is still named`);
}

// A demonstration score is labelled before anything else is read.
const demo = voiceEvidence(
  copy.en,
  { ...full, evidence: { ...full.evidence, synthetic_demo: true } },
  'en',
);
assert.ok(demo.includes(copy.en.demoMeasurement), 'a demo value is labelled');
assert.ok(
  demo.indexOf(copy.en.demoMeasurement) < demo.indexOf(copy.en.measuredHere),
  'the demo label comes before the numbers it qualifies',
);

// Nothing to show is nothing shown, rather than an empty scaffold.
assert.equal(voiceEvidence(copy.en, null, 'en'), '');
assert.equal(voiceEvidence(copy.en, undefined, 'en'), '');
const bare = voiceEvidence(copy.en, { dimensions: {}, provenance: {} }, 'en');
assert.ok(!bare.includes(copy.en.againstTheLine), 'no alignment section without tokens');
assert.ok(!bare.includes(copy.en.whatToTryNext), 'no guidance section without steps');

// An unrecognised step kind is dropped rather than rendered as an empty bullet.
const unknown = voiceEvidence(
  copy.en,
  { ...full, next_steps: [{ kind: 'not_a_real_step', words: [] }] },
  'en',
);
assert.ok(!unknown.includes('<li>'), 'an unlabelled step is not invented');

assert.equal(sourceLabel(copy.en, null), copy.en.notMeasured);
assert.equal(sourceLabel(copy.en, 'speech_asr'), copy.en.sourceAsr);

// The surface must use this rather than collapsing the envelope again.
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
assert.match(encounter, /voiceEvidence\(c, result\.evaluation, language\)/);
assert.doesNotMatch(
  encounter,
  /c\.contentMatch\}: \$\{result\.content_match/,
  'the single-percentage summary is retired, not sitting beside the evidence',
);

console.log(
  'Speaking evidence: measured, derived and guidance kept apart, unmeasured dimensions named, EN/ZH PASS',
);
