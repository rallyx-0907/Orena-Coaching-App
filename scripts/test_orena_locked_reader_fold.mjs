/* Gate for #472: the locked Reader's Unlock is reachable without scrolling on a phone (360x740, 390x844).

   The end-of-preview card (the Coming-soon card with Unlock) is the workspace's fixed bottom row: a sibling of the
   Reader's scroll region inside `.s-reader`, never inside it. The title, the cover and the first paragraph stay in the
   scroll region, unblurred (owner rule), and scroll there when they are long (Design Contract rule 49). Measured on
   :8021 at 360x740: Unlock at y 650-694, card 465-726, no page scroll, in EN/VI/ZH. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US', onLine: true }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { setLanguages } = await import('../static/orena/copy/index.js');
const { lockedPreviewMarkup } = await import('../static/orena/screens/reader/locked.js');

/* The div depth at each position of the markup, so "sibling of" and "inside" can be read without a DOM. */
function depthAt(markup, index) {
  let depth = 0;
  const tag = /<(\/?)div\b/g;
  let match;
  while ((match = tag.exec(markup)) && match.index < index) depth += match[1] ? -1 : 1;
  return depth;
}
function closeOf(markup, openIndex) {
  const tag = /<(\/?)div\b/g;
  tag.lastIndex = openIndex;
  let depth = 0;
  let match;
  while ((match = tag.exec(markup))) {
    depth += match[1] ? -1 : 1;
    if (depth === 0) return match.index;
  }
  return -1;
}

const preview = { title: 'Rain returns', first_paragraph: 'The river rose overnight. '.repeat(40), language: 'en', image: { url: '/api/reading/articles/0123abcd-0000-0000-0000-000000000000/image', credit: 'Photo: A' } };

for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui });
  const markup = String(lockedPreviewMarkup({ preview: ui === 'zh' ? { ...preview, language: 'zh', first_paragraph: '河水涨了。'.repeat(60) } : preview, tier: 'plus' }));
  const frame = markup.lastIndexOf('<div', markup.indexOf('class="s-reader s-reader-locked"'));
  const scroll = markup.lastIndexOf('<div', markup.indexOf('data-scroll-region'));
  const scrollEnd = closeOf(markup, scroll);
  const foot = markup.lastIndexOf('<div', markup.indexOf('s-reader-locked__foot'));
  const card = markup.indexOf('o-coming__card');
  const unlock = markup.indexOf('data-locked-unlock');
  assert.ok(frame >= 0 && scroll > frame && foot > 0 && card > 0 && unlock > 0, `${ui}: the frame, the region, the foot and Unlock are drawn`);

  // The preview (cover, title, first paragraph) is inside the scroll region.
  for (const part of ['s-reader-locked__cover', 's-reader-locked__title', 's-reader__paragraph']) {
    const at = markup.indexOf(part);
    assert.ok(at > scroll && at < scrollEnd, `${ui}: ${part} scrolls in the Reader's region`);
  }
  // The card and Unlock are not: they sit in the foot, after the region, at the region's own depth (#472).
  assert.ok(card > scrollEnd && unlock > scrollEnd, `${ui}: the end-of-preview card is outside the scroll region`);
  assert.ok(foot > scrollEnd && card > foot, `${ui}: the card is in the foot`);
  assert.equal(depthAt(markup, foot), depthAt(markup, scroll), `${ui}: the foot is the region's sibling inside .s-reader`);
  assert.equal(depthAt(markup, foot), depthAt(markup, frame) + 1, `${ui}: the foot is a direct child of the Reader frame`);
}
setLanguages({ ui: 'en' });

// The CSS: the region takes the rest and scrolls; the foot never shrinks, never floats over the text.
const css = readFileSync('static/orena/screens/reader/reader.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const rule = (selector) => {
  const match = css.match(new RegExp(`(^|\\n)${selector.replace(/[.]/g, '\\.')}\\s*\\{([^}]*)\\}`));
  return match ? match[2] : '';
};
const region = rule('.s-reader__scroll');
assert.ok(/flex:\s*1/.test(region) && /min-height:\s*0/.test(region) && /overflow:\s*auto/.test(region), 'the region fills the rest and scrolls itself');
const footRule = rule('.s-reader-locked__foot');
assert.ok(/flex:\s*none/.test(footRule), 'the foot keeps its height');
assert.ok(!/position:\s*(fixed|absolute|sticky)/.test(footRule), 'the foot is in the flow, never over the preview');
const frameRule = rule('.s-reader');
assert.ok(/display:\s*flex/.test(frameRule) && /flex-direction:\s*column/.test(frameRule) && /height:\s*100%/.test(frameRule), 'the Reader frame is the viewport column');

console.log('Locked Reader fold gate (#472) OK');
