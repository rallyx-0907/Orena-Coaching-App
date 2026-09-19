// Experience identity is presentation over the existing routes, never another
// capability engine. New surfaces join this map and inherit the same shell.
import { link } from '../product/intent.js';
import { esc } from './html.js';
import { scene } from './brand.js';
import { continuationEntries, continuationPlace, hint, pageIntro } from './patterns.js';
import { entryIcon } from './icons.js';
import { icon } from './phosphor.js';
import { art } from './content.js';
import { continuationExperience, continuationLink } from '../product/intent.js';

export { entryIcon } from './icons.js';

export const referenceCopy = {
  en: {
    collection: 'Collection',
    moreStories: 'More to read',
    collectionSearch: 'Find something you kept',
    collectionSearchHint: 'Search everything you have met or kept',
    collectionLenses: 'How you met it',
    lens_all: 'Everything', lens_reading: 'Read', lens_listening: 'Heard',
    lens_speaking: 'Spoken', lens_writing: 'Written', lens_language: 'Language',
    collectionResults: 'here',
    collectionThreads: 'Where you were', collectionYourContent: 'What you brought in',
    collectionYourLanguage: 'Language you kept',
    collectionViewAll: 'See all',
    collectionEmpty: 'Nothing here yet.',
    collectionEmptyNote: 'What you read, hear, keep and write will gather here.',
    threadLabel: 'A thread', contentLabel: 'Yours', languageLabel: 'Kept',
    discover: 'Discover', practice: 'Practice', reading: 'Reading', listening: 'Listening',
    writing: 'Writing', speaking: 'Speaking', vocabulary: 'Vocabulary', understanding: 'Patterns & meaning',
    language: 'My language', recall: 'Recall', continue: 'Continue', content: 'My content', admin: 'Platform Admin',
    world: 'A bigger world', make: 'Make it yours', keep: 'Your growing world',
    destinations: 'Destinations', closeDestinations: 'Close destinations',
    home: 'Home', library: 'Library', progress: 'Progress', profile: 'Profile', you: 'You',
    dictation: 'Dictation', settings: 'Settings', allPractice: 'All practice',
    allDestinations: 'Everything in Orena', mainNavigation: 'Main', practiceNavigation: 'Practice',
    languagePair: 'Learning {learning}, explained in {support}',
    progressWindow: 'Period', progressWindow_7d: '7 days', progressWindow_30d: '30 days',
    progressWindow_90d: '90 days', progressWindow_all: 'All time',
    invitation: 'A little curiosity.\nA bigger world.',
    welcome: 'Come for a story. Stay for what it opens up.',
    note: 'Listen closely. Wander through a story. Find something you want to say.',
    featured: 'Through another window', readNext: 'Between the lines',
    practiceTitle: 'A small moment.\nA little more yours.',
    practiceNote: 'Choose an intention. Work with a real voice, a passage, or a thought of your own.',
    listenTitle: 'The world has\nsomething to say.',
    listenNote: 'Follow a voice at your pace. Stay with the meaning, or step inside a single line.',
    goRead: 'Find a story', goListen: 'Follow a voice', goSpeak: 'Start an exchange',
    studio: 'Make room for your own words', studioNote: 'Something you heard can become something you say.',
    writingInvite: 'A thought worth putting into words.',
    writingDetail: 'A message, a story, a different point of view. Begin with what you mean.',
    practiceInvite: 'Stay with one small moment.',
    practiceDetail: 'Catch the words. Borrow the rhythm. Try again with a little more understanding.',
    continueTitle: 'There’s a thread\nwaiting for you.',
    continueEmpty: 'Your next visit starts here.',
    continueNote: 'The stories you enter and the words you work on leave a way back. These threads stay on this device.',
    collectionTitle: 'A world with\nyour fingerprints on it.',
    collectionNote: 'Things you brought in and chose to keep. Ready for another look.',
    browseAll: 'All the ways in', fieldNote: 'Follow your curiosity', continueLearning: 'Continue learning',
    railPrevious: 'Previous', railNext: 'Next', railEmpty: 'Nothing here yet.',
    startTitle: 'Start here', startAction: 'Start learning', continueAction: 'Continue',
    railShort: 'Around five minutes', railStories: 'Stories', railVoices: 'Everyday voices',
    railSay: 'Something to say', railWords: 'Words worth keeping', railMinutes: 'min',
    newContent: 'New content', newContentEmpty: 'Nothing new yet',
    direct: 'Choose your intention', review: 'Reference in progress · your work stays yours',
  },
  zh: {
    admin: '\u5e73\u53f0\u7ba1\u7406',
    collection: '收藏',
    moreStories: '更多可读的',
    collectionSearch: '找回你留下的东西',
    collectionSearchHint: '搜索你遇到过、留下过的一切',
    collectionLenses: '你是怎么遇到它的',
    lens_all: '全部', lens_reading: '读过', lens_listening: '听过',
    lens_speaking: '说过', lens_writing: '写过', lens_language: '语言',
    collectionResults: '项',
    collectionThreads: '上次停在哪里', collectionYourContent: '你带进来的',
    collectionYourLanguage: '你留下的语言',
    collectionViewAll: '查看全部',
    collectionEmpty: '这里还是空的。',
    collectionEmptyNote: '你读过、听过、留下和写下的，都会聚到这里。',
    threadLabel: '一条线索', contentLabel: '你的', languageLabel: '已留下',
    discover: '发现', practice: '练习', reading: '阅读', listening: '聆听', writing: '写作',
    speaking: '表达', vocabulary: '词汇', understanding: '句式与含义', language: '我的语言', recall: '回想',
    continue: '继续', content: '我的内容', world: '走进更大的世界', make: '用自己的方式表达', keep: '慢慢积累的世界',
    destinations: '去处', closeDestinations: '收起去处',
    home: '首页', library: '书库', progress: '进度', profile: '个人', you: '我',
    dictation: '听写', settings: '设置', allPractice: '全部练习',
    allDestinations: 'Orena 的全部去处', mainNavigation: '主要', practiceNavigation: '练习',
    languagePair: '正在学{learning}，用{support}讲解',
    progressWindow: '时间范围', progressWindow_7d: '7 天', progressWindow_30d: '30 天',
    progressWindow_90d: '90 天', progressWindow_all: '全部',
    invitation: '一点好奇，\n一个更大的世界。', welcome: '从一个故事开始，看看它会带你去哪里。',
    note: '听见一种声音，走进一个故事，找到自己想说的话。',
    featured: '打开另一扇窗', readNext: '在字里行间',
    practiceTitle: '留住一个瞬间，\n让它成为你的语言。',
    practiceNote: '选一个练习方向。从真实的声音、文章，或自己的想法开始。',
    listenTitle: '这个世界，\n有话想对你说。', listenNote: '按自己的节奏听懂一种声音。可以一直听，也可以停下来练一句。',
    goRead: '找一个故事', goListen: '跟随一种声音', goSpeak: '开始一段对话',
    studio: '给自己的话留一点空间', studioNote: '刚刚听到的话，也可以成为你自己的表达。',
    writingInvite: '有个想法，值得写下来。', writingDetail: '一条消息，一个故事，一种不同的看法。从你真正想表达的意思开始。',
    practiceInvite: '多留一会儿，听懂这一刻。', practiceDetail: '听清文字，感受节奏。多一点理解，再试一次。',
    continueTitle: '上次的故事，\n等你接着往下走。', continueEmpty: '下次回来，从这里继续。',
    continueNote: '读过的故事、写到一半的话，都留下一条回来的路。这些记录保存在当前设备。',
    collectionTitle: '这个世界里，\n有你留下的印记。', collectionNote: '你带来的、你选择留下的内容。随时可以再看看。',
    browseAll: '每一种开始', fieldNote: '跟着好奇心走', continueLearning: '继续学习',
    railPrevious: '上一组', railNext: '下一组', railEmpty: '这里还没有内容。',
    startTitle: '从这里开始', startAction: '开始学习', continueAction: '继续',
    railShort: '五分钟左右', railStories: '故事', railVoices: '真实的声音',
    railSay: '说点什么', railWords: '值得记住的词', railMinutes: '分钟',
    newContent: '新上线', newContentEmpty: '暂无新内容',
    direct: '选择练习方向', review: '参考体验建设中 · 你的作品属于你',
  },
};
/* The rail and the room headings follow the support language too. Vietnamese
   merges over English for the same reason the main pack does: a key that has
   no Vietnamese yet still reads. */
