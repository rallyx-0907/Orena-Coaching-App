// <<LIB:common>>
// <<LIB:validate>>

// Code node "Validate & group" - applies the AI fill-gap answers (only into the gaps asked for), validates every record
// STRICTLY against the repo schema plus the admission rules, splits READY / REJECTED, and groups READY by language into
// one import file each. An invalid record is rejected with its reasons; it is never downgraded and carried on.
const cfg = $('Config').first().json;
const built = $('Build records').all().map(i => JSON.parse(JSON.stringify(i.json)));
let cedict = {};
try { const p = $('Parse ZH lookup').first().json.data; cedict = ((p && p.lookup) || p || {}).cedict || {}; } catch (e) {}
const inputIssues = $('Parse words').first().json.inputIssues || [];
const aiTag = (r, field) => { r.tags = [...new Set([...(r.tags || []), 'ai-filled:' + field])].sort(); };

// The model's answer: `content` first. A reasoning model may leave `content` empty and put its answer in `reasoning` /
// `reasoning_content`: that is used ONLY if the first complete JSON object in it parses (no other scraping).
function firstJsonObject(text) {
  const s = String(text || ''); const start = s.indexOf('{');
  if (start < 0) return null;
  let depth = 0, inStr = false, esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true; else if (c === '{') depth++; else if (c === '}' && --depth === 0) { const o = parseJsonSafe(s.slice(start, i + 1)); return o && typeof o === 'object' && !Array.isArray(o) ? o : null; }
  }
  return null;
}
function pickAiAnswer(resp) {
  const clip = v => String(typeof v === 'string' ? v : JSON.stringify(v)).replace(/\s+/g, ' ').slice(0, 160);
  const msg = resp && resp.choices && resp.choices[0] && resp.choices[0].message;
  if (!msg) return { problem: 'AI answer has no choices: ' + clip(resp) };
  const content = msg.content;
  if (typeof content === 'string' && content.trim()) {
    const o = parseJsonSafe(content.replace(/^```(?:json)?\s*|\s*```$/g, '').trim());
    if (o && typeof o === 'object' && !Array.isArray(o)) return { answer: o };
    return { problem: 'AI did not return a JSON object: ' + clip(content) };
  }
  if (content && typeof content === 'object' && !Array.isArray(content)) return { answer: content };
  for (const k of ['reasoning', 'reasoning_content']) {
    const o = typeof msg[k] === 'string' ? firstJsonObject(msg[k]) : null;
    if (o) return { answer: o };
  }
  return { problem: 'AI returned no content (reasoning-only model? choose a non-reasoning model that supports response_format)' };
}

// ---- 1. AI answers (gap fill only; the AI never overwrites a value that exists) ----
const first = $input.first().json;
if (!first.noop) {
  const jobs = $('Prepare AI').all().map(i => i.json);
  $input.all().forEach((it, k) => {
    const job = jobs[k]; if (!job) return;
    const b = built[job.recIndex]; const r = b.record;
    if (it.json.error) { b.warnings.push('AI request failed: ' + String((it.json.error && (it.json.error.message || it.json.error.description)) || it.json.error).slice(0, 200)); return; }
    const status = it.json.statusCode;
    const rawBody = it.json.body !== undefined ? it.json.body : it.json.data;
    if (Number.isInteger(status) && (status < 200 || status >= 300)) {
      b.warnings.push(`AI request failed: HTTP ${status}: ${String(typeof rawBody === 'string' ? rawBody : JSON.stringify(rawBody)).replace(/\s+/g, ' ').slice(0, 200)}`);
      return;
    }
    const resp = parseJsonSafe(rawBody);
    if (resp && resp.error) {
      const e = resp.error;
      b.warnings.push('AI request failed: ' + String((typeof e === 'string' ? e : e.message) || JSON.stringify(e)).slice(0, 160) + (e && e.code !== undefined ? ` (code ${String(e.code).slice(0, 40)})` : ''));
      return;
    }
    if (!resp || typeof resp !== 'object') { b.warnings.push('AI did not return JSON: ' + String(typeof rawBody === 'string' ? rawBody : JSON.stringify(rawBody)).replace(/\s+/g, ' ').slice(0, 160)); return; }
    const picked = pickAiAnswer(resp);
    const ai = picked.answer;
    if (!ai) { b.warnings.push(picked.problem); return; }
    if (job.want.includes('pos') && !r.pos.length && Array.isArray(ai.pos)) {
      const codes = [...new Set(ai.pos.map(x => String(x).toLowerCase().trim()))].filter(c => POS_CODES.includes(c));
      if (codes.length) { r.pos = codes.map(c => posObj(c, r.lang)); aiTag(r, 'pos'); b.warnings.push('AI filled: pos'); }
    }
    if (job.want.includes('meaning_vi') && typeof ai.meaning_vi === 'string' && ai.meaning_vi.trim() && ai.meaning_vi.length <= 200) {
      if (!r.meanings.length) { r.meanings.push({ vi: ai.meaning_vi.trim() }); aiTag(r, 'meaning_vi'); b.warnings.push('AI filled: meanings[0].vi'); }
      else if (!r.meanings[0].vi) { r.meanings[0].vi = ai.meaning_vi.trim(); aiTag(r, 'meaning_vi'); b.warnings.push('AI filled: meanings[0].vi'); }
    }
    if (job.want.includes('translations_vi') && ai.translations_vi && typeof ai.translations_vi === 'object') {
      for (const [k2, v] of Object.entries(ai.translations_vi)) {
        const ex = r.examples[+k2];
        if (ex && !ex.translation_vi && typeof v === 'string' && v.trim()) { ex.translation_vi = v.trim(); aiTag(r, 'translation_vi'); b.warnings.push(`AI filled: examples[${k2}].translation_vi`); }
      }
    }
    if (job.want.includes('examples') && !r.examples.length && Array.isArray(ai.examples)) {
      for (const x of ai.examples) {
        if (r.examples.length >= cfg.record.maxExamples) break;
        if (!x || typeof x.text !== 'string' || typeof x.translation_vi !== 'string' || !x.translation_vi.trim()) continue;
        const text = x.text.trim();
        const match = r.lang === 'zh-Hans' ? (text.includes(r.headword) ? r.headword : null) : ((new RegExp('\\b' + escRe(r.headword) + '\\b', 'i').exec(text) || [])[0] || null);
        if (!match) continue;
        const ex = { text, highlight: { match }, translation_vi: x.translation_vi.trim() };
        if (r.lang === 'zh-Hans') {
          const [reading, headPy] = sentencePinyin(ex.text, r.headword, cedict);
          if (reading) { ex.reading = reading; if (headPy && reading.includes(headPy)) ex.reading_highlight = { match: headPy }; }
        }
        r.examples.push(ex);
        aiTag(r, 'examples');
        b.warnings.push(`AI filled: examples[${r.examples.length - 1}]`);
      }
    }
    if (job.want.includes('ipa') && ai.ipa && typeof ai.ipa === 'object' && r.en && !(r.en.ipa && Object.keys(r.en.ipa).length)) {
      const ipa = {};
      for (const acc of ['uk', 'us']) if (typeof ai.ipa[acc] === 'string' && ai.ipa[acc].trim()) ipa[acc] = normIpa(ai.ipa[acc]);
      if (Object.keys(ipa).length) { r.en.ipa = ipa; aiTag(r, 'ipa'); b.warnings.push('AI filled: en.ipa'); }
    }
  });
}

