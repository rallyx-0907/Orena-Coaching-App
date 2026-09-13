import fs from 'node:fs';
import assert from 'node:assert/strict';

const recorder=fs.readFileSync(
  new URL('../static/orena/capabilities/audio-recorder.js',import.meta.url),
  'utf8',
);

assert.match(recorder,/loadRnnoise,RnnoiseWorkletNode/);
assert.match(recorder,/sampleRate:48000/);
assert.match(recorder,/audioWorklet\.addModule/);
assert.match(recorder,/createMediaStreamDestination/);
assert.match(recorder,/mode:'rnnoise-enhanced'/);
assert.match(recorder,/processingMode=processingPipeline\.mode/);
assert.match(recorder,/processing_mode:processingMode/);

console.log('Speaking RNNoise denoiser source contract: PASS');
