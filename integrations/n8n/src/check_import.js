// <<LIB:sync>>

// Code node "Check import" - reads each import answer strictly. The set must be pending_review (authored entries never publish)
// and no source may have failed or conflicted. The local files are never touched by this step.
const sent = $('Check preview').all();
const replies = $input.all();
return sent.map((s, k) => {
  const c = checkImport((replies[k] || {}).json || null, { collection_id: s.json.collection_id, ready: s.json.ids.length });
  return { json: { collection_id: s.json.collection_id, ok: c.ok, reasons: c.reasons, result: c.result, status: c.status } };
});
