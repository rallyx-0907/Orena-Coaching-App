import assert from 'node:assert/strict';
import {evaluateListeningReconstruction as evaluate,listeningReconstructionDiff as diff} from '../static/orena/capabilities/dictation-evaluator.js';
import {activeCanonicalSegment} from '../static/orena/capabilities/transcript-timeline.js';
import {evaluateSpeechTranscript} from '../static/orena/capabilities/speech-comparison.js';
import {posterUrl,playbackAvailable,segmentPlaybackDelayMs} from '../static/orena/capabilities/media-player.js';
for(const [language,text,wrong] of [['en','A pen in my bag.','A pan in bag'],['zh','今天下雨了。','今天下鱼']]) {
  assert.equal(evaluate({source_language:language,expected:text,answer:text}).exact,true);
  assert.equal(evaluate({source_language:language,expected:text,answer:wrong}).exact,false);
  assert.ok(diff({source_language:language,expected:text,answer:wrong}).some(x=>x.status!=='correct'));
  assert.equal(evaluateSpeechTranscript(text,text).content_match,100);
}
assert.throws(()=>evaluate({source_language:'en',expected:'hello',answer:' '}));
assert.throws(()=>evaluate({source_language:'en',expected:'hello',answer:'a'.repeat(2001)}));
const segments=[{segment_id:'a',start_ms:100,end_ms:500},{segment_id:'b',start_ms:700,end_ms:1000}];
assert.equal(activeCanonicalSegment(segments,150).segment_id,'a');
assert.equal(activeCanonicalSegment(segments,500),null);
assert.equal(activeCanonicalSegment(segments,700).segment_id,'b');
assert.equal(activeCanonicalSegment(segments,1000),null);
assert.equal(segmentPlaybackDelayMs(1000,3000,2),1090,'Includes the existing 90ms playback-tail allowance');
assert.equal(posterUrl('https://thumb.wikimedia.org/x.jpg'),'https://thumb.wikimedia.org/x.jpg');
assert.equal(posterUrl('https://thumb.wikimedia.org.evil.test/x.jpg'),'');
assert.equal(playbackAvailable({kind:'video',provider:'wikimedia-commons',url:'https://thumb.wikimedia.org/x.webm'}),false);
console.log('Extracted capability primitives: PASS (EN/ZH reconstruction, speech comparison, timeline, rate and media origin safety)');
