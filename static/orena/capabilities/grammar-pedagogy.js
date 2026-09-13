/* The pedagogical layer of the Grammar system.
 *
 * ORENA_GRAMMAR_LESSON_DESIGN_SYSTEM §26 puts four layers under Grammar:
 *
 *     GRAMMAR KNOWLEDGE → PEDAGOGICAL LESSON MODEL → RENDERER → LEARNER STATE
 *
 * The knowledge layer is closed (master spec §13.5: no mass rewrite, no runtime
 * regeneration, no casual id changes) and the renderer "should not invent
 * pedagogy" (§26.3). This module is the layer between them, and it was missing:
 * it decides what kind of concept is being taught and what each part of its
 * pattern actually is.
 *
 * Everything here is derived, never invented. The curriculum already states the
 * roles - a 把 pattern is authored as `S / 把 / specific O / complex VP+result`
 * and a 被 pattern as `Patient / 被 / agent / VP` - but files them all under
 * `role: "marker"` with the labels "Part 1, Part 2, Part 3". So the words are
 * there and the meaning is not attached to them. This reads the meaning back
 * off the words the content itself uses.
 *
 * Deterministic by design: master spec §0.5 puts deterministic logic first and
 * keeps AI out of the hot path, and grammar curriculum lookup is on its list of
 * things that must never call a model.
 */

/* ------------------------------------------------------------- segments --- */

/* Ordered: the first match wins, so the specific markers are tested before the
   general word lists. Each entry is [role, test]. */
const ROLE_RULES=[
  // Chinese grammatical markers keep their own identity - they are the concept
  // being taught, not a generic part of it.
  ['marker',/^(把|被|给|让|叫|使|由|对|跟|和|比|从|向|往)$/u],
  ['particle',/^(了|过|着|的|地|得|吗|呢|吧|啊|嘛|呀)$/u],
  ['negation',/^(不|没|没有|别|无|非)$/u],

  ['subject',/^(s|subj|subject|doer)\b/i],
  ['agent',/^(agent)\b/i],
  ['subject',/^(主语|施事)/u],
  ['patient',/^(patient|undergoer)\b/i],
  ['patient',/^(受事)/u],
  ['object',/^(o|obj|object|specific o|definite o)\b/i],
  ['object',/^(宾语|受词)/u],
  ['verb',/^(v\d?|vp|verb|predicate|action)\b/i],
  ['verb',/^(动词|谓语)/u],
  ['complement',/\b(result|complement|resultative)\b/i],
  ['complement',/(补语|结果)/u],
  ['classifier',/\b(measure word|classifier|mw|numeral)\b/i],
  ['classifier',/(量词|数量)/u],
  ['time',/^(time|when|tense marker)\b/i],
  ['time',/(时间|时候)/u],
  ['location',/^(place|location|where)\b/i],
  ['location',/(地点|处所)/u],
  /* Anchored, because these must fire when a part *names* a role, not when it
     happens to contain the word: "I/you/we/they have" is a chunk of the pattern,
     not the label "auxiliary", and an unanchored `have` turned the whole Present
     Perfect pattern into three mislabelled boxes. The complement rules above stay
     unanchored on purpose - "complex VP/result/location/recipient." is a
     slash-list of role names, which is exactly what it claims to be. */
  ['auxiliary',/^(aux|auxiliary|modal)\b/i],
  ['preposition',/^(prep|preposition)\b/i],
  ['article',/^(article|a \/ an)\b/i],
  ['adjective',/^(adj|adjective)\b/i],
  ['adverb',/^(adv|adverb)\b/i],
  ['noun',/^(n|noun)\b/i],
  ['topic',/^(topic)\b/i],
  ['topic',/(主题|话题)/u],
];

/* An authored role that says nothing. The curriculum files most parts under
   `marker` regardless of what they are, so `marker` on its own is treated as
   "not yet classified" rather than as a claim. */
const UNSPECIFIC_ROLES=new Set(['','marker','segment','part','piece','item']);

/* "Part 1" / "Thành phần 2" / "成分 3" / "Distinction 1" / "Phân biệt 2" /
   "辨析 3" - a position, not a name. */
const GENERIC_LABEL=/^(part|thành phần|thanh phan|成分|distinction|phân biệt|phan biet|辨析|section|khối)\s*\d+[.:]?$/iu;

export function isGenericLabel(label){
  return GENERIC_LABEL.test(String(label||'').trim());
}

/* The role a part plays, read off the part itself. An authored role that says
   something is always kept - the content is the authority when it speaks. */
