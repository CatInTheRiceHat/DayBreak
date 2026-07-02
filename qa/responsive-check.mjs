/**
 * Lightweight responsive QA for the Chrysalis algorithm/reels demo.
 *
 * Drives the built app across the target viewport matrix and asserts:
 *   - no horizontal overflow (document + key elements)
 *   - reel card / frame fits within the viewport
 *   - action rail and mode controls are not clipped off-screen
 *   - no console errors
 * Captures a screenshot per viewport into qa/screenshots/.
 *
 * Usage:  node qa/responsive-check.mjs [baseURL]
 * Requires the preview/dev server already running (default http://localhost:4317).
 */
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || 'http://localhost:4317';
const SHOTS = join(__dirname, 'screenshots');
mkdirSync(SHOTS, { recursive: true });

// /algorithm shows an onboarding mode-picker first, then the feed. We QA both.
const ROUTE = '/algorithm';

const VIEWPORTS = [
  { name: '390x844-mobile',        width: 390,  height: 844,  dpr: 3, mobile: true },
  { name: '430x932-large-mobile',  width: 430,  height: 932,  dpr: 3, mobile: true },
  { name: '768x1024-tablet',       width: 768,  height: 1024, dpr: 2, mobile: true },
  { name: '1024x768-landscape',    width: 1024, height: 768,  dpr: 2 },
  { name: '1366x768-laptop',       width: 1366, height: 768,  dpr: 1 },
  { name: '1440x900-desktop',      width: 1440, height: 900,  dpr: 1 },
  { name: '1920x1080-monitor',     width: 1920, height: 1080, dpr: 1 },
  { name: '2560x1440-monitor',     width: 2560, height: 1440, dpr: 1 },
];

// Selectors that must never push past the right edge of the viewport.
const ONBOARD_TARGETS = [
  '.reels-onboard', '.reels-onboard__title', '.mode-grid', '.mode-card',
  '.onboard-cta', '.reels-onboard__privacy',
];
const FEED_TARGETS = [
  '.reel-frame', '.reel-rail', '.reel-caption', '.reel-title-clamp',
  '.mode-tabs', '.compass-panel', '.feed-compass', '.reels-shell',
  '.reel-chip', '.chrysalis-topbar', '.app-bottom-nav',
];

async function measureOverflow(page, targets) {
  return page.evaluate((sels) => {
    const de = document.documentElement;
    const docOverflow = de.scrollWidth - de.clientWidth;
    const vw = window.innerWidth;
    const offenders = [];
    for (const sel of sels) {
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.right > vw + 1.5 || r.left < -1.5) {
          offenders.push({ sel, left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width) });
          break;
        }
      }
    }
    return { docOverflow, vw, offenders };
  }, targets);
}

const results = [];
let hardFailures = 0;

const browser = await chromium.launch();

for (const vp of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: vp.dpr,
    isMobile: !!vp.mobile,
    hasTouch: !!vp.mobile,
  });
  const page = await context.newPage();
  const consoleErrors = [];
  // Ignore environmental backend-absence noise in standalone QA (the app falls
  // back to seed data); still capture real JS/React/runtime errors.
  const isEnvNoise = (t) => /ERR_CONNECTION_REFUSED|Failed to load resource|net::ERR|Access-Control-Allow-Origin|is not allowed by|\/api\//i.test(t);
  page.on('console', (msg) => { if (msg.type() === 'error' && !isEnvNoise(msg.text())) consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => { if (!isEnvNoise(err.message)) consoleErrors.push(`pageerror: ${err.message}`); });

  await page.goto(`${BASE}${ROUTE}`, { waitUntil: 'commit' });
  await page.waitForTimeout(1400);

  async function record(phase, targets) {
    const m = await measureOverflow(page, targets);
    await page.screenshot({ path: join(SHOTS, `${phase}_${vp.name}.png`), fullPage: false });
    const pass = m.docOverflow <= 1 && m.offenders.length === 0 && consoleErrors.length === 0;
    if (!pass) hardFailures += 1;
    results.push({ viewport: vp.name, phase, docOverflowPx: m.docOverflow, offenders: m.offenders, consoleErrors: [...consoleErrors], pass });
    consoleErrors.length = 0;
  }

  // Phase 1 — onboarding mode picker
  await record('onboarding', ONBOARD_TARGETS);

  // Enter the feed via "Skip for now" (default mode), then QA the feed.
  try {
    const skip = page.locator('.onboard-skip, button:has-text("Skip for now")').first();
    if (await skip.isVisible({ timeout: 1500 })) { await skip.click(); }
  } catch { /* already in feed */ }
  await page.waitForTimeout(1600);
  await record('feed', FEED_TARGETS);

  await context.close();
}

await browser.close();

console.log('\n=== Responsive QA results ===');
for (const r of results) {
  const status = r.pass ? 'PASS' : 'FAIL';
  console.log(`[${status}] ${r.viewport.padEnd(22)} ${r.phase.padEnd(11)} docOverflow=${r.docOverflowPx}px  offenders=${r.offenders.length}  consoleErrors=${r.consoleErrors.length}`);
  for (const o of r.offenders) console.log(`         overflow: ${o.sel}  left=${o.left} right=${o.right} (w=${o.w})`);
  for (const e of r.consoleErrors) console.log(`         console: ${e}`);
}
console.log(`\nScreenshots: ${SHOTS}`);
console.log(hardFailures === 0 ? '\nALL VIEWPORTS PASS ✅' : `\n${hardFailures} viewport(s) FAILED ❌`);
process.exit(hardFailures === 0 ? 0 : 1);
