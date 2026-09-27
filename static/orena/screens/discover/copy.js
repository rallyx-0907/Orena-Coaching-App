/* Discover's own words (frame 04-Discover.html, 52-Filter-Sheet.html). Interface layer throughout
   - every key here is a control, a state or a data label, never an explanation (D-079). The page
   title itself reuses copy/shell.js's `discover` (the same word already carries the rail label and
   the breadcrumb; rule 50 also drops the frame's decorative subtitle entirely, so there is no
   separate title string to declare here). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'searchPlaceholder', 'filters', 'importAction', 'clearFilters', 'emptyText',
  'tabAll', 'tabRead', 'tabListen', 'tabCollections', 'tabImported',
  'typeArticle', 'typeBook', 'typeVideo', 'typeAudio', 'typeCollection', 'typeText', 'typeUpload',
  'durationMinRead', 'durationChapters', 'durationItems', 'collectionWordCount', 'progressPercent', 'progressLearnedOf',
  'resultsLabel', 'groupLevel', 'groupTopic', 'groupType', 'clear', 'showResults',
];

export const t = defineCopy('discover', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    searchPlaceholder: 'Search books, media, collections…',
    filters: 'Filters', importAction: 'Import', clearFilters: 'Clear filters',
    emptyText: 'Nothing matches these filters yet.',
    tabAll: 'All', tabRead: 'Read', tabListen: 'Listen · Watch', tabCollections: 'Collections', tabImported: 'Imported',
    typeArticle: 'Article', typeBook: 'Book', typeVideo: 'Video', typeAudio: 'Audio',
    typeCollection: 'Collection', typeText: 'Text', typeUpload: 'Imported',
    durationMinRead: '{n} min read', durationChapters_one: '{n} chapter', durationChapters_other: '{n} chapters',
    durationItems_one: '{n} item', durationItems_other: '{n} items',
    collectionWordCount_one: '{n} word', collectionWordCount_other: '{n} words',
    progressPercent: '{pct}%', progressLearnedOf: '{learned} / {total} learned',
    resultsLabel_one: '{n} result', resultsLabel_other: '{n} results',
    groupLevel: 'Level', groupTopic: 'Topic', groupType: 'Content type', clear: 'Clear',
    showResults_one: 'Show {n} result', showResults_other: 'Show {n} results',
  },
  vi: {
    searchPlaceholder: 'Tìm sách, media, bộ sưu tập…',
    filters: 'Bộ lọc', importAction: 'Nhập', clearFilters: 'Xóa bộ lọc',
    emptyText: 'Chưa có gì khớp với các bộ lọc này.',
    tabAll: 'Tất cả', tabRead: 'Đọc', tabListen: 'Nghe · Xem', tabCollections: 'Bộ sưu tập', tabImported: 'Đã nhập',
    typeArticle: 'Bài viết', typeBook: 'Sách', typeVideo: 'Video', typeAudio: 'Âm thanh',
    typeCollection: 'Bộ sưu tập', typeText: 'Văn bản', typeUpload: 'Đã nhập',
    durationMinRead: '{n} phút đọc', durationChapters_other: '{n} chương',
    durationItems_other: '{n} mục',
    collectionWordCount_other: '{n} từ',
    progressPercent: '{pct}%', progressLearnedOf: '{learned} / {total} đã học',
    resultsLabel_other: '{n} kết quả',
    groupLevel: 'Trình độ', groupTopic: 'Chủ đề', groupType: 'Loại nội dung', clear: 'Xóa',
    showResults_other: 'Xem {n} kết quả',
  },
  zh: {
    searchPlaceholder: '搜索书籍、媒体、合集…',
    filters: '筛选', importAction: '导入', clearFilters: '清除筛选',
    emptyText: '没有符合这些筛选条件的内容。',
    tabAll: '全部', tabRead: '阅读', tabListen: '听 · 看', tabCollections: '合集', tabImported: '已导入',
    typeArticle: '文章', typeBook: '书籍', typeVideo: '视频', typeAudio: '音频',
    typeCollection: '合集', typeText: '文本', typeUpload: '已导入',
    durationMinRead: '{n} 分钟阅读', durationChapters_other: '{n} 章',
    durationItems_other: '{n} 项',
    collectionWordCount_other: '{n} 个词',
    progressPercent: '{pct}%', progressLearnedOf: '已学 {learned} / {total}',
    resultsLabel_other: '{n} 个结果',
    groupLevel: '级别', groupTopic: '主题', groupType: '内容类型', clear: '清除',
    showResults_other: '查看 {n} 个结果',
  },
});
