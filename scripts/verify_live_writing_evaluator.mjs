// Live EN/ZH Writing evaluator verification against the configured local
// Ollama model. This mirrors the application's evaluator request exactly:
// the same structured schema from writing_evaluator_contract.py, the same
// language system prompts from the profiles, the same SUPPORT LANGUAGE block
// the T12 request contract adds, and the same Ollama /api/chat contract the
// OllamaProvider sends. It is a manual/local gate, not CI: CI has no Ollama
// and must never depend on a live model.
import { readFileSync } from 'node:fs';

// Same configuration the application reads, with the same defaults.
const OLLAMA_URL = (process.env.OLLAMA_URL || 'http://127.0.0.1:11434').replace(/\/+$/, '');
const OLLAMA_MODEL = (process.env.OLLAMA_MODEL || 'qwen3:8b').trim();

const RUBRIC = ['grammar', 'vocabulary', 'coherence', 'task_achievement', 'naturalness'];
// CJK ideographs plus Hiragana/Katakana, matching the script the registry
// tags "cjk" (writing_coach/core/support_languages.py script_family).
const CJK_PATTERN = /[぀-ヿ㐀-䶿一-鿿豈-﫿]/;

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const between = (src, marker) => src.split(marker)[1]?.split('"""')[0] ?? '';
const quoted = (src, marker) =>
  [...(src.split(marker)[1] ?? '').split(')')[0].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);

// Derive support-language names/codes from the same registry the application
// resolves against, instead of hardcoding a second copy of it. This is a
// read-only parse for verification only; it does not touch application
// resolution (writing_coach/core/support_languages.py stays untouched).
function parseSupportLanguages(src) {
  const body = src.split('_DEFINITIONS = (')[1]?.split('\n)')[0] ?? '';
  const pattern = /SupportLanguageDefinition\(\s*"([a-z]{2,3})"\s*,\s*"([^"]+)"(?:\s*,\s*"([a-z]+)")?\s*\)/g;
  const definitions = {};
  for (const [, code, label, scriptFamily] of body.matchAll(pattern)) {
    definitions[code] = { code, label, cjk: scriptFamily === 'cjk' };
  }
  return definitions;
}

const enSource = read('writing_coach/languages/english/profile.py');
const zhSource = read('writing_coach/languages/chinese/profile.py');
const supportSource = read('writing_coach/core/support_languages.py');
const SUPPORT_LANGUAGES = parseSupportLanguages(supportSource);
for (const code of ['en', 'ja', 'zh']) {
  if (!SUPPORT_LANGUAGES[code]) {
    throw new Error(`Expected support language '${code}' in writing_coach/core/support_languages.py`);
  }
}

const EN = {
  system: between(enSource, 'SYSTEM_PROMPT = """'),
  errors: quoted(enSource, 'ERROR_CATEGORIES = ('),
  levels: ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'],
};
const ZH = {
  system: between(zhSource, 'SYSTEM_PROMPT = """'),
  errors: quoted(zhSource, 'ERROR_CATEGORIES = ('),
  levels: ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9'],
};

function buildSchema(levels, errorCategories) {
  const number = { type: 'number', minimum: 0, maximum: 100 };
  const properties = Object.fromEntries(RUBRIC.map((key) => [key, number]));
  properties.band_status = { type: 'string', enum: ['estimated', 'insufficient_evidence'] };
  properties.cefr_estimate = { type: 'string', enum: ['', ...levels] };
  properties.summary_vi = { type: 'string' };
  properties.strengths_vi = { type: 'array', items: { type: 'string' }, maxItems: 6 };
  properties.strength_evidence = {
    type: 'array',
    maxItems: 6,
    items: {
      type: 'object',
      properties: {
        category: { type: 'string', enum: RUBRIC },
        fragment: { type: 'string', minLength: 1 },
        explanation_vi: { type: 'string', minLength: 1 },
        confidence: { type: 'number', minimum: 0, maximum: 1 },
      },
      required: ['category', 'fragment', 'explanation_vi', 'confidence'],
    },
  };
  properties.priorities_vi = { type: 'array', items: { type: 'string' }, maxItems: 6 };
  properties.errors = {
    type: 'array',
    maxItems: 20,
    items: {
      type: 'object',
      properties: {
        category: { type: 'string', enum: errorCategories },
        fragment: { type: 'string', minLength: 1 },
        explanation_vi: { type: 'string', minLength: 1 },
        suggestion: { type: 'string', minLength: 1 },
        mini_rule_vi: { type: 'string', minLength: 1 },
        confidence: { type: 'number', minimum: 0, maximum: 1 },
      },
      required: ['category', 'fragment', 'explanation_vi', 'suggestion', 'mini_rule_vi', 'confidence'],
    },
  };
  return {
    type: 'object',
    properties,
    required: [
      ...RUBRIC,
      'band_status',
      'cefr_estimate',
      'summary_vi',
      'strengths_vi',
      'strength_evidence',
      'priorities_vi',
      'errors',
    ],
  };
}

