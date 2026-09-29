/* Frame 27 "Search" (pinned design, focus route). Interface layer throughout: every string here
   is a chrome label, a state line or a kind chip, not learner-facing explanation (D-079).

   Titles already in copy/shell.js (shellCopy) are reused from the screen instead of repeated here:
   `back`, `search`, `word`, `content`, `myLibrary`, `writing`, `pronunciation`, `grammar`. */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'wordsGroup', 'kindArticle', 'kindMedia', 'kindUpload', 'kindText',
  'recentLabel', 'placeholder', 'clearLabel', 'noneMessage', 'resultsFor',
  'relationship_saved', 'relationship_completed', 'relationship_practised', 'relationship_submitted', 'relationship_spoken',
];

export const t = defineCopy('search', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    wordsGroup: 'Words', kindArticle: 'Article', kindMedia: 'Media', kindUpload: 'Upload', kindText: 'Text',
    recentLabel: 'Recent', placeholder: 'Words, content, saved items…', clearLabel: 'Clear search',
    noneMessage: 'Nothing found for “{query}”. Try a word, a title, or something you’ve saved.',
    resultsFor_one: '{n} result for “{query}”',
    resultsFor_other: '{n} results for “{query}”',
    relationship_saved: 'Saved', relationship_completed: 'Completed', relationship_practised: 'Practised',
    relationship_submitted: 'Submitted', relationship_spoken: 'Spoken',
  },
  vi: {
    wordsGroup: 'Từ', kindArticle: 'Bài đọc', kindMedia: 'Media', kindUpload: 'Đã tải lên', kindText: 'Văn bản',
    recentLabel: 'Gần đây', placeholder: 'Từ, nội dung, mục đã lưu…', clearLabel: 'Xóa tìm kiếm',
    noneMessage: 'Không tìm thấy gì cho “{query}”. Thử một từ, một tiêu đề, hoặc thứ bạn đã lưu.',
    resultsFor_other: '{n} kết quả cho “{query}”',
    relationship_saved: 'Đã lưu', relationship_completed: 'Đã hoàn thành', relationship_practised: 'Đã luyện tập',
    relationship_submitted: 'Đã gửi', relationship_spoken: 'Đã nói',
  },
  zh: {
    wordsGroup: '词语', kindArticle: '文章', kindMedia: '媒体', kindUpload: '上传内容', kindText: '文本',
    recentLabel: '最近搜索', placeholder: '词语、内容、已保存的内容…', clearLabel: '清除搜索',
    noneMessage: '没有找到 “{query}” 的结果。试试某个词、标题，或你保存过的内容。',
    resultsFor_other: '找到 {n} 个结果：“{query}”',
    relationship_saved: '已保存', relationship_completed: '已完成', relationship_practised: '已练习',
    relationship_submitted: '已提交', relationship_spoken: '已说',
  },
});
