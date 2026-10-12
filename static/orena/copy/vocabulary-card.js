/* The shared VocabularyCard's own words (kit/vocabulary-card.js, D-179). Section titles and the card's
   controls are chrome ('interface'), named as the human's flashcard reference names them ("Nghĩa",
   "Họ từ", "Đồng / trái nghĩa", "Xem ví dụ →", "← Mặt trước", "Ví dụ & cách dùng", "Kết hợp thường gặp",
   "Mẹo nhớ", "Bộ thủ", "Lượng từ", "Từ liên quan", "Hán Việt"). The content inside the sections is the
   entry's own or its support-language layer, never copy from here. The part-of-speech labels double as
   the part of speech's name in the word's own language (`posNative`, read from the en/zh pack). */
import { defineCopy } from './index.js';

const KEYS = [
  'playWord', 'saveWord', 'unsaveWord', 'meaningUnavailable', 'seeExamples', 'backToFront',
  'sectionMeaning', 'sectionWordFamily', 'sectionSynAnt', 'sectionExamplesUsage', 'sectionStructure',
  'sectionCollocations', 'sectionMemoryTip', 'sectionRadical', 'sectionMeasureWord', 'sectionRelated',
  'sectionCommonMistake', 'sectionEtymology',
  'hanVietLabel', 'regionUk', 'regionUs', 'strokeCount',
  'posNoun', 'posVerb', 'posAdjective', 'posAdverb', 'posPronoun', 'posDeterminer', 'posPreposition',
  'posConjunction', 'posNumeral', 'posParticle', 'posAuxiliary', 'posInterjection', 'posClassifier',
  'posMeasureWord', 'posPhrase', 'posIdiom', 'posProperNoun', 'posOther', 'posJoin',
];

export const t = defineCopy('vocabularyCard', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    playWord: 'Play pronunciation', saveWord: 'Save word', unsaveWord: 'Remove from saved words',
    meaningUnavailable: 'No meaning yet', seeExamples: 'See examples →', backToFront: '← Front',
    sectionMeaning: 'Meaning', sectionWordFamily: 'Word family', sectionSynAnt: 'Synonyms / antonyms',
    sectionExamplesUsage: 'Examples & usage', sectionStructure: 'Structure', sectionCollocations: 'Common collocations',
    sectionMemoryTip: 'Memory tip', sectionRadical: 'Radical', sectionMeasureWord: 'Measure word',
    sectionRelated: 'Related words', sectionCommonMistake: 'Common mistake', sectionEtymology: 'Origin',
    hanVietLabel: 'Sino-Vietnamese', regionUk: 'UK', regionUs: 'US',
    strokeCount_one: '{n} stroke', strokeCount_other: '{n} strokes',
    posNoun: 'Noun', posVerb: 'Verb', posAdjective: 'Adjective', posAdverb: 'Adverb', posPronoun: 'Pronoun',
    posDeterminer: 'Determiner', posPreposition: 'Preposition', posConjunction: 'Conjunction',
    posNumeral: 'Numeral', posParticle: 'Particle', posAuxiliary: 'Auxiliary', posInterjection: 'Interjection',
    posClassifier: 'Classifier', posMeasureWord: 'Measure word', posPhrase: 'Phrase', posIdiom: 'Idiom',
    posProperNoun: 'Proper noun', posOther: 'Other', posJoin: ' / ',
  },
  vi: {
    playWord: 'Phát âm', saveWord: 'Lưu từ', unsaveWord: 'Bỏ khỏi từ đã lưu',
    meaningUnavailable: 'Chưa có nghĩa', seeExamples: 'Xem ví dụ →', backToFront: '← Mặt trước',
    sectionMeaning: 'Nghĩa', sectionWordFamily: 'Họ từ', sectionSynAnt: 'Đồng / trái nghĩa',
    sectionExamplesUsage: 'Ví dụ & cách dùng', sectionStructure: 'Cấu trúc', sectionCollocations: 'Kết hợp thường gặp',
    sectionMemoryTip: 'Mẹo nhớ', sectionRadical: 'Bộ thủ', sectionMeasureWord: 'Lượng từ',
    sectionRelated: 'Từ liên quan', sectionCommonMistake: 'Lỗi thường gặp', sectionEtymology: 'Nguồn gốc',
    hanVietLabel: 'Hán Việt', regionUk: 'Anh', regionUs: 'Mỹ',
    strokeCount_other: '{n} nét',
    posNoun: 'Danh từ', posVerb: 'Động từ', posAdjective: 'Tính từ', posAdverb: 'Trạng từ', posPronoun: 'Đại từ',
    posDeterminer: 'Hạn định từ', posPreposition: 'Giới từ', posConjunction: 'Liên từ',
    posNumeral: 'Số từ', posParticle: 'Trợ từ', posAuxiliary: 'Trợ động từ', posInterjection: 'Thán từ',
    posClassifier: 'Lượng từ', posMeasureWord: 'Lượng từ', posPhrase: 'Cụm từ', posIdiom: 'Thành ngữ',
    posProperNoun: 'Danh từ riêng', posOther: 'Khác', posJoin: ' / ',
  },
  zh: {
    playWord: '播放发音', saveWord: '收藏单词', unsaveWord: '从收藏中移除',
    meaningUnavailable: '暂无释义', seeExamples: '查看例句 →', backToFront: '← 正面',
    sectionMeaning: '释义', sectionWordFamily: '词族', sectionSynAnt: '近义词 / 反义词',
    sectionExamplesUsage: '例句与用法', sectionStructure: '结构', sectionCollocations: '常见搭配',
    sectionMemoryTip: '记忆技巧', sectionRadical: '部首', sectionMeasureWord: '量词',
    sectionRelated: '相关词', sectionCommonMistake: '常见错误', sectionEtymology: '词源',
    hanVietLabel: '汉越音', regionUk: '英', regionUs: '美',
    strokeCount_other: '{n} 画',
    posNoun: '名词', posVerb: '动词', posAdjective: '形容词', posAdverb: '副词', posPronoun: '代词',
    posDeterminer: '限定词', posPreposition: '介词', posConjunction: '连词',
    posNumeral: '数词', posParticle: '助词', posAuxiliary: '助动词', posInterjection: '叹词',
    posClassifier: '量词', posMeasureWord: '量词', posPhrase: '短语', posIdiom: '成语',
    posProperNoun: '专有名词', posOther: '其他', posJoin: '／',
  },
});
