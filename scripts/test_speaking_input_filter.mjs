import fs from 'node:fs';
import assert from 'node:assert/strict';

const source=fs.readFileSync(
  new URL('../static/orena/capabilities/audio-recorder.js',import.meta.url),
  'utf8'
);

// Keep the microphone signal raw for the optional RNNoise pipeline. Asking
// the browser for a second noise gate or auto-gain stage would make the
// enhanced and native-fallback paths behave differently.
assert.match(source,/noiseSuppression:\{ideal:false\}/);
assert.match(source,/echoCancellation:\{ideal:true\}/);
assert.match(source,/autoGainControl:\{ideal:false\}/);
assert.match(source,/channelCount:\{ideal:1\}/);
assert.match(source,/getSettings\?\.\(\)/);
assert.match(source,/input_settings:inputSettings/);

console.log('Speaking input audio filter contract: PASS');
