import assert from 'node:assert/strict';
import fs from 'node:fs';
import { questionsFrom, grade } from '../static/orena/screens/listening-questions/model.js';
const manifest=JSON.parse(fs.readFileSync('writing_coach/content/listening_catalog.v1.json','utf8'));
for (const lesson of manifest.lessons) {
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
console.log('Listening comprehension: persisted EN/ZH questions, correct/wrong feedback, revision admission: PASS');
