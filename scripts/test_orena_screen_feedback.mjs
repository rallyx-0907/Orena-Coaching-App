/* Gate for Feedback (static/orena/screens/feedback): Send posts to /api/feedback (D-156), the history
   is the learner's own reviews from /api/feedback/mine, the form (stars, areas, text) is the design's.
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

assert.equal(model.SEND_AVAILABLE, true, 'the backend takes feedback');
assert.deepEqual(model.history(), [], 'no reviews yet');
assert.deepEqual(model.history(null), []);
assert.equal(model.canSend({ stars: 5 }), true);
assert.equal(model.canSend({ stars: 5, available: false }), false);
assert.equal(model.canSend({ stars: 0 }), false, 'a rating is required');
const mapped = model.history([{ id: 'a', stars: 4, areas: ['writing', 'nope'], text: ' hi ', created_at: '2026-10-09T10:00:00Z' }]);
assert.deepEqual(mapped, [{ id: 'a', stars: 4, areas: ['writing'], text: 'hi', createdAt: '2026-10-09T10:00:00Z' }]);
assert.equal(model.starsText(3), '★★★☆☆');
assert.equal(model.starsText(9), '★★★★★');
assert.deepEqual(model.sendBody({ stars: 4, areas: ['bugs'], text: ' x ' }, { language: 'zh', interfaceLanguage: 'vi' }), { stars: 4, areas: ['bugs'], text: 'x', language: 'zh', interface: 'vi' });
assert.equal(model.errorKey(429), 'errTooMany');
assert.equal(model.errorKey(503), 'errUnavailable');
assert.equal(model.errorKey(422), 'errInvalid');
assert.equal(model.errorKey(500), 'errFailed');
assert.equal(model.errorKey(undefined), 'errFailed');
assert.deepEqual(model.prepend([{ id: 'a' }, { id: 'b' }], { id: 'c' }).map((r) => r.id), ['c', 'a', 'b']);
assert.deepEqual(model.prepend([{ id: 'a' }], { id: 'a' }).map((r) => r.id), ['a'], 'a review is listed once');
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

const sample = [{ id: 'r1', stars: 4, areas: ['speaking'], text: 'Slower audio please', created_at: '2026-09-21T08:00:00Z' }];
for (const ui of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  const markup = String(feedbackMarkup({ stars: 3, areas: ['writing'], text: 'x' }));
  assert.equal((markup.match(/data-star=/g) || []).length, 5, `${ui}: five stars`);
  assert.equal((markup.match(/aria-pressed="true"/g) || []).length, 3 + 1, `${ui}: three stars and one area are selected`);
  assert.equal((markup.match(/data-area=/g) || []).length, 7, `${ui}: seven areas`);
  assert.doesNotMatch(markup, /data-send disabled/, `${ui}: Send is live with a rating`);
  assert.match(String(feedbackMarkup()), /data-send disabled/, `${ui}: Send waits for a rating`);
  assert.match(String(feedbackMarkup({ stars: 3, sending: true })), /data-send disabled/, `${ui}: Send is disabled while sending`);
  assert.match(markup, /data-text/);
  assert.doesNotMatch(markup, /not available yet|s-fb-item__row/, `${ui}: no inert hint, no sample review`);
  assert.match(markup, /s-fb-past__count[^>]*>[^<]*0[^<]*</, `${ui}: the honest zero count`);
  const withItems = String(feedbackMarkup({ items: sample }));
  assert.match(withItems, /★★★★☆/, `${ui}: the card draws its stars`);
  assert.match(withItems, /Slower audio please/);
  assert.match(withItems, /s-fb-item__tag/, `${ui}: the area is a pill`);
  assert.match(withItems, /s-fb-past__count[^>]*>[^<]*1[^<]*</, `${ui}: the count`);
  assert.match(String(feedbackMarkup({ stars: 2, error: copy.t('feedback', 'errTooMany') })), /data-error role="alert">[^<]+</, `${ui}: the error shows under the button`);
  for (const key of ['sending', 'hintChoose', 'hintSent', 'thanks', 'statusSent', 'errTooMany', 'errUnavailable', 'errInvalid', 'errFailed']) {
    assert.notEqual(copy.t('feedback', key), key, `${ui}: ${key} is translated`);
  }
}
copy.setLanguages({ ui: 'en', support: 'en' });
assert.match(String(feedbackMarkup({ items: sample })), /Sep 21, 2026|21 Sep/, 'the date is localized');
assert.match(String(feedbackMarkup()), /0 reviews/);
assert.match(String(feedbackMarkup()), /Tap a star to rate/);
assert.match(String(feedbackMarkup()), /Choose a rating first/);

assert.equal(byId('feedback').focus, true, "Feedback is in the design's focus list");
assert.equal(match('#/feedback').route.id, 'feedback');

console.log('Orena feedback screen: send, history, form, EN/VI/ZH markup, route: PASS');
