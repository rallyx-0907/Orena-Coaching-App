// <<LIB:report>>

// Code node "Final report" - the audit files again, now carrying the outcome of the sync (api mode) and of the first writes.
const cfg = $('Config').first().json;
const batch = $('Validate & group').first().json;
const tried = name => { try { return $(name).all().map(i => i.json); } catch (e) { return null; } };
const writes = ((tried('Check writes') || [])[0] || {}).writes || [];
const prep = tried('Prepare sync') || [];
const previews = tried('Check preview');
const imports = tried('Check import');
const sync = {};
if (cfg.mode === 'api') {
  const noop = prep.length && prep[0].noop ? prep[0] : null;
  for (const g of batch.groups) {
    if (noop) { sync[g.collection_id] = { status: noop.reason === 'no_ready_records' || !g.readyCount ? 'no_ready_records' : 'blocked', reasons: [noop.reason] }; continue; }
    if (!g.readyCount) { sync[g.collection_id] = { status: 'no_ready_records', reasons: [] }; continue; }
    const p = (previews || []).find(x => x.collection_id === g.collection_id);
    if (!p) { sync[g.collection_id] = { status: 'blocked', reasons: ['no preview result'] }; continue; }
    if (!p.passed) {
      sync[g.collection_id] = { status: 'blocked', reasons: p.preview.ok ? ['held: another file of this batch did not pass preview, so nothing was imported'] : p.preview.reasons, preview: p.preview };
      continue;
    }
    const im = (imports || []).find(x => x.collection_id === g.collection_id);
    if (!im) sync[g.collection_id] = { status: 'failed', reasons: ['no import result'], preview: p.preview };
    else sync[g.collection_id] = { status: im.ok ? 'imported' : 'failed', reasons: im.reasons, preview: p.preview, import: im.result };
  }
}
const report = buildReport(cfg, batch, sync, writes);
const add = async (role, path, text, mime, extra) => ({
  json: { role, path, ...(extra || {}) },
  binary: { data: await this.helpers.prepareBinaryData(Buffer.from(text, 'utf8'), path.split('/').pop(), mime) },
});
return [
  await add('report_json', `${cfg.output.dir}/${cfg.runId}_report.json`, JSON.stringify(report, null, 2) + '\n', 'application/json', { sync_status: report.sync_status }),
  await add('report_csv', `${cfg.output.dir}/${cfg.runId}_report.csv`, reportCsv(report), 'text/csv', { sync_status: report.sync_status }),
];
