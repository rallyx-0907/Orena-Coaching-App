export const practiceIntentions=['dictation','shadowing','speaking','writing','grammar','recall'];
export function route(hash='') {
  const [path,query]=String(hash).replace(/^#\/?/,'').split('?');
  const q=new URLSearchParams(query||'');
  return {page:['practice','encounter','content','language','expression','preferences'].includes(path)?path:'discover',id:q.get('id')||'',intent:practiceIntentions.includes(q.get('intent'))?q.get('intent'):null};
}
export function link(page='discover',{id='',intent=null}={}) {
  const query=new URLSearchParams();if(id)query.set('id',id);if(practiceIntentions.includes(intent))query.set('intent',intent);
  return `#/${page==='discover'?'':page}${query.size?'?'+query:''}`;
}
export function supports(content,intent) {
  if(!intent)return true;
  if(['dictation','shadowing'].includes(intent))return ['audio','video','embed'].includes(content.kind||content.playback_kind);
  return true;
}

export function continuationLink(item) {
  if(item.intent==='writing'||item.id.startsWith('expression:'))return link('expression',{id:item.id});
  if(item.id.startsWith('grammar:'))return link('practice',{id:item.id.slice(8),intent:'grammar'});
  return link('encounter',{id:item.id,intent:item.intent});
}
export function sourceLink(id) {
  if(id.startsWith('expression:'))return link('practice');
  if(id.startsWith('grammar:'))return link('practice',{id:id.slice(8),intent:'grammar'});
  return link('encounter',{id});
}
