/* The names of the Grammar Library's categories, one table per LEARNING language (human review 2026-10-09, GLB-4).

   Where the categories come from. A category is a point's `function` (`fn.<snake_case>`, contract §0). The content
   package (grammar_lab/functions/functions.yaml, authored by the Grammar Lab pipeline's agent sessions) holds ONE
   registry of "communicative functions shared by every target language", each with a vi / en / zh-Hans title written
   once and read for English and Chinese alike. A name that is right for English is often wrong for Chinese ("Động
   từ đi với -ing hoặc to V" over 兼语句), so the Library does not show those titles when this table has a name:

   - the table is keyed by learning language, then category id, then the language the name is written in;
   - a name is written for that learning language's own grammar, in the terms its teachers use in that language
     (Vietnamese: câu chữ 把, bổ ngữ xu hướng, trợ từ động thái; Chinese: 把字句, 补语, 能愿动词), never translated from
     the English name; the original-language term is added in brackets where it helps;
   - an id that has no points in a learning language is not in its table (a Chinese learner never sees "Articles"),
     and the catalogue only ever lists categories that have points, so it is not shown either;
   - a support language is added by adding its key to every row; scripts/test_orena_screen_grammar.mjs fails on a row
     that lacks any shipped language, and on an id the corpus does not use for that learning language.

   Order of fallback for the name shown: the interface language's name -> the English name -> the title the catalogue
   API sends -> the id's last words (model.js). The table lists only what the approved corpus uses today
   (scripts/fixtures/grammar/category_usage.json); a new category falls back to the API title until it is added. */

export const SUPPORT_LANGUAGES = Object.freeze(['vi', 'en', 'zh']);

const name = (vi, en, zh) => Object.freeze({ vi, en, zh });

const ENGLISH = {
  'fn.verb_patterns': name('Động từ đi với V-ing hoặc to V', 'Verb patterns (-ing and to + verb)', '动词后接 -ing 或不定式'),
  'fn.possibility': name('Động từ khuyết thiếu: khả năng', 'Modals: ability and possibility', '情态动词：能力与可能'),
  'fn.information_structure': name('Nhấn mạnh và cấu trúc thông tin', 'Emphasis and information structure', '强调与信息结构'),
  'fn.future_plans': name('Thì tương lai', 'Future forms', '将来时'),
  'fn.reference': name('Mạo từ', 'Articles', '冠词'),
  'fn.completed_past': name('Quá khứ đơn và quá khứ hoàn thành', 'Past simple and past perfect', '一般过去时与过去完成时'),
  'fn.sentence_basics': name('Cấu trúc câu', 'Sentence structure', '句子结构'),
  'fn.quantity': name('Lượng từ và số nhiều', 'Quantifiers and plurals', '数量词与复数'),
  'fn.questions': name('Câu hỏi', 'Questions', '疑问句'),
  'fn.condition_real': name('Câu điều kiện', 'Conditionals', '条件句'),
  'fn.relative': name('Mệnh đề quan hệ', 'Relative clauses', '关系从句'),
  'fn.pronoun_reference': name('Đại từ', 'Pronouns', '代词'),
  'fn.obligation_advice': name('Động từ khuyết thiếu: nghĩa vụ, lời khuyên', 'Modals: obligation and advice', '情态动词：义务与建议'),
  'fn.reporting': name('Câu tường thuật', 'Reported speech', '间接引语'),
  'fn.linking': name('Từ nối và liên kết ý', 'Linking words', '连接词与衔接'),
  'fn.degree': name('Trạng từ và mức độ', 'Adverbs and degree', '副词与程度'),
  'fn.comparison': name('So sánh', 'Comparison', '比较'),
  'fn.voice_causative': name('Câu bị động và thể sai khiến', 'Passive and causative', '被动语态与使役'),
  'fn.past_experience': name('Hiện tại hoàn thành', 'Present perfect', '现在完成时'),
  'fn.habit_fact': name('Hiện tại đơn', 'Present simple', '一般现在时'),
  'fn.aspect_viewpoint': name('Thể (aspect) nâng cao', 'Aspect, advanced', '体（高阶）'),
  'fn.hypothetical_counterfactual': name('Giả định và điều kiện không có thật', 'Hypothetical and unreal conditions', '虚拟与非真实条件'),
  'fn.possession': name('Sở hữu', 'Possession', '所有格与所属'),
  'fn.identity_state': name('Động từ to be và động từ chỉ trạng thái', 'Be and stative verbs', 'be 动词与状态动词'),
  'fn.past_ongoing': name('Quá khứ tiếp diễn', 'Past continuous', '过去进行时'),
  'fn.register_style': name('Văn phong và ngữ vực', 'Register and style', '语体与风格'),
  'fn.negation': name('Phủ định', 'Negation', '否定'),
  'fn.contrast': name('Đối lập và nhượng bộ', 'Contrast and concession', '转折与让步'),
  'fn.existence': name('Cấu trúc tồn tại (there is / there are)', 'Existential there', '存在句 there be'),
  'fn.place_time': name('Giới từ chỉ nơi chốn và thời gian', 'Prepositions of place and time', '地点与时间介词'),
  'fn.sequence': name('Mệnh đề chỉ thời gian', 'Time clauses', '时间状语从句'),
  'fn.time_expression': name('Cách nói thời gian', 'Time expressions', '时间表达'),
  'fn.reason_result': name('Nguyên nhân và kết quả', 'Cause and result', '原因与结果'),
  'fn.exclusion': name('Giới hạn và loại trừ', 'Limitation and exclusion', '限定与排除'),
  'fn.instructions': name('Câu mệnh lệnh', 'Imperatives', '祈使句'),
  'fn.indefinite_reference': name('Đại từ bất định', 'Indefinite pronouns', '不定代词'),
  'fn.ongoing_now': name('Hiện tại tiếp diễn', 'Present continuous', '现在进行时'),
};

