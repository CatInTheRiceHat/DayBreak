# Chrysalis — Multi-Agent Testing Pipeline

## Pipeline overview

```
Phase 1 (parallel)          Phase 2 (sequential)
──────────────────          ────────────────────────────────────────────
test-runner       ──┐
                    ├──▶ fact-checker ──▶ analysis-agent ──▶ fix-agent
simulation-agent  ──┘
                                                               │
                                              (if fixes made) └──▶ test-runner (loop)
```

All agent definitions live in [.claude/agents/](.claude/agents/). All outputs go to `reports/`.

---

## Routing rules

When asked to run the full Chrysalis test and analysis pipeline, follow these rules exactly.

### Phase 1 — Run in parallel (no shared state)

Spawn both agents simultaneously. They write to different files and share nothing:

| Agent | Output |
|---|---|
| `test-runner` | `reports/test_results.json` |
| `simulation-agent` | `reports/simulation_results.json` |

Do not proceed to Phase 2 until both have written their output files.

### Phase 2 — Run sequentially, in order

1. **fact-checker** — reads both Phase 1 outputs → writes `reports/fact_check.json`
2. **analysis-agent** — reads all three JSONs → writes `reports/analysis.md`
3. **fix-agent** — reads `reports/analysis.md`, edits source files, re-runs tests → appends Fix Report to `reports/analysis.md`

### Loop condition

After fix-agent completes:
- If fix-agent output contains `LOOP: re-run test-runner`: re-run `test-runner` alone, then stop (do not re-run the full pipeline)
- If fix-agent output contains `PIPELINE COMPLETE`: stop

---

## Agent descriptions

| Agent | When to invoke |
|---|---|
| `test-runner` | Before and after any code change; Phase 1 of pipeline |
| `simulation-agent` | Phase 1 of pipeline; when validating Cocoon or Migration Mode behavior |
| `fact-checker` | Phase 2, after both Phase 1 agents complete |
| `analysis-agent` | Phase 2, after fact-checker |
| `fix-agent` | Phase 2, after analysis-agent; only when fixes are needed |

---

## Reports directory

`reports/` is gitignored. Agents create it automatically. Files:

| File | Written by |
|---|---|
| `reports/test_results.json` | test-runner |
| `reports/simulation_results.json` | simulation-agent |
| `reports/fact_check.json` | fact-checker |
| `reports/analysis.md` | analysis-agent (Fix Report appended by fix-agent) |

---

## Manual invocation

```bash
# Full pipeline
bash scripts/run_pipeline.sh

# Single agent (e.g. just run tests)
claude -p "run the test-runner agent"
```

---

## Project context

Chrysalis is a mental-health-aware social media recommendation algorithm. Two modes are under test:

- **Cocoon Mode** (`core/cocoon.py`) — exponential decay tapering: T(n) = T(0) × 0.8^n, graduating users to Migration Mode at ≤ 45 min/day
- **Migration Mode** (`migration_scheduler.py`) — curated non-personalized daily drops at 07:00 and 19:00 with diversity (Gini < 0.3) and prosocial (avg > 0.6) constraints

Python interpreter: `.venv/bin/python3.13` (system Python lacks pytest and project deps).
Dataset: `datasets/processed_dataset.csv`.
Database: `chrysalis.db` (SQLite, project root).
