// Manual local verification of the Writing learning-workspace rule.
//
// Not a CI gate: it needs Playwright and the running sandbox app at 8011, and
// it makes two real evaluations through the local Ollama provider. It checks
// the product rule the workspace now follows - the activity and its result
// share one desktop frame, a long result scrolls inside its own region, and a
// narrow screen takes activity and result one frame at a time.
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE = process.env.ORENA_BASE_URL || 'http://127.0.0.1:8011';
const SHOTS = process.env.ORENA_SHOT_DIR || tmpdir();
const TEXT =
  'Yesterday I go to the shop and buyed some bread for my family. It were a sunny day and the people was very friendly to me.';

const report = {};
const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function openWriting(page) {
  await page.goto(`${BASE}/#/expression`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#expressionForm #expressionText');
  await page.locator('#expressionText').fill(TEXT);
  await page.locator('[name=task]').fill('A note about my morning');
}

async function pressReview(page) {
  const settled = page.waitForResponse(
    (response) => response.url().includes('/api/evaluate'),
    { timeout: 180000 },
  );
  await page.locator('#expressionForm button.primary').click();
  const status = (await settled).status();
  await page.waitForSelector('#writingFeedback .review-headline', { timeout: 180000 });
  return status;
}

function snapshot(page) {
  return page.evaluate(() => {
    const style = (selector) => getComputedStyle(document.querySelector(selector));
    const rect = (selector) => {
      const node = document.querySelector(selector);
      return node ? node.getBoundingClientRect() : null;
    };
    const scroll = document.querySelector('.workspace-result__scroll');
    const result = rect('.workspace-result');
    return {
      innerHeight: window.innerHeight,
      scrollY: Math.round(window.scrollY),
      workspaceState: document.querySelector('.learning-workspace')?.dataset.workspace,
      activityVisible: style('.workspace-activity').display !== 'none',
      resultVisible: style('.workspace-result').display !== 'none',
      reviewButtonBottom: Math.round(rect('#expressionForm button.primary').bottom),
      workspaceBottom: Math.round(rect('.learning-workspace').bottom),
      resultTop: result ? Math.round(result.top) : null,
      resultBottom: result ? Math.round(result.bottom) : null,
      internalScroll: scroll ? scroll.scrollHeight > scroll.clientHeight + 1 : false,
      backVisible: Boolean(document.querySelector('[data-back-to-writing]')?.offsetParent),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      hierarchy: document.querySelector('.correction__rule')
        ? {
            ruleBackground: style('.correction__rule').backgroundColor,
            pageBackground: getComputedStyle(document.body).backgroundColor,
            fixColor: style('.correction__fix strong').color,
            whyColor: style('.correction__why span:last-child').color,
            wroteDecoration: style('.correction__wrote del').textDecorationLine,
            labels: [...document.querySelectorAll('.correction__label')].map((n) => n.textContent.trim()),
          }
        : null,
    };
  });
}

/* Desktop: the whole activity and its result inside one viewport. */
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await openWriting(page);
  report.desktopBefore = await snapshot(page);
  await page.screenshot({ path: join(SHOTS, 'workspace-desktop-before.png') });
  report.desktopStatus = await pressReview(page);
  report.desktopAfter = await snapshot(page);
  await page.screenshot({ path: join(SHOTS, 'workspace-desktop-after.png') });
  await page.evaluate(() => {
    const scroll = document.querySelector('.workspace-result__scroll');
    const issues = document.querySelector('.review-issues');
    if (scroll && issues) scroll.scrollTop = issues.offsetTop - 8;
  });
  await page.screenshot({ path: join(SHOTS, 'workspace-desktop-corrections.png') });
  await page.close();
}

/* Narrow: frame one is the activity, frame two is the result, and coming back
   returns the learner to the editor. */
{
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await openWriting(page);
  report.mobileBefore = await snapshot(page);
  await page.screenshot({ path: join(SHOTS, 'workspace-mobile-activity.png') });
  report.mobileStatus = await pressReview(page);
  report.mobileAfter = await snapshot(page);
  await page.screenshot({ path: join(SHOTS, 'workspace-mobile-feedback.png') });
  await page.locator('[data-back-to-writing]').click();
  report.mobileBack = await page.evaluate(() => ({
    workspaceState: document.querySelector('.learning-workspace').dataset.workspace,
    activityVisible: getComputedStyle(document.querySelector('.workspace-activity')).display !== 'none',
    focused: document.activeElement?.id || '',
  }));
  await page.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
