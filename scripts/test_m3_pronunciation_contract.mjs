import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const api=readFileSync(new URL('../static/orena/infrastructure/api.js',import.meta.url),'utf8');
const speaking=readFileSync(new URL('../static/orena/ui/encounter.js',import.meta.url),'utf8');
const speechApi=readFileSync(new URL('../writing_coach/speech_api.py',import.meta.url),'utf8');
const provider=readFileSync(new URL('../writing_coach/speech_pronunciation.py',import.meta.url),'utf8');
const dockerfile=readFileSync(new URL('../Dockerfile',import.meta.url),'utf8');

assert.match(api,/assessPronunciation:/);
assert.match(speaking,/api\.assessPronunciation/);
/* The report is one shared renderer, and it draws a measurement only when the
   provider actually measured something. A recogniser transcript, a similarity
   percentage, or the demo provider's confident-looking values are not a
   pronunciation score and must never be rendered as one. */
const report=readFileSync(new URL('../static/orena/ui/pronunciation-report.js',import.meta.url),'utf8');
assert.match(speaking,/pronunciationReportHtml\(/);
assert.match(report,/voiceMeasureNote/);
assert.match(report,/score_kind !== 'measured'/,'anything not a measurement is refused');
assert.match(report,/speakDemoAssessment/,'the demo provider gets an honest line, not numbers');
assert.match(report,/speakNoAssessment/);
const { isRealMeasurement, pronunciationReportHtml } = await import('../static/orena/ui/pronunciation-report.js');
const { copy } = await import('../static/orena/ui/copy.js');
const demo={provider:'demo-synthetic',score_kind:'synthetic_demo',accuracy_score:74,fluency_score:78,completeness_score:100,words:[{word:'hello',accuracy_score:84,error_type:'SyntheticDemo'}]};
assert.equal(isRealMeasurement(demo),false,'a synthetic demo result is not a measurement');
const demoHtml=pronunciationReportHtml(copy.en,demo,'en');
for(const digits of ['74','78','84','100'])
  assert.equal(demoHtml.includes(digits),false,`demo values must not be rendered: ${digits}`);
assert.match(demoHtml,new RegExp(copy.en.speakDemoAssessment.slice(0,20)));
const measured={score_kind:'measured',accuracy_score:82,fluency_score:71,prosody_score:null,words:[{word:'raining',accuracy_score:52,error_type:'Mispronunciation',phonemes:[{phoneme:'ŋ',accuracy_score:31}]},{word:'the',accuracy_score:96,error_type:'None'}]};
assert.equal(isRealMeasurement(measured),true);
const realHtml=pronunciationReportHtml(copy.en,measured,'en');
assert.match(realHtml,/82/);
assert.match(realHtml,/71/);
assert.equal(realHtml.includes(copy.en.prosody),false,'a dimension the provider did not measure is not drawn');
assert.match(realHtml,/raining/,'the words worth working on are named');
assert.match(realHtml,/ŋ/,'with the phoneme evidence the provider gave');
assert.equal(realHtml.includes('>the<'),false,'a word that was fine is not listed as a problem');
assert.equal(isRealMeasurement({recognized_text:'hello'}),false,'a recogniser transcript is not a score');
assert.equal(isRealMeasurement(null),false);
for(const ui of ['en','zh'])
  for(const key of ['speakNoAssessment','speakDemoAssessment','completeness','prosody'])
    assert.ok(copy[ui][key]?.trim(),`${ui}.${key} is localized`);
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
