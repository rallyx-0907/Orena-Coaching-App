// Code node "Config" - every setting of the workflow lives here. No secret belongs in this node:
// the Orena token and the AI key are n8n Credentials (Header Auth) chosen on the HTTP nodes.
//
// Where a value comes from (first match wins): the form / manual input -> the SETTINGS block below -> an n8n
// environment variable. n8n 2.x may block $env in Code nodes (N8N_BLOCK_ENV_ACCESS_IN_NODE); then edit SETTINGS.
const SETTINGS = {
  output: {
    dir: '',                        // '' = /files/orena, inside the n8n container: mount a Docker volume there (README). Env: ORENA_VOCAB_OUT_DIR
  },
  orena: {
    baseUrl: '',                    // api mode only, e.g. https://orena.example (no trailing path). Env: ORENA_BASE_URL
    allowFormOverwrite: false,      // true = a form submitter may choose duplicates=overwrite. Env: ORENA_VOCAB_ALLOW_FORM_OVERWRITE=true
  },
  ai: {
    enabled: true,                  // AI only fills gaps the dictionaries leave; with no endpoint/model it is simply off
    endpoint: '',                   // OpenAI-compatible chat completions URL. Env: AI_ENDPOINT
    model: '',                      // Env: AI_MODEL
  },
  metadata: {
    // What the generator can honestly claim. It reads Free Dictionary (Wiktionary, CC BY-SA), Tatoeba (CC BY 2.0 FR),
    // CC-CEDICT / CVDICT (CC BY-SA), Unihan and Make Me a Hanzi: attribution / share-alike terms apply, and no one has
    // cleared this batch. Authored entries land pending_review whatever is written here (D-178); raise these only
    // after a human has actually checked the rights and the batch is a whole set.
    rights_status: 'unknown',
    completeness: 'partial',
  },
};

const DEFAULT_OUTPUT_DIR = '/files/orena';
const env = k => { try { return ($env && $env[k]) || ''; } catch (e) { return ''; } };
const flag = v => ['1', 'true', 'yes', 'on'].includes(String(v || '').trim().toLowerCase());
const form = $input.first().json || {};
const pick = (...keys) => { for (const k of keys) if (form[k] !== undefined && form[k] !== null && String(form[k]).trim() !== '') return String(form[k]); return ''; };
// Only the manual "Test input" path is operator-controlled. Anything else arrives through the form trigger (a webhook).
const trusted = form._trigger === 'manual';
const now = new Date();
const runId = now.toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '-');   // 20261013-091500

let mode = (pick('Delivery mode', 'mode') || 'file').toLowerCase();
if (!['file', 'api'].includes(mode)) throw new Error("Delivery mode must be 'file' or 'api'");

let duplicates = (pick('When already stored', 'duplicates') || 'skip').toLowerCase();
if (!['skip', 'overwrite'].includes(duplicates)) throw new Error("duplicates must be 'skip' or 'overwrite'");
let duplicatesNote = '';
const overwriteAllowed = trusted || SETTINGS.orena.allowFormOverwrite || flag(env('ORENA_VOCAB_ALLOW_FORM_OVERWRITE'));
if (duplicates === 'overwrite' && !overwriteAllowed) {
  duplicates = 'skip';
  duplicatesNote = "'overwrite' was requested through the form, which is not allowed to overwrite; 'skip' was used instead";
}

const dir = String(SETTINGS.output.dir || env('ORENA_VOCAB_OUT_DIR') || DEFAULT_OUTPUT_DIR).replace(/\/+$/, '');
if (!/^\/[A-Za-z0-9_\-. \/]+$/.test(dir) || dir.split('/').includes('..')) throw new Error('output.dir must be an absolute path without ".."');

const baseUrl = String(SETTINGS.orena.baseUrl || env('ORENA_BASE_URL') || '').trim().replace(/\/+$/, '');
if (baseUrl && !/^https?:\/\/[^\s/]+$/i.test(baseUrl)) throw new Error('orena.baseUrl must be an origin such as https://orena.example');

const aiEndpoint = String(SETTINGS.ai.endpoint || env('AI_ENDPOINT') || '').trim();
const aiModel = String(SETTINGS.ai.model || env('AI_MODEL') || '').trim();

const config = {
  runId,
  trusted,
  mode,
  duplicates,
  duplicatesNote,

  input: {
    text: pick('Word list', 'words'),             // one per line: word - level [- Vietnamese meaning]
    title: pick('Batch title', 'title'),
    collectionId: pick('Collection ID', 'collection_id'),
  },

  orena: {
    baseUrl,
    previewUrl: baseUrl + '/api/admin/vocabulary/preview',
    importUrl: baseUrl + '/api/admin/vocabulary/import',
    configured: !!baseUrl,
    fileFormat: 'jsonl',            // 'jsonl' | 'json'
  },

  metadata: { ...SETTINGS.metadata },

  record: {
    status: 'draft',                // the generator never publishes; Orena ignores the file's status and holds the set for review
    allowedStatuses: ['draft'],
    maxExamples: 2,                 // 1-4 (schema)
    // The level is what the operator typed. Nothing here checks it against a word list, and the sources say so.
    levelSourceEN: 'operator-supplied CEFR level (not checked against a word list)',
    levelSourceZH: 'operator-supplied HSK level (not checked against the HSK 3.0 list)',
  },

  sources: {
    freeDictionary: 'https://api.dictionaryapi.dev/api/v2/entries/en/',
    tatoebaSearch: 'https://tatoeba.org/en/api_v0/search',
    cedict: 'https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz',
    cvdict: 'https://raw.githubusercontent.com/ph0ngp/CVDICT/main/CVDICT.u8',
    makeMeAHanzi: 'https://raw.githubusercontent.com/skishore/makemeahanzi/master/dictionary.txt',
    unihan: 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip',
  },
  zhLookup: { path: dir + '/zh_lookup.json', rebuild: false },

  ai: {
    enabled: !!SETTINGS.ai.enabled,
    endpoint: aiEndpoint,
    model: aiModel,
    fill: { pos: true, meaning_vi: true, translation_vi: true, examples: true, ipa: true },
  },
  // IPA the dictionary does not tag as UK or US: 'none' = do not use it (AI fills or the word is rejected)
  untaggedIpaAs: 'none',

  output: { dir },
};

config.record.maxExamples = Math.min(4, Math.max(1, config.record.maxExamples | 0));
if (config.record.status === 'published') throw new Error('The generator never publishes: record.status cannot be published');
config.ai.active = !!(config.ai.enabled && config.ai.endpoint && config.ai.model);
if (config.ai.active && !/^https?:\/\//i.test(config.ai.endpoint)) throw new Error('AI endpoint must be an http(s) URL');

return [{ json: config }];
