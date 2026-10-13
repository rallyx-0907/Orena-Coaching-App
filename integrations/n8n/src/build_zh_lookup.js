// <<LIB:common>>

// Code node "Build ZH lookup" - merges CC-CEDICT + CVDICT + Make Me a Hanzi + Unihan into one compact lookup file.
function parseCedict(txt) {
  const d = {};
  const re = /^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+\/(.*)\/\s*$/;
  for (const line of String(txt || '').split(/\r?\n/)) {
    if (!line || line[0] === '#') continue;
    const m = re.exec(line);
    if (m) (d[m[2]] = d[m[2]] || []).push([m[3], m[4].split('/').filter(Boolean)]);
  }
  return d;
}
const cedict = parseCedict($('CEDICT text').first().json.data);
if (Object.keys(cedict).length < 1000) throw new Error('The CC-CEDICT download is not valid (too few entries)');
const cvdict = {};
for (const [k, v] of Object.entries(parseCedict($('Download CVDICT').first().json.data))) { const e = pickEntry(v); if (e) cvdict[k] = e[1]; }
if (Object.keys(cvdict).length < 1000) throw new Error('The CVDICT download is not valid - check sources.cvdict in Config');

const hanzi = {};
for (const line of String($('Download Make Me a Hanzi').first().json.data || '').split(/\r?\n/)) {
  if (!line.trim()) continue;
  try { const o = JSON.parse(line); hanzi[o.character] = [o.decomposition || '', o.radical || '']; } catch (e) {}
}

const want = new Set();
for (const k of Object.keys(cedict)) for (const ch of Array.from(k)) want.add(ch);
for (let n = 1; n <= 214; n++) want.add(String.fromCodePoint(0x2F00 + n - 1).normalize('NFKC'));
const FIELDS = { kRSUnicode: 0, kTotalStrokes: 1, kVietnamese: 2, kMandarin: 3 };
const unihan = {};
const item = $input.first();
let filesRead = 0;
for (const key of Object.keys(item.binary || {})) {
  const name = (item.binary[key].fileName || '').split('/').pop();
  if (!/^Unihan.*\.txt$/.test(name)) continue;
  const txt = (await this.helpers.getBinaryDataBuffer(0, key)).toString('utf8');
  filesRead++;
  for (const line of txt.split('\n')) {
    if (!line.startsWith('U+')) continue;
    const [cp, field, val] = line.split('\t');
    if (!(field in FIELDS)) continue;
    const ch = String.fromCodePoint(parseInt(cp.slice(2), 16));
    if (want.has(ch)) (unihan[ch] = unihan[ch] || ['', '', '', ''])[FIELDS[field]] = (val || '').trim();
  }
}
if (!filesRead) throw new Error('No Unihan_*.txt found after unzipping Unihan.zip');
return [{ json: { lookup: { v: 1, built_at: new Date().toISOString(), cedict, cvdict, hanzi, unihan },
  stats: { cedict: Object.keys(cedict).length, cvdict: Object.keys(cvdict).length, hanzi: Object.keys(hanzi).length, unihan: Object.keys(unihan).length } } }];
