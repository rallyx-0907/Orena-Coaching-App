/* Gate for the Situation Reaction screen's pure data mapping (frame 31, route 'situation'; Design
   Contract rule 40). Imports only the DOM-free module
   (static/orena/screens/situation/model.js), no browser, no network. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const fixture = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));

const { scenarios, progressLabel, naturalAlternative } = await import('../static/orena/screens/situation/model.js');

// 1. Scenarios: the same real, Orena-authored bank Free Talk/Conversation draw from - 3 items,
// not the frame's own fixed 2-item `SITUATIONS`, real in both learning languages.
{
  const en = scenarios('en');
  assert.equal(en.length, 3);
  for (const item of en) assert.ok(item.scenario.length > 0);
  const zh = scenarios('zh');
  assert.equal(zh.length, 3);
  assert.notEqual(zh[0].scenario, en[0].scenario);
}

// 2. progressLabel: a real 1-based position in the real bank, never out of range.
assert.deepEqual(progressLabel(0, 3), { index: 1, total: 3 });
assert.deepEqual(progressLabel(2, 3), { index: 3, total: 3 });

// 3. naturalAlternative: prefers the concrete `say_again` line, falls back to `another_way`, never
// invents a value when neither is present.
assert.equal(naturalAlternative({ say_again: 'Nice to meet you.', another_way: 'x' }), 'Nice to meet you.');
assert.equal(naturalAlternative({ say_again: '', another_way: 'Try a softer opener.' }), 'Try a softer opener.');
assert.equal(naturalAlternative({}), '');
assert.equal(naturalAlternative(null), '');

// 4. The real spoken-response captures: the two fields the result rows read (`next_attempt`,
// `say_again`) are really there, and a real capture maps to a Natural alternative.
for (const name of ['spoken_response.json', 'spoken_response_landed.json']) {
  const real = fixture(name);
  assert.equal(typeof real.next_attempt, 'string', name);
  assert.ok(real.next_attempt.length > 0, `${name}: a real next_attempt for the "One useful improvement" row`);
  assert.ok(naturalAlternative(real).length > 0, `${name}: a real line for the "Natural alternative" row`);
}

console.log('Orena screen situation: model mapping (scenarios, progress, natural alternative) against the real spoken-response captures: PASS');

// D-139 HD-13: every scenario carries an authored context for the chip above it, in both languages.
{
  const { scenarios } = await import('../static/orena/screens/situation/model.js');
  for (const language of ['en', 'zh']) {
    for (const item of scenarios(language)) assert.ok(typeof item.context === 'string' && item.context.length > 0, `${language} ${item.key} has a context`);
  }
}
