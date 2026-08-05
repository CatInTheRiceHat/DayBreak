/**
 * Responsive evidence capture for the DayBreak problem/solution matrix audit.
 *
 * Usage: node qa/problem-matrix-audit.mjs [baseURL] [apiURL]
 */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const BASE = process.argv[2] || 'http://127.0.0.1:4318';
const API = process.argv[3] || 'http://127.0.0.1:8000';
const OUTPUT = resolve(process.cwd(), '..', 'screenshots', 'problem-matrix-audit');

const VIEWPORTS = [
  { name: 'desktop-1280', width: 1280, height: 800 },
  { name: 'tablet-768', width: 768, height: 1024, mobile: true },
  { name: 'mobile-375', width: 375, height: 812, mobile: true },
];

mkdirSync(OUTPUT, { recursive: true });
const browser = await chromium.launch();
const results = [];

async function preparePage(context) {
  const page = await context.newPage();
  const runtimeErrors = [];
  page.on('pageerror', (error) => runtimeErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error' && !/Failed to load resource|ERR_/i.test(message.text())) {
      runtimeErrors.push(message.text());
    }
  });
  await page.route('**/api/**', async (route) => {
    const incoming = new URL(route.request().url());
    try {
      const response = await route.fetch({
        url: `${API}${incoming.pathname}${incoming.search}`,
      });
      await route.fulfill({ response });
    } catch {
      await route.continue();
    }
  });
  return { page, runtimeErrors };
}

async function capture(page, name, fullPage = false) {
  const overflow = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  await page.screenshot({
    path: resolve(OUTPUT, `${name}.png`),
    fullPage,
    animations: 'disabled',
  });
  return overflow;
}

async function openFeed(page, query = '') {
  await page.goto(`${BASE}/${query}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.reels-feed, .reels-onboard', { timeout: 8_000 });
  await page.waitForTimeout(1_800);
}

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: Boolean(viewport.mobile),
    hasTouch: Boolean(viewport.mobile),
    reducedMotion: 'reduce',
  });
  await context.addInitScript(() => {
    localStorage.setItem('chrysalis-intro-done', '1');
    localStorage.setItem('chrysalis-diagnostic-done', '1');
    localStorage.setItem('chrysalis-algorithm-onboarded', '1');
    localStorage.setItem('chrysalis-algorithm-mode', 'flutter-feed');
    localStorage.setItem('chrysalis-algorithm-theme', 'light');
  });
  const { page, runtimeErrors } = await preparePage(context);

  await openFeed(page);
  const feedOverflow = await capture(page, `review-feed-${viewport.name}`);

  await page.getByRole('button', { name: 'Open feed details' }).first().click();
  await page.waitForSelector('.feed-details-drawer__panel');
  const detailsOverflow = await capture(page, `review-feed-details-${viewport.name}`);

  await page.getByRole('button', { name: 'Change intention' }).click();
  await page.waitForSelector('.reels-onboard');
  const modesOverflow = await capture(page, `review-mode-picker-${viewport.name}`);

  results.push({ viewport: viewport.name, view: 'feed', overflow: feedOverflow, runtimeErrors: [...runtimeErrors] });
  results.push({ viewport: viewport.name, view: 'details', overflow: detailsOverflow, runtimeErrors: [] });
  results.push({ viewport: viewport.name, view: 'mode-picker', overflow: modesOverflow, runtimeErrors: [] });
  await context.close();
}

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: Boolean(viewport.mobile),
    hasTouch: Boolean(viewport.mobile),
    reducedMotion: 'reduce',
  });
  await context.addInitScript(() => {
    localStorage.setItem('chrysalis-intro-done', '1');
    localStorage.setItem('chrysalis-diagnostic-done', '1');
    localStorage.setItem('chrysalis-algorithm-onboarded', '1');
    localStorage.setItem('chrysalis-algorithm-mode', 'flutter-feed');
    localStorage.setItem('chrysalis-algorithm-theme', 'light');
  });
  const { page, runtimeErrors } = await preparePage(context);
  await openFeed(page, '?breaks=demo');

  await page.getByRole('button', { name: 'Why this video?' }).first().click();
  await page.waitForSelector('.reel-why');
  const whyOverflow = await capture(page, `review-why-panel-${viewport.name}`);
  await page.getByRole('button', { name: 'Close explanation' }).click();

  await page.getByRole('button', { name: 'Open comments' }).first().click();
  await page.waitForSelector('.comments');
  const commentsOverflow = await capture(page, `review-comments-${viewport.name}`);
  await page.getByRole('button', { name: 'Close comments' }).click();

  await page.locator('.reels-fab--demo').first().evaluate((button) => button.click());
  await page.waitForSelector('.break-screen');
  const breakOverflow = await capture(page, `review-break-${viewport.name}`);

  results.push({ viewport: viewport.name, view: 'why', overflow: whyOverflow, runtimeErrors: [...runtimeErrors] });
  results.push({ viewport: viewport.name, view: 'comments', overflow: commentsOverflow, runtimeErrors: [] });
  results.push({ viewport: viewport.name, view: 'break', overflow: breakOverflow, runtimeErrors: [] });
  await context.close();
}

const routeCases = [
  { name: 'challenges', path: '/challenges', waitFor: '.challenges', fullPage: true },
  { name: 'diagnostic', path: '/diagnostic', waitFor: '.diag-quiz', fullPage: true },
  { name: 'login', path: '/login', waitFor: '.cx-card', fullPage: true },
  { name: 'study', path: '/study', waitFor: '.study-route, .study-state', fullPage: false, longWait: true },
];

for (const routeCase of routeCases) {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: Boolean(viewport.mobile),
      hasTouch: Boolean(viewport.mobile),
      reducedMotion: 'reduce',
    });
    await context.addInitScript(({ diagnostic }) => {
      localStorage.setItem('chrysalis-intro-done', '1');
      if (diagnostic) localStorage.removeItem('chrysalis-diagnostic-done');
      else localStorage.setItem('chrysalis-diagnostic-done', '1');
      localStorage.setItem('chrysalis-algorithm-onboarded', '1');
      localStorage.setItem('chrysalis-algorithm-mode', 'flutter-feed');
      localStorage.setItem('chrysalis-algorithm-theme', 'light');
    }, { diagnostic: routeCase.name === 'diagnostic' });
    const { page, runtimeErrors } = await preparePage(context);
    await page.goto(`${BASE}${routeCase.path}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector(routeCase.waitFor, { timeout: 10_000 });
    await page.waitForTimeout(routeCase.longWait ? 2_200 : 800);
    const overflow = await capture(
      page,
      `review-${routeCase.name}-${viewport.name}`,
      routeCase.fullPage,
    );
    results.push({ viewport: viewport.name, view: routeCase.name, overflow, runtimeErrors });
    await context.close();
  }
}

await browser.close();

let failures = 0;
for (const result of results) {
  const overflowPx = result.overflow.scrollWidth - result.overflow.viewportWidth;
  const pass = overflowPx <= 1 && result.runtimeErrors.length === 0;
  if (!pass) failures += 1;
  console.log(`[${pass ? 'PASS' : 'FAIL'}] ${result.viewport.padEnd(12)} ${result.view.padEnd(12)} overflow=${overflowPx} errors=${result.runtimeErrors.length}`);
  for (const error of result.runtimeErrors) console.log(`  ${error}`);
}
console.log(`Screenshots: ${OUTPUT}`);
process.exitCode = failures ? 1 : 0;
