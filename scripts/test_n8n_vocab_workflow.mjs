// Contract gate for integrations/n8n/orena_vocab_generator.json (the n8n Vocabulary Generator).
//
// n8n itself is not run here. What is tested is the workflow file as shipped: its n8n shape, its absence of secrets and
// instance ids, the schema it carries, and - by extracting the JavaScript of its Code nodes and running them in a vm with
// a mocked n8n runtime ($, $input, $env, this.helpers) - the behaviour of the nodes that decide anything:
// Config, Parse words, Build records, Prepare AI, Validate & group, Build files, Check writes, Prepare sync, Check preview,
// Check import, Final report, Run summary. HTTP nodes are replaced by recorded fixtures; no network is touched.
//
//   node scripts/test_n8n_vocab_workflow.mjs            run the gate
//   node scripts/test_n8n_vocab_workflow.mjs --update   rewrite tests/fixtures/n8n_vocab_ready_example.jsonl

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WORKFLOW = path.join(ROOT, 'integrations/n8n/orena_vocab_generator.json');
const SCHEMA_FILE = path.join(ROOT, 'docs/vocab/vocab_entry.schema.json');
const FIXTURES = path.join(ROOT, 'tests/fixtures');
const UPDATE = process.argv.includes('--update');
const read = p => fs.readFileSync(p, 'utf8');
const readJson = p => JSON.parse(read(p));

const workflowText = read(WORKFLOW);
const workflow = JSON.parse(workflowText);
const byName = Object.fromEntries(workflow.nodes.map(n => [n.name, n]));

let passed = 0;
const failures = [];
async function test(name, fn) {
  try { await fn(); passed++; } catch (e) { failures.push(`${name}\n    ${String(e && e.stack || e).split('\n').slice(0, 6).join('\n    ')}`); }
}

// ---------------------------------------------------------------- the mocked n8n runtime
function makeRuntime(outputs, env = {}) {
  const dollar = name => {
    if (!(name in outputs)) throw new Error(`Node '${name}' hasn't been executed`);
    const items = outputs[name];
    return { first: () => items[0], all: () => items, item: items[0] };
  };
  const helpers = {
    prepareBinaryData: async (buffer, fileName, mimeType) => ({ data: Buffer.from(buffer).toString('base64'), fileName, mimeType }),
    getBinaryDataBuffer: async () => Buffer.alloc(0),
  };
  return { dollar, helpers, env };
}

async function runNode(name, outputs, input, env = {}) {
  const node = byName[name];
  assert.ok(node && node.type === 'n8n-nodes-base.code', `no Code node '${name}'`);
  const rt = makeRuntime(outputs, env);
  const sandbox = vm.createContext({
    $: rt.dollar,
    $input: { first: () => input[0], all: () => input },
    $env: rt.env,
    Buffer, URL, JSON, Math, Date, Array, Object, Set, Map, RegExp, String, Number, Error, Promise, console,
  });
  const fn = vm.runInContext(`(async function () {\n${node.parameters.jsCode}\n})`, sandbox);
  // The vm has its own realm (its arrays are not this realm's): hand back plain data, as n8n does between nodes.
  return JSON.parse(JSON.stringify(await fn.call({ helpers: rt.helpers })));
}

// ---------------------------------------------------------------- fixtures: what the HTTP nodes would have returned
const FREE_DICT_RESILIENT = [{
  word: 'resilient',
  phonetic: '/rɪˈzɪliənt/',
  phonetics: [
    { text: '/rɪˈzɪliənt/', audio: 'https://api.dictionaryapi.dev/media/pronunciations/en/resilient-uk.mp3' },
    { text: '/rɪˈzɪljənt/', audio: 'https://api.dictionaryapi.dev/media/pronunciations/en/resilient-us.mp3' },
  ],
  meanings: [{
    partOfSpeech: 'adjective',
    definitions: [{ definition: 'Able to recover quickly after something unpleasant, such as shock or injury.', example: 'Children are often more resilient than adults expect.', synonyms: ['tough'], antonyms: [] }],
    synonyms: ['hardy'], antonyms: ['fragile'],
  }],
}];
const TATOEBA_EN = { results: [
  { text: 'The network is designed to be resilient to power failures.', translations: [[{ lang: 'vie', text: 'Mạng được thiết kế để chịu được sự cố mất điện.' }]] },
  { text: 'Children are often more resilient than adults expect.', translations: [[{ lang: 'vie', text: 'Trẻ em thường kiên cường hơn người lớn nghĩ.' }]] },
] };
const TATOEBA_ZH = { results: [
  { text: '我们应该保护森林。', translations: [[{ lang: 'vie', text: 'Chúng ta nên bảo vệ rừng.' }]] },
] };
const ZH_LOOKUP = {
  cedict: {
    '森林': [['sen1 lin2', ['forest', 'CL:片[pian4]']]],
    '我们': [['wo3 men5', ['we']]], '应该': [['ying1 gai1', ['should']]], '保护': [['bao3 hu4', ['to protect']]],
  },
  cvdict: { '森林': ['rừng', 'rừng rậm'], '木': ['cây'] },
  hanzi: { '森': ['⿱木林', '木'], '林': ['⿰木木', '木'] },
  unihan: {
    '森': ['75.8', '12', 'sâm', 'sēn'], '林': ['75.4', '8', 'lâm', 'lín'], '木': ['75.0', '4', 'mộc', 'mù'],
  },
};

const text = j => ({ json: { data: typeof j === 'string' ? j : JSON.stringify(j) } });

