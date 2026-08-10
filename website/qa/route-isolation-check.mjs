import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || 'http://localhost:4317';
const EVIDENCE = join(HERE, '..', '..', 'assets', 'qa', 'step10-route-isolation');
const CONTRACT_VERSION = 'intentional-break-v1';
const PARTICIPANT_ID = '11111111-1111-4111-8111-111111111111';
const SESSION_ID = '22222222-2222-4222-8222-222222222222';
const ACCESS_TOKEN = 'qa-anonymous-bearer-token';
const STORAGE_KEY = 'chrysalis-research-participant-v1';
const CHANNEL = 'daybreak-intentional-break-journey-v1';

const ACTIVE_ROUTES = ['/', '/challenges', '/saved', '/profile', '/diagnostic'];
const COOLDOWN_ROUTES = ['/', '/reels', '/community'];

function envelope(data) {
  return {
    ok: true,
    data,
    server_timestamp: new Date().toISOString(),
    contract_version: CONTRACT_VERSION,
  };
}

function journey(state) {
  const now = Date.now();
  return {
    session_id: SESSION_ID,
    journey_state: state,
    intention: 'quick_break',
    planned_video_count: 5,
    estimated_duration_seconds: 150,
    suggested_cooldown_seconds: 300,
    selected_cooldown_seconds: 300,
    highest_reached_position: state === 'active' ? 0 : 3,
    finish_reason: ['checkout', 'cooldown'].includes(state) ? 'finished_early' : null,
    checkout_status: state === 'checkout' ? 'required' : 'submitted',
    checkout_submitted: state === 'cooldown',
    cooldown_started_at: state === 'cooldown' ? new Date(now - 30_000).toISOString() : null,
    cooldown_ends_at: state === 'cooldown' ? new Date(now + 270_000).toISOString() : null,
    cooldown_remaining_seconds: state === 'cooldown' ? 270 : null,
    remaining_seconds: state === 'cooldown' ? 270 : null,
    cooldown_outcome: null,
    override_started_at: null,
    override_available_at: null,
    override_reason: null,
    completed_at: null,
    cancelled_at: null,
  };
}

function errorEnvelope(status) {
  return {
    ok: false,
    error_code: status === 401 ? 'invalid_credential' : 'service_unavailable',
    message: status === 401 ? 'Credential unavailable.' : 'Study service unavailable.',
    retryable: status >= 500,
    details: null,
    server_timestamp: new Date().toISOString(),
    contract_version: CONTRACT_VERSION,
  };
}

async function installCredential(context) {
  await context.addInitScript(({ key, participant }) => {
    window.localStorage.setItem(key, JSON.stringify(participant));
  }, {
    key: STORAGE_KEY,
    participant: {
      participant_id: PARTICIPANT_ID,
      access_token: ACCESS_TOKEN,
      status: 'active',
    },
  });
}

async function installApi(context, initialState) {
  const control = {
    state: initialState,
    delayMs: 750,
    nextFailure: null,
    currentCalls: 0,
    participantCalls: 0,
  };
  await context.route('**/api/research/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/participants')) {
      control.participantCalls += 1;
      return route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    }
    assert.equal(request.headers().authorization, `Bearer ${ACCESS_TOKEN}`);
    if (path.endsWith('/current')) {
      control.currentCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, control.delayMs));
      if (control.nextFailure) {
        const status = control.nextFailure;
        control.nextFailure = null;
        return route.fulfill({
          status,
          contentType: 'application/json',
          body: JSON.stringify(errorEnvelope(status)),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(envelope({
          journey: control.state ? journey(control.state) : null,
        })),
      });
    }
    if (path.endsWith('/items')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(envelope({
          items: Array.from({ length: 5 }, (_, index) => ({
            post_id: ['dQw4w9WgXcQ', '9bZkp7q19f0', '3JZ_D3ELwOQ', 'L_jWHffIx5E', 'kJQP7kiw5Fk'][index],
            session_position: index + 1,
          })),
          planned_total: 5,
          journey_state: 'active',
          has_more: false,
          next_position: null,
        })),
      });
    }
    if (path.endsWith('/events')) {
      const events = request.postDataJSON().events;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(envelope({
          events: events.map((event, index) => ({
            client_event_id: event.client_event_id,
            server_sequence_number: index + 10,
            newly_accepted: true,
            idempotent_replay: false,
          })),
          journey: journey(control.state || 'active'),
          resulting_lifecycle_events: [],
        })),
      });
    }
    if (path.endsWith('/cooldown')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(envelope({
          journey: journey('cooldown'),
          remaining_seconds: 270,
        })),
      });
    }
    return route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify(errorEnvelope(500)),
    });
  });
  return control;
}

