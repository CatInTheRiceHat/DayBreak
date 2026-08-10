# DayBreak Intentional Break pilot data retention

## Policy

For the closed formative pilot:

- Raw participant-level pilot research data has a target retention period of
  180 days after the pilot closes.
- An approved participant deletion request may require earlier deletion.
- Anonymous aggregate findings may be retained after raw participant-level data
  is removed only when they can no longer reasonably be linked back to the
  participant.
- The repository does not hard-code a pilot close date or purge date.

This is an operations policy, not an automated lifecycle rule or legal
determination. The pilot's research/school supervisor must approve the actual
dates, access roles, export scope, and exception handling.

## Operational dates

Record these values in the approved pilot operations log:

- `pilot_start_date`
- `pilot_close_date`
- `raw_data_purge_target`

Calculate:

`raw_data_purge_target = pilot_close_date + 180 days`

Use timezone-aware timestamps and record who made and verified the calculation.

## What is raw participant-level data

Raw pilot data includes the participant row, sessions, canonical and client
events, legacy issued feed items, reserved Intentional Break items, checkout
answers, cooldown/override outcomes, and associated identifiers or timestamps.
The operator enrollment mapping is a separate controlled operational record,
but it also requires an approved retention/minimization decision.

## Existing `retain_until` field

The schema provides `research_sessions.retain_until`; it is not populated by the
participant lifecycle and there is no participant-level equivalent. The first
pilot therefore uses an explicit close procedure:

1. Determine and record the close date and +180-day target.
2. Take the exact pilot participant UUID list from the controlled enrollment
   mapping—not from a guessed date or behavior.
3. Run `set-retention` separately for each exact UUID to mark all of that
   participant's sessions.
4. Preview each participant and run the count-only `retention-preview` command.
5. Reconcile the marked counts to the approved pilot roster.

This avoids changing lifecycle/storage behavior and avoids accidentally marking
unrelated historical research. Participants with no sessions still remain on
the external purge-review list because there is no participant-level marker.

## Earlier approved deletion

Do not wait for the global target when an approved participant deletion request
applies. Follow [withdrawal-deletion-runbook.md](withdrawal-deletion-runbook.md),
delete the participant through the exact-UUID cascade procedure, and record
completion using a non-reversible request reference when sufficient.

Setting `deletion_requested_at` is useful only while a request is pending. An
immediate completed deletion removes the participant row, so the external
operations log is the durable record. Do not retain the research row merely to
retain that timestamp.

## When the pilot closes

1. Stop issuing invitations.
2. Record the pilot close timestamp.
3. Calculate and independently verify the +180-day purge target.
4. Export only an approved analysis dataset if needed.
5. Minimize participant and session identifiers in analysis exports.
6. Record and resolve outstanding withdrawal/deletion requests.
7. Mark remaining pilot sessions through the exact-UUID procedure.
8. Schedule the manual purge review.
9. Do not silently retain raw data indefinitely.

## Manual purge review

The utility intentionally has no production bulk-delete command because the
research schema does not contain a unique pilot cohort marker. At the target:

1. Reconcile `retention-preview --before <target>` counts with the controlled
   pilot enrollment mapping.
2. Include pilot participants with no sessions from the mapping.
3. Preview each participant separately.
4. Obtain the required human authorization.
5. Delete each exact participant with the individual transactional cascade
   command.
6. Verify every cascade and unrelated-participant preservation result.
7. Record aggregate completion evidence without unnecessarily retaining raw UUIDs.

No cron job is part of the first pilot. Manual review is acceptable only if the
close date, target date, responsible operator, backup reviewer, and scheduled
reminder/location are recorded before the pilot closes.

## Analysis exports and aggregates

Any approved export should contain only fields needed for the stated pilot
analysis, use minimized or replaced identifiers, and have its own recorded
location/access/retention owner. Removing direct identifiers does not by itself
prove data is anonymous; the human supervisor must confirm the aggregate can no
longer reasonably be linked to a participant before retaining it beyond the raw
data target.

## Required human decisions

Before invitations begin, record human approval/confirmation for:

- Pilot start and intended close process
- Authorized operators and deletion approvers
- Enrollment mapping storage location and access
- Operations/action log storage location and access
- Participant request authentication/contact process
- Analysis export contents, location, and access
- Reminder owner and manual purge reviewer
- Treatment of any approved exception or unresolved request