// ---------------------------------------------------------------- the pipeline, node by node (HTTP/file nodes mocked)
// opts: { form, env, enrich: { word: [call1, call2] }, ai: (jobs) => items | null, saveFails: Set(role), zh: bool }
async function pipeline(opts) {
  const env = opts.env || {};
  const o = {};
  o.Config = await runNode('Config', o, [{ json: opts.form }], env);
  o['Output folder probe'] = await runNode('Output folder probe', o, o.Config);
  assert.equal(o['Output folder probe'][0].json.path, `${o.Config[0].json.output.dir}/.orena-write-check`);
  o['Check output folder'] = await runNode('Check output folder', o, [{ json: opts.probeFails ? { error: "ENOENT: no such file or directory, realpath '/files/orena'" } : {} }]);
  o['Parse words'] = await runNode('Parse words', o, o.Config);
  const parsed = o['Parse words'][0].json;
  o.Words = await runNode('Words', o, o['Parse words']);
  if (parsed.hasZh) o['Parse ZH lookup'] = [{ json: { data: { lookup: opts.zhLookup || ZH_LOOKUP } } }];
  const calls = o.Words.map(w => (opts.enrich || {})[w.json.word] || [text('[]'), text('{"results":[]}')]);
  o['Enrich call 1'] = calls.map(c => c[0]);
  o['Enrich call 2'] = calls.map(c => c[1]);
  o['Build records'] = await runNode('Build records', o, o['Enrich call 2']);
  o['Prepare AI'] = await runNode('Prepare AI', o, o['Build records']);
  let aiIn = o['Prepare AI'];
  if (!aiIn[0].json.noop) {
    assert.ok(opts.ai, 'the workflow asked for AI but the test gave no AI fixture');
    aiIn = opts.ai(aiIn.map(i => i.json));
  }
  o['Validate & group'] = await runNode('Validate & group', o, aiIn);
  o['Build files'] = await runNode('Build files', o, o['Validate & group']);
  const saveFails = opts.saveFails || new Set();
  const saved = o['Build files'].map(f => saveFails.has(f.json.role) ? { json: { error: 'EACCES: permission denied' } } : { json: {} });
  o['Check writes'] = await runNode('Check writes', o, saved);
  o['Prepare sync'] = await runNode('Prepare sync', o, o['Check writes']);
  if (!o['Prepare sync'][0].json.noop) {
    const sent = o['Prepare sync'];
    const previewReplies = sent.map(s => (opts.previewReply || (() => ({ json: { error: 'no preview reply configured' } })))(s.json, sent));
    o['Orena · Preview'] = previewReplies;
    o['Check preview'] = await runNode('Check preview', o, previewReplies);
    if (o['Check preview'][0].json.passed) {
      const importReplies = o['Check preview'].map(s => (opts.importReply || (() => ({ json: { error: 'no import reply configured' } })))(s.json));
      o['Check import'] = await runNode('Check import', o, importReplies);
    }
  }
  o['Final report'] = await runNode('Final report', o, o['Prepare sync']);
  o['Run summary'] = await runNode('Run summary', o, o['Final report'].map(f => (opts.finalSaveFails && opts.finalSaveFails.has(f.json.role)) ? { json: { error: 'disk full' } } : { json: {} }));
  return o;
}

const MANUAL = (extra = {}) => ({ 'Word list': 'resilient — C1 — kiên cường\n森林 — HSK4', 'Batch title': 'Test Batch 01', _trigger: 'manual', ...extra });
const ENRICH = { resilient: [text(FREE_DICT_RESILIENT), text(TATOEBA_EN)], '森林': [text(TATOEBA_ZH), text({ results: [] })] };
const fileOf = (o, role, lang) => {
  const g = o['Validate & group'][0].json.groups.find(x => x.lang === lang);
  return role === 'ready' ? g : null;
};
const buildFile = (o, role, startsWith) => o['Build files'].find(f => f.json.role === role && (!startsWith || f.json.path.includes(startsWith)));
const decode = f => Buffer.from(f.binary.data.data, 'base64').toString('utf8');
const readyRecords = (o, lang) => fileOf(o, 'ready', lang).fileContent.trim().split('\n').filter(Boolean).map(l => JSON.parse(l));

// ================================================================ 1. the workflow file as shipped
await test('the workflow has the n8n export shape', () => {
  for (const k of ['name', 'nodes', 'connections', 'settings']) assert.ok(k in workflow, `missing ${k}`);
  assert.ok(Array.isArray(workflow.nodes) && workflow.nodes.length > 20);
  const names = new Set();
  const ids = new Set();
  for (const n of workflow.nodes) {
    for (const k of ['name', 'type', 'typeVersion', 'position', 'parameters', 'id']) assert.ok(k in n, `${n.name}: missing ${k}`);
    assert.ok(!names.has(n.name), `duplicate node name ${n.name}`); names.add(n.name);
    assert.ok(!ids.has(n.id), `duplicate node id ${n.id}`); ids.add(n.id);
    assert.match(n.type, /^n8n-nodes-base\.[A-Za-z]+$/);
    assert.ok(Array.isArray(n.position) && n.position.length === 2);
    if (n.type === 'n8n-nodes-base.code') assert.equal(typeof n.parameters.jsCode, 'string');
  }
  for (const [src, v] of Object.entries(workflow.connections)) {
    assert.ok(names.has(src), `connection from unknown node ${src}`);
    for (const out of v.main) for (const c of out) assert.ok(names.has(c.node), `${src} -> unknown node ${c.node}`);
  }
  const triggers = workflow.nodes.filter(n => /Trigger$/.test(n.type)).map(n => n.name).sort();
  assert.deepEqual(triggers, ['Form', 'Run test']);
  assert.equal(workflow.active, false, 'an imported workflow must be inactive');
});

await test('every node is reachable from a trigger', () => {
  const seen = new Set(['Form', 'Run test']);
  const queue = ['Form', 'Run test'];
  while (queue.length) for (const out of (workflow.connections[queue.shift()] || { main: [] }).main) for (const c of out) if (!seen.has(c.node)) { seen.add(c.node); queue.push(c.node); }
  const loose = workflow.nodes.filter(n => !seen.has(n.name) && n.type !== 'n8n-nodes-base.stickyNote').map(n => n.name);
  assert.deepEqual(loose, []);
});

