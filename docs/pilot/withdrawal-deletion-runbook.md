# DayBreak pilot withdrawal and deletion runbook

## 1. Purpose

This runbook is the manual operating procedure for withdrawal, deletion, and
combined requests during the small closed Intentional Break pilot. It turns the
existing participant status fields and database cascades into a repeatable,
reviewable operator process. The first real invitation must not be sent until
the dummy-participant rehearsal in section 19 passes against the configured
pilot PostgreSQL/Supabase database.

## 2. Scope

This procedure covers only anonymous research records in:

- `research_participants`
- `research_sessions`
- `research_events`
- `research_feed_items`
- `research_session_items`
- `research_session_checkouts`

It does not change a session's Intentional Break lifecycle state. A withdrawn
participant can leave a journey in `planned`, `active`, `checkout`, or
`cooldown`; the participant-level inactive status makes the bearer credential
unusable. Withdrawal preserves existing research data. Deletion removes it.

## 3. Roles and access

Only an authorized pilot operator with trusted backend/database access may run
the utility. Use a secured operator workstation and the configured backend
`DATABASE_URL`. Never distribute database credentials or use a browser
Supabase anonymous key for this work. Research tables have row-level security
enabled and no browser policies; the utility is intended for the same trusted
backend database role used by the research API.

One operator performs the command. A second authorized person should verify the
request reference and exact anonymous participant UUID before production
deletion when staffing permits. Who may approve withdrawal, deletion, exports,
and final purge requires human research/school-supervision confirmation.

## 4. Participant identification

The research database is pseudonymous. It stores an anonymous participant UUID,
a one-way bearer-token hash, assigned condition, sessions, and behavior. It must
not receive participant names, contact details, or invitation codes.

The separate operator enrollment record maps:

`invitation record or pilot code -> anonymous research participant UUID`

The approved storage location for that mapping is an operator decision and must
be recorded before invitations begin. It must be access-controlled and separate
from research behavioral tables. The utility accepts one complete UUID only; it
does not search names, partial IDs, event behavior, sessions, or timestamps.

Resolve a request as follows:

1. Assign the request a non-reversible operational request reference.
2. Authenticate the requester using the approved invitation/contact process.
3. Resolve the invitation or pilot code in the operator enrollment record.
4. Copy the complete anonymous participant UUID.
5. Have the operator compare the exact UUID and invitation record before preview.
6. Never ask the participant to send a bearer token.

## 5. Stop-participation request

For “I do not want to participate anymore,” without a deletion request:

1. Resolve the exact participant UUID using section 4.
2. Run `preview` and compare its UUID, created time, condition, and counts to the
   enrollment record. Do not proceed on any mismatch.
3. Run `withdraw` and complete its confirmation.
4. Run `preview` again. Verify `status: withdrawn`, `withdrawn_at` is set, and
   all session/event/item/checkout counts are unchanged.
5. Verify credential invalidation as described in section 10.
6. Preserve the research records under the pilot retention policy unless
   deletion was also requested.
7. Record the safe operational result described in section 14.

The command sets only participant-level `status` and `withdrawn_at`. It does not
set `deletion_requested_at`, rewrite events, or transition an unfinished
session. Repeating the command preserves the original withdrawal timestamp. If
the participant is already `deletion_requested`, withdrawal records
`withdrawn_at` but does not undo the stronger pending status.

## 6. Deletion request

For “Please remove my study data”:

1. Assign and approve the request under the pilot's human procedure.
2. Resolve the exact participant UUID and run `preview`.
3. Record only the counts needed to verify completion; do not copy payloads,
   token hashes, or private seeds.
4. If execution will be delayed, run `withdraw` immediately so the credential
   becomes inactive. The schema permits `deletion_requested_at`, but this
   utility does not create a pending queue. Record the pending request in the
   external operator log instead of retaining a participant row merely for its
   request timestamp.
5. Run `delete`, typing the exact participant UUID. PostgreSQL also requires
   `--production-confirm`.
6. Confirm the utility reports zero remaining participant, session, event,
   legacy-item, reserved-item, and checkout rows for the UUID and confirms the
   unrelated participant count was preserved.
7. Run `preview` again; it must return `participant not found`.
8. Verify credential invalidation under section 10 and log completion.

Deleting `research_participants` is the intended root operation. Database
foreign keys cascade through sessions and all related research tables. The
utility performs the delete and cascade checks in one transaction; a failed
check rolls back.

## 7. Combined withdrawal and deletion

For “Stop participation now and delete my study data”:

1. Resolve and preview the exact UUID.
2. If deletion cannot be performed immediately, run `withdraw` first, verify the
   inactive status, and process the approved deletion afterward.
3. If deletion is approved for immediate execution, run `withdraw-delete`. It
   marks the participant withdrawn and deletes the root row in one transaction.
4. Verify the zero cascade counts, invalid credential, and external completion
   log.

