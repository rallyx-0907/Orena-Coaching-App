/* The learner's speaking attempts as the SERVER keeps them (`GET /api/speech/attempts`, scoped to the account and
   the learning language), shaped for Attempt History and Speaking Summary - so both come back in a fresh browser,
   not only in the tab that made the take (D-110).

   Only a SERVER-VERIFIED score is shown or counted (D-108.3, D-103.4): an attempt whose pronunciation provenance is a
   stub ("stub-for-verification") or whose measurement is not `measured` still happened - it is listed - but it has
   no score, no accuracy, no fluency, and takes no part in "best" or "change". A figure with no real source is
   absent, never a zero. */

const num = (value) => (Number.isFinite(Number(value)) && value !== null && value !== '' ? Math.round(Number(value)) : null);
const unverified = (provenance) => !provenance || /stub|synthetic|unverified/i.test(String(provenance));

/* One server attempt -> the row shape the Speaking screens already share ({id, at, overall, accuracy, fluency}). */
export function attemptRow(item) {
  const pronunciation = item?.evidence?.pronunciation || {};
  const measured = pronunciation.score_kind === 'measured' && !unverified(item?.provenance?.pronunciation);
  const fluencyVerified = measured && !unverified(item?.provenance?.fluency);
  return {
    id: String(item?.id || ''),
    takeId: String(item?.take_id || ''),
    at: Date.parse(item?.created_at) || 0,
    assetId: String(item?.asset_id || ''),
    segmentId: String(item?.segment_id || ''),
    language: String(item?.language || ''),
    text: String(item?.transcript_text || ''),
    verified: measured,
    overall: measured ? num(item?.dimensions?.pronunciation) : null,
    accuracy: measured ? num(pronunciation.accuracy_score) : null,
    fluency: fluencyVerified ? num(item?.dimensions?.fluency) : null,
    server: true,
  };
}

/* The attempts of one line, newest first, or `null` when the server could not be read (the caller then shows only
   what this tab knows). */
export async function loadLineAttempts(api, { assetId = '', segmentId = '', limit = 50 } = {}) {
  try {
    const payload = await api.speakingAttempts(limit, assetId, segmentId);
    return (payload?.items || []).map(attemptRow).sort((a, b) => b.at - a.at);
  } catch {
    return null;
  }
}

/* Merge by persisted identity, never by time: several real takes can happen within 90 seconds. */
export function mergeAttempts(tabTakes, serverRows) {
  const sameAttempt = (take, row) => (take.attemptId && String(take.attemptId) === row.id) || (row.takeId && take.id === row.takeId);
  const tab = (tabTakes || []).map((take) => {
    const verified = (serverRows || []).find(row => sameAttempt(take, row));
    return { ...take, verified: verified?.verified ?? false, overall: verified?.overall ?? null,
      accuracy: verified?.accuracy ?? null, fluency: verified?.fluency ?? null };
  });
  const extra = (serverRows || []).filter((row) => !tab.some((take) =>
    sameAttempt(take, row)));
  return [...tab, ...extra].sort((a, b) => (b.at || 0) - (a.at || 0));
}

/* The learner's speaking attempts since an instant (Speaking Summary's "this session" is a window the server keeps). */
export async function loadAttemptsSince(api, sinceIso, limit = 100) {
  try {
    const payload = await api.speakingAttempts(limit, '', '', sinceIso);
    return (payload?.items || []).map(attemptRow).sort((a, b) => a.at - b.at);
  } catch {
    return null;
  }
}
