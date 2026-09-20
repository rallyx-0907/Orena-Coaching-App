import { esc } from './html.js';
import { icon } from './phosphor.js';

const LEVEL_SKINS = {
  A1: 'bronze',
  A2: 'silver',
  B1: 'gold',
  B2: 'platinum',
  C1: 'violet',
  C2: 'aurora',
  HSK1: 'bronze',
  HSK2: 'silver',
  HSK3: 'gold',
  HSK4: 'platinum',
  HSK5: 'violet',
  HSK6: 'aurora',
  'HSK7-9': 'aurora',
};

/* A level is the framework's own name for where a word sits; a rank is the
   material that level is cut from. `639b03d` replaced the rank letter with the
   real proficiency level and dropped the letter entirely, so every card since
   has carried the same neutral edge. The level stays authoritative - the rank
   rides with it rather than standing in for it. */
const LEVEL_RANKS = {
  A1: 'D',
  A2: 'C',
  B1: 'B',
  B2: 'A',
  C1: 'S',
  C2: 'S+',
  HSK1: 'D',
  HSK2: 'C',
  HSK3: 'B',
  HSK4: 'A',
  HSK5: 'S',
  HSK6: 'S+',
  'HSK7-9': 'S+',
};

function value(input) {
  return String(input || '').trim();
}

function rawVocabularyLevel(input = {}) {
  return value(input && typeof input === 'object' ? input.level : input);
}

export function vocabularyLevel(input = {}) {
  const raw = rawVocabularyLevel(input);
  const normalized = raw.toUpperCase().replace(/[–—]/g, '-').replace(/\s+/g, '');
  return LEVEL_SKINS[normalized] ? normalized : '';
}

export function vocabularyLevelSkin(input = {}) {
  return LEVEL_SKINS[vocabularyLevel(input)] || 'neutral';
}

export function vocabularyRank(input = {}) {
  return LEVEL_RANKS[vocabularyLevel(input)] || '';
}

export function vocabularyRankToken(copy, input = {}) {
  const rank = vocabularyRank(input);
  if (!rank) return '';
  const label = value(copy?.vocabularyRank) || 'Rank';
  return `<span class="vocabulary-rank" aria-label="${esc(`${label} ${rank}`)}">${esc(rank)}</span>`;
}

/* Mastery, as the design draws it: three stars, amber for what was earned.
   The text form stays the accessible name, so nothing depends on the glyphs. */
export function masteryStarRow(card = {}) {
  const earned = (masteryStars(card).match(/★/g) || []).length;
  return `<span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${[0, 1, 2]
    .map((step) => `<span${step < earned ? ' class="is-earned"' : ''}>${icon('star', { size: 12, filled: step < earned })}</span>`)
    .join('')}</span>`;
}

export function masteryStars(card = {}) {
  const stage = Math.max(0, Math.min(4, Number(card.review_stage) || 0));
  const count = stage >= 4 ? 3 : stage >= 2 ? 2 : 1;
  return `${'★'.repeat(count)}${'☆'.repeat(3 - count)}`;
}

export function vocabularyStatus(card = {}) {
  if (!card.saved) return 'new';
  if (card.due) return 'due';
  if ((Number(card.review_stage) || 0) >= 3) return 'mastered';
  return 'learning';
}

export function supportMeaning(card = {}, supportLanguage = '') {
  const target = value(card.identity?.language);
  const meanings = Array.isArray(card.meanings) ? card.meanings : [];
  const support = meanings.find(
    (meaning) => value(meaning?.language) === value(supportLanguage),
  );
  if (support?.text) return value(support.text);
  const vietnamese = meanings.find((meaning) => value(meaning?.language) === 'vi');
  if (vietnamese?.text) return value(vietnamese.text);
  return value(
    meanings.find((meaning) => value(meaning?.language) !== target)?.text ||
      meanings[0]?.text,
  );
}