await test('no secret, credential reference or instance id is embedded', () => {
  for (const n of workflow.nodes) assert.ok(!('credentials' in n), `${n.name} references a credential`);
  const patterns = [
    [/sk-[A-Za-z0-9_-]{16,}/, 'OpenAI-style key'], [/AIza[0-9A-Za-z_-]{30,}/, 'Google API key'], [/gh[pousr]_[A-Za-z0-9]{20,}/, 'GitHub token'],
    [/xox[abp]-[A-Za-z0-9-]{10,}/, 'Slack token'], [/eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}/, 'JWT'], [/AKIA[0-9A-Z]{16}/, 'AWS key'],
    [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, 'private key'], [/Bearer\s+[A-Za-z0-9._~+\/-]{20,}/, 'bearer token'],
    [/(?:api[_-]?key|secret|password|token)["']?\s*[:=]\s*["'][A-Za-z0-9_\-+\/=]{16,}["']/i, 'key assignment'],
  ];
  for (const [re, label] of patterns) assert.ok(!re.test(workflowText), `looks like a ${label}`);
  assert.ok(!/home\/node\/\.n8n-files/.test(workflowText), 'the old non-persistent audit path is still referenced');
  assert.ok(!/ORENA_AI_/.test(workflowText), 'the generator must not require ORENA_AI_*');
  assert.ok(!/localhost:5678|n8n\.cloud|webhook\/[0-9a-f]{8}-/.test(workflowText), 'an instance URL is embedded');
  const ids = [...workflowText.matchAll(/"(?:id|webhookId)":\s*"([^"]+)"/g)].map(m => m[1]);
  assert.ok(ids.length > 20);
  for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/, `${id} is not a deterministic uuid5`);
});

await test('the embedded vocabulary schema equals docs/vocab/vocab_entry.schema.json', () => {
  const repoText = read(SCHEMA_FILE).replace(/\r\n/g, '\n');
  const carriers = workflow.nodes.filter(n => n.type === 'n8n-nodes-base.code' && n.parameters.jsCode.includes('const VOCAB_SCHEMA_TEXT = '));
  assert.ok(carriers.length >= 1, 'no Code node carries the schema');
  for (const n of carriers) {
    const m = /const VOCAB_SCHEMA_TEXT = ("(?:[^"\\]|\\.)*");/.exec(n.parameters.jsCode);
    assert.ok(m, `${n.name}: schema literal not found`);
    const embedded = JSON.parse(m[1]);
    assert.equal(embedded, repoText, `${n.name}: the embedded schema text differs from the repo file`);
    assert.deepEqual(JSON.parse(embedded), JSON.parse(repoText));
  }
  const schema = JSON.parse(repoText);
  assert.ok(!('etymology_en' in schema.$defs.en_fields.properties), 'the repo schema now has etymology_en: revisit the generator');
  assert.ok(!/etymology_en/.test(workflowText.replace(/const VOCAB_SCHEMA_TEXT = "(?:[^"\\]|\\.)*";/g, '')), 'etymology_en is used by the workflow');
});

await test('the form is protected and file mode / skip are the defaults', () => {
  const form = byName.Form.parameters;
  assert.equal(form.authentication, 'basicAuth');
  const field = label => form.formFields.values.find(f => f.fieldLabel === label);
  assert.equal(field('Delivery mode').fieldOptions.values[0].option, 'file');
  assert.equal(field('When already stored').fieldOptions.values[0].option, 'skip');
});

await test('HTTP nodes to Orena use a selectable credential type and never a literal header', () => {
  for (const name of ['Orena · Preview', 'Orena · Import', 'AI · Fill gaps']) {
    const p = byName[name].parameters;
    assert.equal(p.authentication, 'genericCredentialType'); assert.equal(p.genericAuthType, 'httpHeaderAuth');
    assert.ok(!p.sendHeaders && !p.headerParameters, `${name} carries a literal header`);
  }
  assert.ok(!('Authorization' in JSON.parse(JSON.stringify(byName['Orena · Preview'].parameters))));
});

// ================================================================ 2. schema parity (shared cases; jsonschema is the truth in pytest)
const CASES = readJson(path.join(FIXTURES, 'n8n_vocab_schema_cases.json')).cases;
function applyOps(sample, ops) {
  const rec = JSON.parse(JSON.stringify(sample));
  for (const [op, p, value] of ops) {
    let parent = rec;
    for (const k of p.slice(0, -1)) parent = parent[k];
    const last = p[p.length - 1];
    if (op === 'set') parent[last] = value === '__five__' ? Array.from({ length: 5 }, () => JSON.parse(JSON.stringify(rec.examples[0]))) : value;
    else if (op === 'del') delete parent[last];
  }
  return rec;
}
const validateSrc = byName['Validate & group'].parameters.jsCode.split('// ===== end of admission validator =====')[0];
function loadValidator() {
  const sandbox = vm.createContext({ JSON, Array, Object, Set, Number, String, RegExp, Error });
  const common = byName['Parse words'].parameters.jsCode.split('// ===== end of shared helpers =====')[0] + '// ===== end of shared helpers =====';
  vm.runInContext(common + '\n' + validateSrc.slice(validateSrc.indexOf('// ===== Orena vocabulary generator | admission validator')) + '\n' +
    'this.schemaErrors = schemaErrors; this.domainErrors = domainErrors; this.validateRecord = validateRecord; this.makeId = makeId; this.VOCAB_SCHEMA = VOCAB_SCHEMA;', sandbox);
  // the vm has its own Array prototype: hand results back as this realm's plain data
  const plain = x => JSON.parse(JSON.stringify(x));
  return {
    validateRecord: (r, statuses) => plain(sandbox.validateRecord(r, statuses)),
    schemaErrors: (v, schema, p, root, errs) => sandbox.schemaErrors(v, schema, p, root, errs),
    makeId: (l, w) => sandbox.makeId(l, w),
    VOCAB_SCHEMA: plain(sandbox.VOCAB_SCHEMA),
  };
}
const V = loadValidator();
const SAMPLES = { en_resilient: readJson(path.join(ROOT, 'docs/vocab/samples/en_resilient.json')), zh_senlin: readJson(path.join(ROOT, 'docs/vocab/samples/zh_senlin.json')) };

for (const c of CASES) {
  await test(`schema parity: ${c.name}`, () => {
    const rec = applyOps(SAMPLES[c.sample], c.ops);
    const errs = [];
    V.schemaErrors(rec, V.VOCAB_SCHEMA, [], V.VOCAB_SCHEMA, errs);
    assert.equal(errs.length === 0, c.valid, `workflow validator says ${errs.length ? errs.join(' | ') : 'valid'}, jsonschema says ${c.valid ? 'valid' : 'invalid'}`);
  });
}

await test('the repo samples pass the whole admission validator (schema + domain rules) except the id convention', () => {
  // The samples use hand-written ids (en:resilient is the derived id; zh-Hans:senlin is editorial), so only the id rule may differ.
  const en = V.validateRecord(SAMPLES.en_resilient, ['draft']);
  assert.deepEqual(en, []);
  const zh = V.validateRecord(SAMPLES.zh_senlin, ['draft']);
  assert.deepEqual(zh, [`id: 'zh-Hans:senlin' is not the deterministic id 'zh-Hans:68ee-6797' of this headword`]);
});

