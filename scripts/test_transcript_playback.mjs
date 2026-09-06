import assert from 'node:assert/strict';
import {activeCanonicalSegment} from '../static/orena/capabilities/transcript-timeline.js';

const segments=[
  {segment_id:'s0',start_ms:0,end_ms:3900},
  {segment_id:'s1',start_ms:2100,end_ms:6100},
  {segment_id:'s2',start_ms:6100,end_ms:9500},
  {segment_id:'s3',start_ms:9400,end_ms:12600},
];

assert.equal(activeCanonicalSegment(segments,500)?.segment_id,'s0');
assert.equal(activeCanonicalSegment(segments,2500)?.segment_id,'s1');
assert.equal(activeCanonicalSegment(segments,6500)?.segment_id,'s2');
assert.equal(activeCanonicalSegment(segments,9500)?.segment_id,'s3');
assert.equal(activeCanonicalSegment(segments,2500)?.segment_id,'s1');
assert.equal(activeCanonicalSegment(segments,500)?.segment_id,'s0');

console.log('TRANSCRIPT_PLAYBACK=PASS');
