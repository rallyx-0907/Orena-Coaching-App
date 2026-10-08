/* Re-runs the browser Dictation evaluator on the shared golden vectors (D4 I18). The Python port is
   held to the same file by tests/test_dictation_evaluator.py; regenerate with
   scripts/generate_dictation_golden.mjs only when the browser evaluator's behaviour is meant to change. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { evaluateListeningReconstruction } from '../static/orena/capabilities/dictation-evaluator.js';

const { cases } = JSON.parse(readFileSync(fileURLToPath(new URL('../tests/fixtures/dictation_golden.json', import.meta.url)), 'utf8'));
assert.ok(cases.length >= 60, 'the vector file has its cases');
for (const { input, result, error } of cases) {
  let actual;
  try {
    actual = { result: evaluateListeningReconstruction(input) };
  } catch (thrown) {
    actual = { error: thrown.code };
  }
  assert.deepEqual(actual, error ? { error } : { result }, `golden vector drifted: ${JSON.stringify(input).slice(0, 120)}`);
}
console.log(`Dictation golden vectors: ${cases.length} cases match the browser evaluator: PASS`);
