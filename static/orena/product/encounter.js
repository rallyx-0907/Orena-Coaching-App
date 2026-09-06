import {activeCanonicalSegment} from '../capabilities/transcript-timeline.js';
// One content focus is shared by Follow and every practice intention. No
// destination-specific session, return route, or duplicated media payload.
export function encounter(payload,supportLanguage) {
  const segments=(payload?.transcript?.segments||[]).map(segment=>({...segment,spoken_text:payload.catalog?.spoken_text_by_segment?.[segment.segment_id]||segment.original_text}));
  let focus=segments[0]?.segment_id||null;
  return {
    payload,segments,
    get current(){return segments.find(x=>x.segment_id===focus)||null;},
    select(id){if(!segments.some(x=>x.segment_id===id))return false;focus=id;return true;},
    follow(time){const current=activeCanonicalSegment(segments,time);if(current)focus=current.segment_id;return current;},
    meaning(id=focus){return (payload.translations||[]).find(x=>x.segment_id===id&&x.target_language===supportLanguage)?.translated_meaning||null;},
  };
}