// Mirrors writing_coach/writing_evaluator_contract.py's
// build_writing_evaluator_request exactly, including the T12 SUPPORT
// LANGUAGE block, which is emitted separately from TARGET LANGUAGE and keeps
// learner fragments/corrections in the target language.
function buildUserPrompt(languageName, supportLanguageName, targetLevel, taskPrompt, learnerText) {
  const parts = [`TARGET LANGUAGE: ${languageName}\n`, `SUBMISSION MODE: guided\n`];
  if (supportLanguageName) {
    parts.push(
      `SUPPORT LANGUAGE: ${supportLanguageName}\n`,
      'SUPPORT LANGUAGE POLICY:\n',
      `Write explanations, summaries, strengths, priorities and reusable rules in ${supportLanguageName}.\n`,
      'Keep learner fragments, corrections and target-language examples in the TARGET LANGUAGE.\n',
    );
  }
  if (targetLevel) {
    parts.push(
      `TARGET LEVEL (LEARNING CONTEXT ONLY): ${targetLevel}\n`,
      'TARGET LEVEL POLICY:\n',
      'The target level guides pedagogical relevance and expected sophistication. ',
      'Estimate the learner\'s actual demonstrated performance. Do not force the proficiency ',
      'estimate upward, inflate scores, or deflate scores merely to match the target level.\n',
    );
  }
  parts.push(
    'DEMONSTRATED BAND POLICY:\n',
    'Infer only the band demonstrated by this sample. Requested length must not affect scores ',
    'or the demonstrated band. If the sample is too short, repetitive, or otherwise too limited ',
    "for a defensible estimate, return band_status='insufficient_evidence' and an empty ",
    'cefr_estimate while retaining only grounded language feedback.\n',
    'TASK ACHIEVEMENT: applicable\n',
    '<WRITING_TASK>\n',
    `${taskPrompt}\n`,
    '</WRITING_TASK>\n',
    '\n<LEARNER_TEXT>\n',
    `${learnerText}\n`,
    '</LEARNER_TEXT>\n\n',
    'EVALUATION AND EVIDENCE CONTRACT:\n',
    '- Evaluate the ORIGINAL learner text, not a rewritten version.\n',
    '- Never invent learner evidence. Every returned `fragment` must occur literally in ',
    'LEARNER_TEXT.\n',
    '- Every strength_evidence item must describe a genuine strength visible in its exact fragment.\n',
    '- Identify 1-3 exact learner fragments that demonstrate genuine strengths.\n',
    '- Every errors item must describe a genuine problem visible in its exact fragment.\n',
    '- Every error suggestion must meaningfully differ from the erroneous fragment.\n',
    '- If uncertain whether something is wrong, omit it. Fewer high-confidence findings are ',
    'preferable to many doubtful findings.\n',
    '- Return evidence only when confidence >= 0.75.\n',
    '- Focus on recurring or reusable learning points, not only isolated typos.\n',
    'Return one complete JSON object matching the supplied structured schema.',
  );
  return parts.join('');
}

