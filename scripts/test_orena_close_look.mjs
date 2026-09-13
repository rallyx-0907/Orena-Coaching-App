import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
const moduleUrl = new URL('../static/orena/ui/annotated-line.js', import.meta.url);
assert.ok(existsSync(moduleUrl), 'Close look needs a renderer that preserves canonical text and timed Follow');
const { annotatedLine } = await import(moduleUrl);
const s = {original_text:'Anna, run!', words:[{text:'Anna',start_ms:0,end_ms:500},{text:'run',start_ms:500,end_ms:1000}]};
const data = {text:s.original_text,annotations:[{start:0,end:4,fragment:'Anna',pos:'proper_noun'},{start:6,end:9,fragment:'run',pos:'verb'}]};
const html = annotatedLine(s,data);
assert.ok(html.includes('data-token="Anna"'));
assert.ok(html.includes('data-word="0"') && html.includes('data-word="1"'), 'close look retains word clock anchors');
assert.equal(html.replace(/<[^>]*>/g,''),s.original_text);
assert.equal(annotatedLine(s,{...data,text:'another line'}),null,'stale text cannot annotate this line');
for (const bad of [{start:0,end:100,fragment:'Anna'},{start:0,end:4,fragment:'Else'},{start:0,end:null,fragment:'Anna'},{start:-1,end:3,fragment:'Anna'}]) {
  assert.equal(annotatedLine(s,{...data,annotations:[bad]}),null,'invalid offsets cannot alter the transcript');
}
// Python offsets count Unicode code points. JS must not split astral characters.
const zh={original_text:'🙂 你好！'};
const zhData={text:zh.original_text,reading_aid:'pinyin',annotations:[{start:2,end:4,fragment:'你好',pos:'verb',pronunciation:'nǐ hǎo'}]};
assert.ok(annotatedLine(zh,zhData,{pinyin:true}).includes('data-reading="nǐ hǎo"'));
assert.ok(annotatedLine(zh,zhData,{pinyin:false}).includes('data-token="你好"'));
assert.ok(!annotatedLine(zh,zhData,{pinyin:false}).includes('data-reading='));
assert.equal(annotatedLine(zh,zhData,{pinyin:false}).replace(/<[^>]*>/g,''),zh.original_text);
const hostile={original_text:'<a>'};
assert.ok(annotatedLine(hostile,{text:'<a>',annotations:[{start:1,end:2,fragment:'a',pos:'noun'}]}).startsWith('&lt;'));
// An annotation can span multiple timed words; neither timing nor punctuation is discarded.
assert.equal(annotatedLine(s,{text:s.original_text,annotations:[{start:0,end:9,fragment:'Anna, run',pos:'other'}]}).match(/data-word=/g).length,2);
console.log('Close look: canonical text, Unicode offsets, timing, Pinyin preference and invalid-data fallback PASS');
