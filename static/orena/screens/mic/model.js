/* Pure data for the Mic state sheet (frame 62, E2 §11): the six drawn states, each's icon tokens,
   title/body/steps copy keys and its action buttons, exactly as `orena-script.js`'s `MS` object
   defines them - nothing here invents a 7th state or a state-specific icon (the frame draws the
   same `mic` glyph in every state; only the disc's two colour tokens change).

   `textFallback` (blocked only) mirrors the source's own `textOK` branch: a host screen that offers
   no typed alternative to speaking (Scripted Pronunciation, Shadowing) passes `false`; every other
   caller leaves the default. No DOM here - scripts/test_orena_screen_mic.mjs exercises it directly. */

export const MIC_STATES = Object.freeze(['permission', 'blocked', 'notheard', 'noisy', 'provider', 'offline']);

export function micStateSpec(state, { textFallback = true } = {}) {
  if (!MIC_STATES.includes(state)) return null;
  if (state === 'permission') {
    return {
      iconBg: 'var(--accent-soft)', iconColor: 'var(--accent)',
      titleKey: 'permissionTitle', bodyKey: 'permissionBody', stepsKey: '',
      actions: [
        { key: 'allow', labelKey: 'permissionAllow', variant: 'primary' },
        { key: 'dismiss', labelKey: 'permissionDismiss', variant: 'secondary' },
      ],
    };
  }
  if (state === 'blocked') {
    return {
      iconBg: 'var(--red-soft)', iconColor: 'var(--red)',
      titleKey: 'blockedTitle', bodyKey: textFallback ? 'blockedBodyFallback' : 'blockedBodyNoFallback', stepsKey: 'blockedSteps',
      actions: [
        { key: 'retry', labelKey: 'blockedRetry', variant: 'primary' },
        textFallback
          ? { key: 'typeInstead', labelKey: 'blockedTypeInstead', variant: 'secondary' }
          : { key: 'close', labelKey: 'blockedClose', variant: 'secondary' },
      ],
    };
  }
  if (state === 'notheard') {
    return {
      iconBg: 'var(--amber-soft)', iconColor: 'var(--amber)',
      titleKey: 'notheardTitle', bodyKey: 'notheardBody', stepsKey: '',
      actions: [
        { key: 'tryagain', labelKey: 'notheardTryAgain', variant: 'primary' },
        { key: 'cancel', labelKey: 'notheardCancel', variant: 'secondary' },
      ],
    };
  }
  if (state === 'noisy') {
    return {
      iconBg: 'var(--amber-soft)', iconColor: 'var(--amber)',
      titleKey: 'noisyTitle', bodyKey: 'noisyBody', stepsKey: '',
      // Source order: "Keep this attempt" (secondary) drawn above "Record again" (primary).
      actions: [
        { key: 'keep', labelKey: 'noisyKeep', variant: 'secondary' },
        { key: 'recordagain', labelKey: 'noisyRecordAgain', variant: 'primary' },
      ],
    };
  }
  if (state === 'provider') {
    return {
      iconBg: 'var(--surface2)', iconColor: 'var(--muted)',
      titleKey: 'providerTitle', bodyKey: 'providerBody', stepsKey: '',
      actions: [
        { key: 'retry', labelKey: 'providerRetry', variant: 'primary' },
        { key: 'continue', labelKey: 'providerContinue', variant: 'secondary' },
      ],
    };
  }
  // offline
  return {
    iconBg: 'var(--surface2)', iconColor: 'var(--muted)',
    titleKey: 'offlineTitle', bodyKey: 'offlineBody', stepsKey: '',
    actions: [{ key: 'ok', labelKey: 'offlineOk', variant: 'primary' }],
  };
}

/* The one real signal mic-readiness.js reports → which of `micGate`'s two own states (never the
   four post-recording ones, which only a real recording/assessment attempt can determine) applies.
   `null` means "go ahead, no sheet needed". */
export function gateStateFor(readinessState) {
  if (readinessState === 'ready') return null;
  if (readinessState === 'denied' || readinessState === 'no_device' || readinessState === 'unsupported') return 'blocked';
  return null;
}