// Deterministic, offline self-check of the T12 request contract (acceptance
// criterion 1): fails fast, before any live call, if the SUPPORT LANGUAGE
// block ever drifts from writing_evaluator_contract.py's wording.
function assertSupportLanguageContract(prompt, supportName) {
  const problems = [];
  if (!prompt.includes(`SUPPORT LANGUAGE: ${supportName}\n`)) {
    problems.push(`missing 'SUPPORT LANGUAGE: ${supportName}' line`);
  }
  if (!prompt.includes(`Write explanations, summaries, strengths, priorities and reusable rules in ${supportName}.`)) {
    problems.push('missing the support-language explanatory-field instruction');
  }
  if (!prompt.includes('Keep learner fragments, corrections and target-language examples in the TARGET LANGUAGE.')) {
    problems.push('missing the target-language fragment/correction separation instruction');
  }
  if (!prompt.includes('SUPPORT LANGUAGE')) {
    problems.push('SUPPORT LANGUAGE block absent entirely');
  }
  const targetIdx = prompt.indexOf('TARGET LANGUAGE:');
  const supportIdx = prompt.indexOf('SUPPORT LANGUAGE:');
  if (targetIdx === -1 || supportIdx === -1 || supportIdx <= targetIdx) {
    problems.push('SUPPORT LANGUAGE block must follow TARGET LANGUAGE');
  }
  if (problems.length) {
    throw new Error(`Request contract check failed: ${problems.join('; ')}`);
  }
}

