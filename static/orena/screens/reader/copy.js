/* Reader's own words (design route `reader`, frame 14). Place titles, "Discussion", "Respond to
   content", "Reading Transfer", "Check understanding", "Ask Orena", "Close" and "Undo" already exist
   in copy/shell.js (shellCopy) and are reused, not redefined here.

   Rule 50 drops (recorded in the report): the frame's empty-notes how-to ("Tap a sentence ->
   'Add note' or 'Save highlight'") and the Summary panel's "the text stays in place; close this
   panel..." footer are not translated - the first tells the learner about controls the selection
   toolbar already shows, the second explains what a close button does; and the end-of-text note
   keeps only where the learner is, not the "optional: check your understanding, or..." sentence
   that restates the buttons right under it. */
import { defineCopy } from '../../copy/index.js';

const SUPPORT = ['posLegendHint', 'roleNounHelp', 'roleVerbHelp', 'roleModifierHelp', 'roleConnectorHelp', 'rolePronounHelp', 'roleNumberHelp'];
const KEYS = [
  'readingAppearance', 'aa', 'aaSmaller', 'aaLarger', 'aidsLabel', 'moreLabel',
  'themeDark', 'listen', 'listenPause', 'saveLabel', 'savedLabel', 'savedToast', 'removedToast', 'saveFailed',
  'translationAid', 'vocabLensAid', 'wordRolesAid', 'pinyinAid', 'pinyinNotApplicable',
  'notesLabel', 'summaryLabel', 'summaryNotPrepared',
  'roleNoun', 'roleVerb', 'roleModifier', 'roleConnector', 'rolePronoun', 'roleNumber', 'posLegendHint',
  'roleNounHelp', 'roleVerbHelp', 'roleModifierHelp', 'roleConnectorHelp', 'rolePronounHelp', 'roleNumberHelp',
  'yourNote', 'noteExpand', 'noteCollapse', 'editInSentence',
  'notesHighlights', 'noNotesYet', 'typeFactual', 'typeReflection', 'typeQuestion', 'typeHighlight',
  'selTranslate', 'selHighlight', 'selHighlighted', 'selNote',
  'chapters', 'markAsFinished', 'nextChapterCta', 'endNoteChapter', 'endNoteArticle', 'endNoteText',
  'translationUnavailable', 'listenStarted', 'listenStopped', 'listenUnavailable',
  'writeResponse', 'kindArticle', 'kindBook', 'kindText', 'modeActive', 'pageOf',
  'summaryGenerated', 'summaryLoading', 'summaryFailed', 'summaryStays', 'retry', 'translationFailed', 'translationLoading',
  'practiceTitle', 'minutes', 'endNotePractice',
];

