// Experience identity is presentation over the existing routes, never another
// capability engine. New surfaces join this map and inherit the same shell.
import { link } from '../product/intent.js';
import { esc } from './html.js';
import { scene } from './brand.js';
import { continuationEntries, continuationPlace, hint, pageIntro } from './patterns.js';
import { entryIcon } from './icons.js';
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
export function referenceNavigation(ctx) {
  const c = referenceCopy[ctx.ui], active = experienceFor(ctx.location), entries = entryPoints(ctx.ui);
  const group = (label, ids) => `<div class="nav-group"><small>${esc(label)}</small>${entries.filter(x=>ids.includes(x.id)).map(x=>`<a href="${x.href}" ${active === x.id ? 'aria-current="page"' : ''}>${entryIcon(x.icon)}<span>${esc(x.label)}</span>${x.id==='continue' && ctx.memory.value.continuation.length ? '<i aria-hidden="true"></i>' : ''}</a>`).join('')}</div>`;
  const adminEntry = ctx.user?.is_admin === true ? `<div class="nav-group nav-group--admin"><small>${esc(c.admin)}</small><a href="${link('admin')}" ${active === 'admin' ? 'aria-current="page"' : ''}>${entryIcon('spark')}<span>${esc(c.admin)}</span></a></div>` : '';
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
