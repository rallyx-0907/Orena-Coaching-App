/* Pure data shaping for the Grammar Concept screen (pinned design frame 47, the generic
   "gconcept" template - the only Grammar Concept route the shell has; SCRATCH/reports/
   primitives.md's own measurement confirms 47, not the hand-built 23, is the one reachable from a
   real route). No DOM, no fetch: a node gate (scripts/test_orena_screen_grammar.mjs) exercises
   this directly.

   The backend (GET /api/library/grammar/{id}) returns a full `learning_model` (schema v2,
   writing_coach/grammar_learning_model.py): a flow of stages, each carrying one or more typed
   `blocks`. static/orena/capabilities/grammar-pedagogy.js already classifies a concept's
   archetype and picks the block type that should lead ("primaryModelType") - this module wires
   that classifier onto frame 47's three drawn cards (Concept: pattern + examples + common
   mistake; Quiz: multiple-choice micro_practice; Try it yourself: personal_practice) rather than
   re-deriving the pedagogy. A block type 47 draws no visual for (timeline, contrast, scene,
   sentence_builder, transformation, inflection_table, recall, memory_hook, skill_transfer) is
   never invented a bespoke widget (rule 44); the pattern slot falls back to a generic
   chip/row rendering built only from primitives the frame already draws (see primaryPattern's
   'rows' kind) - recorded as a backend/design gap in SCRATCH/reports/grammar.md. */
import { primaryModelType } from '../../capabilities/grammar-pedagogy.js';
import { guidanceLocale } from '../../product/languages.js';

/* A learning_model text field is a plain string (target-language content: a pattern word, an
   example) or a locale map (explanatory prose, authored in whichever of en/vi/zh the curriculum
   has - grammar_learning_model.py's `_text()`). Picked by the learner's support language, English
   the documented fallback (never the interface language - D-079).

   `_text()`'s own validator (writing_coach/grammar_learning_model.py `_locale_key`) accepts a key
   that is either a BCP-47 code or the literal string `"default"` - a locale-neutral fallback the
   schema itself defines, not a frontend guess. The live catalogue actually uses it: every concept
   checked has `{vi: "...", default: "..."}` for its summary/common-mistake/personal-practice
   prose (identical text under both keys right now - the pipeline has only authored Vietnamese
   explanatory prose so far, a content gap recorded in SCRATCH/reports/grammar.md and
   docs/project/UI_BACKEND_GAPS.md, not a fabrication). Falling through to `value[codes[0]]` when
   neither the support locale nor English exists happened to read right by accident (`vi` is
   inserted before `default` in every concept seen), but is a coincidence of object key order, not
   a rule - `value.default` is the schema's own documented fallback and is checked explicitly. */
export function pickLocale(value, support = 'en') {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') {
    const codes = Object.keys(value);
    if (!codes.length) return '';
    const code = guidanceLocale(support, codes);
    return value[code] ?? value.en ?? value.default ?? value[codes[0]] ?? '';
  }
  return String(value);
}

export function findBlock(lesson, type) {
  const blocks = lesson?.learning_model?.blocks;
  return Array.isArray(blocks) ? blocks.find((block) => block?.type === type) || null : null;
}

function blocksOfType(lesson, type) {
  const blocks = lesson?.learning_model?.blocks;
  return Array.isArray(blocks) ? blocks.filter((block) => block?.type === type) : [];
}

/* The four semantic-role buckets frame 47's pattern chips draw (a=accent/b=green/k=neutral/
   m=amber, E5 §2.2). grammar_learning_model.py's SEMANTIC_ROLES has 30+ roles (far more than the
   two concepts the mock ever exercised); this buckets every one deterministically rather than
   adding a fifth colour the frame does not draw. Functional/operating words lead (accent); the
   result/outcome of the pattern is the "changed" state (green); the participants are neutral;
   everything else (time, place, degree, form-class, exceptions) is the marked/amber case. */
const ROLE_BUCKET = {
  verb: 'a', auxiliary: 'a', particle: 'a', negation: 'a', connector: 'a', conjunction: 'a', marker: 'a',
  complement: 'b', result: 'b', changed: 'b',
  subject: 'k', agent: 'k', patient: 'k', topic: 'k', pronoun: 'k', noun: 'k', object: 'k',
};

export function roleBucket(role) {
  return ROLE_BUCKET[String(role || '').toLowerCase()] || 'm';
}

/* The lead teaching object for the "Pattern" section: the block composeLesson's archetype names
   as primary if the concept has it, else the flow's own pattern-stage block. `kind: 'chips'`
   covers every segment-shaped block type (formula/semantic_sentence/word_order/position/
   insertion/particle_position/agreement_map - all `{parts|segments:[{text,role,label|meaning}]}`,
   the same shape frame 47 draws for `formula`). `kind: 'transform'` covers `transformation`
   (from/to, no chip shape in the source - rendered as two chips with an arrow, reusing the chip
   primitive rather than inventing a new one). Anything else falls back to `kind: 'rows'`, reusing
   frame 47's own example-row shell generically (label/text/note) rather than building the
   timeline/contrast/scene/table visuals the archetype system implies but no reachable frame
   draws. */
