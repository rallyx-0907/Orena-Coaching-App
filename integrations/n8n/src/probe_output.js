// Code node "Output folder probe" - n8n's Read/Write Files node does not create folders, so a fresh install would fail
// on the first write (ENOENT realpath). This writes a tiny marker into the output folder FIRST; "Check output folder"
// turns a failure into one clear message before any download or enrichment is spent.
const cfg = $('Config').first().json;
const path = `${cfg.output.dir}/.orena-write-check`;
return [{
  json: { path },
  binary: { data: await this.helpers.prepareBinaryData(Buffer.from('ok\n', 'utf8'), '.orena-write-check', 'text/plain') },
}];
