/**
 * Focused route-level QA for /study.
 *
 * Uses the existing Playwright dependency and deterministic in-browser API
 * mocks. No study condition is supplied to the UI, and the production research
 * service remains unchanged.
 *
 * Usage: npm run qa:study -- [baseURL]
 * Requires a preview/dev server (default http://localhost:4317).
 */
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || 'http://localhost:4317';
const SHOTS = join(HERE, 'screenshots', 'study');

const VIEWPORTS = [
  { name: '320x568', width: 320, height: 568, mobile: true },
  { name: '375x667', width: 375, height: 667, mobile: true },
  { name: '768x1024', width: 768, height: 1024, mobile: true },
  { name: '1024x768', width: 1024, height: 768, mobile: false },
  { name: '1440x900', width: 1440, height: 900, mobile: false },
];

const PARTICIPANT_ID = '11111111-1111-4111-8111-111111111111';
const SESSION_ID = '22222222-2222-4222-8222-222222222222';

mkdirSync(SHOTS, { recursive: true });

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installResearchApiMock(context, options = {}) {
  const state = {
    completionCalls: 0,
    participantCalls: 0,
  };

  await context.route('**/api/research/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/participants')) {
      state.participantCalls += 1;
      if (options.loadingGate && state.participantCalls === 1) await options.loadingGate;
      if (options.failFirstParticipant && state.participantCalls === 1) {
        return json(route, { detail: 'temporarily unavailable' }, 503);
      }
      return json(route, {
        participant_id: PARTICIPANT_ID,
        access_token: 'anonymous-bearer-token',
      }, 201);
    }

    if (path.endsWith('/sessions') && request.method() === 'POST') {
      return json(route, {
        session_id: SESSION_ID,
        participant_id: PARTICIPANT_ID,
        status: 'active',
        next_sequence_number: 1,
      }, 201);
    }

    if (path.endsWith('/feed')) {
      assert.equal(request.headers().authorization, 'Bearer anonymous-bearer-token');
      return json(route, { items: [], has_more: false });
    }

    if (path.endsWith('/events/batch')) {
      const payload = request.postDataJSON();
      return json(route, {
        accepted: payload.events.map(({ event_id }) => ({ event_id })),
        duplicate_event_ids: [],
      });
    }

    if (path.endsWith('/complete')) {
      state.completionCalls += 1;
      return json(route, { session_id: SESSION_ID, status: 'completed' });
    }

    if (path.includes(`/sessions/${SESSION_ID}`)) {
      return json(route, {
        session_id: SESSION_ID,
        participant_id: PARTICIPANT_ID,
        status: 'active',
        next_sequence_number: 1,
      });
    }

    return json(route, { detail: `Unhandled QA route: ${path}` }, 500);
  });

  return state;
}

async function inspectActiveStudy(page) {
  return page.evaluate(() => {
    const control = document.querySelector('.research-session-controls');
    const completeButton = control?.querySelector('button');
    const studyLabel = control?.querySelector('.research-session-controls__label');
    const controlRect = control?.getBoundingClientRect();
    const buttonRect = completeButton?.getBoundingClientRect();
    const labelRect = studyLabel?.getBoundingClientRect();
    const labelStyle = studyLabel ? getComputedStyle(studyLabel) : null;
    const duplicateIds = [...document.querySelectorAll('[id]')]
      .map((element) => element.id)
      .filter((id, index, ids) => ids.indexOf(id) !== index);
    const visibleText = document.body.innerText;

    return {
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      hasMain: Boolean(document.querySelector('main.reels-shell')),
      h1Count: document.querySelectorAll('h1').length,
      duplicateIds,
      conditionLeak: /assigned[_ ]condition|feed[_ ]condition|\bregular\b|\bbalanced\b/i.test(visibleText),
      dayBreakVisible: Boolean(
        studyLabel?.textContent?.includes('DayBreak research')
        && labelRect?.width > 0
        && labelRect?.height > 0
        && labelStyle?.display !== 'none'
        && labelStyle?.visibility !== 'hidden'
        && labelStyle?.opacity !== '0'
      ),
      controlClipped: !controlRect
        || controlRect.left < -1
        || controlRect.right > window.innerWidth + 1
        || controlRect.top < -1
        || controlRect.bottom > window.innerHeight + 1,
      completeButtonName: completeButton?.getAttribute('aria-label') || completeButton?.textContent?.trim(),
      completeButtonWidth: Math.round(buttonRect?.width || 0),
      completeButtonHeight: Math.round(buttonRect?.height || 0),
    };
  });
}

