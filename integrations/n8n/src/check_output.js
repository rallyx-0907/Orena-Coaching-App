// Code node "Check output folder" - stops the run early, with the folder to create, when the probe could not be written.
const cfg = $('Config').first().json;
const r = $input.first();
const err = !r ? 'no result from the write node' : (r.json && r.json.error);
if (err) {
  const msg = String((err && (err.message || err.description)) || err).slice(0, 300);
  throw new Error(`The output folder ${cfg.output.dir} is not writable (${msg}). n8n does not create it: create the folder inside the ` +
    `mounted volume first (for example: mkdir -p ./orena-files/orena for a mount of ./orena-files at /files), make it writable ` +
    `by the n8n user, and set N8N_RESTRICT_FILE_ACCESS_TO to a parent of it. Nothing was generated.`);
}
return [{ json: { ok: true } }];
