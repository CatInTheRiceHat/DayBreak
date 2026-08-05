/**
 * Guard test: the reels feed must never ask for location.
 *
 * Scans the reels source for browser-geolocation usage and location-asking
 * onboarding/profile fields, so a future change can't silently reintroduce a
 * location permission prompt. Run: npm run test:unit
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const DIR = dirname(fileURLToPath(import.meta.url));

function sourceFiles() {
  return readdirSync(DIR)
    .filter((name) => /\.(jsx?|js)$/.test(name) && !name.endsWith('.test.js'))
    .map((name) => ({ name, text: readFileSync(join(DIR, name), 'utf8') }));
}

test('no browser geolocation API is used anywhere in the feed', () => {
  const offenders = [];
  for (const { name, text } of sourceFiles()) {
    // strip line comments so the explanatory "we do NOT use geolocation" note is ignored
    const code = text.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
    if (/navigator\s*\.\s*geolocation|getCurrentPosition|watchPosition/.test(code)) {
      offenders.push(name);
    }
  }
  assert.deepEqual(offenders, [], `geolocation used in: ${offenders.join(', ')}`);
});

test('the location-asking setup modal is gone', () => {
  const names = sourceFiles().map((f) => f.name);
  assert.ok(!names.includes('LanguageSetupNotice.jsx'), 'LanguageSetupNotice.jsx should be removed');
});

test('no location-permission request helpers remain', () => {
  for (const { name, text } of sourceFiles()) {
    assert.ok(!/requestApproxLocationConsent|use_approx_location/.test(text), `location helper found in ${name}`);
  }
});