Inside one transaction the intermediate inactive status is not externally
observable; deletion at commit removes the token hash and invalidates the
credential. The separate withdrawal step is operationally useful only when
there is a delay before deletion.

## 8. Preview and identity-verification procedure

Preview is read-only and displays only:

- Exact anonymous participant UUID
- Participant status, condition, and created timestamp
- Withdrawal and deletion-request timestamps
- Counts of sessions, events, legacy feed items, reserved session items, and checkouts
- Current nonterminal session UUID and journey state, if present

It never displays an access-token hash, raw bearer token, feed seed, event
payload, ranking snapshot, or database connection string. Stop if the UUID is
missing, partial, guessed, or inconsistent with the operator enrollment record.

## 9. Operator command examples

Run commands from the repository root. Global flags come before the command.

```bash
# Read-only PostgreSQL preview
python scripts/pilot_participant_admin.py \
  --backend postgres \
  preview --participant-id <EXACT_PARTICIPANT_UUID>

# Withdrawal; prompts for the word "withdraw"
python scripts/pilot_participant_admin.py \
  --backend postgres \
  withdraw --participant-id <EXACT_PARTICIPANT_UUID>

# Deletion; prompts for the exact UUID and requires the production gate
python scripts/pilot_participant_admin.py \
  --backend postgres --production-confirm \
  delete --participant-id <EXACT_PARTICIPANT_UUID>

# Immediate combined request
python scripts/pilot_participant_admin.py \
  --backend postgres --production-confirm \
  withdraw-delete --participant-id <EXACT_PARTICIPANT_UUID>

# Controlled noninteractive deletion still requires an exact matching UUID
python scripts/pilot_participant_admin.py \
  --backend postgres --production-confirm \
  delete --participant-id <EXACT_PARTICIPANT_UUID> \
  --confirm-participant-id <EXACT_PARTICIPANT_UUID>
```

`--yes` exists only for controlled withdrawal/retention automation; it does not
bypass the exact-UUID deletion confirmation. With no command, the utility only
prints help/error and makes no database change.

## 10. Credential invalidation verification

All versioned Intentional Break endpoints use the shared bearer-authentication
gate. A participant whose status is `withdrawn` or `deletion_requested` receives
`403 participant_inactive` before any current-journey read or mutation. After
deletion, the token hash no longer exists and the same credential receives
`401 invalid_credential`.

For a real request, never obtain the participant's raw token. Verify withdrawal
by reading the exact participant's inactive status, and verify deletion by the
missing root row and zero cascade counts. The pre-pilot rehearsal separately
proves the API result using operator-created dummy credentials. A participant
may independently confirm that `/study` no longer resumes, without sending the
operator a token.

The existing gate covers current journey, session read, planning, cancel/start,
item reads, event submission, Finish Early, checkout, cooldown read, override
start, and override confirmation.

## 11. Cascade verification

The delete command verifies, before commit, that the following counts are zero
for the participant UUID:

- `research_sessions`
- `research_events`
- `research_feed_items`
- `research_session_items`
- `research_session_checkouts`

It also verifies exactly one root participant was removed and that the total
number of other participants did not change. If any assertion fails, the
transaction rolls back. Do not replace this with piecemeal table deletes.

## 12. Browser-local credential limitation

Server withdrawal or deletion cannot remotely erase the anonymous bearer
credential already stored in a participant's browser profile. That local value
no longer authenticates and cannot recover deleted data. A later `/study` visit
must fail safely as inactive or invalid.

Use this accurate optional participant instruction after confirmation:

> After a confirmed withdrawal/deletion, you may also clear DayBreak site data
> from your browser if you want to remove the local anonymous credential.

Never claim that server deletion cleared browser localStorage.

## 13. Shared-device guidance

Ask participants to use their own device and browser profile where practical.
Avoid shared public computers and shared household browser profiles because the
anonymous bearer credential persists locally and can resume the same study
journey until the server marks it inactive or deletes it.

## 14. Operational action log

The approved pilot log should record:

- Non-reversible request/ticket reference
- Request type and received timestamp
- Identity/mapping verification completed: yes/no
- Authorizing role and operator role
- Action timestamp and deployment/database environment
- Pre-action and post-action counts
- Credential-invalidation verification method/result
- Completion or failure/recovery status

While a request is active, the controlled enrollment mapping may hold the
anonymous UUID. After deletion is verified, retain only the non-reversible
request reference when that is sufficient; do not create an unnecessary
permanent deletion log containing the raw participant UUID. The exact approved
log and mapping locations require human/operator choice.

## 15. Failure and recovery procedure

1. Stop after any identifier mismatch, missing migration/table, unexpected
   count, database error, or confirmation failure.
2. Do not rerun against a different guessed UUID.
3. The utility rolls failed mutations back. Reconnect and run read-only
   `preview` on the same exact UUID to establish the actual state.
