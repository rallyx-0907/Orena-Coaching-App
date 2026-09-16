// Experience identity is presentation over the existing routes, never another
// capability engine. New surfaces join this map and inherit the same shell.
import { link } from '../product/intent.js';
import { esc } from './html.js';
import { scene } from './brand.js';
import { continuationShelf, pageIntro } from './patterns.js';

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
    writing: 'Writing', speaking: 'Speaking', understanding: 'Patterns & meaning',
    language: 'My language', recall: 'Recall', continue: 'Continue', content: 'My content', admin: 'Platform Admin',
    world: 'A bigger world', make: 'Make it yours', keep: 'Your growing world',
    destinations: 'Destinations', closeDestinations: 'Close destinations',
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
    browseAll: 'All the ways in', fieldNote: 'Follow your curiosity',
    startHere: 'Start here', startNote: 'See the ways to learn in Orena.',
    goReadNote: 'Read in context', goListenNote: 'Follow a voice', goSpeakNote: 'Start speaking',
    practiceShort: 'Try a focused activity', writingShort: 'Put it into words',
    vocabularyShort: 'Browse words and review', continueShort: 'Pick up where you left off',
    discoverMore: 'Explore more',
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
    speaking: '表达', understanding: '句式与含义', language: '我的语言', recall: '回想',
    continue: '继续', content: '我的内容', world: '走进更大的世界', make: '用自己的方式表达', keep: '慢慢积累的世界',
    destinations: '去处', closeDestinations: '收起去处',
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
    browseAll: '每一种开始', fieldNote: '跟着好奇心走',
    startHere: '从这里开始', startNote: '看看在 Orena 里可以怎样学习。',
    goReadNote: '在语境中阅读', goListenNote: '跟随一种声音', goSpeakNote: '开始表达',
    practiceShort: '做一个专注练习', writingShort: '把想法写下来',
    vocabularyShort: '浏览词汇并复习', continueShort: '从上次停下的地方继续',
    discoverMore: '查看更多',
    direct: '选择练习方向', review: '参考体验建设中 · 你的作品属于你',
  },
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
  if (page === 'encounter') return /^(media:|url:)/.test(id) ? 'listening' : 'reading';
  if (page === 'practice' && intent === 'reading') return 'reading';
  if (page === 'practice' && intent === 'follow') return 'listening';
  return page === 'preferences' ? 'discover' : page;
}
const strokes = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5Z"/>',
  return: '<path d="M4 10a8 8 0 1 1 2 8M4 4v6h6M12 7v5l3 2"/>',
  book: '<path d="M12 5v15M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Z"/>',
  sound: '<path d="M3 10v4m4-8v12m5-16v20m5-17v14m4-9v4"/>',
  focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/>',
  pen: '<path d="m4 16 12-12 4 4L8 20H4Zm9-9 4 4M3 23h18"/>',
  voice: '<path d="M8 14h-3V3h16v11h-8l-5 4ZM3 9H1v13h12v-4"/>',
  spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z"/>',
  folder: '<path d="M2 6V3h7l3 3h10v15H2Z"/>',
  leaf: '<path d="M4 20C-2 6 10 4 21 3c-1 12-4 19-17 17Zm0 0L16 8"/>',
};
export function entryIcon(name) {
  return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${strokes[name] || strokes.compass}</svg>`;
}
export function referenceNavigation(ctx) {
  const c = referenceCopy[ctx.ui], active = experienceFor(ctx.location), entries = entryPoints(ctx.ui);
  const group = (label, ids) => `<div class="nav-group"><small>${esc(label)}</small>${entries.filter(x=>ids.includes(x.id)).map(x=>`<a href="${x.href}" ${active === x.id ? 'aria-current="page"' : ''}>${entryIcon(x.icon)}<span>${esc(x.label)}</span>${x.id==='continue' && ctx.memory.value.continuation.length ? '<i aria-hidden="true"></i>' : ''}</a>`).join('')}</div>`;
  const adminEntry = ctx.user?.is_admin === true ? `<div class="nav-group"><small>${esc(c.admin)}</small><a href="${link('admin')}" ${active === 'admin' ? 'aria-current="page"' : ''}>${entryIcon('spark')}<span>${esc(c.admin)}</span></a></div>` : '';
  return `<nav id="shellNav" aria-label="Orena">${group(c.world,['discover','continue','reading','listening'])}${group(c.make,['practice','writing','speaking','understanding'])}${group(c.keep,['content','language','recall'])}${adminEntry}</nav>`;
}

/* How the eleven destinations are reached on a narrow screen.

   The rail becomes a header there, and the whole list used to be laid out
   across it: three groups wrapping onto three lines, each line wider than the
   phone, so the header ate 228px of an 844px screen and Listening, Patterns &
   meaning and Recall sat off the right edge where nothing could reach them.

   So the list moves behind one control - and that control names where the
   learner currently is, rather than being an anonymous hamburger. Closed, it
   still answers "where am I"; open, it shows every destination with its group
   heading, which the flattened strip had dropped. Desktop never sees it: the
   rail is unchanged and this button is not rendered there. */
export function navigationToggle(ctx) {
  const c = referenceCopy[ctx.ui];
  const active = experienceFor(ctx.location);
  const here = active === 'admin' && ctx.user?.is_admin === true
    ? { id: 'admin', label: c.admin, icon: 'spark' }
    : entryPoints(ctx.ui).find((x) => x.id === active);
  return `<button class="nav-toggle" data-nav-toggle type="button" aria-expanded="false" aria-controls="shellNav">${entryIcon(here?.icon || 'compass')}<span class="nav-toggle-here">${esc(here?.label || c.destinations)}</span><span class="sr-only">, ${esc(c.destinations)}</span><svg class="nav-toggle-caret" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>`;
}
export function editorialIntro(ctx, {title, note, state, eyebrow}) {
  return `<header class="editorial-intro"><div><small>${esc(eyebrow || referenceCopy[ctx.ui].fieldNote)}</small><h1>${esc(title).replaceAll('\n','<br>')}</h1><p>${esc(note)}</p></div>${scene(state,{size:'hero'})}</header>`;
}
/* The room whose whole subject is coming back.

   It asked the store how many threads it held and trusted the answer, which
   was wrong twice: a device that cannot remember reported nothing to continue
   rather than saying it had lost the ability to, and threads the shelf now
   declines to offer still counted, leaving the room empty under a heading
   promising otherwise. The shelf decides what can be resumed; this asks it. */
export function renderContinue(root, ctx) {
  const c = referenceCopy[ctx.ui];
  const threads = continuationShelf(ctx, ctx.memory.value.continuation.length);
  root.innerHTML = `${editorialIntro(ctx,{title:c.continueTitle,note:c.continueNote,state:'returning',eyebrow:c.continue})}${ctx.memory.available ? '' : `<p class="notice">${esc(ctx.c.memoryUnavailable)}</p>`}${threads || `<section class="continue-empty"><h2>${esc(c.continueEmpty)}</h2><a class="primary" href="${link()}">${esc(c.discover)} →</a></section>`}`;
}