export function primaryPattern(lesson, support = 'en') {
  const type = primaryModelType(lesson);
  const block = (type && blocksOfType(lesson, type)[0]) || findBlock(lesson, 'formula') || findBlock(lesson, 'semantic_sentence');
  if (!block) return null;
  const payload = block.payload || {};
  const title = pickLocale(block.title, support);
  const parts = payload.parts || payload.segments;
  if (Array.isArray(parts)) {
    return {
      kind: 'chips',
      title,
      parts: parts.map((part) => ({
        text: pickLocale(part.text, support),
        role: roleBucket(part.role),
        label: pickLocale(part.label ?? part.meaning, support),
      })),
    };
  }
  if (block.type === 'transformation') {
    return { kind: 'transform', title, from: pickLocale(payload.from, support), to: pickLocale(payload.to, support) };
  }
  const rows =
    payload.events ||
    payload.items ||
    payload.lines ||
    (payload.slots || []).map((slot) => ({ label: slot.label, text: (slot.options || []).map((option) => pickLocale(option, support)).join(' / ') })) ||
    [];
  return {
    kind: 'rows',
    title,
    rows: (Array.isArray(rows) ? rows : []).map((row) => ({
      label: pickLocale(row.label ?? row.speaker, support),
      text: pickLocale(row.text, support),
      note: pickLocale(row.note ?? row.meaning, support),
    })),
  };
}

/* Frame 47's "Examples" section is the lesson's own authored `examples[]` (plain target-language
   sentences with a translation), not the learning_model's `scene` block - a closer visual and
   content match (E5 §2.2: plain sentence rows, not a dialogue).

   Bug fixed here: every example in the real catalogue (English- and Chinese-target alike) only
   ever carries a Vietnamese gloss (`meaning_vi`, `vi` - confirmed against the live API for both
   target languages; no `meaning_en`/`meaning_zh` field exists anywhere in the content pipeline).
   The first version of this function returned that Vietnamese text unconditionally, regardless of
   the learner's actual support language - a real EN/ZH parity break (D-079, AGENTS.md "no
   hardcoding"): an English- or Chinese-support learner would see an unlabelled Vietnamese
   sentence they cannot read, not an absent translation. `guidanceLocale` (product/languages.js) is
   the existing primitive for "does the learner's support language match a pack this field
   actually has" - here the only pack is `['vi']` - so the gloss is shown only when the learner's
   support language resolves to vi, and left off (rule 40's honest empty, not a fabricated one)
   for every other support language. */
export function examplesOf(lesson, support = 'en') {
  const hasViGloss = guidanceLocale(support, ['vi']) === 'vi';
  return (Array.isArray(lesson?.examples) ? lesson.examples : [])
    .filter((example) => example?.target)
    .map((example) => ({ text: example.target, translation: hasViGloss ? example.meaning_vi || example.vi || '' : '' }));
}

export function mistakeOf(lesson, support = 'en') {
  const block = findBlock(lesson, 'common_mistake');
  if (!block) return null;
  const payload = block.payload || {};
  return {
    incorrect: pickLocale(payload.incorrect, support),
    correct: pickLocale(payload.correct, support),
    why: pickLocale(payload.why, support),
  };
}

const CHOICE_INTERACTIONS = new Set(['choose', 'classify', 'identify', 'compare']);

/* Every micro_practice block whose interaction is a "pick one option" shape - the only shape
   frame 47's quiz card draws (lettered options, one answer, an explanation on reveal). A
   reorder/build/match/fill/transform/speak/write interaction has no drawn quiz visual and is left
   out of the quiz rather than forced into it (rule 43); recorded as a design gap. */
export function quizQuestions(lesson, support = 'en') {
  return blocksOfType(lesson, 'micro_practice')
    .map((block) => block.payload || {})
    .filter((payload) => CHOICE_INTERACTIONS.has(payload.interaction))
    .map((payload) => ({
      prompt: pickLocale(payload.prompt, support),
      options: (Array.isArray(payload.options) ? payload.options : []).map((option) => pickLocale(option, support)),
      answer: pickLocale(payload.answer, support),
      explanation: pickLocale(payload.explanation, support),
    }))
    .filter((question) => question.prompt && question.options.length);
}

export function personalPractice(lesson, support = 'en') {
  const block = findBlock(lesson, 'personal_practice');
  if (!block) return null;
  const payload = block.payload || {};
  return { prompt: pickLocale(payload.prompt, support), placeholder: pickLocale(payload.placeholder, support) };
}

/* "Grammar · {level} · {family}" (E5 §2.2's header meta), family being whichever real field the
   lesson carries. */
export function headerMeta(lesson) {
  return { level: lesson?.level || '', family: lesson?.module || lesson?.category || '' };
}