referenceCopy.vi = {
  ...referenceCopy.en,
  discover: 'Khám phá',
  practice: 'Luyện tập',
  reading: 'Đọc',
  listening: 'Nghe',
  writing: 'Viết',
  speaking: 'Nói',
  vocabulary: 'Từ vựng',
  understanding: 'Cấu trúc & ý nghĩa',
  language: 'Ngôn ngữ của tôi',
  recall: 'Ôn lại',
  continue: 'Tiếp tục',
  content: 'Nội dung của tôi',
  admin: 'Quản trị nền tảng',
  world: 'Một thế giới rộng hơn',
  make: 'Theo cách của bạn',
  keep: 'Những gì bạn giữ lại',
  destinations: 'Các điểm đến',
  closeDestinations: 'Đóng danh sách',
  home: 'Trang chủ',
  library: 'Thư viện',
  progress: 'Tiến độ',
  profile: 'Hồ sơ',
  you: 'Bạn',
  dictation: 'Chính tả',
  settings: 'Cài đặt',
  allPractice: 'Tất cả bài luyện',
  allDestinations: 'Mọi nơi trong Orena',
  mainNavigation: 'Chính',
  practiceNavigation: 'Luyện tập',
  languagePair: 'Đang học {learning}, giải thích bằng {support}',
  progressWindow: 'Khoảng thời gian',
  progressWindow_7d: '7 ngày',
  progressWindow_30d: '30 ngày',
  progressWindow_90d: '90 ngày',
  progressWindow_all: 'Toàn bộ',
  fieldNote: 'Đi theo tò mò của bạn',
  continueLearning: 'Tiếp tục học',
  continueAction: 'Tiếp tục',
  startTitle: 'Bắt đầu ở đây',
  startAction: 'Bắt đầu học',
  collectionViewAll: 'Xem tất cả',
  railPrevious: 'Trước',
  railNext: 'Sau',
  railEmpty: 'Chưa có gì ở đây.',
  railShort: 'Khoảng năm phút',
  railStories: 'Câu chuyện',
  railVoices: 'Những giọng nói đời thường',
  railSay: 'Điều muốn nói',
  railWords: 'Từ đáng giữ lại',
  railMinutes: 'phút',
  continueEmpty: 'Lần tới bạn sẽ bắt đầu từ đây.',
  browseAll: 'Mọi lối vào',
  direct: 'Chọn một hướng luyện tập',
  collection: 'Bộ sưu tập',
  collectionTitle: 'Một thế giới mang\ndấu tay của bạn.',
  collectionNote:
    'Những thứ bạn mang vào và chọn giữ lại. Sẵn sàng để xem lại một lần nữa.',
  collectionSearch: 'Tìm thứ bạn đã giữ',
  collectionSearchHint: 'Tìm trong mọi thứ bạn đã gặp hoặc đã giữ',
  collectionLenses: 'Bạn gặp nó theo cách nào',
  collectionResults: 'ở đây',
  collectionThreads: 'Nơi bạn đang dở',
  collectionYourContent: 'Thứ bạn mang vào',
  collectionYourLanguage: 'Ngôn ngữ bạn giữ lại',
  collectionEmpty: 'Chưa có gì ở đây.',
  collectionEmptyNote:
    'Những gì bạn đọc, nghe, giữ lại và viết ra sẽ tụ về đây.',
  lens_all: 'Tất cả',
  lens_reading: 'Đã đọc',
  lens_listening: 'Đã nghe',
  lens_speaking: 'Đã nói',
  lens_writing: 'Đã viết',
  lens_language: 'Ngôn ngữ',
  threadLabel: 'Một mạch đang dở',
  contentLabel: 'Của bạn',
  languageLabel: 'Đã giữ',
  moreStories: 'Còn nữa để đọc',
  invitation: 'Một chút tò mò.\nMột thế giới rộng hơn.',
  welcome: 'Đến vì một câu chuyện. Ở lại vì những gì nó mở ra.',
  note:
    'Lắng nghe thật kỹ. Đi lang thang trong một câu chuyện. Tìm ra điều bạn muốn nói.',
  featured: 'Qua một ô cửa khác',
  readNext: 'Giữa những dòng chữ',
  practiceTitle: 'Một khoảnh khắc nhỏ.\nThêm một chút là của bạn.',
  practiceNote:
    'Chọn một ý định. Làm việc với một giọng nói thật, một đoạn văn, hoặc một suy nghĩ của riêng bạn.',
  listenTitle: 'Thế giới có điều\nmuốn nói với bạn.',
  listenNote:
    'Đi theo một giọng nói với tốc độ của bạn. Ở lại với ý nghĩa, hoặc bước vào bên trong một câu.',
  goRead: 'Tìm một câu chuyện',
  goListen: 'Đi theo một giọng nói',
  goSpeak: 'Bắt đầu một cuộc trao đổi',
  studio: 'Dành chỗ cho lời của chính bạn',
  studioNote: 'Điều bạn nghe được có thể thành điều bạn nói ra.',
  writingInvite: 'Một suy nghĩ đáng được viết thành lời.',
  writingDetail:
    'Một tin nhắn, một câu chuyện, một góc nhìn khác. Hãy bắt đầu từ điều bạn muốn nói.',
  practiceInvite: 'Ở lại với một khoảnh khắc nhỏ.',
  practiceDetail:
    'Bắt lấy từng chữ. Mượn lấy nhịp điệu. Thử lại với một chút hiểu biết hơn.',
  continueTitle: 'Có một mạch đang\nchờ bạn quay lại.',
  continueNote:
    'Những câu chuyện bạn bước vào và những chữ bạn đang gọt giũa đều để lại một lối về. Các mạch này ở lại trên thiết bị này.',
  newContent: 'Nội dung mới',
  newContentEmpty: 'Chưa có gì mới',
  review: 'Phần tham chiếu đang hoàn thiện · bài của bạn vẫn là của bạn',
};

