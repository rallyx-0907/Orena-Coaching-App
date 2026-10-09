// Applies the repository-owned legal text (docs/legal/public/*) to a public page skeleton.
//
// The skeleton is the pinned design page (header, nav, hero, summary card, contents list, article, footer). This
// module replaces only the regions that carry words and rebuilds them with the skeleton's own markup, so layout,
// type and spacing stay the design's. Words come from docs/legal/public/<page>.<lang>.json; facts that the
// operator must confirm come from docs/legal/public/facts.json. A fact that is not confirmed (null) renders as a
// visible "[pending: ...]" mark in a normal build and fails a --release build (PUB-2, D-161).
import fs from 'node:fs';
import path from 'node:path';

export const LANGS = ['vi', 'en'];
export const PAGES = ['privacy', 'terms', 'account-deletion'];

// --- facts -----------------------------------------------------------------------------------------------------

export function loadFacts(root) {
  return JSON.parse(fs.readFileSync(path.join(root, 'docs/legal/public/facts.json'), 'utf8'));
}

function getPath(obj, p) {
  return p.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function formatDate(iso, lang) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) throw new Error(`effective_date must be YYYY-MM-DD, got ${JSON.stringify(iso)}`);
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return lang === 'vi' ? `${d} tháng ${mo}, ${y}` : `${MONTHS_EN[mo - 1]} ${d}, ${y}`;
}

// Every place where a fact is still unconfirmed is recorded here; --release fails when this is not empty.
export class Pending {
  constructor() { this.paths = new Set(); }
  add(p) { this.paths.add(p); }
  mark(p) {
    this.add(p);
    return `<mark style="background:#FFD54A;color:#1A1400;padding:0 4px;border-radius:4px">[pending: ${p}]</mark>`;
  }
}

// --- inline markup ---------------------------------------------------------------------------------------------

const STRONG = '<strong style="color:var(--text);font-weight:600">';

// `**bold**` and `[text](url)`. Everything else is passed through as typed (the design's own text keeps its raw
// `&`), so source text must not contain `<`.
function inline(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, `${STRONG}$1</strong>`)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, t, u) => `<a href="${u}">${t}</a>`);
}

function resolve(text, ctx) {
  return text.replace(/\{\{fact:([A-Za-z0-9_.]+)\}\}/g, (_m, name) => {
    const v = getPath(ctx.facts, name);
    if (v === null || v === undefined) return ctx.pending.mark(name);
    const lv = typeof v === 'object' ? v[ctx.lang] : v;
    if (lv === undefined) throw new Error(`fact ${name} has no ${ctx.lang} form`);
    return String(lv);
  });
}

function text(t, ctx) {
  if (/</.test(t)) throw new Error(`text must not contain "<": ${t.slice(0, 60)}`);
  return inline(resolve(t, ctx));
}

// --- blocks ----------------------------------------------------------------------------------------------------

const P_PRETTY = '<p style="margin:0;text-wrap:pretty">';
const P_LEAD = '<p style="margin:0">';
const UL = '<ul style="margin:0;padding-left:22px;display:flex;flex-direction:column;gap:8px">';
const CARDS = '<div style="display:flex;flex-direction:column;gap:12px">';
const CARD = '<div style="background:var(--surface);border-radius:18px;padding:16px 18px;display:flex;flex-direction:column;gap:4px"><div style="font-size:16px;font-weight:600;color:var(--text)">';
const CARD_BODY = '</div><div style="font-size:15.5px;line-height:1.6">';
const CONTACT = '<div style="background:var(--surface);border-radius:18px;padding:18px 20px;display:flex;flex-wrap:wrap;gap:12px 32px">';
const CONTACT_ITEM = '<div style="display:flex;flex-direction:column;gap:2px"><span style="font-size:13px;color:var(--text3)">';

