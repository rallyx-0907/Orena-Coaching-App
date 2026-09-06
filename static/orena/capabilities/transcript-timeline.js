export function activeCanonicalSegment(segments,timeMs){
  const values=Array.isArray(segments)?segments:[];
  const time=Number(timeMs);
  if(!values.length||!Number.isFinite(time))return null;

  let low=0;
  let high=values.length-1;
  let index=-1;

  while(low<=high){
    const mid=(low+high)>>1;
    const start=Number(values[mid]?.start_ms);
    if(Number.isFinite(start)&&start<=time){
      index=mid;
      low=mid+1;
    }else{
      high=mid-1;
    }
  }

  if(index<0)return null;

  const current=values[index];
  const ownEnd=Number(current?.end_ms);
  const nextStart=index+1<values.length?Number(values[index+1]?.start_ms):null;
  const effectiveEnd=Number.isFinite(nextStart)
    ?Math.min(Number.isFinite(ownEnd)?ownEnd:nextStart,nextStart)
    :ownEnd;

  if(Number.isFinite(effectiveEnd)&&time>=effectiveEnd)return null;
  return current;
}