await test('domain rules reject what the schema allows', () => {
  const bad = (sample, ops) => V.validateRecord(applyOps(SAMPLES[sample], ops), ['draft']).join(' | ');
  assert.match(bad('en_resilient', [['set', ['status'], 'published']]), /status: 'published' is not allowed/);
  assert.match(bad('en_resilient', [['set', ['id'], 'en:other']]), /deterministic id/);
  assert.match(bad('en_resilient', [['set', ['examples', 0, 'highlight', 'match'], 'zzz']]), /examples\/0\/highlight/);
  assert.match(bad('en_resilient', [['set', ['examples', 0, 'highlight', 'occurrence'], 2]]), /examples\/0\/highlight/);
  assert.match(bad('en_resilient', [['set', ['examples', 0, 'translation_vi'], '  ']]), /translation_vi: a Vietnamese translation is required/);
  assert.match(bad('en_resilient', [['set', ['meanings', 0, 'vi'], '']]), /meanings\/0\/vi/);
  assert.match(bad('en_resilient', [['set', ['en', 'ipa', 'uk'], 'rɪˈzɪliənt']]), /IPA must be slash-delimited/);
  assert.match(bad('zh_senlin', [['set', ['zh', 'chars', 1, 'hanzi'], '木']]), /zh\/chars: spell '森木'/);
  assert.match(bad('zh_senlin', [['set', ['zh', 'pinyin'], '']]), /zh\/pinyin: required/);
  assert.match(bad('zh_senlin', [['set', ['zh', 'chars', 0, 'pinyin'], '']]), /zh\/chars\/0\/pinyin: required/);
  assert.match(bad('zh_senlin', [['set', ['zh', 'pinyin'], 'sēnlín2']]), /pinyin letters/);
  assert.match(bad('zh_senlin', [['set', ['zh', 'pinyin'], 'sēnlǐn']]), /does not equal the per-character pinyin/);
  assert.match(bad('zh_senlin', [['set', ['examples', 0, 'reading_highlight', 'match'], 'xyz']]), /reading_highlight/);
  assert.match(bad('zh_senlin', [['del', ['examples', 0, 'reading']]]), /reading_highlight/);
});

// ================================================================ 3. file mode: resilient and 森林 end to end, no Orena config
let FILE_RUN;
await test('file mode, no Orena config: resilient - C1 and 森林 - HSK4 are READY', async () => {
  FILE_RUN = await pipeline({ form: MANUAL(), enrich: ENRICH });
  const cfg = FILE_RUN.Config[0].json;
  assert.equal(cfg.mode, 'file'); assert.equal(cfg.orena.configured, false); assert.equal(cfg.output.dir, '/files/orena');
  assert.equal(cfg.ai.active, false);
  const b = FILE_RUN['Validate & group'][0].json;
  assert.deepEqual(b.rejected, [], JSON.stringify(b.rejected.map(r => [r.id, r.reasons])));
  assert.deepEqual(b.ready.map(r => r.id).sort(), ['en:resilient', 'zh-Hans:68ee-6797']);
  const en = readyRecords(FILE_RUN, 'en')[0];
  assert.equal(en.id, 'en:resilient'); assert.deepEqual(en.level, { scale: 'CEFR', value: 'C1', source: 'operator-supplied CEFR level (not checked against a word list)' });
  assert.deepEqual(en.en, { ipa: { uk: '/rɪˈzɪliənt/', us: '/rɪˈzɪljənt/' } });
  assert.deepEqual(en.audio, { tts: true });
  assert.equal(en.status, 'draft'); assert.ok(!('etymology_en' in en.en));
  assert.ok(en.examples.length >= 1 && en.examples.every(x => x.translation_vi && x.text.includes(x.highlight.match)));
  assert.equal(en.pos[0].code, 'adjective');
  assert.ok(en.tags.includes('gen:n8n-vocab-generator') && en.tags.includes('src:free-dictionary'));
  const zh = readyRecords(FILE_RUN, 'zh-Hans')[0];
  assert.equal(zh.id, 'zh-Hans:68ee-6797'); assert.equal(zh.level.scale, 'HSK3'); assert.equal(zh.level.value, '4');
  assert.equal(zh.zh.pinyin, 'sēnlín'); assert.deepEqual(zh.zh.chars.map(c => c.hanzi).join(''), '森林');
  assert.deepEqual(zh.zh.chars.map(c => c.pinyin), ['sēn', 'lín']);
  assert.equal(zh.zh.han_viet, 'SÂM LÂM'); assert.equal(zh.zh.chars[0].radical.char, '木');
  assert.deepEqual(zh.examples[0].reading_highlight, { match: 'sēnlín' }); assert.equal(zh.examples[0].reading, 'Wǒmen yīnggāi bǎohù sēnlín.');
  assert.equal(zh.pos[0].code, 'noun');
  // every ready record passes the full admission validator
  for (const r of [en, zh]) assert.deepEqual(V.validateRecord(r, ['draft']), []);
});

await test('file mode writes the ready file, rejected.json and the reports to /files/orena and calls no API', () => {
  const files = FILE_RUN['Build files'].map(f => f.json);
  assert.deepEqual(files.map(f => f.role), ['ready', 'ready', 'rejected', 'report_json', 'report_csv']);
  for (const f of files) assert.ok(f.path.startsWith('/files/orena/'), f.path);
  assert.match(files[0].path, /\/en-batch-[0-9a-f]{8}\.[0-9a-f]{8}\.ready\.jsonl$|test-batch-01-en\.[0-9a-f]{8}\.ready\.jsonl$/);
  assert.equal(FILE_RUN['Prepare sync'][0].json.noop, true); assert.equal(FILE_RUN['Prepare sync'][0].json.reason, 'file_mode');
  assert.ok(!('Orena · Preview' in FILE_RUN) && !('Check preview' in FILE_RUN));
  const report = JSON.parse(decode(buildFile(FILE_RUN, 'report_json')));
  assert.equal(report.sync_status, 'not_requested'); assert.equal(report.totals.ready, 2); assert.equal(report.rights_status, 'unknown'); assert.equal(report.completeness, 'partial');
  const summary = FILE_RUN['Run summary'][0].json;
  assert.equal(summary.ready, 2); assert.equal(summary.rejected, 0); assert.equal(summary.sync_status, 'not_requested'); assert.deepEqual(summary.non_critical_write_failures, []);
  assert.equal(summary.files.length, 5);
});