// ---- 2. Tidy and validate strictly ----
const ready = [], rejected = [];
for (const b of built) {
  const r = b.record;
  const meaningsBefore = (r.meanings || []).length;
  r.meanings = (r.meanings || []).filter(m => m.vi && m.vi.trim());
  if (r.meanings.length < meaningsBefore) b.warnings.push(`dropped ${meaningsBefore - r.meanings.length} meaning(s) without a Vietnamese text`);
  const before = r.examples.length;
  r.examples = (r.examples || []).filter(x => x.translation_vi && x.translation_vi.trim()).slice(0, cfg.record.maxExamples);
  if (r.examples.length < before) b.warnings.push(`dropped ${before - r.examples.length} example(s) without a Vietnamese translation`);
  if (r.related && !r.related.length) delete r.related;
  if (r.lang === 'en' && r.en && r.en.ipa && !Object.keys(r.en.ipa).length) delete r.en.ipa;
  const errs = [...b.errors, ...validateRecord(r, cfg.record.allowedStatuses)];
  if (errs.length) {
    const hint = cfg.ai.active ? '' : ' (AI off)';
    if (!r.pos.length) errs.unshift('no part of speech' + hint);
    if (!r.meanings.length) errs.unshift('no Vietnamese meaning' + (cfg.ai.active ? '' : ' (AI off; add it on the input line)'));
    if (!r.examples.length) errs.unshift('no example sentence with a Vietnamese translation' + hint);
    if (r.lang === 'en' && !(r.en && r.en.ipa)) errs.unshift('no IPA (uk/us)' + hint);
  }
  const row = { id: r.id, headword: r.headword, lang: r.lang, line: b.word.line, warnings: b.warnings };
  if (errs.length) rejected.push({ ...row, reasons: [...new Set(errs)], record: r });
  else ready.push({ ...row, record: r });
}

// ---- 3. One import file per language (collection id and file name are deterministic) ----
const langs = [...new Set(built.map(b => b.record.lang))].sort();
const multi = langs.length > 1;
const allIds = built.map(b => b.record.id).sort();
const groups = langs.map(lang => {
  const code = lang === 'zh-Hans' ? 'zh' : 'en';
  const rs = ready.filter(x => x.record.lang === lang).map(x => x.record).sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  let collection_id = slug(cfg.input.collectionId || '') || (cfg.input.title ? slug(cfg.input.title) : `${code}-batch-${fnv1a(allIds.filter(id => id.startsWith(lang + ':')).join('|'))}`);
  if (!collection_id) collection_id = `${code}-batch-${fnv1a(allIds.filter(id => id.startsWith(lang + ':')).join('|'))}`;
  if (multi && (cfg.input.collectionId || cfg.input.title)) collection_id += '-' + code;
  const title = (cfg.input.title || `Vocabulary ${code.toUpperCase()} ${collection_id}`) + (multi && cfg.input.title ? ` (${code.toUpperCase()})` : '');
  const metadata = { title, language_code: code, collection_id, rights_status: cfg.metadata.rights_status, completeness: cfg.metadata.completeness, provenance: { label: 'n8n-vocab-generator' } };
  const ext = cfg.orena.fileFormat === 'json' ? 'json' : 'jsonl';
  const fileContent = ext === 'json' ? JSON.stringify(rs, null, 2) : rs.map(x => JSON.stringify(x)).join('\n') + (rs.length ? '\n' : '');
  // Named by its content: the same input gives the same file name and bytes; changed input never overwrites an earlier file.
  const fileName = `${collection_id}.${fnv1a(fileContent)}.ready.${ext}`;
  return {
    lang, language_code: code, collection_id, title, metadata,
    fileName, readyPath: `${cfg.output.dir}/${fileName}`, fileContent,
    readyIds: rs.map(x => x.id), readyCount: rs.length,
    rejectedCount: rejected.filter(x => x.lang === lang).length,
  };
});

return [{ json: {
  groups,
  ready: ready.map(({ record, ...x }) => x),
  rejected,
  inputIssues,
} }];
