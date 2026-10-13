// ===== Orena vocabulary generator | admission validator =====
// VOCAB_SCHEMA_TEXT is docs/vocab/vocab_entry.schema.json copied verbatim by build_workflow.py (never edited by hand).
// The validator below interprets that schema generically, so the rules cannot drift from the repo schema.
// <<SCHEMA>>

const _typeOf = v => Array.isArray(v) ? 'array' : v === null ? 'null' : Number.isInteger(v) ? 'integer' : typeof v;
const _cp = s => Array.from(s).length;

function _resolve(root, ref) {
  if (!ref.startsWith('#/')) throw new Error('unsupported $ref ' + ref);
  return ref.slice(2).split('/').reduce((o, k) => o[k], root);
}

// JSON Schema (2020-12 subset used by the Orena schema): type, enum, const, pattern, min/maxLength, minimum,
// min/maxItems, minProperties, required, properties, additionalProperties:false, items, $ref, allOf, if/then, not.
function schemaErrors(value, schema, path, root, errs) {
  if (schema.$ref) schema = _resolve(root, schema.$ref);
  const here = path.length ? path.join('/') : '(record)';
  const add = msg => errs.push(`${here}: ${msg}`);
  if (schema.type) {
    const vt = _typeOf(value);
    const ok = schema.type === vt || (schema.type === 'number' && vt === 'integer');
    if (!ok) { add(`${JSON.stringify(value)} is not of type '${schema.type}'`); return; }
  }
  if (schema.const !== undefined && value !== schema.const) add(`${JSON.stringify(schema.const)} was expected`);
  if (schema.enum && !schema.enum.includes(value)) add(`${JSON.stringify(value)} is not one of ${JSON.stringify(schema.enum)}`);
  if (typeof value === 'string') {
    if (schema.minLength !== undefined && _cp(value) < schema.minLength) add('is too short');
    if (schema.maxLength !== undefined && _cp(value) > schema.maxLength) add('is too long');
    if (schema.pattern && !new RegExp(schema.pattern, 'u').test(value)) add(`does not match '${schema.pattern}'`);
  }
  if (typeof value === 'number' && schema.minimum !== undefined && value < schema.minimum) add(`is less than the minimum of ${schema.minimum}`);
  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) add(`needs at least ${schema.minItems} item(s)`);
    if (schema.maxItems !== undefined && value.length > schema.maxItems) add(`allows at most ${schema.maxItems} item(s)`);
    if (schema.items) value.forEach((v, i) => schemaErrors(v, schema.items, [...path, String(i)], root, errs));
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const k of schema.required || []) if (!(k in value)) add(`'${k}' is a required property`);
    const props = schema.properties || {};
    if (schema.additionalProperties === false) {
      for (const k of Object.keys(value)) if (!(k in props)) add(`Additional properties are not allowed ('${k}' was unexpected)`);
    }
    if (schema.minProperties !== undefined && Object.keys(value).length < schema.minProperties) add(`needs at least ${schema.minProperties} propert(ies)`);
    for (const [k, sub] of Object.entries(props)) if (k in value) schemaErrors(value[k], sub, [...path, k], root, errs);
  }
  for (const sub of schema.allOf || []) schemaErrors(value, sub, path, root, errs);
  if (schema.if) {
    const probe = [];
    schemaErrors(value, schema.if, path, root, probe);
    if (!probe.length && schema.then) schemaErrors(value, schema.then, path, root, errs);
    if (probe.length && schema.else) schemaErrors(value, schema.else, path, root, errs);
  }
  if (schema.not) {
    const probe = [];
    schemaErrors(value, schema.not, path, root, probe);
    if (!probe.length) add('should not be valid under the "not" schema');
  }
}