await test('collection metadata claims no more than the evidence', () => {
  const m = FILE_RUN['Validate & group'][0].json.groups[0].metadata;
  assert.equal(m.rights_status, 'unknown'); assert.equal(m.completeness, 'partial');
  assert.deepEqual(Object.keys(m).sort(), ['collection_id', 'completeness', 'language_code', 'provenance', 'rights_status', 'title']);
  assert.ok(!('publish' in m) && !('publication_attested' in m));
});

// ================================================================ 4. admission: invalid -> rejected with reasons, never downgraded
await test('a deliberately invalid record is rejected with explicit reasons', async () => {
  const o = await pipeline({ form: MANUAL({ 'Word list': 'resilient — C1 — kiên cường\nephemeral — C3\nzzzword — B1\n森林' }), enrich: ENRICH });
  const b = o['Validate & group'][0].json;
  assert.deepEqual(b.ready.map(r => r.id), ['en:resilient']);
  const byId = Object.fromEntries(b.rejected.map(r => [r.id, r]));
  assert.ok(byId['en:ephemeral'].reasons.some(r => /level "C3" is not a valid CEFR/.test(r)), JSON.stringify(byId['en:ephemeral'].reasons));
  assert.ok(byId['en:zzzword'].reasons.some(r => /no part of speech/.test(r)));
  assert.ok(byId['en:zzzword'].reasons.some(r => /no Vietnamese meaning/.test(r)));
  assert.ok(byId['en:zzzword'].reasons.some(r => /no example sentence/.test(r)));
  assert.ok(byId['en:zzzword'].reasons.some(r => /no IPA/.test(r)));
  assert.ok(byId['zh-Hans:68ee-6797'].reasons.some(r => /the level is missing/.test(r)), JSON.stringify(byId['zh-Hans:68ee-6797'].reasons));
  for (const r of b.rejected) assert.ok(r.reasons.length && r.record, 'a rejected record keeps its reasons and its record');
  // never downgraded: nothing rejected is in any ready file, and no ready file contains a record that fails validation
  const ready = readyRecords(o, 'en');
  assert.deepEqual(ready.map(r => r.id), ['en:resilient']);
  const rej = JSON.parse(decode(buildFile(o, 'rejected')));
  assert.equal(rej.length, 3);
  const rows = decode(buildFile(o, 'report_csv')).trim().split('\n');
  assert.equal(rows[0], 'line,id,headword,lang,status,reasons,warnings,collection_id,sync');
  assert.equal(rows.length, 5);
});

await test('a zh record without a CC-CEDICT entry is rejected (no pinyin), not guessed', async () => {
  const o = await pipeline({ form: MANUAL({ 'Word list': '稀有词 — HSK6' }), enrich: {} });
  const b = o['Validate & group'][0].json;
  assert.equal(b.ready.length, 0);
  assert.ok(b.rejected[0].reasons.some(r => /no pinyin/.test(r)));
  assert.equal(o['Build files'].filter(f => f.json.role === 'ready').length, 0, 'no ready file for an empty batch');
});

await test('the same word twice in the input is reported, not silently dropped', async () => {
  const o = await pipeline({ form: MANUAL({ 'Word list': 'resilient — C1\nResilient — C1' }), enrich: ENRICH });
  const issues = o['Validate & group'][0].json.inputIssues;
  assert.equal(issues.length, 1); assert.match(issues[0].issue, /same id as line 1/);
});

// ================================================================ 5. AI is a fill-gap layer with neutral config
await test('AI config is neutral (AI_ENDPOINT / AI_MODEL) and only fills gaps; filled fields are tagged', async () => {
  const env = { AI_ENDPOINT: 'https://llm.example/v1/chat/completions', AI_MODEL: 'some-model' };
  const noAi = await pipeline({ form: MANUAL({ 'Word list': 'resilient — C1 — kiên cường' }), enrich: ENRICH, env });
  assert.equal(noAi.Config[0].json.ai.active, true);
  assert.equal(noAi['Prepare AI'][0].json.noop, true, 'nothing was missing, so AI was not asked');
  // a word with no dictionary data: AI is asked for everything it may fill
  let asked;
  const o = await pipeline({
    form: MANUAL({ 'Word list': 'zzzword — B1' }), enrich: {}, env,
    ai: jobs => {
      asked = jobs;
      const answer = { pos: ['noun'], meaning_vi: 'một từ thử', examples: [{ text: 'This is a zzzword in a sentence.', translation_vi: 'Đây là một từ thử trong câu.' }], ipa: { uk: '/ˈzɪzwɜːd/', us: '/ˈzɪzwɝːd/' } };
      return jobs.map(() => ({ json: { data: JSON.stringify({ choices: [{ message: { content: JSON.stringify(answer) } }] }) } }));
    },
  });
  assert.equal(asked.length, 1); assert.deepEqual(asked[0].want.sort(), ['examples', 'ipa', 'meaning_vi', 'pos']);
  assert.ok(!JSON.stringify(asked[0].body).includes('ORENA'));
  const r = readyRecords(o, 'en')[0];
  assert.equal(r.meanings[0].vi, 'một từ thử');
  assert.ok(['ai-filled:examples', 'ai-filled:ipa', 'ai-filled:meaning_vi', 'ai-filled:pos'].every(t => r.tags.includes(t)), r.tags.join());
  assert.deepEqual(V.validateRecord(r, ['draft']), []);
});

