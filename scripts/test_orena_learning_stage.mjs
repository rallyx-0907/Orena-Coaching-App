/* The transcript stage preferences and microphone readiness.

   Source-level contracts that outlived the retired listening workspace: the three
   transcript display preferences are kept through the one shared module the Listening
   screen and the Settings Learning tab both use, and the microphone readiness check
   releases the device it opened and says what it may claim. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* --- The three preferences are kept in the shared module ---------------- */
const transcriptStage = read('static/orena/product/transcript-stage.js');
const listening = read('static/orena/screens/listening/screen.js');
assert.match(listening, /import \{ readStage, writeStage, transcriptDefaults \} from '\.\.\/\.\.\/product\/transcript-stage\.js'/,
  'the stage read/write is the shared preference module, not a second local implementation');
assert.match(listening, /writeStage\(\{ \.\.\.readStage\(\), autoscroll: autoScroll, meaning: showTrans, wordhl: wordHighlight \}\)/,
  'the three preferences are kept as the reader keeps its own');
assert.match(transcriptStage, /storage\.setItem\(STAGE_KEY/, 'which is where they are actually written');
assert.match(read('static/orena/screens/settings/screen.js'), /transcript-stage\.js/,
  'the Settings Learning tab reads and writes the same preferences');

/* --- Microphone readiness, and what it may claim ------------------------ */
const mic = read('static/orena/capabilities/mic-readiness.js');
assert.match(mic, /track\.stop\(\)/, 'the readiness check releases the device it opened');
assert.match(mic, /NotFoundError/, 'no device and refused permission are different answers');

console.log('Learning stage: shared transcript preferences and microphone readiness: PASS');
