import assert from 'node:assert/strict';
import test from 'node:test';
import {
  calculateServerClockOffsetMs,
  createServerTimeReference,
  formatCountdown,
  remainingSecondsAt,
} from './cooldownTime.js';

test('server/client offset handles aligned, ahead, and behind client clocks', () => {
  const server = '2026-08-07T12:00:00.000Z';
  assert.equal(calculateServerClockOffsetMs(server, Date.parse(server)), 0);
  assert.equal(calculateServerClockOffsetMs(server, Date.parse('2026-08-07T12:01:00.000Z')), -60_000);
  assert.equal(calculateServerClockOffsetMs(server, Date.parse('2026-08-07T11:59:00.000Z')), 60_000);
});

test('remaining time follows the authoritative end using corrected server time', () => {
  const reference = createServerTimeReference({
    serverTimestamp: '2026-08-07T12:00:00.000Z',
    endsAt: '2026-08-07T12:10:00.000Z',
    remainingSeconds: 600,
    clientNowMs: Date.parse('2026-08-07T13:00:00.000Z'),
  });
  assert.equal(remainingSecondsAt(reference, Date.parse('2026-08-07T13:00:00.000Z')), 600);
  assert.equal(remainingSecondsAt(reference, Date.parse('2026-08-07T13:09:59.001Z')), 1);
  assert.equal(remainingSecondsAt(reference, Date.parse('2026-08-07T13:10:00.000Z')), 0);
  assert.equal(remainingSecondsAt(reference, Date.parse('2026-08-07T13:11:00.000Z')), 0);
});

test('authoritative remaining seconds are a safe fallback when timestamps are invalid', () => {
  const reference = createServerTimeReference({
    serverTimestamp: 'invalid',
    endsAt: 'also-invalid',
    remainingSeconds: 15,
    clientNowMs: 1_000,
  });
  assert.equal(remainingSecondsAt(reference, 1_000), 15);
  assert.equal(remainingSecondsAt(reference, 15_001), 1);
  assert.equal(remainingSecondsAt(reference, 16_000), 0);
  assert.equal(createServerTimeReference({ serverTimestamp: 'bad', endsAt: 'bad' }), null);
  assert.equal(remainingSecondsAt(null), null);
});

test('countdown formatting is display-only and clamps at zero', () => {
  assert.equal(formatCountdown(0), '0:00');
  assert.equal(formatCountdown(65), '1:05');
  assert.equal(formatCountdown(3_661), '1:01:01');
  assert.equal(formatCountdown(Number.NaN), '--:--');
});
