/* Gate for Feedback (static/orena/screens/feedback): no backend takes feedback, so Send is inert,
   the history is empty with its honest zero, and the form (stars, areas, text) is a draft only.
   Every word exists in English, Vietnamese and Chinese. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const model = await import('../static/orena/screens/feedback/model.js');
const { feedbackMarkup } = (await import('../static/orena/screens/feedback/screen.js')).__internal;
const copy = await import('../static/orena/copy/index.js');
const { byId, match } = await import('../static/orena/shell/routes.js');

assert.equal(model.SEND_AVAILABLE, false, 'there is no feedback endpoint');
assert.deepEqual(model.history(), [], 'nothing can have been sent');
assert.equal(model.canSend({ stars: 5 }), false, 'a rating alone cannot send without an endpoint');
assert.equal(model.canSend({ stars: 5, available: true }), true);
assert.equal(model.canSend({ stars: 0, available: true }), false, 'a rating is required');
assert.deepEqual(model.AREAS, ['listening', 'speaking', 'reading', 'writing', 'vocabulary', 'orena', 'bugs']);
assert.equal(model.ratingKey(0), 'rate0');
assert.equal(model.ratingKey(5), 'rate5');
assert.equal(model.ratingKey(9), 'rate5');
assert.equal(model.ratingKey(-2), 'rate0');
assert.equal(model.ratingKey('x'), 'rate0');
assert.deepEqual(model.toggleArea([], 'writing'), ['writing']);
assert.deepEqual(model.toggleArea(['writing'], 'writing'), []);
assert.deepEqual(model.toggleArea(['writing'], 'nope'), ['writing'], 'an unknown area is ignored');
assert.equal(model.clampText('a'.repeat(700)).length, model.TEXT_LIMIT);
assert.equal(model.clampText(null), '');

for (const ui of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  const markup = String(feedbackMarkup({ stars: 3, areas: ['writing'], text: 'x' }));
  assert.equal((markup.match(/data-star=/g) || []).length, 5, `${ui}: five stars`);
  assert.equal((markup.match(/aria-pressed="true"/g) || []).length, 3 + 1, `${ui}: three stars and one area are selected`);
  assert.equal((markup.match(/data-area=/g) || []).length, 7, `${ui}: seven areas`);
  assert.match(markup, /data-send disabled/, `${ui}: Send is inert`);
  assert.match(markup, /data-text/);
  assert.doesNotMatch(markup, /s-fb-past__item|Just now/, `${ui}: no sample review`);
  assert.match(markup, /s-fb-past__count">[^<]*0[^<]*</, `${ui}: the honest zero count`);
}
copy.setLanguages({ ui: 'en', support: 'en' });
assert.match(String(feedbackMarkup()), /0 reviews/);
assert.match(String(feedbackMarkup()), /Tap a star to rate/);

assert.equal(byId('feedback').focus, true, "Feedback is in the design's focus list");
assert.equal(match('#/feedback').route.id, 'feedback');

console.log('Orena feedback screen: inert send, empty history, draft form, EN/VI/ZH markup, route: PASS');