export function compactSupportMeaning(card = {}, supportLanguage = '', maxLength = 150) {
  const meaning = supportMeaning(card, supportLanguage);
  if (meaning.length <= maxLength) return meaning;
  const firstSentence = meaning.split(/(?<=[.!?。！？])\s+/)[0].trim();
  const compact = firstSentence && firstSentence.length <= maxLength ? firstSentence : meaning;
  return compact.length <= maxLength ? compact : `${compact.slice(0, maxLength - 1).trimEnd()}…`;
}

function targetMeaning(card = {}) {
  const language = value(card.identity?.language);
  const meanings = Array.isArray(card.meanings) ? card.meanings : [];
  return value(
    meanings.find((meaning) => value(meaning?.language) === language)?.text ||
      meanings[0]?.text,
  );
}

function exampleText(card = {}) {
  const authored = Array.isArray(card.examples) ? card.examples : [];
  const first = authored.find((example) => value(example?.text || example?.target || example));
  return value(card.example) || value(first?.text || first?.target || first);
}

function exampleLanguage(card = {}, fallback = '') {
  const authored = Array.isArray(card.examples) ? card.examples : [];
  const first = authored.find((example) => value(example?.text || example?.target || example));
  return value(first?.language) || value(card.identity?.language) || fallback || 'en';
}

function frameworkLabel(copy, framework) {
  const raw = value(framework);
  if (!raw) return '';
  const key = `vocabularyFramework_${raw.replace(/[^a-z0-9]/gi, '').toLowerCase()}`;
  return value(copy[key]) || raw;
}

export function vocabularyKeepPayload(card, sourceKind, supportLanguage) {
  return {
    word: card.headword,
    phonetic: card.pronunciation || '',
    part_of_speech: card.part_of_speech || '',
    definition: targetMeaning(card),
    translation_vi: supportMeaning(card, supportLanguage),
    source_kind: sourceKind,
  };
}

function statusLabel(copy, status) {
  return copy[
    { new: 'newWord', learning: 'learning', due: 'due', mastered: 'mastered' }[
      status
    ]
  ];
}

function metadata(copy, card) {
  const level = vocabularyLevel(card) || '—';
  const framework = frameworkLabel(copy, card.framework);
  const status = vocabularyStatus(card);
  return `<span class="vocabulary-meta"><span>${esc(level)}</span>${vocabularyRankToken(copy, card)}${framework ? `<span>${esc(framework)}</span>` : ''}<span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span><span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></span>`;
}

function collectionLevelLabel(collection) {
  const explicitRange = value(collection?.level_range || collection?.levelRange);
  if (explicitRange) return explicitRange;
  const levels = Array.isArray(collection?.levels)
    ? collection.levels.map((level) => value(level)).filter(Boolean)
    : [];
  if (levels.length > 1) return `${levels[0]}–${levels[levels.length - 1]}`;
  return vocabularyLevel(collection) || levels[0] || '—';
}

function collectionLevel(collection) {
  const levels = Array.isArray(collection?.levels)
    ? collection.levels.map((level) => value(level)).filter(Boolean)
    : [];
  return vocabularyLevel({ level: levels[0] || collection?.level }) || '';
}

