/* Collection Detail's own words (frame 21, D2 §6). Titles the shell already owns ("Collection",
   "Back") stay in copy/shell.js (shellCopy) and are reused, not redeclared here. Every key here
   is interface layer (labels, a button, a state, a toast) - none of it explains the language
   being learned, so none of it is 'support' (D-079). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'collectionLoading',
  'collectionPillLevel', 'collectionPillPlain',
  'collectionWordCount', 'collectionMetInSources', 'collectionStartReview',
  'collectionSave', 'collectionSaveUnavailable', 'collectionAudioUnavailable',
  'collectionWordsHeading', 'collectionNewBadge', 'collectionEmptyWords', 'collectionPlay',
];

export const t = defineCopy('collection', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    collectionLoading: 'Loading collection…',
    collectionPillLevel: 'Collection · {level}',
    collectionPillPlain: 'Collection',
    collectionWordCount_one: '{n} word',
    collectionWordCount_other: '{n} words',
    collectionMetInSources: '{n} met in your sources',
    collectionStartReview_one: 'Start review · {n} item',
    collectionStartReview_other: 'Start review · {n} items',
    collectionSave: 'Save',
    collectionSaveUnavailable: 'Saving a whole collection isn’t available yet',
    collectionAudioUnavailable: 'No pronunciation available for this word yet',
    collectionWordsHeading: 'Words',
    collectionNewBadge: 'NEW',
    collectionEmptyWords: 'This collection has no words yet.',
    collectionPlay: 'Play pronunciation',
  },
  vi: {
    collectionLoading: 'Đang tải bộ sưu tập…',
    collectionPillLevel: 'Bộ sưu tập · {level}',
    collectionPillPlain: 'Bộ sưu tập',
    collectionWordCount_other: '{n} từ',
    collectionMetInSources: '{n} đã gặp trong nguồn của bạn',
    collectionStartReview_other: 'Ôn tập ngay · {n} mục',
    collectionSave: 'Lưu',
    collectionSaveUnavailable: 'Chưa thể lưu cả bộ sưu tập này',
    collectionAudioUnavailable: 'Từ này chưa có phát âm',
    collectionWordsHeading: 'Từ vựng',
    collectionNewBadge: 'MỚI',
    collectionEmptyWords: 'Bộ sưu tập này chưa có từ nào.',
    collectionPlay: 'Nghe phát âm',
  },
  zh: {
    collectionLoading: '正在加载合集…',
    collectionPillLevel: '合集 · {level}',
    collectionPillPlain: '合集',
    collectionWordCount_other: '{n} 个词',
    collectionMetInSources: '{n} 个已在你的素材中出现',
    collectionStartReview_other: '开始复习 · {n} 项',
    collectionSave: '保存',
    collectionSaveUnavailable: '暂不支持保存整个合集',
    collectionAudioUnavailable: '这个词还没有发音',
    collectionWordsHeading: '词语',
    collectionNewBadge: '新',
    collectionEmptyWords: '这个合集还没有词语。',
    collectionPlay: '播放发音',
  },
});
