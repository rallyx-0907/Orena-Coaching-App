import { esc, focusRegion } from './html.js';
import { judgementLabel } from './understanding.js';

/* Guidance on a spoken response, kept apart from the evidence panel on purpose.

   What the stack measured - recognition confidence, and pronunciation when a
   provider is configured - lives in `voiceEvidence`. This is the other thing,
   and it is a different kind of claim: a reading of the words recognition
   returned, not of the audio. The heading says so, because a learner who
   cannot tell measurement from opinion cannot judge either. */

function quoted(c, item, language, { alternative = false } = {}) {
  return `<article class="coaching-point">
    <blockquote lang="${esc(language)}">${esc(item.quote)}</blockquote>
    ${alternative && item.judgement ? `<small>${esc(judgementLabel(c, item.judgement))}</small>` : ''}
    <p>${esc(item.why)}</p>
    ${
      alternative && item.instead
        ? `<p class="coaching-instead" lang="${esc(language)}">${esc(item.instead)}</p>`
        : ''
    }
  </article>`;
}

export function spokenCoaching(c, result, language) {
  const carried = result?.carried || [];
  const landed = result?.landed_differently || [];
  if (!result?.available || (!carried.length && !landed.length)) return '';
  return `<section class="spoken-coaching">
    <h3>${esc(c.coachingTitle)}</h3>
    <p class="meta">${esc(c.coachingNote)}</p>
    ${
      carried.length
        ? `<h4>${esc(c.coachingCarried)}</h4>${carried.map((x) => quoted(c, x, language)).join('')}`
        : ''
    }
    ${
      landed.length
        ? `<h4>${esc(c.coachingLanded)}</h4>${landed
            .map((x) => quoted(c, x, language, { alternative: true }))
            .join('')}`
        : ''
    }
    ${
      result.another_way
        ? `<h4>${esc(c.coachingAnotherWay)}</h4><p lang="${esc(language)}">${esc(result.another_way)}</p>`
        : ''
    }
    ${
      result.next_attempt
        ? `<h4>${esc(c.coachingNextAttempt)}</h4><p>${esc(result.next_attempt)}</p>`
        : ''
    }
  </section>`;
}

/* Asked for after the take is saved, so guidance never delays the learner's own
   words or the evidence. When it does not arrive, the section says so and
   nothing is invented in its place. */
export async function loadSpokenCoaching(host, ctx, { transcript, situation }) {
  const { c, api, language, support, alive } = ctx;
  host.innerHTML = `<p class="meta">${esc(c.coachingWorking)}</p>`;
  try {
    const result = await api.spokenResponseCoaching({
      transcript: transcript.slice(0, 2400),
      source_language: language,
      target_language: support,
      situation: String(situation || '').slice(0, 1200),
    });
    if (!alive() || !host.isConnected) return;
    const html = spokenCoaching(c, result, language);
    host.innerHTML =
      html || `<p class="meta">${esc(c.coachingUnavailable)}</p>`;
    if (html) focusRegion(host.querySelector('h3'));
  } catch {
    if (alive() && host.isConnected)
      host.innerHTML = `<p class="meta">${esc(c.coachingUnavailable)}</p>`;
  }
}
