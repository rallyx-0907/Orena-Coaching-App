// Live EN/ZH Writing evaluator verification against the configured local
// Ollama model. This mirrors the application's evaluator request exactly:
// the same structured schema from writing_evaluator_contract.py, the same
// language system prompts from the profiles, and the same Ollama /api/chat
// contract the OllamaProvider sends. It is a manual/local gate, not CI: CI has
// no Ollama and must never depend on a live model.
import { readFileSync } from 'node:fs';

// Same configuration the application reads, with the same defaults.
const OLLAMA_URL = (process.env.OLLAMA_URL || 'http://127.0.0.1:11434').replace(/\/+$/, '');
const OLLAMA_MODEL = (process.env.OLLAMA_MODEL || 'qwen3:8b').trim();

const RUBRIC = ['grammar', 'vocabulary', 'coherence', 'task_achievement', 'naturalness'];

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const between = (src, marker) => src.split(marker)[1]?.split('"""')[0] ?? '';
const quoted = (src, marker) =>
  [...(src.split(marker)[1] ?? '').split(')')[0].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);

const enSource = read('writing_coach/languages/english/profile.py');
const zhSource = read('writing_coach/languages/chinese/profile.py');
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

function buildUserPrompt(languageName, targetLevel, taskPrompt, learnerText) {
  const parts = [`TARGET LANGUAGE: ${languageName}\n`, `SUBMISSION MODE: guided\n`];
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

async function evaluate({ name, language, system, errors, levels, target, text }) {
  const taskPrompt = 'Write one short practice response.';
  const body = {
    model: OLLAMA_MODEL,
    stream: false,
    think: false,
    keep_alive: '30m',
    format: buildSchema(levels, errors),
    options: { temperature: 0.0, num_ctx: 4096, num_predict: 2200, seed: 42 },
    messages: [
      { role: 'system', content: system },
      { role: 'user', content: buildUserPrompt(language, target, taskPrompt, text) },
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

function check(result, text, errors, levels) {
  const p = result.parsed;
  return {
    requiredKeys: [...RUBRIC, 'band_status', 'cefr_estimate', 'summary_vi', 'strengths_vi', 'strength_evidence', 'priorities_vi', 'errors'].every((key) => key in p),
    scoresInRange: RUBRIC.every((key) => typeof p[key] === 'number' && p[key] >= 0 && p[key] <= 100),
    bandStatus: ['estimated', 'insufficient_evidence'].includes(p.band_status),
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
  };
}

const cases = [
  {
    name: 'en',
    language: 'English',
    system: EN.system,
    errors: EN.errors,
    levels: EN.levels,
    target: 'B1',
    text: 'Yesterday I go to the shop and buyed some bread for my family. It were a sunny day and the people was very friendly to me.',
  },
  {
    name: 'zh',
    language: 'Chinese',
    system: ZH.system,
    errors: ZH.errors,
    levels: ZH.levels,
    target: 'HSK2',
    text: '我在商店买了一个书，然后我回家。昨天天气很好，我们都很高兴。',
  },
];

const results = [];
for (const item of cases) {
  const result = await evaluate(item);
  results.push({
    name: result.name,
    done_reason: result.done_reason,
    contentLength: result.contentLength,
    checks: check(result, item.text, item.errors, item.levels),
    summary: {
      band: result.parsed.band_status,
      level: result.parsed.cefr_estimate,
      scores: Object.fromEntries(RUBRIC.map((key) => [key, result.parsed[key]])),
      errors: (result.parsed.errors || []).map((e) => ({ category: e.category, fragment: e.fragment, suggestion: e.suggestion })),
      strengths: (result.parsed.strength_evidence || []).map((s) => ({ category: s.category, fragment: s.fragment })),
    },
  });
}

console.log(JSON.stringify(results, null, 2));

const allChecksPass = results.every((r) =>
  Object.values(r.checks).every((value) => value === true),
);
process.exitCode = allChecksPass ? 0 : 1;
