const TOKEN_RE=/\p{Script=Han}|[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu;
export function transcriptTokens(value){
  const text=String(value??''); const tokens=[]; let cursor=0;
  for(const match of text.matchAll(TOKEN_RE)){
    const index=match.index??0;
    if(index>cursor)tokens.push({text:text.slice(cursor,index),word:false});
    tokens.push({text:match[0],word:true});
    cursor=index+match[0].length;
  }
  if(cursor<text.length)tokens.push({text:text.slice(cursor),word:false});
  return tokens;
}
