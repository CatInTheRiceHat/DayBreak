# Archived unused code — 2026-07-03

Code removed from the live app during the pilot cleanup. Nothing here is imported,
routed, built, or tested by the running application. Kept for reference / possible
revival rather than deleted outright.

This folder sits **outside** `algorithm/`, so pytest and the Vite build never see
it. Paths below mirror their original locations, so restoring is a plain move-back.

## Why each item was retired

### Deprecated Cocoon / Migration Mode
The old "weaning program" backend. The recovery concept now lives as the
**`metamorphosis`** reels ranking mode in `core/ranking/modes.py`, which does not
use any of this code or its tables.

- `algorithm/core/cocoon.py` — Cocoon weaning math (weekly `0.8^week` decay).
- `algorithm/migration_scheduler.py` — twice-daily non-personalized "drops". The
  scheduler was only ever started in the local `api.py`; never ran in production.
- `algorithm/tests/test_cocoon.py` — tests for the above.

Also removed in the same pass (in the live tree, not archived — trivially
reconstructable): the `/api/cocoon/*`, `/api/migration/today`, `/api/cron/drop`
endpoints and the legacy-`videos` feed merge. The backing tables
(`videos`, `cocoon_profiles`, `migration_drops`, `youtube_channel_candidates`)
are dropped by `algorithm/migrations/014_drop_dead_tables.sql`.

### Dead marketing-demo frontend components
Rendered only by `LiveDemo`, which was imported by nobody (the old `RebootPage`
marketing route is no longer routed).

- `algorithm/website/src/components/LiveDemo.jsx`
- `algorithm/website/src/components/Metamorphosis.jsx`
- `algorithm/website/src/components/DailyDew.jsx`
- `algorithm/website/src/components/FlutterFeed.jsx`

### Retired multi-agent test pipeline
Built entirely around validating Cocoon/Migration behavior, which no longer
exists. Invoked manually only.

- `algorithm/.claude/agents/{test-runner,simulation-agent,fact-checker,analysis-agent,fix-agent}.md`
- `algorithm/scripts/run_pipeline.sh`
- `algorithm/CLAUDE.md` — the original (full) pipeline documentation. The live
  `algorithm/CLAUDE.md` was slimmed to just project context.

## To restore something

```bash
# from repo root, e.g. bring back cocoon.py:
git mv "archive/2026-07-03-unused-code/algorithm/core/cocoon.py" algorithm/core/cocoon.py
```

Endpoints, imports, and the dropped tables would also need to be re-added.
