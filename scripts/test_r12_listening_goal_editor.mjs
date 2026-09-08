/* R12: the Listening screen exposes its goal editor.
 *
 * This is the second half of the Home listening-goal handoff. Home's half -
 * that the habit card renders real state and navigates to Listening - lives in
 * test_r12_listening_habit_home.mjs and is a CI gate.
 *
 * This half is NOT in CI, and the reason is recorded rather than hidden: it
 * fails at HEAD and failed before the Home migration. The harness renders the
 * Listening screen without resolving its library load, so the screen is still
 * showing "Preparing your Listening library…" when the assertion runs, and the
 * goal editor legitimately does not exist yet. The fix belongs to the Listening
 * screen's test harness, not to Home, so it is kept visible here instead of
 * being deleted or quietly weakened.
 */

import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderListening} from '../static/becoming/screens/listening.js';
import {LISTEN_GOAL_KEY,LISTEN_TIME_KEY} from '../static/becoming/domain/listening-habit.js';

const storage=new Map();
globalThis.localStorage={
  getItem:key=>storage.get(key)??null,
  setItem:(key,value)=>storage.set(key,String(value)),
  removeItem:key=>storage.delete(key),
};
globalThis.sessionStorage={getItem:()=>null,setItem(){},removeItem(){}};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},body:{classList:{add(){},remove(){}}}};
globalThis.window={dispatchEvent(){},setInterval(){return 1;},clearInterval(){}};
globalThis.location={hash:'#/listen'};
globalThis.HashChangeEvent=class {};
if(!globalThis.Element)globalThis.Element=Object;
if(!globalThis.HTMLIFrameElement)globalThis.HTMLIFrameElement=class {};

function listeningRoot(){
  let html='';
  return {
    get innerHTML(){return html;},
    set innerHTML(value){html=String(value||'');},
    querySelector(selector){
      if(selector.startsWith('[data-listening-view=')){
        const id=selector.match(/"([^"]+)"/)?.[1];
        return id&&html.includes(`data-listening-view="${id}"`)?{}:null;
      }
      return null;
    },
    querySelectorAll(){return [];},
    addEventListener(){},
  };
}

const original={dashboard:api.dashboard};
try{
  api.dashboard=async()=>({});
  storage.clear();
  storage.set(LISTEN_TIME_KEY,JSON.stringify({}));
  storage.set(LISTEN_GOAL_KEY,JSON.stringify({daily:30}));
  state.language='en';
  state.supportLanguage='en';

  const root=listeningRoot();
  await renderListening(root,{
    loadListeningProgress:async()=>({items:[]}),
    loadShadowingProgress:async()=>({items:[]}),
  });
  assert.match(root.innerHTML,/data-edit-goals/,
    'Listening should expose its goal editor once its library has loaded');
  assert.ok(root.innerHTML.includes('Edit goals'));
}finally{
  Object.assign(api,original);
}

console.log('R12 Listening goal editor: PASS');
