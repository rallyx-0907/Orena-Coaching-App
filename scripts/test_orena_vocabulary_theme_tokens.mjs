import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';

const css = readFileSync(new URL('../static/orena/world.css', import.meta.url), 'utf8');
const themeCss = readFileSync(new URL('../static/orena/theme.css', import.meta.url), 'utf8');

function rule(source, selector) {
  const start = source.indexOf(`${selector} {`);
  assert.notEqual(start, -1, `missing CSS rule: ${selector}`);
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    if (source[index] === '}') depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  throw new Error(`unterminated CSS rule: ${selector}`);
}

const vocabularyStart = css.indexOf('/* Vocabulary redesign:');
const libraryStart = css.indexOf('/* Shared Reading Library:');
assert.ok(vocabularyStart >= 0 && libraryStart > vocabularyStart, 'vocabulary CSS scope is present');
const vocabularyCss = css.slice(vocabularyStart, libraryStart);

for (const selector of ['.vocabulary-collection-card', '.vocabulary-browse-card', '.vocabulary-study-card']) {
  const block = rule(vocabularyCss, selector);
  assert.match(block, /background:\s*var\(--surface\);/, `${selector} uses the Orena surface token`);
  assert.doesNotMatch(
    block,
    /background:[^;]*--vocabulary-level-color/,
    `${selector} does not turn the rank accent into a separate background palette`,
  );
}

const browse = rule(vocabularyCss, '.vocabulary-browse-card');
assert.doesNotMatch(browse, /--vocabulary-level-wash/, 'browse cards do not carry a rank wash palette');
const stars = rule(vocabularyCss, '.vocabulary-browse-card__status .vocabulary-stars');
assert.match(stars, /color:\s*var\(--accent\);/, 'mastery stars use the semantic accent');
assert.doesNotMatch(vocabularyCss, /outline:\s*\d+px solid var\(--sun\)/, 'focus rings do not use a decorative sun token');

for (const themeName of ['paper', 'night-ink', 'deep-forest', 'sage-field']) {
  const start = themeCss.indexOf(`[data-theme='${themeName}']`);
  assert.notEqual(start, -1, `${themeName} is registered in the theme token owner`);
  const end = themeCss.indexOf('}', start);
  const block = themeCss.slice(start, end);
  for (const token of ['--surface', '--ink', '--muted', '--line', '--accent', '--coral', '--sun', '--sage']) {
    assert.match(block, new RegExp(`${token}:`), `${themeName} provides ${token} for vocabulary visuals`);
  }
}

for (const ui of ['en', 'zh']) {
  for (const key of ['vocabularyTitle', 'vocabularyLibraryTitle', 'vocabularyFeedTitle', 'vocabularyStudy', 'vocabularySave']) {
    assert.ok(copy[ui][key], `${ui}.${key} keeps vocabulary copy parity`);
  }
}

console.log('Orena Vocabulary visual tokens: semantic surfaces, light rank accents, four themes, EN/ZH parity PASS');
