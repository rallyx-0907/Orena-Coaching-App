// Manual local browser verification of the Orena Writing review flow.
//
// Not a CI gate: it needs Playwright and the running sandbox app. It uses the
// installed system Chrome channel, so it downloads no browser. Run it with the
// sandbox at 127.0.0.1:8011:
//
//   npm install playwright    # anywhere resolvable, e.g. a scratch directory
//   NODE_PATH=<that node_modules> node scripts/verify_writing_review_browser.mjs
//
// It walks the real learner path - write, press Review with no target chosen,
// then with an explicit target, then a forced degraded evaluation and its
// retry - and leaves screenshots in the OS temp directory for visual review.
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE = process.env.ORENA_BASE_URL || 'http://127.0.0.1:8011';
const SHOTS = process.env.ORENA_SHOT_DIR || tmpdir();
const REVIEW_TIMEOUT = 180000;
const TEXT =
  'Yesterday I go to the shop and buyed some bread for my family. It were a sunny day and the people was very friendly to me.';

const checks = {};
const fail = (message) => {
  throw new Error(message);
};

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const consoleErrors = [];
const evaluateCalls = [];
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text());
});
page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`));
page.on('response', (response) => {
  if (response.url().includes('/api/evaluate')) {
    evaluateCalls.push({ status: response.status(), method: response.request().method() });
  }
});

async function submitAndWait() {
  const settled = page.waitForResponse(
    (response) => response.url().includes('/api/evaluate'),
    { timeout: REVIEW_TIMEOUT },
  );
  await page.locator('#expressionForm button.primary').click();
  return settled;
}

try {
  await page.goto(`${BASE}/#/expression`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#expressionForm #expressionText');
  const textarea = page.locator('#expressionText');
  const target = page.locator('select[name=target]');
  const feedback = page.locator('#writingFeedback');

  await textarea.fill(TEXT);

  /* 1. No proficiency target chosen. The control must not be required and the
     review must still be produced from the sample. */
  checks.targetNotRequired = !(await target.evaluate((el) => el.hasAttribute('required')));
  if (!checks.targetNotRequired) fail('the feedback target is still a required field');
  checks.targetStartsEmpty = (await target.inputValue()) === '';
  if (!checks.targetStartsEmpty) fail('the feedback target did not start unchosen');

  const noTargetResponse = await submitAndWait();
  checks.noTargetStatus = noTargetResponse.status();
  await page.waitForSelector('#writingFeedback .review-headline', { timeout: REVIEW_TIMEOUT });
  const noTargetHtml = await feedback.innerHTML();
  checks.noTargetRendered = noTargetHtml.includes('review-headline') && noTargetHtml.includes('review-dimensions');
  checks.noTargetNotDegraded = !noTargetHtml.includes('data-retry-review');
  if (!checks.noTargetRendered) fail('a review with no target did not render');
  if (!checks.noTargetNotDegraded) fail('a review with no target fell into the retry state');
  await page.screenshot({ path: join(SHOTS, 'orena-writing-no-target.png'), fullPage: true });

  /* 2. Explicit target chosen: the same flow must keep working. */
  await target.selectOption('B1');
  const targetResponse = await submitAndWait();
  checks.targetStatus = targetResponse.status();
  await page.waitForFunction(
    () => document.querySelector('#writingFeedback')?.innerHTML.includes('review-headline'),
    null,
    { timeout: REVIEW_TIMEOUT },
  );
  const targetHtml = await feedback.innerHTML();
  checks.targetRendered = targetHtml.includes('review-headline');
  checks.targetNotDegraded = !targetHtml.includes('data-retry-review');
  if (!checks.targetRendered) fail('a review with an explicit target did not render');
  if (!checks.targetNotDegraded) fail('a review with an explicit target fell into the retry state');

  /* 3. Degraded evaluation: a retryable 503 must keep the draft and offer one
     working retry that resubmits the same submission. */
  await page.route('**/api/evaluate', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          category: 'evaluation_unavailable',
          message: 'AI evaluation is temporarily unavailable. Please try again.',
          retryable: true,
          context: {},
        },
      }),
    }),
  );
  await submitAndWait();
  await page.waitForSelector('#writingFeedback [data-retry-review]', { timeout: 30000 });
  checks.degradedOffersRetry = true;
  checks.draftPreservedOnDegrade = (await textarea.inputValue()) === TEXT;
  if (!checks.draftPreservedOnDegrade) fail('the draft was lost on a degraded evaluation');
  await page.screenshot({ path: join(SHOTS, 'orena-writing-degraded.png'), fullPage: true });
  await page.unroute('**/api/evaluate');

  const retryResponse = page.waitForResponse(
    (response) => response.url().includes('/api/evaluate'),
    { timeout: REVIEW_TIMEOUT },
  );
  await page.locator('#writingFeedback [data-retry-review]').click();
  checks.retryStatus = (await retryResponse).status();
  await page.waitForSelector('#writingFeedback .review-headline', { timeout: REVIEW_TIMEOUT });
  const retryHtml = await feedback.innerHTML();
  checks.retryRendered = retryHtml.includes('review-headline');
  checks.draftPreservedOnRetry = (await textarea.inputValue()) === TEXT;
  if (!checks.retryRendered) fail('the retry did not produce a review');
  if (!checks.draftPreservedOnRetry) fail('the draft was lost across the retry');
  await page.screenshot({ path: join(SHOTS, 'orena-writing-retry.png'), fullPage: true });

  checks.consoleErrors = consoleErrors;
  checks.evaluateCalls = evaluateCalls;
  console.log(JSON.stringify({ checks, screenshots: SHOTS }, null, 2));
} finally {
  await browser.close();
}
