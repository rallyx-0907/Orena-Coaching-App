import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { byId } from '../static/orena/shell/routes.js';
import { sourceFromLesson, segmentOf } from '../static/orena/product/speaking-source.js';
import { mapLesson } from '../static/orena/screens/listening/model.js';
assert.equal(byId('shadow').screen,'compare','old Shadowing links open the unified recorder/comparison');
assert.equal(byId('speak').screen,'compare','Pronunciation uses the same runtime');
assert.equal(segmentOf(new URLSearchParams('seg=line-2')),'line-2','old links preserve their selected line');
for (const language of ['en','zh']) {
  const payload=JSON.parse(readFileSync(new URL(`./fixtures/api/listening_library_lesson.${language}.json`,import.meta.url)));
  payload.catalog.available_modes=['listen'];
  const first=payload.transcript.segments[0];
  payload.translations=[{segment_id:first.segment_id,target_language:'vi',translated_meaning:'Nghĩa hỗ trợ'}];
  const source=sourceFromLesson('actual-media',payload,'','vi');
  assert.equal(source.lines.length,payload.transcript.segments.length);
  assert.equal(source.line.meaning,'Nghĩa hỗ trợ');
  assert.equal(sourceFromLesson('regional-media',{...payload,asset:{...payload.asset,source_language:language==='zh'?'zh-CN':'en-GB'}}).language,language,'regional provider tags retain the same learning-language scope');
  assert.equal(mapLesson(payload).modes.shadowing,true,'usable media is not restricted to a separate Speaking catalogue');
  const youtube={...payload,playback:{kind:'embed',provider:'youtube',url:'https://www.youtube-nocookie.com/embed/B0p5SdkBydU'}};
  assert.equal(mapLesson(youtube).modes.shadowing,true,'transcript-backed YouTube imports enter shared practice');
  assert.equal(sourceFromLesson('youtube-media',youtube).hasModelAudio,true,'YouTube uses the real model-audio endpoint');
  const unsafe={...youtube,playback:{...youtube.playback,url:'https://untrusted.example/embed/B0p5SdkBydU'}};
  assert.equal(mapLesson(unsafe).modes.shadowing,false,'an unsupported embed is not advertised as usable practice');
  assert.equal(sourceFromLesson('actual-media',payload,'removed-line','vi'),null,'never silently reopen a different sentence');
  assert.equal(mapLesson({...payload,transcript:{segments:[]}}).modes.shadowing,false);
}
console.log('Unified media Speaking: same runtime, any usable media, exact lines, support meanings, honest transcript gate: PASS');
