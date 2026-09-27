/* Practice Hub / Skill Hub's own words. Every mode label reuses copy/shell.js's own route titles
   (`shellCopy`) - this table only holds what shellCopy does not already have: the six skill
   category headings and the hub's own chrome (rule: don't duplicate a translation table). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'skillSpeak', 'skillWrite', 'skillListen', 'skillVocabulary', 'skillGrammar', 'skillReading',
  'recommended', 'start', 'continueCta',
  'due', 'emptySkill',
];

export const t = defineCopy('practice', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    skillSpeak: 'Speak', skillWrite: 'Write', skillListen: 'Listen', skillVocabulary: 'Vocabulary',
    skillGrammar: 'Grammar', skillReading: 'Reading',
    recommended: 'Recommended', start: 'Start', continueCta: 'Continue',
    due_one: '{n} due', due_other: '{n} due',
    emptySkill: 'No modes here yet.',
  },
  vi: {
    skillSpeak: 'Nói', skillWrite: 'Viết', skillListen: 'Nghe', skillVocabulary: 'Từ vựng',
    skillGrammar: 'Ngữ pháp', skillReading: 'Đọc',
    recommended: 'Đề xuất', start: 'Bắt đầu', continueCta: 'Tiếp tục',
    due_other: '{n} từ cần ôn',
    emptySkill: 'Chưa có bài luyện nào ở đây.',
  },
  zh: {
    skillSpeak: '口语', skillWrite: '写作', skillListen: '听力', skillVocabulary: '词汇',
    skillGrammar: '语法', skillReading: '阅读',
    recommended: '推荐', start: '开始', continueCta: '继续',
    due_other: '{n} 个待复习',
    emptySkill: '这里还没有练习模式。',
  },
});
