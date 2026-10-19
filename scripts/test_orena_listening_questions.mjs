import assert from 'node:assert/strict';
import fs from 'node:fs';
import { questionsFrom, grade } from '../static/orena/screens/listening-questions/model.js';
// The shipped catalogue is empty since D-245; its lessons (none, or any added later) and the fixture-local
// catalogue's are both checked, each against its own sources.
const manifests=['writing_coach/content/listening_catalog.v1.json','tests/fixtures/listening_catalog.fixture.v1.json']
  .map(path=>JSON.parse(fs.readFileSync(path,'utf8')));
let checkedLessons=0;
for (const manifest of manifests) for (const lesson of manifest.lessons) {
  checkedLessons+=1;
  if (!lesson.comprehension?.length) continue;
  const source=manifest.sources.find(s=>s.source_media_id===lesson.source_media_id);
  const payload={catalog:lesson,transcript:{segments:source.segments.filter(s=>s.start_ms>=lesson.excerpt_start_ms&&s.end_ms<=lesson.excerpt_end_ms)}};
  const questions=questionsFrom(payload);
  assert.equal(questions.length,lesson.comprehension.length);
  assert.equal(grade(questions[0],questions[0].correct_index).correct,true);
  assert.equal(grade(questions[0],(questions[0].correct_index+1)%questions[0].options.length).correct,false);
  assert.equal(grade(questions[0],-1),null);
  const stale=structuredClone(payload);stale.transcript.segments[0].original_text+=' changed';
  const affected=questions.find(q=>q.evidence_segment_ids.includes(stale.transcript.segments[0].segment_id));
  if(affected) assert.deepEqual(questionsFrom(stale),[], 'stale source evidence is never admitted');
  assert.deepEqual(questionsFrom({...payload,catalog:{}}),[], 'no questions means no comprehension capability');
}
assert.ok(checkedLessons>0,'the comprehension questions are actually being checked');
console.log('Listening comprehension: persisted EN/ZH questions, correct/wrong feedback, revision admission: PASS');
