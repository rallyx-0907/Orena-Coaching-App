/* iOS risk (P0 QA): word recordings from Wikimedia Commons are Ogg, which iOS Safari may not play. Every surface that
   plays a word asks kit/audio-support.js first and, when the device cannot play the recording, uses the device's own
   voice (kit/device-voice.js), labelled as the device's - the fallback #449 already takes. No browser: a stub audio
   element answers canPlayType like iOS Safari (no Ogg) and like Chrome (Ogg). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { canPlayAudio, mediaTypeOf } = await import('../static/orena/kit/audio-support.js');

const safari = () => ({ canPlayType: (type) => (/ogg/.test(type) ? '' : /mpeg|mp4|aac|wav/.test(type) ? 'maybe' : '') });
const chrome = () => ({ canPlayType: (type) => (/vorbis|opus|mpeg|mp4|wav|webm/.test(type) ? 'probably' : '') });
const asked = [];
const recorder = () => ({ canPlayType: (type) => { asked.push(type); return ''; } });

assert.equal(mediaTypeOf('/api/library/audio/abc.ogg'), 'audio/ogg');
assert.equal(mediaTypeOf('/x/En-us-harbour.mp3?v=1'), 'audio/mpeg');
assert.equal(mediaTypeOf('/x/a.ogg', 'audio/mpeg'), 'audio/mpeg', 'the payload media type wins over the extension');
assert.equal(mediaTypeOf('/api/library/audio/digest'), '');

/* iOS Safari: no Ogg -> not playable; MP3 / M4A are. Chrome plays Ogg. */
assert.equal(canPlayAudio('/api/library/audio/k.ogg', 'audio/ogg', safari), false);
assert.equal(canPlayAudio('/api/library/audio/k', 'audio/ogg', safari), false);
assert.equal(canPlayAudio('/a.mp3', '', safari), true);
assert.equal(canPlayAudio('/a.m4a', 'audio/mp4', safari), true);
assert.equal(canPlayAudio('/api/library/audio/k.ogg', 'audio/ogg', chrome), true);
/* Ogg is asked with its codecs (Vorbis, Opus): "audio/ogg" alone can say "maybe" without a decoder. */
canPlayAudio('/k.ogg', 'audio/ogg', recorder);
assert.deepEqual(asked, ['audio/ogg; codecs="vorbis"', 'audio/ogg; codecs="opus"']);
/* Nothing to ask, or no type: the browser is left to try. */
assert.equal(canPlayAudio('/api/library/audio/digest', '', safari), true);
assert.equal(canPlayAudio('/k.ogg', 'audio/ogg', () => null), true);
assert.equal(canPlayAudio('/k.ogg', 'audio/ogg', () => ({ canPlayType: () => { throw new Error('x'); } })), false);

/* Every place a word recording is played checks first and falls back to the device voice. */
const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const sheet = read('screens/quick-sheet/sheet.js');
assert.match(sheet, /if \(canPlayAudio\(card\.audioUrl\)\) playUrl\(card\.audioUrl[^\n]*\n\s*else onDevice\(\);/);
assert.match(sheet, /result\.url && !canPlayAudio\(result\.url, result\.mediaType\)\) \{\n\s*onDevice\(\);/);
assert.match(sheet, /const onDevice = \(\) => \{\n\s*if \(speakOnDevice\(target, lang\)\) audioAttribution = t\('sourceDevice'\);/);
assert.match(read('screens/word/screen.js'), /audioInfo\.url && !canPlayAudio\(audioInfo\.url, audioInfo\.mediaType\)\) onDevice\(\);/);
assert.match(read('screens/feed/screen.js'), /info\.url && !canPlayAudio\(info\.url, info\.mediaType\)\) \{\n\s*toast\(t\(speakOnDevice\(card\.word, language\) \? 'sourceDevice' : 'noAudio'\)\);/);
const feedCopy = read('screens/feed/copy.js');
for (const words of ['Your device’s voice', 'Giọng của thiết bị', '设备语音']) {
  assert.ok(feedCopy.includes(`sourceDevice: '${words}'`), `the device voice is labelled: ${words}`);
}

console.log('Word audio format: Ogg the device cannot play falls back to the device voice, on every surface: PASS');
