import assert from 'node:assert/strict';
import { applyLifecycle } from '../static/orena/capabilities/admin-content.js';
const calls = [];
await applyLifecycle({ setMediaStatus: async (...args) => calls.push(args) }, 'media', 'M', 'publish');
assert.deepEqual(calls, [['M', 'published']]);
await applyLifecycle({ setMediaStatus: async (...args) => calls.push(args) }, 'media', 'M', 'restore');
assert.deepEqual(calls[1], ['M', 'unpublished'], 'Restore returns to reviewable shelf without publication');
console.log('Admin media review Publish uses canonical status API: PASS');
