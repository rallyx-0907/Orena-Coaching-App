/* Gate for the new learner UI's shared components (D-091 primitives pass; Design Contract rules
   16, 30, 44, 46). Each exported function in kit/components.js:
   - escapes every learner/API string it is given (kit/html.js's default), even inside an
     attribute value the component builds itself (dataset, style);
   - renders the parts a caller asked for and omits the parts it did not (no dangling wrapper for
     an absent optional field);
   - never has a colour literal - callers pass var(--token) strings, this file must not need to. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const { raw } = await import('../static/orena/kit/html.js');

const SRC = fs.readFileSync('static/orena/kit/components.js', 'utf8');
const CSS = fs.readFileSync('static/orena/kit/components.css', 'utf8');

// 1. No colour literal in either file (the same rule test_orena_kit.mjs enforces tree-wide;
// checked again here, scoped, so this gate fails loudly the moment a component regresses it).
for (const [name, code] of [['components.js', SRC], ['components.css', CSS]]) {
  const stripped = code.replace(/\/\*[\s\S]*?\*\//g, '');
  const literal = stripped.match(/(?<![&\w])#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/);
  assert.equal(literal, null, `${name}: colour literal ${literal?.[0]} - use var(--token)`);
}

// 2. Every icon() call names an icon kit/icons.js actually has.
const { ICONS } = await import('../static/orena/kit/icons.js');
for (const match of SRC.matchAll(/\bicon\(\s*'([a-z0-9-]+)'/g) ) assert.ok(ICONS[match[1]], `icon "${match[1]}" is in kit/icons.js`);
for (const match of SRC.matchAll(/icon\(iconName,/g)) void match; // iconName is a caller param, not a literal - nothing to check here.

const {
  mediaCard, listRow, rowIconSwatch, rowThumb, rowBadge, sectionHead, progressRing, segmentedControl, heroMedia, pageHeader, masteryBars,
} = await import('../static/orena/kit/components.js');

const XSS = '<script>alert(1)</script>&"\'';
const ESCAPED = '&lt;script&gt;alert(1)&lt;/script&gt;&amp;&quot;&#039;';

function has(markup, needle) {
  return String(markup).includes(needle);
}

// 3. mediaCard: escapes title/meta/tag text and the dataset; renders only the badges/progress/tags
// it was given.
{
  const bare = String(mediaCard({ title: XSS }));
  assert.ok(has(bare, ESCAPED), 'mediaCard escapes the title');
  assert.ok(!bare.includes('c-media__badge'), 'mediaCard draws no badge without kind/duration');
  assert.ok(!bare.includes('c-media__progress'), 'mediaCard draws no progress strip when progress is null');
  assert.ok(!bare.includes('c-media__tags'), 'mediaCard draws no tag row when tags is empty');

  const full = String(mediaCard({
    title: 'Morning Routines', meta: XSS, kind: 'Video', duration: '12 min', progress: 40,
    tags: [{ label: 'B1', tone: 'accent' }], dataset: { open: XSS },
  }));
  assert.ok(has(full, ESCAPED), 'mediaCard escapes meta text');
  assert.ok(has(full, 'c-media__badge--tl') && has(full, '>Video<'), 'mediaCard draws the type pill');
  assert.ok(has(full, 'c-media__badge--br') && has(full, '>12 min<'), 'mediaCard draws the duration pill');
  assert.ok(has(full, 'width:40%'), 'mediaCard draws the progress strip at the given percent');
  assert.ok(has(full, 'o-tag--accent') && has(full, '>B1<'), 'mediaCard draws its tags');
  assert.ok(has(full, `data-open="${ESCAPED}"`), 'mediaCard escapes a dataset value used as an attribute');
  assert.equal(String(mediaCard({ title: 'x', progress: 140 })).match(/width:(\d+)%/)[1], '100', 'mediaCard clamps progress to 100');
  assert.equal(String(mediaCard({ title: 'x', progress: -20 })).match(/width:(\d+)%/)[1], '0', 'mediaCard clamps progress to 0');
}

// 4. listRow: escapes title/sub; only draws the lead/trail/chevron/kind it was given; carries the
// radius/pad a screen measured; the kind-line and inline-sub shapes (D-091 kit fidelity pass).
{
  const bare = String(listRow({ title: XSS, sub: XSS }));
  assert.ok(has(bare, ESCAPED), 'listRow escapes title and sub');
  assert.ok(!bare.includes('c-row__lead'), 'listRow draws no leading slot when leading is null');
  assert.ok(!bare.includes('c-row__trail'), 'listRow draws no trailing slot when trailing is null');
  assert.ok(!bare.includes('c-row__chevron'), 'listRow draws no chevron unless asked');
  assert.ok(!bare.includes('c-row__kind'), 'listRow draws no kind line without one');
  assert.ok(!bare.includes('font-size:'), 'listRow draws no inline title style at the default titleSize');
  assert.ok(has(bare, '<button'), 'listRow defaults to a button');

  const full = String(listRow({
    tag: 'div', variant: 'outline', radius: 14, pad: '13px 18px',
    leading: rowThumb({ width: 64, height: 48 }), title: 'Word', sub: 'meaning', trailing: masteryBars({ filled: 2 }), chevron: true,
  }));
  assert.ok(has(full, '<div'), 'listRow renders a div when tag is "div"');
  assert.ok(has(full, 'c-row--outline'), 'listRow applies the outline variant');
  assert.ok(has(full, 'border-radius:14px;padding:13px 18px'), 'listRow carries the measured radius and padding');
  assert.ok(has(full, 'c-row__lead') && has(full, 'c-row__thumb'), 'listRow renders the given leading slot');
  assert.ok(has(full, 'c-row__trail') && has(full, 'c-bars'), 'listRow renders the given trailing slot');
  assert.ok(has(full, 'c-row__chevron'), 'listRow renders the chevron when asked');

  // Notifications' own kind+when/title/sub shape: a `kind` line, escaped, ahead of the title.
  const kinded = String(listRow({ kind: XSS, title: 'Review', sub: 'x' }));
  assert.ok(has(kinded, 'c-row__kind') && has(kinded, ESCAPED), 'listRow draws and escapes the given kind line');
  assert.ok(kinded.indexOf('c-row__kind') < kinded.indexOf('c-row__title'), 'listRow draws the kind line before the title');
  assert.ok(has(kinded, 'c-row__sub">'), 'listRow still draws sub as its own line when inlineSub is not set');

  // Profile's own action-row shape: sub nested inside the title, no separate stacked line, at a
  // caller-given title size.
  const inline = String(listRow({ title: 'Settings', titleSize: 16, inlineSub: true, sub: XSS, chevron: true }));
  assert.ok(has(inline, 'c-row__title--loose'), 'listRow marks the title loose (no truncation) when inlineSub is set');
  assert.ok(has(inline, 'font-size:16px'), 'listRow carries the given titleSize as an inline style');
  const titleSpan = inline.slice(inline.indexOf('c-row__title'), inline.indexOf('c-row__trail'));
  assert.ok(titleSpan.includes('c-row__sub--inline') && titleSpan.includes(ESCAPED), 'listRow nests the escaped sub inside the title span, not as a sibling, when inlineSub is set');

  // The one row that is a real external navigation, not an in-app route.
  const anchor = String(listRow({ tag: 'a', href: '/#/admin', title: 'Platform admin' }));
  assert.ok(has(anchor, '<a ') && has(anchor, 'href="/#/admin"') && has(anchor, '</a>'), 'listRow renders an anchor with its href when tag is "a"');

  // Grammar Library's own explicit line-height, independent of the kind-line shape.
  const glTitle = String(listRow({ radius: 20, pad: '16px', title: 'Mixed conditionals', titleLineHeight: 20 }));
  assert.ok(has(glTitle, 'line-height:20px'), 'listRow carries an explicit titleLineHeight as an inline style');
  const combined = String(listRow({ title: 'x', titleSize: 16, titleLineHeight: 20 }));
  assert.ok(has(combined, 'style="font-size:16px;line-height:20px"'), 'listRow combines titleSize and titleLineHeight in one style attribute');
}

// 5. rowIconSwatch / rowThumb / rowBadge: escape their string inputs, size themselves from params.
{
  assert.ok(has(String(rowIconSwatch({ iconName: 'search', tint: 'var(--accent-soft)', size: 44 })), 'width:44px'), 'rowIconSwatch sizes from `size`');
  assert.ok(has(String(rowThumb({ image: 'url(x.jpg)', width: 64, height: 48, radius: 12 })), 'border-radius:12px'), 'rowThumb carries its radius');
  assert.ok(String(rowThumb({})).includes('o-art'), 'rowThumb falls back to the artwork placeholder when there is no image');
  assert.ok(has(String(rowBadge({ glyph: XSS })), ESCAPED), 'rowBadge escapes its glyph');
}

// 6. sectionHead: escapes title/label; the action link (with its optional chevron) only appears
// when an action was given.
{
  const bare = String(sectionHead({ title: XSS }));
  assert.ok(has(bare, ESCAPED), 'sectionHead escapes the title');
  assert.ok(!bare.includes('c-section-head__action'), 'sectionHead draws no action without one');
  const withAction = String(sectionHead({ title: 'For you', size: 'sm', action: { label: XSS, chevron: true, dataset: { go: 'discover' } } }));
  assert.ok(has(withAction, 'c-section-head--sm'), 'sectionHead applies the sm size');
  assert.ok(has(withAction, ESCAPED), 'sectionHead escapes the action label');
  assert.ok(has(withAction, '<svg'), 'sectionHead draws the chevron icon as inline svg when asked');
  assert.ok(has(withAction, 'data-go="discover"'), 'sectionHead carries the action dataset');
}

// 7. progressRing: clamps percent into the dasharray, only draws a center when given one.
{
  const bare = String(progressRing({ percent: 55 }));
  assert.ok(has(bare, 'stroke-dasharray="55 100"'), 'progressRing sets the dasharray from percent');
  assert.ok(!bare.includes('c-ring__center'), 'progressRing draws no center without one');
  assert.ok(has(String(progressRing({ percent: 250 })), 'stroke-dasharray="100 100"'), 'progressRing clamps percent to 100');
  assert.ok(has(String(progressRing({ percent: -10 })), 'stroke-dasharray="0 100"'), 'progressRing clamps percent to 0');
  const withCenter = String(progressRing({ percent: 40, center: '40%' }));
  assert.ok(has(withCenter, 'c-ring__center') && has(withCenter, '>40%<'), 'progressRing draws the given center content');
}

// 8. segmentedControl: escapes labels, marks the selected option, carries the group name.
{
  const seg = String(segmentedControl({
    name: 'range', options: [{ value: 'week', label: 'Week', selected: true }, { value: XSS, label: XSS, selected: false }],
  }));
  assert.ok(has(seg, 'aria-pressed="true"'), 'segmentedControl marks the selected option');
  assert.ok(has(seg, ESCAPED), 'segmentedControl escapes an option label');
  assert.ok(has(seg, `data-value="${ESCAPED}"`), 'segmentedControl escapes an option value used as an attribute');
  assert.ok(has(seg, 'data-seg="range"'), 'segmentedControl carries the group name');
  assert.ok(has(String(segmentedControl({ options: [], variant: 'hero' })), 'c-seg--hero'), 'segmentedControl applies the hero variant');
}

// 9. heroMedia: escapes title/meta/pill text; only draws pills/meta it was given.
{
  const bare = String(heroMedia({ title: XSS }));
  assert.ok(has(bare, ESCAPED), 'heroMedia escapes the title');
  assert.ok(!bare.includes('c-hero__pill'), 'heroMedia draws no pill when none is given');
  assert.ok(!bare.includes('c-hero__meta'), 'heroMedia draws no meta line without one');
  const full = String(heroMedia({ title: 'A Morning in the City', meta: XSS, pill: XSS, height: 200, radius: 24, titleSize: 26 }));
  assert.ok(has(full, ESCAPED), 'heroMedia escapes meta and pill text');
  assert.ok(has(full, 'height:200px;border-radius:24px'), 'heroMedia carries its measured height and radius');
  assert.ok(has(full, 'font-size:26px'), 'heroMedia carries its measured title size');
}

// 10. pageHeader: renders the h1 shell by default, the compact shell when asked; only draws a back
// button/actions/meta it was given.
{
  const plain = String(pageHeader({ title: XSS }));
  assert.ok(has(plain, ESCAPED), 'pageHeader escapes the title');
  assert.ok(has(plain, 'o-h1'), 'pageHeader defaults to the full o-h1 heading');
  assert.ok(!plain.includes('o-iconbtn--back'), 'pageHeader draws no back button without one');
  assert.ok(!plain.includes('o-sub'), 'pageHeader draws no subtitle without meta');

  const compact = String(pageHeader({
    compact: true, back: { label: XSS, dataset: { back: '1' } }, title: 'Present perfect', meta: XSS, actions: [raw('<button>Ask</button>')],
  }));
  assert.ok(has(compact, 'c-pagehead--compact'), 'pageHeader renders the compact shell when asked');
  assert.ok(has(compact, 'o-iconbtn') && !has(compact, 'o-iconbtn--back'), 'pageHeader draws the plain (radius-12) back button in compact mode, not the --back modifier');
  assert.ok(has(compact, `aria-label="${ESCAPED}"`), 'pageHeader escapes the back button label');
  assert.ok(has(String(pageHeader({ back: { label: 'Back' }, title: 'Settings' })), 'o-iconbtn--back'), 'pageHeader draws the --back modifier (radius 14) in the default, non-compact shell');
  assert.ok(has(compact, 'c-pagehead__meta') && has(compact, ESCAPED), 'pageHeader draws and escapes the compact meta line');
  assert.ok(has(compact, '<button>Ask</button>'), 'pageHeader inserts pre-built action markup as trusted markup');
}

// 11. masteryBars: fills exactly `filled` of `total` bars.
{
  const bars = String(masteryBars({ filled: 2, total: 4 }));
  assert.equal([...bars.matchAll(/c-bars__bar/g)].length, 4, 'masteryBars draws `total` bars');
  const accentCount = [...bars.matchAll(/background:var\(--accent\)/g)].length;
  assert.equal(accentCount, 2, 'masteryBars fills exactly `filled` bars in the given colour');
}

console.log('Orena components: markup escapes data, renders only the parts it was given, no colour literal, icons known: PASS');
