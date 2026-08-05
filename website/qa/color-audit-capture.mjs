/**
 * Capture a deterministic route/viewport matrix for the DayBreak color audit.
 *
 * Usage: node qa/color-audit-capture.mjs before|after [baseURL]
 */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const stage = process.argv[2];
if (!['before', 'after'].includes(stage)) {
  throw new Error('Pass either "before" or "after" as the first argument.');
}

const baseURL = process.argv[3] || 'http://localhost:4317';
const outputDirectory = resolve(process.cwd(), '..', 'color-audit-screenshots', stage);
const cases = [
  { name: 'feed-desktop-light', route: '/', width: 1440, height: 900, theme: 'light' },
  { name: 'feed-laptop-light', route: '/', width: 1280, height: 800, theme: 'light' },
  { name: 'feed-tablet-light', route: '/', width: 768, height: 1024, theme: 'light', mobile: true },
  { name: 'feed-mobile-light', route: '/', width: 390, height: 844, theme: 'light', mobile: true },
  { name: 'feed-mobile-dark', route: '/', width: 390, height: 844, theme: 'dark', mobile: true },
  { name: 'challenges-desktop-light', route: '/challenges', width: 1440, height: 900, theme: 'light' },
  { name: 'challenges-mobile-dark', route: '/challenges', width: 390, height: 844, theme: 'dark', mobile: true },
  { name: 'saved-tablet-light', route: '/saved', width: 768, height: 1024, theme: 'light', mobile: true },
  { name: 'login-desktop-light', route: '/login', width: 1440, height: 900, theme: 'light' },
  { name: 'login-mobile-dark', route: '/login', width: 390, height: 844, theme: 'dark', mobile: true },
  { name: 'diagnostic-mobile-light', route: '/diagnostic', width: 390, height: 844, theme: 'light', mobile: true },
  { name: 'profile-tablet-light', route: '/profile', width: 768, height: 1024, theme: 'light', mobile: true },
  { name: 'study-desktop-light', route: '/study', width: 1440, height: 900, theme: 'light' },
];

mkdirSync(outputDirectory, { recursive: true });
const browser = await chromium.launch();

try {
  for (const item of cases) {
    const context = await browser.newContext({
      viewport: { width: item.width, height: item.height },
      isMobile: Boolean(item.mobile),
      hasTouch: Boolean(item.mobile),
      reducedMotion: 'reduce',
      colorScheme: item.theme,
    });

    await context.addInitScript(({ theme }) => {
      localStorage.setItem('chrysalis-intro-done', '1');
      localStorage.setItem('chrysalis-diagnostic-done', '1');
      localStorage.setItem('chrysalis-algorithm-onboarded', '1');
      localStorage.setItem('chrysalis-algorithm-mode', 'flutter-feed');
      localStorage.setItem('chrysalis-algorithm-theme', theme);
    }, { theme: item.theme });

    const page = await context.newPage();
    await page.goto(`${baseURL}${item.route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(item.route === '/' ? 2200 : 900);
    await page.screenshot({
      path: resolve(outputDirectory, `${item.name}.png`),
      fullPage: item.route !== '/',
      animations: 'disabled',
    });
    await context.close();
    console.log(`[captured] ${item.name}`);
  }
} finally {
  await browser.close();
}

console.log(`Screenshots: ${outputDirectory}`);
