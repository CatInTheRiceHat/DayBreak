# En-Masse Narrative Saturation Detector (v1: appearance/body)

**Date:** 2026-07-02
**Status:** Design — awaiting review
**Scope:** `algorithm/core/algorithm.py`, `algorithm/core/constants.py` (+ tests)

## Origin

Cross-referenced from a Stanford Center for Youth Mental Health & Wellbeing
("Tech-X") workshop (reference screenshots). The driving slide: **#skinnytok** —
*"Singular posts may seem harmless but en masse form a harmful narrative."* The
looksmaxxing slide makes the same point ("drawing the line is complicated").

This is the first of four planned changes derived from that workshop. The other
three (proactive Papageno weaving, real-world/in-person nudge, transparency +
anti-manipulation audit) get their own specs later and are out of scope here.

## Problem

`build_prototype_feed` already detects rabbit holes (Step 6,
`emotional_amplification_streak`), but only counts an item as part of a rabbit
hole when `engagement > 0.6 AND risk > 0.5`. A run of individually-safe
appearance clips — "what I eat in a day", gym/aesthetic, looksmaxxing, each with
`risk ≈ 0.3` — never trips it. Harm here is **cumulative across a theme**, not
per-item. Nothing in the current pipeline breaks that pattern.

Existing partial coverage (intentionally not sufficient):
- `HIGH_RISK_TOPICS` streak caps limit *consecutive identical topics*, but a feed
  can alternate `body_image` / `weight_loss` / `appearance` and stay under the cap
  while still saturating the appearance theme.
