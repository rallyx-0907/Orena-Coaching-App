// Static, script-free legal pages (Terms, Privacy, Delete account), D-161.
//
// The whole text is in the HTML response: a crawler or a store reviewer without JavaScript reads everything. The
// markup is the pinned design's, taken from the page that public_legal_text.mjs fills; what the design's runtime did
// with bindings is done with CSS and links instead: the two-language switch is two links (?lang=), the wide and
// narrow layouts are a media query, hover is :hover, and the contents list highlights the section being read with a
// small optional script (the page reads the same without it). Neither the design runtime nor React is loaded.
import { LANGS, PAGE_HREF, must, rep, split } from './public_legal_text.mjs';

export const LANG_QUERY = { vi: '', en: '?lang=en' };

const STATIC_CSS = `
.lg-layout{flex-direction:column}
.lg-toc{width:100%;position:static}
@media (min-width:900px){.lg-layout{flex-direction:row}.lg-toc{width:240px;position:sticky}}
.lg-toc a.on{color:var(--text)!important;background:var(--surface)!important}
`;

// Optional: highlight the contents entry of the section being read. Nothing depends on it.
const ENHANCE = `(function(){try{
var secs=document.querySelectorAll('[data-sec]'),links=document.querySelectorAll('.lg-toc a[href^="#s"]');
if(!secs.length||!links.length)return;
function on(){var act='1';secs.forEach(function(el){if(el.getBoundingClientRect().top<160)act=el.getAttribute('data-sec')});
links.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#s'+act)})}
document.addEventListener('scroll',on,{passive:true,capture:true});on();}catch(e){}})();`;

const attr = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;');

export function staticPage(filled, page, lang, texts) {
  const [head, vi, en] = split(filled);
  let pane = lang === 'vi' ? vi : en;
  const data = texts[lang];

  // Hover: `style-hover="X"` becomes a data attribute and one :hover rule per distinct value.
  const hovers = [];
  const hoverId = (v) => { let i = hovers.indexOf(v); if (i < 0) { hovers.push(v); i = hovers.length - 1; } return i; };
  const toHover = (s) => s.replace(/ style-hover="([^"]*)"/g, (_m, v) => ` data-h="${hoverId(v)}"`);

  // Header: the language switch is two links; the "Open Orena" label is the page's language.
  let header = must(/<header [\s\S]*?<\/header>/, head, 'header')[0];
  const here = PAGE_HREF[page];
  const toggle = must(/<div style="display:flex;padding:3px;border-radius:11px;background:var\(--surface\);gap:2px;flex:none">[\s\S]*?<\/div>/, header, 'language switch')[0];
  const linkStyle = (on) => `height:32px;padding:0 10px;border-radius:8px;display:flex;align-items:center;justify-content:center;background:${on ? 'var(--accent-soft)' : 'transparent'};color:${on ? 'var(--text)' : 'var(--muted)'};font-family:inherit;font-size:13px;font-weight:600`;
  header = rep(header, toggle,
    '<div style="display:flex;padding:3px;border-radius:11px;background:var(--surface);gap:2px;flex:none">'
    + `<a href="${here}" hreflang="vi" aria-label="Tiếng Việt" style="${linkStyle(lang === 'vi')}">VI</a>`
    + `<a href="${here}?lang=en" hreflang="en" aria-label="English" style="${linkStyle(lang === 'en')}">EN</a></div>`);
  header = header.replace(/<sc-if value="\{\{ isVi \}\}"[^>]*>([^<]*)<\/sc-if><sc-if value="\{\{ isEn \}\}"[^>]*>([^<]*)<\/sc-if>/, (_m, v, e) => (lang === 'vi' ? v : e));
  header = toHover(header);

  // The pane: bindings become static values.
  pane = pane.replace(/[ \t]*<\/?sc-if[^>]*>\r?\n?/g, '');
  pane = rep(pane, 'flex-direction:{{ layoutDir }};', '');
  pane = rep(pane, '<div style="max-width:1120px;margin:0 auto;padding:clamp(36px,6vh,56px) clamp(16px,4vw,48px) clamp(56px,10vh,110px);display:flex;gap:',
    '<div class="lg-layout" style="max-width:1120px;margin:0 auto;padding:clamp(36px,6vh,56px) clamp(16px,4vw,48px) clamp(56px,10vh,110px);display:flex;gap:');
  pane = rep(pane, '<aside style="flex:0 0 240px;width:{{ tocWidth }};position:{{ tocPos }};top:96px;', '<aside class="lg-toc" style="flex:0 0 240px;top:96px;');
  pane = pane.replace(/color:\{\{ a\.s\d+ \}\};background:\{\{ b\.s\d+ \}\}">/g, 'color:var(--muted);background:transparent">');
  pane = rep(pane, '<a href="#s1" style=', '<a href="#s1" class="on" style=');
  pane = toHover(pane);

  // The logo symbol only: the design's animated Orena Intelligence mark is not drawn on these pages.
  const svg = must(/<svg width="0" height="0"[\s\S]*?<\/svg>/, head, 'logo symbols')[0]
    .replace(/<radialGradient id="ol-g12"[\s\S]*?<\/symbol>(?=<\/defs>)/, '');
  const root = must(/<div data-screen-label="[^"]*" style="[^"]*">/, head, 'page root')[0];
  const baseStyle = must(/<style>([\s\S]*?)<\/style>/, head, 'base style')[1];
  const hoverCss = hovers.map((v, i) => `[data-h="${i}"]:hover{${v}}`).join('\n');
  const other = LANGS.find((l) => l !== lang);
  const desc = data.intro.replace(/\{\{[^}]*\}\}/g, '').replace(/[*[\]]|\([^)]*\)/g, '');
  const out = `<!doctype html>
<html lang="${lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${data.title}</title>
<meta name="description" content="${attr(desc)}">
<link rel="icon" type="image/svg+xml" href="/orena-brand/logo/orena-mark.svg">
<link rel="alternate" hreflang="${lang}" href="${here}${LANG_QUERY[lang]}">
<link rel="alternate" hreflang="${other}" href="${here}${LANG_QUERY[other]}">
<link href="/orena-assets/fonts/fonts.css" rel="stylesheet">
<style>${baseStyle}${STATIC_CSS}${hoverCss}
</style>
</head>
<body>
${svg}
${root}

  ${header}

${pane.replace(/^\s+/, '  ')}
</div>
<script>${ENHANCE}</script>
</body>
</html>
`;
  if (/\{\{\s*[a-zA-Z]/.test(out) || /sc-if|style-hover|<x-dc|<helmet|support\.js/.test(out)) {
    throw new Error(`${page}.${lang}: a design binding survived in the static page`);
  }
  return out;
}
