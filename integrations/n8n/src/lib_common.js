// ===== Orena vocabulary generator | shared helpers (inlined into every Code node that needs them) =====
const TONE_MARKS = { a: 'āáǎà', e: 'ēéěè', i: 'īíǐì', o: 'ōóǒò', u: 'ūúǔù', 'ü': 'ǖǘǚǜ' };

function syllableToMark(syl) {
  const m = /^([A-Za-zü:]+)([1-5])$/.exec(syl);
  if (!m) return syl.replace(/u:/g, 'ü').replace(/v/g, 'ü');
  const body = m[1].replace(/u:/g, 'ü').replace(/U:/g, 'Ü').replace(/v/g, 'ü');
  const tone = +m[2];
  if (tone === 5) return body;
  const low = body.toLowerCase();
  let idx;
  if (low.includes('a')) idx = low.indexOf('a');
  else if (low.includes('e')) idx = low.indexOf('e');
  else if (low.includes('ou')) idx = low.indexOf('o');
  else idx = Math.max(...['i', 'o', 'u', 'ü'].map(v => low.lastIndexOf(v)));
  if (idx < 0) return body;
  let mk = TONE_MARKS[low[idx]][tone - 1];
  if (body[idx] !== low[idx]) mk = mk.toUpperCase();
  return body.slice(0, idx) + mk + body.slice(idx + 1);
}

function joinSyllables(arr) {
  let out = '';
  arr.forEach((s, i) => {
    if (i && s && 'aeo'.includes(s.normalize('NFD')[0].toLowerCase())) out += "'";
    out += s;
  });
  return out;
}

function slug(s) { return String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }

function fnv1a(str) {
  let h = 0x811c9dc5;
  for (const ch of String(str)) { h ^= ch.codePointAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, '0');
}

const CJK_RE = /[\u3400-\u9fff\uf900-\ufaff]/;
function isCjk(s) { return CJK_RE.test(s); }

// Deterministic id, a function of the language and the headword only (never of the run, the time or the order):
// a rerun with the same input yields the same ids. The id pattern of the repo schema is ^[a-z]{2}(-[A-Za-z]+)?:[a-z0-9_-]+$.
// Orena itself keys an entry by (language, term, first part of speech); this id is its editorial handle (provenance.source_id).
function makeId(lang, word) {
  if (lang === 'zh-Hans') return 'zh-Hans:' + Array.from(String(word).trim()).map(c => c.codePointAt(0).toString(16)).join('-');
  const w = String(word).trim();
  const s = slug(w);
  const clean = /^[a-z0-9]+(?:[ '-][a-z0-9]+)*$/i.test(w);
  return 'en:' + ((s && clean) ? s : (s ? s + '-' : 'w-') + fnv1a(w.toLowerCase()).slice(0, 6));
}

function normLevel(lang, raw) {
  let v = String(raw || '').trim().toUpperCase().replace(/\s+/g, '');
  if (!v) return null;
  if (lang === 'zh-Hans') {
    v = v.replace(/^HSK/, '');
    if (/^[789]$|^7-9$|^7–9$/.test(v)) return '7-9';
    return /^[1-6]$/.test(v) ? v : null;
  }
  v = v.replace(/^CEFR/, '');
  return /^(A1|A2|B1|B2|C1|C2)$/.test(v) ? v : null;
}

function cleanGlosses(glosses, limit = 3) {
  const out = [];
  for (let g of glosses || []) {
    if (/^(CL:|variant of|old variant|see |also written|surname )/.test(g)) continue;
    g = g.replace(/\s*\[[^\]]*\]/g, '').replace(/\|[^\s,;)]+/g, '').trim();
    if (g) out.push(g);
  }
  return out.slice(0, limit);
}

