// Code node "Check writes" - which writes failed? The ready file is CRITICAL: if it was not written the run stops here,
// says so, and nothing is sent to Orena. The rejected file and the reports are NON-critical: a failure is recorded and
// reported, and never touches the generated batch (held in memory and in the ready file).
const planned = $('Build files').all().map(i => i.json);
const results = $input.all();
const msgOf = e => String((e && (e.message || e.description)) || e || 'unknown error').slice(0, 300);
const writes = planned.map((f, i) => {
  const r = results[i];
  const err = !r ? 'no result from the write node' : (r.json && r.json.error ? msgOf(r.json.error) : '');
  return { role: f.role, path: f.path, ok: !err, error: err };
});
const failedCritical = writes.filter(w => w.role === 'ready' && !w.ok);
if (failedCritical.length) {
  throw new Error('Critical write failed - the ready file could not be saved (' + failedCritical.map(w => `${w.path}: ${w.error}`).join('; ') +
    '). Nothing was sent to Orena. Check that the output folder is a mounted volume and that N8N_RESTRICT_FILE_ACCESS_TO allows it.');
}
return [{ json: { writes, nonCriticalFailures: writes.filter(w => !w.ok) } }];
