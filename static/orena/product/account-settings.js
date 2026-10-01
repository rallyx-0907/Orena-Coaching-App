/* The account-wide choices and the per-language profile writes, kept on the server (D4 I2, I3, I3b,
   I13; D-104 H-17).

   Three scalars follow the person, not the language: the learning language, the interface language
   and the weekly goal. The server versions them with ONE opaque token (`settings_version`). Every
   write here carries the token it just read, echoed verbatim - never parsed, never built from a
   clock - and a 409 means another device moved first: read again and re-apply once, then give up
   quietly (the device keeps the choice; the learner is never told something was saved that was not).

   Where the account has no row to hold settings (`stored: false`, authentication-disabled local
   development) nothing is sent with a token and nothing is claimed. */
import { api } from '../infrastructure/api.js';

async function readSettings() {
  try {
    return await api.accountSettings();
  } catch {
    return null;
  }
}

/* Run `write(version)` against a fresh token; on 409 read again and run it once more. */
async function withToken(write) {
  for (let attempt = 0; ; attempt += 1) {
    const current = await readSettings();
    const version = current?.stored ? current.settings_version : undefined;
    try {
      return await write(version);
    } catch (error) {
      if (error?.status !== 409 || version === undefined || attempt >= 1) throw error;
    }
  }
}

/* Choose the learning language: switches the session and stores the choice on the account. */
export function selectLearningLanguage(code) {
  return withToken((version) => api.setLanguage(code, version));
}

/* Store account-wide scalars (`interface_language`, `weekly_goal_days`, `learning_language`). A
   device with no account row resolves to null and sends nothing. */
export function saveAccountSettings(changes) {
  return withToken((version) => (version === undefined ? null : api.patchAccountSettings({ expected_settings_version: version, ...changes })));
}

/* Reconcile the interface language at boot: the device value is the first-paint cache. When the
   device has none the account's is used; when the device has one and the account none, the device's
   seeds the first save. Returns the code to apply on this device, or ''. */
export async function reconcileInterface(account, deviceChoice) {
  if (!account?.stored) return '';
  if (!deviceChoice && account.interface_language) return account.interface_language;
  if (deviceChoice && !account.interface_language) {
    saveAccountSettings({ interface_language: deviceChoice }).catch(() => {});
  }
  return '';
}

/* Review settings live on the per-language profile row, written against the profile's version
   (H2's conditional write): a 409 re-reads the profile and re-applies once. */
export async function saveReviewSettings(change, profileVersion, onProfile) {
  // ONLY what the learner changed is sent (a toggled mode, a changed limit): the server merges it into what it
  // stores, so a device that has not read the server yet, or that is stale, can never write its defaults or
  // another device's older view over a value the learner did not touch. A 409 re-reads the profile and re-applies
  // the same change to the fresh one.
  const body = {};
  if (Number.isFinite(change?.newPerDay)) body.review_new_per_day = change.newPerDay;
  if (Number.isFinite(change?.limitPerDay)) body.review_limit_per_day = change.limitPerDay;
  const modes = Object.fromEntries(['typing', 'cloze', 'dictation'].filter((name) => typeof change?.modes?.[name] === 'boolean').map((name) => [name, change.modes[name]]));
  if (Object.keys(modes).length) body.review_modes = modes;
  if (!Object.keys(body).length) return null;
  let version = profileVersion ?? '';
  for (let attempt = 0; ; attempt += 1) {
    try {
      const next = await api.patchLearnerProfile({ expected_version: version, ...body });
      onProfile?.(next);
      return next;
    } catch (error) {
      if (error?.status !== 409 || attempt >= 1) throw error;
      const fresh = await api.learnerProfile();
      onProfile?.(fresh);
      version = fresh?.version ?? '';
    }
  }
}

/* The server's stored review settings as the device shape, or null when none is stored. */
export function reviewFromProfile(profile) {
  if (!profile) return null;
  const { review_new_per_day: newPerDay, review_limit_per_day: limitPerDay, review_modes: modes } = profile;
  if (newPerDay == null && limitPerDay == null && !modes) return null;
  return { ...(newPerDay != null ? { newPerDay } : {}), ...(limitPerDay != null ? { limitPerDay } : {}), ...(modes ? { modes } : {}) };
}