function assertActiveStudy(result, viewportName) {
  assert.ok(result.documentOverflow <= 1, `${viewportName}: horizontal overflow (${result.documentOverflow}px)`);
  assert.equal(result.hasMain, true, `${viewportName}: study feed needs a main landmark`);
  assert.equal(result.h1Count, 1, `${viewportName}: expected one route-level h1`);
  assert.deepEqual(result.duplicateIds, [], `${viewportName}: duplicate ids found`);
  assert.equal(result.conditionLeak, false, `${viewportName}: hidden study condition leaked into copy`);
  assert.equal(result.dayBreakVisible, true, `${viewportName}: DayBreak study label is missing`);
  assert.equal(result.controlClipped, false, `${viewportName}: session controls are clipped`);
  assert.equal(result.completeButtonName, 'Complete test session');
  assert.ok(result.completeButtonWidth >= 44, `${viewportName}: completion target is too narrow`);
  assert.ok(result.completeButtonHeight >= 44, `${viewportName}: completion target is too short`);
}

function collectRuntimeErrors(page) {
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && !/Failed to load resource|ERR_/i.test(message.text())) {
      errors.push(message.text());
    }
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

const browser = await chromium.launch();
const results = [];

try {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.mobile,
      hasTouch: viewport.mobile,
      reducedMotion: 'reduce',
    });
    const page = await context.newPage();
    const runtimeErrors = collectRuntimeErrors(page);
    let releaseLoading;
    const loadingGate = new Promise((resolve) => { releaseLoading = resolve; });
    const apiState = await installResearchApiMock(context, { loadingGate });

    await page.goto(`${BASE}/study`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Preparing your session' }).waitFor();
    const loadingAnimation = await page.locator('.study-state__icon svg').evaluate(
      (element) => getComputedStyle(element).animationName,
    );
    assert.equal(loadingAnimation, 'none', `${viewport.name}: reduced motion should stop the loader`);

    releaseLoading();
    await page.getByRole('button', { name: 'Complete test session' }).waitFor();

    const activeResult = await inspectActiveStudy(page);
    assertActiveStudy(activeResult, viewport.name);

    await page.getByRole('button', { name: 'Complete test session' }).focus();
    const focusOutline = await page.getByRole('button', { name: 'Complete test session' }).evaluate(
      (element) => parseFloat(getComputedStyle(element).outlineWidth),
    );
    assert.ok(focusOutline >= 2, `${viewport.name}: completion focus ring is not visible`);

    await page.screenshot({ path: join(SHOTS, `active-${viewport.name}.png`) });
    await page.getByRole('button', { name: 'Complete test session' }).click();
    await page.getByRole('heading', { name: 'Session complete' }).waitFor();
    assert.equal(apiState.completionCalls, 1, `${viewport.name}: completion endpoint call count changed`);

    const completedLayout = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      status: document.querySelector('[role="status"]')?.textContent?.trim(),
    }));
    assert.ok(completedLayout.overflow <= 1, `${viewport.name}: completion screen overflows`);
    assert.equal(completedLayout.status, 'Your anonymous research events were saved.');
    assert.deepEqual(runtimeErrors, [], `${viewport.name}: browser runtime errors`);

    results.push({ viewport: viewport.name, active: activeResult, pass: true });
    await context.close();
  }

  const retryContext = await browser.newContext({ viewport: { width: 375, height: 667 } });
  const retryPage = await retryContext.newPage();
  const retryErrors = collectRuntimeErrors(retryPage);
  await installResearchApiMock(retryContext, { failFirstParticipant: true });
  await retryPage.goto(`${BASE}/study`, { waitUntil: 'domcontentloaded' });
  await retryPage.getByRole('alert').waitFor();
  const retryButton = retryPage.getByRole('button', { name: 'Try again' });
  const retrySize = await retryButton.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  });
  assert.ok(retrySize.width >= 44 && retrySize.height >= 44, 'Retry target is smaller than 44px');
  await retryButton.click();
  await retryPage.getByRole('button', { name: 'Complete test session' }).waitFor();
  assert.deepEqual(retryErrors, [], 'Retry flow produced browser runtime errors');
  await retryContext.close();
} finally {
  await browser.close();
}

console.log('\n=== DayBreak /study QA ===');
for (const result of results) {
  console.log(`[PASS] ${result.viewport.padEnd(9)} overflow=${result.active.documentOverflow}px target=${result.active.completeButtonWidth}x${result.active.completeButtonHeight}`);
}
console.log('[PASS] loading, reduced motion, error/retry, focus, hidden-condition, and completion checks');
console.log(`Screenshots: ${SHOTS}`);
