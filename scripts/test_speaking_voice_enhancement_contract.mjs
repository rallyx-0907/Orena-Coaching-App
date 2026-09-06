import fs from 'node:fs';
import assert from 'node:assert/strict';

const source=fs.readFileSync(
  new URL('../static/orena/capabilities/audio-recorder.js',import.meta.url),
  'utf8',
);

assert.match(source,/noiseSuppression:\{ideal:false\}/);
assert.match(source,/autoGainControl:\{ideal:false\}/);
assert.match(source,/echoCancellation:\{ideal:true\}/);
assert.match(source,/highpassHz:80/);
assert.match(source,/lowpassHz:9000/);
assert.match(source,/outputGain:2\.0/);
assert.match(source,/createBiquadFilter\(\)/);
assert.match(source,/createDynamicsCompressor\(\)/);
assert.match(source,/createGain\(\)/);
assert.match(source,/mode:'rnnoise-enhanced'/);
assert.match(source,/denoiser\.connect\(highpass\)/);
assert.match(source,/lowpass\.connect\(gain\)/);
assert.match(source,/gain\.connect\(compressor\)/);

console.log('Speaking voice enhancement contract: PASS');