function _occurrences(text, match) {
  let count = 0, from = 0;
  while (match) { const at = text.indexOf(match, from); if (at < 0) break; count++; from = at + match.length; }
  return count;
}
const _highlightOk = (text, h) => !!h && typeof h.match === 'string' && h.match.length > 0 && _occurrences(String(text || ''), h.match) >= (h.occurrence || 1);
const PINYIN_RE = /^[A-Za-zÜüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ' ]+$/;
const _pyKey = s => String(s || '').normalize('NFC').toLowerCase().replace(/[\s']/g, '');

// Admission rules beyond the schema. Every failure is a reason the record is `rejected`; nothing is downgraded.
function domainErrors(r, allowedStatuses) {
  const errs = [];
  if (!r || typeof r !== 'object') return errs;
  if (r.lang && typeof r.headword === 'string' && r.id !== makeId(r.lang, r.headword)) errs.push(`id: '${r.id}' is not the deterministic id '${makeId(r.lang, r.headword)}' of this headword`);
  if (allowedStatuses && !allowedStatuses.includes(r.status)) errs.push(`status: '${r.status}' is not allowed (only ${allowedStatuses.join('/')}); the generator never publishes`);
  (r.meanings || []).forEach((m, i) => { if (!m || typeof m.vi !== 'string' || !m.vi.trim()) errs.push(`meanings/${i}/vi: a Vietnamese meaning is required`); });
  (r.examples || []).forEach((ex, i) => {
    if (!ex || typeof ex !== 'object') return;
    if (typeof ex.text !== 'string' || !ex.text.trim()) errs.push(`examples/${i}/text: must not be empty`);
    if (typeof ex.translation_vi !== 'string' || !ex.translation_vi.trim()) errs.push(`examples/${i}/translation_vi: a Vietnamese translation is required`);
    if (ex.highlight && typeof ex.text === 'string' && !_highlightOk(ex.text, ex.highlight)) errs.push(`examples/${i}/highlight: the match is not in the sentence (or not that many times)`);
    if (ex.reading_highlight) {
      if (typeof ex.reading !== 'string' || !_highlightOk(ex.reading, ex.reading_highlight)) errs.push(`examples/${i}/reading_highlight: the match is not in the reading`);
    }
  });
  if (r.lang === 'en' && r.en && r.en.ipa && typeof r.en.ipa === 'object') {
    for (const [acc, v] of Object.entries(r.en.ipa)) if (typeof v === 'string' && !/^\/[^\/]+\/$/.test(v)) errs.push(`en/ipa/${acc}: IPA must be slash-delimited, like /rɪˈzɪliənt/`);
  }
  if (r.lang === 'zh-Hans' && r.zh && typeof r.zh === 'object') {
    const chars = Array.isArray(r.zh.chars) ? r.zh.chars : [];
    const joined = chars.map(c => (c && c.hanzi) || '').join('');
    if (typeof r.headword === 'string' && joined !== r.headword) errs.push(`zh/chars: spell '${joined}', not the headword '${r.headword}'`);
    if (typeof r.zh.pinyin !== 'string' || !r.zh.pinyin.trim()) errs.push('zh/pinyin: required (the word has no CC-CEDICT reading)');
    else if (!PINYIN_RE.test(r.zh.pinyin)) errs.push('zh/pinyin: must be pinyin letters with tone marks');
    chars.forEach((c, i) => { if (!c || typeof c.pinyin !== 'string' || !c.pinyin.trim()) errs.push(`zh/chars/${i}/pinyin: required for every character`); });
    if (typeof r.zh.pinyin === 'string' && chars.every(c => c && typeof c.pinyin === 'string' && c.pinyin.trim())
        && _pyKey(chars.map(c => c.pinyin).join('')) !== _pyKey(r.zh.pinyin)) errs.push('zh/pinyin: does not equal the per-character pinyin joined');
    if (r.zh.han_viet !== undefined && !String(r.zh.han_viet).trim()) errs.push('zh/han_viet: must not be empty when present');
  }
  return errs;
}

function validateRecord(r, allowedStatuses) {
  const errs = [];
  schemaErrors(r, VOCAB_SCHEMA, [], VOCAB_SCHEMA, errs);
  return [...new Set([...errs.map(e => 'schema: ' + e), ...domainErrors(r, allowedStatuses)])];
}
// ===== end of admission validator =====