export function renderVocabularyCollectionCard(copy, collection, { index = 0 } = {}) {
  const progress = collection.progress || {};
  const learned = Number(progress.learned_count) || 0;
  const total = Number(collection.item_count) || 0;
  const percent = total ? Math.round((learned / total) * 100) : 0;
  const level = collectionLevel(collection);
  const levelLabel = collectionLevelLabel(collection);
  const skin = vocabularyLevelSkin({ level });
  const framework = frameworkLabel(copy, collection.framework);
  return `<article class="vocabulary-collection-card" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-level-range="${esc(levelLabel)}" data-vocabulary-rank="${esc(vocabularyRank({ level }))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-collection-card="${esc(index)}"><button class="vocabulary-collection-card__open" data-vocabulary-collection="${esc(collection.id)}" data-open-collection="${esc(collection.id)}"><span class="vocabulary-collection-card__cap"><span class="vocabulary-collection-card__eyebrow">${esc(levelLabel)}${framework ? ` · ${esc(framework)}` : ''}</span>${vocabularyRankToken(copy, { level })}</span><h3>${esc(collection.title || '')}</h3>${collection.topic ? `<p>${esc(collection.topic)}</p>` : ''}<div class="vocabulary-collection-card__progress"><span>${esc(learned)} / ${esc(total)} ${esc(copy.words || 'words')}</span><span>${esc(percent)}%</span></div><div class="vocabulary-progress" aria-hidden="true"><span style="width:${percent}%"></span></div><div class="vocabulary-collection-card__stats"><span>${esc(progress.learning_count || 0)} ${esc(copy.learning || 'Learning')}</span><span>${esc(progress.due_count || 0)} ${esc(copy.due || 'Due')}</span><span>${esc(progress.mastered_count || 0)} ${esc(copy.mastered || 'Mastered')}</span></div><span class="vocabulary-collection-card__footer">${esc(copy.open || 'Open')} <span aria-hidden="true">→</span></span></button></article>`;
}

function browseMetadata(copy, card) {
  const parts = [];
  const partOfSpeech = value(card.part_of_speech);
  const framework = frameworkLabel(copy, card.framework);
  const topic = value(card.topic);
  if (partOfSpeech) parts.push(partOfSpeech);
  if (framework) parts.push(framework);
  if (topic) parts.push(topic);
  if (!parts.length) return '';
  return `<p class="vocabulary-browse-card__meta">${parts.map((part) => `<span>${esc(part)}</span>`).join('<span aria-hidden="true">·</span>')}</p>`;
}

export function renderVocabularyBrowseCard(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save', source = 'browse', className = '', ariaHidden = null, inert = false } = {}) {
  const language = value(card.identity?.language) || 'en';
  const headword = value(card.headword);
  const meaning = compactSupportMeaning(card, copy.supportLanguage);
  const pronunciation = value(card.pronunciation);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const stars = masteryStars(card);
  const state = vocabularyStatus(card);
  const saved = Boolean(card.saved);
  const sourceAttr = source ? ` data-vocabulary-source="${esc(source)}"` : '';
  const feedAttr = source === 'feed' ? ` data-vocabulary-feed-item="${esc(index)}"` : '';
  const hiddenAttr = ariaHidden === null ? '' : ` aria-hidden="${ariaHidden ? 'true' : 'false'}"`;
  const inertAttr = inert ? ' inert' : '';
  const cardClass = ['vocabulary-browse-card', className].filter(Boolean).join(' ');
  const saveLabel = saved ? `${copy.saved || 'Saved'} ✓` : `+ ${copy.save || 'Save'}`;
  return `<article class="${esc(cardClass)}" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-rank="${esc(vocabularyRank(card))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-browse-card="${esc(index)}"${sourceAttr}${feedAttr}${hiddenAttr}${inertAttr}><div class="vocabulary-browse-card__top"><span class="vocabulary-browse-card__level">${esc(level || '—')}</span>${vocabularyRankToken(copy, card)}</div><div class="vocabulary-browse-card__content"><h3 lang="${esc(language)}">${esc(headword)}</h3><p class="vocabulary-browse-card__meaning" lang="${esc(copy.supportLanguage || 'en')}">${esc(meaning)}</p>${pronunciation ? `<p class="vocabulary-browse-card__pronunciation" lang="${esc(language)}">${esc(pronunciation)}</p>` : ''}${browseMetadata(copy, card)}</div><div class="vocabulary-browse-card__status"><span class="vocabulary-stars" aria-label="${esc(stars)}">${esc(stars)}</span><span class="vocabulary-state vocabulary-state--${esc(state)}">${esc(statusLabel(copy, state))}</span></div><div class="vocabulary-browse-card__actions"><button class="primary vocabulary-browse-card__study" data-vocabulary-study="${esc(index)}" data-vocabulary-study-source="${esc(source)}">${esc(copy.study || copy.open)}</button><button class="outline vocabulary-browse-card__save" ${saveAttribute}="${esc(index)}" aria-label="${esc(saveLabel)}" aria-pressed="${saved ? 'true' : 'false'}" ${saved ? 'disabled' : ''}>${esc(saveLabel)}</button></div></article>`;
}

