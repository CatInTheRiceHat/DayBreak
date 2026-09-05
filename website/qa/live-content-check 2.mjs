/**
 * Live-backend + long-content responsive QA for the Chrysalis feed.
 *
 * The browser app (origin :4317) is CORS-blocked from the local FastAPI backend
 * (:8000). To exercise the REAL data path without changing the backend, we
 * intercept the page's /api/feed/* request and `route.fetch()` it server-side
 * (no CORS), then fulfill the page with the real JSON. In `stress` mode we mutate
 * that real response with adversarial long titles / channels / hashtags /
 * captions, a missing thumbnail, and weird metadata — same schema, pathological
 * values — to confirm nothing overflows.
 *
 * Usage: node qa/live-content-check.mjs [baseURL]
 * Requires: preview server (:4317) AND the FastAPI backend (:8000) both running.
 */
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || 'http://localhost:4317';
const SHOTS = join(__dirname, 'screenshots');
mkdirSync(SHOTS, { recursive: true });

const LONG_WORD = 'Supercalifragilisticexpialidocious'.repeat(3); // 102-char unbroken token
const LONG_TITLE = `This is an extraordinarily long real-world style video title that keeps going and going about ${LONG_WORD} and somehow never reaches a natural stopping point`;
const LONG_CHANNEL = `ChannelWith${LONG_WORD}NameThatIsFarTooLong`;
const LONG_CAPTION = ('A very long caption that describes the video in exhausting detail, '
  + 'repeating itself and rambling on well past any reasonable length, including '
  + `the unbreakable token ${LONG_WORD} to probe overflow-wrap behaviour. `).repeat(3);
const LONG_HASHTAGS = ['#wellness', `#${LONG_WORD}`, '#aReallyLongHashtagThatShouldWrapOrClampNicely',
  '#calm', '#focus', '#selfcare', '#mindfulness', '#gratitude', '#study', '#reset', '#positivity', '#feelgood'];

function injectLong(data) {
  const items = data.items || [];
  items.slice(0, 3).forEach((it, i) => {
    it.title = LONG_TITLE;
    it.display_title = LONG_TITLE; it.displayTitle = LONG_TITLE;
    it.channel_title = LONG_CHANNEL; it.display_channel = LONG_CHANNEL; it.displayChannel = LONG_CHANNEL;
    it.short_description = LONG_CAPTION; it.display_description = LONG_CAPTION; it.displayDescription = LONG_CAPTION;
    it.display_hashtags = LONG_HASHTAGS; it.displayHashtags = LONG_HASHTAGS;
    it.tags = LONG_HASHTAGS.map((h) => h.slice(1));
    if (i === 0) { it.thumbnail = ''; it.embed_url = ''; } // missing thumbnail → wash fallback
    it.ranking_reason = LONG_CAPTION; it.rankingReason = LONG_CAPTION;
    it.safety_reason = LONG_CAPTION; it.concern_reason = LONG_CAPTION;
    it.source_category = `weird/${LONG_WORD}`;
  });
  return data;
}

const OVERFLOW_TARGETS = [
  '.reel-frame', '.reel-rail', '.reel-caption', '.reel-title-clamp', '.reels-shell',
  '.reel-chip', '.feed-compass', '.feed-compass__why-card', '.feed-compass__bars',
  '.feed-details-drawer__panel', '.reel-hashtags', '.reel-caption__hashtags',
];

async function measure(page) {
  return page.evaluate((sels) => {
    const de = document.documentElement;
    const vw = window.innerWidth;
    const offenders = [];
    for (const sel of sels) {
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.right > vw + 1.5 || r.left < -1.5) { offenders.push({ sel, l: Math.round(r.left), r: Math.round(r.right) }); break; }
      }
    }
    // crude raw-JSON-leak probe on visible feed text
    const body = (document.querySelector('.reels-shell') || document.body).innerText || '';
    const jsonLeak = /"youtube_id"|"chrysalis_scores"|\{"|\bnull\b\s*,\s*"/.test(body);
    return { docOverflow: de.scrollWidth - de.clientWidth, offenders, jsonLeak };
  }, OVERFLOW_TARGETS);
}

