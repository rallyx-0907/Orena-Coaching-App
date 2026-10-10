/* The words of the explanation Plans shows when a refused language opens it (D-17Q), from the facts of
   model.languageReasonFacts(): the plan and its limit, the languages the learner already learns, the one they tried to
   add and the plan that would allow it. Every figure and name is the server's or the catalogue's; the languages are named
   in the interface language. A fact that is not known leaves its sentence out - nothing is invented in its place. */
import { languages } from '../../copy/index.js';
import { planName } from '../../copy/shell.js';
import { languageName } from '../onboarding/model.js';
import { t } from './copy.js';
import { formatNumber } from './model.js';

function listOf(names, ui) {
  try {
    return new Intl.ListFormat(ui, { style: 'long', type: 'conjunction' }).format(names);
  } catch {
    return names.join(', ');
  }
}

export function languageReasonText(facts) {
  if (!facts) return null;
  const ui = languages().ui;
  const plan = facts.plan ? planName(facts.plan) : t('reasonThisPlan');
  const title = facts.included && facts.limit != null
    ? t.plural('reasonLanguageTitle', facts.limit, { plan, limit: formatNumber(facts.limit, ui) })
    : t('reasonLanguageNone', { plan });
  const held = facts.held.map((code) => languageName(code, ui));
  const sentences = [];
  if (held.length) sentences.push(t('reasonHave', { have: listOf(held, ui) }));
  if (facts.upgrade) {
    const target = planName(facts.upgrade);
    sentences.push(facts.requested && !facts.held.includes(facts.requested)
      ? t('reasonUpgradeTo', { requested: languageName(facts.requested, ui), plan: target })
      : t('reasonUpgradeAny', { plan: target }));
  } else {
    sentences.push(t('reasonNoUpgrade'));
  }
  sentences.push(t('reasonNothingChanged'));
  return { title, text: sentences.join(ui === 'zh' ? '' : ' ') };
}
