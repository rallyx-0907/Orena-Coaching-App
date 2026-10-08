// Pure Listening. Watching or listening to something and understanding it is a
// complete way to learn, so the encounter has to support it end to end without
// an exercise being the point. These assertions hold the data contracts under it:
// Follow leads, and meanings are the lesson's own, by segment id.
import assert from 'node:assert/strict';
import { practiceIntentions, deeperPractice, supports } from '../static/orena/product/intent.js';
import { encounter } from '../static/orena/product/encounter.js';

// Follow leads the intentions and opens nothing over the moment. Everything
// else is a path a learner may choose, never the definition of listening.
assert.equal(practiceIntentions[0], 'follow');
assert.ok(!deeperPractice.includes('follow'), 'Follow opens no practice panel');
assert.deepEqual(deeperPractice, ['dictation', 'shadowing', 'speaking']);
assert.equal(supports({ kind: 'audio' }, 'follow'), true);

/* Understanding the whole thing, not only the line under the playhead. The
   meanings are the ones the lesson already ships - the model already took a
   segment id, so nothing new is fetched or generated to show them. */
const payload = {
  transcript: {
    segments: [
      { segment_id: 'a', original_text: 'One.', start_ms: 0, end_ms: 1000 },
      { segment_id: 'b', original_text: 'Two.', start_ms: 1000, end_ms: 2000 },
    ],
  },
  translations: [
    { segment_id: 'a', target_language: 'vi', translated_meaning: 'Mot.', provenance: 'editorial' },
    { segment_id: 'b', target_language: 'vi', translated_meaning: 'Hai.', provenance: 'editorial' },
  ],
};
const model = encounter(payload, 'vi');
assert.equal(model.meaning('a'), 'Mot.', 'a meaning is readable by segment id');
assert.equal(model.meaning('b'), 'Hai.');
assert.equal(
  encounter(payload, 'ja').meaning('a'),
  null,
  'a meaning in a language the learner did not ask for is not shown',
);

console.log('Pure Listening: Follow leads and meanings come from the lesson: PASS');