export function deriveSegmentRole(text,authoredRole=''){
  const authored=String(authoredRole||'').trim().toLowerCase();
  if(authored&&!UNSPECIFIC_ROLES.has(authored))return authored;

  const value=String(text||'').trim();
  if(!value)return authored||'marker';
  /* Only the opening of a part is diagnostic: parts often trail a whole
     explanatory clause after the thing they name. */
  const head=value.slice(0,40);
  for(const [role,test] of ROLE_RULES){
    if(test.test(head))return role;
  }
  return authored||'marker';
}

/* ----------------------------------------------------------- archetypes --- */

/* The visual archetypes of the design system, §6. `general` is the honest
   answer when a concept does not clearly belong to one - it is not a failure,
   it means the lesson leads with its pattern and examples. */
export const ARCHETYPES=[
  'temporal_aspect',
  'word_order',
  'transformation',
  'contrast_choice',
  'semantic_scale',
  'role_flow',
  'logic_relation',
  'classification_selection',
  'result_chain',
  'pragmatic_particle',
  'general',
];

/* Tested in order. A concept can look like several things; the earlier entries
   are the ones whose visual answers the learner's question most directly. */
const ARCHETYPE_RULES=[
  // §6.6 role/participant flow - the Chinese disposal and passive frames, and
  // English passive/causative.
  ['role_flow',/把|被|使役|causative|passive|bị động|participant/iu],
  ['role_flow',/\b(agent|patient)\b/i],

  // §6.9 result and direction chains - central to Chinese complements.
  ['result_chain',/补语|complement|resultative|directional|potential complement/iu],

  // §6.1 temporal / aspect.
  ['temporal_aspect',/\b(tense|aspect|perfect|continuous|progressive|future|past|present)\b/i],
  ['temporal_aspect',/(了|过|着|正在|时态|体貌)/u],

  // §6.8 classification / selection.
  ['classification_selection',/\b(article|articles|countable|uncountable|quantifier|determiner|pronoun)\b/i],
  ['classification_selection',/(量词|classifier|measure word|数量)/iu],

  // §6.5 semantic scale - modality and degree.
  ['semantic_scale',/\b(modal|must|should|might|may|obligation|probability|degree|comparative|superlative)\b/i],
  ['semantic_scale',/(必须|应该|可以|可能|一定|程度|比较级)/u],

  // §6.7 logic relation.
  ['logic_relation',/\b(conditional|because|although|however|unless|purpose|reason|result clause)\b/i],
  ['logic_relation',/(因为|所以|虽然|但是|如果|就|条件|转折)/u],

  // §6.3 transformation.
  ['transformation',/\b(reported speech|indirect speech|transform|convert|question formation|inversion)\b/i],
  ['transformation',/(变换|转换|改写)/u],

  // §6.4 contrast / choice.
  ['contrast_choice',/\s(vs\.?|versus)\s/i],
  ['contrast_choice',/\b(difference between|choose between|confusion)\b/i],
  ['contrast_choice',/(辨析|区别|还是)/u],

  // §6.10 pragmatic particle / discourse function.
  ['pragmatic_particle',/\b(particle|discourse|politeness|tone|nuance|sentence-final)\b/i],
  ['pragmatic_particle',/(语气|吧|呢|啊|嘛)/u],

  // §6.2 word order - last, because many concepts mention order in passing.
  ['word_order',/\b(word order|order of|placement|position of|inversion|sentence structure)\b/i],
  ['word_order',/(语序|词序|位置)/u],
];

/* The signal is the concept's own identity and the words of its pattern - not
   the generated prose around them, which is close to identical across the
   curriculum and would classify everything the same way. */
function archetypeSignal(concept={}){
  const model=concept.learning_model||{};
  const blocks=Array.isArray(model.blocks)?model.blocks:[];
  const patternText=blocks
    .filter(block=>block?.stage==='pattern')
    .flatMap(block=>{
      const payload=block.payload||{};
      const parts=[...(payload.parts||[]),...(payload.segments||[])];
      return parts.map(part=>typeof part?.text==='string'?part.text:'');
    })
    .join(' ');
  return [
    String(concept.id||'').replace(/[-_]+/g,' '),
    String(concept.title||''),
    String(concept.kind||''),
    patternText,
  ].join(' • ');
}

export function classifyArchetype(concept={}){
  const signal=archetypeSignal(concept);
  for(const [archetype,test] of ARCHETYPE_RULES){
    if(test.test(signal))return archetype;
  }
  return 'general';
}

/* Which visual best answers "how does this grammar work?" for an archetype
   (§23 component mapping). The renderer uses this to decide what to lead with
   among the blocks a concept actually has - it never conjures a block that the
   content does not carry. */
