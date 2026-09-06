import {esc,status} from './html.js';
import {link} from '../product/intent.js';
import {contentFor} from '../content/texts.js';

export async function renderExpression(root,ctx) {
  const {c,language,api,memory,alive}=ctx,id=ctx.location.id||'expression:free';
  const source=memory.value.continuation.find(x=>x.id===id)||memory.value.imports.find(x=>x.id===id)||contentFor(language).find(x=>`story:${x.id}`===id);
  let parentId=null;
  const title=source?.title||c.freeTitle;
  root.innerHTML=`<div class="back-row"><a href="${source?link('encounter',{id}):link('practice')}">← ${source?c.returnLabel:c.practice}</a></div><section class="expression-room"><small>${c.writingName}</small><h1>${esc(title)}</h1><p>${c.responsePrompt}</p><form id="expressionForm"><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="12" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id]||'')}</textarea><div class="expression-tools"><span data-draft-status class="meta">${memory.available?c.local:c.memoryUnavailable}</span><button class="primary">${c.review} ↗</button></div></form><section id="writingFeedback" aria-live="polite"></section></section>`;
  root.querySelector('textarea').oninput=event=>{memory.write(id,event.target.value);memory.enter({id,title,intent:'writing'});root.querySelector('[data-draft-status]').textContent=memory.available?c.local:c.memoryUnavailable;};
  root.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const button=event.currentTarget.querySelector('button'),feedback=root.querySelector('#writingFeedback');button.disabled=true;feedback.textContent=c.loading;
    try {const text=root.querySelector('textarea').value;const result=await ctx.mutate(()=>api.evaluate({prompt:source?`${title}\n${c.responsePrompt}`:c.freeTitle,text,target_cefr:language==='zh'?'HSK4':'B2',learning_language:language,parent_essay_id:parentId}));
      if(!alive())return;parentId=result.id;
      const corrections=(result.errors||[]).filter(x=>x.original||x.corrected);
      feedback.innerHTML=`<h2>${c.review}</h2>${result.corrected_text?`<blockquote lang="${language}">${esc(result.corrected_text)}</blockquote>`:''}${corrections.map(x=>`<article class="correction"><del lang="${language}">${esc(x.original||'')}</del><p lang="${language}">${esc(x.corrected||'')}</p>${ctx.support==='vi'&&x.explanation_vi?`<p lang="vi">${esc(x.explanation_vi)}</p>`:''}</article>`).join('')}<p>${c.persisted}</p><button class="outline" data-revise>${c.revision} ↗</button>`;
      feedback.querySelector('[data-revise]').onclick=()=>root.querySelector('textarea').focus();
    }catch{if(alive())feedback.textContent=c.reviewUnavailable;}finally{if(alive())button.disabled=false;}
  };
}
export async function renderLanguage(root,ctx) {
  const {api,c,language,alive}=ctx;
  const data=await api.libraryVocabulary();if(!alive())return;
  let items=data.items||[],recalling=ctx.location.intent==='recall',revealed=false;
  function paint() {
    if(!alive())return;
    const due=items.filter(x=>x.due),current=due[0];
    root.innerHTML=`<header class="page-intro"><div><small>${c.language}</small><h1>${c.wordsTitle}</h1><p>${c.wordsIntro}</p></div></header>${items.length?`<div class="language-summary"><span>${due.length} ${c.due}</span>${due.length&&!recalling?`<button class="primary" data-recall>${c.recallName} →</button>`:''}</div>`:''}${recalling?current?`<section class="recall-moment"><small>${c.recallName}</small><h2 lang="${language}">${esc(current.word)}</h2>${current.phonetic&&ctx.profile.pinyin!=='off'?`<p class="pinyin">${esc(current.phonetic)}</p>`:''}<blockquote lang="${language}">${esc(current.source_fragment||'')}</blockquote>${revealed?`<p>${esc(current.definition||current.translation_vi||'')}</p><div class="button-row"><button class="outline" data-grade="again">${c.again}</button><button class="primary" data-grade="got_it">${c.gotIt}</button></div><p class="meta">${c.recallTruth}</p>`:`<button class="primary" data-reveal>${c.showMeaning} →</button>`}<p role="status" data-recall-status></p></section>`:`<section class="empty"><h2>${c.allDone}</h2><a class="outline" href="${link('language')}">${c.language} →</a></section>`:items.length?`<section class="word-collection">${items.map(x=>`<article><small>${esc(x.focus_note||c.sourceContext)}</small><h2 lang="${language}">${esc(x.word)}</h2>${x.phonetic&&ctx.profile.pinyin!=='off'?`<p class="pinyin">${esc(x.phonetic)}</p>`:''}<blockquote lang="${language}">${esc(x.source_fragment||'')}</blockquote><details><summary>${c.meaning}</summary><p>${esc(x.definition||x.translation_vi||'')}</p></details></article>`).join('')}</section>`:`<section class="empty"><h2>${c.noWords}</h2><p>${c.noWordsNote}</p><a class="primary" href="#/">${c.discover} ↗</a></section>`}`;
    root.querySelector('[data-recall]')?.addEventListener('click',()=>{recalling=true;paint();});
    root.querySelector('[data-reveal]')?.addEventListener('click',()=>{revealed=true;paint();});
    root.querySelectorAll('[data-grade]').forEach(button=>button.onclick=async()=>{root.querySelectorAll('[data-grade]').forEach(x=>x.disabled=true);const output=root.querySelector('[data-recall-status]');output.textContent=c.saving;try{await ctx.mutate(()=>api.reviewLibraryVocabulary(current.word,button.dataset.grade));const updated=await api.libraryVocabulary();if(!alive())return;items=updated.items||[];revealed=false;paint();status(c.persisted);}catch{if(alive()){output.textContent=c.failedSave;root.querySelectorAll('[data-grade]').forEach(x=>x.disabled=false);}}});
  }paint();
}
export async function renderGrammar(root,ctx) {
  const {api,c,language,alive,memory}=ctx;
  if(!ctx.location.id) {
    const result=await api.grammarLibrary();if(!alive())return;
    const lessons=result.lessons||[];
    root.innerHTML=`<header class="page-intro"><div><small>${c.grammarName}</small><h1>${c.grammarTitle}</h1><p>${c.grammarNote}</p></div></header><div class="pattern-list">${lessons.map(x=>`<a href="${link('practice',{intent:'grammar',id:x.id})}"><small>${esc(x.level)}</small><h2 lang="${language}">${esc(x.title)}</h2><span>↗</span></a>`).join('')}</div>`;return;
  }
  const lesson=await api.grammarLesson(ctx.location.id);if(!alive())return;
  const examples=lesson.examples||[],id=`grammar:${lesson.id}`;
  root.innerHTML=`<div class="back-row"><a href="${link('practice',{intent:'grammar'})}">← ${c.grammarName}</a></div><header class="page-intro"><div><small>${esc(lesson.level)}</small><h1 lang="${language}">${esc(lesson.title)}</h1><p>${c.grammarNote}</p></div></header><section class="grammar-encounter"><div><h2>${c.example}</h2>${examples.map(x=>`<blockquote lang="${language}">${esc(x.target||x.en||x.zh||'')}${x.pinyin&&ctx.profile.pinyin!=='off'?`<small>${esc(x.pinyin)}</small>`:''}${ctx.support==='vi'&&x.vi?`<p lang="vi">${esc(x.vi)}</p>`:''}</blockquote>`).join('')}</div><div><h2>${c.yourExample}</h2><textarea rows="6" lang="${language}" maxlength="12000">${esc(memory.value.expressions[id]||'')}</textarea><p class="meta">${c.local}</p><a class="primary" href="${link('expression',{id})}">${c.develop} ↗</a></div></section>`;
  root.querySelector('textarea').oninput=event=>{memory.write(id,event.target.value);memory.enter({id,title:lesson.title,intent:'writing'});};
}