await test('AI answers never overwrite a value that exists, and bad AI output is rejected by validation', async () => {
  const env = { AI_ENDPOINT: 'https://llm.example/v1', AI_MODEL: 'm' };
  // the dictionary gave no Vietnamese translation of the example: AI is asked for translations only
  const dict = [{ ...FREE_DICT_RESILIENT[0] }];
  const o = await pipeline({
    form: MANUAL({ 'Word list': 'resilient — C1' }), env,
    enrich: { resilient: [text(dict), text({ results: [] })] },
    ai: jobs => {
      assert.deepEqual(jobs[0].want.sort(), ['meaning_vi', 'translations_vi'], 'only the gaps are asked for');
      return jobs.map(() => ({ json: { data: JSON.stringify({ choices: [{ message: { content: JSON.stringify({ meaning_vi: 'kiên cường', translations_vi: { 0: 'Trẻ em thường kiên cường hơn người lớn nghĩ.' }, ipa: { uk: '/x/' }, pos: ['verb'] }) } }] }) } }));
    },
  });
  const r = readyRecords(o, 'en')[0];
  assert.equal(r.pos[0].code, 'adjective', 'AI must not replace the dictionary part of speech');
  assert.deepEqual(r.en.ipa, { uk: '/rɪˈzɪliənt/', us: '/rɪˈzɪljənt/' });
  assert.ok(r.tags.includes('ai-filled:translation_vi') && r.tags.includes('ai-filled:meaning_vi'));
  // junk from the AI is just ignored and the record is rejected for the gap that is left
  const o2 = await pipeline({
    form: MANUAL({ 'Word list': 'zzzword — B1' }), env, enrich: {},
    ai: jobs => jobs.map(() => ({ json: { data: '<html>502 Bad Gateway</html>' } })),
  });
  assert.equal(o2['Validate & group'][0].json.ready.length, 0);
  assert.ok(o2['Validate & group'][0].json.rejected[0].reasons.length >= 3);
});

// ================================================================ 6. stable ids, idempotent reruns
await test('rerun with the same input gives the same ids, the same bytes and the same file names', async () => {
  const a = await pipeline({ form: MANUAL(), enrich: ENRICH });
  const b = await pipeline({ form: MANUAL(), enrich: ENRICH });
  const ga = a['Validate & group'][0].json.groups, gb = b['Validate & group'][0].json.groups;
  assert.deepEqual(ga.map(g => [g.collection_id, g.fileName, g.fileContent, g.readyIds]), gb.map(g => [g.collection_id, g.fileName, g.fileContent, g.readyIds]));
  // the order of the input lines does not change the ready bytes
  const c = await pipeline({ form: MANUAL({ 'Word list': '森林 — HSK4\nresilient — C1 — kiên cường' }), enrich: ENRICH });
  assert.deepEqual(c['Validate & group'][0].json.groups.map(g => g.fileContent), ga.map(g => g.fileContent));
});

await test('ids are deterministic, schema-valid and independent of the run', () => {
  assert.equal(V.makeId('en', 'resilient'), 'en:resilient');
  assert.equal(V.makeId('en', 'Ice cream'), 'en:ice-cream');
  assert.equal(V.makeId('en', 'café'), V.makeId('en', 'café'));
  assert.match(V.makeId('en', 'café'), /^en:cafe-[0-9a-f]{6}$/);
  assert.equal(V.makeId('zh-Hans', '森林'), 'zh-Hans:68ee-6797');
  const idPattern = new RegExp(V.VOCAB_SCHEMA.properties.id.pattern, 'u');
  for (const id of [V.makeId('en', 'resilient'), V.makeId('en', "rock 'n' roll"), V.makeId('en', 'café'), V.makeId('zh-Hans', '森林')]) assert.match(id, idPattern, id);
});

const EXAMPLE_FILE = path.join(FIXTURES, 'n8n_vocab_ready_example.jsonl');
await test('the ready file the workflow generates equals the committed fixture (which pytest sends through the real Orena routes)', () => {
  const content = FILE_RUN['Validate & group'][0].json.groups.map(g => g.fileContent).join('');
  if (UPDATE) fs.writeFileSync(EXAMPLE_FILE, content, 'utf8');
  assert.equal(content, read(EXAMPLE_FILE), 'run: node scripts/test_n8n_vocab_workflow.mjs --update');
});

// ================================================================ 7. who may overwrite
await test('the form can never trigger overwrite; the operator path can; a deliberate setting allows the form', async () => {
  const fromForm = await runNode('Config', {}, [{ json: { 'Word list': 'resilient — C1', 'When already stored': 'overwrite', 'Delivery mode': 'api' } }]);
  assert.equal(fromForm[0].json.duplicates, 'skip'); assert.match(fromForm[0].json.duplicatesNote, /not allowed to overwrite/);
  const manual = await runNode('Config', {}, [{ json: MANUAL({ 'When already stored': 'overwrite' }) }]);
  assert.equal(manual[0].json.duplicates, 'overwrite');
  const allowed = await runNode('Config', {}, [{ json: { 'Word list': 'a — A1', 'When already stored': 'overwrite' } }], { ORENA_VOCAB_ALLOW_FORM_OVERWRITE: 'true' });
  assert.equal(allowed[0].json.duplicates, 'overwrite');
  const apiOverwrite = await runNode('Config', {}, [{ json: MANUAL({ 'When already stored': 'overwrite', 'Delivery mode': 'api' }) }]);
  assert.equal(apiOverwrite[0].json.duplicates, 'skip'); assert.match(apiOverwrite[0].json.duplicatesNote, /api mode/);
  const dflt = await runNode('Config', {}, [{ json: { 'Word list': 'a — A1' } }]);
  assert.equal(dflt[0].json.duplicates, 'skip'); assert.equal(dflt[0].json.mode, 'file');
  await assert.rejects(() => runNode('Config', {}, [{ json: { 'Word list': 'a — A1', 'Delivery mode': 'cloud' } }]), /Delivery mode/);
  await assert.rejects(() => runNode('Config', {}, [{ json: { 'Word list': 'a — A1' } }], { ORENA_VOCAB_OUT_DIR: '/files/../etc' }), /output.dir/);
});

// ================================================================ 8. Orena responses: strict readers
const real = readJson(path.join(FIXTURES, 'n8n_vocab_orena_responses.json'));
const jsonReply = (status, body, ctype = 'application/json') => ({ json: { statusCode: status, headers: { 'content-type': ctype }, body: typeof body === 'string' ? body : JSON.stringify(body) } });
const clone = o => JSON.parse(JSON.stringify(o));

function previewFor(fileName, ids, mutate) {
  const body = clone(real.preview);
  const item = body.items[0];
  item.filename = fileName;
  item.row_count = ids.length;
  item.authored.rows = ids.map((id, i) => ({ ...clone(real.preview.items[0].authored.rows[0]), row: i + 1, id, term: id.split(':')[1] }));
  item.authored.counts = { ready: ids.length };
  item.authored.language_code = ids[0].startsWith('zh-Hans:') ? 'zh' : 'en';
  if (mutate) mutate(body);
  return body;
}

