/* Reading Complete's own words (design route `rcomplete`, frame 40). "Reading Transfer" already
   exists in copy/shell.js (shellCopy) and is reused, not redefined here. The frame's eyebrow
   "Next · same theme" is "Next": the backend has no relatedness signal, so the row does not claim
   one (recorded in the report). */
import { defineCopy } from '../../copy/index.js';

const KEYS = ['sessionComplete', 'savedFromText', 'notesHighlights', 'understood', 'nextLabel', 'nextChapter', 'chooseNext', 'reviewSavedWords', 'backTo'];

export const t = defineCopy('reader-complete', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    sessionComplete: 'Session complete',
    savedFromText: 'saved from this text', notesHighlights: 'notes & highlights', understood: 'understood',
    nextLabel: 'Next', nextChapter: 'Next chapter', chooseNext: 'Choose what to read next',
    reviewSavedWords: 'Review saved words', backTo: 'Back to {place}',
  },
  vi: {
    sessionComplete: 'Hoàn thành phiên đọc',
    savedFromText: 'đã lưu từ bài này', notesHighlights: 'ghi chú & tô sáng', understood: 'đã hiểu',
    nextLabel: 'Tiếp theo', nextChapter: 'Chương tiếp theo', chooseNext: 'Chọn bài đọc tiếp theo',
    reviewSavedWords: 'Ôn từ đã lưu', backTo: 'Quay lại {place}',
  },
  zh: {
    sessionComplete: '阅读完成',
    savedFromText: '本文已保存', notesHighlights: '笔记与高亮', understood: '已理解',
    nextLabel: '下一篇', nextChapter: '下一章', chooseNext: '选择接下来读什么',
    reviewSavedWords: '复习已保存的词', backTo: '返回{place}',
  },
});
