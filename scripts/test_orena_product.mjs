import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {route, link, continuationLink, sourceLink, practiceIntentions, deeperPractice, supports} from '../static/orena/product/intent.js';
import {learnerMemory} from '../static/orena/product/memory.js';
import {encounter} from '../static/orena/product/encounter.js';
import {dictationEvidence, mergeListeningEvidence} from '../static/orena/product/evidence.js';

for (const retired of ['static/becoming', 'templates/becoming/index.html', 'templates/index.html', 'static/app.js', 'static/product-shell.js']) {
  assert.equal(existsSync(new URL('../'+retired, import.meta.url)), false, `Retired product restored: ${retired}`);
}
for (const intent of practiceIntentions) {
  assert.equal(route(link('practice',{intent})).intent, intent);
  assert.equal(route(link('encounter',{id:'media:a',intent})).intent, intent);
}
assert.equal(route(continuationLink({id:'expression:free',intent:'writing'})).page,'expression');
/* Every origin a learner can keep from resolves back to the thing itself, with
   its work reference intact. An origin that cannot be reopened must not be
   answered with a room the learner was never in. */
assert.equal(route(sourceLink('expression:free')).page,'expression');
assert.equal(route(sourceLink('expression:free')).id,'expression:free');
assert.equal(route(sourceLink('story:last-train')).page,'encounter');
assert.equal(route(sourceLink('media:x')).page,'encounter');
assert.equal(route(sourceLink('conversation:abc')).page,'conversation');
assert.equal(route(sourceLink('conversation:abc')).id,'conversation:abc');
assert.equal(route(sourceLink('voice:invitation')).intent,'speaking');
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

// A draft is overwritten as the learner types, so without this the version
// they revised from is destroyed by revising. Revisions record what was sent
// for review, never a keystroke.
a.recordRevision('expression:free',{text:'First try.',essay_id:1,revision_no:1,overall:62,level:'B1'});
a.recordRevision('expression:free',{text:'First try.',essay_id:1,revision_no:1,overall:62,level:'B1'});
a.recordRevision('expression:free',{text:'Second, better try.',essay_id:2,revision_no:2,overall:74,level:'B1'});
const kept=learnerMemory(storage,'owner-a','en').value.revisions['expression:free'];
assert.equal(kept.length,2,'reviewing the same words twice is one revision');
assert.deepEqual(kept.map(x=>x.revision_no),[1,2],'order is the learner history');
assert.equal(kept[0].text,'First try.','the earlier text survives the later one');
assert.equal(kept[1].overall,74);
assert.equal(a.recordRevision('expression:free',{text:'   '}),false,'nothing is not a version');
assert.equal(a.recordRevision('__proto__',{text:'x'}),false,'prototype keys stay rejected');
assert.equal(learnerMemory(storage,'owner-b','en').value.revisions['expression:free'],undefined,'revisions are owner-scoped');
assert.equal(learnerMemory(storage,'owner-a','zh').value.revisions['expression:free'],undefined,'revisions are language-scoped');
// The Writing screen records a version when a draft is sent for review, never on a keystroke.
const writingSource=readFileSync(new URL('../static/orena/screens/writing/screen.js',import.meta.url),'utf8');
assert.match(writingSource,/memory\.recordRevision\(nextKey, \{\s*text,/,'a reviewed draft is recorded as a version');
assert.doesNotMatch(writingSource,/oninput[\s\S]{0,200}recordRevision/,'typing is not a version');

// Listening must not collapse into Dictation. Following a piece of media to its
// end is an intention of its own, and it is the one intention that opens
// nothing over the moment.
assert.equal(practiceIntentions[0],'follow','following the voice leads the intentions');
assert.ok(!deeperPractice.includes('follow'),'Follow opens no practice panel');
assert.deepEqual(deeperPractice,['dictation','shadowing','speaking'],'only these open over the moment');
assert.equal(route(link('practice',{intent:'follow'})).intent,'follow');
assert.equal(supports({kind:'audio'},'follow'),true,'a voice can be followed');
assert.equal(supports({kind:'text'},'follow'),false,'a text is read, not followed');
// A take's result is drawn and its actions live before anything is saved, and saving is never awaited by them.
const speakingTake=readFileSync(new URL('../static/orena/capabilities/speaking-take.js',import.meta.url),'utf8');
assert.match(speakingTake,/set\(\{ phase: TAKE\.RESULT, result \}\);\s*if \(keep\) void remember\(result, mine\);/,'Take actions must be wired before the progress save is awaited');

// Plan/usage (ORENA_COMMERCE_ARCHITECTURE.md section 2, 4): read-only, additive to the frozen mobile /me
// contract, no enforcement, no provider identifier. Profile and Settings both read it.
// Settings' plan rows moved to Plan & usage when its tab became Privacy (D-153).
for (const screen of ['profile','plan']) {
  const source=readFileSync(new URL(`../static/orena/screens/${screen}/screen.js`,import.meta.url),'utf8');
  assert.match(source,/api\.productCommerce\(\)\.catch\(/,`${screen}: a failed plan/usage read must never block the screen`);
  assert.doesNotMatch(source,/api\.productMe\(\)/,`${screen}: the web client reads the web-only canonical endpoint, not the frozen mobile one`);
  assert.doesNotMatch(source,/external_customer_id|external_subscription_id/,`${screen}: no provider/customer identifier may reach a learner-facing template`);
}
console.log('Orena product boundary, intents, owned memory, EN/ZH meaning and truthful evidence: PASS');