async function apiRun({ mode = 'api', baseUrl = 'https://orena.example', previewReply, importReply, form = {}, saveFails, finalSaveFails } = {}) {
  return pipeline({
    form: MANUAL({ 'Delivery mode': mode, ...form }), env: baseUrl ? { ORENA_BASE_URL: baseUrl } : {}, enrich: ENRICH,
    previewReply: previewReply || ((s) => jsonReply(200, previewFor(s.fileName, s.ids))),
    importReply: importReply || ((s) => jsonReply(200, { collection: { id: s.collection_id, title: s.metadata.title, catalog_status: 'pending_review' }, items: [{ source_import_id: 'x', filename: s.fileName, status: 'imported', imported: s.ids.length, skipped: 0, duplicates: 0, warnings: [], failed: 0, failure_reason: '', updated: 0, conflicts: 0, localizations_retired: 0, rows: [] }] })),
    saveFails, finalSaveFails,
  });
}

await test('api mode: files first, then preview, then import; the set lands pending_review', async () => {
  const o = await apiRun();
  assert.ok(o['Build files'].some(f => f.json.role === 'ready'));
  const prepared = o['Prepare sync'];
  assert.equal(prepared.length, 2);
  assert.equal(prepared[0].json.previewUrl, 'https://orena.example/api/admin/vocabulary/preview');
  assert.equal(prepared[0].json.importUrl, 'https://orena.example/api/admin/vocabulary/import');
  assert.equal(prepared[0].json.duplicates, 'skip');
  assert.ok(prepared.every(p => p.binary.data.fileName.endsWith('.ready.jsonl')));
  assert.equal(o['Check preview'][0].json.passed, true);
  assert.equal(o['Check import'].every(c => c.json.ok), true);
  const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
  assert.equal(report.sync_status, 'imported');
  assert.deepEqual(report.groups.map(g => g.sync.status), ['imported', 'imported']);
  assert.equal(o['Run summary'][0].json.sync_status, 'imported');
});

await test('api mode without an Orena URL blocks the sync and keeps the local files', async () => {
  const o = await apiRun({ baseUrl: '' });
  assert.equal(o['Prepare sync'][0].json.reason, 'api_mode_needs_orena_base_url');
  assert.ok(!('Check preview' in o));
  const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
  assert.equal(report.sync_status, 'blocked');
  assert.ok(o['Build files'].some(f => f.json.role === 'ready'));
});

const BLOCKING = {
  'an HTML page with status 200': () => jsonReply(200, '<!doctype html><html><body>Sign in</body></html>', 'text/html; charset=utf-8'),
  'HTML served as JSON content-type': () => jsonReply(200, '<html>login</html>'),
  'a login redirect page': () => jsonReply(200, '<html></html>', 'text/html'),
  'an empty body': () => jsonReply(200, ''),
  'JSON that is not an object': () => jsonReply(200, '[1,2,3]'),
  'JSON without items': () => jsonReply(200, { ok: true }),
  'unknown extra shape': () => jsonReply(200, { items: [{}] }),
  'items that is not an array': () => jsonReply(200, { items: 'x' }),
  'two items for one file': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => b.items.push(clone(b.items[0])))),
  'a 401': () => jsonReply(401, { detail: 'Authentication required' }),
  'a 403': () => jsonReply(403, { detail: 'Platform administrator access required' }),
  'a 500': () => jsonReply(500, 'Internal Server Error', 'text/plain'),
  'a 3xx': () => jsonReply(302, ''),
  'a response without a status code': () => ({ json: { body: JSON.stringify(real.preview) } }),
  'a network error': () => ({ json: { error: { message: 'ECONNREFUSED' } } }),
  'no reply at all': () => ({ json: null }),
  'an item error': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].error = 'The file is not valid JSON'; })),
  'an item that was not read as authored entries': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { delete b.items[0].authored; })),
  'a refused row': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { const r = b.items[0].authored.rows[0]; r.outcome = 'refused'; r.reason = 'schema: x'; b.items[0].authored.counts = { ready: b.items[0].authored.rows.length - 1, refused: 1 }; })),
  'a conflict row': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { const r = b.items[0].authored.rows[0]; r.outcome = 'conflict'; r.existing = 'published_conflict'; r.reason = 'published'; b.items[0].authored.counts = { ready: b.items[0].authored.rows.length - 1, conflict: 1 }; })),
  'an unknown outcome': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.rows[0].outcome = 'maybe'; b.items[0].authored.counts = { ready: b.items[0].authored.rows.length - 1, maybe: 1 }; })),
  'a missing outcome': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { delete b.items[0].authored.rows[0].outcome; })),
  'existing: unknown (Orena could not look the entries up)': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.rows[0].existing = 'unknown'; })),
  'fewer rows than were sent': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.rows.pop(); b.items[0].authored.counts = { ready: b.items[0].authored.rows.length }; })),
  'other ids than were sent': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.rows[0].id = 'en:someone-else'; })),
  'counts that disagree with the rows': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.counts = { ready: 99 }; })),
  'another language': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].authored.language_code = 'fr'; })),
  'another file name': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { b.items[0].filename = 'other.jsonl'; })),
  'no content_hash': (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => { delete b.items[0].content_hash; })),
};
for (const [label, reply] of Object.entries(BLOCKING)) {
  await test(`api mode BLOCKS the import on ${label}`, async () => {
    const o = await apiRun({ previewReply: reply });
    assert.equal(o['Check preview'][0].json.passed, false, 'the preview check let it through');
    assert.ok(!('Check import' in o), 'the import ran');
    const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
    assert.equal(report.sync_status, 'blocked');
    assert.ok(report.groups.every(g => g.sync.status === 'blocked' && g.sync.reasons.length));
    assert.ok(o['Build files'].some(f => f.json.role === 'ready'), 'the local files must survive');
    assert.equal(o['Run summary'][0].json.sync_status, 'blocked');
  });
}

