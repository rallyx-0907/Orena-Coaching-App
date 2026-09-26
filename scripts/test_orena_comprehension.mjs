/* The reading check as its frames draw it (canonical frames 11-12).
 *
 * "Reading · comprehension question" is one question with plain option cards,
 * a quiet line saying it can be skipped, and one button: "Trả lời".
 * "Reading · comprehension result" answers it straight away - the verdict, the
 * lines in the passage that settle it, why - and only then offers the next
 * question. So a verdict must exist per question, which means the server
 * scores one answer as the learner gives it.
 *
 * The attempt - the whole set - is still written once, so a learner's record
 * means what it always meant.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const ui = at('static/orena/ui/comprehension.js');
const api = at('static/orena/infrastructure/api.js');
const server = at('writing_coach/persistence/reading_evidence_repository.py');
const routes = at('writing_coach/reading_practice_api.py');
const css = at('static/orena/rooms.css');
const encounter = at('static/orena/ui/encounter.js');
const { copy } = await import('../static/orena/ui/copy.js');

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

assert.match(ui, /const scored = await practice\.grade\(questions\[index\]\.id, answers\[index\]\);/,
  'answering asks the server, never the client');
assert.match(ui, /if \(recorded\) return true;/,
  'and the attempt is written once, when the learner has been through the set');
assert.match(ui, /await ctx\.mutate\(\(\) => practice\.submit\(answers\)\);/, 'through canonical Reading evidence');

/* --- What the frames draw ------------------------------------------------ */

assert.match(ui, /class="quiz-skip">\$\{esc\(c\.quizSkip\)\}/, 'the line that says it can be skipped');
assert.match(ui, /data-quiz-answer/, 'and the one button that answers');
assert.match(ui, /class="quiz-verdict" data-tone="right">\$\{icon\('check-circle', \{ filled: true, size: 24 \}\)\}/,
  'the verdict is a filled mark at the frame’s size');
assert.match(ui, /data-tone="wrong">\$\{icon\('x-circle'/, 'both ways');
assert.match(ui, /c\.quizEvidenceLabel/, 'the label over the lines that settle it');
assert.match(ui, /highlighted\(passage, fragment\)/, 'quoted in the paragraph they stand in, with the words marked');
assert.match(ui, /data-quiz-look/, 'a way back into the text');
assert.match(ui, /data-quiz-discuss/, 'and into the discussion');
assert.match(encounter, /onDiscuss: \(\) => openDiscussion\(\),/, 'which is the discussion the reader already has');
assert.match(encounter, /passageOfEvidence: \(fragment\) =>/, 'the paragraph comes from the text the learner just read');

/* Deleted, because the frames draw none of it (rule 44). */
for (const gone of ['quiz-rail', 'quiz-invite', 'quiz-score', 'quiz-option__letter', 'quiz-type', 'data-quiz-start', 'quizYourAnswer', 'quiz-answer__where'])
  assert.ok(!ui.includes(gone), `${gone} is gone from the check`);
for (const gone of ['.quiz-rail', '.quiz-invite', '.quiz-score', '.quiz-option__letter', '.quiz-type'])
  assert.ok(!css.includes(gone), `${gone} is gone from the stylesheet`);
for (const gone of ['quizQuestions', 'quizMultipleChoice', 'quizYourAnswer', 'comprehensionScore', 'comprehensionClaim', 'comprehensionOptional', 'quizFromParagraph'])
  for (const pack of ['en', 'zh'])
    assert.ok(!(gone in copy[pack]), `${gone} went with it (${pack})`);

/* --- The frame's sizes --------------------------------------------------- */

for (const [what, rule] of [
  ['the question', /\.quiz-question \{[^}]*font-size: 25px;\n  font-weight: var\(--weight-heavy\);\n  line-height: 1\.3;\n  letter-spacing: -0\.02em;/s],
  ['an option', /\.quiz-option \{[^}]*padding: 17px 18px;\n  border: 0;\n  border-radius: 15px;/s],
  ['the verdict', /\.quiz-verdict \{[^}]*padding: 15px 17px;\n  border-radius: 15px;/s],
  ['the evidence', /\.quiz \.quiz-evidence__text \{[^}]*font-size: 16\.5px;\n  line-height: 1\.8;/s],
  ['a quiet action', /\.quiz-quiet \{[^}]*block-size: 50px;/s],
  ['the primary', /\.quiz-primary\.primary \{[^}]*block-size: 54px;[^}]*border-radius: 15px;/s],
])
  assert.match(css, rule, `${what} is the frame’s size`);
/* The semantic colour is ink on the mark, never a fill on the glass. */
assert.match(css, /\.quiz-verdict\[data-tone='right'\] > svg \{ color: var\(--status-success\); \}/, 'the mark is ink');

/* --- In every interface language ---------------------------------------- */

const { vi } = await import('../static/orena/ui/copy-vi.js');
const packs = { en: copy.en, zh: copy.zh, vi };
for (const [name, pack] of Object.entries(packs))
  for (const key of ['quizAnswer', 'quizSkip', 'quizRight', 'quizWrong', 'quizEvidenceLabel', 'quizBackToText', 'quizNext', 'quizFinish', 'quizPlace'])
    assert.ok(pack[key], `${name} writes ${key} in its own words`);
/* The frame writes the counter bare: "1 / 3". */
for (const pack of Object.values(packs)) assert.equal(pack.quizPlace, '{n} / {t}');

console.log('test_orena_comprehension.mjs: one question, answered, with the lines that settle it');
