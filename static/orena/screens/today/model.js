/* Today (T1, frame 10-Today.html): pure data mapping, no DOM. screen.js fetches from the real
   services and hands their raw payloads here; every function below is a deterministic projection
   of that data, so scripts/test_orena_screen_today.mjs can prove the mapping and the rule-40
   zero-fallbacks without a browser.

   Design Contract rule 40: the goal ring, the streak and the level/XP card have no cross-activity
   backend (C2 audit - only a Writing-only streak on /api/dashboard, which this screen must not
   reuse as a daily streak). Their builders below always return the zero/"not tracked" shape; the
   gap is recorded in docs/project/UI_BACKEND_GAPS.md and in SCRATCH/reports/today.md, not resolved
   by inventing a number. */

import { tidyTitle } from '../../product/tidy-title.js';
import { placePercent } from '../../product/place-progress.js';
import { speakingResumeTarget } from '../../product/speaking-resume.js';

export const RECOMMEND_LIMIT = 3;
export const FOR_YOU_LIMIT = 12;

/* --- duration -------------------------------------------------------- */

/* The same locale-invariant "M:SS" clock format the design's media/duration pill uses everywhere
   else it appears in this build (Discover's own model.js, and product/duration.js, moved from the
   old UI for exactly this pill) - never words, and empty when the source gives no duration at all
   (rule 40 for a text field: an unmeasured value renders nothing, never an invented figure). */