async function assertCheckingBoundary(page, requestedPath) {
  await page.getByRole('heading', { name: 'Checking your DayBreak…' }).waitFor();
  assert.equal(new URL(page.url()).pathname, requestedPath);
  assert.equal(await page.locator('main').count(), 1);
  assert.equal(await page.locator('.reels-shell, .challenges-page, .saved-page').count(), 0);
  assert.equal(await page.locator('nav').count(), 0);
}

async function assertStudyDestination(page, state) {
  await page.waitForURL((url) => url.pathname === '/study');
  try {
    if (state === 'cooldown') {
      await page.getByRole('heading', { name: 'Time for your reset' }).waitFor({ timeout: 5_000 });
    } else if (state === 'active') {
      await page.getByRole('button', { name: 'Finish early' }).waitFor({ timeout: 5_000 });
    }
  } catch (error) {
    console.error('Study destination did not settle:', await page.locator('body').innerText());
    throw error;
  }
  assert.equal(await page.locator('.challenges-page, .saved-page').count(), 0);
}

async function directRouteMatrix(browser, state, routes, screenshotRoute) {
  const results = [];
  for (const requestedPath of routes) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await installCredential(context);
    const api = await installApi(context, state);
    const page = await context.newPage();
    const navigation = page.goto(`${BASE}${requestedPath}`, { waitUntil: 'domcontentloaded' });
    await assertCheckingBoundary(page, requestedPath);
    await navigation;
    await assertStudyDestination(page, state);
    assert.equal(api.participantCalls, 0);
    if (requestedPath === screenshotRoute) {
      await page.screenshot({ path: join(EVIDENCE, `${state}-${requestedPath.slice(1) || 'root'}-redirect.png`) });
    }
    results.push({ requestedPath, finalPath: new URL(page.url()).pathname });
    await context.close();
  }
  return results;
}

const browser = await chromium.launch();
const report = {};

