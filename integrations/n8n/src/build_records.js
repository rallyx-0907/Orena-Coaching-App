// <<LIB:common>>

// Code node "Build records" - assembles the deterministic data (Free Dictionary, Tatoeba, CC-CEDICT, CVDICT, Unihan,
// Make Me a Hanzi) into the card shape of docs/vocab/vocab_entry.schema.json and records what is still missing (gaps).
// Nothing here is invented: a field the sources do not give stays absent and becomes a gap (AI fills it, or the word is rejected).
const cfg = $('Config').first().json;
const words = $('Words').all().map(i => i.json);
const call1 = $('Enrich call 1').all().map(i => i.json);
const call2 = $input.all().map(i => i.json);
let L = null;
try { const p = $('Parse ZH lookup').first().json.data; L = (p && p.lookup) || p; } catch (e) { L = null; }

const POS_EN = { noun: 'noun', verb: 'verb', adjective: 'adjective', adverb: 'adverb', pronoun: 'pronoun', preposition: 'preposition',
  conjunction: 'conjunction', interjection: 'interjection', exclamation: 'interjection', determiner: 'determiner', article: 'determiner',
  numeral: 'numeral', number: 'numeral', phrase: 'phrase', idiom: 'idiom' };
const dataOf = j => (j && j.data !== undefined ? j.data : null);

