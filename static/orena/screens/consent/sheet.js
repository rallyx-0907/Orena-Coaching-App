/* The two consent sheets (D-229 clause 5, D-233), both in the Mic state sheet's own shape (frame 62: the centred icon
   disc, title, one body paragraph and stacked buttons) - the kit's sheet, its classes and its styles; nothing new is drawn.

   - `openConsentSheet(ctx)`: due once for an account with no consent record (`product/consent.js` `consentRequired()`):
     the Terms and Privacy Policy as links, and "I agree". It has no other way out than the scrim and Escape, which close
     it without recording: the sheet comes back at the next start of the app.
   - `ensureVoiceConsent(ctx)`: asked just in time, before the first use of the microphone. Resolves true when the
     learner allows (or when the server keeps no answer, so nothing is asked), false for "Not now" or a failed save. */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { languages as copyLanguages } from '../../copy/index.js';
import { acceptConsent, consentRequired, markVoiceRefused, voiceConsent, writeVoiceConsent } from '../../product/consent.js';
import { legalHref, legalLabel } from '../../legal/links.js';
import { t } from './copy.js';

const DISC = { iconBg: 'var(--accent-soft)', iconColor: 'var(--accent)' };

function body({ iconName, title, text, links = [], actions }) {
  return html`
    <div class="s-mic__icon" style="background:${DISC.iconBg};color:${DISC.iconColor}">${raw(icon(iconName, { size: 28 }))}</div>
    <div class="s-mic__title">${title}</div>
    <div class="s-mic__body">${text}</div>
    ${links.length ? html`<div class="s-mic__body">${links.map((link, index) => html`${index ? ' · ' : ''}<a href="${link.href}" target="_blank" rel="noopener" style="color:var(--text);text-decoration:underline">${link.label}</a>`)}</div>` : ''}
    <div class="s-mic__actions">${actions.map((action) => html`<button type="button" class="s-mic__action s-mic__action--${action.variant}" data-action="${action.key}">${action.label}</button>`)}</div>
  `;
}

async function open(ctx, { label, view, onAction, onClose }) {
  await useStyles('screens/mic/mic.css');
  if (ctx?.isCurrent && !ctx.isCurrent()) return null;
  return openSheet({
    label,
    className: 's-mic',
    scrim: true,
    onClose,
    render(element, handle) {
      mount(element, body(view));
      element.querySelectorAll('[data-action]').forEach((button) => {
        button.addEventListener('click', () => void onAction(button.dataset.action, handle));
      });
      return null;
    },
  });
}

export async function openConsentSheet(ctx = {}) {
  if (!consentRequired()) return null;
  const ui = copyLanguages().ui;
  return open(ctx, {
    label: t('consentTitle'),
    view: {
      iconName: 'file-text',
      title: t('consentTitle'),
      text: t('consentBody'),
      links: [
        { href: legalHref('/terms'), label: legalLabel(t('consentTerms'), ui) },
        { href: legalHref('/privacy'), label: legalLabel(t('consentPrivacy'), ui) },
      ],
      actions: [{ key: 'agree', label: t('consentAgree'), variant: 'primary' }],
    },
    onAction: async (key, handle) => {
      if (key !== 'agree') return;
      try {
        await acceptConsent(ui);
        handle.close();
      } catch (error) {
        // A 401 already reached the signed-out handling in request(); no second message.
        if (error?.status !== 401) toast(t('voiceSaveError'));
      }
    },
  });
}

/* A request the server refused with 403 `voice_consent_required` (infrastructure/api.js): the answer is "no" from now on,
   so the same question is asked at once. One sheet at a time. */
let asking = false;
export function onVoiceConsentRefused(ctx = {}) {
  markVoiceRefused();
  if (asking) return Promise.resolve(false);
  asking = true;
  return ensureVoiceConsent(ctx).finally(() => { asking = false; });
}

/* true: go on (allowed, or nothing to ask). false: do not record. */
export function ensureVoiceConsent(ctx = {}) {
  if (voiceConsent() !== false) return Promise.resolve(true);
  return new Promise((resolve) => {
    let settled = false;
    const settle = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    open(ctx, {
      label: t('voiceTitle'),
      view: {
        iconName: 'mic',
        title: t('voiceTitle'),
        text: t('voiceBody'),
        actions: [
          { key: 'allow', label: t('voiceAllow'), variant: 'primary' },
          { key: 'later', label: t('voiceLater'), variant: 'secondary' },
        ],
      },
      onClose: () => settle(false), // the scrim or Escape: not allowed, nothing records
      onAction: async (key, handle) => {
        if (key === 'later') {
          settle(false);
          handle.close();
          return;
        }
        try {
          const stored = await writeVoiceConsent(true);
          settle(stored !== false);
          handle.close();
        } catch (error) {
          if (error?.status !== 401) toast(t('voiceSaveError'));
        }
      },
    }).then((handle) => {
      if (!handle) settle(false);
    }, () => settle(false));
  });
}
