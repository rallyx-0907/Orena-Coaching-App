/* Original media + the pinned Check Understanding question/feedback composition.
   Sets are admitted source artifacts. This room reads and locally checks them;
   it never generates questions, acquires media or claims durable ability evidence. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { langAttr } from '../../kit/lang.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy } from '../../copy/shell.js';
import { openMedia } from '../../product/media-source.js';
import { sourceFromLesson } from '../../product/speaking-source.js';
import { originalSegmentPlayer } from '../../product/original-segment-player.js';
import { encounter } from '../../product/encounter.js';
import { optionStyle, markFor } from '../check/model.js';
import { questionsFrom, grade } from './model.js';
import { t } from './copy.js';

export default async function listeningQuestions(element, ctx) {
  await useStyles('screens/check/check.css');
  await useStyles('screens/listening-questions/questions.css');
  const id = ctx.params.id;
  const payload = await openMedia(id,{api,language:ctx.context.language,support:languages().support,owner:ctx.context.owner});
  const questions = questionsFrom(payload);
  const source = sourceFromLesson(id,payload);
  const support = languages().support;
  const meanings = encounter(payload,support);
  if (!ctx.isCurrent()) return;
  if (!questions.length || !source?.hasModelAudio || source.language !== ctx.context.language) throw Error('This listening exercise is unavailable.');
  const start = payload.catalog.excerpt_start_ms;
  const end = payload.catalog.excerpt_end_ms;
  source.line = { ...source.line, startMs:start, endMs:end };
  const player = originalSegmentPlayer(source);
  let index=0, finished=false, playing=false;
  let playGeneration=0;
  const results=new Map();
  mount(element,html`<div class="s-check s-listenq">
    <div class="s-check__head"><button class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left',{size:21}))}</button>
      <div class="s-check__head-body"><div class="s-check__title">${shellCopy('listeningComprehension')}</div><div class="s-check__meta" ${langAttr(source.language)}>${source.title}</div></div>
      <button class="o-btn o-btn--link" data-choose>${t('choose')}</button></div>
    <div class="s-listenq__player"><button class="o-btn o-btn--primary" data-play>${t('play')}</button><div data-player></div></div>
    <div class="s-check__bar"><span data-progress></span></div>
    <div class="s-check__card" data-card data-scroll-region></div>
    <div class="s-listenq__footer" data-footer></div>
  </div>`);
  const choose=()=>ctx.go(ctx.href('discover',{}, {practice:'listening',tab:'listen'}));
  element.querySelector('[data-choose]').addEventListener('click',choose);
  element.querySelector('[data-back]').addEventListener('click',()=>ctx.back());
  player.attach(element.querySelector('[data-player]'));
  const playButton=element.querySelector('[data-play]');
  function stop() { playGeneration++; playing=false;player.stop();playButton.textContent=t('play'); }
  async function play(from=start,to=end) {
    if (playing) {stop(); return;}
    const generation=++playGeneration;
    playing=true; playButton.textContent=t('stop');
    await player.play({from:(from-start)/1000,to:(to-start)/1000});
    if (generation===playGeneration && ctx.isCurrent()) {playing=false;playButton.textContent=t('play');}
  }
  playButton.addEventListener('click',()=>play());
  function paint() {
    const card=element.querySelector('[data-card]');
    const footer=element.querySelector('[data-footer]');
    element.querySelector('[data-progress]').style.width=`${results.size/questions.length*100}%`;
    if (finished) {
      mount(card,html`<div class="s-check__question">${t('result',{n:[...results.values()].filter(r=>r.correct).length,total:questions.length})}</div>`);
      mount(footer,html`<button class="o-btn o-btn--secondary" data-again>${t('again')}</button><button class="o-btn o-btn--primary" data-choose-next>${t('choose')}</button>`);
      footer.querySelector('[data-again]').addEventListener('click',()=>{results.clear();index=0;finished=false;paint();});
      footer.querySelector('[data-choose-next]').addEventListener('click',choose);
      return;
    }
    const q=questions[index], result=results.get(q.id);
    const translatedEvidence = support !== source.language ? q.evidence_segment_ids.map(id=>meanings.meaning(id)).filter(Boolean).join('\n') : '';
    mount(card,html`<div class="s-check__type">${t('question',{n:index+1,total:questions.length})}</div>
      <div class="s-check__question" ${langAttr(source.language)}>${q.prompt}</div>
      <div class="s-check__options">${q.options.map((text,i)=>{
        const state={index:i,graded:!!result,correctIndex:result?.correct_index,selectedIndex:result?.selected_index}, style=optionStyle(state);
        return html`<button class="s-check__option" data-option="${i}" aria-disabled="${!!result}" style="border-color:${style.border};background:${style.bg};color:${style.color}" ${langAttr(source.language)}><span class="s-check__mark" style="background:${style.markBg};color:${style.markColor}">${markFor(state)}</span>${text}</button>`;
      })}</div>
      ${result ? html`<div class="s-check__verdict" role="status"><strong>${t(result.correct?'correct':'incorrect')}</strong><p class="s-check__explain" ${langAttr(source.language)}>${q.explanation}</p><div class="s-check__evidence-label">${t('evidence')}</div><p class="s-check__evidence" ${langAttr(source.language)}>${q.evidence_text}</p>${translatedEvidence ? html`<p class="s-check__explain" ${langAttr(support)}>${translatedEvidence}</p>` : ''}<button class="s-check__show" data-evidence>${t('replayEvidence')}</button></div>` : ''}`);
    card.querySelectorAll('[data-option]').forEach(button=>button.addEventListener('click',()=>{
      if (results.has(q.id)) return;
      results.set(q.id,grade(q,Number(button.dataset.option))); paint();
    }));
    card.querySelector('[data-evidence]')?.addEventListener('click',()=>{
      const lines=payload.transcript.segments.filter(s=>q.evidence_segment_ids.includes(s.segment_id));
      stop();
      play(Math.min(...lines.map(s=>s.start_ms)),Math.max(...lines.map(s=>s.end_ms)));
    });
    mount(footer,html`<button class="o-btn o-btn--primary" data-next ${result?'':raw('disabled')}>${t(index+1<questions.length?'next':'finish')}</button>`);
    footer.querySelector('[data-next]').addEventListener('click',()=>{
      if (!results.has(q.id)) return;
      stop(); index++;finished=index===questions.length;paint();card.scrollTop=0;
    });
  }
  paint();
  return ()=>{playGeneration++;player.dispose();};
}