function renderBlock(block, ctx) {
  if ('p' in block) return `${P_PRETTY}${text(block.p, ctx)}</p>`;
  if ('lead' in block) return `${P_LEAD}${text(block.lead, ctx)}</p>`;
  if ('ul' in block) {
    const items = block.ul.map((it) => `<li>${text(it, ctx)}</li>`);
    return `${UL}\n${items.map((i) => `          ${i}`).join('\n')}\n        </ul>`;
  }
  if ('cards' in block) {
    const cards = block.cards.map(([t, d]) => `          ${CARD}${text(t, ctx)}${CARD_BODY}${text(d, ctx)}</div></div>`);
    return `${CARDS}\n${cards.join('\n')}\n        </div>`;
  }
  if ('contact' in block) {
    const items = block.contact.map(([label, mail]) =>
      `          ${CONTACT_ITEM}${label}</span><a href="mailto:${mail}" style="font-size:16px;font-weight:600">${mail}</a></div>`);
    return `${CONTACT}\n${items.join('\n')}\n        </div>`;
  }
  throw new Error(`unknown block ${JSON.stringify(block).slice(0, 80)}`);
}

function renderSection(sec, i, ctx) {
  const H2 = '<h2 style="margin:0;font-size:24px;line-height:1.25;font-weight:700;letter-spacing:-.02em;color:var(--text)">';
  const inner = sec.blocks.map((b) => `        ${renderBlock(b, ctx)}`).filter((l) => l.trim()).join('\n');
  return `      <section id="s${i}" data-sec="${i}" style="display:flex;flex-direction:column;gap:14px">\n        ${H2}${sec.h}</h2>\n${inner}\n      </section>`;
}

// --- page regions ----------------------------------------------------------------------------------------------

export function rep(s, from, to) { return s.replace(from, () => to); }

export function must(re, s, name) {
  const m = re.exec(s);
  if (!m) throw new Error(`skeleton region not found: ${name}`);
  return m;
}

export const PAGE_HREF = { privacy: '/privacy', terms: '/terms', 'account-deletion': '/account-deletion' };

function href(page, lang) { return PAGE_HREF[page] + (lang === 'en' ? '?lang=en' : ''); }

