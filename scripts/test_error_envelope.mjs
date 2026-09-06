/* The canonical error envelope, ORENA_BE_FE_MASTER_IMPLEMENTATION_SPEC §2.6.
 *
 * Both halves of the contract are checked here because either half alone is
 * useless: a backend that emits a category nobody reads, or a frontend that
 * reads a category nobody emits.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=path=>readFileSync(new URL(path,import.meta.url),'utf8');

/* ---- backend: one helper owns the shape ---------------------------------- */

const errors=read('../writing_coach/core/errors.py');
for(const needle of ['"category"','"message"','"retryable"','"context"',
                     'RETRYABLE_CATEGORIES','def orena_http_error','def error_detail']){
  assert.ok(errors.includes(needle),`core/errors.py must define ${needle}`);
}

/* Retryability is a property of the category, not of the call site: the same
   category must not mean "retry" in one route and "do not" in the next. */
assert.ok(/provider_timeout/.test(errors),'a provider timeout must be retryable');
assert.ok(!/malformed_url/.test(errors),'a malformed URL is not retryable');

/* ---- the routes that already carry categories use it --------------------- */

for(const path of ['../writing_coach/media_api.py','../writing_coach/speech_api.py']){
  const source=read(path);
  assert.ok(source.includes('from writing_coach.core.errors import orena_http_error'),
    `${path} must build errors through the shared helper`);
  const handBuilt=source.match(/detail=\{\s*\n\s*"category"/g)||[];
  assert.equal(handBuilt.length,0,
    `${path} still hand-builds an error body; use orena_http_error`);
}

/* Categories stay the strings the product already uses (§2.6: do not invent a
   second vocabulary when one exists). */
const media=read('../writing_coach/media_api.py');
for(const category of ['media_job_unavailable','invalid_media_transcript']){
  assert.ok(media.includes(`"${category}"`),`media category ${category} must survive`);
}
const speech=read('../writing_coach/speech_api.py');
for(const category of ['pronunciation_unconfigured','pronunciation_timeout',
                       'pronunciation_audio_unsupported','pronunciation_provider_malformed']){
  assert.ok(speech.includes(`"${category}"`),`speech category ${category} must survive`);
}

/* ---- frontend: the wrapper surfaces every field a screen may branch on --- */

const api=read('../static/orena/infrastructure/api.js');
for(const needle of ['error.category=detail.category',
                     'error.retryable=detail.retryable',
                     'error.context=detail.context',
                     'error.status=response.status']){
  assert.ok(api.replace(/\s+/g,'').includes(needle.replace(/\s+/g,'')),
    `api.js must surface ${needle}`);
}

console.log('Error envelope infrastructure: PASS');
