// The contextual explanation API (POST /api/media-learning/explain) is bounded server-side: an
// explanation stays about something the learner can see, never manufactures authority, and names
// a problem with one fixed vocabulary of judgements. The learner UI reaches it through
// infrastructure/api.js; these assertions hold the parts of the contract that live on the server.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const server = readFileSync('writing_coach/media_interaction.py', 'utf8');
const api = readFileSync('static/orena/infrastructure/api.js', 'utf8');

assert.match(api, /explainMediaText:\(payload\)=>request\('\/api\/media-learning\/explain'/, 'the client reaches the explanation endpoint');

// "Wrong" is not one thing: the server names every distinction, and a fixed set of them.
const declared = [
  ...server
    .split('USAGE_JUDGEMENTS = (')[1]
    .split(')')[0]
    .matchAll(/"([a-z_]+)"/g),
].map((m) => m[1]);
assert.ok(declared.length >= 4, 'the judgement vocabulary distinguishes more than right and wrong');
assert.equal(new Set(declared).size, declared.length, 'no judgement is declared twice');
assert.ok(declared.includes('natural'), 'the default judgement is one of them');
assert.match(
  server,
  /return candidate if candidate in USAGE_JUDGEMENTS else "natural"/,
  'a judgement outside the vocabulary is not passed through',
);

// The server refuses a selection its context does not contain.
assert.match(
  server,
  /if source\.casefold\(\) not in context\.casefold\(\)/,
  'an explanation must stay about something the learner can see',
);
assert.match(
  server,
  /Never cite a source, rule number, dictionary or corpus you were not/,
  'explanations must not manufacture authority',
);

console.log('Contextual understanding: the server-side judgement vocabulary, context bound and no invented authority PASS');
