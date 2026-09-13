/* The RNNoise vendor module touches AudioWorkletNode at import time, so a
   static import here made this file - and every screen importing it - unusable
   in the Node contract tests. It is only needed once a recording actually
   starts, so it is loaded then: {loadRnnoise,RnnoiseWorkletNode} arrive from
   the same module, just later. */

const SPEECH_AUDIO_CONSTRAINTS={
  echoCancellation:{ideal:true},
  noiseSuppression:{ideal:false},
  autoGainControl:{ideal:false},
  channelCount:{ideal:1},
};

const SPEECH_ENHANCEMENT={
  highpassHz:80,
  lowpassHz:9000,
  outputGain:2.0,
  compressorThreshold:-18,
  compressorKnee:12,
  compressorRatio:4,
  compressorAttack:0.003,
  compressorRelease:0.25,
};

const RNNOISE_ASSETS={
  worklet:new URL('../vendor/web-noise-suppressor/rnnoiseWorklet.js',import.meta.url).href,
  wasm:new URL('../vendor/web-noise-suppressor/rnnoise.wasm',import.meta.url).href,
  simdWasm:new URL('../vendor/web-noise-suppressor/rnnoise_simd.wasm',import.meta.url).href,
};

function stopTracks(stream){
  for(const track of stream?.getTracks?.()||[]){
    try{track.stop();}catch{}
  }
}

async function buildRnnoisePipeline(stream,{
  AudioContextCtor=globalThis.AudioContext||globalThis.webkitAudioContext,
}={}){
  if(typeof AudioContextCtor!=='function')return null;

  let context;
  try{
    context=new AudioContextCtor({sampleRate:48000});
  }catch{
    context=new AudioContextCtor();
  }

  if(context.sampleRate!==48000){
    try{await context.close();}catch{}
    return null;
  }

  try{
    const {loadRnnoise,RnnoiseWorkletNode}=await import('../vendor/web-noise-suppressor/index.js');
    const wasmBinary=await loadRnnoise({
      url:RNNOISE_ASSETS.wasm,
      simdUrl:RNNOISE_ASSETS.simdWasm,
    });
    await context.audioWorklet.addModule(RNNOISE_ASSETS.worklet);

    const source=context.createMediaStreamSource(stream);
    const denoiser=new RnnoiseWorkletNode(context,{
      wasmBinary,
      maxChannels:1,
    });

    const highpass=context.createBiquadFilter();
    highpass.type='highpass';
    highpass.frequency.value=SPEECH_ENHANCEMENT.highpassHz;
    highpass.Q.value=0.707;

    const lowpass=context.createBiquadFilter();
    lowpass.type='lowpass';
    lowpass.frequency.value=SPEECH_ENHANCEMENT.lowpassHz;
    lowpass.Q.value=0.707;

    const gain=context.createGain();
    gain.gain.value=SPEECH_ENHANCEMENT.outputGain;

    const compressor=context.createDynamicsCompressor();
    compressor.threshold.value=SPEECH_ENHANCEMENT.compressorThreshold;
    compressor.knee.value=SPEECH_ENHANCEMENT.compressorKnee;
    compressor.ratio.value=SPEECH_ENHANCEMENT.compressorRatio;
    compressor.attack.value=SPEECH_ENHANCEMENT.compressorAttack;
    compressor.release.value=SPEECH_ENHANCEMENT.compressorRelease;

    const destination=context.createMediaStreamDestination();

    source.connect(denoiser);
    denoiser.connect(highpass);
    highpass.connect(lowpass);
    lowpass.connect(gain);
    gain.connect(compressor);
    compressor.connect(destination);

    if(context.state==='suspended')await context.resume();

    return {
      stream:destination.stream,
      context,
      source,
      denoiser,
      highpass,
      lowpass,
      gain,
      compressor,
      destination,
      mode:'rnnoise-enhanced',
    };
  }catch(error){
    try{await context.close();}catch{}
    console.warn('[Orena Speaking] RNNoise unavailable; using native microphone processing.',error);
    return null;
  }
}

export function localAudioRecordingSupported({
  mediaDevices=globalThis.navigator?.mediaDevices,
  Recorder=globalThis.MediaRecorder,
}={}){
  return Boolean(mediaDevices?.getUserMedia&&typeof Recorder==='function');
}

