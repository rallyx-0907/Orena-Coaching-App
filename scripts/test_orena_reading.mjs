import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  readingText,
  readingEntry,
  readingSessionId,
} from '../static/orena/content/reading.js';
import { comprehensionSection } from '../static/orena/ui/comprehension.js';
import { copy } from '../static/orena/ui/copy.js';
import { origin } from '../static/orena/ui/content.js';

for (const language of ['en', 'zh']) {
  const passage =
    language === 'en'
      ? 'First line.\nStill here.\n\nA second paragraph.'
      : '第一行。\n还在这里。\n\n第二段。';
  const session = {
    id: 12,
    language_code: language,
    passage,
    title: '<a title>',
    generation_mode: 'built-in',
    topic: 'work',
    material: 'news',
    questions: [
      { question: 'Why?', options: ['<one>', 'two', 'three', 'four'] },
    ],
  };
  const content = readingText(session, language);
  assert.equal(content.paragraphs.length, 2);
  assert.equal(content.paragraphs[0], passage.split('\n\n')[0]);
  assert.equal(content.topic, '');
  assert.equal(content.material, '');
  assert.equal(origin(content, copy[language]), copy[language].readingBuiltIn);
  assert.equal(
    readingText(
      { ...session, language_code: language === 'en' ? 'zh' : 'en' },
      language,
    ),
    null,
  );
  assert.equal(readingText({ ...session, id: '../evil' }, language), null);
  assert.equal(readingText({ ...session, passage: '' }, language), null);
  assert.equal(readingEntry(session, language).attempted, false);
  assert.equal(
    readingEntry(
      { ...session, latest_attempt: { total: 4, correct_count: 0 } },
      language,
    ).attempted,
    true,
  );
  const markup = comprehensionSection(copy[language], content.questions);
  assert.match(markup, /^<details/);
  assert.ok(!markup.includes('<details open'));
  assert.match(markup, /&lt;one&gt;/);
  assert.equal(comprehensionSection(copy[language], []), '');
}
for (const id of [
  '',
  'reading:0',
  'reading:-1',
  'reading:1/answer',
  'reading:01',
])
  assert.equal(readingSessionId(id), null);
assert.equal(readingSessionId('reading:12'), 12);
const encounter = readFileSync('static/orena/ui/encounter.js', 'utf8');
assert.match(
  encounter,
  /payload\.found \? payload\.session : null/,
  'Read the real API envelope',
);
console.log(
  'Reading: source truth, EN/ZH, paragraph fidelity, optional comprehension, API envelope PASS',
);
