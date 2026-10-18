/* Light consent, client side (D-229 clause 5, D-233): what the server holds about this account's consent, and the two
   writes. The server answers `consent: { stored, consent_required, consent_version, voice_consent }` in the session
   bootstrap and in every consent call. `stored: false` means the server cannot hold a record (its database has not
   taken the consent columns yet): nothing is required, nothing is asked, and nothing is blocked - the client behaves as
   it did before consent existed.

   - `consentRequired()`: the one-time "I agree" sheet is due (an account with no record).
   - `voiceConsent()`: true / false is the learner's answer; null is "unknown or not kept" and never gates anything. */
import { request } from '../infrastructure/api.js';

let state = { required: false, voice: null };

function parse(body) {
  if (!body || typeof body !== 'object' || body.stored !== true) return { required: false, voice: null };
  return { required: body.consent_required === true, voice: typeof body.voice_consent === 'boolean' ? body.voice_consent : null };
}

/* The bootstrap's `consent` object (or anything else: a server without it gives the quiet state). */
export function setConsentState(body) {
  state = parse(body);
  return state;
}

export const consentRequired = () => state.required;
export const voiceConsent = () => state.voice;

/* The sign-out of a learner leaves nothing of their answers for the next one on this page. */
export function clearConsentState() {
  state = { required: false, voice: null };
}

/* "I agree": records the current Terms / Privacy version with the interface language. Throws on a failed request; the
   server saying it cannot keep a record is not a failure (the sheet simply does not come back this session). */
export async function acceptConsent(language, fetcher = request) {
  const body = await fetcher('/api/account-settings/consent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language: String(language || '') }),
  });
  state = { ...parse(body), required: false };
  return true;
}

/* The voice answer from the server, or null when it cannot be kept or read. A 401 is rethrown. */
export async function readVoiceConsent(fetcher = request) {
  try {
    const body = await fetcher('/api/account-settings/consent');
    state = { ...state, voice: parse(body).voice };
    return state.voice;
  } catch (error) {
    if (error?.status === 401) throw error;
    return null;
  }
}

/* Writes the learner's voice answer. Returns the stored boolean, or null when the server cannot keep it. Throws on a
   failed request so the caller can put the switch back. */
export async function writeVoiceConsent(granted, fetcher = request) {
  const body = await fetcher('/api/account-settings/voice-consent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ granted: Boolean(granted) }),
  });
  state = { ...state, voice: parse(body).voice };
  return state.voice;
}

export const __reset = clearConsentState;
