// Pure Listening. Watching or listening to something and understanding it is a
// complete way to learn, so the encounter has to support it end to end without
// an exercise being the point. These assertions hold the three things that make
// it complete rather than a player with a transcript beside it.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { practiceIntentions, deeperPractice, supports } from '../static/orena/product/intent.js';
import { encounter } from '../static/orena/product/encounter.js';

const encounterSource = readFileSync(
  new URL('../static/orena/ui/encounter.js', import.meta.url),
  'utf8',
);

// Follow leads the intentions and opens nothing over the moment. Everything
// else is a path a learner may choose, never the definition of listening.
assert.equal(practiceIntentions[0], 'follow');
assert.ok(!deeperPractice.includes('follow'), 'Follow opens no practice panel');
assert.deepEqual(deeperPractice, ['dictation', 'shadowing', 'speaking']);
assert.equal(supports({ kind: 'audio' }, 'follow'), true);

/* Asking what something means must not cost the learner their place. Without
   this the voice runs on behind the answer and they come back three lines
   later, which is exactly the failure that makes people stop following. */
assert.ok(
  encounterSource.includes('function holdTheVoice()'),
  'a question asked while the voice runs must pause it',
);
assert.ok(
  /const held = holdTheVoice\(\);/.test(encounterSource),
  'the inspect action holds the voice before opening the answer',
);
assert.ok(
  encounterSource.includes('c.heldForYou'),
  'the learner is told the voice was paused, not left to notice',
);

/* Reaching the end is the thing this intention is for, and it used to pass
   unmarked. It is not a score and it opens no exercise. */
assert.ok(
  encounterSource.includes('reachedTheEnd = true'),
  'following something to its end must be recognised',
);
assert.ok(
  /reachedTheEnd &&\s*\n\s*!playing/.test(encounterSource),
  'the end is only marked once the player has settled, not mid-play',
);
assert.ok(
  encounterSource.includes('payload.catalog?.excerpt_end_ms || payload.asset.duration_ms'),
  'an excerpt ends where the excerpt ends, not where the source asset does',
);
for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  for (const key of [
    'reachedTheEnd',
    'reachedTheEndNote',
    'hearItAgain',
    'readItThrough',
    'showAllMeaning',
    'allMeaningNote',
    'heldForYou',
  ])
    assert.ok(c[key] && c[key].length > 2, `${ui}: missing copy for "${key}"`);
  // What follows the end must not read as a verdict or a next exercise.
  assert.ok(
    !/\bscore\b|\bwell done\b|\bcongratulations\b|得分|恭喜/i.test(c.reachedTheEnd),
    `${ui}: reaching the end is not a result`,
  );
}

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
assert.ok(
  encounterSource.includes('model.meaning(s.segment_id)'),
  'the transcript reads meanings from the lesson rather than fetching them',
);
assert.ok(
  encounterSource.includes('data-meaning-note'),
  'shown meanings say where they came from',
);

/* --- A spoken segment is one block, not two columns ---

   Setting the original and its meaning side by side turns one utterance into
   two things to read, makes the pair break apart the moment the column
   narrows, and leaves the active-line highlight covering only half of what the
   learner is following. Time, original and meaning stack, in that order, and
   the highlight covers the whole of it. */
assert.ok(
  encounterSource.includes('<span class="line-original"'),
  'the original line is named, so it can be styled apart from its meaning',
);
const segmentMarkup = encounterSource.slice(
  encounterSource.indexOf('<li><button data-segment='),
  encounterSource.indexOf('</button></li>'),
);
assert.ok(
  segmentMarkup.indexOf('<time>') <
    segmentMarkup.indexOf('line-original') &&
    segmentMarkup.indexOf('line-original') < segmentMarkup.indexOf('line-meaning'),
  'time, then the line, then what it means',
);

const listeningCss = readFileSync(new URL('../static/orena/listening.css', import.meta.url), 'utf8');
/* The row rule is scoped to actual transcript rows: the panel also holds ordinary controls (the head's
   chips, the hint), and they are not rows. */
const rowStart = listeningCss.indexOf('.listen-workspace .transcript-panel li > [data-segment] {');
const segmentRule = listeningCss.slice(rowStart, listeningCss.indexOf('}', rowStart));
assert.ok(rowStart > 0, 'the row rule was found');
assert.ok(
  /display:\s*grid/.test(segmentRule) && /grid-template-columns:\s*56px/.test(segmentRule),
  "the segment is a grid of the time and the line's own stack, as the frame draws it",
);
assert.ok(
  !/display:\s*flex/.test(segmentRule),
  'a flex row is what made the original and its meaning parallel columns',
);
assert.ok(
  listeningCss.includes("li[data-current] .line-meaning {"),
  'the lit block carries its meaning with it, set off by an edge, rather than highlighting half of itself',
);

/* --- Support text ships in its own writing system --- */
assert.ok(
  !/\.transcript-panel \[data-segment\] > span/.test(listeningCss),
  'styling every child alike is what flattened the meaning into a second original',
);

console.log('Pure Listening: following to the end, holding the voice, and reading it through: PASS');
