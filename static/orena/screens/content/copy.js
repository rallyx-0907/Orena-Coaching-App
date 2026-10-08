/* Content Detail's own words (design route `detail`, frame 05). Every string here is chrome -
   a control label or a real system state, never the frame's sample title/description/transcript
   (D-068: those are the content's own data, read from the API). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'back',
  'typeArticle', 'typeBook', 'typeText', 'typeVideo', 'typeAudio',
  'startReading', 'continueReading', 'listen', 'continueListening', 'continueWatching',
  'save', 'saved', 'practiceThisText', 'transcript',
  'generated', 'captions', 'minutes',
  'related', 'resume', 'resumeAt', 'resumeChapter', 'readAgain', 'progressPercent',
  'more', 'deleteFromOrena', 'deletedFromOrena',
];

export const t = defineCopy('content', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    back: '← Back',
    typeArticle: 'Article', typeBook: 'Book', typeText: 'My text', typeVideo: 'Video', typeAudio: 'Audio',
    startReading: 'Start reading', continueReading: 'Continue reading',
    listen: 'Start listening', continueListening: 'Continue listening', continueWatching: 'Continue watching',
    save: 'Save', saved: 'Saved', practiceThisText: 'Practice this text', transcript: 'Transcript',
    generated_one: 'Generated · {n} segment', generated_other: 'Generated · {n} segments',
    captions_one: 'Captions · {n} segment', captions_other: 'Captions · {n} segments',
    minutes: '{n} min',
    related: 'Related', resume: 'Resume', resumeAt: 'Resume at {at}', resumeChapter: 'Resume at chapter {n} of {total}', readAgain: 'Read again', progressPercent: '{pct}% complete',
    more: 'More', deleteFromOrena: 'Delete from Orena', deletedFromOrena: 'Deleted from Orena',
  },
  vi: {
    back: '← Quay lại',
    typeArticle: 'Bài đọc', typeBook: 'Sách', typeText: 'Văn bản của tôi', typeVideo: 'Video', typeAudio: 'Âm thanh',
    startReading: 'Bắt đầu đọc', continueReading: 'Tiếp tục đọc',
    listen: 'Bắt đầu nghe', continueListening: 'Tiếp tục nghe', continueWatching: 'Tiếp tục xem',
    save: 'Lưu', saved: 'Đã lưu', practiceThisText: 'Luyện tập với bài này', transcript: 'Bản ghi',
    generated_other: 'Tự động tạo · {n} đoạn',
    captions_other: 'Phụ đề · {n} đoạn',
    minutes: '{n} phút',
    related: 'Liên quan', resume: 'Tiếp tục', resumeAt: 'Tiếp tục từ {at}', resumeChapter: 'Tiếp tục ở chương {n} / {total}', readAgain: 'Đọc lại', progressPercent: 'Hoàn thành {pct}%',
    more: 'Thêm', deleteFromOrena: 'Xoá khỏi Orena', deletedFromOrena: 'Đã xoá khỏi Orena',
  },
  zh: {
    back: '← 返回',
    typeArticle: '文章', typeBook: '书籍', typeText: '我的文本', typeVideo: '视频', typeAudio: '音频',
    startReading: '开始阅读', continueReading: '继续阅读',
    listen: '开始收听', continueListening: '继续收听', continueWatching: '继续观看',
    save: '保存', saved: '已保存', practiceThisText: '练习这篇文本', transcript: '文字记录',
    generated_other: '自动生成 · {n} 段',
    captions_other: '字幕 · {n} 段',
    minutes: '{n} 分钟',
    related: '相关内容', resume: '继续', resumeAt: '从 {at} 继续', resumeChapter: '从第 {n} / {total} 章继续', readAgain: '重新阅读', progressPercent: '已完成 {pct}%',
    more: '更多', deleteFromOrena: '从 Orena 删除', deletedFromOrena: '已从 Orena 删除',
  },
});