export const ARCHETYPE_PRIMARY_VISUAL={
  temporal_aspect:'timeline',
  word_order:'word_order_rail',
  transformation:'transformation_pair',
  contrast_choice:'contrast_matrix',
  semantic_scale:'semantic_scale',
  role_flow:'role_flow',
  logic_relation:'logic_flow',
  classification_selection:'classifier_map',
  result_chain:'complement_chain',
  pragmatic_particle:'scenario_card',
  general:'formula_block',
};

/* The block type that carries each visual, so an audit can say whether a
   concept has the block its archetype calls for. */
export const VISUAL_BLOCK_TYPE={
  timeline:'timeline',
  word_order_rail:'word_order',
  transformation_pair:'transformation',
  contrast_matrix:'contrast',
  semantic_scale:'semantic_sentence',
  role_flow:'word_order',
  logic_flow:'semantic_sentence',
  classifier_map:'word_order',
  complement_chain:'word_order',
  scenario_card:'scene',
  formula_block:'formula',
};

const ARCHETYPE_LABELS={
  en:{
    temporal_aspect:'Time and aspect',word_order:'Word order',transformation:'Transformation',
    contrast_choice:'Contrast',semantic_scale:'Degree and modality',role_flow:'Who does what',
    logic_relation:'Logic relation',classification_selection:'Choosing the right form',
    result_chain:'Verb and result',pragmatic_particle:'Tone and nuance',general:'Pattern',
  },
  vi:{
    temporal_aspect:'Thời gian và thể',word_order:'Trật tự từ',transformation:'Biến đổi câu',
    contrast_choice:'Phân biệt',semantic_scale:'Mức độ và tình thái',role_flow:'Ai làm gì với ai',
    logic_relation:'Quan hệ logic',classification_selection:'Chọn đúng dạng',
    result_chain:'Động từ và kết quả',pragmatic_particle:'Sắc thái',general:'Cấu trúc',
  },
  zh:{
    temporal_aspect:'时间与体',word_order:'语序',transformation:'句式变换',
    contrast_choice:'辨析',semantic_scale:'程度与情态',role_flow:'谁对谁做什么',
    logic_relation:'逻辑关系',classification_selection:'选择正确形式',
    result_chain:'动词与结果',pragmatic_particle:'语气',general:'结构',
  },
};

export function archetypeLabel(archetype,locale='en'){
  const table=ARCHETYPE_LABELS[locale]||ARCHETYPE_LABELS.en;
  return table[archetype]||table.general;
}

/* ---------------------------------------------------------- composition --- */

/* Which question a block answers, per §16 "each visible block should answer one
   question". The renderer emits blocks in the order the content was authored;
   the lesson is composed from these slots instead, so every concept reads in
   the order §19 lays out rather than in the order its JSON happened to list. */
export const BLOCK_SLOT={
  formula:'model',
  word_order:'model',
  timeline:'model',
  semantic_sentence:'model',
  transformation:'model',
  sentence_builder:'practice',
  scene:'examples',
  contrast:'compare',
  common_mistake:'mistake',
  exception:'mistake',
  micro_practice:'practice',
  personal_practice:'practice',
  recall:'recall',
  memory_hook:'recall',
  skill_transfer:'transfer',
};

/* §19 desktop and §20 mobile agree on the sequence; they differ only in that
   the desktop pairs "when to use" with "examples" side by side. */
export const LESSON_SLOT_ORDER=[
  'model',
  'use',
  'examples',
  'compare',
  'mistake',
  'practice',
  'recall',
  'transfer',
  'extra',
];

/* §4 Level 2: one dominant teaching object that answers "how does this grammar
   work?". The archetype names which visual would answer it best; if the concept
   carries that block it leads, and otherwise the pattern does. Nothing is
   conjured - a concept with no timeline simply leads with its pattern, and the
   audit counts it as needing one. */
export function primaryModelType(concept={}){
  const blocks=Array.isArray(concept?.learning_model?.blocks)?concept.learning_model.blocks:[];
  const present=new Set(blocks.map(block=>block?.type));
  const wanted=VISUAL_BLOCK_TYPE[ARCHETYPE_PRIMARY_VISUAL[classifyArchetype(concept)]];
  if(wanted&&present.has(wanted))return wanted;
  const pattern=blocks.find(block=>block?.stage==='pattern');
  if(pattern?.type)return pattern.type;
  const model=blocks.find(block=>BLOCK_SLOT[block?.type]==='model');
  return model?.type||'';
}

export function composeLesson(concept={}){
  const archetype=classifyArchetype(concept);
  return {
    archetype,
    primaryVisual:ARCHETYPE_PRIMARY_VISUAL[archetype],
    primaryType:primaryModelType(concept),
    order:LESSON_SLOT_ORDER,
  };
}
