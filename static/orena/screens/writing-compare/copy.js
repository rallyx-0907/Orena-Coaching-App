/* Compare Versions' own words (D-079, Design Contract rules 9, 26, 50). All interface (labels,
   headers, counts) - this screen states a diff, it explains nothing, so it carries no support
   layer at all. */
import { defineCopy } from '../../copy/index.js';

const LAYERS = {
  versionLabel: 'interface', versionBare: 'interface', earlierTab: 'interface', revisedTab: 'interface',
  changesHeader: 'interface',
  fixedLabel: 'interface', remainingLabel: 'interface', newLabel: 'interface',
  gramWord: 'interface', rangeWord: 'interface',
};

export const t = defineCopy('writing-compare', {
  layers: LAYERS,
  en: {
    versionLabel: 'Version {n} · {when}', versionBare: 'Version {n}', earlierTab: 'Earlier', revisedTab: 'Revised',
    changesHeader: 'Changes',
    fixedLabel: 'Fixed', remainingLabel: 'Still present', newLabel: 'New',
    gramWord: 'Grammar', rangeWord: 'range',
  },
  vi: {
    versionLabel: 'Phiên bản {n} · {when}', versionBare: 'Phiên bản {n}', earlierTab: 'Trước', revisedTab: 'Sau khi sửa',
    changesHeader: 'Thay đổi',
    fixedLabel: 'Đã sửa', remainingLabel: 'Vẫn còn', newLabel: 'Mới',
    gramWord: 'Ngữ pháp', rangeWord: 'trình độ',
  },
  zh: {
    versionLabel: '版本 {n} · {when}', versionBare: '版本 {n}', earlierTab: '之前', revisedTab: '修改后',
    changesHeader: '变化',
    fixedLabel: '已修正', remainingLabel: '仍存在', newLabel: '新增',
    gramWord: '语法', rangeWord: '水平',
  },
});