async function evaluate({ name, language, system, errors, levels, target, text, supportName }) {
  const taskPrompt = 'Write one short practice response.';
  const prompt = buildUserPrompt(language, supportName, target, taskPrompt, text);
  assertSupportLanguageContract(prompt, supportName);
  const body = {
    model: OLLAMA_MODEL,
    stream: false,
    think: false,
    keep_alive: '30m',
    format: buildSchema(levels, errors),
    options: { temperature: 0.0, num_ctx: 4096, num_predict: 2200, seed: 42 },
    messages: [
      { role: 'system', content: system },
      { role: 'user', content: prompt },
    ],
  };
  const response = await fetch(`${OLLAMA_URL}/api/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(240000),
  });
  const envelope = await response.json();
  const content = envelope?.message?.content;
  if (typeof content !== 'string' || !content.trim()) {
    throw new Error(`${name}: Ollama returned no message content`);
  }
  const parsed = JSON.parse(content);
  return { name, parsed, done_reason: envelope.done_reason, contentLength: content.length };
}

// Every explanatory field the T12 contract asks the model to write in the
// SUPPORT LANGUAGE, not the target language.
function explanatoryStrings(p) {
  const strings = [];
  if (typeof p.summary_vi === 'string') strings.push(p.summary_vi);
  for (const s of p.strengths_vi || []) if (typeof s === 'string') strings.push(s);
  for (const s of p.priorities_vi || []) if (typeof s === 'string') strings.push(s);
  for (const s of p.strength_evidence || []) if (typeof s?.explanation_vi === 'string') strings.push(s.explanation_vi);
  for (const e of p.errors || []) {
    if (typeof e?.explanation_vi === 'string') strings.push(e.explanation_vi);
    if (typeof e?.mini_rule_vi === 'string') strings.push(e.mini_rule_vi);
  }
  return strings.filter((s) => s.trim());
}

function check(result, text, errors, levels, supportCjk) {
  const p = result.parsed;
  const explanations = explanatoryStrings(p);
  return {
    requiredKeys: [...RUBRIC, 'band_status', 'cefr_estimate', 'summary_vi', 'strengths_vi', 'strength_evidence', 'priorities_vi', 'errors'].every((key) => key in p),
    scoresInRange: RUBRIC.every((key) => typeof p[key] === 'number' && p[key] >= 0 && p[key] <= 100),
    bandStatus: ['estimated', 'insufficient_evidence'].includes(p.band_status),
    insufficientEvidenceConsistent: p.band_status !== 'insufficient_evidence' || p.cefr_estimate === '',
    level: p.cefr_estimate === '' || levels.includes(p.cefr_estimate),
    errorsGrounded: Array.isArray(p.errors) && p.errors.every((e) =>
      typeof e?.category === 'string' && errors.includes(e.category)
      && typeof e?.fragment === 'string' && text.includes(e.fragment)
      && typeof e?.suggestion === 'string' && e.suggestion.trim() && e.suggestion !== e.fragment
      && typeof e?.explanation_vi === 'string' && e.explanation_vi.trim()
      && typeof e?.mini_rule_vi === 'string' && e.mini_rule_vi.trim()
      && typeof e?.confidence === 'number' && e.confidence >= 0.75 && e.confidence <= 1),
    strengthsGrounded: Array.isArray(p.strength_evidence) && p.strength_evidence.every((s) =>
      typeof s?.category === 'string' && RUBRIC.includes(s.category)
      && typeof s?.fragment === 'string' && text.includes(s.fragment)
      && typeof s?.explanation_vi === 'string' && s.explanation_vi.trim()
      && typeof s?.confidence === 'number' && s.confidence >= 0.75 && s.confidence <= 1),
    // Explanatory fields must be non-empty, and where the requested support
    // language makes the check meaningful (its script is unambiguous either
    // way), consistent with that script rather than with the target
    // language's script — this is exactly the allow_explanation_cjk/allow_cjk
    // decoupling T12 introduced.
    explanationsNonEmpty: explanations.length > 0,
    explanationScriptMatchesSupportLanguage: explanations.every((s) =>
      supportCjk ? CJK_PATTERN.test(s) : !CJK_PATTERN.test(s)),
  };
}

const EN_SUPPORT = SUPPORT_LANGUAGES.en;
const JA_SUPPORT = SUPPORT_LANGUAGES.ja;
const ZH_SUPPORT = SUPPORT_LANGUAGES.zh;

const cases = [
  {
    name: 'en-support-en',
    language: 'English',
    system: EN.system,
    errors: EN.errors,
    levels: EN.levels,
    target: 'B1',
    text: 'Yesterday I go to the shop and buyed some bread for my family. It were a sunny day and the people was very friendly to me.',
    supportCode: EN_SUPPORT.code,
    supportName: EN_SUPPORT.label,
    supportCjk: EN_SUPPORT.cjk,
  },
  {
    // Decoupling case: English target with a CJK support language, so
    // explanatory fields must switch script while learner fragments/
    // corrections (checked against the English text) stay in English.
    name: 'en-support-ja',
    language: 'English',
    system: EN.system,
    errors: EN.errors,
    levels: EN.levels,
    target: 'B1',
    text: 'Yesterday I go to the shop and buyed some bread for my family. It were a sunny day and the people was very friendly to me.',
    supportCode: JA_SUPPORT.code,
    supportName: JA_SUPPORT.label,
    supportCjk: JA_SUPPORT.cjk,
  },
  {
    name: 'zh-support-zh',
    language: 'Chinese',
    system: ZH.system,
    errors: ZH.errors,
    levels: ZH.levels,
    target: 'HSK2',
    text: '我在商店买了一个书，然后我回家。昨天天气很好，我们都很高兴。',
    supportCode: ZH_SUPPORT.code,
    supportName: ZH_SUPPORT.label,
    supportCjk: ZH_SUPPORT.cjk,
  },
  {
    // Decoupling case in the other direction: Chinese (CJK) target with a
    // Latin support language, so explanatory fields must stay Latin even
    // though the target-language fragments they cite are Chinese.
    name: 'zh-support-en',
    language: 'Chinese',
    system: ZH.system,
    errors: ZH.errors,
    levels: ZH.levels,
    target: 'HSK2',
    text: '我在商店买了一个书，然后我回家。昨天天气很好，我们都很高兴。',
    supportCode: EN_SUPPORT.code,
    supportName: EN_SUPPORT.label,
    supportCjk: EN_SUPPORT.cjk,
  },
];

const results = [];
for (const item of cases) {
  const result = await evaluate(item);
  results.push({
    name: result.name,
    requestedSupportLanguage: { code: item.supportCode, name: item.supportName, cjk: item.supportCjk },
    done_reason: result.done_reason,
    contentLength: result.contentLength,
    checks: check(result, item.text, item.errors, item.levels, item.supportCjk),
    summary: {
      band: result.parsed.band_status,
      level: result.parsed.cefr_estimate,
      scores: Object.fromEntries(RUBRIC.map((key) => [key, result.parsed[key]])),
      errors: (result.parsed.errors || []).map((e) => ({ category: e.category, fragment: e.fragment, suggestion: e.suggestion })),
      strengths: (result.parsed.strength_evidence || []).map((s) => ({ category: s.category, fragment: s.fragment })),
      // A sample so a script-consistency failure can be read directly from
      // the report instead of requiring a re-run.
      summary_vi: result.parsed.summary_vi,
    },
  });
}

console.log(JSON.stringify(results, null, 2));

const allChecksPass = results.every((r) =>
  Object.values(r.checks).every((value) => value === true),
);
process.exitCode = allChecksPass ? 0 : 1;
