/* Words around the legal pages (completion plan item 5, D-128): the three titles and the draft line.
   The legal text itself is not copy - it is the drafts' own text (legal/content.js). Chinese has no
   approved text yet, so a Chinese interface reads the English text and its line says so; nothing is
   machine-translated (UI_BACKEND_GAPS, "Legal pages"). */
import { defineCopy } from './index.js';

const KEYS = ['terms', 'privacy', 'refund', 'draft', 'draftEnglish'];

export const legalCopy = defineCopy('legal', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    terms: 'Terms of Use',
    privacy: 'Privacy Policy',
    refund: 'Refund Policy',
    draft: 'Draft, awaiting approval',
    draftEnglish: 'Draft, awaiting approval',
  },
  vi: {
    terms: 'Điều khoản sử dụng',
    privacy: 'Chính sách bảo mật',
    refund: 'Chính sách hoàn tiền',
    draft: 'Bản dự thảo, đang chờ duyệt',
    draftEnglish: 'Bản dự thảo, đang chờ duyệt',
  },
  zh: {
    terms: '使用条款',
    privacy: '隐私政策',
    refund: '退款政策',
    draft: '草案，待批准',
    draftEnglish: '草案，待批准。中文版待批准，以下为英文文本。',
  },
});
