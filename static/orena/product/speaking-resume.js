/* Navigation projection over the existing continuation record. No learner evidence or
   new persistence authority: source access/language are checked by the destination. */
export function speakingResumeTarget(entry) {
  const id = String(entry?.id || '');
  const intent = entry?.intent;
  if (!['speaking', 'speaking_compare'].includes(intent)) return null;
  if (!/^(media:|speak:).+/.test(id)) return null;
  const segment = String(entry.segment || '');
  return {kind:'speak', routeId:intent==='speaking_compare'?'compare':'speak',
    params:{id}, query:segment?{segment}:{}};
}
