import assert from 'node:assert/strict';
import { speakModes, listenModes } from '../static/orena/screens/practice/model.js';
import { practiceCandidates, practiceHref } from '../static/orena/screens/discover/model.js';
const catalog = [{ lesson_id: 'a', available_modes: ['listen','dictation','shadowing'], comprehension_count: 2 }];
// D-139 HD-2: Speak offers Pronunciation and Shadowing, each once, both through the media chooser (no first-lesson assignment).
const speakEntries = speakModes([{practice_type:'clip',id:'media:a'}]).filter(m => ['speak','shadow'].includes(m.key));
assert.deepEqual(speakEntries.map(m => [m.key, m.routeId, m.query.practice]), [['speak','discover','pronunciation'],['shadow','discover','shadowing']]);
assert.ok(speakEntries.every(m => !m.params), 'no first-lesson assignment');
assert.deepEqual(listenModes(catalog).map(m => [m.key,m.routeId,m.query.practice]), [['listening','discover','listening'],['dictation','discover','dictation']]);
assert.ok(listenModes(catalog).every(m => !m.params), 'no first-lesson assignment');
const entries=[{id:'media:a',kind:'media',availableModes:['dictation','shadowing'],comprehensionCount:2}, {id:'media:b',kind:'media',availableModes:['dictation'],comprehensionCount:0}];
assert.equal(practiceCandidates(entries,'listening').length,1);
assert.equal(practiceCandidates(entries,'dictation').length,2);
const href=(route,params,query)=>({route,params,query});
assert.equal(practiceHref(entries[1],href,{intent:'dictation'}).route,'dictation');
assert.equal(practiceHref(entries[0],href,{intent:'listening'}).route,'listenQuestions');
console.log('Listening entries: distinct skills, content selection, ready questions: PASS');