export const t = defineCopy('reader', {
  layers: Object.fromEntries(KEYS.map((key) => [key, SUPPORT.includes(key) ? 'support' : 'interface'])),
  en: {
    readingAppearance: 'Reading appearance', aa: 'Aa', aaSmaller: 'Smaller text', aaLarger: 'Larger text', aidsLabel: 'Aids', moreLabel: 'More',
    themeDark: 'Dark theme', listen: 'Listen', listenPause: 'Pause read-aloud',
    saveLabel: 'Save', savedLabel: 'Saved ✓', savedToast: 'Saved', removedToast: 'Removed', saveFailed: 'Could not save right now',
    translationAid: '{lang} meaning', vocabLensAid: 'Vocab lens', wordRolesAid: 'Word roles', pinyinAid: 'Pinyin',
    pinyinNotApplicable: 'Pinyin · n/a for English',
    notesLabel: 'Notes · {n}', summaryLabel: 'Summary', summaryNotPrepared: 'Summary is not prepared for this text',
    roleNoun: 'noun', roleVerb: 'verb', roleModifier: 'modifier', roleConnector: 'connector', rolePronoun: 'pronoun', roleNumber: 'number',
    posLegendHint: '· tap a word for its role',
    roleNounHelp: 'names a thing, person or idea', roleVerbHelp: 'the action or state', roleModifierHelp: 'describes or qualifies',
    roleConnectorHelp: 'links clauses or ideas', rolePronounHelp: 'refers back to something', roleNumberHelp: 'quantity or order',
    yourNote: 'Your note · {when}', noteExpand: 'Expand note', noteCollapse: 'Collapse note', editInSentence: 'Edit in sentence',
    notesHighlights: 'Notes & highlights', noNotesYet: 'No notes yet. Tap a sentence → “Add note” or “Save highlight”.',
    typeFactual: 'Factual', typeReflection: 'Reflection', typeQuestion: 'Question', typeHighlight: 'Highlight',
    selTranslate: 'Translate', selHighlight: 'Highlight', selHighlighted: 'Highlighted', selNote: 'Note',
    chapters: 'Chapters', markAsFinished: 'Mark as finished', nextChapterCta: 'Next chapter →',
    endNoteChapter: 'End of chapter {n} · optional: check your understanding, or go on to the next chapter.', endNoteArticle: 'End of the article · optional: check your understanding, or mark as finished.', endNoteText: 'End of your text.',
    translationUnavailable: 'Translation is not available right now',
    listenStarted: 'Reading aloud from your position', listenStopped: 'Read-aloud paused',
    listenUnavailable: 'Read-aloud is not available on this device',
    writeResponse: 'Write a response', kindArticle: 'Article', kindBook: 'Book', kindText: 'Imported text', modeActive: 'Active Reading', pageOf: 'p. {n} of {total}',
    practiceTitle: 'Reading Practice', minutes: '{n} min', endNotePractice: 'End of text · {n} questions, then the next reading.',
    summaryGenerated: 'Generated on request', summaryLoading: 'Writing the summary…', summaryFailed: 'The summary could not be made right now.', summaryStays: 'The text stays in place; close this panel to keep reading.', retry: 'Retry', translationFailed: 'The translation could not be made right now.', translationLoading: 'Translating…',
  },
  vi: {
    readingAppearance: 'Giao diện đọc', aa: 'Aa', aaSmaller: 'Chữ nhỏ hơn', aaLarger: 'Chữ lớn hơn', aidsLabel: 'Hỗ trợ', moreLabel: 'Thêm',
    themeDark: 'Giao diện tối', listen: 'Nghe', listenPause: 'Tạm dừng đọc to',
    saveLabel: 'Lưu', savedLabel: 'Đã lưu ✓', savedToast: 'Đã lưu', removedToast: 'Đã xoá', saveFailed: 'Chưa lưu được lúc này',
    translationAid: 'Nghĩa {lang}', vocabLensAid: 'Lớp từ vựng', wordRolesAid: 'Vai trò từ', pinyinAid: 'Pinyin',
    pinyinNotApplicable: 'Pinyin · không dùng cho tiếng Anh',
    notesLabel: 'Ghi chú · {n}', summaryLabel: 'Tóm tắt', summaryNotPrepared: 'Chưa có bản tóm tắt cho văn bản này',
    roleNoun: 'danh từ', roleVerb: 'động từ', roleModifier: 'từ bổ nghĩa', roleConnector: 'từ nối', rolePronoun: 'đại từ', roleNumber: 'số từ',
    posLegendHint: '· chạm vào một từ để xem vai trò của nó',
    roleNounHelp: 'chỉ sự vật, con người hoặc ý tưởng', roleVerbHelp: 'chỉ hành động hoặc trạng thái', roleModifierHelp: 'miêu tả hoặc bổ nghĩa',
    roleConnectorHelp: 'nối các mệnh đề hoặc ý', rolePronounHelp: 'thay cho một điều đã nhắc tới', roleNumberHelp: 'chỉ số lượng hoặc thứ tự',
    yourNote: 'Ghi chú của bạn · {when}', noteExpand: 'Mở rộng ghi chú', noteCollapse: 'Thu gọn ghi chú', editInSentence: 'Sửa trong câu',
    notesHighlights: 'Ghi chú & tô sáng', noNotesYet: 'Chưa có ghi chú nào. Chạm vào một câu → “Thêm ghi chú” hoặc “Lưu tô sáng”.',
    typeFactual: 'Sự kiện', typeReflection: 'Suy ngẫm', typeQuestion: 'Câu hỏi', typeHighlight: 'Tô sáng',
    selTranslate: 'Dịch', selHighlight: 'Tô sáng', selHighlighted: 'Đã tô sáng', selNote: 'Ghi chú',
    chapters: 'Chương', markAsFinished: 'Đánh dấu đã đọc xong', nextChapterCta: 'Chương tiếp theo →',
    endNoteChapter: 'Hết chương {n} · không bắt buộc: kiểm tra mức hiểu, hoặc sang chương tiếp theo.', endNoteArticle: 'Hết bài đọc · không bắt buộc: kiểm tra mức hiểu, hoặc đánh dấu đã đọc xong.', endNoteText: 'Hết văn bản của bạn.',
    translationUnavailable: 'Chưa dịch được lúc này',
    listenStarted: 'Đang đọc to từ vị trí của bạn', listenStopped: 'Đã tạm dừng đọc to',
    listenUnavailable: 'Thiết bị này không hỗ trợ đọc to',
    writeResponse: 'Viết phản hồi', kindArticle: 'Bài viết', kindBook: 'Sách', kindText: 'Văn bản đã nhập', modeActive: 'Đọc chủ động', pageOf: 'tr. {n}/{total}',
    practiceTitle: 'Luyện đọc', minutes: '{n} phút', endNotePractice: 'Hết bài · {n} câu hỏi, rồi sang bài đọc tiếp theo.',
    summaryGenerated: 'Tạo khi bạn yêu cầu', summaryLoading: 'Đang viết bản tóm tắt…', summaryFailed: 'Chưa tạo được bản tóm tắt lúc này.', summaryStays: 'Văn bản vẫn ở nguyên chỗ; đóng bảng này để đọc tiếp.', retry: 'Thử lại', translationFailed: 'Chưa dịch được lúc này.', translationLoading: 'Đang dịch…',
  },
  zh: {
    readingAppearance: '阅读外观', aa: 'Aa', aaSmaller: '缩小文字', aaLarger: '放大文字', aidsLabel: '辅助', moreLabel: '更多',
    themeDark: '深色主题', listen: '朗读', listenPause: '暂停朗读',
    saveLabel: '收藏', savedLabel: '已收藏 ✓', savedToast: '已收藏', removedToast: '已移除', saveFailed: '暂时无法保存',
    translationAid: '{lang} 释义', vocabLensAid: '词汇高亮', wordRolesAid: '词性', pinyinAid: '拼音',
    pinyinNotApplicable: '拼音 · 仅适用于中文',
    notesLabel: '笔记 · {n}', summaryLabel: '摘要', summaryNotPrepared: '此文本尚未准备摘要',
    roleNoun: '名词', roleVerb: '动词', roleModifier: '修饰词', roleConnector: '连接词', rolePronoun: '代词', roleNumber: '数词',
    posLegendHint: '· 点按一个词查看它的词性',
    roleNounHelp: '表示事物、人或概念', roleVerbHelp: '表示动作或状态', roleModifierHelp: '描述或限定',
    roleConnectorHelp: '连接分句或观点', rolePronounHelp: '指代前面提到的事物', roleNumberHelp: '表示数量或顺序',
    yourNote: '你的笔记 · {when}', noteExpand: '展开笔记', noteCollapse: '收起笔记', editInSentence: '在句子中编辑',
    notesHighlights: '笔记与高亮', noNotesYet: '暂无笔记。点按一个句子 → “添加笔记”或“保存高亮”。',
    typeFactual: '事实', typeReflection: '感想', typeQuestion: '问题', typeHighlight: '高亮',
    selTranslate: '翻译', selHighlight: '高亮', selHighlighted: '已高亮', selNote: '笔记',
    chapters: '章节', markAsFinished: '标记为已读完', nextChapterCta: '下一章 →',
    endNoteChapter: '第 {n} 章结束 · 可选：检查理解，或继续下一章。', endNoteArticle: '文章结束 · 可选：检查理解，或标记为已读完。', endNoteText: '你的文本已结束。',
    translationUnavailable: '暂时无法翻译',
    listenStarted: '正在从当前位置朗读', listenStopped: '已暂停朗读',
    listenUnavailable: '此设备不支持朗读',
    writeResponse: '写一段回应', kindArticle: '文章', kindBook: '书', kindText: '导入的文本', modeActive: '主动阅读', pageOf: '第 {n}/{total} 页',
    practiceTitle: '阅读练习', minutes: '{n} 分钟', endNotePractice: '本文结束 · {n} 道题，然后进入下一篇。',
    summaryGenerated: '按需生成', summaryLoading: '正在生成摘要…', summaryFailed: '暂时无法生成摘要。', summaryStays: '原文保持不动；关闭此面板即可继续阅读。', retry: '重试', translationFailed: '暂时无法翻译。', translationLoading: '正在翻译…',
  },
});
