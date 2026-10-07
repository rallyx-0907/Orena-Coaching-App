/* My Library's own words (frame 12, live source `orena-script.js` LIBT/`activeUse` - the pinned
   design's own compact export mis-hinted "4 tabs"; the live script proves 5: Saved content, Saved
   language, Collections, Active use, Due Review). Titles the shell already owns (Review, Context
   Transfer, Situation Reaction, Timed Recall - the Active-use tab's four fixed shortcuts; Listening,
   Writing, Grammar, Word - the type chip and the "in this session" fallback label) come from
   copy/shell.js, not repeated here; this table holds only what is specific to this screen.
   Interface layer throughout - every string here is a label, a control or a system-state
   sentence, never an explanation (D-079). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'tabContent', 'tabLanguage', 'tabCollections', 'tabActive', 'tabDueCount',
  'typePhrase', 'newBadge', 'emptyLanguage',
  'dueNow', 'dueItemsLabel', 'statWords', 'statPhrases', 'statSource', 'startReview', 'inThisSession',
  'kindSpeaking', 'sourceReading', 'sourceFeedback',
  /* The four Active-use cards (design: `activeUse[]{stage, title, desc, dur, onOpen}`, a fixed
     shortcut list into Vocabulary's own Recall/Use/Transfer flows, not a backend-fetched row set -
     see model.js's `activeUseCards`). `dur` ("~3 min" in the design) is not carried: no route this
     tab opens returns a duration, and `screens/practice/model.js`'s own precedent for the same gap
     ("no duration is ever returned, so the eyebrow never grows a fabricated '~N min'") is the one to
     match, not re-litigate per screen. */
  'activeDueTitle', 'activeDueDesc', 'activeTransferDesc', 'activeSituationTitle', 'activeSituationDesc',
  'activeTimedDesc', 'stageRecall', 'stageUse', 'stageTransfer', 'stageFast',
  'collectionItems', 'emptyCollections',
  'more', 'deleteFromOrena', 'deletedFromOrena', 'untitledContent', 'contentUnavailable',
];

export const t = defineCopy('library', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    tabContent: 'Saved content', tabLanguage: 'Saved language', tabCollections: 'Collections', tabActive: 'Active use',
    tabDueCount: 'Due Review · {n}',
    emptyCollections: 'No collections yet.',
    typePhrase: 'Phrase', newBadge: 'NEW', emptyLanguage: 'Nothing saved yet.',
    dueNow: 'Due now',
    dueItemsLabel_one: 'item', dueItemsLabel_other: 'items',
    statWords_one: 'word', statWords_other: 'words',
    statPhrases_one: 'phrase', statPhrases_other: 'phrases',
    statSource: 'source-aware',
    startReview: 'Start review', inThisSession: 'In this session',
    kindSpeaking: 'Speaking',
    sourceReading: 'From your reading', sourceFeedback: 'From your writing feedback',
    activeDueTitle: 'Due review',
    activeDueDesc_one: 'Retrieve without seeing the answer · {n} item',
    activeDueDesc_other: 'Retrieve without seeing the answer · {n} items',
    activeTransferDesc: 'Produce the word from a situation prompt; the target stays hidden',
    activeSituationTitle: 'Situation Reaction · context variant', activeSituationDesc: 'Same intent, new context → Transfer evidence',
    activeTimedDesc_one: 'Time to start and time to answer, {n} due word',
    activeTimedDesc_other: 'Time to start and time to answer, {n} due words',
    stageRecall: 'Recall', stageUse: 'Use', stageTransfer: 'Transfer', stageFast: 'Fast retrieval',
    collectionItems_one: '{n} item', collectionItems_other: '{n} items',
    more: 'More', deleteFromOrena: 'Delete from Orena', deletedFromOrena: 'Deleted from Orena',
    untitledContent: 'Untitled', contentUnavailable: 'No longer available',
  },
  vi: {
    tabContent: 'Nội dung đã lưu', tabLanguage: 'Từ & cụm đã lưu', tabCollections: 'Bộ sưu tập', tabActive: 'Vận dụng',
    tabDueCount: 'Cần ôn tập · {n}',
    emptyCollections: 'Chưa có bộ sưu tập nào.',
    typePhrase: 'Cụm từ', newBadge: 'MỚI', emptyLanguage: 'Chưa lưu gì.',
    dueNow: 'Cần ôn ngay',
    dueItemsLabel_other: 'mục', statWords_other: 'từ', statPhrases_other: 'cụm từ', statSource: 'theo ngữ cảnh nguồn',
    startReview: 'Bắt đầu ôn tập', inThisSession: 'Trong buổi này',
    kindSpeaking: 'Nói',
    sourceReading: 'Từ bài đọc của bạn', sourceFeedback: 'Từ phản hồi bài viết của bạn',
    activeDueTitle: 'Ôn đến hạn',
    activeDueDesc_other: 'Nhớ lại mà không xem đáp án · {n} mục',
    activeTransferDesc: 'Tạo ra từ từ một tình huống gợi ý; từ mục tiêu vẫn được giấu kín',
    activeSituationTitle: 'Phản xạ tình huống · biến thể ngữ cảnh', activeSituationDesc: 'Cùng một ý định, ngữ cảnh mới → chuyển thành minh chứng',
    activeTimedDesc_other: 'Tính giờ từ lúc bắt đầu đến lúc trả lời, {n} từ đến hạn',
    stageRecall: 'Nhớ lại', stageUse: 'Vận dụng', stageTransfer: 'Chuyển ngữ cảnh', stageFast: 'Nhớ nhanh',
    collectionItems_other: '{n} mục',
    more: 'Thêm', deleteFromOrena: 'Xoá khỏi Orena', deletedFromOrena: 'Đã xoá khỏi Orena',
    untitledContent: 'Chưa có tên', contentUnavailable: 'Không còn khả dụng',
  },
  zh: {
    tabContent: '已保存内容', tabLanguage: '已保存词语', tabCollections: '合集', tabActive: '运用',
    tabDueCount: '待复习 · {n}',
    emptyCollections: '还没有合集。',
    typePhrase: '短语', newBadge: '新', emptyLanguage: '还没有保存内容。',
    dueNow: '现在待复习',
    dueItemsLabel_other: '项', statWords_other: '单词', statPhrases_other: '短语', statSource: '结合来源',
    startReview: '开始复习', inThisSession: '本次复习',
    kindSpeaking: '口语',
    sourceReading: '来自你的阅读', sourceFeedback: '来自你的写作反馈',
    activeDueTitle: '待复习',
    activeDueDesc_other: '不看答案回忆 · {n} 项',
    activeTransferDesc: '根据情景提示说出该词；目标词保持隐藏',
    activeSituationTitle: '情景反应 · 语境变体', activeSituationDesc: '相同意图，新的语境 → 转化为迁移证据',
    activeTimedDesc_other: '计时从开始到作答，{n} 个待复习单词',
    stageRecall: '回忆', stageUse: '运用', stageTransfer: '语境迁移', stageFast: '快速回忆',
    collectionItems_other: '{n} 项',
    more: '更多', deleteFromOrena: '从 Orena 删除', deletedFromOrena: '已从 Orena 删除',
    untitledContent: '无标题', contentUnavailable: '已不可用',
  },
});
