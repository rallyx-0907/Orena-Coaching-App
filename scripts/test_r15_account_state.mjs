import assert from 'node:assert/strict';
import fs from 'node:fs';

const api=fs.readFileSync(new URL('../static/orena/infrastructure/api.js',import.meta.url),'utf8');
const admin=fs.readFileSync(new URL('../static/admin.js',import.meta.url),'utf8');
const productApi=fs.readFileSync(new URL('../writing_coach/product/api.py',import.meta.url),'utf8');
const service=fs.readFileSync(new URL('../writing_coach/product/service.py',import.meta.url),'utf8');

assert.match(api,/productMe:\(\)=>request\('\/api\/product\/me'\)/);
assert.match(admin,/fetch\('\/api\/product\/admin\/account'/);
assert.match(admin,/renderAccountState\(\)/);
assert.match(productApi,/def product_me\(request: Request\)/);
assert.match(productApi,/def product_admin_account\(request: Request\)/);
assert.match(productApi,/require_admin\(request\)/);
assert.match(service,/"available": False/);
assert.match(service,/usage_state="unavailable"/);
assert.match(service,/"subscription"/);
console.log('R15 account-state API/Profile/Admin contract passed');
