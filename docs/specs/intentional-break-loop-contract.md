# Intentional Break Loop Contract

## 1. Purpose

This document freezes the shared architectural contract for the first DayBreak Intentional Break Loop pilot. The pilot tests one question: can a participant choose a finite feed session, reach the boundary they selected, complete a short reflection, and spend a visible period away from the feed?

This is the normative contract for new Intentional Break Loop sessions. Later frontend, API, persistence, analytics, and participant-material work must conform to it.

## 2. Scope and non-goals

The first pilot provides one fixed feed policy, a participant-selected finite allowance, a three-question checkout, and a timed cooldown with a deliberate early-return override.

This contract does not implement the feature, define a production database migration, modify API behavior, change the active feed, or specify a user interface. It does not create a regular-versus-balanced experiment. It does not reinterpret historical research sessions; it applies only to newly created Intentional Break Loop sessions.

## 3. Definitions

- **Participant credential:** The anonymous credential created or resumed when `/study` opens. A credential is not a session.
- **Session:** One planned finite-feed experience and its checkout and cooldown lifecycle.
- **Nonterminal session:** A session in `planned`, `active`, `checkout`, or `cooldown`.
- **Terminal session:** A session in `completed` or `cancelled`.
- **Planned video count (N):** The participant-selected session-wide allowance: 5, 10, 20, or 40.
- **Stored batch:** Exactly N eligible posts, reserved in a stable order for a successfully created plan.
- **Global session position:** The immutable one-based position of an item in the stored batch, from 1 through N.
- **Meaningful impression:** An accepted `post_impression` meeting the existing threshold of at least 60% visibility for one continuous second.
- **Server time:** The authoritative clock for cooldown and override timing.
- **Semantic idempotency:** Repeating a lifecycle command produces no duplicate transition or lifecycle event and returns the already-established result where appropriate.

## 4. Fixed feed policy

Every new session governed by this contract uses:

- Session condition: `intentional_break_v1`
- Feed policy: `balanced-v1`

These values are fixed attributes, not experiment assignments. Historical research sessions retain their original semantics and policy metadata.

## 5. Participant initialization

Opening `/study` creates or resumes only the anonymous participant credential. It must not create, plan, or start a research session automatically.

After credential initialization, the future server checks for an existing nonterminal session. If one exists, `/study` resumes it. If none exists, the participant may begin planning.

## 6. Lifecycle state machine

The lifecycle states are `planned`, `active`, `checkout`, `cooldown`, `completed`, and `cancelled`.

The only valid transitions are:

| From | To | Required qualifier |
| --- | --- | --- |
| No session | `planned` | Successful plan creation |
| `planned` | `active` | Participant confirmation |
| `planned` | `cancelled` | Cancellation |
| `active` | `checkout` | Finish reason `boundary_reached` |
| `active` | `checkout` | Finish reason `finished_early` |
| `checkout` | `cooldown` | Valid checkout submission |
| `cooldown` | `completed` | Cooldown outcome `completed` |
| `cooldown` | `completed` | Cooldown outcome `overridden` |

No other transition is valid. In particular, there is no direct `active` to `completed` transition.

Only `planned`, `active`, `checkout`, and `cooldown` are nonterminal. A participant may have at most one nonterminal session. This uniqueness must ultimately be enforced by the server under concurrency, not inferred only by a client.

## 7. Plan creation

The allowed intentions are:

- `relax`
- `learn`
- `inspired`
- `catch_up`
- `quick_break`

The allowed planned video counts are 5, 10, 20, and 40.

Planning proceeds as follows:

1. The participant chooses one allowed intention and one allowed count.
2. The future server creates a `planned` session only after it can reserve the full requested batch.
3. It materializes exactly the selected number of ordered feed items.
4. It assigns every item an immutable global session position from 1 through N.
5. It persists the batch and order so they remain stable across refreshes and tabs.
6. It returns the estimated duration and recommended cooldown.
7. The participant selects an allowed cooldown before starting.
8. Only deliberate confirmation transitions the session from `planned` to `active` and inserts `session_started`.

The selectable cooldown values are five-minute increments from 5 through 120 minutes inclusive. The recommendation is a default or guide; the participant's valid selection becomes the session's cooldown duration.

Plan creation and enforcement of the one-nonterminal-session rule must be concurrency-safe. A competing request resumes the already-created nonterminal session rather than creating another.

If eligible inventory is insufficient, plan creation fails atomically: the response uses `insufficient_inventory`, reports the available count, does not silently lower the requested count, and does not create an active or partially materialized planned session.

