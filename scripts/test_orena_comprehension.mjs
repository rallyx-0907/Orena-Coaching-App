/* The reading check's server contract.
 *
 * "Reading · comprehension question" answers each question straight away - the verdict, the lines
 * in the passage that settle it, why - so a verdict must exist per question, which means the server
 * scores one answer as the learner gives it. The attempt - the whole set - is still written once,
 * so a learner's record means what it always meant. (The check's screens are
 * test_orena_screen_check.mjs and test_orena_listening_questions*.mjs.)
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const api = at('static/orena/infrastructure/api.js');
const server = at('writing_coach/persistence/reading_evidence_repository.py');
const routes = at('writing_coach/reading_practice_api.py');

/* --- One question, answered as it is answered ---------------------------- */

assert.match(server, /def grade_question\(self, set_id: str, question_id: str, selected_index: int,/,
  'the server can score one question');
assert.match(routes, /class QuestionChoiceBody\(BaseModel\):/, 'with its own payload');
assert.match(routes, /selected_index: int = Field\(ge=0, le=5\)/, 'an option index, bounded like the set');
assert.match(routes, /@router\.post\("\/sets\/\{set_id\}\/questions\/\{question_id\}\/grade"\)/,
  'and a route of its own beside the set');
/* Grading one question records nothing: the attempt is the set. */
const grading = server.slice(server.indexOf('    def grade_question('), server.indexOf('    def answer_key('));
assert.ok(!grading.includes('insert('), 'scoring one question writes no attempt');
assert.match(grading, /"correct": selected_index == question\.correct_index/, 'the canonical question supplies the verdict');
assert.match(api, /gradeReadingPracticeQuestion:\(setId,questionId,selectedIndex\)=>request/, 'the client can ask for one');

console.log('test_orena_comprehension.mjs: the server scores one question and writes the attempt once');
