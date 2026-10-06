/* One line's dictation practice - the answer box, the progressive hint, Check, the comparison and the
   server-saved evidence - as one piece both rooms mount: the standalone Dictation room and the
   Listening workspace's Dictation mode (human direction 2026-10-06, LEX-029). The room owns the media,
   the line navigation and where the two blocks sit; this owns what happens to one line's answer.

   The answer is never shown before Check: the room asks `revealed(id)` before drawing a line's text,
   pinyin or meaning, and a line is revealed only once it has been checked in this session. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { toast } from '../../kit/toast.js';
import { markGlyph } from '../../kit/brand.js';
import { langAttr } from '../../kit/lang.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { dictationEvidence, recoverListeningEvidence } from '../../product/evidence.js';
import { t } from './copy.js';
import {
  previousEvidence, checkAnswer, chipsFor, scoreOf, scoreNoteKey, hintNoteKey, hintButton, liveView, MAX_HINT_LEVEL,
} from './model.js';

function setText(target, value) {
  if (target) target.textContent = String(value ?? '');
}

/* `lesson` is dictation/model.js#mapLesson's shape; `priorRead` may be a function. `byId` is the stored progress per segment; the
   factory adds this session's own checks to it. */
export function createLinePractice({ lesson, byId, priorRead = true, memory = null, onChange = () => {}, onNext = () => {}, onCheck = () => {} }) {
  // Whether the stored progress was read: a value, or a question asked at check time when it loads later.
  const readPrior = typeof priorRead === 'function' ? priorRead : () => priorRead;
  const localById = new Map(); // this session's latest real check per segment
  const revealedIds = new Set(); // lines checked in this session: their answer may now be drawn
  const results = new Map(); // each checked line keeps its own answer and result (id -> state)
  let seg = null;
  let stageEl = null;
  let dockEl = null;
  let answer = '';
  let hintLevel = 0;
  let hintHidden = false; // the learner put the hint away to try unaided; the level it reached stays (LEX-033)
  let checked = false;
  let lastResult = null;
  let evidence = null;
  let recover = null;
  let nextLabel = '';

  const q = (selector) => stageEl?.querySelector(selector) || dockEl?.querySelector(selector) || null;
  const draftKey = () => `${lesson.assetId || lesson.id}:${seg.id}`;
  function saveDraft(value) {
    try { memory?.write(draftKey(), value, 'answers'); } catch { /* device memory unavailable */ }
  }
  function readDraft() {
    try { return String(memory?.value?.answers?.[draftKey()] || ''); } catch { return ''; }
  }

  function ensureEvidence() {
    const target = seg.id;
    evidence = dictationEvidence({
      asset: lesson.assetId,
      segment: { segment_id: target, spoken_text: seg.text },
      language: lesson.language,
      previous: previousEvidence(byId.get(target)),
    });
    // The stored record could not be read and this session has not saved this line yet: fold the
    // server's copy in at save time instead of replacing it.
    recover = !readPrior() && !byId.has(target)
      ? recoverListeningEvidence(async () => {
          const stored = await api.listeningProgress(lesson.assetId);
          return (stored?.items || []).find((item) => item.segment_id === target) || {};
        })
      : null;
  }

  function liveMarkup() {
    const view = liveView({ expected: seg.text, answer, language: lesson.language, level: hintLevel });
    return html`<div class="s-dict__livehead"><span class="s-dict__livelabel">${t('liveLabel')}</span><span class="s-dict__livecount">${t.plural('liveCount', view.total, { n: view.found, total: view.total })}</span></div>
      <div class="s-dict__livechips" lang="${langAttr(lesson.language)}">
        ${view.chips.map((chip) => html`<span class="s-dict__livechip s-dict__livechip--${chip.kind}">${chip.text}${chip.kind === 'ok' ? html`${raw(icon('check', { size: 14 }))}` : ''}</span>`)}
      </div>`;
  }
  function paintLive() {
    const box = q('[data-live]');
    if (!box) return;
    box.hidden = hintLevel <= 0 || hintHidden;
    if (hintLevel > 0 && !hintHidden) mount(box, liveMarkup());
    const toggle = q('[data-hint-toggle]');
    if (toggle) {
      toggle.hidden = hintLevel <= 0;
      setText(toggle, t(hintHidden ? 'hintShow' : 'hintHide'));
      toggle.setAttribute('aria-pressed', String(!hintHidden));
    }
  }
  function paintHint() {
    const button = q('[data-hint]');
    const note = q('[data-hint-note]');
    if (!button || !note) return;
    const view = hintButton(hintLevel);
    setText(button, t(view.key, view.values));
    button.disabled = view.disabled;
    setText(note, t(hintNoteKey(hintLevel, lesson.language)));
  }

  function paintPre() {
    mount(stageEl, html`<textarea class="s-dict__input" data-input rows="3" lang="${langAttr(lesson.language)}" aria-label="${t('placeholder')}" placeholder="${t('placeholder')}">${answer}</textarea>
      <div class="s-dict__live" data-live hidden></div>`);
    mount(dockEl, html`<div class="s-dict__hintrow">
      <button type="button" class="s-dict__hint" data-hint></button>
      <button type="button" class="s-dict__hinttoggle" data-hint-toggle hidden></button>
      <span class="s-dict__hintnote" data-hint-note></span>
      <span class="s-dict__spacer"></span>
      <button type="button" class="o-btn o-btn--primary s-dict__check" data-check>${t('checkButton')}</button>
    </div>`);
    const input = q('[data-input]');
    input.addEventListener('input', (event) => {
      answer = event.target.value;
      saveDraft(answer);
      if (hintLevel > 0) paintLive();
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        void check();
      }
    });
    q('[data-hint]').addEventListener('click', () => {
      if (hintLevel >= MAX_HINT_LEVEL) return;
      hintLevel += 1;
      hintHidden = false;
      paintHint();
      paintLive();
    });
    q('[data-hint-toggle]').addEventListener('click', () => {
      hintHidden = !hintHidden;
      paintLive();
    });
    q('[data-check]').addEventListener('click', () => void check());
    paintHint();
    paintLive();
  }

  function paintPost() {
    const score = scoreOf(lastResult);
    const chips = chipsFor(lastResult, { expected: seg.text, answer, language: lesson.language });
    mount(stageEl, html`<div class="s-dict__result">
      <div class="s-dict__scorerow">
        <span class="s-dict__score">${score.correct}/${score.total}</span>
        <span class="s-dict__scorenote">${t(scoreNoteKey(score.tier))}</span>
        ${hintLevel > 0 ? html`<span class="s-dict__hintbadge">${t('usedHintBadge')}</span>` : ''}
      </div>
      <div class="s-dict__chipblock">
        <div class="s-dict__chiplabel">${t('youWrote')}</div>
        <div class="s-dict__chips" lang="${langAttr(lesson.language)}">
          ${chips.mine.map((chip) => html`<span class="s-dict__chip s-dict__chip--mine-${chip.kind}">${chip.text}</span>`)}
          ${chips.mineEmpty ? html`<span class="s-dict__chipempty">${t('emptyAnswer')}</span>` : ''}
        </div>
      </div>
      <div class="s-dict__chipblock">
        <div class="s-dict__chiplabel">${t('transcript')}</div>
        <div class="s-dict__chips" lang="${langAttr(lesson.language)}">
          ${chips.src.map((chip) => html`<span class="s-dict__chip s-dict__chip--src-${chip.kind}">${chip.text}</span>`)}
        </div>
        ${seg.support ? html`<div class="s-dict__support">${seg.support}</div>` : ''}
      </div>
    </div>`);
    mount(dockEl, html`<div class="s-dict__actions">
      <button type="button" class="s-dict__navbtn s-dict__retry" data-retry>${t('retry')}</button>
      <button type="button" class="s-dict__ai" data-explain>${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('explainLine')}</button>
      <span class="s-dict__spacer"></span>
      <button type="button" class="o-btn o-btn--primary s-dict__next" data-next>${nextLabel}</button>
    </div>`);
    q('[data-retry]').addEventListener('click', retry);
    q('[data-explain]').addEventListener('click', () => {
      askOrena({
        surface: 'listening.dictation',
        activity_type: 'listening',
        content_id: `media:${lesson.id}`,
        selected_item: { type: 'sentence', id: seg.id, text: seg.text, lang: lesson.language },
      });
    });
    q('[data-next]').addEventListener('click', () => onNext(seg));
  }

  function paint() {
    if (!stageEl || !dockEl || !seg) return;
    if (checked) paintPost();
    else paintPre();
  }

  async function check() {
    const line = seg;
    lastResult = checkAnswer({ expected: line.text, answer, language: lesson.language });
    checked = true;
    revealedIds.add(line.id);
    results.set(line.id, { answer, hintLevel, lastResult });
    const attempted = Boolean(answer.trim());
    // A blank submission shows the honest "everything missing" comparison and is never persisted.
    if (attempted) localById.set(line.id, { exact: lastResult.exact });
    onCheck(line);
    paint();
    onChange();
    if (!attempted) return;
    evidence.compare(answer, { hintLevel });
    let outgoing = evidence.value;
    if (recover) {
      try {
        outgoing = await recover(outgoing);
      } catch {
        toast(t('progressUnread'));
        return;
      }
    }
    try {
      const saved = await api.saveListeningProgress(outgoing);
      if (saved?.item) {
        // The stored score is the server's (D-103.2): once acknowledged it replaces the instant mark.
        byId.set(line.id, saved.item);
        localById.delete(line.id);
        onChange();
      }
    } catch {
      toast(t('saveFailed'));
    }
  }

  function retry() {
    answer = '';
    saveDraft('');
    hintLevel = 0;
    hintHidden = false;
    checked = false;
    lastResult = null;
    results.delete(seg.id);
    ensureEvidence();
    paint();
    q('[data-input]')?.focus();
  }

  return {
    localById,
    /* Whether a line's own words may be drawn: only once it has been checked in this session. */
    revealed: (id) => revealedIds.has(id),
    /* Show `line` in the two blocks; a different line starts fresh with its answer hidden. */
    show(line, { stage, dock, next }) {
      stageEl = stage;
      dockEl = dock;
      nextLabel = next;
      if (!seg || seg.id !== line.id) {
        seg = line;
        const kept = results.get(line.id);
        answer = kept ? kept.answer : readDraft();
        hintLevel = kept ? kept.hintLevel : 0;
        hintHidden = false;
        checked = Boolean(kept);
        lastResult = kept ? kept.lastResult : null;
        ensureEvidence();
      }
      paint();
    },
    isChecked: () => checked,
  };
}