const CHINESE = {
  'fn.linking': name('Từ nối và câu phức', 'Connectives and complex sentences', '关联词语与复句'),
  'fn.sentence_basics': name('Câu cơ bản', 'Basic sentence patterns', '基本句型'),
  'fn.negation': name('Phủ định', 'Negation', '否定表达'),
  'fn.questions': name('Câu hỏi', 'Questions', '疑问句'),
  'fn.time_expression': name('Biểu đạt thời gian', 'Time expressions', '时间表达'),
  'fn.location': name('Phương vị từ và vị trí', 'Location and direction words', '方位与处所'),
  'fn.quantity': name('Số từ và lượng từ', 'Numbers and measure words', '数词与量词'),
  'fn.degree': name('Mức độ và phương thức', 'Degree and manner', '程度与方式'),
  'fn.object_disposal': name('Câu chữ 把 (把字句)', 'The 把 construction (把字句)', '把字句'),
  'fn.contrast': name('Quan hệ chuyển ngoặt (转折)', 'Contrast (转折)', '转折关系'),
  'fn.reason_result': name('Quan hệ nhân quả', 'Cause and result', '因果关系'),
  'fn.possibility': name('Động từ năng nguyện và khả năng', 'Modal verbs and possibility', '能愿动词与可能'),
  'fn.pronoun_reference': name('Đại từ', 'Pronouns', '代词'),
  'fn.sequence': name('Trình tự và nối tiếp', 'Sequence', '承接与先后'),
  'fn.comparison': name('Câu so sánh', 'Comparison', '比较句'),
  'fn.condition_real': name('Điều kiện và giả thiết', 'Conditions', '条件关系'),
  'fn.obligation_advice': name('Lời khuyên và nghĩa vụ', 'Advice and obligation', '建议与义务'),
  'fn.action_result': name('Bổ ngữ (kết quả, xu hướng, trạng thái)', 'Complements (result, direction, degree)', '补语（结果、趋向、状态）'),
  'fn.ongoing_now': name('Tiến hành và kéo dài (在, 着)', 'Progressive and durative (在, 着)', '进行与持续（在、着）'),
  'fn.relative': name('Định ngữ (定语)', 'Attributives (定语)', '定语'),
  'fn.future_plans': name('Ý định và tương lai', 'Intentions and the future', '意愿与将来'),
  'fn.exclusion': name('Loại trừ và phạm vi', 'Exclusion and scope', '排除与范围'),
  'fn.register_style': name('Phong cách ngôn ngữ (语体)', 'Register and style (语体)', '语体与风格'),
  'fn.duration_frequency': name('Bổ ngữ thời lượng và động lượng', 'Duration and frequency complements', '时量与动量'),
  'fn.verb_patterns': name('Cấu trúc động từ (câu kiêm ngữ…)', 'Verb patterns (pivotal sentences…)', '动词结构（兼语句等）'),
  'fn.voice_causative': name('Câu chữ 被 và câu sai khiến', 'The 被 passive and causatives', '被字句与使役句'),
  'fn.information_structure': name('Chủ đề và nhấn mạnh', 'Topic and emphasis', '话题与强调'),
  'fn.reference': name('Chỉ thị (之, 者…)', 'Reference (之, 者…)', '指代（之、者等）'),
  'fn.completed_past': name('Hoàn thành (了)', 'Completion (了)', '完成（了）'),
  'fn.identity_state': name('Câu chữ 是 và vị ngữ tính từ', '是 sentences and adjective predicates', '“是”字句与形容词谓语句'),
  'fn.instructions': name('Câu cầu khiến', 'Imperatives and requests', '祈使句'),
  'fn.hypothetical_counterfactual': name('Câu giả thiết', 'Hypotheticals', '假设关系'),
  'fn.existence': name('Câu tồn hiện và câu chữ 有', 'Existence (存现句, 有)', '存现句与“有”字句'),
  'fn.aspect_viewpoint': name('Trợ từ động thái 了/过/着', 'Aspect particles 了 / 过 / 着', '动态助词“了/过/着”'),
  'fn.reporting': name('Trích dẫn và thuật lại', 'Quoting and reporting', '引述与转述'),
  'fn.possession': name('Sở hữu (的)', 'Possession (的)', '领属（的）'),
  'fn.past_experience': name('Trải nghiệm (过)', 'Experience (过)', '经历（过）'),
  'fn.separable_verbs': name('Động từ ly hợp (离合词)', 'Separable verbs (离合词)', '离合词'),
};

export const CATEGORY_NAMES = Object.freeze({ en: Object.freeze(ENGLISH), zh: Object.freeze(CHINESE) });

/* The name of category `id` for a learner of `target`, written in the first of `languages` that has one; '' when the
   table has none (the caller falls back to the catalogue's own title). */
export function categoryName(target, id, languages = []) {
  const row = CATEGORY_NAMES[target]?.[id];
  if (!row) return '';
  for (const language of [...languages, 'en']) if (language && row[language]) return row[language];
  return '';
}
