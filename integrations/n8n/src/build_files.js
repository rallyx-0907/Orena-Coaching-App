// <<LIB:report>>

// Code node "Build files" - the durable local result, written BEFORE anything is sent to Orena:
//   ready file(s)  critical      <collection>.<content-hash>.ready.jsonl  (same input -> same name and bytes)
//   rejected.json  non-critical  every rejected record with its reasons
//   report.json / report.csv  non-critical  audit (rewritten with the sync outcome after an api run)
const cfg = $('Config').first().json;
const batch = $('Validate & group').first().json;
const items = [];
const add = async (role, path, text, mime) => items.push({
  json: { role, path },
  binary: { data: await this.helpers.prepareBinaryData(Buffer.from(text, 'utf8'), path.split('/').pop(), mime) },
});
for (const g of batch.groups) if (g.readyCount) await add('ready', g.readyPath, g.fileContent, 'application/x-ndjson');
await add('rejected', `${cfg.output.dir}/${cfg.runId}_rejected.json`, JSON.stringify(batch.rejected, null, 2) + '\n', 'application/json');
const report = buildReport(cfg, batch, {}, []);
await add('report_json', `${cfg.output.dir}/${cfg.runId}_report.json`, JSON.stringify(report, null, 2) + '\n', 'application/json');
await add('report_csv', `${cfg.output.dir}/${cfg.runId}_report.csv`, reportCsv(report), 'text/csv');
return items;
