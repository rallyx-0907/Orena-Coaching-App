import { esc } from './html.js';

/* The Speaking envelope already separates what was measured from what was
   derived, and the surface used to collapse all of it into one percentage.
   This renders the separation the evaluator makes, and never presents a
   derived suggestion as though something had measured it.

   Nothing here invents a dimension. A dimension the stack could not measure
   says so, with the reason the envelope gives. */

// Provenance the evaluator can report, and what it honestly means on screen.
const SOURCE_KEYS = {
  speech_asr: 'sourceAsr',
  deterministic_reference_alignment: 'sourceAlignment',
  synthetic_demo: 'sourceDemo',
  not_assessed: 'sourceNotAssessed',
  not_applicable: 'sourceNotApplicable',
};

export function sourceLabel(c, provenance) {
  if (!provenance) return c.notMeasured;
  return c[SOURCE_KEYS[provenance]] || `${c.sourceProvider}: ${provenance}`;
}

/* Three states, not two. A dimension was measured, or it could have been and
   was not, or it does not apply to what the learner was asked to do. Free
   expression has no line to match, and reporting that as "not measured" would
   describe a gap in the stack rather than the truth about the task. */
function dimensionRow(c, key, value, provenance) {
  const measured = value !== null && value !== undefined;
  const inapplicable = !measured && provenance === 'not_applicable';
  return `<div class="voice-dimension"${measured ? '' : inapplicable ? ' data-inapplicable' : ' data-unmeasured'}>
    <dt>${esc(c[`dimension_${key}`] || key)}</dt>
    <dd><b>${measured ? esc(String(value)) : esc(inapplicable ? c.notApplicable : c.notMeasured)}</b><small>${esc(sourceLabel(c, provenance))}</small></dd>
  </div>`;
}

/* `next_steps` are rules over the evidence, not a measurement and not a model's
   opinion. They are labelled as guidance so a learner can tell the difference
   between "this was measured" and "this is what to try next". */
function nextStep(c, step) {
  const words = (step.words || []).filter(Boolean);
  const label = c[`step_${step.kind}`] || '';
  if (!label) return '';
  return `<li>${esc(label)}${words.length ? `: <b lang="${esc(c.__lang || '')}">${words.map((w) => esc(w)).join(', ')}</b>` : ''}</li>`;
}

export function voiceEvidence(c, evaluation, language) {
  if (!evaluation || typeof evaluation !== 'object') return '';
  const dimensions = evaluation.dimensions || {};
  const provenance = evaluation.provenance || {};
  const evidence = evaluation.evidence || {};
  const demo = evidence.synthetic_demo === true;
  const missing = evidence.content?.missing_tokens || [];
  const extra = evidence.content?.extra_tokens || [];
  const steps = (evaluation.next_steps || [])
    .map((step) => nextStep({ ...c, __lang: language }, step))
    .filter(Boolean);

  return `<section class="voice-evidence">
    ${demo ? `<p class="notice">${esc(c.demoMeasurement)}</p>` : ''}
    <h3>${esc(c.measuredHere)}</h3>
    <dl class="voice-dimensions">${Object.keys(dimensions)
      .map((key) => dimensionRow(c, key, dimensions[key], provenance[key]))
      .join('')}</dl>
    ${
      missing.length || extra.length
        ? `<h3>${esc(c.againstTheLine)}</h3><p class="meta">${esc(c.alignmentNote)}</p><p class="voice-tokens">${
            missing.length
              ? `<span class="missing"><small>${esc(c.missing)}</small> <b lang="${esc(language)}">${missing.map((w) => esc(w)).join(' ')}</b></span>`
              : ''
          }${
            extra.length
              ? `<span class="extra"><small>${esc(c.extra)}</small> <b lang="${esc(language)}">${extra.map((w) => esc(w)).join(' ')}</b></span>`
              : ''
          }</p>`
        : ''
    }
    ${
      steps.length
        ? `<h3>${esc(c.whatToTryNext)}</h3><p class="meta">${esc(c.guidanceNote)}</p><ul class="voice-steps">${steps.join('')}</ul>`
        : ''
    }
    <p class="meta">${esc(c.proficiencyNote)}</p>
  </section>`;
}
