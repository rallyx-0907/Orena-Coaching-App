// Optional browser gate: install Playwright outside this dependency-free repo.
// ORENA_PREVIEW_URL must name the isolated frontend preview, not production.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.ORENA_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.ORENA_PREVIEW_URL;
if (!base || !['localhost','127.0.0.1'].includes(new URL(base).hostname))
  throw Error('An explicit local isolated preview URL is required');
const browser = await chromium.launch({headless:true,
  ...(process.env.ORENA_BROWSER_EXECUTABLE ? {executablePath:process.env.ORENA_BROWSER_EXECUTABLE} : {})});
const context = await browser.newContext();
const page = await context.newPage();
const errors=[]; page.on('pageerror', error=>errors.push(error.message));
const route='/#/encounter?id=story%3Afamiliar-street';
try {
  await page.goto(base+route);
  for(const language of ['en','zh']) {
    await page.locator('[data-preference]').first().click();
    for(let attempt=0;attempt<3;attempt++) {
      await page.locator('select[name=learning]').selectOption(language);
      await page.locator('select[name=interface]').selectOption(language);
      await page.locator('input[name=pinyin]').check();
      await page.locator('#preferencesForm .primary').click();
      await page.waitForTimeout(500);
      if(await page.locator('dialog').count()===0) break;
      // Existing preferences explicitly refresh after an optimistic conflict.
      // Reapply the visible requested choice; do not change the I1 contract.
      assert((await page.locator('#preferenceError').innerText()).length>0);
    }
    await page.locator('dialog').waitFor({state:'detached'});
    await page.goto(base+route);
    await page.locator('[data-text-lens-toggle]').click();
    await page.locator('.passage [data-token]').first().waitFor();
    assert.equal(await page.locator('.passage [data-word]').count(),0,'untimed text must not claim word synchronization');
    if(language==='zh') assert(await page.locator('.passage [data-reading]').count()>0);
    for(const width of [390,1440,1920]) {
      await page.setViewportSize({width,height:1000});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${language} overflow ${width}`);
      if(process.env.ORENA_BROWSER_EVIDENCE) {
        await mkdir(process.env.ORENA_BROWSER_EVIDENCE,{recursive:true});
        await page.screenshot({path:`${process.env.ORENA_BROWSER_EVIDENCE}/${language}-${width}.png`,fullPage:true});
      }
    }
    const token=page.locator('.passage [data-token]').first();
    const selected=await token.getAttribute('data-token');
    await token.click();
    await page.locator('dialog').waitFor();
    assert((await page.locator('dialog').innerText()).includes(selected));
    await page.keyboard.press('Escape');
    await page.locator('[data-text-lens-toggle]').click();
    assert.equal(await page.locator('.passage [data-token]').count(),0);
  }
  assert.deepEqual(errors,[]);
  console.log('Browser: EN/ZH tokens, supplied Pinyin, source explanation, untimed text, toggle, 390/1440/1920 PASS');
} finally { await browser.close(); }
