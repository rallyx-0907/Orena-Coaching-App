import assert from 'node:assert/strict';
import { evaluateVoice } from '../static/orena/capabilities/voice-feedback.js';
import { voiceInvitations } from '../static/orena/content/voice-invitations.js';
import {
  continuationLink,
  sourceLink,
  route,
} from '../static/orena/product/intent.js';

for (const language of ['en', 'zh']) {
  const heard =
    language === 'en' ? 'Let me show you my city.' : '我带你看看这座城市。';
  let evaluated, saved;
  const api = {
    transcribeSpeech: async () => ({ text: heard, confidence: null }),
    evaluateSpeaking: async (value) => {
      evaluated = value;
      return {
        dimensions: {
          content_match: value.content_match?.content_match ?? null,
          proficiency: null,
        },
      };
    },
    saveSpeakingAttempt: async (value) => {
      saved = value;
    },
  };
  const result = await evaluateVoice({
    api,
    blob: new Blob(['audio']),
    language,
    segmentId: 'voice:invitation',
    takeId: 'unique-take',
  });
  assert.equal(result.saved, true);
  assert.equal(evaluated.reference_text, '');
  assert.equal(
    evaluated.content_match,
    null,
    'Free speech must not be scored against the invitation',
  );
  assert.equal(saved.asset_id, '', 'No invented media source');
  assert.equal(saved.transcript_text, heard);
  assert.equal(saved.segment_id, 'voice:invitation');
  assert.equal(result.evaluation.dimensions.proficiency, null);
  assert.equal(
    (
      await evaluateVoice({
        api: {
          ...api,
          saveSpeakingAttempt: async () => {
            throw Error('offline');
          },
        },
        language,
        segmentId: 'voice:invitation',
        takeId: 'another',
      })
    ).saved,
    false,
  );
  await assert.rejects(
    evaluateVoice({
      api: { ...api, transcribeSpeech: async () => ({ text: '' }) },
      language,
    }),
    /No speech/,
  );
  await assert.rejects(
    evaluateVoice({
      api: {
        ...api,
        transcribeSpeech: async () => {
          throw Error('unavailable');
        },
      },
      language,
    }),
    /unavailable/,
  );
  const shadow = await evaluateVoice({
    api,
    language,
    reference: heard,
    segmentId: 'line',
    takeId: 'shadow',
  });
  assert.equal(
    shadow.content_match.content_match,
    100,
    'Shared engine preserves reference-based Shadowing',
  );
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
  'Free voice: real transcript only, no reference alignment, save failure, EN/ZH continuity and Shadowing reuse PASS',
);
