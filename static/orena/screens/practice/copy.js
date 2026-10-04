/* Practice Hub / Skill Hub's own words. Every mode label reuses copy/shell.js's own route titles
   (`shellCopy`) - this table only holds what shellCopy does not already have: the six skill
   category headings and the hub's own chrome (rule: don't duplicate a translation table). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'skillSpeak', 'skillWrite', 'skillListen', 'skillVocabulary', 'skillGrammar', 'skillReading',
  'recommended', 'start', 'continueCta',
  'due', 'emptySkill',
  'continueTitle', 'recentTitle', 'nothingPending', 'draftReason', 'conversationReason',
  'readingReason', 'recentLine', 'recentReason', 'recentExplanation', 'noRecent',
];

export const t = defineCopy('practice', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    continueTitle: 'Continue learning', recentTitle: 'Recently opened',
    nothingPending: 'No unfinished work to resume. Choose a practice below.',
    draftReason: 'Draft not submitted · Continue writing',
    conversationReason: 'Conversation not ended · Return to the last exchange',
    readingReason: 'Reading paused at {n}% · Return to your saved place',
    recentLine: 'Last opened at line {n} of {total} · Open again',
    recentReason: 'Previously opened · Open again',
    recentExplanation: 'Recent visits, not assignments or a measure of mastery.',
    noRecent: 'No available recent items.',
    skillSpeak: 'Speak', skillWrite: 'Write', skillListen: 'Listen', skillVocabulary: 'Vocabulary',
    skillGrammar: 'Grammar', skillReading: 'Reading',
    recommended: 'Recommended', start: 'Start', continueCta: 'Continue',
    due_one: '{n} due', due_other: '{n} due',
    emptySkill: 'No modes here yet.',
  },
  vi: {
    continueTitle: 'Học tiếp', recentTitle: 'Bài mở gần đây',
    nothingPending: 'Không có bài đang dở cần tiếp tục. Chọn bài luyện bên dưới.',
    draftReason: 'Bản nháp chưa gửi · Tiếp tục viết',
    conversationReason: 'Hội thoại chưa kết thúc · Trở lại lượt trao đổi cuối',
    readingReason: 'Đang đọc ở {n}% · Trở lại vị trí đã lưu',
    recentLine: 'Lần trước mở ở câu {n}/{total} · Mở lại',
    recentReason: 'Đã mở trước đây · Mở lại',
    recentExplanation: 'Lịch sử mở bài, không phải bài được giao hay đánh giá mức độ thành thạo.',
    noRecent: 'Chưa có bài gần đây có thể mở.',
    skillSpeak: 'Nói', skillWrite: 'Viết', skillListen: 'Nghe', skillVocabulary: 'Từ vựng',
    skillGrammar: 'Ngữ pháp', skillReading: 'Đọc',
    recommended: 'Đề xuất', start: 'Bắt đầu', continueCta: 'Tiếp tục',
    due_other: '{n} từ cần ôn',
    emptySkill: 'Chưa có bài luyện nào ở đây.',
  },
  zh: {
    continueTitle: '继续学习', recentTitle: '最近打开',
    nothingPending: '暂无未完成的学习内容。请选择下面的练习。',
    draftReason: '草稿尚未提交 · 继续写作',
    conversationReason: '对话尚未结束 · 回到上次的交流',
    readingReason: '阅读停在 {n}% · 回到保存的位置',
    recentLine: '上次打开第 {n}/{total} 句 · 再次打开',
    recentReason: '之前打开过 · 再次打开',
    recentExplanation: '这里只是打开记录，并非学习任务或掌握程度评估。',
    noRecent: '暂无可打开的最近内容。',
    skillSpeak: '口语', skillWrite: '写作', skillListen: '听力', skillVocabulary: '词汇',
    skillGrammar: '语法', skillReading: '阅读',
    recommended: '推荐', start: '开始', continueCta: '继续',
    due_other: '{n} 个待复习',
    emptySkill: '这里还没有练习模式。',
  },
});
