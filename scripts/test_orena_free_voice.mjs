import assert from 'node:assert/strict';
import { voiceInvitations } from '../static/orena/content/voice-invitations.js';
import {
  continuationLink,
  sourceLink,
  route,
} from '../static/orena/product/intent.js';

for (const language of ['en', 'zh']) {
  for (const invitation of voiceInvitations(language)) {
    assert.ok(invitation.title && invitation.prompt && invitation.cue);
    const id = `voice:${invitation.key}`;
    assert.equal(
      route(continuationLink({ id, intent: 'speaking' })).page,
      'practice',
    );
    assert.equal(route(sourceLink(id)).intent, 'speaking');
  }
}
console.log(
  'Free voice: EN/ZH invitations are complete and continue into the speaking intent PASS',
);
