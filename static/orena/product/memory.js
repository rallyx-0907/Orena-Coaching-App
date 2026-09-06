// Content relationships and unfinished work, scoped to an authenticated owner.
// Practice evidence remains in the existing PostgreSQL-backed capability APIs.
const volatile=new Map();
export function learnerMemory(storage,owner,language) {
  const key=`orena.encounters.v1:${encodeURIComponent(owner)}:${language}`;
  let available=true,value={imports:[],kept:[],continuation:[],expressions:{},answers:{}};
  try {
    const parsed=volatile.get(key)||JSON.parse(storage.getItem(key)||'null');
    if(parsed&&typeof parsed==='object') {
      value.imports=(Array.isArray(parsed.imports)?parsed.imports:[]).filter(x=>x&&x.origin==='imported'&&x.language===language&&typeof x.id==='string'&&typeof x.title==='string'&&typeof x.text==='string'&&x.text.length<=12000).slice(0,20);
      value.kept=(Array.isArray(parsed.kept)?parsed.kept:[]).filter(x=>typeof x==='string').slice(0,100);
      value.continuation=(Array.isArray(parsed.continuation)?parsed.continuation:[]).filter(x=>x&&typeof x.id==='string'&&typeof x.title==='string').slice(0,20);
      for(const field of ['expressions','answers'])value[field]=Object.fromEntries(Object.entries(parsed[field]||{}).filter(([k,v])=>!['__proto__','constructor','prototype'].includes(k)&&typeof v==='string').slice(-100).map(([k,v])=>[k,v.slice(0,12000)]));
    }
    if(volatile.has(key))available=false;
  } catch {available=false;}
  const save=()=>{try{storage.setItem(key,JSON.stringify(value));volatile.delete(key);available=true;}catch{volatile.set(key,value);available=false;}return available;};
  return {
    get value(){return value;},get available(){return available;},
    keep(id){value.kept=value.kept.includes(id)?value.kept.filter(x=>x!==id):[id,...value.kept].slice(0,100);return save();},
    enter({id,title,segment='',intent=null,source_url=''}) {value.continuation=[{id,title,segment,intent,source_url},...value.continuation.filter(x=>x.id!==id)].slice(0,20);return save();},
    write(id,text,field='expressions'){if(!['expressions','answers'].includes(field)||['__proto__','constructor','prototype'].includes(id))throw Error('Invalid draft');value[field][id]=String(text).slice(0,12000);return save();},
    add({title,text}) {if(value.imports.length>=20||!title?.trim()||!text?.trim()||text.length>12000)throw Error('Invalid text');const item={id:`text:${crypto.randomUUID()}`,title:title.trim().slice(0,120),text:text.trim(),language,origin:'imported',kind:'text'};value.imports.unshift(item);save();return item;},
    remove(id){value.imports=value.imports.filter(x=>x.id!==id);value.kept=value.kept.filter(x=>x!==id);value.continuation=value.continuation.filter(x=>x.id!==id);delete value.expressions[id];save();},
  };
}
