/* Linking words (frame 29 result tile "Linking", D-139 HD-9). One language-neutral contract,
   `countLinkers(text, language) -> number`, over a short, explicit, authored list of discourse
   linkers per learning language. Counting is deterministic and measures only what the transcript
   contains: it is a count of linking devices, not a score and not a judgement of their use.

   English (and any other Latin-script learning language falls back to English): whole words or
   phrases, case-insensitive, never inside a longer word ("so" is not counted in "also"). A phrase
   is matched as consecutive words ("for example", "as a result").
   Chinese: substring match on the Han text (Chinese has no spaces), longest linker first so
   "但是" is one linker, not "但" plus "是"; overlapping matches are not counted twice.

   Extending a language means adding a list here and nothing else. */

export const LINKERS = Object.freeze({
  en: Object.freeze([
    'because', 'so', 'but', 'and then', 'then', 'however', 'although', 'though', 'while', 'whereas',
    'first', 'firstly', 'second', 'secondly', 'next', 'after that', 'finally', 'lastly',
    'for example', 'for instance', 'such as', 'also', 'moreover', 'furthermore', 'besides',
    'therefore', 'as a result', 'in addition', 'on the other hand', 'in conclusion', 'actually',
    'instead', 'otherwise', 'meanwhile', 'since', 'unless', 'in fact',
  ]),
  zh: Object.freeze([
    '因为', '所以', '但是', '可是', '然而', '不过', '然后', '而且', '并且', '虽然', '尽管', '如果', '那么',
    '首先', '其次', '接着', '最后', '另外', '此外', '比如', '例如', '因此', '于是', '同时', '总之', '其实',
    '不但', '而是', '或者', '还有', '一方面', '另一方面',
  ]),
});

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function countEnglish(text, list) {
  // Longest phrase first so "and then" wins over "then"; a matched span is consumed.
  const ordered = [...list].sort((a, b) => b.length - a.length);
  const body = ordered.map((item) => escapeRegExp(item).replace(/ /g, '\\s+')).join('|');
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}'])(?:${body})(?![\\p{L}\\p{N}'])`, 'giu');
  return (String(text).match(pattern) || []).length;
}

function countHan(text, list) {
  const ordered = [...list].sort((a, b) => b.length - a.length);
  const pattern = new RegExp(ordered.map(escapeRegExp).join('|'), 'g');
  return (String(text).match(pattern) || []).length;
}

export function countLinkers(text, language) {
  const value = String(text || '');
  if (!value.trim()) return 0;
  if (language === 'zh') return countHan(value, LINKERS.zh);
  return countEnglish(value, LINKERS.en);
}