## 8. Finite-feed and allowance semantics

The selected count is a session-wide allowance, never a per-request `k` value. A successful plan reserves and persists the complete ordered batch.

- A request may return only items from the stored batch.
- Resetting exclusions cannot add to, replace, or enlarge the batch.
- Refreshing cannot add to, replace, reset, or enlarge the batch.
- Concurrent tabs cannot add to, replace, reset, or enlarge the batch.
- Progress uses global session position, for example, `7 of 20`.
- Back-scrolling does not restore consumed positions or change the highest reached position.
- A participant may finish early.
- No content is fetched or displayed after the session enters `checkout`.

Pagination is an implementation detail over the stored batch. It must not alter the session-wide allowance or ordering.

## 9. Boundary and early-finish semantics

### Natural boundary

The natural boundary is reached only when the future server accepts a valid `post_impression` for global session position N and that impression satisfies the existing meaningful-impression threshold: at least 60% visibility for one continuous second.

In one atomic server transaction, it must:

1. Insert `session_boundary_reached`.
2. Transition the session from `active` to `checkout`.
3. Store finish reason `boundary_reached`.

The interface may optimistically show the ending state, but the server state is authoritative. Retries must not duplicate the event or transition.

### Finish early

A participant may finish before reaching global session position N. In one atomic server transaction, the future server must:

1. Insert `session_finished_early`.
2. Store the highest reached global position (zero if no position has yet been meaningfully reached).
3. Transition the session from `active` to `checkout`.
4. Store finish reason `finished_early`.

Finishing early never transitions directly from `active` to `completed`.

## 10. Duration and cooldown calculations

The frozen constants are:

| Constant | Value |
| --- | ---: |
| `SECONDS_PER_ESTIMATED_VIDEO` | 30 |
| `COOLDOWN_MULTIPLIER` | 2 |
| `COOLDOWN_INCREMENT_SECONDS` | 300 |
| `MIN_COOLDOWN_SECONDS` | 300 |
| `MAX_COOLDOWN_SECONDS` | 7200 |
| `OVERRIDE_PAUSE_SECONDS` | 15 |

For pilot version 1:

`estimated_duration_seconds = planned_video_count × 30`

The recommended cooldown calculation is:

1. Multiply `estimated_duration_seconds` by 2.
2. Round upward to the next 300-second increment (an exact increment remains unchanged).
3. Clamp to a minimum of 300 seconds.
4. Clamp to a maximum of 7200 seconds.

Equivalent pseudocode:

```text
raw = estimated_duration_seconds × 2
rounded = ceil(raw / 300) × 300
recommended_cooldown_seconds = min(7200, max(300, rounded))
```

All participant-facing duration-estimate copy must say “about” or “estimated.” The estimate is not a psychological, clinical, or exact watch-time measure.

## 11. Checkout

Checkout requires one allowed value for each of three questions.

### Worthwhile

- `yes`
- `mostly`
- `not_really`
- `prefer_not_to_answer`

### Perceived control

- Integer `1`
- Integer `2`
- Integer `3`
- Integer `4`
- Integer `5`
- `prefer_not_to_answer`

The endpoint labels are:

- 1 = Not at all in control
- 5 = Completely in control

Numeric strings are not integers and are invalid.

### Mood

- `better`
- `same`
- `worse`
- `prefer_not_to_answer`

Closing, refreshing, or opening another tab during checkout resumes the same checkout. A valid submission will eventually perform these actions atomically:

1. Insert `checkout_submitted`.
2. Transition `checkout` to `cooldown`.
3. Store server-authoritative `cooldown_started_at` and `cooldown_ends_at` timestamps based on the participant's selected cooldown.
4. Insert `cooldown_started`.

The transition and both events are semantically idempotent.

## 12. Cooldown completion and override

Cooldown uses server time. While the session is in `cooldown`:

- No feed content is returned.
- No feed preview is shown.
- Refresh resumes the same cooldown.
- Another tab resumes the same cooldown.
- Remaining time derives from the stored server timestamps, not a client countdown.

### Natural completion

When server time reaches `cooldown_ends_at`, the next session-state read or relevant request may atomically insert `cooldown_completed`, transition `cooldown` to `completed`, and store cooldown outcome `completed`. A background job is not required for the first pilot; lazy server reconciliation is allowed. Reconciliation is semantically idempotent.

### Early-return override

An early return requires two server-authoritative steps.

