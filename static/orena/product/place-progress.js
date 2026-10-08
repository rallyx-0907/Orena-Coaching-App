/* One truth for "how far through is this" (LEX-082, LEX-083). Every surface that shows a percent for
   a continuation place - Discover cards, Content Detail, Today - reads it through here.

   A place is {index, total, within?}. A flat text or a media item is "1 of 1" (the continuation record
   needs a pair), so its index/total says nothing about progress: only `within`, how far into it the
   learner really got, does. A book's chapter is a real position among `total` chapters, so the share
   of the whole is the chapters before it plus `within` of this one. A place with nothing measured is a
   place the learner opened and has not moved through: null, never an invented 0% or 100%. */
export function placePercent(place) {
  const index = Number(place?.index);
  const total = Number(place?.total);
  if (!Number.isInteger(index) || !Number.isInteger(total) || index < 1 || total < 1 || index > total) return null;
  const within = Number(place?.within);
  const hasWithin = place?.within != null && Number.isFinite(within);
  const into = hasWithin ? Math.max(0, Math.min(100, within)) / 100 : 0;
  if (total === 1) return hasWithin && into > 0 ? Math.max(1, Math.round(into * 100)) : null;
  const share = ((index - 1 + into) / total) * 100;
  return share > 0 ? Math.max(1, Math.min(100, Math.round(share))) : null;
}

/* A book's place is its furthest chapter (its chapters are "book:<bookId>:<chapterId>"; the list is newest
   first, so among chapters at the same position the newest wins). Re-opening chapter 1 to look something up
   does not move the learner back to the start. Reduced to what a resume strip needs. */
export function bookPlace(continuation, bookId) {
  const prefix = `book:${bookId}:`;
  let entry = null;
  for (const item of Array.isArray(continuation) ? continuation : []) {
    if (!String(item?.id || '').startsWith(prefix)) continue;
    if (!entry || (Number(item.place?.index) || 0) > (Number(entry.place?.index) || 0)) entry = item;
  }
  if (!entry) return { started: false, chapterId: '', percent: null, index: 0, total: 0, title: '' };
  const percent = placePercent(entry.place);
  return {
    started: true,
    chapterId: String(entry.id).slice(prefix.length),
    percent,
    index: Number(entry.place?.index) || 0,
    total: Number(entry.place?.total) || 0,
    within: Number.isFinite(entry.place?.within) ? entry.place.within : null,
    title: String(entry.title || ''),
  };
}
