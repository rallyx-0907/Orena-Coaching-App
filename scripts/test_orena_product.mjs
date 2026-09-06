import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {route, link, continuationLink, sourceLink, practiceIntentions} from '../static/orena/product/intent.js';
import {learnerMemory} from '../static/orena/product/memory.js';
import {encounter} from '../static/orena/product/encounter.js';
import {dictationEvidence, mergeListeningEvidence} from '../static/orena/product/evidence.js';
import {copy} from '../static/orena/ui/copy.js';

for (const retired of ['static/becoming', 'templates/becoming/index.html', 'templates/index.html', 'static/app.js', 'static/product-shell.js']) {
  assert.equal(existsSync(new URL('../'+retired, import.meta.url)), false, `Retired product restored: ${retired}`);
}
assert.deepEqual(Object.keys(copy.en).sort(), Object.keys(copy.zh).sort());
assert.ok(!Object.values(copy.zh).some(x=>/\?{3}/.test(x)), 'Chinese copy must not be damaged');
for (const intent of practiceIntentions) {
  assert.equal(route(link('practice',{intent})).intent, intent);
  assert.equal(route(link('encounter',{id:'media:a',intent})).intent, intent);
}
assert.equal(route(continuationLink({id:'expression:free',intent:'writing'})).page,'expression');
assert.equal(route(sourceLink('grammar:en_1')).page,'practice');
assert.equal(route(sourceLink('grammar:en_1')).id,'en_1');

const entries=new Map();
const storage={getItem:key=>entries.get(key)||null,setItem:(key,value)=>entries.set(key,value)};
const a=learnerMemory(storage,'owner-a','en');
const imported=a.add({title:'My own words',text:'A text I chose to bring.'});
a.write(imported.id,'My real response');a.keep(imported.id);
a.enter({id:'media:a',title:'A voice',segment:'two',source_url:'https://example.org/a'});
a.enter({id:'media:a',title:'A voice',intent:'writing'});
assert.equal(a.value.continuation[0].segment,'two');
assert.equal(learnerMemory(storage,'owner-a','en').value.expressions[imported.id],'My real response');
assert.equal(learnerMemory(storage,'owner-b','en').value.imports.length,0);
assert.equal(learnerMemory(storage,'owner-a','zh').value.imports.length,0);
assert.equal(imported.origin,'imported');
const unavailable=learnerMemory({getItem(){throw Error('blocked');},setItem(){throw Error('quota');}},'volatile','zh');
assert.equal(unavailable.write('draft','你好'),false);
assert.equal(unavailable.value.expressions.draft,'你好');

