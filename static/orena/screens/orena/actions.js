/* Running one offered action from a card (AGENT_CONTRACT §7 "An action is shown as a button ... the
   client never runs it without a learner tap"). Shared by Orena Home and the Contextual panel so
   the two behave the same way when a tap does not do what the card said.

   The card is marked done the moment it is tapped so a second tap cannot start the same action
   twice; if the action did not run (the learner declined a confirmation, the word is not in the
   learning language, the request failed) the card becomes tappable again, and - except for a
   declined confirmation, which is the learner's own answer - a short toast says so. Nothing is ever
   left looking done that was not. */
import { toast } from '../../kit/toast.js';
import { t } from './copy.js';
import { actionFailureKey } from './model.js';

export async function runOffered({ dispatcher, action, ranActions, repaint }) {
  if (!action || ranActions.has(action.id)) return null;
  ranActions.add(action.id);
  repaint();
  const result = await dispatcher.run(action);
  if (!result?.ok) ranActions.delete(action.id);
  repaint();
  const key = actionFailureKey(result);
  if (key) toast(t(key), { iconName: 'circle-alert' });
  return result;
}
