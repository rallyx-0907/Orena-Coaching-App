import assert from 'node:assert/strict';
const {createLocalAudioRecorder,localAudioRecordingSupported}=await import('../static/orena/capabilities/audio-recorder.js');
let stoppedTracks=0;
const fakeStream={getTracks:()=>[{stop(){stoppedTracks+=1;}}]};
const mediaDevices={async getUserMedia(options){
  assert.deepEqual(options,{audio:true});
  return fakeStream;
}};
class FakeRecorder{
  constructor(stream){
    assert.equal(stream,fakeStream);
    this.listeners=new Map();
    this.mimeType='audio/webm';
    this.state='inactive';
  }
  addEventListener(name,handler){this.listeners.set(name,handler);}
  start(){this.state='recording';}
  stop(){
    this.listeners.get('dataavailable')?.({data:new Blob(['voice'],{type:'audio/webm'})});
    this.state='inactive';
    this.listeners.get('stop')?.();
  }
}
const revoked=[];
const URLApi={
  createObjectURL(){return 'blob:local-speaking-take';},
  revokeObjectURL(url){revoked.push(url);},
};

assert.equal(localAudioRecordingSupported({mediaDevices,Recorder:FakeRecorder}),true);
const speechMediaDevices={
  async getUserMedia(constraints){
    assert.equal(constraints?.audio?.echoCancellation?.ideal,true);
    assert.equal(constraints?.audio?.noiseSuppression?.ideal,false);
    assert.equal(constraints?.audio?.autoGainControl?.ideal,false);
    assert.equal(constraints?.audio?.channelCount?.ideal,1);
    // Reuse the legacy fake stream while validating the new recorder contract.
    return mediaDevices.getUserMedia({audio:true});
  },
};
const recorder=createLocalAudioRecorder({mediaDevices:speechMediaDevices,Recorder:FakeRecorder,URLApi});
assert.equal(await recorder.start(),true);
assert.equal(recorder.snapshot().status,'recording');
const take=await recorder.stop();
assert.equal(take.url,'blob:local-speaking-take');
assert.equal(take.size>0,true);
assert.equal(recorder.snapshot().status,'ready');
assert.equal(stoppedTracks,1);
assert.equal(recorder.discard(),true);
assert.deepEqual(revoked,['blob:local-speaking-take']);

/* Leaving the room while recording must release the microphone.

   A recorder that is still capturing when the learner navigates away leaves the
   browser's recording indicator on and the device held open. `cleanup()` is the
   teardown every room calls, and it has to stop the tracks whether or not the
   take was ever finished. */
{
  let stopped=0;
  // The shared FakeRecorder asserts it is handed the one known stream, so the
  // teardown case reuses it and counts its own stops.
  const liveStream=fakeStream;
  const originalStop=liveStream.getTracks;
  liveStream.getTracks=()=>[{stop(){stopped+=1;}}];
  const devices={async getUserMedia(){return liveStream;}};
  const mid=createLocalAudioRecorder({mediaDevices:devices,Recorder:FakeRecorder,URLApi});
  assert.equal(await mid.start(),true);
  assert.equal(mid.snapshot().status,'recording');
  mid.cleanup();
  assert.equal(stopped,1,'navigating away mid-recording stops the microphone track');
  assert.equal(mid.snapshot().status,'idle','and the recorder is left in a clean state');
  liveStream.getTracks=originalStop;
}

/* Every room that can record hands that teardown back to the route lifecycle. */
{
  const { readFileSync } = await import('node:fs');
  const read=(path)=>readFileSync(new URL(`../${path}`, import.meta.url),'utf8');
  for (const screen of ['conversation','free-talk']) {
    const src=read(`static/orena/screens/${screen}/screen.js`);
    assert.match(src,/createLocalAudioRecorder\(\)/,`${screen} records through the shared recorder`);
    assert.match(src,/recorder\.cleanup\(\)/,`${screen} releases the microphone when it is torn down`);
  }
  const voice=read('static/orena/screens/orena/voice.js');
  assert.match(voice,/recorder\.cleanup\(\)/,'the Orena voice screen releases the microphone when it is torn down');
}

/* #443: an AudioContext that will not run (iOS Safari: `suspended` outside a tap, `interrupted` after other media
   played) would record silence through the processing graph. The take records the microphone's own stream then. */
{
  let closed=0;
  class StuckContext{
    constructor(){this.sampleRate=48000;this.state='suspended';}
    resume(){return new Promise(()=>{});} // never settles, as iOS can leave it
    close(){closed+=1;return Promise.resolve();}
  }
  const devices={async getUserMedia(){return fakeStream;}};
  const stuck=createLocalAudioRecorder({mediaDevices:devices,Recorder:FakeRecorder,URLApi,AudioContextCtor:StuckContext});
  assert.equal(await stuck.start(),true,'the take starts, on the native stream (FakeRecorder asserts it is the microphone stream)');
  assert.equal(stuck.snapshot().processing_mode,'native-fallback');
  assert.equal(closed,1,'the context that would not run is closed');
  assert.equal(stuck.input(),fakeStream,'the live input is the microphone stream, for a level meter to clone');
  await stuck.stop();
}

/* #439: a recorder that never reports its end does not leave the room recording for ever. */
{
  const { STOP_WAIT_MS }=await import('../static/orena/capabilities/audio-recorder.js');
  assert.ok(STOP_WAIT_MS>=2000&&STOP_WAIT_MS<=6000,'a bounded wait, long enough for a real recorder');
  const src=(await import('node:fs')).readFileSync(new URL('../static/orena/capabilities/audio-recorder.js',import.meta.url),'utf8');
  assert.match(src,/watchdog=setTimeout\(/,'stop() is bounded by a watchdog');
  assert.match(src,/error='recording_failed';\n\s+finish\(null\);/,'a recorder that never ends is reported as a failed take');
}

const unsupported=createLocalAudioRecorder({mediaDevices:null,Recorder:null,URLApi});
assert.equal(await unsupported.start(),false);
assert.equal(unsupported.snapshot().status,'unsupported');

console.log('Local audio recorder lifecycle: PASS');