export function renderVocabularyFeedPreview(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save', active = false } = {}) {
  return renderVocabularyBrowseCard(copy, card, {
    index,
    saveAttribute,
    source: 'feed',
    className: 'vocabulary-feed-slide',
    ariaHidden: !active,
    inert: !active,
  });
}

export function renderVocabularyFeedCarousel(
  copy,
  cards,
  { limit = 5, saveAttribute = 'data-vocabulary-save', full = false, variant = '' } = {},
) {
  const count = Math.max(0, Number(limit) || 0);
  const items = Array.isArray(cards) ? cards.slice(0, count) : [];
  if (!items.length) return '';
  const title = value(copy.vocabularyFeedTitle) || 'Daily Vocabulary';
  const previous = value(copy.vocabularyFeedPrevious) || 'Previous words';
  const next = value(copy.vocabularyFeedNext) || 'Next words';
  const soundOn = value(copy.vocabularyFeedSoundOn) || 'Turn feed snap sound off';
  const fullClass = full ? ' vocabulary-feed-carousel--full' : '';
  const variantClass = variant ? ` vocabulary-feed-carousel--${value(variant)}` : '';
  const dots = items
    .map(
      (_, index) =>
        `<button type="button" class="vocabulary-feed-carousel__dot${index === 0 ? ' is-active' : ''}" data-vocabulary-feed-dot="${index}" aria-label="${esc(`${title} ${index + 1}`)}" aria-current="${index === 0 ? 'true' : 'false'}"></button>`,
    )
    .join('');
  const soundOff = value(copy.vocabularyFeedSoundOff) || 'Turn feed snap sound on';
  return `<div class="vocabulary-feed-carousel${fullClass}${variantClass}" data-vocabulary-feed-carousel role="region" aria-roledescription="carousel" aria-label="${esc(title)}"><div class="vocabulary-feed-carousel__viewport"><div class="vocabulary-feed-carousel__stage"><button type="button" class="vocabulary-feed-carousel__control vocabulary-feed-carousel__control--prev" data-vocabulary-feed-prev aria-label="${esc(previous)}" ${items.length < 2 ? 'disabled' : ''}>←</button><section class="vocabulary-feed-preview" data-vocabulary-feed-track role="list" tabindex="0" aria-label="${esc(title)}">${items.map((card, index) => renderVocabularyFeedPreview(copy, card, { index, saveAttribute, active: index === 0 })).join('')}</section><button type="button" class="vocabulary-feed-carousel__control vocabulary-feed-carousel__control--next" data-vocabulary-feed-next aria-label="${esc(next)}" ${items.length < 2 ? 'disabled' : ''}>→</button></div></div><div class="vocabulary-feed-carousel__rail"><span class="vocabulary-feed-carousel__position" data-vocabulary-feed-position role="status">1 / ${items.length}</span><span class="vocabulary-feed-carousel__dots" role="tablist" aria-label="${esc(title)}">${dots}</span><button type="button" class="vocabulary-feed-carousel__sound" data-vocabulary-feed-sound data-vocabulary-feed-sound-on="${esc(soundOn)}" data-vocabulary-feed-sound-off="${esc(soundOff)}" aria-pressed="true" aria-label="${esc(soundOn)}"><span aria-hidden="true">⌁</span><span class="sr-only">${esc(soundOn)}</span><span class="vocabulary-feed-carousel__sound-state" data-vocabulary-feed-sound-state>${esc(soundOn)}</span></button></div></div>`;
}

