import assert from 'node:assert/strict';
import { isTransientRequestError, retryOnce } from '../static/orena/infrastructure/retry.js';

let attempts = 0;
const recovered = await retryOnce(
  async () => {
    attempts += 1;
    if (attempts === 1) {
      const error = new Error('temporary service failure');
      error.status = 503;
      throw error;
    }
    return { items: [] };
  },
  isTransientRequestError,
);
assert.deepEqual(recovered, { items: [] });
assert.equal(attempts, 2, 'a transient vocabulary read is retried once');

let permanentAttempts = 0;
await assert.rejects(
  retryOnce(
    async () => {
      permanentAttempts += 1;
      const error = new Error('invalid request');
      error.status = 422;
      throw error;
    },
    isTransientRequestError,
  ),
  /invalid request/,
);
assert.equal(permanentAttempts, 1, 'a non-transient vocabulary error is not retried');

assert.equal(isTransientRequestError({ status: 503 }), true);
assert.equal(isTransientRequestError({ status: 422 }), false);
assert.equal(isTransientRequestError({ name: 'TypeError' }), true);
assert.equal(isTransientRequestError({ name: 'SyntaxError' }), false);

console.log('Orena language recovery retry boundary: PASS');
