/* Words of the Notifications sheet (frame 59). The sheet's own title/close reuse shellCopy
   ('notifications'/'close', already the bell's own words); this table holds only what is specific
   to its two real row kinds - kind labels are interface (chrome/state), the empty message and the
   progress sub-line are support (they explain a state, not name a control).

   `percentComplete` (not `percentRead`) is deliberate: the same progress fraction is shown for
   reading, listening and writing continuation rows alike (sheet.js's KIND_LABEL), so "read" would
   be wrong on a listening or writing row - "complete" fits all three.

   `dueTitle` is declared once, under its bare name, and read with `t.plural('dueTitle', n)`
   (D-091 kit fidelity pass - `copy/index.js`'s `plural()` now picks the form by the plural rules
   of the language the key itself renders in, not by which forms the resolved table happens to
   hold, so vi/zh correctly always read `dueTitle_other` and English reads `dueTitle_one` only at
   n===1). vi/zh have no real singular form (Vietnamese and Chinese have one plural rule, "other",
   for every n), so only `dueTitle_other` is declared for them - `dueTitle_one` would never be
   selected and duplicating the same string under both keys would just be dead weight. */
import { defineCopy } from '../../copy/index.js';

export const t = defineCopy('notifications', {
  layers: {
    subtitle: 'interface',
    reviewKind: 'interface',
    continueReadingKind: 'interface',
    continueListeningKind: 'interface',
    continueWritingKind: 'interface',
    // A due-count state label, like word/copy.js's dueToday/dueInDays and practice/copy.js's
    // dueOne/dueOther - not an explanation, so interface (the learner's own device language),
    // not support (their profile's support language, a different setting the bell has no reason
    // to follow).
    dueTitle: 'interface',
    // System copy follows the interface language (HP-1 A, as D-139 HD-14).
    percentComplete: 'interface',
    empty: 'interface',
  },
  en: {
    subtitle: 'Tap one to open the exact result',
    reviewKind: 'Review',
    continueReadingKind: 'Continue reading', continueListeningKind: 'Continue listening', continueWritingKind: 'Continue writing',
    dueTitle_one: '{n} word due for review', dueTitle_other: '{n} words due for review',
    percentComplete: '{n}% complete',
    empty: 'You’re all caught up.',
  },
  vi: {
    subtitle: 'Nhấn vào một mục để mở đúng kết quả',
    reviewKind: 'Ôn tập',
    continueReadingKind: 'Tiếp tục đọc', continueListeningKind: 'Tiếp tục nghe', continueWritingKind: 'Tiếp tục viết',
    dueTitle_other: '{n} từ đến hạn ôn tập',
    percentComplete: 'Hoàn thành {n}%',
    empty: 'Bạn đã hoàn tất mọi việc.',
  },
  zh: {
    subtitle: '点击即可打开对应内容',
    reviewKind: '复习',
    continueReadingKind: '继续阅读', continueListeningKind: '继续听力', continueWritingKind: '继续写作',
    dueTitle_other: '有 {n} 个词到期需要复习',
    percentComplete: '已完成 {n}%',
    empty: '暂无待办，你都跟上了。',
  },
});
