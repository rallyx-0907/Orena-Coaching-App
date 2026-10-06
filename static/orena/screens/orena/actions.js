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

/* §7: "the client never runs it without a learner tap, except `navigate` when the learner's message was itself
   the request". The learner asked to open, go, play, listen to, watch or read something - in the words the
   server's own rule reads (writing_coach/agent/outputs.py `asks_to_go`), in vi, en and zh - and the reply offers a
   place: it opens now, and its button stays in the thread. Only `navigate`; every other action waits for a tap. */
const ASKS_TO_GO = new RegExp(
  '(?:^|[^\p{L}])(?:mở|đi tới|đi đến|đưa (?:mình|tôi|em) (?:tới|đến|sang)|chuyển (?:tới|sang)|open|go to|take me|show me)(?:$|[^\p{L}])'
    + '|(?:^|[^\p{L}])cho (?:mình|tôi|em|tớ) (?:nghe|xem|đọc)(?:$|[^\p{L}])|(?:^|[^\p{L}])(?:play|listen to|watch|read me)(?:$|[^\p{L}])'
    + '|打开|去|带我|进入|播放|我想听|我想看',
  'iu',
);

export function asksToGo(message) {
  return ASKS_TO_GO.test(String(message || ''));
}

export function openIfAsked({ message, reply, dispatcher, ranActions, repaint }) {
  if (!asksToGo(message) || !reply || reply.error) return null;
  const place = (reply.actions || []).find((action) => action?.type === 'navigate');
  return place ? runOffered({ dispatcher, action: place, ranActions, repaint }) : null;
}
