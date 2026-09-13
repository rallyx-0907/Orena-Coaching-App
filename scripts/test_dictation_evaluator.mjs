import assert from 'node:assert/strict';
import {MAX_LISTENING_EVALUATION_UNITS,MAX_LISTENING_RECONSTRUCTION_CHARS,evaluateListeningReconstruction,listeningReconstructionDiff,listeningUnits} from '../static/orena/capabilities/dictation-evaluator.js';
const evaluate=(source_language,expected,answer)=>evaluateListeningReconstruction({source_language,expected,answer});

assert.equal(evaluate('en','Listen to this idea.','Listen to this idea.').accuracy_percent,100);
assert.equal(evaluate('en','Listen to this idea.','LISTEN TO THIS IDEA').accuracy_percent,100);
assert.equal(evaluate('en','Listen, to this idea!','Listen to this idea').accuracy_percent,100);
assert.ok(evaluate('en','Listen to this complete idea','Listen to this idea').accuracy_percent<100);
assert.ok(evaluate('en','Listen to this idea','Please listen to this idea').accuracy_percent<100);
assert.ok(evaluate('en','Listen to this idea','Listen to that idea').accuracy_percent<100);
assert.ok(evaluate('en',"Don't stop listening","Dont stop listening").accuracy_percent<100);
assert.equal(evaluate('en',"Don\u2019t stop listening","Don't stop listening").accuracy_percent,100);

assert.equal(evaluate('zh','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b\u3002','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b\u3002').accuracy_percent,100);
assert.equal(evaluate('zh','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b\uff01','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b').accuracy_percent,100);
assert.equal(evaluate('zh','\u6211 \u4eec \u4e00 \u8d77 \u7ec3 \u4e60','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60').accuracy_percent,100);
assert.ok(evaluate('zh','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60').accuracy_percent<100);
assert.ok(evaluate('zh','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60','\u6211\u4eec\u4e00\u8d77\u7ec3\u4e60\u542c\u529b').accuracy_percent<100);
assert.ok(evaluate('zh','\u6211\u4eec\u7ec3\u4e60\u542c\u529b','\u4f60\u4eec\u7ec3\u4e60\u542c\u529b').accuracy_percent<100);
assert.deepEqual(listeningUnits('\u6211\u7528 GPT-4 \u5b66\u4e60 123','zh'),['\u6211','\u7528','gpt-4','\u5b66','\u4e60','123']);
assert.deepEqual(evaluate('zh','\u6211\u7528 GPT-4 \u5b66\u4e60 123','\u6211\u7528 GPT-4 \u5b66\u4e60 123'),evaluate('zh','\u6211\u7528 GPT-4 \u5b66\u4e60 123','\u6211\u7528 GPT-4 \u5b66\u4e60 123'));
assert.deepEqual(listeningReconstructionDiff({source_language:'en',expected:'Take the train home.',answer:'Take train safely home'}).map(item=>item.status),['correct','missing','correct','extra','correct']);
assert.deepEqual(listeningReconstructionDiff({source_language:'zh',expected:'\u6211\u4eca\u5929\u5f88\u597d\u3002',answer:'\u6211 \u4eca\u5929 \u597d'}).map(item=>item.status),['correct','correct','correct','missing','correct']);

assert.throws(()=>evaluate('en','Expected text','   '),error=>error.code==='answer_empty');
assert.throws(()=>evaluate('en','Expected text','x'.repeat(MAX_LISTENING_RECONSTRUCTION_CHARS+1)),error=>error.code==='answer_too_large');
assert.throws(()=>evaluate('en','word '.repeat(MAX_LISTENING_EVALUATION_UNITS+1),'word'),error=>error.code==='evaluation_too_large');

const originalFetch=globalThis.fetch;
globalThis.fetch=()=>{throw new Error('network must not be used');};
try{assert.equal(evaluate('en','Offline only','offline only').accuracy_percent,100);}finally{globalThis.fetch=originalFetch;}

console.log('Dictation evaluator EN/ZH: PASS');
