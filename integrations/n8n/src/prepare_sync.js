// Code node "Prepare sync" - api mode only: one upload per language group that has READY records.
// Anything that cannot be sent (file mode, no Orena URL, nothing ready) yields one {noop:true, reason} item.
const cfg = $('Config').first().json;
const batch = $('Validate & group').first().json;
if (cfg.mode !== 'api') return [{ json: { noop: true, reason: 'file_mode' } }];
if (!cfg.orena.configured) return [{ json: { noop: true, reason: 'api_mode_needs_orena_base_url' } }];
const out = [];
for (const g of batch.groups) {
  if (!g.readyCount) continue;
  out.push({
    json: { collection_id: g.collection_id, language_code: g.language_code, fileName: g.fileName, ids: g.readyIds, metadata: g.metadata,
      duplicates: cfg.duplicates, previewUrl: cfg.orena.previewUrl, importUrl: cfg.orena.importUrl },
    binary: { data: await this.helpers.prepareBinaryData(Buffer.from(g.fileContent, 'utf8'), g.fileName, 'application/x-ndjson') },
  });
}
return out.length ? out : [{ json: { noop: true, reason: 'no_ready_records' } }];
