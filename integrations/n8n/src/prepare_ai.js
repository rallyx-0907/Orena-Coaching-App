// <<LIB:common>>

// Code node "Prepare AI" - builds an AI request ONLY for a record that still has a gap the deterministic sources could not fill.
// AI is a fill-gap layer: it never overwrites a field that already has a value. Nothing to ask, or AI not configured -> one {noop:true} item.
const cfg = $('Config').first().json;
const F = cfg.ai.fill;
const jobs = [];
if (cfg.ai.active) {
  $input.all().forEach((it, idx) => {
    const { record: r, gaps, errors } = it.json;
    if (errors.length) return;                       // hard errors (missing level, no pinyin ...) are not for AI to repair
    const want = {};
    if (gaps.includes('pos') && F.pos) want.pos = `array of part-of-speech codes, only from: ${POS_CODES.join(', ')}`;
    if (gaps.includes('meaning_vi') && F.meaning_vi) want.meaning_vi = 'a short Vietnamese meaning, the most common sense';
    const tIdx = gaps.filter(g => g.startsWith('translation_vi:')).map(g => +g.split(':')[1]);
    if (tIdx.length && F.translation_vi) want.translations_vi = 'object {sentence index: natural Vietnamese translation} for the sentences: ' + JSON.stringify(Object.fromEntries(tIdx.map(k => [k, r.examples[k].text])));
    if (gaps.includes('examples') && F.examples) want.examples = `array of 1-${cfg.record.maxExamples} short natural example sentences at level ${r.level ? r.level.value : ''}, each CONTAINING "${r.headword}" verbatim` +
      (r.lang === 'zh-Hans' ? ', written in Simplified Chinese' : '') + '; each element {"text","translation_vi"}';
    if (gaps.includes('ipa') && F.ipa) want.ipa = 'object {"uk": "/.../", "us": "/.../"}, standard slash-delimited IPA';
    if (!Object.keys(want).length) return;
    const context = { headword: r.headword, lang: r.lang, level: r.level, pos: r.pos.map(p => p.code),
      meanings: r.meanings, zh_pinyin: r.zh ? r.zh.pinyin : undefined };
    const body = {
      model: cfg.ai.model,
      temperature: 0,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: 'You complete missing fields of a vocabulary card for Vietnamese learners of a foreign language. Reply with ONE JSON object holding exactly the requested keys, nothing else, no explanation. If you are not sure of a key, leave it out.' },
        { role: 'user', content: 'Existing data (do not change):\n' + JSON.stringify(context) + '\n\nReturn JSON with these keys:\n' +
          Object.entries(want).map(([k, v]) => `- "${k}": ${v}`).join('\n') },
      ],
    };
    jobs.push({ json: { recIndex: idx, want: Object.keys(want), body } });
  });
}
return jobs.length ? jobs : [{ json: { noop: true } }];
