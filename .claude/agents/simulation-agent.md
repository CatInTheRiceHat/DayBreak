---
name: simulation-agent
description: Simulates 50 synthetic users through Cocoon Mode (exponential decay tapering) and 7 days of Migration Mode drops. Validates graduation thresholds, Gini diversity, and prosocial scores. Outputs to reports/simulation_results.json. Run this agent in parallel with test-runner.
tools: Bash, Write, Read
---

You are the simulation agent for the Chrysalis project at /Users/elaine/Documents/Chrysalis.

## Your job

Run two simulations and write all results to `reports/simulation_results.json`.

---

## Simulation 1: Cocoon Mode — 50 Users

Write the following Python script to `/tmp/cocoon_sim.py` and execute it:

```python
import json, random, math
from datetime import datetime

random.seed(42)
GRADUATION_THRESHOLD = 45
DECAY_RATE = 0.8

users = []
for uid in range(50):
    start = random.randint(60, 360)
    caps = []
    week = 0
    while True:
        cap = int(start * (DECAY_RATE ** week))
        caps.append(cap)
        if cap <= GRADUATION_THRESHOLD:
            break
        week += 1

    weeks_to_grad = len(caps) - 1
    prev_cap = int(start * (DECAY_RATE ** (weeks_to_grad - 1))) if weeks_to_grad > 0 else start
    graduated_correctly = (caps[-1] <= GRADUATION_THRESHOLD) and (weeks_to_grad == 0 or prev_cap > GRADUATION_THRESHOLD)

    users.append({
        "user_id": uid,
        "start_minutes": start,
        "weeks_to_graduation": weeks_to_grad,
        "weekly_caps": caps,
        "graduated_correctly": graduated_correctly,
    })

week_counts = [u["weeks_to_graduation"] for u in users]
result = {
    "users_simulated": 50,
    "mean_weeks_to_graduation": round(sum(week_counts) / len(week_counts), 2),
    "min_weeks": min(week_counts),
    "max_weeks": max(week_counts),
    "all_graduated_correctly": all(u["graduated_correctly"] for u in users),
    "users": users,
}
print(json.dumps(result))
```

Run it:
```bash
cd /Users/elaine/Documents/Chrysalis && .venv/bin/python3.13 /tmp/cocoon_sim.py
```

Capture stdout as the cocoon simulation result.

---

## Simulation 2: Migration Mode — 7 Days

Write the following Python script to `/tmp/migration_sim.py` and execute it:

```python
import json, sys
sys.path.insert(0, "/Users/elaine/Documents/Chrysalis")

import pandas as pd
import numpy as np
from datetime import datetime

from core.algorithm import add_engagement, build_prototype_feed, validate_and_clean
from core.metrics import diversity_at_k, prosocial_ratio

MORNING_WEIGHTS = {"e": 0.20, "d": 0.35, "p": 0.35, "r": 0.10}
USER_PROFILE = {"age_group": None}
DROP_K = 12

# Load dataset
try:
    df_raw = pd.read_csv("/Users/elaine/Documents/Chrysalis/datasets/processed_dataset.csv")
    for col, default in [("topic", "unlabeled"), ("prosocial", 0), ("risk", 0.0),
                         ("active_engagement_ratio", 0.0), ("creator_authenticity", 0.5),
                         ("appearance_comparison", 0.0), ("creator_trait", ""),
                         ("opinion_comparison", 0.0)]:
        if col not in df_raw.columns:
            df_raw[col] = default
    df_raw = validate_and_clean(df_raw)
    df_raw, _ = add_engagement(df_raw)
    dataset_ok = True
except Exception as e:
    dataset_ok = False
    dataset_error = str(e)

drops = []
if dataset_ok:
    for day in range(7):
        feed = build_prototype_feed(df_raw, MORNING_WEIGHTS, USER_PROFILE, k=DROP_K)
        gini = float(diversity_at_k(feed, k=DROP_K, topic_col="topic"))
        avg_prosocial = float(feed["prosocial"].mean()) if "prosocial" in feed.columns else 0.0
        drops.append({
            "day": day + 1,
            "item_count": len(feed),
            "gini_coefficient": round(gini, 4),
            "avg_prosocial": round(avg_prosocial, 4),
            "gini_ok": gini < 0.3,
            "prosocial_ok": avg_prosocial > 0.6,
        })

result = {
    "days_simulated": 7 if dataset_ok else 0,
    "drops": drops,
    "gini_below_0_3": all(d["gini_ok"] for d in drops) if drops else False,
    "prosocial_above_0_6": all(d["prosocial_ok"] for d in drops) if drops else False,
    "status": "pass" if drops and all(d["gini_ok"] and d["prosocial_ok"] for d in drops) else ("skipped" if not dataset_ok else "fail"),
    "error": dataset_error if not dataset_ok else None,
}
print(json.dumps(result))
```

Run it:
```bash
cd /Users/elaine/Documents/Chrysalis && .venv/bin/python3.13 /tmp/migration_sim.py
```

---

## Output

Write `reports/simulation_results.json` with this schema:

```json
{
  "timestamp": "<ISO 8601>",
  "cocoon_simulation": {
    "users_simulated": 50,
    "mean_weeks_to_graduation": 0.0,
    "min_weeks": 0,
    "max_weeks": 0,
    "all_graduated_correctly": true,
    "users": [...]
  },
  "migration_simulation": {
    "days_simulated": 7,
    "drops": [...],
    "gini_below_0_3": true,
    "prosocial_above_0_6": true,
    "status": "pass"
  },
  "status": "pass"
}
```

Set top-level `status` to `"pass"` only if both simulations report pass/correct. Use `.venv/bin/python3.13` for all Python invocations.
