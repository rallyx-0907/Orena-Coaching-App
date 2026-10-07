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
    /* What the account kept of the assessment itself (never audio, D-076): the heard text, the line's
       completeness and prosody, each word's score, miscue and sounds. Word timing was never stored. */
    evidence: measured ? evidenceOf(item, pronunciation) : null,
    server: true,
  };
}

const isNone = (type) => ['', 'none'].includes(String(type || 'None').trim().toLowerCase());

function evidenceOf(item, pronunciation) {
  return {
    heard: String(item?.evidence?.recognized_text || item?.transcript_text || ''),
    completeness: num(pronunciation.completeness_score),
    prosody: num(pronunciation.prosody_score),
    words: (Array.isArray(pronunciation.words) ? pronunciation.words : [])
      .filter((word) => String(word?.word || '').trim() && String(word.error_type || '').toLowerCase() !== 'insertion')
      .map((word) => ({
        text: String(word.word).trim(),
        score: num(word.accuracy_score),
        errorType: isNone(word.error_type) ? 'None' : String(word.error_type),
        phonemes: (Array.isArray(word.phonemes) ? word.phonemes : [])
          .filter((unit) => String(unit?.phoneme || '').trim())
          .map((unit) => ({ label: String(unit.phoneme).trim(), score: num(unit.accuracy_score) })),
      })),
  };
}

/* One kept assessment as the `pronunciationView()`-shaped object every Speaking screen reads - for a
   past attempt reopened from the account. Scores, miscues and sounds are the provider's; where a word
   sat in the take is unknown (`offsetKnown: false`), and so are the pace and the line's own timing. */
export function viewOfEvidence(take) {
  const evidence = take?.evidence;
  if (!evidence) return null;
  const words = evidence.words.map((word, index) => {
    const weak = word.phonemes.filter((unit) => unit.score != null).reduce((low, unit) => (low && low.score <= unit.score ? low : unit), null);
    return {
      index,
      text: word.text,
      pinyin: '',
      score: word.score ?? 0,
      scoreMeasured: word.score != null,
      scoreKnown: word.score != null,
      flagged: !isNone(word.errorType),
      errorType: word.errorType,
      weakest: weak ? { label: weak.label, score: weak.score } : null,
      phonemes: word.phonemes,
      syllables: [],
      offsetMs: null,
      durationMs: null,
      offsetKnown: false,
      toneTarget: [],
      toneActual: [],
    };
  });
  return {
    measured: true,
    reduced: false,
    synthetic: false,
    overall: take.overall ?? 0,
    accuracy: take.accuracy ?? 0,
    fluency: take.fluency ?? 0,
    fluencyMeasured: take.fluency != null,
    completeness: evidence.completeness ?? 0,
    prosody: evidence.prosody,
    timing: null,
    heard: evidence.heard,
    passedCount: words.filter((word) => !word.flagged).length,
    totalCount: words.length,
    words,
  };
}

/* The attempts Compare can open for one line, newest first: this tab's own takes, untouched (they
   hold the audio and the full assessment), each carrying what the account kept of it when the account
   has it; then every verified attempt only the account remembers (no audio - D-076 - but its scores,
   transcript and word detail). An attempt with no verified score has nothing to review and is left
   out. Matched by persisted identity, never by time. */
export function reviewableAttempts(tabTakes, serverRows) {
  const rows = serverRows || [];
  const sameAttempt = (take, row) => (take.attemptId && String(take.attemptId) === row.id) || (row.takeId && take.id === row.takeId);
  const tab = (tabTakes || []).map((take) => {
    const kept = rows.find((row) => sameAttempt(take, row));
    return kept?.evidence && !take.evidence ? { ...take, evidence: kept.evidence } : take;
  });
  const extra = rows.filter((row) => row.verified && !tab.some((take) => sameAttempt(take, row)));
  return [...tab, ...extra].sort((a, b) => (b.at || 0) - (a.at || 0));
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

/* D-142: the learner's live practice session (`GET /api/speech/attempts?session=current`), kept by the server so a second
   tab or device sees the same one. `null` when the server does not offer it (the flag is off, or the read failed) - the
   caller then keeps the client ledger and the seven-day window exactly as before. `meta` is null when no session is
   live (idle for over 30 minutes). */
/* Three outcomes, never blurred:
   - `null`: the server says, explicitly, that the feature is off (404, category `practice_session_disabled`) - the caller
     keeps the client ledger and the seven-day window exactly as before;
   - `{ meta, rows }`: the session (`meta` is null when none is live, idle for over 30 minutes);
   - a thrown `speaking_session_unavailable` for any other failure (5xx, network, malformed payload): the caller shows its
     unavailable state and never falls back to the client notion, which could present cross-device data that is wrong. */
export const SESSION_DISABLED_CATEGORY = 'practice_session_disabled';

export async function loadCurrentSession(api, limit = 100) {
  let payload;
  try {
    payload = await api.speakingCurrentSession(limit);
  } catch (error) {
    if (error && error.status === 404 && error.category === SESSION_DISABLED_CATEGORY) return null;
    throw new Error('speaking_session_unavailable');
  }
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.items)) throw new Error('speaking_session_unavailable');
  return { meta: payload.session || null, rows: payload.items.map(attemptRow).sort((a, b) => a.at - b.at) };
}
