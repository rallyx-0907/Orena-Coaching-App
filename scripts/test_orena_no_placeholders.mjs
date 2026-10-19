// Gate (#155): no unresolved `{{ ... }}` template placeholder reaches the browser as live markup.
//
// The Landing is the design's own file, run by the design's template runtime (support.js), and its bindings
// (`points="{{ ot.mPts }}"`, `d="{{ sp.mFill }}"`, `width="{{ ... }}"`) are resolved in the browser by that
// runtime, not by the server. The browser parses the served HTML before the runtime runs, so a binding left in
// live SVG markup is a console error per attribute. The rule, by file type and render path:
//
//   - templates/orena/**/*.html are served verbatim (app.py `_page`, no Jinja): `{{` may appear only inside
//     `<script>` blocks (the runtime's logic) or inside the one inert `<template data-dc-inert>` that
//     scripts/build_public_pages.mjs wraps around the Landing's template, which the browser never validates and
//     which the runtime reads. Anywhere else it is a failure.
//   - the served runtime (static/orena/public/support.js) must read that inert template.
//   - static/orena/**/*.js and *.css are served verbatim and never templated: `{{` outside a comment is a failure.
//     (Comments may quote the design's bindings, e.g. "the source's `{{ tlLabel }}`".)
//   - the Landing declares an icon, so the browser does not ask for /favicon.ico (404).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const PLACEHOLDER = /\{\{[^}]*\}\}/;

function walk(dir, exts, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== 'vendor' && e.name !== 'node_modules') walk(p, exts, out); }
    else if (exts.includes(path.extname(e.name))) out.push(p);
  }
  return out;
}
const rel = (p) => p.split(path.sep).join('/');

// The markup a browser would parse as live DOM: scripts and the inert template removed.
function liveMarkup(html) {
  return html
    .replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<template data-dc-inert>[\s\S]*<\/template>/, '')
    .replace(/<!--[\s\S]*?-->/g, '');
}

// 1. Served templates.
const templates = walk('templates', ['.html']);
assert.ok(templates.length >= 5, 'the served templates are found (the shell, the Landing and three English-only legal pages, D-238)');
let inertSeen = 0;
for (const file of templates) {
  const html = fs.readFileSync(file, 'utf8');
  const live = liveMarkup(html);
  const hit = PLACEHOLDER.exec(live);
  assert.ok(!hit, `${rel(file)}: unresolved placeholder in live markup: ${hit && hit[0]} (context: ${hit && live.slice(Math.max(0, hit.index - 60), hit.index + 40).replace(/\s+/g, ' ')})`);
  if (/<template data-dc-inert>/.test(html)) {
    inertSeen += 1;
    assert.equal((html.match(/<template data-dc-inert>/g) || []).length, 1, `${rel(file)}: exactly one inert template`);
    assert.equal((html.match(/<\/template>\s*<\/x-dc>/g) || []).length, 1, `${rel(file)}: the inert template closes right before </x-dc>`);
  }
}
// The Landing carries bindings, so it must be the file that holds the inert template.
const landing = fs.readFileSync('templates/orena/public/landing.html', 'utf8');
assert.ok(PLACEHOLDER.test(landing), 'the Landing still carries the design bindings');
assert.equal(inertSeen, 1, 'the Landing is the one page with an inert template');
assert.ok(/<link rel="icon"[^>]*href="\/orena-brand\/logo\/orena-mark\.svg"/.test(landing), 'the Landing declares the brand icon (no /favicon.ico 404)');

// 2. The runtime reads the template from the inert element, from the parsed document and from refetched text.
const runtime = fs.readFileSync('static/orena/public/support.js', 'utf8');
assert.ok(runtime.includes('template[data-dc-inert]'), 'support.js reads the inert template from the document');
assert.ok(runtime.includes('<template data-dc-inert>'), 'support.js unwraps the inert template from refetched text');

// 3. Served scripts and styles are never templated.
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1');
for (const file of walk('static/orena', ['.js', '.mjs', '.css'])) {
  if (rel(file) === 'static/orena/public/support.js') continue; // the runtime itself parses `{{ }}` by design
  const hit = PLACEHOLDER.exec(stripComments(fs.readFileSync(file, 'utf8')));
  assert.ok(!hit, `${rel(file)}: unresolved placeholder outside a comment: ${hit && hit[0]}`);
}

console.log('ok: no unresolved {{ }} placeholder reaches live markup (templates, runtime, static scripts and styles)');
