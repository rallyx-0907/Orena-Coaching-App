import assert from 'node:assert/strict';
import {sourceFromLesson} from '../static/orena/product/speaking-source.js';
import {loadComparisonReference} from '../static/orena/product/compare-reference.js';
import {openMedia} from '../static/orena/product/media-source.js';

for (const language of ['en', 'zh']) {
  const playback={kind:'embed',provider:'youtube',url:'https://www.youtube-nocookie.com/embed/B0p5SdkBydU'};
  const payload={asset:{asset_id:'prepared',source_language:language},playback,
    transcript:{segments:[{segment_id:'line-2',original_text:language==='zh'?'你好':'Hello',start_ms:7000,end_ms:9000}]},
    catalog:{pinyin_by_segment:{'line-2':'nǐ hǎo'}}};
  const source=sourceFromLesson('prepared',payload,'line-2','vi');
  let providerCalls=0;
  const forbidden=async()=>{providerCalls++;throw Error('workspace attempted source preparation');};
  const options={api:{speakingModelReference:forbidden,wordDetail:async()=>({}),annotateMediaText:forbidden},fetchImpl:forbidden};
  await loadComparisonReference(source,options);
  await loadComparisonReference(source,options);
  assert.equal(providerCalls,0,`${language}: opening/reopening ready media never executes source work`);
  assert.deepEqual(source.playback,playback,'Hear model keeps the canonical media playback');
  assert.equal(source.line.startMs,7000);
  assert.equal(source.line.lineId,'line-2');
  const readOnlyApi={prepareMedia:forbidden,importMedia:forbidden,
    mediaSource:async(url,target)=>{assert.equal(target,'vi');return payload;}};
  assert.equal(await openMedia('url:https://youtu.be/B0p5SdkBydU',{api:readOnlyApi,support:'vi',language}),payload);
  assert.equal(providerCalls,0,'old URL membership resolves a stored item rather than importing it again');
  assert.equal(source.line.modelClipUrl,'','no prepared clip: the line names no clip to read');

  /* D-140: a clip prepared at content readiness is the ONE thing a reference may read; opening and reopening
     fetches only that stored artifact and never calls source preparation. */
  const preparedPayload={...payload,catalog:{...payload.catalog,model_clip_segments:['line-2']}};
  const withClip=sourceFromLesson('prepared',preparedPayload,'line-2','vi');
  assert.equal(withClip.line.modelClipUrl,'/api/speaking/model-clip/prepared/line-2');
  const fetched=[];
  const clipOptions={api:options.api,fetchImpl:async url=>{fetched.push(url);return {ok:true,blob:async()=>new Blob(['clip'])};},
    decode:async()=>({duration:2}),analyse:()=>({duration:2,contour:[]})};
  await loadComparisonReference(withClip,clipOptions);
  await loadComparisonReference(withClip,clipOptions);
  assert.deepEqual(fetched,['/api/speaking/model-clip/prepared/line-2','/api/speaking/model-clip/prepared/line-2'],`${language}: only the prepared artifact is read`);
  assert.equal(providerCalls,0,`${language}: reading the prepared clip never executes source preparation`);
  const other=sourceFromLesson('prepared',{...preparedPayload,transcript:{segments:[...payload.transcript.segments,{segment_id:'line-3',original_text:'x',start_ms:9000,end_ms:10000}]}},'line-3','vi');
  assert.equal(other.line.modelClipUrl,'','a line the lesson does not list as prepared reads nothing');
}
const punctuated={asset:{source_language:'zh'},playback:{kind:'audio',provider:'orena',url:'/api/media/files/media/a/original.wav'},
  transcript:{segments:[{segment_id:'s',original_text:'你...好',start_ms:0,end_ms:1000}]},
  catalog:{pinyin_by_segment:{s:'nǐ ... hǎo'},pinyin_chars_by_segment:{s:[{char:'你',pinyin:'nǐ'},{char:'好',pinyin:'hǎo'}]}}};
const punctuatedSource=sourceFromLesson('a',punctuated,'s');
const reading=await loadComparisonReference(punctuatedSource);
assert.equal(reading.positionReadings.length,2,'reuse persisted character readings despite transcript punctuation');
const {originalSegmentPlayer}=await import('../static/orena/product/original-segment-player.js');
{
  const listeners=new Map();
  const frame={src:'https://www.youtube-nocookie.com/embed/B0p5SdkBydU',contentWindow:{postMessage(){}}};
  const root={dataset:{mediaClock:'ready'},addEventListener:(name,fn)=>listeners.set(name,fn),querySelector:()=>frame};
  const player=originalSegmentPlayer({hasModelAudio:true,title:'Prepared',playback:{kind:'embed',provider:'youtube',url:frame.src},line:{startMs:5000,endMs:10000}},{documentImpl:{createElement:()=>root}});
  let finished=false;
  const play=player.play().then(()=>{finished=true;});
  const clock=detail=>listeners.get('orena:media-time')({detail});
  clock({time_ms:10000,player_state:2}); // asynchronous seek still reports the previous paused endpoint
  await Promise.resolve();
  assert.equal(finished,false,'a stale pre-seek endpoint must not finish the new model playback');
  clock({time_ms:5000,player_state:1});
  clock({time_ms:10000,player_state:2});
  await play;
  assert.equal(finished,true);
  player.stop();
}
const fakeRoot={dataset:{},addEventListener(){}};
const videoSource={...punctuatedSource,playback:{kind:'video',provider:'orena',url:'/api/media/files/media/a/original.mp4'}};
const video=originalSegmentPlayer(videoSource,{documentImpl:{createElement:()=>fakeRoot}});
assert.match(video.root.innerHTML,/<video/,'stored video keeps its canonical media element');
assert.equal(video.root.hidden,true);
const englishPrepared={...videoSource,language:'en',line:{...videoSource.line,text:'Hello',reading:'',positionReadings:[{text:'Hello',start:0,end:5,reading:'/həˈləʊ/'}]}};
assert.equal((await loadComparisonReference(englishPrepared)).positionReadings[0].reading,'/həˈləʊ/');
const {loadSpeakingSource}=await import('../static/orena/product/speaking-source.js');
await assert.rejects(loadSpeakingSource('media:not-ready',{api:{listeningLibraryLesson:async()=>({...punctuated,playback:null})},language:'zh'}),/speaking_lesson_unavailable/,'deep links cannot open a capability without original playback');
console.log('Content readiness EN/ZH: canonical segment + zero source preparation on reopen: PASS');