const paths = [
  ['discover', 'discover', null, 'compass'], ['continue', 'continue', null, 'return'],
  ['reading', 'practice', 'reading', 'book'], ['listening', 'practice', 'follow', 'sound'],
  ['practice', 'practice', null, 'focus'], ['writing', 'expression', null, 'pen'],
  ['speaking', 'practice', 'speaking', 'voice'], ['understanding', 'practice', 'grammar', 'spark'],
  ['content', 'content', null, 'folder'], ['language', 'language', null, 'leaf'],
  ['recall', 'practice', 'recall', 'return'],
];
export function entryPoints(ui) {
  const c = referenceCopy[ui] || referenceCopy.en;
  return paths.map(([id, page, intent, icon]) => ({ id, label: c[id], href: link(page, { intent }), icon }));
}
export function experienceFor(location) {
  const { page, intent, id = '' } = location;
  if (intent === 'recall') return 'recall';
  if (page === 'conversation' || (page === 'practice' && intent === 'speaking')) return 'speaking';
  if (page === 'expression') return 'writing';
  if (page === 'practice' && intent === 'grammar') return 'understanding';
  if (['dictation','shadowing','speaking'].includes(intent) && page === 'encounter') return 'practice';
  /* Which room an encounter belongs to.

     The id prefix is the usual answer, but it cannot be the only one: a route
     the product cannot classify used to fall to Reading, so a malformed media
     link took a learner who had asked to listen into the Reading room, rail
     highlight and error state included. The learner's stated intention decides
     when the id cannot, and only then - a `media:` id is Listening whatever
     the intent says, because the content is what it is. */
  if (page === 'encounter') {
    if (/^(media:|url:|upload:)/.test(id)) return 'listening';
    if (id) return 'reading';
    return intent === 'follow' ? 'listening' : 'reading';
  }
  if (page === 'practice' && intent === 'reading') return 'reading';
  if (page === 'practice' && intent === 'follow') return 'listening';
  return page === 'preferences' ? 'discover' : page;
}
/* The shell's destinations (D-059, Design Contract rule 38).

   Five places a learner goes - Home, Library, Vocabulary, Progress, Profile -
   and a Practice group of the rooms where they do the work. Nothing that
   existed before is dropped to fit that shape: Continue sits under Home and
   Recall under Vocabulary, every earlier hash keeps its meaning, and the
   Practice heading itself still opens the full practice map.

   `current` is derived from the same `experienceFor` the rooms use, so the
   rail, the tab bar and the room can never disagree about where the learner
   is. */