4. Preserve sanitized command status and counts; never paste credentials,
   connection strings, hashes, seeds, or event payloads into defect logs.
5. Escalate to the authorized technical/research supervisor before retrying.
6. If withdrawal succeeded but deletion failed, the credential remains inactive
   and the data can be deleted after the failure is resolved.
7. If a participant cannot be resolved through the approved mapping, acknowledge
   the request and escalate. Do not guess from behavior.

## 16. Pilot-close retention procedure

When the pilot closes:

1. Stop issuing participant invitations.
2. Record the pilot close timestamp in the approved operations log.
3. Calculate `raw_data_purge_target = pilot_close_date + 180 days`.
4. Record the pilot start date, close date, and calculated target; no date is
   hard-coded in the repository.
5. Export only an approved analysis dataset if necessary, minimizing participant
   identifiers.
6. Resolve or record every outstanding withdrawal/deletion request.
7. For each exact UUID in the closed-pilot enrollment mapping, use
   `set-retention --retain-until <PURGE_TARGET>`, then preview it. The field is
   session-level; there is no participant-level `retain_until` column.
8. Run count-only `retention-preview --before <PURGE_TARGET>` and compare the
   counts with the approved pilot roster. It does not delete anything.
9. Schedule a manual purge review for the target date.
10. Do not silently keep raw participant-level data indefinitely.

Example:

```bash
python scripts/pilot_participant_admin.py \
  --backend postgres \
  set-retention --participant-id <EXACT_PARTICIPANT_UUID> \
  --retain-until <ISO_8601_PURGE_TARGET>

python scripts/pilot_participant_admin.py \
  --backend postgres \
  retention-preview --before <ISO_8601_PURGE_TARGET>
```

The schema cannot independently distinguish this pilot from unrelated historic
research rows. The approved enrollment mapping is therefore authoritative for
which exact participants receive the marker. Never apply it by a broad guessed
date alone.

## 17. 180-day purge review

At the purge target:

1. Reconfirm the approved pilot participant UUID list from the controlled mapping.
2. Run count-only `retention-preview` and reconcile it with that list.
3. Check for unresolved approved withdrawals/deletions and analysis/export holds
   authorized by the human research supervisor.
4. Preview each exact participant individually.
5. Obtain the required purge authorization.
6. Delete each exact participant with the individual `delete` command and verify
   its cascade. There is intentionally no live bulk-purge command.
7. Record completion using non-reversible request/purge references and aggregate
   counts, then minimize/remove the UUID mapping according to the approved plan.

Raw pilot research data has a target of 180 days after pilot closure. Approved
participant deletion requests are handled earlier. Anonymous aggregate findings
may be retained only when they can no longer reasonably be linked back to a
participant. See [pilot-data-retention.md](pilot-data-retention.md).

## 18. What must never be done

- Never ask a participant to send their bearer token.
- Never place participant names inside research event/session tables.
- Never locate a participant by guessing from behavior.
- Never expose access-token hashes.
- Never manually delete only events while leaving an inconsistent session graph
  unless there is a defined, approved reason.
- Never edit lifecycle events to make results “cleaner.”
- Never reuse deleted participant records.
- Never claim browser localStorage was remotely deleted.
- Never bulk-delete production rows without preview and authorization.
- Never use a browser Supabase anonymous key for operator mutations.
- Never proceed from a partial identifier or a preview mismatch.

## 19. Pre-pilot rehearsal checklist

This rehearsal is required before GO and must use dummy participants in the
configured pilot PostgreSQL/Supabase environment:

- [ ] Record the deployed version and migration state.
- [ ] Create dummy participant A and temporarily retain its dummy credential in
      a secure rehearsal-only location.
- [ ] Complete part of an Intentional Break journey.
- [ ] Add dummy A to the operator mapping using a dummy invitation code.
- [ ] Resolve the exact UUID through that mapping and preview it.
- [ ] Withdraw dummy A.
- [ ] Verify its stored data remains and its old credential receives
      `participant_inactive` across the Intentional Break API.
- [ ] Create dummy participant B and an unrelated dummy participant C.
- [ ] For B, create legacy/session data as applicable, lifecycle events, legacy
      feed items, reserved items, and a checkout.
- [ ] Preview B, then delete B with exact-UUID and production confirmations.
- [ ] Verify the participant, sessions, events, legacy items, reserved items,
      and checkout are gone.
- [ ] Verify B's old credential receives `invalid_credential`.
- [ ] Verify unrelated dummy C remains unchanged.
- [ ] Rehearse combined withdrawal/deletion on another disposable dummy if the
      pilot will offer that single-request workflow.
- [ ] Save only safe pass/fail evidence, request references, timestamps, counts,
      operator/version information, and sanitized error codes—never tokens,
      hashes, seeds, payloads, or database credentials.
- [ ] Obtain the required human research/school-supervision approval to open the pilot.
