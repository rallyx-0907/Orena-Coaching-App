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

const unsupported=createLocalAudioRecorder({mediaDevices:null,Recorder:null,URLApi});
assert.equal(await unsupported.start(),false);
assert.equal(unsupported.snapshot().status,'unsupported');

console.log('Local audio recorder lifecycle: PASS');