const DESTINATIONS = [
  { id: 'discover', page: 'discover', icon: 'house', label: 'home', sub: ['continue'] },
  { id: 'content', page: 'content', icon: 'books', label: 'library' },
  { id: 'language', page: 'language', icon: 'cards', label: 'vocabulary', sub: ['recall'] },
  { id: 'progress', page: 'progress', icon: 'chart-line-up', label: 'progress' },
];
const SUBS = {
  continue: { page: 'continue', icon: 'clock-counter-clockwise', label: 'continue' },
  recall: { page: 'practice', intent: 'recall', icon: 'arrow-counter-clockwise', label: 'recall' },
};
const PRACTICE = [
  { id: 'reading', page: 'practice', intent: 'reading', icon: 'book-open', domain: 'reading' },
  { id: 'listening', page: 'practice', intent: 'follow', icon: 'headphones', domain: 'listening' },
  { id: 'speaking', page: 'practice', intent: 'speaking', icon: 'microphone', domain: 'speaking' },
  { id: 'dictation', page: 'practice', intent: 'dictation', icon: 'keyboard', domain: 'dictation' },
  { id: 'writing', page: 'expression', icon: 'pencil-simple', domain: 'writing' },
  { id: 'understanding', page: 'practice', intent: 'grammar', icon: 'sparkle', domain: 'neutral' },
];
/* The phone's tab bar. Each tab owns the rooms it leads to, so the one that
   lights up is the way back to where the learner is. */