export function formatDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return '';
  const totalSeconds = Math.round(n / 1000);
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`;
}

/* --- meaning / language ------------------------------------------------ */

/* The catalogue meaning in the learner's support language, else English, else whatever the entry
   carries first. Never a guess at a language the entry does not have. */
export function pickMeaning(meanings, supportLang) {
  const list = Array.isArray(meanings) ? meanings : [];
  const match = list.find((m) => m && m.language === supportLang) || list.find((m) => m && m.language === 'en') || list[0];
  return match ? String(match.text || '') : '';
}

/* --- recommendation pool ("Recommended for today") --------------------- */

/* One candidate per real source: the learner's real due-vocabulary-review queue first (when
   anything is actually due - GET /api/library/review-queue, the same source My Library's own
   Due-Review tab already reads), then Reading's selection policy, then the top Listening item,
   then the top Speaking item. Review leads the pool - not just competes at the end of it -
   because a due SRS interval is time-sensitive in a way a catalogue pick never is: docs/design/
   canonical-ui/brief/ORENA_DESIGN_SPEC.md §7 section B gives a review-based suggestion as a
   canonical "Recommended for today" example, and the pinned design's own live state machine
   (SCRATCH/design-full/orena-script.js, `todayRecs`) renders exactly this section with a Review
   card whenever the mock queue is non-empty. A source with nothing available (no due reviews, no
   published article in this environment, an empty catalogue) simply contributes nothing - the
   pool is shorter, never padded with an invented kind. */
export function buildRecommendationPool({ reading, listening = [], speaking = [], review = null, language = '' }, t) {
  const pool = [];
  const dueCount = Number(review?.due_count) || 0;
  const dueWord = String(review?.first_due_word || '').trim();
  if (dueCount > 0 && dueWord) {
    pool.push({
      source: 'review',
      id: `review:${dueWord}`,
      kind: t('kindReview'),
      title: dueWord,
      // languages-5 / finding A: a real vocabulary word, not a catalogue title - the due-review
      // queue (GET /api/library/review-queue) answers for the learner's one active learning
      // language, so that language (already read by screen.js from ctx.context) is the word's own,
      // never a script guess (kit/lang.js's own doc comment on why this build never sniffs script).
      lang: language,
      level: '',
      durationLabel: '',
      image: '',
      tint: 'var(--skill-vocab)',
      icon: 'whole-word',
      routeId: 'review',
      routeParams: {},
      routeQuery: {},
      // A real "why this" string (rule 40 could not populate one for any other source - see
      // screen.js's report): the due-review queue's own count, phrased the way My Library's
      // Due-Review tab already phrases the same figure.
      reason: t.plural('reviewReason', dueCount),
    });
  }
  const article = reading?.available ? reading.next?.set?.article : null;
  if (article?.id) {
    pool.push({
      source: 'reading',
      id: article.id,
      kind: t('kindRead'),
      title: article.title || '',
      level: article.level || '',
      durationLabel: '',
      image: '',
      tint: 'var(--skill-read)',
      icon: 'book-open',
      routeId: 'reader',
      routeParams: { id: article.id },
      routeQuery: reading.next.recommendation ? { rec: reading.next.recommendation } : {},
    });
  }
  const firstListening = listening.find((item) => item?.lesson_id);
  if (firstListening) {
    pool.push({
      source: 'listening',
      id: firstListening.lesson_id,
      kind: t('kindListen'),
      title: firstListening.title || '',
      level: firstListening.level || '',
      durationLabel: formatDuration(firstListening.duration_ms),
      image: firstListening.thumbnail_url || firstListening.poster_url || '',
      tint: 'var(--skill-listen)',
      icon: 'headphones',
      routeId: 'listening',
      routeParams: { id: firstListening.lesson_id },
      routeQuery: {},
    });
  }
  const firstSpeaking = speaking.find((item) => item?.id);
  if (firstSpeaking) {
    pool.push({
      source: 'speaking',
      id: firstSpeaking.id,
      kind: t('kindSpeak'),
      title: firstSpeaking.title || '',
      level: firstSpeaking.level || '',
      durationLabel: formatDuration(firstSpeaking.duration_ms),
      image: firstSpeaking.thumbnail_url || '',
      tint: 'var(--skill-speak)',
      icon: 'mic',
      routeId: 'speak',
      routeParams: { id: firstSpeaking.id },
      routeQuery: {},
    });
  }
  return pool.slice(0, RECOMMEND_LIMIT);
}

/* --- continuation (unfinished work, device memory) ---------------------- */

/* A continuation entry the new shell can confidently route: today only the curated-lesson and
   grammar-point shapes, whose id namespace is shared verbatim with the real catalogue endpoints
   this screen already calls. An entry of another kind (a conversation, a piece of writing, a
   speaking situation, a recall session) has no route this screen could build without guessing at
   an id mapping the new shell has not confirmed yet - it is left out rather than risk a broken
   link, and the gap is recorded (SCRATCH/reports/today.md, "unfinished work").

   No `progress` field: the frame's own "For you" rail cards never draw a start-progress strip
   (unlike Discover's/My Library's media cards, which do) - a continuation entry's real
   `place.within` percent is left off the card rather than adding an element rule 43 says Today
   does not draw; the "unfinished work" fact is carried in the card's meta text instead. */
export function mapContinuationEntry(entry, t) {
  const id = String(entry?.id || '');
  /* Where the learner stopped, when it is measured (LEX-090): the same percent every other surface reads. */
  const pct = placePercent(entry?.place);
  /* The card's kind is the skill the learner returns to; "Continue" leads its meta line (design/UX review 2026-10-08:
     five cards all labelled "Continue" told the learner nothing about what each was). */
  const lead = t('kindContinue');
  const where = (context) => {
    const said = String(context || '').toLocaleLowerCase().startsWith(lead.toLocaleLowerCase());
    return [said ? '' : lead, context || '', pct != null && pct < 100 ? t('placePercent', { pct }) : ''].filter(Boolean).join(' · ');
  };
  const speaking = speakingResumeTarget(entry);
  if (speaking) return {
    source:'continue', id, kind:t('kindSpeak'), title:tidyTitle(entry.title || ''),
    meta:where(entry.context), tag:null, durationLabel:'', image:'',
    routeId:speaking.routeId, routeParams:speaking.params, routeQuery:speaking.query,
  };
  if (id.startsWith('media:')) {
    const lessonId = id.slice('media:'.length);
    if (!lessonId) return null;
    const dictation = entry.intent === 'dictation';
    const shadowing = entry.intent === 'shadowing';
    return {
      source: 'continue',
      id,
      kind: t(shadowing ? 'kindSpeak' : 'kindListen'),
      title: tidyTitle(entry.title || ''),
      meta: where(entry.context),
      tag: null,
      durationLabel: '',
      image: '',
      routeId: dictation ? 'dictation' : shadowing ? 'shadow' : 'listening',
      routeParams: { id: lessonId },
      routeQuery: {},
    };
  }
  if (/^(article|book):[^:]+(:[^:]+)?$/.test(id) && !(entry.place?.within >= 100)) {
    return {
      source: 'continue', id, kind: t('kindRead'), title: tidyTitle(entry.title || ''),
      meta: where(entry.context), tag: null, durationLabel: '', image: '',
      routeId: 'reader', routeParams: { id }, routeQuery: {},
    };
  }
  if (/^conversation:[\w-]+$/.test(id)) {
    return {
      source: 'continue',
      id,
      kind: t('kindSpeak'),
      title: tidyTitle(entry.title || ''),
      meta: where(entry.context),
      tag: null,
      durationLabel: '',
      image: '',
      routeId: 'conv',
      routeParams: {},
      routeQuery: { id },
    };
  }
  if (id.startsWith('grammar:')) {
    const conceptId = id.slice('grammar:'.length);
    if (!conceptId) return null;
    return {
      source: 'continue',
      id,
      kind: t('kindGrammar'),
      title: tidyTitle(entry.title || ''),
      meta: where(entry.context),
      tag: null,
      durationLabel: '',
      image: '',
      routeId: 'gconcept',
      routeParams: { id: conceptId },
      routeQuery: {},
    };
  }
  return null;
}

/* --- "For you" rail ----------------------------------------------------- */

/* Everything the recommendation pool did not use: the learner's unfinished work first (most
   recent continuation entries, device memory), then the rest of the real Listening and Speaking
   catalogues, then today's Daily Vocabulary Feed words - never an invented card. */
export function buildForYou({ continuation = [], listening = [], speaking = [], feed = [], usedIds = new Set(), supportLang = 'en', language = '' }, t) {
  const items = [];
  // One destination is one card (LEX-073): an item the learner is continuing is not offered again from the catalogue.
  const seen = new Set();
  const place = (item) => `${item.routeId}:${item.routeParams?.id ?? ''}`;
  const taken = (item) => item.routeParams?.id && seen.has(place(item));
  /* The same title is the same thing even when a continued place and a catalogue row name it by different ids
     ("Make room for someone" twice). */
  const titles = new Set([...usedIds].filter((value) => String(value).startsWith('title:')).map((value) => String(value).slice(6)));
  const titleKey = (item) => String(item?.title || '').trim().toLowerCase();
  const sameTitle = (item) => Boolean(titleKey(item)) && item.source !== 'word' && titles.has(titleKey(item));
  const take = (item) => { if (item.routeParams?.id) seen.add(place(item)); if (titleKey(item) && item.source !== 'word') titles.add(titleKey(item)); items.push(item); };
  for (const entry of continuation) {
    if (items.length >= FOR_YOU_LIMIT) break;
    const mapped = mapContinuationEntry(entry, t);
    if (mapped && !usedIds.has(mapped.id) && !taken(mapped) && !sameTitle(mapped)) take(mapped);
  }
  for (const item of listening) {
    if (items.length >= FOR_YOU_LIMIT) break;
    if (!item?.lesson_id || usedIds.has(item.lesson_id)) continue;
    if (taken({ routeId: 'listening', routeParams: { id: item.lesson_id } }) || sameTitle(item)) continue;
    take({
      source: 'listening',
      id: item.lesson_id,
      kind: t('kindListen'),
      title: item.title || '',
      meta: item.level || '',
      tag: null,
      durationLabel: formatDuration(item.duration_ms),
      image: item.thumbnail_url || item.poster_url || '',
      routeId: 'listening',
      routeParams: { id: item.lesson_id },
      routeQuery: {},
    });
  }
  for (const item of speaking) {
    if (items.length >= FOR_YOU_LIMIT) break;
    if (!item?.id || usedIds.has(item.id)) continue;
    if (taken({ routeId: 'speak', routeParams: { id: item.id } }) || sameTitle(item)) continue;
    take({
      source: 'speaking',
      id: item.id,
      kind: t('kindSpeak'),
      title: item.title || '',
      meta: item.level || '',
      tag: null,
      durationLabel: formatDuration(item.duration_ms),
      image: item.thumbnail_url || '',
      routeId: 'speak',
      routeParams: { id: item.id },
      routeQuery: {},
    });
  }
  for (const word of feed) {
    if (items.length >= FOR_YOU_LIMIT) break;
    const headword = word?.headword || word?.identity?.normalized;
    if (!headword) continue;
    items.push({
      source: 'word',
      id: `word:${headword}`,
      kind: t('kindWord'),
      title: headword,
      // languages-5 / finding A: the Daily Vocabulary Feed (GET /api/vocabulary/daily-feed) is
      // fetched for the same active learning language screen.js already read - real data, not a
      // script guess.
      lang: language,
      meta: pickMeaning(word.meanings, supportLang),
      tag: word.level || null,
      durationLabel: '',
      image: '',
      routeId: 'word',
      routeParams: { id: headword },
      routeQuery: {},
    });
  }
  return items;
}

/* The learner's own unfinished work leads the day (LEX-073): the most recent continuation entry the shell can
   route becomes the first Recommended card - the design's hero, kind "Continue", its context as the reason - and
   is taken out of "For you" by id, so no item appears twice. `cover` is the tile's icon and tint for its route. */
export function leadWithContinuation(pool, continuation, t, coverFor) {
  for (const entry of continuation || []) {
    const mapped = mapContinuationEntry(entry, t);
    if (!mapped) continue;
    const cover = coverFor(mapped) || {};
    const lead = { ...mapped, reason: mapped.meta || '', level: '', tint: cover.tint || 'var(--skill-read)', icon: cover.icon || 'book-open' };
    return [lead, ...pool.filter((item) => item.id !== lead.id && item.routeParams?.id !== lead.routeParams?.id)].slice(0, RECOMMEND_LIMIT);
  }
  return pool;
}

export function usedRecommendationIds(pool) {
  return new Set(pool.flatMap((item) => [item.id, item.routeParams?.id, item.source !== 'word' && item.title ? `title:${String(item.title).trim().toLowerCase()}` : '']).filter(Boolean));
}

/* --- goal ring, streak, level/XP: rule 40 -------------------------------- */

/* Real evidence when the window has any (learner-summary), never invented; "this week" is named
   as what it is, since Orena has no per-day activity read - a day-scoped claim built from a 7-day
   window would misstate the window, which rule 40 forbids as surely as a fabricated number would. */
export function buildGoalSummary({ domains } = {}, t) {
  const entries = Object.entries(domains || {})
    .map(([key, domain]) => ({ key, count: Number(domain?.activity?.count || 0) + Number(domain?.activity?.undated || 0), label: domain?.activity?.label || '' }))
    .filter((entry) => entry.count > 0);
  if (!entries.length) return { pct: 0, label: t('goalLabel'), sub: t('notTrackedYet') };
  const parts = entries.map((entry) => (t.has(`activity_${entry.label}`) ? t.plural(`activity_${entry.label}`, entry.count) : String(entry.count)));
  return { pct: 0, label: t('goalLabel'), sub: t('evidenceThisWeek', { list: parts.join(t('evidenceSeparator')) }) };
}

/* The frame draws each mini-ring's caption as one fused string, "Reading 0%" (label + the same
   percent the ring itself draws) - never just the bare skill name. Digits and "%" need no
   per-language template (identical shape in en/vi/zh), so this stays a plain JS concatenation
   rather than a copy.js placeholder - which sidesteps the copy/index.js `fill()` defect below
   entirely for this value. `name` is kept separately for the ring's `title` tooltip, matching the
   frame's own `title="Reading 0%"` attribute one level up (same fused text, native tooltip). */
export function buildSkillRings(t) {
  return ['reading', 'listening', 'speaking'].map((key) => {
    const name = t(`skill${key[0].toUpperCase()}${key.slice(1)}`);
    const percent = 0;
    return {
      key,
      percent,
      color: `var(--skill-${key === 'reading' ? 'read' : key === 'listening' ? 'listen' : 'speak'})`,
      icon: key === 'reading' ? 'book-open' : key === 'listening' ? 'headphones' : 'mic',
      name,
      label: `${name} ${percent}%`,
    };
  });
}

const WEEK_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

/* The frame bolds and enlarges only the streak *count* inside its sentence ("<b>12</b> day
   streak", 24px/700 against the rest at 15px/400) - never the sentence as one flat string. English
   puts the count first ("{n} day streak"); Vietnamese and Chinese both put a word before it
   ("Chuỗi {n} ngày", "连续 {n} 天"), so the count cannot be isolated by string position. Rather than
   add prefix/suffix copy keys (which would need an empty English "prefix" - scripts/test_orena_
   copy.mjs rejects any blank pack value), the surrounding words are read straight off `dayStreak`'s
   own `{n}` placeholder: splitting the unparametrised translation on the literal token "{n}" gives
   exactly the text either side of where the count goes, in every language, with nothing new to
   translate. `n` is always 0 (rule 40 - no cross-activity streak; the Writing-only one on
   /api/dashboard must not be reused as this one). */
/* The streak is REAL (D4 I14, D-104 H-5): GET /api/learner-activity derives it from server records - an
   essay version, a speaking attempt, a Reading attempt - by the learner's own calendar day; a page visit
   never counts. `activity` is that answer, or null when it could not be read (then there is no streak to
   show, and the card says nothing rather than 0 days). The week strip marks the days the server says
   were active, Monday first. */
export function buildStreak(t, activity = null) {
  const [before, after] = t('dayStreak').split('{n}');
  const week = Array.isArray(activity?.week?.days) ? activity.week.days : [];
  return {
    known: Boolean(activity?.streak),
    n: Math.max(0, Number(activity?.streak?.days) || 0),
    before: before || '',
    after: after || '',
    // The server names today's date and which days have not come yet (learner_activity.py): today is marked
    // and only a day that really had activity is ticked (LEX-073).
    days: WEEK_DAYS.map((key, index) => ({
      key,
      letter: t(`weekday_${key}`),
      done: Boolean(week[index]?.active),
      today: Boolean(week[index]?.date) && week[index].date === activity?.today,
      future: Boolean(week[index]?.future),
    })),
  };
}

export function buildLevel(t) {
  return { badge: '–', name: t('levelLabel'), xp: t('levelXp', { n: 0 }), pct: 0, next: t('notTrackedYet') };
}

/* --- "Fri, Sep 25" -> the real date, never hardcoded -------------------- */

export function todayDateLabel(date, locale) {
  try {
    return new Intl.DateTimeFormat(locale, { weekday: 'short', month: 'short', day: 'numeric' }).format(date);
  } catch {
    return new Intl.DateTimeFormat('en', { weekday: 'short', month: 'short', day: 'numeric' }).format(date);
  }
}

/* --- header: greeting from the device's own real clock -------------------- */

/* Design Contract rule 40: never an invented clock - the caller always hands in its own real
   `new Date()` (screen.js), so this stays a pure, gate-testable projection of the device's local
   time (`Date#getHours()` already reads local, not UTC - exactly "the device's local time").
   Three bands, fixed here so they can be asserted and documented rather than eyeballed:
     05:00-11:59  morning
     12:00-17:59  afternoon
     18:00-04:59  evening
   The frame draws exactly three greeting states (Good morning/afternoon/evening - never a fourth
   "good night" one), so the evening band absorbs the remaining night hours rather than inventing
   a state the source does not draw. */