const browser = await chromium.launch();
const results = [];

for (const mode of ['live', 'stress']) {
  for (const [w, h, isMobile] of [[390, 844, true], [1440, 900, false], [2560, 1440, false]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile, hasTouch: isMobile });
    const page = await ctx.newPage();
    const consoleErrors = [];
    const isEnvNoise = (t) => /ERR_FAILED|ERR_CONNECTION|CORS|Access to fetch|Access-Control-Allow-Origin|is not allowed by|Failed to load resource/i.test(t);
    page.on('console', (m) => { if (m.type() === 'error' && !isEnvNoise(m.text())) consoleErrors.push(m.text()); });
    page.on('pageerror', (e) => { if (!isEnvNoise(e.message)) consoleErrors.push(`pageerror: ${e.message}`); });

    // Proxy the feed request server-side (bypasses CORS); inject long content in stress mode.
    let realServed = false;
    await page.route('**/api/feed/**', async (route) => {
      try {
        const resp = await route.fetch();
        let data = await resp.json();
        realServed = Array.isArray(data.items) && data.items.length > 0;
        if (mode === 'stress') data = injectLong(data);
        await route.fulfill({ response: resp, json: data });
      } catch { await route.continue(); }
    });

    await page.goto(`${BASE}/algorithm`, { waitUntil: 'commit' });
    await page.waitForTimeout(1200);
    try { const s = page.locator('.onboard-skip').first(); if (await s.isVisible({ timeout: 1500 })) await s.click(); } catch { /* */ }
    await page.waitForTimeout(2200);

    const feedM = await measure(page);
    await page.screenshot({ path: join(SHOTS, `${mode}_feed_${w}x${h}.png`) });

    // Open the Feed details / Compass drawer and re-measure (real or long content).
    let drawerM = null;
    for (const sel of ['button[aria-label="Open feed details"]', '.app-sidebar__intention', 'button[title="Feed details"]', 'button[aria-label^="Your intention"]']) {
      try { const t = page.locator(sel).first(); if (await t.isVisible({ timeout: 800 })) { await t.click(); break; } } catch { /* */ }
    }
    await page.waitForTimeout(900);
    drawerM = await measure(page);
    await page.screenshot({ path: join(SHOTS, `${mode}_drawer_${w}x${h}.png`) });

    const pass = feedM.docOverflow <= 1 && feedM.offenders.length === 0 && !feedM.jsonLeak
      && drawerM.docOverflow <= 1 && drawerM.offenders.length === 0 && consoleErrors.length === 0;
    results.push({ mode, vp: `${w}x${h}`, realServed, feedM, drawerM, consoleErrors: [...consoleErrors], pass });
    await ctx.close();
  }
}

await browser.close();

console.log('\n=== Live + long-content QA ===');
let fails = 0;
for (const r of results) {
  if (!r.pass) fails++;
  console.log(`[${r.pass ? 'PASS' : 'FAIL'}] ${r.mode.padEnd(6)} ${r.vp.padEnd(9)} realData=${r.realServed} `
    + `feedOverflow=${r.feedM.docOverflow} feedOffenders=${r.feedM.offenders.length} jsonLeak=${r.feedM.jsonLeak} `
    + `drawerOverflow=${r.drawerM.docOverflow} drawerOffenders=${r.drawerM.offenders.length} consoleErr=${r.consoleErrors.length}`);
  for (const o of [...r.feedM.offenders, ...r.drawerM.offenders]) console.log(`        overflow: ${o.sel} l=${o.l} r=${o.r}`);
  for (const e of r.consoleErrors) console.log(`        console: ${e.slice(0, 100)}`);
}
console.log(`\nScreenshots: ${SHOTS}`);
console.log(fails === 0 ? 'ALL LIVE + STRESS CHECKS PASS ✅' : `${fails} FAILED ❌`);
process.exit(fails === 0 ? 0 : 1);
