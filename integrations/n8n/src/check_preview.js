// <<LIB:sync>>

// Code node "Check preview" - fail closed. The import runs only if EVERY file's preview has the exact expected shape and
// EVERY row is `ready`. HTML, an unknown shape, a missing status, any refused / conflict / unknown row, or a request error
// blocks the whole batch (nothing is imported); the local files are untouched.
const sent = $('Prepare sync').all();
const replies = $input.all();
const checks = sent.map((s, k) => checkPreview((replies[k] || {}).json || null, { filename: s.json.fileName, language_code: s.json.language_code, ids: s.json.ids }));
if (replies.length !== sent.length) checks.forEach(c => { c.ok = false; c.reasons.push(`Orena answered ${replies.length} of ${sent.length} preview request(s)`); });
const passed = checks.every(c => c.ok);
return sent.map((s, k) => ({
  json: { ...s.json, passed, preview: { ok: checks[k].ok, status: checks[k].status, reasons: checks[k].reasons, counts: checks[k].counts, existing: checks[k].existing, warnings: checks[k].warnings } },
  ...(passed ? { binary: s.binary } : {}),
}));
