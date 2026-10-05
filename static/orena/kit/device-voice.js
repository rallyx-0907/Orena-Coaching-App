/* The device's own voice (LEX-010, D-132): used only when the server's synthesised voice failed or the app could
   not reach it, and always labelled as the device's by the caller. One helper for every surface that plays a
   word (Word Quick Sheet, Word Detail), so the fallback behaves the same everywhere (LEX-020).

   Returns false when the device has no speech synthesis, or no voice for the language. */
export function speakOnDevice(text, lang) {
  try {
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return false;
    const wanted = lang === 'zh' ? 'zh' : 'en';
    const voices = window.speechSynthesis.getVoices?.() || [];
    if (voices.length && !voices.some((voice) => String(voice.lang || '').toLowerCase().startsWith(wanted))) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === 'zh' ? 'zh-CN' : 'en-US';
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return true;
  } catch {
    return false;
  }
}