let sortedKeys = null;
const lowerBound = (arr, x) => { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] < x) lo = m + 1; else hi = m; } return lo; };
const out = [];
words.forEach((w, i) => {
  const warnings = [], errors = [];
  const tags = new Set(['gen:n8n-vocab-generator']);
  const rec = { id: w.id, lang: w.lang, headword: w.word };
  if (w.level) rec.level = { scale: w.lang === 'en' ? 'CEFR' : 'HSK3', value: w.level, source: w.lang === 'en' ? cfg.record.levelSourceEN : cfg.record.levelSourceZH };
  else errors.push(w.levelRaw ? `level "${w.levelRaw}" is not a valid ${w.lang === 'en' ? 'CEFR (A1-C2)' : 'HSK (1-6, 7-9)'} level` : 'the level is missing');
  rec.pos = []; rec.meanings = []; rec.examples = [];
  let cands = [];

  if (w.lang === 'en') {
    const d1 = dataOf(call1[i]);
    const parsed = parseJsonSafe(d1);
    const entries = Array.isArray(parsed) ? parsed : [];
    const call1Err = call1[i] && call1[i].error;
    if (call1Err) warnings.push('Free Dictionary request failed: ' + String((call1Err && (call1Err.message || call1Err.description)) || call1Err).slice(0, 200));
    else if (!entries.length) warnings.push('Free Dictionary: no entry' + (parsed && parsed.title ? ` (${String(parsed.title).slice(0, 80)})` : ''));
    else tags.add('src:free-dictionary');
    const ipa = {}; let untagged = '';
    const syn = [], ant = [];
    for (const e of entries) {
      for (const p of e.phonetics || []) {
        const a = p.audio || '';
        if (p.text && /-uk\.mp3$/.test(a) && !ipa.uk) ipa.uk = normIpa(p.text);
        else if (p.text && /-us\.mp3$/.test(a) && !ipa.us) ipa.us = normIpa(p.text);
        else if (p.text && !untagged) untagged = p.text;
      }
      if (e.phonetic && !untagged) untagged = e.phonetic;
      for (const m of e.meanings || []) {
        const code = POS_EN[(m.partOfSpeech || '').toLowerCase()];
        if (code && !rec.pos.some(p => p.code === code)) rec.pos.push(posObj(code, 'en'));
        const d0 = (m.definitions || [])[0];
        if (d0 && rec.meanings.length < 2) rec.meanings.push({ vi: '', en: d0.definition });
        syn.push(...(m.synonyms || [])); ant.push(...(m.antonyms || []));
        for (const d of m.definitions || []) {
          syn.push(...(d.synonyms || [])); ant.push(...(d.antonyms || []));
          if (d.example) cands.push({ text: d.example.replace(/^["“]|["”]$/g, ''), vi: '', source: 'dictionary' });
        }
      }
    }
    if (!ipa.uk && !ipa.us && untagged && ['uk', 'us'].includes(cfg.untaggedIpaAs)) { ipa[cfg.untaggedIpaAs] = normIpa(untagged); warnings.push(`IPA is not tagged UK/US; assigned to ${cfg.untaggedIpaAs}`); }
    if (entries.length && !ipa.uk && !ipa.us) {
      warnings.push(untagged
        ? `Free Dictionary: IPA ${untagged} is not tagged UK/US, so it was not used (set untaggedIpaAs in Config to use it)`
        : 'Free Dictionary: the entry has no IPA text');
    }
    rec.en = Object.keys(ipa).length ? { ipa } : {};
    // The dictionary's audio file is a third-party URL; the card plays text-to-speech instead of hot-linking it.
    rec.audio = { tts: true };
    const rel = [];
    [...new Set(syn)].filter(s => s.toLowerCase() !== w.word.toLowerCase()).slice(0, 3).forEach(s => rel.push({ word: s, relation: 'synonym' }));
    [...new Set(ant)].slice(0, 3).forEach(s => rel.push({ word: s, relation: 'antonym' }));
    if (rel.length) rec.related = rel;
    cands = parseTatoeba(dataOf(call2[i])).concat(cands);
    const re = new RegExp('\\b' + escRe(w.word) + '\\b', 'i');
    const picked = pickExamples(cands, t => re.test(t), cfg.record.maxExamples);
    picked.forEach(c => tags.add('src:' + (c.source === 'tatoeba' ? 'tatoeba' : 'free-dictionary')));
    rec.examples = picked.map(c => ({ text: c.text, highlight: { match: re.exec(c.text)[0] }, translation_vi: c.vi }));
  } else {
    if (!L || !L.cedict) { errors.push('the Chinese dictionary (zh_lookup.json) could not be read'); L = { cedict: {}, cvdict: {}, hanzi: {}, unihan: {} }; }
    const { cedict, cvdict, hanzi, unihan } = L;
    const entries = cedict[w.word] || [];
    const e = pickEntry(entries);
    if (!e) warnings.push('CC-CEDICT: no entry');
    else { tags.add('src:cc-cedict'); tags.add('src:unihan'); tags.add('src:makemeahanzi'); }
    if (entries.length > 1) warnings.push('CC-CEDICT has several readings; the first was chosen');
    const syl = e ? e[0].split(/\s+/).map(syllableToMark) : [];
    const chars = Array.from(w.word).map((ch, k) => {
      const u = unihan[ch] || ['', '', '', ''];
      const c = { hanzi: ch, pinyin: syl.length === Array.from(w.word).length ? syl[k] : '' };
      if (u[2]) c.han_viet = u[2].split(/\s+/)[0].toUpperCase();
      if (u[1]) c.strokes = parseInt(u[1], 10);
      const rad = kangxiRadicalChar(u[0]) || (hanzi[ch] || [])[1];
      if (rad) {
        const ru = unihan[rad] || ['', '', '', ''];
        const r = { char: rad };
        if (ru[3]) r.pinyin = ru[3].split(/\s+/)[0];
        if (ru[2]) r.name_vi = ru[2].split(/\s+/)[0].replace(/^./, s => s.toUpperCase());
        const g = cleanGlosses(cvdict[rad], 1);
        if (g.length) r.meaning_vi = g[0];
        c.radical = r;
      }
      const comp = components((hanzi[ch] || [])[0]);
      if (comp.length) c.components = comp;
      return c;
    });
    rec.zh = { pinyin: syl.length ? joinSyllables(syl) : '', chars };
    const hv = chars.map(c => c.han_viet || '');
    if (hv.every(Boolean)) rec.zh.han_viet = hv.join(' ');
    const mws = e ? measureWords(e[1]) : [];
    if (mws.length) rec.zh.measure_words = mws;
    const viGloss = cleanGlosses(cvdict[w.word]).join('; ');
    const enGloss = e ? cleanGlosses(e[1]).join('; ') : '';
    if (viGloss) tags.add('src:cvdict');
    if (viGloss || enGloss) rec.meanings.push(enGloss ? { vi: viGloss, en: enGloss } : { vi: viGloss });
    // CC-CEDICT has no part of speech, so it is inferred from the gloss shape - and said so.
    const g0 = e ? (cleanGlosses(e[1], 1)[0] || '') : '';
    if (/^to /i.test(g0)) { rec.pos.push(posObj('verb', 'zh-Hans')); warnings.push('pos inferred from the gloss "to ..." (CC-CEDICT)'); }
    else if (/^classifier/i.test(g0)) { rec.pos.push(posObj('measure_word', 'zh-Hans')); warnings.push('pos inferred from "classifier" (CC-CEDICT)'); }
    else if (e && e[1].some(g => /^CL:/.test(g))) { rec.pos.push(posObj('noun', 'zh-Hans')); warnings.push('pos = noun because CC-CEDICT lists a classifier (CL:)'); }
    cands = parseTatoeba(dataOf(call1[i])).concat(parseTatoeba(dataOf(call2[i])));
    const picked = pickExamples(cands, t => t.includes(w.word), cfg.record.maxExamples);
    if (picked.length) tags.add('src:tatoeba');
    rec.examples = picked.map(c => {
      const ex = { text: c.text, highlight: { match: w.word }, translation_vi: c.vi };
      const [reading, headPy] = sentencePinyin(c.text, w.word, cedict);
      if (reading) { ex.reading = reading; if (headPy && reading.includes(headPy)) ex.reading_highlight = { match: headPy }; }
      return ex;
    });
    if (rec.examples.some(x => x.reading)) warnings.push('sentence pinyin was generated from CC-CEDICT');
    const rel = [];
    if (e) {
      if (!sortedKeys) sortedKeys = Object.keys(cedict).sort();
      const keys = [];
      for (let k = lowerBound(sortedKeys, w.word); k < sortedKeys.length && sortedKeys[k].startsWith(w.word) && keys.length < 3; k++)
        if (sortedKeys[k] !== w.word && Array.from(sortedKeys[k]).length <= Array.from(w.word).length + 2) keys.push(sortedKeys[k]);
      for (const k of keys) {
        let [rd] = sentencePinyin(k, w.word, cedict);
        if (!rd) rd = joinSyllables(pickEntry(cedict[k])[0].split(/\s+/).map(syllableToMark));
        const it = { word: k, relation: 'compound', reading: rd[0].toLowerCase() + rd.slice(1) };
        const g = cleanGlosses(cvdict[k], 1); if (g.length) it.gloss_vi = g[0];
        rel.push(it);
      }
    }
    if (rel.length) rec.related = rel;
  }

  // The Vietnamese meaning typed on the input line wins over any source.
  if (w.meaningVi) {
    if (rec.meanings.length) rec.meanings[0].vi = w.meaningVi; else rec.meanings.push({ vi: w.meaningVi });
    tags.add('src:operator-meaning');
  }
  rec.status = cfg.record.status;
  rec.tags = [...tags].sort();

  const gaps = [];
  if (!rec.pos.length) gaps.push('pos');
  if (!rec.meanings.some(m => m.vi)) gaps.push('meaning_vi');
  if (!rec.examples.length) gaps.push('examples');
  rec.examples.forEach((x, k) => { if (!x.translation_vi) gaps.push('translation_vi:' + k); });
  if (w.lang === 'en' && !(rec.en.ipa && (rec.en.ipa.uk || rec.en.ipa.us))) gaps.push('ipa');
  if (w.lang === 'zh-Hans' && !rec.zh.pinyin) errors.push('no pinyin (the word is not in CC-CEDICT)');
  out.push({ json: { word: w, record: rec, gaps, warnings, errors } });
});
return out;
