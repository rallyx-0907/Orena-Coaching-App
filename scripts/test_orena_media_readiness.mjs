import assert from 'node:assert/strict';
import { transcriptState } from '../static/orena/screens/listening/model.js';
assert.equal(transcriptState({transcript:null,asset:{processing_state:'processing'}}),'processing');
assert.equal(transcriptState({transcript:null,asset:{processing_state:'ready'}}),'unavailable');
assert.equal(transcriptState({transcript:{segments:[{original_text:'Hello'}]}}),'ready');
assert.equal(transcriptState({transcript:{segments:[]},processing:{state:'failed'}}),'unavailable');
console.log('Media readiness: PASS');
