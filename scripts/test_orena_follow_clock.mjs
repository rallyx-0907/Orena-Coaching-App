import assert from 'node:assert/strict';
import {connectMediaPlayer,disconnectMediaPlayer,replaySegment,seekPlayback,setPlaybackRate} from '../static/orena/capabilities/media-player.js';
import {encounter} from '../static/orena/product/encounter.js';

class ElementStub extends EventTarget {dataset={};isConnected=true;}
class AudioStub extends ElementStub {
  currentTime=0;duration=10;paused=true;readyState=1;playbackRate=1;
  play(){this.paused=false;return Promise.resolve();}
  pause(){this.paused=true;}
}
globalThis.Element=ElementStub;globalThis.HTMLAudioElement=AudioStub;
globalThis.HTMLVideoElement=class extends AudioStub{};
globalThis.HTMLIFrameElement=class extends ElementStub{};
const audio=new AudioStub();const root=new ElementStub();root.querySelector=()=>audio;
const playback={kind:'audio',provider:'wikimedia-commons',url:'https://upload.wikimedia.org/audio.ogg'};
const model=encounter({transcript:{segments:[{segment_id:'one',start_ms:0,end_ms:1000,original_text:'你好'},{segment_id:'two',start_ms:1000,end_ms:3000,original_text:'再见'}]},translations:[{segment_id:'one',target_language:'en',translated_meaning:'Hello'},{segment_id:'two',target_language:'en',translated_meaning:'Goodbye'}]},'en');
root.addEventListener('orena:media-time',event=>model.follow(event.detail.time_ms));
const tick=()=>new Promise(resolve=>setTimeout(resolve,160));
try {
  assert.equal(connectMediaPlayer(root,playback),true);
  seekPlayback(root,playback,1500);assert.equal(model.current.segment_id,'two');assert.equal(model.meaning(),'Goodbye');
  replaySegment(root,playback,0,1000,1);assert.equal(model.meaning(),'Hello');
  for(const rate of [.5,.75,1,1.25,1.5,2]){assert.equal(setPlaybackRate(root,playback,rate),true);assert.equal(audio.playbackRate,rate);}
  // A rate change or buffering must not cause a wall-clock deadline to end the line.
  audio.currentTime=.5;await tick();assert.equal(audio.paused,false);
  audio.currentTime=1.1;await tick();assert.equal(audio.paused,true);
  replaySegment(root,playback,0,1000);seekPlayback(root,playback,1500);await tick();
  assert.equal(audio.paused,false,'Seeking cancels the previous replay boundary');
  assert.equal(model.current.segment_id,'two');assert.equal(model.meaning(),'Goodbye');
  audio.dispatchEvent(new Event('error'));
  assert.equal(root.dataset.mediaClock,'error','A failed source is observable to the product');
} finally {disconnectMediaPlayer(root);}
assert.equal(audio.paused,true,'Leaving an encounter stops its native audio');
audio.dispatchEvent(new Event('loadedmetadata'));
audio.dispatchEvent(new Event('play'));
assert.equal(root.dataset.mediaClock,'disconnected','Late media events cannot revive a retired encounter');
console.log('Follow playback clock: seek, selection, replay and all displayed rates PASS');
