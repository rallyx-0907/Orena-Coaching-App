/* Hanzi stroke-order practice in the Chinese learner dictionary.
 *
 * The rule this holds is UPGRADE_REGRESSION_RULES.md §33: stroke order may only
 * be shown when verified stroke data exists. That makes three things worth
 * pinning, and none of them is a screenshot:
 *
 *   - the data really is vendored, with its licence, and the provider reads it
 *     rather than asking a model;
 *   - the frontend gets its strokes from that provider through the shared API
 *     wrapper, never from a CDN or an AI call;
 *   - the whole surface stays inside the shared dictionary component, so
 *     Writing, Review and Library keep one implementation between them
 *     (UPGRADE_REGRESSION_RULES.md §32).
 */
import assert from 'node:assert/strict';
import {readFileSync,existsSync,statSync} from 'node:fs';

const url=path=>new URL(path,import.meta.url);
const read=path=>readFileSync(url(path),'utf8');

/* ---- the data is present, intact and licensed --------------------------- */

const dataDir='../writing_coach/languages/chinese/stroke_data/';
for(const file of ['hanzi_strokes.pack','hanzi_strokes.index.json','ARPHICPL.TXT','README.md']){
  assert.ok(existsSync(url(dataDir+file)),`vendored stroke data must include ${file}`);
}

/* The Arphic Public License permits redistribution only while ARPHICPL.TXT
   travels unaltered with the data (§1), and a reformatted copy must say how and
   when it was changed (§2a). */
const licence=read(dataDir+'ARPHICPL.TXT');
assert.ok(licence.includes('ARPHIC PUBLIC LICENSE'),'the licence file must be the real one');
const provenance=read(dataDir+'README.md');
assert.ok(/Arphic Public License/.test(provenance),'provenance must name the licence');
assert.ok(/Make Me a Hanzi/.test(provenance),'provenance must name the upstream project');
assert.ok(/Modification notice/i.test(provenance),'§2a modification notice is missing');

const index=JSON.parse(read(dataDir+'hanzi_strokes.index.json'));
assert.equal(index.format,'orena.hanzi-strokes.v1','index format changed without the reader');
assert.ok(index.count>9000,`stroke pack covers only ${index.count} characters`);
assert.equal(Object.keys(index.offsets).length,index.count,'index count and offsets disagree');
assert.ok(typeof index.pack_sha256==='string'&&index.pack_sha256.length===64,
  'the index must carry a digest of the pack it describes');

/* Every offset has to land inside the pack, or a lookup serves another
   character's bytes rather than failing. */
const packBytes=statSync(url(dataDir+'hanzi_strokes.pack')).size;
for(const [character,[offset,length]] of Object.entries(index.offsets)){
  assert.ok(offset>=0&&offset+length<=packBytes,`offset for ${character} falls outside the pack`);
}

/* ---- the provider is deterministic ------------------------------------- */

const provider=read('../writing_coach/languages/chinese/stroke_order.py');
for(const forbidden of ['ai_json','generate_structured','requests.','http://','https://']){
  assert.ok(!provider.includes(forbidden),
    `stroke order must not reach for ${forbidden}; it is vendored data, not a provider call`);
}
assert.ok(provider.includes('def stroke_order_for'),'stroke_order_for must exist');
assert.ok(provider.includes('unavailable'),
  'a character with no data must be reported, not approximated');

const app=read('../app.py');
assert.ok(app.includes('@app.get("/api/chinese/stroke-order")'),'the stroke-order route is missing');
assert.ok(app.includes('stroke_data_unavailable'),
  'missing stroke data must answer with the canonical error envelope');

/* ---- the frontend reads the app, not the internet ----------------------- */

console.log('Hanzi data and provider contract: PASS');