export function bindVocabularyFeedCarousel(root) {
  if (!root?.querySelectorAll) return;
  root.querySelectorAll('[data-vocabulary-feed-carousel]').forEach((carousel) => {
    const track = carousel.querySelector('[data-vocabulary-feed-track]');
    const slides = track ? [...track.children] : [];
    const previousButton = carousel.querySelector('[data-vocabulary-feed-prev]');
    const nextButton = carousel.querySelector('[data-vocabulary-feed-next]');
    const position = carousel.querySelector('[data-vocabulary-feed-position]');
    const dots = [...carousel.querySelectorAll('[data-vocabulary-feed-dot]')];
    if (!track || !slides.length) return;
    const reducedMotion = () =>
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let activeIndex = 0;
    let interactionArmed = false;
    let soundEnabled = true;
    let audioContext = null;
    let pointerState = null;
    let suppressClickUntil = 0;
    const soundButton = carousel.querySelector('[data-vocabulary-feed-sound]');
    const soundState = carousel.querySelector('[data-vocabulary-feed-sound-state]');
    const soundOn = soundButton?.dataset.vocabularyFeedSoundOn || 'Turn feed snap sound off';
    const soundOff = soundButton?.dataset.vocabularyFeedSoundOff || 'Turn feed snap sound on';
    const armInteraction = () => {
      interactionArmed = true;
    };
    const updateSoundLabel = () => {
      if (!soundButton) return;
      const label = soundEnabled ? soundOn : soundOff;
      soundButton.setAttribute('aria-label', label);
      soundButton.setAttribute('aria-pressed', soundEnabled ? 'true' : 'false');
      if (soundState) soundState.textContent = label;
    };
    const playTick = () => {
      if (!interactionArmed || !soundEnabled || typeof window === 'undefined') return;
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      try {
        audioContext ||= new AudioContextClass();
        if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        const now = audioContext.currentTime;
        oscillator.type = 'triangle';
        oscillator.frequency.setValueAtTime(760, now);
        oscillator.frequency.exponentialRampToValueAtTime(540, now + 0.035);
        gain.gain.setValueAtTime(0.018, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.045);
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(now);
        oscillator.stop(now + 0.05);
      } catch {
        // Sound is an optional affordance; navigation must remain functional.
      }
    };
    const update = (index = activeIndex) => {
      activeIndex = index;
      carousel.classList.toggle('is-reduced-motion', reducedMotion());
      if (position) position.textContent = `${index + 1} / ${slides.length}`;
      if (previousButton) previousButton.disabled = index === 0;
      if (nextButton) nextButton.disabled = index >= slides.length - 1;
      slides.forEach((slide, slideIndex) => {
        const active = slideIndex === index;
        slide.classList.toggle('is-active', active);
        slide.classList.toggle('is-prev', slideIndex === index - 1);
        slide.classList.toggle('is-next', slideIndex === index + 1);
        slide.setAttribute('aria-hidden', active ? 'false' : 'true');
        slide.toggleAttribute('inert', !active);
        slide.inert = !active;
      });
      dots.forEach((dot, dotIndex) => {
        const active = dotIndex === index;
        dot.classList.toggle('is-active', active);
        dot.setAttribute('aria-current', active ? 'true' : 'false');
      });
    };
    const goTo = (index, { announce = true } = {}) => {
      const bounded = Math.max(0, Math.min(index, slides.length - 1));
      if (!slides[bounded]) return;
      const changed = bounded !== activeIndex;
      activeIndex = bounded;
      update(bounded);
      if (changed && announce) playTick();
    };
    previousButton?.addEventListener('click', () => { armInteraction(); goTo(activeIndex - 1); });
    nextButton?.addEventListener('click', () => { armInteraction(); goTo(activeIndex + 1); });
    dots.forEach((dot, index) => dot.addEventListener('click', () => { armInteraction(); goTo(index); }));
    track.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        armInteraction();
        goTo(activeIndex + (event.key === 'ArrowRight' ? 1 : -1));
      }
    });
    track.addEventListener('pointerdown', (event) => {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      armInteraction();
      pointerState = { id: event.pointerId, startX: event.clientX, moved: false };
      track.classList.add('is-dragging');
      track.setPointerCapture?.(event.pointerId);
    });
    track.addEventListener('pointermove', (event) => {
      if (!pointerState || pointerState.id !== event.pointerId) return;
      const delta = Math.max(-110, Math.min(110, event.clientX - pointerState.startX));
      if (Math.abs(delta) > 8) pointerState.moved = true;
      track.style.setProperty('--feed-drag-x', `${delta}px`);
      track.style.setProperty('--feed-drag-rotate', `${Math.max(-5, Math.min(5, delta / 22))}deg`);
    });
    const finishPointer = (event) => {
      if (!pointerState || pointerState.id !== event.pointerId) return;
      const delta = event.clientX - pointerState.startX;
      const moved = pointerState.moved;
      pointerState = null;
      track.classList.remove('is-dragging');
      track.style.removeProperty('--feed-drag-x');
      track.style.removeProperty('--feed-drag-rotate');
      if (moved) suppressClickUntil = Date.now() + 220;
      if (Math.abs(delta) >= 32) goTo(activeIndex + (delta < 0 ? 1 : -1));
    };
    track.addEventListener('pointerup', finishPointer);
    track.addEventListener('pointercancel', finishPointer);
    track.addEventListener('click', (event) => {
      if (Date.now() < suppressClickUntil) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);
    soundButton?.addEventListener('click', () => {
      armInteraction();
      soundEnabled = !soundEnabled;
      updateSoundLabel();
    });
    update(0);
  });
}