// Imported media is content the learner owns, held to the same owner and
// language scoping as imported text, and reachable from the same surfaces.
assert.equal(a.addMedia({id:'media:a',title:'Not an import'}),false,'Only url: identities are learner media imports');
assert.equal(a.value.mediaImports.length,0);
a.addMedia({id:'url:https://example.org/a',title:'A voice I brought',kind:'audio',duration_ms:61000});
a.addMedia({id:'url:https://example.org/a',title:'A voice I brought',kind:'audio',duration_ms:61000});
assert.equal(a.value.mediaImports.length,1,'Re-entering an import must not duplicate it');
assert.equal(a.value.mediaImports[0].origin,'imported');
assert.equal(learnerMemory(storage,'owner-a','en').value.mediaImports.length,1);
assert.equal(learnerMemory(storage,'owner-b','en').value.mediaImports.length,0);
assert.equal(learnerMemory(storage,'owner-a','zh').value.mediaImports.length,0);
a.remove('url:https://example.org/a');
assert.equal(learnerMemory(storage,'owner-a','en').value.mediaImports.length,0);
const world=readFileSync(new URL('../static/orena/ui/world.js',import.meta.url),'utf8');
assert.match(world,/practiceMedia[\s\S]{0,40}\.filter\(\(x\) => supports\(/,'Practice intents must offer imported media, not the catalog alone');

for (const language of ['en','zh']) {
  const text=language==='en'?'The train is here.':'火车来了。';
  const segments=[{segment_id:'one',start_ms:500,end_ms:2000,original_text:text},{segment_id:'two',start_ms:3000,end_ms:5000,original_text:text}];
  const payload={transcript:{segments},translations:[{segment_id:'one',target_language:'vi',translated_meaning:'one meaning'},{segment_id:'two',target_language:'vi',translated_meaning:'two meaning'},{segment_id:'two',target_language:'en',translated_meaning:'wrong support language'}]};
  const model=encounter(payload,'vi');
  assert.equal(model.follow(3100).segment_id,'two');assert.equal(model.meaning(),'two meaning');
  assert.equal(model.follow(2400),null);assert.equal(model.select('missing'),false);
  assert.equal(model.select('one'),true);assert.equal(model.meaning(),'one meaning');
  const evidence=dictationEvidence({asset:'source',segment:segments[0],language});
  evidence.reveal();assert.equal(evidence.value.checked_attempt_count,0);
  assert.equal(evidence.compare(text).result.exact,true);assert.equal(evidence.value.checked_attempt_count,1);
  const snapshot=evidence.value;evidence.compare(text);assert.equal(snapshot.checked_attempt_count,1);
}
const dialogue=dictationEvidence({asset:'dialogue',language:'zh',segment:{segment_id:'one',original_text:'欧文：你好。',spoken_text:'你好。'}});
assert.equal(dialogue.compare('你好').result.exact,true,'Unspoken speaker labels must not be graded');
// The server replaces a segment record wholesale, so practice that began
// without the stored copy must fold into it, never write over it.
const stored={revealed:true,checked_attempt_count:4,best_accuracy_percent:88,best_exact:true,last_answer:'earlier'};
const local={asset_id:'a',segment_id:'one',presentation:'checked',revealed:false,checked_attempt_count:1,best_accuracy_percent:40,best_exact:false,last_answer:'now'};
const merged=mergeListeningEvidence(stored,local);
assert.equal(merged.best_accuracy_percent,88,'A recovered write must never lower the stored best accuracy');
assert.equal(merged.checked_attempt_count,5,'Attempts made offline are added to the stored count');
assert.equal(merged.revealed,true,'A previously revealed line stays revealed');
assert.equal(merged.best_exact,true,'A previous exact match is not erased');
assert.equal(merged.last_answer,'now','The newest answer is the one worth keeping');
assert.equal(merged.asset_id,'a');assert.equal(merged.segment_id,'one');
assert.equal(mergeListeningEvidence({},local).best_accuracy_percent,40,'A genuinely empty record keeps the local result');
assert.equal(mergeListeningEvidence(null,local).best_accuracy_percent,40,'A missing record keeps the local result');
assert.equal(mergeListeningEvidence({best_accuracy_percent:null},{...local,best_accuracy_percent:null}).best_accuracy_percent,null,'Unmeasured stays unmeasured rather than becoming zero');
assert.equal(mergeListeningEvidence(stored,{...local,checked_attempt_count:999}).checked_attempt_count,1000,'The stored contract bound still holds');

// Contracts the encounter surface must keep. These are the regressions this
// layer has actually shipped, so they are worth naming rather than trusting.
const encounterSource=readFileSync(new URL('../static/orena/ui/encounter.js',import.meta.url),'utf8');
assert.match(encounterSource,/mergeListeningEvidence\(await readPrior\(\)/,'Dictation that began without the stored record must merge into it, never replace it');
assert.match(encounterSource,/playing \? 'gap' : lastClockSegment/,'A resting player is not "between spoken lines"; Follow must keep showing the current line');
assert.doesNotMatch(encounterSource,/memory\.write\(id, heard\)\s*;/,'A speech transcript must not overwrite writing the learner already has');
assert.match(encounterSource,/bindPronunciation\(\);[\s\S]{0,200}if \(intent === 'shadowing'\)/,'Take actions must be wired before the progress save is awaited');

const app=readFileSync(new URL('../static/orena/app.js',import.meta.url),'utf8');
assert.doesNotMatch(app,/applySkillNavigation|sharedMediaSession|ShadowingStudio/);
assert.match(app,/languages.support_languages/);
assert.match(app,/a\.skip[\s\S]{0,160}event\.preventDefault\(\)/,'Skip to content must move focus without rewriting the route');
assert.match(app,/if \(location\.hash === next\) render\(\)/,'Re-entering the route you are already on must still act');
console.log('Orena product boundary, intents, owned memory, EN/ZH meaning and truthful evidence: PASS');
