/* The sheet a Free learner meets on any voice entry (the desk rail's mic, the full-screen voice, the Home and panel voice
   rows) or when the server refuses a voice session or its renewal (403 `feature_not_in_plan`, `context.feature`
   `orena.voice`; AGENT_CONTRACT §2.1 and §9, v11, D-235). Voice chat with Orena is a Plus and Pro benefit; text chat and
   Speaking practice are unchanged.

   It reuses the Mic state sheet's shape (screens/mic/sheet.js, `.s-mic`): one centred sheet with a sentence and one primary
   button, closed by the scrim or Escape. The button goes to the plans (`pricing`, the route every plan limit already
   uses). Nothing else is drawn: the design has no voice-upsell frame, so this is the existing sheet and the existing route
   (docs/project/UI_BACKEND_GAPS.md). */
import { openSheet } from '../../kit/overlay.js';
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { href } from '../../shell/routes.js';
import { t } from './copy.js';

export async function openVoiceUpsell() {
  await useStyles('screens/mic/mic.css');
  return openSheet({
    label: t('voiceNotInPlan'),
    className: 's-mic',
    scrim: true,
    render(element, handle) {
      mount(element, html`<div class="s-mic__body">${t('voiceNotInPlan')}</div>
        <div class="s-mic__actions"><button type="button" class="s-mic__action s-mic__action--primary" data-voice-plans>${t('voiceSeePlans')}</button></div>`);
      element.querySelector('[data-voice-plans]')?.addEventListener('click', () => {
        handle.close();
        location.hash = href('pricing');
      });
      return null;
    },
  });
}
