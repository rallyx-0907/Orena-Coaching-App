/* Gate for the Lesson complete modal's pure data (static/orena/screens/lesson-complete/model.js),
   frame 63 / E3 §7. No DOM - imports only the DOM-free module. Locks rule 40: a fact with no real
   label or no real value is dropped, `0` (a real measured zero) is kept. */
import assert from 'node:assert/strict';
import { measuredScore, sanitizeFacts } from '../static/orena/screens/lesson-complete/model.js';

assert.deepEqual(sanitizeFacts(undefined), [], 'no facts given: an empty list, never invented ones');
assert.deepEqual(sanitizeFacts(null), []);
assert.deepEqual(sanitizeFacts([]), []);

assert.deepEqual(
  sanitizeFacts([{ label: 'words reviewed', value: 12 }, { label: 'min', value: 4 }]),
  [{ label: 'words reviewed', value: 12 }, { label: 'min', value: 4 }],
  'real facts pass through unchanged',
);

assert.deepEqual(
  sanitizeFacts([{ label: 'new words', value: 0 }]),
  [{ label: 'new words', value: 0 }],
  'a real measured zero is a real fact - rule 40 keeps it, never drops it as if it were missing',
);

assert.deepEqual(
  sanitizeFacts([
    { label: '', value: 5 },
    { label: 'XP', value: null },
    { label: 'XP', value: undefined },
    { label: 'XP', value: '' },
    { label: '   ', value: '   ' },
    null,
    undefined,
  ]),
  [],
  'no label, no value, or a value that is only whitespace: never shown as if it were a real fact',
);

assert.deepEqual(
  sanitizeFacts([{ label: '  words reviewed  ', value: '12' }]),
  [{ label: 'words reviewed', value: '12' }],
  'a label is trimmed; a string value is kept exactly (the caller already formatted it)',
);

/* The percentage (D-098): the server's own count out of its own total, or nothing. */
assert.equal(measuredScore({ correct: 3, total: 4 }), 75);
assert.equal(measuredScore({ correct: 0, total: 5 }), 0, 'a measured zero is a real score');
assert.equal(measuredScore({ correct: 2, total: 3 }), 67);
for (const missing of [undefined, null, {}, { correct: 3 }, { total: 4 }, { correct: 1, total: 0 }, { correct: 5, total: 4 }, { correct: -1, total: 4 }, { correct: 1.5, total: 4 }, { correct: '3', total: '4' }]) {
  assert.equal(measuredScore(missing), null, `${JSON.stringify(missing)} is not a measurement: no percentage`);
}

console.log('test_orena_screen_lesson-complete.mjs: Lesson complete modal - rule 40 fact sanitising, measured score only: PASS');