/* Where a saved word was met.

   A word kept while reading is not the same thing as a word from a list: the
   sentence it was met in, and the piece it came from, are most of why a
   learner recognises it again. Both already travel on the saved record, and
   showing them is the difference between My Language and a dictionary export.
   One line, quoted, in the learning language - it is content, not chrome. */
function sourceLine(card, language) {
  const encounter = (card.source_encounters || []).find((entry) => value(entry?.fragment));
  if (!encounter) return '';
  const fragment = value(encounter.fragment).replace(/\s+/g, ' ');
  const where = value(encounter.where);
  return `<p class="vocabulary-row__source">${where ? `<span class="vocabulary-row__where">${esc(where)}</span>` : ''}<q lang="${esc(language)}">${esc(fragment)}</q></p>`;
}

export function renderVocabularyRow(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save' } = {}) {
  const headword = value(card.headword);
  const language = value(card.identity?.language) || 'en';
  const translation = compactSupportMeaning(card, copy.supportLanguage);
  const pronunciation = value(card.pronunciation);
  const saved = Boolean(card.saved);
  const saveLabel = saved ? `${copy.saved} ✓` : copy.save;
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  return `<article class="vocabulary-row" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-rank="${esc(vocabularyRank(card))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-row="${esc(index)}"><div class="vocabulary-row__word"><strong lang="${esc(language)}">${esc(headword)}</strong>${pronunciation ? `<span class="vocabulary-row__pronunciation">${esc(pronunciation)}</span>` : ''}</div><div class="vocabulary-row__meaning" lang="${esc(copy.supportLanguage || 'en')}">${esc(translation || targetMeaning(card))}</div>${sourceLine(card, language)}${metadata(copy, card)}<div class="vocabulary-row__actions"><button class="quiet" data-vocabulary-study="${esc(index)}">${esc(copy.study || copy.open)}</button><button class="quiet" ${saveAttribute}="${esc(index)}" aria-label="${esc(saveLabel)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saveLabel)}</button></div></article>`;
}

function orthography(card, copy) {
  const characters = Array.isArray(card.orthography?.characters)
    ? card.orthography.characters.filter((item) => value(item?.character))
    : [];
  if (!characters.length) return '';
  return `<section class="vocabulary-study__orthography"><h3>${esc(copy.orthography || 'Orthography')}</h3><ul>${characters
    .map(
      (item) =>
        `<li lang="zh"><span>${esc(item.character)}</span><small>${esc(item.stroke_count)} ${esc(copy.strokes)}</small></li>`,
    )
    .join('')}</ul></section>`;
}