try {
  report.active = await directRouteMatrix(browser, 'active', ACTIVE_ROUTES, '/challenges');
  report.cooldown = await directRouteMatrix(browser, 'cooldown', COOLDOWN_ROUTES, '/community');

  const backContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await installCredential(backContext);
  const backApi = await installApi(backContext, null);
  const backPage = await backContext.newPage();
  await backPage.goto(`${BASE}/challenges`);
  await backPage.locator('.challenges-page').waitFor();
  await backPage.goto(`${BASE}/study`);
  await backPage.getByRole('heading', { name: 'Welcome to the DayBreak pilot' }).waitFor();
  const historyLength = await backPage.evaluate(() => window.history.length);
  backApi.state = 'active';
  const backNavigation = backPage.goBack({ waitUntil: 'domcontentloaded' });
  await assertCheckingBoundary(backPage, '/challenges');
  await backNavigation;
  await assertStudyDestination(backPage, 'active');
  await backPage.waitForTimeout(250);
  assert.equal(new URL(backPage.url()).pathname, '/study');
  assert.ok(await backPage.evaluate(() => window.history.length) <= historyLength);
  await backPage.screenshot({ path: join(EVIDENCE, 'browser-back-active-redirect.png') });
  await backContext.close();

  const refreshContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await installCredential(refreshContext);
  await installApi(refreshContext, 'cooldown');
  const refreshPage = await refreshContext.newPage();
  const refreshNavigation = refreshPage.goto(`${BASE}/profile`, { waitUntil: 'domcontentloaded' });
  await assertCheckingBoundary(refreshPage, '/profile');
  await refreshNavigation;
  await assertStudyDestination(refreshPage, 'cooldown');
  await refreshPage.screenshot({ path: join(EVIDENCE, 'refresh-profile-cooldown-redirect.png') });
  await refreshContext.close();

  const retryContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await installCredential(retryContext);
  const retryApi = await installApi(retryContext, 'active');
  retryApi.nextFailure = 503;
  const retryPage = await retryContext.newPage();
  await retryPage.goto(`${BASE}/saved`, { waitUntil: 'domcontentloaded' });
  await retryPage.getByRole('heading', { name: "We couldn't check your DayBreak session." }).waitFor();
  assert.equal(await retryPage.locator('.saved-page, .reels-shell').count(), 0);
  await retryPage.screenshot({ path: join(EVIDENCE, 'retryable-error-fails-closed.png') });
  await retryPage.getByRole('button', { name: 'Try again' }).click();
  await assertStudyDestination(retryPage, 'active');
  assert.equal(retryApi.participantCalls, 0);
  await retryContext.close();

  const crossTabContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await installCredential(crossTabContext);
  const crossTabApi = await installApi(crossTabContext, null);
  const studyTab = await crossTabContext.newPage();
  const productTab = await crossTabContext.newPage();
  await productTab.goto(`${BASE}/challenges`);
  await productTab.locator('.challenges-page').waitFor();
  await studyTab.goto(`${BASE}/study`);
  await studyTab.getByRole('heading', { name: 'Welcome to the DayBreak pilot' }).waitFor();
  crossTabApi.state = 'planned';
  await studyTab.evaluate(({ channel, sessionId }) => {
    const synchronizer = new BroadcastChannel(channel);
    synchronizer.postMessage({ session_id: sessionId, changed_at: Date.now() });
    synchronizer.close();
  }, { channel: CHANNEL, sessionId: SESSION_ID });
  await productTab.waitForURL((url) => url.pathname === '/study');
  await productTab.getByRole('heading', { name: 'Ready for your DayBreak?' }).waitFor();
  assert.equal(await productTab.locator('.challenges-page').count(), 0);
  await productTab.screenshot({ path: join(EVIDENCE, 'cross-tab-planned-redirect.png') });
  crossTabApi.state = null;
  await productTab.goto(`${BASE}/challenges`);
  await productTab.locator('.challenges-page').waitFor();
  await crossTabContext.close();

  const noCredentialContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const noCredentialApi = await installApi(noCredentialContext, null);
  const noCredentialPage = await noCredentialContext.newPage();
  await noCredentialPage.goto(`${BASE}/challenges`);
  await noCredentialPage.locator('.challenges-page').waitFor();
  assert.equal(noCredentialApi.currentCalls, 0);
  assert.equal(noCredentialApi.participantCalls, 0);
  await noCredentialContext.close();

  const invalidContext = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await installCredential(invalidContext);
  const invalidApi = await installApi(invalidContext, null);
  invalidApi.nextFailure = 401;
  const invalidPage = await invalidContext.newPage();
  await invalidPage.goto(`${BASE}/challenges`);
  await invalidPage.locator('.challenges-page').waitFor();
  assert.equal(invalidApi.participantCalls, 0);
  assert.equal(await invalidPage.evaluate((key) => Boolean(localStorage.getItem(key)), STORAGE_KEY), true);
  assert.doesNotMatch(await invalidPage.locator('body').innerText(), new RegExp(ACCESS_TOKEN));
  await invalidContext.close();
} finally {
  await browser.close();
}

console.log('=== Intentional Break route-isolation QA ===');
for (const [state, entries] of Object.entries(report)) {
  entries.forEach(({ requestedPath, finalPath }) => {
    console.log(`[PASS] ${state.padEnd(8)} ${requestedPath.padEnd(14)} -> ${finalPath}`);
  });
}
console.log('[PASS] Back, refresh, retry, cross-tab, no-credential, and invalid-credential scenarios');
console.log(`Evidence: ${EVIDENCE}`);
