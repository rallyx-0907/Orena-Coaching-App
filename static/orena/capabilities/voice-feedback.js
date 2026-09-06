import {evaluateSpeechTranscript} from './speech-comparison.js';
// A recording and a source segment are enough. No knowledge of destinations,
// studios, navigation, shared-screen stores, or a Listening mode.
export async function evaluateVoice({api,blob,language,reference,assetId='',segmentId,takeId,pronunciation=null}) {
  const transcription=await api.transcribeSpeech(blob,language);
  const heard=transcription.text||transcription.transcript||'';
  if(!heard.trim())throw Error('No speech recognized');
  const content_match=evaluateSpeechTranscript(reference,heard);
  const evaluation=await api.evaluateSpeaking({language,reference_text:reference,transcript_text:heard,content_match,pronunciation,transcription_confidence:transcription.confidence??null});
  let saved=false;
  try{await api.saveSpeakingAttempt({language,take_id:takeId,asset_id:assetId,segment_id:segmentId,reference_text:reference,transcript_text:heard,evaluation});saved=true;}catch{}
  return {heard,content_match,evaluation,saved};
}