export function createLocalAudioRecorder({
  mediaDevices=globalThis.navigator?.mediaDevices,
  Recorder=globalThis.MediaRecorder,
  URLApi=globalThis.URL,
  BlobCtor=globalThis.Blob,
  AudioContextCtor=globalThis.AudioContext||globalThis.webkitAudioContext,
}={}){
  let rawStream=null;
  let recordingStream=null;
  let processingPipeline=null;
  let recorder=null;
  let chunks=[];
  let recordingUrl=null;
  let recordingBlob=null;
  let recordingMimeType='';
  let status='idle';
  let error=null;
  let disposed=false;
  let inputSettings=null;
  let processingMode='none';

  const revoke=()=>{
    if(recordingUrl&&URLApi?.revokeObjectURL){
      try{URLApi.revokeObjectURL(recordingUrl);}catch{}
    }
    recordingUrl=null;
  };

  const shutdownCapture=async()=>{
    stopTracks(recordingStream);
    if(recordingStream!==rawStream)stopTracks(rawStream);
    recordingStream=null;
    rawStream=null;

    if(processingPipeline){
      try{processingPipeline.source?.disconnect?.();}catch{}
      try{processingPipeline.denoiser?.disconnect?.();}catch{}
      try{processingPipeline.highpass?.disconnect?.();}catch{}
      try{processingPipeline.lowpass?.disconnect?.();}catch{}
      try{processingPipeline.gain?.disconnect?.();}catch{}
      try{processingPipeline.compressor?.disconnect?.();}catch{}
      try{processingPipeline.denoiser?.destroy?.();}catch{}
      try{await processingPipeline.context?.close?.();}catch{}
    }
    processingPipeline=null;
  };

  const snapshot=()=>({
    status,
    error,
    url:recordingUrl,
    blob:recordingBlob,
    mime_type:recordingMimeType,
    size:recordingBlob?.size||0,
    supported:localAudioRecordingSupported({mediaDevices,Recorder}),
    input_settings:inputSettings,
    processing_mode:processingMode,
    enhancement:SPEECH_ENHANCEMENT,
  });

  async function start(){
    if(status==='recording')return false;

    revoke();
    recordingBlob=null;
    recordingMimeType='';
    chunks=[];
    error=null;
    disposed=false;
    inputSettings=null;
    processingMode='none';

    if(!localAudioRecordingSupported({mediaDevices,Recorder})){
      status='unsupported';
      error='recording_unsupported';
      return false;
    }

    try{
      rawStream=await mediaDevices.getUserMedia({
        audio:SPEECH_AUDIO_CONSTRAINTS,
      });
      if(disposed){await shutdownCapture();return false;}

      const audioTrack=rawStream.getAudioTracks?.()[0];
      inputSettings=audioTrack?.getSettings?.()||null;

      processingPipeline=await buildRnnoisePipeline(rawStream,{AudioContextCtor});
      if(disposed){await shutdownCapture();return false;}
      if(processingPipeline){
        recordingStream=processingPipeline.stream;
        processingMode=processingPipeline.mode;
      }else{
        recordingStream=rawStream;
        processingMode='native-fallback';
      }

      recorder=new Recorder(recordingStream);
      recorder.addEventListener('dataavailable',event=>{
        if(event?.data?.size>0)chunks.push(event.data);
      });
      recorder.start();
      status='recording';
      console.info('[Orena Speaking] microphone settings',inputSettings);
      console.info('[Orena Speaking] processing mode',processingMode);
      return true;
    }catch(captureError){
      await shutdownCapture();
      recorder=null;
      status='error';
      error='microphone_unavailable';
      console.warn('[Orena Speaking] microphone start failed',captureError);
      return false;
    }
  }

  async function stop(){
    if(status!=='recording'||!recorder)return null;
    const activeRecorder=recorder;

    return await new Promise(resolve=>{
      let settled=false;
      const finish=value=>{
        if(settled)return;
        settled=true;
        resolve(value);
      };

      activeRecorder.addEventListener('stop',async()=>{
        await shutdownCapture();
        recorder=null;

        if(disposed){
          chunks=[];
          status='idle';
          finish(null);
          return;
        }

        const mimeType=activeRecorder.mimeType||chunks[0]?.type||'audio/webm';
        try{
          const blob=new BlobCtor(chunks,{type:mimeType});
          chunks=[];
          if(!blob.size||!URLApi?.createObjectURL){
            status='error';
            error='recording_empty';
            finish(null);
            return;
          }

          recordingBlob=blob;
          recordingMimeType=mimeType;
          recordingUrl=URLApi.createObjectURL(blob);
          status='ready';
          error=null;

          finish({
            url:recordingUrl,
            blob:recordingBlob,
            mime_type:recordingMimeType,
            size:blob.size,
            processing_mode:processingMode,
            input_settings:inputSettings,
          });
        }catch{
          chunks=[];
          status='error';
          error='recording_failed';
          finish(null);
        }
      },{once:true});

      try{
        activeRecorder.stop();
      }catch{
        shutdownCapture().finally(()=>{
          recorder=null;
          chunks=[];
          status='error';
          error='recording_failed';
          finish(null);
        });
      }
    });
  }

  function discard(){
    if(status==='recording')return false;
    revoke();
    recordingBlob=null;
    recordingMimeType='';
    chunks=[];
    error=null;
    status='idle';
    inputSettings=null;
    processingMode='none';
    return true;
  }

  function cleanup(){
    disposed=true;
    if(status==='recording'&&recorder){
      try{recorder.stop();}catch{}
    }
    shutdownCapture();
    recorder=null;
    chunks=[];
    recordingBlob=null;
    recordingMimeType='';
    revoke();
    status='idle';
    inputSettings=null;
    processingMode='none';
    error=null;
  }

  return {start,stop,discard,cleanup,snapshot};
}