const TABS = [
  { id: 'discover', icon: 'house', label: 'home', owns: ['discover', 'continue', 'practice', 'speaking', 'dictation', 'writing', 'understanding'] },
  { id: 'content', icon: 'books', label: 'library', owns: ['content', 'reading', 'listening', 'collection'] },
  { id: 'language', icon: 'cards', label: 'vocabulary', owns: ['language', 'recall'] },
  { id: 'progress', icon: 'chart-line-up', label: 'progress', owns: ['progress'] },
];

/* Which navigation entry the learner is in. Practice over media - dictation,
   shadowing - is its own entry where one exists and the Practice map where
   it does not. */
export function navigationCurrent(location) {
  const experience = experienceFor(location);
  if (experience === 'practice')
    return location.intent === 'dictation' ? 'dictation' : location.intent === 'shadowing' ? 'listening' : 'practice';
  return experience;
}
export function navigationEntries(ui) {
  const c = referenceCopy[ui] || referenceCopy.en;
  const main = DESTINATIONS.map((x) => ({
    ...x,
    label: c[x.label],
    href: link(x.page),
    sub: (x.sub || []).map((id) => ({ id, ...SUBS[id], label: c[SUBS[id].label], href: link(SUBS[id].page, { intent: SUBS[id].intent }) })),
  }));
  const practice = PRACTICE.map((x) => ({ ...x, label: c[x.id], href: link(x.page, { intent: x.intent }) }));
  return { main, practice, practiceHref: link('practice') };
}
const current = (on) => (on ? ' aria-current="page"' : '');
function navLink(entry, here, { domain = '' } = {}) {
  const on = here === entry.id;
  const glyph = domain
    ? `<span class="nav-tile" data-domain="${domain}">${icon(entry.icon, { filled: on, size: 18 })}</span>`
    : icon(entry.icon, { filled: on, size: 20 });
  return `<a class="nav-link" href="${entry.href}"${current(on)} data-nav="${entry.id}">${glyph}<span class="nav-label">${esc(entry.label)}</span></a>`;
}
export function referenceNavigation(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const here = navigationCurrent(ctx.location);
  const { main, practice, practiceHref } = navigationEntries(ctx.ui);
  const hasThread = Boolean(ctx.memory?.value?.continuation?.length);
  const mainLinks = main
    .map((entry) => {
      const subs = entry.sub
        .map((sub) => {
          const on = here === sub.id;
          const dot = sub.id === 'continue' && hasThread ? '<i class="nav-dot" aria-hidden="true"></i>' : '';
          return `<a class="nav-link nav-link--sub" href="${sub.href}"${current(on)} data-nav="${sub.id}">${icon(sub.icon, { filled: on, size: 16 })}<span class="nav-label">${esc(sub.label)}</span>${dot}</a>`;
        })
        .join('');
      return navLink(entry, here) + subs;
    })
    .join('');
  const practiceLinks = practice.map((entry) => navLink(entry, here, { domain: entry.domain })).join('');
  const adminEntry =
    ctx.user?.is_admin === true
      ? `<div class="nav-group nav-group--admin"><a class="nav-link" href="${link('admin')}"${current(here === 'admin')} data-nav="admin">${icon('gear-six', { filled: here === 'admin', size: 20 })}<span class="nav-label">${esc(c.admin)}</span></a></div>`
      : '';
  return `<nav id="shellNav" aria-label="Orena"><div class="nav-sheet-head"><strong>${esc(c.allDestinations)}</strong><button class="nav-close" type="button" data-nav-close aria-label="${esc(c.closeDestinations)}">${icon('x', { size: 20 })}</button></div><div class="nav-group nav-group--main" role="group" aria-label="${esc(c.mainNavigation)}">${mainLinks}</div><div class="nav-group nav-group--practice" role="group" aria-labelledby="navPractice"><a class="nav-heading" id="navPractice" href="${practiceHref}"${current(here === 'practice')} data-nav="practice"><span>${esc(c.practiceNavigation)}</span><span class="sr-only">, ${esc(c.allPractice)}</span></a>${practiceLinks}</div>${adminEntry}</nav>`;
}