export function greetingPeriod(hour) {
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 18) return 'afternoon';
  return 'evening';
}

export function buildGreeting(date, t) {
  const period = greetingPeriod(date.getHours());
  return t(`greeting${period.charAt(0).toUpperCase()}${period.slice(1)}`);
}

/* --- header: the subtitle, from the real state of the page below it ------- */

/* Rule 40: the frame's fixed "Two things worth doing today, then something to enjoy." is sample
   content (D-068), never data. The real referents already exist on this same page - the size of
   the "Recommended for today" pool this render actually built, and whether the "For you" rail
   below it holds anything - so the sentence is built from those two counts instead. Nothing
   recommended at all is an honest silence (no line), never a fabricated one; the "then something
   to enjoy" clause is added only when the For-you rail genuinely has something for it to name. */
export function buildHeadSubtitle({ recommendedCount = 0, forYouCount = 0 } = {}, t) {
  if (!recommendedCount) return '';
  return t.plural(forYouCount > 0 ? 'subtitleBoth' : 'subtitleOnly', recommendedCount);
}

/* The level prompt (D-105 H-19): a profile that exists for this learning language and declares no
   level. A missing profile is Welcome's business (entryRoute), and an unreadable one (null) is not
   "no level". Skipping it is per visit: a stored "dismissed" marker would be a persistence decision
   nobody has made, so nothing is written to the account. */
export function needsLevelPrompt(profile) {
  return Boolean(profile && profile.exists === true && !String(profile.declared_level || '').trim());
}
