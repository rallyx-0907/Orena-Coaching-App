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

/* PRE-206: a report from an AI output opens the form with its area chosen and the reference at the start of the text. */
{
  const { reportHref, cleanRef, reportLink, REF_LIMIT } = await import('../static/orena/product/report-problem.js');
  assert.deepEqual(model.reportDraft(new URLSearchParams('area=writing&ref=writing-evaluation%20%7C%20e1')), { areas: ['writing'], text: '[writing-evaluation | e1] ' });
  assert.deepEqual(model.reportDraft(new URLSearchParams('area=nope')), { areas: [], text: '' }, 'an unknown area is dropped');
  assert.deepEqual(model.reportDraft(undefined), { areas: [], text: '' });
  assert.equal(model.reportDraft(new URLSearchParams({ ref: 'a]\nb[' })).text, '[a b] ', 'brackets and newlines never break the reference');
  assert.equal(cleanRef(['word-sheet', 'c1', 'x'.repeat(400)]).length, REF_LIMIT, 'the reference is bounded');
  assert.equal(cleanRef(['listening-question', '', null, 'q1']), 'listening-question | q1');
  const address = reportHref({ area: 'vocabulary', surface: 'word-sheet', id: 'c1', text: 'forest' });
  assert.match(address, /^#\/feedback\?area=vocabulary&ref=/);
  const query = new URLSearchParams(address.split('?')[1]);
  assert.deepEqual(model.reportDraft(query), { areas: ['vocabulary'], text: '[word-sheet | c1 | forest] ' }, 'the link and the screen agree');
  for (const [ui, word] of [['en', 'Report a problem'], ['vi', 'Báo sai'], ['zh', '报告问题']]) {
    copy.setLanguages({ ui, support: ui });
    assert.match(String(reportLink({ area: 'writing', surface: 'w' })), new RegExp(`data-report-problem[^>]*>${word}<`), `${ui}: the link reads ${word}`);
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
}

/* PRE-204: an estimated content level reads with the "est." qualifier; a reviewed one reads plain. */
{
  const { levelIsEstimated, levelWithQualifier } = await import('../static/orena/kit/level-label.js');
  assert.equal(levelIsEstimated({ level: 'B2', level_source: 'deterministic-estimate' }), true);
  assert.equal(levelIsEstimated({ level: 'B1', level_source: 'editorial-review' }), false);
  assert.equal(levelIsEstimated({ estimated_level: 'B2' }), true);
  assert.equal(levelIsEstimated({ level: 'B2', estimated_level: 'B2' }), false);
  assert.equal(levelIsEstimated(null), false);
  for (const [ui, word] of [['en', 'est.'], ['vi', 'ước tính'], ['zh', '估计']]) {
    copy.setLanguages({ ui, support: ui });
    assert.equal(levelWithQualifier('HSK4', true), `HSK4 · ${word}`);
  }
  assert.equal(levelWithQualifier('B2', false), 'B2');
  assert.equal(levelWithQualifier('', true), '');
  copy.setLanguages({ ui: 'en', support: 'en' });
  // PRE-204 (AC): a reading article says it (level_source from the learner payloads); every surface goes through one helper.
  const { itemLevelLabel } = await import('../static/orena/kit/level-label.js');
  assert.equal(itemLevelLabel({ level: 'B1', level_source: 'deterministic-estimate' }), 'B1 · est.');
  assert.equal(itemLevelLabel({ level: 'B1', level_source: 'editorial-review' }), 'B1');
  assert.equal(itemLevelLabel({ level: 'B1' }), 'B1');
  assert.equal(itemLevelLabel({}), '');
  const { articleItems, listeningItems } = await import('../static/orena/screens/search/model.js');
  assert.equal(articleItems({ items: [{ id: 1, title: 'x', level: 'B2', level_source: 'deterministic-estimate' }] }, '')[0].meta, 'B2 · est.');
  assert.equal(articleItems({ items: [{ id: 1, title: 'x', level: 'B2', level_source: 'editorial-review' }] }, '')[0].meta, 'B2');
  assert.equal(listeningItems({ items: [{ lesson_id: 'm', title: 'x', level: 'A2', level_source: 'deterministic-estimate' }] }, '')[0].meta, 'A2 · est.');
  const { normalizeArticle } = await import('../static/orena/screens/content/model.js');
  assert.equal(normalizeArticle({ title: 't', level: 'B1', level_source: 'deterministic-estimate' }).levelEstimated, true);
  assert.equal(normalizeArticle({ title: 't', level: 'B1', level_source: 'editorial-review' }).levelEstimated, false);
  const { shellCopy } = await import('../static/orena/copy/shell.js');
  for (const [ui, text] of [['en', 'Automatic estimate, for reference only.'], ['vi', 'Điểm ước tính tự động, chỉ để tham khảo.'], ['zh', '自动估算分数，仅供参考。']]) {
    copy.setLanguages({ ui, support: ui });
    assert.equal(shellCopy('scoreNote'), text);
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
  copy.setLanguages({ ui: 'en', support: 'en' });
}

console.log('Orena feedback screen: send, history, form, EN/VI/ZH markup, route, report-a-problem, estimated level: PASS');
