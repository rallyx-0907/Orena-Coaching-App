// ===== Orena vocabulary generator | report builders =====
const csvCell = v => { const s = String(v === undefined || v === null ? '' : v); return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };

// batch  = the single item of "Validate & group"
// sync   = { [collection_id]: { status, reasons[], preview?, import? } } (empty in file mode)
// writes = [{ role, path, ok, error }]
function buildReport(cfg, batch, sync, writes) {
  const groupSync = id => sync[id] || { status: cfg.mode === 'api' ? 'pending' : 'not_requested', reasons: [] };
  const statuses = batch.groups.map(g => groupSync(g.collection_id).status);
  let overall = 'not_requested';
  if (cfg.mode === 'api') {
    if (!batch.groups.some(g => g.readyCount)) overall = 'skipped_no_ready_records';
    else if (statuses.some(s => s === 'failed')) overall = 'failed';
    else if (statuses.some(s => s === 'blocked')) overall = 'blocked';
    else if (statuses.every(s => s === 'imported' || s === 'no_ready_records')) overall = 'imported';
    else overall = 'pending';
  }
  const rowSync = lang => { const g = batch.groups.find(x => x.lang === lang); return g ? groupSync(g.collection_id).status : ''; };
  const rows = [
    ...batch.ready.map(x => ({ line: x.line, id: x.id, headword: x.headword, lang: x.lang, status: 'ready', reasons: '', warnings: (x.warnings || []).join(' | '), collection_id: (batch.groups.find(g => g.lang === x.lang) || {}).collection_id || '', sync: rowSync(x.lang) })),
    ...batch.rejected.map(x => ({ line: x.line, id: x.id, headword: x.headword, lang: x.lang, status: 'rejected', reasons: x.reasons.join(' | '), warnings: (x.warnings || []).join(' | '), collection_id: '', sync: 'not_sent' })),
  ].sort((a, b) => a.line - b.line);
  return {
    run_id: cfg.runId,
    mode: cfg.mode,
    mode_source: cfg.modeSource,
    duplicates: cfg.duplicates,
    duplicates_note: cfg.duplicatesNote || '',
    totals: { input: batch.ready.length + batch.rejected.length, ready: batch.ready.length, rejected: batch.rejected.length },
    ai: { configured: !!cfg.ai.active, endpoint_host: cfg.ai.host || '', reason: cfg.ai.active ? '' : (cfg.ai.reason || 'AI not configured: missing endpoint/model') },
    rights_status: cfg.metadata.rights_status,
    completeness: cfg.metadata.completeness,
    sync_status: overall,
    groups: batch.groups.map(g => ({ lang: g.lang, collection_id: g.collection_id, ready: g.readyCount, rejected: g.rejectedCount, ready_file: g.readyCount ? g.readyPath : '', sync: groupSync(g.collection_id) })),
    input_issues: batch.inputIssues || [],
    writes: writes || [],
    rows,
  };
}

function reportCsv(report) {
  const head = ['line', 'id', 'headword', 'lang', 'status', 'reasons', 'warnings', 'collection_id', 'sync'];
  return [head.join(','), ...report.rows.map(r => head.map(k => csvCell(r[k])).join(','))].join('\n') + '\n';
}
// ===== end of report builders =====
