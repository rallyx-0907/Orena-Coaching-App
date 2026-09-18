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
  const encounter=read('static/orena/ui/encounter.js');
  assert.match(encounter,/return \(\) => \{[\s\S]{0,400}recorder\.cleanup\(\)/,
    'the listening room releases the microphone when it is torn down');
  const voice=read('static/orena/ui/voice-response.js');
  assert.match(voice,/recorder\.cleanup\(\)/,
    'the voice response releases the microphone when it is torn down');
}

const unsupported=createLocalAudioRecorder({mediaDevices:null,Recorder:null,URLApi});
assert.equal(await unsupported.start(),false);
assert.equal(unsupported.snapshot().status,'unsupported');

console.log('Local audio recorder lifecycle: PASS');
