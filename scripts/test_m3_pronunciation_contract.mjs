import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const api=readFileSync(new URL('../static/orena/infrastructure/api.js',import.meta.url),'utf8');
const speaking=readFileSync(new URL('../static/orena/ui/encounter.js',import.meta.url),'utf8');
const speechApi=readFileSync(new URL('../writing_coach/speech_api.py',import.meta.url),'utf8');
const provider=readFileSync(new URL('../writing_coach/speech_pronunciation.py',import.meta.url),'utf8');
const dockerfile=readFileSync(new URL('../Dockerfile',import.meta.url),'utf8');

assert.match(api,/assessPronunciation:/);
assert.match(speaking,/api\.assessPronunciation/);
assert.match(speaking,/voiceMeasureNote/);
assert.match(api,/\/api\/speech\/pronunciation/);
assert.match(speechApi,/@router\.post\("\/pronunciation"\)/);
assert.match(provider,/class AzureSpeechPronunciationProvider/);
assert.match(provider,/Pronunciation-Assessment/);
assert.match(provider,/pcm_s16le/);
assert.match(provider,/zh-CN/);
assert.match(provider,/en-US/);
assert.match(provider,/class DemoPronunciationProvider/);
assert.match(provider,/synthetic_demo/);
assert.match(provider,/PRONUNCIATION_PROVIDER/);
assert.match(provider,/AZURE_PRONUNCIATION_ENABLE_PROSODY/);
assert.match(dockerfile,/ffmpeg/);
for(const forbidden of ['fetch(','XMLHttpRequest']){
  assert.equal(speaking.includes(forbidden),false,`Speaking bypassed API boundary: ${forbidden}`);
}
console.log('M3 Pronunciation Scoring contracts: PASS');