Step 1 creates one override attempt, stores `override_started_at`, stores `override_available_at = override_started_at + 15 seconds`, and inserts `cooldown_override_started`.

Step 2 rejects confirmation before `override_available_at`. At or after that timestamp it requires one allowed reason code and deliberate confirmation. Acceptance atomically inserts `cooldown_overridden`, transitions `cooldown` to `completed`, and stores cooldown outcome `overridden`.

Allowed reason codes are:

- `change_plan`
- `opened_automatically`
- `want_another_session`
- `other`

Refresh and additional tabs must resume the existing override attempt and cannot shorten or bypass the pause. If natural cooldown completion is due before an override confirmation is accepted, natural completion wins because the session is no longer in `cooldown`.

## 13. Event authority and ordering

The canonical event schema contains:

- `event_id`
- `server_sequence_number`
- `client_event_id`
- `client_sequence_number`
- `event_type`
- `client_timestamp`
- `received_at`
- `metadata`

The server transactionally assigns a monotonically increasing `server_sequence_number` in the canonical session event stream. Client and server producers cannot reserve or collide on canonical sequence values. `client_sequence_number` is retained only for offline-queue diagnostics and never determines canonical order. `received_at` is server-authored; `client_timestamp` is contextual and not authoritative.

UUID idempotency remains required. `event_id` is the canonical event UUID, and client-submitted events use `client_event_id` as their UUID idempotency key. Reusing a client idempotency key must not create a duplicate event. Semantic lifecycle commands are also idempotent independently of transport retries.

Permanent 4xx validation errors must eventually be classified as terminal queue failures instead of being retried forever. Exact retry limits and dead-letter representation remain implementation details, but infinite retries are noncompliant.

The lifecycle event set is:

- `session_plan_created`
- `session_started`
- `session_finished_early`
- `session_boundary_reached`
- `checkout_submitted`
- `cooldown_started`
- `cooldown_completed`
- `cooldown_override_started`
- `cooldown_overridden`
- `session_cancelled`

Existing post and interaction event types are retained. This contract does not rename or redefine them except that an accepted final-position `post_impression` triggers the atomic boundary behavior above.

There is no `next_session_started` event.

## 14. Session linkage

When a new session follows a completed session, `session_started` may include:

- `previous_session_id`
- `previous_cooldown_outcome`
- `seconds_since_previous_session_completed`

These fields describe linkage without creating a separate lifecycle event. `seconds_since_previous_session_completed` is derived from server timestamps and cannot be negative. The fields are absent when there is no applicable previous completed session. A cancelled session is not a previous completed session for this linkage.

## 15. Multi-tab behavior

All tabs and browser views share server-authoritative participant and session state.

- If a nonterminal session exists, a second tab resumes it instead of creating a new session.
- Plan creation under concurrency yields at most one nonterminal session.
- Every tab sees the same stored batch, global positions, progress, checkout state, cooldown timestamps, and override attempt.
- Client state cannot enlarge the allowance, rewind authoritative progress, duplicate a transition, or bypass cooldown.
- Stale requests are validated against the current server state and cannot perform a transition that is no longer valid.

## 16. Study-route isolation

While a participant has a nonterminal session, `/study` is the authoritative destination. During that period:

- Comments are unavailable.
- Messaging is unavailable.
- Challenges and leaderboards are unavailable.
- Saved content is unavailable.
- Profiles are unavailable.
- Community, search, and inbox are unavailable.
- Normal product-feed navigation is unavailable.
- Direct navigation to any of those surfaces redirects to `/study`.

A stored participant credential alone never causes permanent isolation. Isolation begins only when a nonterminal session exists and ends when that session becomes `completed` or `cancelled`.

## 17. Data minimization and retention

The first pilot must not collect:

- Government identification
- Exact location
- Contacts
- Private messages
- Morning photos
- Social-graph data

The pilot retention policy target is to retain raw pilot sessions, events, and feed provenance for 180 days after pilot closure. Approved deletion or withdrawal requests cause earlier deletion when applicable. Anonymous aggregate findings may remain after raw-data deletion.

This is a pilot policy target, not a claim about current system behavior. It must later be reflected consistently in backend implementation and participant materials before the pilot launches.

## 18. Participant introduction copy

The exact approved draft is:

> “Welcome to the DayBreak pilot
>
> DayBreak is testing whether choosing a limited feed session can make scrolling feel more intentional.
>
> You will choose how many videos you want to view. Afterward, you will answer three short questions and begin a break from the feed.
>
> DayBreak records your session choices, viewed posts, interactions, whether you reached your selected boundary, your checkout answers, and whether the break was completed or ended early.
>
> This pilot does not collect your name, government ID, precise location, private messages, or contacts. Participation is voluntary, and you may stop using the study at any time.
>
> DayBreak is an experimental prototype. It has not been proven to improve mental health, sleep, or self-control.”