await test('one bad file holds the whole batch: nothing is imported', async () => {
  const o = await apiRun({ previewReply: (s) => s.language_code === 'zh' ? jsonReply(500, 'boom', 'text/plain') : jsonReply(200, previewFor(s.fileName, s.ids)) });
  assert.ok(!('Check import' in o));
  const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
  const en = report.groups.find(g => g.lang === 'en'), zh = report.groups.find(g => g.lang === 'zh-Hans');
  assert.equal(zh.sync.status, 'blocked'); assert.match(en.sync.reasons[0], /held/);
});

await test('a duplicate on rerun is accepted by the preview (skip) and the import reports skipped', async () => {
  const o = await apiRun({
    previewReply: (s) => jsonReply(200, previewFor(s.fileName, s.ids, b => b.items[0].authored.rows.forEach(r => { r.existing = 'duplicate'; }))),
    importReply: (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'pending_review' }, items: [{ ...real.import_skipped_item, filename: s.fileName, duplicates: s.ids.length }] }),
  });
  assert.equal(o['Check preview'][0].json.passed, true);
  assert.equal(o['Check import'].every(c => c.json.ok), true, JSON.stringify(o['Check import'].map(c => c.json.reasons)));
  assert.equal(o['Check import'][0].json.result.status, 'skipped');
});

const BAD_IMPORT = {
  'a published collection': (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'published' }, items: [{ ...real.import_item, filename: s.fileName }] }),
  'a collection that was not created': (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'not_created' }, items: [{ ...real.import_item, filename: s.fileName }] }),
  'a failed source': (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'pending_review' }, items: [{ ...real.import_item, status: 'failed', failed: 1, failure_reason: 'persistence unavailable' }] }),
  'conflicts': (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'pending_review' }, items: [{ ...real.import_item, conflicts: 1 }] }),
  'a 503': () => jsonReply(503, { detail: { category: 'vocabulary_schema_unavailable' } }),
  'HTML': () => jsonReply(200, '<html></html>', 'text/html'),
  'another collection id': () => jsonReply(200, { collection: { id: 'someone-else', title: 't', catalog_status: 'pending_review' }, items: [real.import_item] }),
  'missing counts': (s) => jsonReply(200, { collection: { id: s.collection_id, title: 't', catalog_status: 'pending_review' }, items: [{ status: 'imported' }] }),
};
for (const [label, reply] of Object.entries(BAD_IMPORT)) {
  await test(`api mode reports a failed sync (and keeps the files) on an import answer with ${label}`, async () => {
    const o = await apiRun({ importReply: reply });
    assert.equal(o['Check import'].some(c => !c.json.ok), true);
    const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
    assert.equal(report.sync_status, 'failed');
    assert.ok(o['Build files'].some(f => f.json.role === 'ready'));
  });
}

await test('an api run with nothing ready sends nothing', async () => {
  const o = await pipeline({ form: MANUAL({ 'Delivery mode': 'api', 'Word list': 'ephemeral — C3' }), env: { ORENA_BASE_URL: 'https://orena.example' }, enrich: {} });
  assert.equal(o['Prepare sync'][0].json.reason, 'no_ready_records');
  const report = JSON.parse(decode(o['Final report'].find(f => f.json.role === 'report_json')));
  assert.equal(report.sync_status, 'skipped_no_ready_records');
});

await test('a missing output folder stops the run first, naming the folder to create (n8n does not create it)', async () => {
  await assert.rejects(() => pipeline({ form: MANUAL(), enrich: ENRICH, probeFails: true }),
    /\/files\/orena is not writable.*ENOENT.*mkdir -p .*Nothing was generated/s);
  const o = await pipeline({ form: MANUAL(), enrich: ENRICH });
  assert.equal(o['Check output folder'][0].json.ok, true);
  // the probe runs before any download / enrichment node
  const order = ['Config', 'Output folder probe', 'Save probe', 'Check output folder', 'Parse words'];
  for (let i = 0; i < order.length - 1; i++) assert.ok(workflow.connections[order[i]].main[0].some(c => c.node === order[i + 1]), order[i]);
  assert.equal(byName['Save probe'].onError, 'continueRegularOutput');
});

// ================================================================ 9. critical vs non-critical writes
await test('a failed READY write is critical: the run stops and nothing is sent to Orena', async () => {
  await assert.rejects(() => apiRun({ saveFails: new Set(['ready']) }), /Critical write failed.*ready file.*Nothing was sent to Orena/);
});

await test('failed audit writes are non-critical: reported, the batch and the sync are unaffected', async () => {
  const o = await apiRun({ saveFails: new Set(['rejected', 'report_json', 'report_csv']), finalSaveFails: new Set(['report_csv']) });
  const summary = o['Run summary'][0].json;
  assert.equal(summary.sync_status, 'imported');
  assert.equal(summary.ready, 2);
  const failed = summary.non_critical_write_failures.map(w => w.role).sort();
  assert.deepEqual(failed, ['rejected', 'report_csv']);
  assert.ok(summary.non_critical_write_failures.every(w => w.error));
  assert.ok(summary.files.some(p => p.endsWith('.ready.jsonl')));
  // the ready bytes are the ones generated, whatever happened to the reports
  assert.equal(o['Validate & group'][0].json.groups[0].fileContent, FILE_RUN['Validate & group'][0].json.groups[0].fileContent);
});

// ================================================================ 10. the real routes' response shape (captured by tests/test_n8n_vocab_workflow.py)
await test('the committed Orena response fixture has the keys the workflow reads', () => {
  const item = real.preview.items[0];
  for (const k of ['filename', 'format', 'content_hash', 'row_count', 'error', 'authored']) assert.ok(k in item, k);
  for (const k of ['language_code', 'format', 'rows', 'counts', 'warnings']) assert.ok(k in item.authored, k);
  for (const k of ['row', 'id', 'term', 'warnings', 'outcome', 'identity_key', 'existing']) assert.ok(k in item.authored.rows[0], k);
  for (const k of ['status', 'imported', 'skipped', 'duplicates', 'failed', 'failure_reason', 'updated', 'conflicts']) assert.ok(k in real.import_item, k);
  assert.equal(real.import.collection.catalog_status, 'pending_review');
});

if (failures.length) {
  console.error(`\n${failures.length} FAILED, ${passed} passed\n`);
  for (const f of failures) console.error(' - ' + f + '\n');
  process.exit(1);
}
console.log(`test_n8n_vocab_workflow: ${passed} checks passed`);
