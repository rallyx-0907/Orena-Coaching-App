import assert from 'node:assert/strict';
import {evaluateSpeechTranscript,speechLearningTokens} from '../static/orena/capabilities/speech-comparison.js';

assert.deepEqual(speechLearningTokens("Hello, world!"),["hello","world"]);
assert.deepEqual(speechLearningTokens("你好世界"),["你","好","世","界"]);

const perfect=evaluateSpeechTranscript("Hello world","hello world");
assert.equal(perfect.content_match,100);
assert.deepEqual(perfect.missing_tokens,[]);
assert.deepEqual(perfect.extra_tokens,[]);

const partial=evaluateSpeechTranscript("I want to learn English","I want learn English today");
assert.equal(partial.matched_count,4);
assert.deepEqual(partial.missing_tokens,["to"]);
assert.deepEqual(partial.extra_tokens,["today"]);
assert.equal(partial.content_match,80);

const zh=evaluateSpeechTranscript("今天天气很好","今天天气好");
assert.equal(zh.missing_tokens.length,1);
assert.ok(zh.content_match>80&&zh.content_match<100);

console.log("Speaking deterministic content matching: PASS");
