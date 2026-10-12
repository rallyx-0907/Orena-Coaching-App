/* The shared VocabularyCard's own words (kit/vocabulary-card.js, D-17W). Section titles, the card's
   controls and the part-of-speech labels are chrome ('interface'); the content inside the sections
   is the entry's own (learning language) or its support-language layer, never copy from here.
   Rule 50: a section title is one or two words; nothing explains what a section is for. */
import { defineCopy } from './index.js';

const KEYS = [
  'playWord', 'saveWord', 'unsaveWord', 'meaningUnavailable',
  'sectionMeaning', 'sectionExamples', 'sectionCollocations', 'sectionSynonyms', 'sectionAntonyms',
  'sectionWordFamily', 'sectionRelated', 'sectionMemoryTip', 'sectionClassifiers', 'sectionCharacters',
  'sectionUsage', 'sectionCommonMistake', 'sectionEtymology', 'sectionMetIn',
  'hanVietLabel', 'radicalLabel', 'regionUk', 'regionUs', 'strokeCount',
  'posNoun', 'posVerb', 'posAdjective', 'posAdverb', 'posPronoun', 'posDeterminer', 'posPreposition',
  'posConjunction', 'posNumeral', 'posParticle', 'posAuxiliary', 'posInterjection', 'posClassifier',
  'posMeasureWord', 'posPhrase', 'posIdiom', 'posProperNoun', 'posOther', 'posJoin',
];

export const t = defineCopy('vocabularyCard', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    playWord: 'Play pronunciation', saveWord: 'Save word', unsaveWord: 'Remove from saved words',
    meaningUnavailable: 'No meaning yet',
    sectionMeaning: 'Meaning', sectionExamples: 'Examples', sectionCollocations: 'Collocations',
    sectionSynonyms: 'Synonyms', sectionAntonyms: 'Opposites', sectionWordFamily: 'Word family',
    sectionRelated: 'Related words', sectionMemoryTip: 'Memory tip', sectionClassifiers: 'Measure words',
    sectionCharacters: 'Characters', sectionUsage: 'Usage', sectionCommonMistake: 'Common mistake',
    sectionEtymology: 'Origin', sectionMetIn: 'Where you met it',
    hanVietLabel: 'Sino-Vietnamese', radicalLabel: 'Radical', regionUk: 'UK', regionUs: 'US',
    strokeCount_one: '{n} stroke', strokeCount_other: '{n} strokes',
    posNoun: 'Noun', posVerb: 'Verb', posAdjective: 'Adjective', posAdverb: 'Adverb', posPronoun: 'Pronoun',
    posDeterminer: 'Determiner', posPreposition: 'Preposition', posConjunction: 'Conjunction',
    posNumeral: 'Numeral', posParticle: 'Particle', posAuxiliary: 'Auxiliary', posInterjection: 'Interjection',
    posClassifier: 'Classifier', posMeasureWord: 'Measure word', posPhrase: 'Phrase', posIdiom: 'Idiom',
    posProperNoun: 'Proper noun', posOther: 'Other', posJoin: ' / ',
  },
  vi: {
    playWord: 'Phát âm', saveWord: 'Lưu từ', unsaveWord: 'Bỏ khỏi từ đã lưu',
    meaningUnavailable: 'Chưa có nghĩa',
    sectionMeaning: 'Nghĩa', sectionExamples: 'Ví dụ', sectionCollocations: 'Kết hợp thường gặp',
    sectionSynonyms: 'Đồng nghĩa', sectionAntonyms: 'Trái nghĩa', sectionWordFamily: 'Họ từ',
    sectionRelated: 'Từ liên quan', sectionMemoryTip: 'Mẹo nhớ', sectionClassifiers: 'Lượng từ',
    sectionCharacters: 'Chữ Hán', sectionUsage: 'Cách dùng', sectionCommonMistake: 'Lỗi thường gặp',
    sectionEtymology: 'Nguồn gốc', sectionMetIn: 'Nơi bạn gặp từ này',
    hanVietLabel: 'Hán Việt', radicalLabel: 'Bộ thủ', regionUk: 'Anh', regionUs: 'Mỹ',
    strokeCount_other: '{n} nét',
    posNoun: 'Danh từ', posVerb: 'Động từ', posAdjective: 'Tính từ', posAdverb: 'Trạng từ', posPronoun: 'Đại từ',
    posDeterminer: 'Hạn định từ', posPreposition: 'Giới từ', posConjunction: 'Liên từ',
    posNumeral: 'Số từ', posParticle: 'Trợ từ', posAuxiliary: 'Trợ động từ', posInterjection: 'Thán từ',
    posClassifier: 'Lượng từ', posMeasureWord: 'Lượng từ', posPhrase: 'Cụm từ', posIdiom: 'Thành ngữ',
    posProperNoun: 'Danh từ riêng', posOther: 'Khác', posJoin: ' / ',
  },
  zh: {
    playWord: '播放发音', saveWord: '收藏单词', unsaveWord: '从收藏中移除',
    meaningUnavailable: '暂无释义',
    sectionMeaning: '释义', sectionExamples: '例句', sectionCollocations: '常见搭配',
    sectionSynonyms: '近义词', sectionAntonyms: '反义词', sectionWordFamily: '同族词',
    sectionRelated: '相关词', sectionMemoryTip: '记忆技巧', sectionClassifiers: '量词',
    sectionCharacters: '汉字', sectionUsage: '用法', sectionCommonMistake: '常见错误',
    sectionEtymology: '词源', sectionMetIn: '你遇到它的地方',
    hanVietLabel: '汉越音', radicalLabel: '部首', regionUk: '英', regionUs: '美',
    strokeCount_other: '{n} 画',
    posNoun: '名词', posVerb: '动词', posAdjective: '形容词', posAdverb: '副词', posPronoun: '代词',
    posDeterminer: '限定词', posPreposition: '介词', posConjunction: '连词',
    posNumeral: '数词', posParticle: '助词', posAuxiliary: '助动词', posInterjection: '叹词',
    posClassifier: '量词', posMeasureWord: '量词', posPhrase: '短语', posIdiom: '成语',
    posProperNoun: '专有名词', posOther: '其他', posJoin: '／',
  },
});
