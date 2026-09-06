import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {route, link, continuationLink, sourceLink, practiceIntentions} from '../static/orena/product/intent.js';
import {learnerMemory} from '../static/orena/product/memory.js';
import {encounter} from '../static/orena/product/encounter.js';
import {dictationEvidence} from '../static/orena/product/evidence.js';
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
const app=readFileSync(new URL('../static/orena/app.js',import.meta.url),'utf8');
assert.doesNotMatch(app,/applySkillNavigation|sharedMediaSession|ShadowingStudio/);
assert.match(app,/languages.support_languages/);
console.log('Orena product boundary, intents, owned memory, EN/ZH meaning and truthful evidence: PASS');