## 19. Error codes

### `insufficient_inventory`

This error means the server cannot materialize the full requested count from eligible posts. The response must include the available count. It must not silently reduce the plan, create a partial stored batch, or activate a session.

Other future validation and conflict error codes are implementation work and are not frozen here. Their behavior must still preserve this contract's lifecycle, concurrency, idempotency, and terminal-4xx rules.

## 20. Invariants

1. A participant has at most one nonterminal session.
2. Credential initialization alone creates no session.
3. Every governed session uses condition `intentional_break_v1` and policy `balanced-v1`.
4. A successful plan has exactly N unique, ordered stored items with immutable positions 1 through N.
5. No request, refresh, exclusion reset, or concurrent tab can enlarge or replace the stored batch.
6. No feed content is fetched or displayed in `checkout`, `cooldown`, `completed`, or `cancelled`.
7. Only an accepted meaningful impression at position N can produce the natural boundary transition.
8. Boundary and early-finish lifecycle events, reasons, and transitions are atomic.
9. Checkout requires one allowed answer for every required question.
10. Cooldown and override timing use server timestamps.
11. An override cannot complete before its 15-second server-authoritative pause ends.
12. Every canonical event order is assigned by the server; client sequence values never control it.
13. Retried events and lifecycle commands cannot duplicate their semantic effects.
14. Historical sessions retain their original meaning.
15. Study-route isolation is caused by a nonterminal session, never by a credential alone.

## 21. Examples

### Pilot duration and recommendation table

| Planned videos | Estimated consumption | Raw cooldown (×2) | Recommended cooldown |
| ---: | ---: | ---: | ---: |
| 5 | 150 seconds (about 2.5 minutes) | 300 seconds | 300 seconds (5 minutes) |
| 10 | 300 seconds (about 5 minutes) | 600 seconds | 600 seconds (10 minutes) |
| 20 | 600 seconds (about 10 minutes) | 1200 seconds | 1200 seconds (20 minutes) |
| 40 | 1200 seconds (about 20 minutes) | 2400 seconds | 2400 seconds (40 minutes) |

For a non-pilot calculation example demonstrating rounding, an estimated duration of 301 seconds produces 602 seconds after multiplication, rounds upward to 900 seconds, and recommends 15 minutes. An estimated duration of 1 second is clamped to 5 minutes; an estimated duration of 4000 seconds is capped at 120 minutes.

### Natural boundary

A 20-video session receives an accepted meaningful `post_impression` for position 20. In one transaction the server inserts `session_boundary_reached`, records `boundary_reached`, and changes `active` to `checkout`. A retry observes the same result without another event.

### Finish early

A participant in a 40-video session finishes after the highest meaningfully reached position is 7. In one transaction the server inserts `session_finished_early`, stores position 7 and reason `finished_early`, and changes `active` to `checkout`. The progress record remains `7 of 40`; the allowance is not rewritten as 7.

### Cooldown override

The server creates an override attempt at 12:00:00 and sets `override_available_at` to 12:00:15. A confirmation at 12:00:14 is rejected. A deliberate confirmation at or after 12:00:15 with reason `change_plan` may atomically complete the override.

## 22. Open implementation notes

The following are intentionally deferred without weakening the frozen behavior above:

- Database tables, columns, constraints, indexes, and production migrations.
- API routes, payload envelopes, status codes beyond `insufficient_inventory`, and response serialization.
- The concurrency mechanism that enforces one nonterminal session and atomic event sequencing.
- Batch-selection internals, eligibility rules, pagination size, and provenance representation.
- UI layout, wording beyond the approved introduction and estimate qualifiers, accessibility treatment, and countdown presentation.
- Queue terminal-failure thresholds and operational tooling for permanent 4xx errors.
- Pilot closure date, approved deletion/withdrawal workflow, and aggregate anonymization procedure.
- Recovery policy for abandoned nonterminal sessions. The approved copy permits a participant to stop using the study at any time; stopping use need not create a lifecycle transition, and this contract deliberately defines no automatic expiry or cancellation transition outside `planned` to `cancelled`.

No deferred choice may introduce another state or transition, enlarge a stored batch, weaken server authority, change the fixed condition or policy, or reinterpret historical sessions without revising this contract.
