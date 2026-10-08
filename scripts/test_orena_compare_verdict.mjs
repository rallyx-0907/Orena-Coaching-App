import assert from 'node:assert/strict';
import { pronunciationStatusKey } from '../static/orena/screens/compare/model.js';
assert.equal(pronunciationStatusKey({status:'close',errorType:'None',score:67}),'valueNotPassed',
  'a provider-recognised but below-target word cannot say Passed beside Not passed');
assert.equal(pronunciationStatusKey({status:'ok',errorType:'None',score:94}),'valuePassed');
assert.equal(pronunciationStatusKey({status:'unclear',errorType:'Omission'}),'valueUnclear');
console.log('Compare verdict: panel and Details share the same word status: PASS');
