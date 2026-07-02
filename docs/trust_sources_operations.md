# Trust-Source System — Operations Guide

A human-curated source-quality layer for the YouTube feed. Three Supabase tables
back the workflow:

```
discovered channel → candidate queue → human review
                   → approved / rejected → ingestion uses ONLY approved
```

| Table | Role |
|---|---|
| `trusted_youtube_channels` | approved/candidate/rejected/… channels. Only `status='approved'` feeds the trusted ingestion lane. |
| `blocked_youtube_channels` | hard denylist — never ingested or served, in **any** lane (search, popular, trusted). |
| `youtube_channel_candidates` | review queue **only**; never feeds ingestion. |

Code: [`core/trust_registry.py`](../core/trust_registry.py),
[`core/source_reputation.py`](../core/source_reputation.py),
trusted lane in [`integrations/youtube_ingest.py`](../integrations/youtube_ingest.py).

---

## ⚠️ Quota guard — read before approving channels

The trusted lane runs **one `search.list` call (~100 YouTube Data API quota
units) per approved channel, per ingestion run** — separate from the feed-mix
cap. Extraction runs **4×/day**, so cost scales fast:

```
trusted-lane cost/day ≈ approved_channels × 100 × 4   (quota units)
```

- **Trusted content is capped in the feed mix** (`TRUSTED_CHANNEL_TARGET_RATIO = 0.15`)
  — but that caps how many trusted videos *appear*, **not** the API fetch cost.
  The fetch cost scales with the number of *approved channels*.
- **Start small: 3–5 approved channels.** Do **not** approve 50 at once.
- A per-run cap protects you: **`MAX_TRUSTED_CHANNELS_PER_RUN` (default `5`)** in
  `integrations/youtube_ingest.py`. Only that many approved channels are queried
  per run (blocked channels are skipped for free and don't count). Override with
  the `MAX_TRUSTED_CHANNELS_PER_RUN` environment variable (Vercel/CI):

  ```
  MAX_TRUSTED_CHANNELS_PER_RUN=3
  ```

- Watch your YouTube Data API quota in the Google Cloud Console for a full day
  after the first run before scaling up.

> Note: if you approve more channels than the cap, the extra approved channels
> simply aren't fetched that run. Raise the cap deliberately, not by accident.

---

## Operational checklist (first deploy)

1. **Run the migration** — paste [`migrations/011_trusted_sources.sql`](../migrations/011_trusted_sources.sql)
   into the Supabase SQL Editor and run it. Idempotent, non-destructive.
2. **Run the smoke test** — paste [`migrations/011_trusted_sources_smoke_test.sql`](../migrations/011_trusted_sources_smoke_test.sql)
   and confirm every line prints `PASS:` and ends with `ALL SMOKE CHECKS PASSED`.
   It rolls itself back — nothing persists.
3. **Insert 3–5 approved channels** — copy [`migrations/seed_trusted_youtube_channels.example.sql`](../migrations/seed_trusted_youtube_channels.example.sql),
   replace the `UC_REPLACE_ME_*` ids with real `UC...` channel ids, set
   `approved_by`, and run only the rows you reviewed.
4. **Run ingestion once manually** — trigger the extract endpoint (or the cron's
   `workflow_dispatch`). Confirm it succeeds.
5. **Check trusted rows landed** — in Supabase:
   ```sql
   select source_type, source_category, count(*)
   from feed_videos where source_type = 'trusted_channel'
   group by 1, 2;
   ```
6. **Check blocked channels are excluded** — block one channel, re-run ingest,
   and confirm none of its videos are in `feed_videos`.
7. **Check the feed still has a mix** — confirm search + popular + trusted all
   appear and trusted hasn't taken over:
   ```sql
   select source_type, count(*) from feed_videos group by 1;
   ```
8. **Watch the YouTube API quota** for a day (Google Cloud Console → APIs →
   YouTube Data API v3 → Quotas).
9. **Only then add more approved channels** — and raise
   `MAX_TRUSTED_CHANNELS_PER_RUN` if needed.

---

## Day-to-day operations

- **Approve a channel:** insert into `trusted_youtube_channels` with `status='approved'`
  (or update an existing row). Set `approved_by` and `approved_at`.
- **Reject / pause a channel:** set `status` to `'rejected'` or `'disabled'`.
  Non-approved channels are never queried.
- **Block a channel:** insert into `blocked_youtube_channels`. Blocked wins over
  approved — a blocked channel is never ingested even if also marked approved.
- **Queue for review:** insert into `youtube_channel_candidates` with
  `review_status='new'`. This never feeds ingestion until a human promotes it
  into `trusted_youtube_channels`.

### Status / tier vocabularies (enforced by CHECK constraints)

- `trusted_youtube_channels.status`: `candidate | approved | rejected | needs_review | disabled`
- `trusted_youtube_channels.trust_tier`: `institutional | established_creator | candidate | experimental`
- `youtube_channel_candidates.review_status`: `new | needs_review | approved | rejected | stale`

`source_group` and blocked `reason` are free text (recommended values documented
in the migration) so the vocabulary can grow without a schema change.