export function renderVocabularyStudyCard(copy, card, { index = 0 } = {}) {
  const language = value(card.identity?.language) || 'en';
  const headword = value(card.headword);
  const pronunciation = value(card.pronunciation);
  const support = supportMeaning(card, copy.supportLanguage);
  const definition = targetMeaning(card);
  const example = exampleText(card);
  const exampleLang = exampleLanguage(card, language);
  const saved = Boolean(card.saved);
  const status = vocabularyStatus(card);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const saveLabel = saved ? `${copy.saved} ✓` : copy.save;
  const proficiencyLabel = level || '—';
  /* The approved card: level and audio above, the word and its reading in the
     middle, the way to turn it and what has been earned below. The back keeps
     the meaning, the sentence it came from, and the two answers the scheduler
     accepts (four grades are GAP-019). */
  const front = `<div class="vocabulary-study-card__front" data-study-front aria-hidden="false"><div class="vocabulary-study-card__top"><span class="ds-label">${esc(proficiencyLabel)}</span>${vocabularyRankToken(copy, card)}<button class="icon-button vocabulary-study-card__audio" data-study-audio data-study-no-flip aria-label="${esc(copy.audio || 'Play audio')}">${icon('speaker-high', { size: 17 })}</button></div><div class="vocabulary-study-card__target"><h2 lang="${esc(language)}">${esc(headword)}</h2>${pronunciation ? `<p class="vocabulary-study-card__reading ds-data" lang="${esc(language)}" data-study-no-flip>${esc(pronunciation)}</p>` : ''}</div><div class="vocabulary-study-card__bottom"><button class="vocabulary-study-card__flip ds-label" data-study-flip>${icon('hand-tap', { size: 13 })}<span>${esc(copy.flip)}</span></button>${masteryStarRow(card)}</div></div>`;
  const back = `<div class="vocabulary-study-card__back" data-study-back aria-hidden="true" inert><div class="vocabulary-study-card__back-body"><div class="vocabulary-study-card__headline"><h2 lang="${esc(language)}">${esc(headword)}</h2>${vocabularyRankToken(copy, card)}${pronunciation ? `<span class="vocabulary-study-card__reading ds-data" lang="${esc(language)}" data-study-no-flip>${esc(pronunciation)}</span>` : ''}</div><p class="vocabulary-study__support" lang="${esc(copy.supportLanguage || 'en')}" data-study-no-flip>${esc(support)}</p>${definition && definition !== support ? `<p class="vocabulary-study__definition" lang="${esc(language)}" data-study-no-flip>${esc(definition)}</p>` : ''}${example ? `<section class="vocabulary-study-card__example"><p lang="${esc(exampleLang)}">${esc(example)}</p></section>` : ''}${card.usage ? `<section class="vocabulary-study__usage"><h3>${esc(copy.usage)}</h3><p lang="${esc(language)}">${esc(card.usage)}</p></section>` : ''}${orthography(card, copy)}</div><div class="vocabulary-study-card__footer"><div class="vocabulary-study-card__actions"><button class="quiet vocabulary-study-card__flip" data-study-flip>${esc(copy.front || copy.flip)}</button><button class="quiet" data-vocabulary-save="${esc(index)}" aria-label="${esc(saveLabel)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saveLabel)}</button></div>${saved ? `<div class="vocabulary-study-card__grades" aria-label="${esc(copy.review)}"><button class="outline" data-study-grade="again">${icon('x', { size: 14 })}<span>${esc(copy.again)}</span></button><button class="primary" data-study-grade="got_it">${icon('check', { size: 14 })}<span>${esc(copy.gotIt)}</span></button></div>` : ''}<div class="vocabulary-study-card__status"><span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></div></div></div>`;
  return `<article class="vocabulary-study-card" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-rank="${esc(vocabularyRank(card))}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-index="${esc(index)}" data-study-state="front" data-study-surface tabindex="0" aria-label="${esc(headword)}"><div class="vocabulary-study-card__inner" data-study-inner>${front}${back}</div></article>`;
}