function measureWords(glosses) {
  const res = [];
  for (const g of glosses || []) {
    const m = /^CL:(.*)$/.exec(g);
    if (!m) continue;
    const re = /([^\s,|\[]+?)(?:\|([^\s,\[]+))?\[([^\]]+)\]/g;
    let mm;
    while ((mm = re.exec(m[1]))) res.push({ mw: mm[2] || mm[1], pinyin: joinSyllables(mm[3].split(/\s+/).map(syllableToMark)) });
  }
  return res;
}

// lookup.cedict[simp] = [[pinyinWithToneNumbers, [glosses...]], ...]
function pickEntry(entries) {
  if (!entries || !entries.length) return null;
  return entries.find(e => e[0] && /^[a-z]/.test(e[0])) || entries[0];
}

function kangxiRadicalChar(rs) {
  const n = parseInt(String(rs || '').split(/\s+/)[0].split('.')[0], 10);
  if (!(n >= 1 && n <= 214)) return null;
  return String.fromCodePoint(0x2F00 + n - 1).normalize('NFKC');
}

function components(decomp) { return Array.from((decomp || '').replace(/[\u2FF0-\u2FFF？?]/g, '')); }

const ZH_PUNCT = { '。': '.', '，': ',', '、': ',', '？': '?', '！': '!', '：': ':', '；': ';', '“': '"', '”': '"', '（': '(', '）': ')', '《': '"', '》': '"' };

// Sentence pinyin: longest-match segmentation over CC-CEDICT; the headword is always one word.
// Returns ['', headPy] when any CJK character is unknown, so no half-guessed reading is ever written.
function sentencePinyin(text, headword, cedict) {
  const wordPy = w => { const e = pickEntry(cedict[w]); return e ? joinSyllables(e[0].split(/\s+/).map(syllableToMark)) : null; };
  const headPy = wordPy(headword) || '';
  const tokens = [];
  let unknown = false;
  text.split(headword).forEach((seg, si) => {
    if (si) tokens.push(headPy || headword);
    const chars = Array.from(seg);
    let i = 0;
    while (i < chars.length) {
      let done = false;
      for (let L = Math.min(8, chars.length - i); L > 0; L--) {
        const p = wordPy(chars.slice(i, i + L).join(''));
        if (p) { tokens.push(p); i += L; done = true; break; }
      }
      if (!done) {
        const ch = chars[i];
        if (ZH_PUNCT[ch]) tokens.push('\u0000' + ZH_PUNCT[ch]);
        else if (/\s/.test(ch)) { /* drop whitespace */ }
        else { tokens.push(ch); if (isCjk(ch)) unknown = true; }
        i++;
      }
    }
  });
  let out = '';
  for (const t of tokens) out += t.startsWith('\u0000') ? t.slice(1) : (out && !/["(]$/.test(out) ? ' ' : '') + t;
  out = out.trim();
  if (unknown || !headPy) return ['', headPy];
  return [out ? out[0].toUpperCase() + out.slice(1) : '', headPy];
}

// Tatoeba api_v0: results[].translations[][]; newer API: data[].translations[]
function parseTatoeba(raw) {
  let o; try { o = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch (e) { return []; }
  const arr = (o && (o.results || o.data)) || [];
  return arr.map(r => {
    const tr = [];
    const walk = x => {
      if (Array.isArray(x)) x.forEach(walk);
      else if (x && typeof x === 'object') { if (x.lang === 'vie' && x.text) tr.push(x.text); if (x.translations) walk(x.translations); }
    };
    walk(r.translations);
    return { text: String(r.text || '').trim(), vi: tr[0] || '', source: 'tatoeba' };
  }).filter(x => x.text);
}

function pickExamples(cands, matchFn, max) {
  const seen = new Set();
  return cands
    .filter(c => { if (seen.has(c.text)) return false; seen.add(c.text); return c.text.length >= 4 && c.text.length <= 120 && matchFn(c.text); })
    .sort((a, b) => (!a.vi - !b.vi) || (Math.abs(a.text.length - 35) - Math.abs(b.text.length - 35)) || (a.text < b.text ? -1 : a.text > b.text ? 1 : 0))
    .slice(0, max);
}

function parseJsonSafe(raw) { try { return typeof raw === 'string' ? JSON.parse(raw) : raw; } catch (e) { return null; } }
function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

// An IPA transcription as the card stores it: slash-delimited ("/rɪˈzɪliənt/"). A bare transcription is wrapped;
// anything else (brackets, empty) is returned unchanged so the validator rejects it rather than the workflow guessing.
function normIpa(s) {
  const t = String(s || '').trim();
  if (!t) return '';
  if (/^\/[^\/]+\/$/.test(t)) return t;
  if (/^[\[(]/.test(t) || /[\])]$/.test(t) || t.includes('/')) return t;
  return '/' + t + '/';
}

const POS_CODES = ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'preposition', 'conjunction', 'determiner', 'interjection', 'numeral', 'measure_word', 'particle', 'phrase', 'idiom'];
const POS_VI = { noun: 'danh từ', verb: 'động từ', adjective: 'tính từ', adverb: 'trạng từ', pronoun: 'đại từ', preposition: 'giới từ',
  conjunction: 'liên từ', interjection: 'thán từ', determiner: 'từ hạn định', numeral: 'số từ', measure_word: 'lượng từ', particle: 'trợ từ',
  phrase: 'cụm từ', idiom: 'thành ngữ' };
const POS_ZH = { noun: '名词', verb: '动词', adjective: '形容词', adverb: '副词', pronoun: '代词', preposition: '介词', conjunction: '连词',
  interjection: '叹词', numeral: '数词', measure_word: '量词', particle: '助词', phrase: '短语', idiom: '成语' };
const posObj = (code, lang) => ({ code, label_native: lang === 'zh-Hans' ? (POS_ZH[code] || code) : code, label_vi: POS_VI[code] || code });
// ===== end of shared helpers =====