function renderPane(pane, page, data, ctx) {
  let s = pane;

  // Nav pills: rebuilt from the skeleton's own inactive/active pill markup, in the order of `data.nav`.
  const nav = must(/(<nav [^>]*>)\n([\s\S]*?)\n(    <\/nav>)/, s, 'nav');
  const pills = [...nav[2].matchAll(/ *<a href="[^"]*" style="([^"]*)"( style-hover="[^"]*")?>[^<]*<\/a>/g)];
  const inactive = pills.find((m) => m[2]);
  const active = pills.find((m) => !m[2]);
  if (!inactive || !active) throw new Error('skeleton nav: no active and inactive pill');
  const pill = (key, label) => {
    const on = key === page;
    const src = on ? active : inactive;
    return `      <a href="${href(key, ctx.lang)}" style="${src[1]}"${src[2] || ''}>${label}</a>`;
  };
  s = rep(s, nav[0], `${nav[1]}\n${data.nav.map(([key, label]) => pill(key, label)).join('\n')}\n${nav[3]}`);

  const h1 = must(/(<h1[^>]*>)([^<]*)(<span[^>]*>)([^<]*)(<\/span><\/h1>)/, s, 'h1');
  // h1[2] is the plain words with their trailing space; the text file keeps that space in `h1[0]`.
  s = rep(s, h1[0], `${h1[1]}${data.h1[0]}${h1[3]}${data.h1[1]}${h1[5]}`);

  const intro = must(/(<p style="margin:0;font-size:clamp\(17px,1\.4vw,19px\)[^>]*>)[^<]*(<\/p>)/, s, 'intro');
  s = rep(s, intro[0], `${intro[1]}${text(data.intro, ctx)}${intro[2]}`);

  const dates = must(/(<div style="display:flex;gap:8px 20px;flex-wrap:wrap;font-size:14px;color:var\(--text3\)">)<span>[^<]*<\/span><span>[^<]*<\/span>(<\/div>)/, s, 'dates');
  const dateText = (t) => t.replace(/\{\{date\}\}/g, () => {
    const d = ctx.facts.effective_date;
    return d === null || d === undefined ? ctx.pending.mark('effective_date') : formatDate(d, ctx.lang);
  });
  s = rep(s, dates[0], `${dates[1]}${data.dates.map((d) => `<span>${dateText(d)}</span>`).join('')}${dates[2]}`);

  const label = must(/(<div style="font-size:15px;font-weight:600;color:var\(--muted\)">)[^<]*(<\/div>)/, s, 'summary label');
  s = rep(s, label[0], `${label[1]}${data.summary.label}${label[2]}`);
  let k = 0;
  s = s.replace(/(<span style="font-size:15\.5px;line-height:1\.5;color:var\(--body\)">)[^<]*(<\/span>)/g, (_m, a, b) => {
    const item = data.summary.items[k++];
    if (item === undefined) throw new Error('summary: skeleton has more items than the text');
    return `${a}${text(item, ctx)}${b}`;
  });
  if (k !== data.summary.items.length) throw new Error(`summary: ${k} slots, ${data.summary.items.length} items`);

  // Contents list: rebuilt from the skeleton's first anchor.
  const aside = must(/(<aside [^>]*>\n)(      <div [^>]*>)[^<]*(<\/div>\n)((?:      <a href="#s\d+"[^>]*>[^<]*<\/a>\n)+)(    <\/aside>)/, s, 'contents');
  const anchor = must(/<a href="#s1" style="([^"]*)">/, aside[4], 'contents anchor');
  const anchors = data.sections.map((sec, i) => `      <a href="#s${i + 1}" style="${anchor[1].replace(/\{\{ a\.s1 \}\}/, `{{ a.s${i + 1} }}`).replace(/\{\{ b\.s1 \}\}/, `{{ b.s${i + 1} }}`)}">${sec.toc || sec.h}</a>\n`).join('');
  if (data.sections.length > 14) throw new Error('the page runtime defines 14 section states');
  s = rep(s, aside[0], `${aside[1]}${aside[2]}${data.tocLabel}${aside[3]}${anchors}${aside[5]}`);

  const art = must(/(<article [^>]*>\n)([\s\S]*?)(\n    <\/article>)/, s, 'article');
  s = rep(s, art[0], `${art[1]}${data.sections.map((sec, i) => renderSection(sec, i + 1, ctx)).join('\n\n')}${art[3]}`);

  const foot = must(/(<footer [\s\S]*?<span>)[^<]*(<\/span>\n    )(<div style="display:flex;gap:20px;flex-wrap:wrap">)\n([\s\S]*?)(    <\/div>)/, s, 'footer');
  const link = must(/<a href="[^"]*" style="color:var\(--muted\)">/, foot[4], 'footer link');
  const links = data.footer.links.map(([key, label]) => {
    const h = key === 'landing' ? '/landing' : href(key, ctx.lang);
    return `      <a href="${h}" style="color:var(${key === page ? '--text' : '--muted'})">${label}</a>`;
  });
  s = rep(s, foot[0], `${foot[1]}${data.footer.copy}${foot[2]}${foot[3]}\n${links.join('\n')}\n${foot[5]}`);
  return s;
}

// Splits a skeleton into [head, viPane, enPane, tail] at the language switches.
export function split(skeleton) {
  const vi = skeleton.indexOf('<sc-if value="{{ isVi }}" hint-placeholder-val="{{ true }}">\n  <div style="max-width:1120px');
  const en = skeleton.indexOf('<sc-if value="{{ isEn }}" hint-placeholder-val="{{ false }}">\n  <div style="max-width:1120px');
  const end = skeleton.indexOf('</sc-if>\n</div>\n</x-dc>');
  if (vi < 0 || en < vi || end < en) throw new Error('skeleton: language panes not found');
  return [skeleton.slice(0, vi), skeleton.slice(vi, en), skeleton.slice(en, end + '</sc-if>'.length), skeleton.slice(end + '</sc-if>'.length)];
}

export function applyText(skeleton, page, texts, facts, pending) {
  const [head, vi, en, tail] = split(skeleton);
  const panes = { vi, en };
  const out = {};
  for (const lang of LANGS) {
    const data = texts[lang];
    out[lang] = renderPane(panes[lang], page, data, { lang, facts, pending });
  }
  let h = head;
  let t = tail;
  const titles = LANGS.map((l) => texts[l].title);
  h = rep(h, /<title>[^<]*<\/title>/, `<title>${titles[0]}</title>`);
  t = rep(t, /document\.title = this\.lang\(\) === 'en' \? "[^"]*" : "[^"]*"/, `document.title = this.lang() === 'en' ? "${titles[1]}" : "${titles[0]}"`);
  return h + out.vi + out.en + t;
}

export function loadTexts(root, page) {
  const texts = {};
  for (const lang of LANGS) texts[lang] = JSON.parse(fs.readFileSync(path.join(root, `docs/legal/public/${page}.${lang}.json`), 'utf8'));
  return texts;
}
