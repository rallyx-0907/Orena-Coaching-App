// <<LIB:common>>

// Code node "Parse words" - reads the list, detects each line's language, normalises the level, derives the deterministic id.
// Line format:  word - level [- Vietnamese meaning]   (separators: tab, an em/en dash, " - ", comma, semicolon, pipe)
const cfg = $('Config').first().json;
const words = [], inputIssues = [], seen = new Map();
String(cfg.input.text || '').split(/\r?\n/).forEach((raw, lineNo) => {
  const line = raw.trim();
  if (!line || line.startsWith('#')) return;
  const parts = line.split(/\t|\s+[—–]\s+|\s*[—–]\s*|\s+-\s+|\s*[,;|]\s*/).map(s => s.trim()).filter(Boolean);
  const word = parts[0];
  const lang = isCjk(word) ? 'zh-Hans' : 'en';
  const levelRaw = parts[1] || '';
  const level = normLevel(lang, levelRaw);
  const meaningVi = parts.slice(2).join(', ');
  const id = makeId(lang, word);
  if (seen.has(id)) { inputIssues.push({ line: lineNo + 1, word, issue: `same id as line ${seen.get(id)}; this line was ignored` }); return; }
  seen.set(id, lineNo + 1);
  words.push({ line: lineNo + 1, word, lang, level, levelRaw, meaningVi, id });
});
if (!words.length) throw new Error('The word list is empty');
return [{ json: { words, inputIssues, hasZh: words.some(w => w.lang === 'zh-Hans'), hasEn: words.some(w => w.lang === 'en') } }];