/* The phone's destinations: four tabs and the learner's own. "You" opens the
   profile and settings sheet, so it is a button, not a link. */
export function navigationTabs(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const here = navigationCurrent(ctx.location);
  const tabs = TABS.map((tab) => {
    const on = tab.owns.includes(here);
    const href = tab.id === 'discover' ? link() : link(tab.id);
    return `<a class="shell-tab" href="${href}"${current(on)}>${icon(tab.icon, { filled: on, size: 24 })}<span>${esc(c[tab.label])}</span></a>`;
  }).join('');
  return `<nav class="shell-tabs" aria-label="${esc(c.mainNavigation)}">${tabs}<button class="shell-tab" type="button" data-preference>${icon('user-circle', { size: 24 })}<span>${esc(c.you)}</span></button></nav>`;
}

/* Everything else, on a phone, is one control away: the whole map above,
   as a sheet. */
export function navigationToggle(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<button class="nav-toggle" data-nav-toggle type="button" aria-expanded="false" aria-controls="shellNav" aria-label="${esc(c.allDestinations)}">${icon('squares-four', { size: 22 })}</button>`;
}

/* "EN → VI": what is being learned, and the language Orena explains it in.
   The learning language keeps its own writing system where it has one. */
const LEARNING_MARK = { zh: '中文', en: 'EN' };
export function languagePair(ctx) {
  const learning = LEARNING_MARK[ctx.language] || String(ctx.language || '').toUpperCase();
  const support = String(ctx.support || ctx.ui || '').toUpperCase();
  return { learning, support, text: `${learning} → ${support}` };
}
export function languageChip(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const pair = languagePair(ctx);
  const label = c.languagePair.replace('{learning}', pair.learning).replace('{support}', pair.support);
  return `<button class="language-chip" type="button" data-preference aria-label="${esc(label)}">${icon('translate', { size: 16 })}<span>${esc(pair.text)}</span></button>`;
}

/* The learner, at the foot of the rail: who they are, what they are learning,
   and the way into settings. Only what the account actually says is shown. */
export function accountCard(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const user = ctx.user || {};
  const name = String(user.name || user.display_name || (user.email ? user.email.split('@')[0] : '') || c.you);
  const initial = Array.from(name.trim())[0]?.toUpperCase() || '·';
  return `<button class="account-card" type="button" data-preference aria-label="${esc(`${c.profile} · ${c.settings}`)}"><span class="account-avatar" aria-hidden="true">${esc(initial)}</span><span class="account-text"><strong>${esc(name)}</strong><small>${esc(languagePair(ctx).text)}</small></span>${icon('gear-six', { size: 18, className: 'account-gear' })}</button>`;
}
export function editorialIntro(ctx, {title, note, state, eyebrow}) {
  return `<header class="editorial-intro"><div><small>${esc(eyebrow || referenceCopy[ctx.ui].fieldNote)}</small><h1>${esc(title).replaceAll('\n','<br>')}</h1><p>${esc(note)}</p></div>${scene(state,{size:'hero'})}</header>`;
}
/* The room whose whole subject is coming back.

   It used to be the same shelf Discover carries, rendered longer: a row of
   white cards each holding a word and a title, which is a list of unfinished
   database rows rather than continuity. What a learner needs here is where
   they are - the thing itself, what it belongs to, how far through they got,
   and one way back in.

   Nothing here is invented. The cover is drawn from the item's own identity,
   the place is printed only when the entry actually carries one, and the shelf
   still decides what can be resumed: a thread whose work is gone is not
   offered, and a device that cannot remember says so.
   `continuationEntries` is that decision; this room asks it. */
const continuationIcons = {
  listening: 'sound',
  reading: 'book',
  speaking: 'voice',
  writing: 'pen',
  understanding: 'spark',
  practice: 'focus',
  recall: 'return',
};

function continueLabel(item, ctx) {
  const experience = continuationExperience(item);
  return experience === 'listening'
    ? ctx.c.followName
    : ctx.c[`${experience}Name`] || ctx.c.resume;
}

function progressBar(place, label) {
  if (!place) return '';
  return `<span class="continue-progress" role="img" aria-label="${esc(label)}"><span class="continue-progress__bar"><span style="width:${place.percent}%"></span></span><small>${place.percent}%</small></span>`;
}

/* The one the learner was last in, given the room to be recognised. */
function continueLead(item, ctx) {
  const c = referenceCopy[ctx.ui];
  const place = continuationPlace(item);
  const progressLabel = place ? `${place.percent}% · ${item.context || item.title}` : '';
  return `<section class="continue-lead"><span class="continue-lead__visual" aria-hidden="true">${art(item)}</span><div class="continue-lead__body"><small>${entryIcon(continuationIcons[continuationExperience(item)] || 'return')}${esc(continueLabel(item, ctx))}</small><h2 lang="${esc(ctx.language)}">${esc(item.title)}</h2>${item.context ? `<p class="continue-lead__context" lang="${esc(ctx.language)}">${esc(item.context)}${place ? ` · ${place.index}/${place.total}` : ''}</p>` : ''}${progressBar(place, progressLabel)}<a class="primary" href="${esc(continuationLink(item))}">${esc(c.continueAction)} <span aria-hidden="true">→</span></a></div></section>`;
}

function continueCard(item, ctx) {
  const place = continuationPlace(item);
  const where = item.context || '';
  return `<a class="continue-card" href="${esc(continuationLink(item))}"><span class="continue-card__visual" aria-hidden="true">${art(item)}</span><span class="continue-card__body"><small>${entryIcon(continuationIcons[continuationExperience(item)] || 'return')}${esc(continueLabel(item, ctx))}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${where ? `<span class="continue-card__context" lang="${esc(ctx.language)}">${esc(where)}${place ? ` · ${place.index}/${place.total}` : ''}</span>` : ''}${progressBar(place, place ? `${place.percent}%` : '')}</span></a>`;
}

export function renderContinue(root, ctx) {
  const c = referenceCopy[ctx.ui];
  const threads = continuationEntries(ctx.memory);
  const [lead, ...rest] = threads;
  const body = lead
    ? `${continueLead(lead, ctx)}${rest.length ? `<section class="continue-more" aria-label="${esc(c.continueLearning)}"><div class="section-head"><h2>${esc(c.continueLearning)}</h2>${hint({ text: ctx.c.deviceThreads })}</div><div class="continue-grid">${rest.map((item) => continueCard(item, ctx)).join('')}</div></section>` : ''}`
    : `<section class="continue-empty">${scene('empty', { size: 'medium' })}<div><h2>${esc(c.continueEmpty)}</h2><a class="primary" href="${link()}">${esc(c.startAction)} <span aria-hidden="true">→</span></a></div></section>`;
  root.innerHTML = `${pageIntro({ title: c.continue, compact: true })}${ctx.memory.available ? '' : `<p class="notice">${esc(ctx.c.memoryUnavailable)}</p>`}${body}`;
}