- Step 5 (crisis) owns `self_harm` / `suicide` / `eating_disorder` / `depression`.
  Appearance-without-crisis (the #skinnytok gray area) is not owned by anyone.

## Goal

Detect sustained exposure to the **appearance/body theme** across a rolling
window — independent of per-item `risk` — and break the pattern by damping
further appearance-theme items and pulling in safe, diverse content. Protection
scales up for younger users via the existing `age_protection_factor`.

Non-goals for v1:
- Any theme other than appearance/body (hustle, rage-bait, etc. — later, if this
  proves out).
- Any user-facing surfacing (captions, "why am I seeing this", nudges). v1 is
  **ranking-only**; surfacing belongs to gaps #3/#4.
- New database columns or network calls. Reuse existing signals only.

## Design

### Theme membership

An item is **appearance-theme** iff:

```
appearance_comparison >= APPEARANCE_COMP_THRESHOLD   (default 0.5)
  OR topic in APPEARANCE_TOPICS
```

where `APPEARANCE_TOPICS = {body_image, eating_disorder, weight_loss, appearance}`
— the appearance subset of `HIGH_RISK_TOPICS`, deliberately **excluding** the
crisis topics (`self_harm`, `suicide`, `depression`) that Step 5 already owns.

Membership **does not read `risk`** — that is the entire #skinnytok point.

### Saturation signal (new state in `build_prototype_feed`)

Mirrors the existing Step 5 crisis-window pattern:

- Track `narrative_window_history: List[bool]` — was each served item
  appearance-theme? — capped at `NARRATIVE_WINDOW` (default **6**).
- `narrative_saturated = sum(window) >= effective_threshold`.

Count-based (not a rolling mean) so it reads and tests like `CRISIS_THRESHOLD`.

**Age lowers the trigger, not just the remedy.** The youngest users should break
a harmful narrative *sooner*, not merely harder:

```
effective_threshold = NARRATIVE_THRESHOLD - 1 if age_group == "13-15"
                      else NARRATIVE_THRESHOLD          # default 4 → 3 for 13-15
```

So 13–15 saturates at 3-of-6 (earlier first break) *and* gets a 1.5× stronger
remedy (below); 16–17 and adults saturate at 4-of-6. This is what makes the age
test's "reaches an off-theme item in fewer positions" assertion hold.

### Remedy (applied per-candidate while saturated) — mirrors Step 6

Inside the existing candidate scoring loop, when `narrative_saturated`:

- **Damp continuation:** if the candidate is appearance-theme,
  `s -= NARRATIVE_DAMP * age_protection_factor`.
- **Pull in safe-diverse:** if the candidate is *not* appearance-theme and
  `risk < 0.3`, `s += NARRATIVE_DIVERSIFY * age_protection_factor`.

`age_protection_factor` is 1.5 for 13–15, 1.15 for 16–17, 1.0 otherwise — so
younger users break the pattern faster, consistent with Steps 3/5/6.

### State update (end of each pick) — mirrors Step 5

```
_is_appearance_theme = (
    float(best_row.get("appearance_comparison", 0.0)) >= APPEARANCE_COMP_THRESHOLD
    or best_row.get("topic", "") in APPEARANCE_TOPICS
)
narrative_window_history.append(_is_appearance_theme)
if len(narrative_window_history) > NARRATIVE_WINDOW:
    narrative_window_history.pop(0)
narrative_saturated = sum(narrative_window_history) >= narrative_threshold
```

where `narrative_threshold` is computed once from `age_group`
(`NARRATIVE_THRESHOLD - 1` for `"13-15"`, else `NARRATIVE_THRESHOLD`).

### New constants (`core/constants.py`)

```python
# Narrative-saturation detector (appearance/body theme)
NARRATIVE_WINDOW = 6              # rolling window of served items
NARRATIVE_THRESHOLD = 4           # appearance-theme items in window to trigger
APPEARANCE_COMP_THRESHOLD = 0.5   # appearance_comparison at/above = appearance-theme
NARRATIVE_DAMP = 0.30             # score penalty for continuing the theme (× age factor)
NARRATIVE_DIVERSIFY = 0.20        # score bonus for safe off-theme content (× age factor)
APPEARANCE_TOPICS = frozenset({"body_image", "eating_disorder", "weight_loss", "appearance"})
```

Magnitudes intentionally match the existing Step 6 scale (`0.30` penalty, `0.5×`
diversity boosts) for behavioural consistency.

### Feature flag (for test isolation)

A `user_profile` key `disable_narrative_saturation` (default `False`) short-circuits
the detector — the state is still tracked but no remedy is applied. This mirrors
how `crisis_mode`/`override_passive_history` are read from `user_profile`, and
lets tests compare a detector-on vs detector-off run on an identical pool. It is
a test/ops seam, not a user-facing setting.

### Interaction with existing steps

- **Step 5 (crisis)** takes precedence for its owned topics; appearance-only
  content that is *not* crisis is what this fills in. No double-counting: crisis
  topics are excluded from `APPEARANCE_TOPICS`.
- **Step 6 (emotional amplification)** still fires independently on high-risk
  high-engagement runs. A clip can be both; penalties are additive, which is
  acceptable (stronger break on genuinely bad runs).
- **Streak caps** are unchanged; this adds a theme-level layer above the existing
  topic/channel streak layer.

## Testing (TDD — written before implementation)

New tests in `tests/test_algorithm.py`:

1. **Saturation breaks the run (baseline-comparative).** Build a candidate pool
   dominated by `risk=0.3, appearance_comparison=0.7` clips plus enough safe
   off-theme content. Because the remedies are soft score nudges (not hard
   blocks), assert *relative* to a control run with the detector disabled:
   - the feed's **total appearance-theme count is strictly lower**, and
   - its **longest consecutive appearance-theme run is shorter**, and
   - at least one safe off-theme item is served within 2 picks after saturation
     first triggers.
2. **Age sensitivity.** Same pool, `age_group="13-15"` vs adult. Assert the
   13–15 feed reaches its first off-theme item in **no more** positions than the
   adult feed (and strictly fewer in the constructed pool).
3. **No false positive.** A normal mixed feed (few/no appearance items) produces
   an **identical ranking** to a detector-disabled run (detector never triggers).
4. **Crisis boundary.** An `eating_disorder`/`self_harm` heavy run still routes
   through Step 5 crisis logic; the appearance detector does not suppress or
   override Step 5's wellness injection.

The detector-disabled control is achieved via a feature flag (default on) so
tests can isolate its effect — see below.

## Files touched

| File | Change |
|---|---|
| `core/constants.py` | Add the six narrative-saturation constants above |
| `core/algorithm.py` | Add "Step 7" state + per-candidate remedy + state update |
| `tests/…` (existing algorithm test module) | Add the four tests above |

No DB migration, no API change, no frontend change.

## Open questions / assumptions to confirm

- `NARRATIVE_WINDOW=6`, `NARRATIVE_THRESHOLD=4` — starting values; tune against
  the simulation-agent if the break feels too eager/too slow.
- `APPEARANCE_COMP_THRESHOLD=0.5` membership rule — could later incorporate a
  light taxonomy keyword check, but not for v1.
- Ranking-only (no user-facing signal) for v1 — confirmed in design discussion.
