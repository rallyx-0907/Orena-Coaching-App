import assert from 'node:assert/strict';

const originalFetch=globalThis.fetch;
const calls=[];
globalThis.fetch=async (url,options)=>{
  calls.push({url,options});
  return new Response(JSON.stringify({status:'processing'}),{
    status:200,
    headers:{'Content-Type':'application/json'},
  });
};

try{
  const {api}=await import('../static/orena/infrastructure/api.js?media-status-compact-test');
  const payload=await api.mediaImportStatusCompact({
    job_id:'opaque-processing-handle-12345',
    compact:false,
  });
  assert.deepEqual(payload,{status:'processing'});
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/media-learning/import/status');
  assert.equal(calls[0].options.method,'POST');
  assert.deepEqual(JSON.parse(calls[0].options.body),{
    job_id:'opaque-processing-handle-12345',
    compact:true,
  });
}finally{
  globalThis.fetch=originalFetch;
}

console.log('Compact media-status accessor contract OK');
