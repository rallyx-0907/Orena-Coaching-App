// Code node "Run summary" - what the operator sees at the end of a run: counts, the files, any non-critical write that
// failed, and the sync outcome. A failed audit write never turns a good batch into a failed one; it is simply listed here.
const cfg = $('Config').first().json;
const batch = $('Validate & group').first().json;
const final = $('Final report').all().map(i => i.json);
const firstWrites = ((() => { try { return $('Check writes').first().json; } catch (e) { return {}; } })()).writes || [];
const msgOf = e => String((e && (e.message || e.description)) || e || 'unknown error').slice(0, 300);
const results = $input.all();
const writes = [
  ...firstWrites.filter(w => w.role === 'ready' || w.role === 'rejected'),
  ...final.map((f, i) => {
    const r = results[i];
    const err = !r ? 'no result from the write node' : (r.json && r.json.error ? msgOf(r.json.error) : '');
    return { role: f.role, path: f.path, ok: !err, error: err };
  }),
];
return [{ json: {
  run_id: cfg.runId, mode: cfg.mode, mode_source: cfg.modeSource, duplicates: cfg.duplicates, duplicates_note: cfg.duplicatesNote || undefined,
  ready: batch.ready.length, rejected: batch.rejected.length,
  files: writes.filter(w => w.ok).map(w => w.path),
  non_critical_write_failures: writes.filter(w => !w.ok),
  sync_status: (final[0] || {}).sync_status || 'unknown',
  note: cfg.mode === 'api' ? 'See sync_status and the report for the Orena preview/import. Imported sets wait for review in Orena Admin.' : 'File mode: import the ready file through Orena Admin (Vocabulary import).',
} }];
