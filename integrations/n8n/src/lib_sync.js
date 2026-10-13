// ===== Orena vocabulary generator | strict readers of Orena's admin vocabulary responses =====
// Contract source: app.py `admin_vocabulary_source_preview` / `admin_vocabulary_source_import` and
// `_authored_preview` (see integrations/n8n/README.md). Anything that does not match EXACTLY blocks the import.

// The HTTP Request node (full response, text format) hands over { statusCode, headers, body } (or { data } for the body).
function readHttp(resp) {
  if (!resp || typeof resp !== 'object') return { ok: false, reason: 'no response from Orena' };
  if (resp.error) return { ok: false, reason: 'request to Orena failed: ' + String((resp.error && (resp.error.message || resp.error.description)) || JSON.stringify(resp.error)).slice(0, 300) };
  const status = resp.statusCode;
  if (!Number.isInteger(status)) return { ok: false, reason: 'the response has no HTTP status code' };
  const raw = resp.body !== undefined ? resp.body : resp.data;
  const snippet = String(typeof raw === 'string' ? raw : JSON.stringify(raw)).replace(/\s+/g, ' ').slice(0, 200);
  if (status < 200 || status >= 300) return { ok: false, status, reason: `HTTP ${status}: ${snippet}` };
  const headers = resp.headers && typeof resp.headers === 'object' ? resp.headers : {};
  const ctype = String(Object.entries(headers).find(([k]) => k.toLowerCase() === 'content-type')?.[1] || '').toLowerCase();
  if (ctype && !ctype.includes('json')) return { ok: false, status, reason: `the response is not JSON (content-type '${ctype.slice(0, 60)}')` };
  let body = raw;
  if (typeof raw === 'string') { try { body = JSON.parse(raw); } catch (e) { return { ok: false, status, reason: 'the response body is not JSON: ' + snippet.slice(0, 80) }; } }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { ok: false, status, reason: 'the response body is not a JSON object' };
  return { ok: true, status, body };
}

const _isObj = v => !!v && typeof v === 'object' && !Array.isArray(v);

// expected = { filename, language_code, ids: [ids in file order] }. Returns { ok, reasons[], counts, existing }.
// `ok` is true only when the response has the exact preview shape AND every row is `ready` with a known `existing`.
function checkPreview(resp, expected) {
  const http = readHttp(resp);
  const out = { ok: false, reasons: [], counts: {}, existing: {}, warnings: [], status: http.status || null };
  if (!http.ok) { out.reasons.push(http.reason); return out; }
  const items = http.body.items;
  if (!Array.isArray(items) || items.length !== 1) { out.reasons.push("unexpected preview shape: 'items' must be an array with exactly one item"); return out; }
  const item = items[0];
  if (!_isObj(item)) { out.reasons.push('unexpected preview shape: the item is not an object'); return out; }
  if (item.error) { out.reasons.push('preview error: ' + String(item.error).slice(0, 300)); return out; }
  if (item.error !== '') { out.reasons.push("unexpected preview shape: item.error must be ''"); return out; }
  if (item.filename !== expected.filename) out.reasons.push(`unexpected preview shape: filename '${item.filename}' is not '${expected.filename}'`);
  if (typeof item.content_hash !== 'string' || !item.content_hash) out.reasons.push('unexpected preview shape: no content_hash');
  const a = item.authored;
  if (!_isObj(a)) { out.reasons.push("the file was not read as authored vocabulary entries (no 'authored' section)"); return out; }
  if (a.format !== 'orena-vocab-entry') out.reasons.push(`unexpected preview shape: authored.format is '${a.format}'`);
  if (a.language_code !== expected.language_code) out.reasons.push(`the preview language '${a.language_code}' is not '${expected.language_code}'`);
  if (!Array.isArray(a.rows) || !_isObj(a.counts) || !Array.isArray(a.warnings)) { out.reasons.push('unexpected preview shape: authored.rows/counts/warnings'); return out; }
  if (a.rows.length !== expected.ids.length) out.reasons.push(`the preview has ${a.rows.length} row(s), the file has ${expected.ids.length}`);
  const tally = {};
  a.rows.forEach((row, i) => {
    if (!_isObj(row)) { out.reasons.push(`row ${i + 1}: not an object`); return; }
    const label = row.id || row.term || `row ${i + 1}`;
    tally[row.outcome] = (tally[row.outcome] || 0) + 1;
    if (row.outcome !== 'ready') { out.reasons.push(`${label}: outcome '${row.outcome}'${row.reason ? ' - ' + String(row.reason).slice(0, 200) : ''}`); return; }
    if (row.id !== expected.ids[i]) out.reasons.push(`row ${i + 1}: id '${row.id}' is not the expected '${expected.ids[i]}'`);
    if (row.existing !== 'new' && row.existing !== 'duplicate') out.reasons.push(`${label}: cannot tell what Orena already holds (existing '${row.existing}')`);
    else out.existing[row.id] = row.existing;
  });
  for (const [k, n] of Object.entries(a.counts)) if (tally[k] !== n) out.reasons.push(`unexpected preview shape: counts.${k}=${n} disagrees with the rows`);
  for (const k of Object.keys(tally)) if (!(k in a.counts)) out.reasons.push(`unexpected preview shape: counts is missing '${k}'`);
  out.counts = a.counts;
  out.warnings = a.warnings.map(w => String(w).slice(0, 300));
  out.ok = out.reasons.length === 0;
  return out;
}

// expected = { collection_id, ready: n }. The import response must show a pending_review set and no failed/conflicting row.
function checkImport(resp, expected) {
  const http = readHttp(resp);
  const out = { ok: false, reasons: [], result: null, status: http.status || null };
  if (!http.ok) { out.reasons.push(http.reason); return out; }
  const { collection, items } = http.body;
  if (!_isObj(collection) || collection.id !== expected.collection_id) out.reasons.push(`unexpected import shape: collection.id is not '${expected.collection_id}'`);
  if (_isObj(collection) && collection.catalog_status !== 'pending_review') out.reasons.push(`the collection is '${collection.catalog_status}', not pending_review (authored vocabulary must wait for review)`);
  if (!Array.isArray(items) || items.length !== 1 || !_isObj(items[0])) { out.reasons.push("unexpected import shape: 'items' must hold exactly one result"); return out; }
  const r = items[0];
  for (const k of ['imported', 'skipped', 'duplicates', 'failed']) if (!Number.isInteger(r[k])) out.reasons.push(`unexpected import shape: '${k}' is not a number`);
  if (r.status !== 'imported' && r.status !== 'skipped') out.reasons.push(`the source result is '${r.status}'${r.failure_reason ? ': ' + String(r.failure_reason).slice(0, 200) : ''}`);
  if (r.failed) out.reasons.push(`${r.failed} source(s) failed${r.failure_reason ? ': ' + String(r.failure_reason).slice(0, 200) : ''}`);
  if (Number.isInteger(r.conflicts) && r.conflicts > 0) out.reasons.push(`${r.conflicts} entr(ies) conflict with a published set and were refused`);
  out.result = { status: r.status, imported: r.imported, updated: r.updated || 0, skipped: r.skipped, duplicates: r.duplicates, conflicts: r.conflicts || 0, catalog_status: _isObj(collection) ? collection.catalog_status : null };
  out.ok = out.reasons.length === 0;
  return out;
}
// ===== end of Orena response readers =====
