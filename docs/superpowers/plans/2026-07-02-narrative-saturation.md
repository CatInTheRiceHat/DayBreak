# En-Masse Narrative Saturation Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Break sustained exposure to the appearance/body theme in a Chrysalis feed even when every individual clip is low-risk (#skinnytok problem).

**Architecture:** Add a rolling "appearance-theme window" (Step 7) inside `build_prototype_feed`, mirroring the existing crisis (Step 5) and rabbit-hole (Step 6) window logic. Membership is a pure helper that ignores `risk`. When ≥ N of the last 6 served items are appearance-theme, apply soft score nudges — damp further appearance items, boost safe off-theme ones — scaled by the existing age-protection factor. Ranking-only; no DB/API/frontend change.

**Tech Stack:** Python 3.13, pandas, numpy; tests are `unittest`-style run under `pytest`.

## Global Constraints

- Interpreter: `.venv/bin/python3.13` (system Python lacks deps). Run from `algorithm/`.
- Run tests with: `.venv/bin/python3.13 -m pytest <path> -v`
- No new database columns, no network calls, no API or frontend changes (spec non-goals).
- Reuse existing signals only: `appearance_comparison`, `topic`, `risk`, `age_group`.
- Feed data passed to `build_prototype_feed` must already have an `engagement` column (call `add_engagement(df)` first — existing test convention).
- Match existing code style in `core/algorithm.py` (numbered "Step N" comment blocks; `getattr(row, ...)` with safe defaults).
- Crisis topics (`self_harm`, `suicide`, `depression`, `eating_disorder`) remain owned by Step 5 — `APPEARANCE_TOPICS` must NOT include `self_harm`/`suicide`/`depression`.

---

### Task 1: Constants + `is_appearance_theme` membership helper

**Files:**
- Modify: `algorithm/core/constants.py` (append)
- Modify: `algorithm/core/algorithm.py` (add module-level helper + import)
- Test: `algorithm/tests/test_algorithm.py` (add a test class)

**Interfaces:**
- Produces: `is_appearance_theme(appearance_comparison: float, topic: str) -> bool` in `core.algorithm`.
- Produces constants in `core.constants`: `NARRATIVE_WINDOW: int`, `NARRATIVE_THRESHOLD: int`, `APPEARANCE_COMP_THRESHOLD: float`, `NARRATIVE_DAMP: float`, `NARRATIVE_DIVERSIFY: float`, `APPEARANCE_TOPICS: frozenset[str]`.

- [ ] **Step 1: Write the failing test**

Add to `algorithm/tests/test_algorithm.py` (import `is_appearance_theme` in the existing `from core.algorithm import (...)` block first):

```python
class TestAppearanceThemeMembership(unittest.TestCase):
    """Membership rule for the narrative-saturation detector (spec: ignores risk)."""

    def test_high_appearance_comparison_is_theme(self):
        self.assertTrue(is_appearance_theme(0.5, "cooking"))
        self.assertTrue(is_appearance_theme(0.9, "science"))

    def test_low_appearance_comparison_not_theme(self):
        self.assertFalse(is_appearance_theme(0.49, "science"))
        self.assertFalse(is_appearance_theme(0.0, "history"))

    def test_appearance_topic_is_theme_regardless_of_comparison(self):
        for topic in ("body_image", "eating_disorder", "weight_loss", "appearance"):
            self.assertTrue(is_appearance_theme(0.0, topic))

    def test_crisis_topics_not_owned_here(self):
        # Owned by Step 5; must not be appearance-theme by topic alone.
        for topic in ("self_harm", "suicide", "depression"):
            self.assertFalse(is_appearance_theme(0.0, topic))

    def test_membership_ignores_risk(self):
        # No risk argument exists — a low-risk appearance clip is still theme.
        self.assertTrue(is_appearance_theme(0.7, "fitness"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3.13 -m pytest tests/test_algorithm.py::TestAppearanceThemeMembership -v`
Expected: FAIL — `ImportError: cannot import name 'is_appearance_theme'`.

- [ ] **Step 3: Add constants**

Append to `algorithm/core/constants.py`:

```python
# Narrative-saturation detector (appearance/body theme) — spec 2026-07-02
NARRATIVE_WINDOW = 6              # rolling window of served items
NARRATIVE_THRESHOLD = 4           # appearance-theme items in window to trigger (13-15 uses -1)
APPEARANCE_COMP_THRESHOLD = 0.5   # appearance_comparison at/above = appearance-theme
NARRATIVE_DAMP = 0.30             # score penalty for continuing the theme (x age factor)
NARRATIVE_DIVERSIFY = 0.20        # score bonus for safe off-theme content (x age factor)
# Appearance subset of HIGH_RISK_TOPICS; excludes crisis topics owned by Step 5.
APPEARANCE_TOPICS = frozenset({"body_image", "eating_disorder", "weight_loss", "appearance"})
```

- [ ] **Step 4: Add the helper + import in `core/algorithm.py`**

In the existing `from .constants import (...)` block, add the six new names:

```python
from .constants import (
    PASSIVE_DECAY_RATE,
    VALENCE_THRESHOLD,
    AGE_PROTECTION_FACTORS,
    SESSION_CAPS,
    CRISIS_WINDOW,
    CRISIS_THRESHOLD,
    NIGHT_RISK_BOOST,
    NIGHT_PROSOCIAL_BOOST,
    NIGHT_FEED_CAP,
    ACTIVE_ENGAGEMENT_BONUS,
    OPINION_COMPARISON_BONUS,
    FATIGUE_ONSET,
    HIGH_RISK_THRESHOLD,
    NARRATIVE_WINDOW,
    NARRATIVE_THRESHOLD,
    APPEARANCE_COMP_THRESHOLD,
    NARRATIVE_DAMP,
    NARRATIVE_DIVERSIFY,
    APPEARANCE_TOPICS,
)
```

Add this module-level function directly after the `CRISIS_TOPICS = frozenset({...})` definition near the top of the file:

```python
def is_appearance_theme(appearance_comparison: float, topic: str) -> bool:
    """Appearance/body theme membership for the narrative-saturation detector.

    Deliberately does NOT read `risk` — the #skinnytok point is that each clip
    is individually low-risk. Crisis topics (self_harm/suicide/depression) are
    excluded here; Step 5 owns those.
    """
    return (
        float(appearance_comparison) >= APPEARANCE_COMP_THRESHOLD
        or topic in APPEARANCE_TOPICS
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python3.13 -m pytest tests/test_algorithm.py::TestAppearanceThemeMembership -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add core/constants.py core/algorithm.py tests/test_algorithm.py
git commit -m "feat: appearance-theme membership helper + narrative-saturation constants

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Step 7 saturation detection + remedy in `build_prototype_feed`

**Files:**
- Modify: `algorithm/core/algorithm.py` (`build_prototype_feed`)
- Test: `algorithm/tests/test_algorithm.py` (add a test class + one fixture helper)

**Interfaces:**
- Consumes: `is_appearance_theme`, `NARRATIVE_WINDOW`, `NARRATIVE_THRESHOLD`, `NARRATIVE_DAMP`, `NARRATIVE_DIVERSIFY` (Task 1).
- Consumes existing: `build_prototype_feed(df, weights, user_profile, k=..., ...)`, `add_engagement`, `get_mode_settings`.
- Behavior: reads `user_profile["disable_narrative_saturation"]` (bool, default `False`) as a test/ops seam; reads existing `user_profile["age_group"]` for threshold + magnitude.

- [ ] **Step 1: Write the fixture helper + the "saturation breaks the run" test**

Add near the other helpers at the top of `algorithm/tests/test_algorithm.py`:

```python
def make_appearance_saturation_data():
    """Attractive (high-engagement) low-risk appearance clips + less-engaging safe clips.

    Appearance clips outrank safe clips on raw engagement, so a plain feed
    saturates with them; only the Step-7 detector should break that up.
    """
    rows = []
    ap_topics = ["fitness", "beauty", "fashion", "aesthetic"]   # NOT in APPEARANCE_TOPICS
    for i in range(12):
        rows.append({
            "view_count": 100000, "topic": ap_topics[i % len(ap_topics)],
            "channel": f"ap_ch_{i}", "prosocial": 0, "risk": 0.3,
            "appearance_comparison": 0.7, "creator_trait": "casual",
            "active_engagement_ratio": 0.2, "opinion_comparison": 0.0,
            "creator_authenticity": 0.5,
        })
    safe_topics = ["science", "nature", "cooking", "history"]
    for i in range(12):
        rows.append({
            "view_count": 20000, "topic": safe_topics[i % len(safe_topics)],
            "channel": f"safe_ch_{i}", "prosocial": 0, "risk": 0.1,
            "appearance_comparison": 0.0, "creator_trait": "casual",
            "active_engagement_ratio": 0.2, "opinion_comparison": 0.0,
            "creator_authenticity": 0.5,
        })
    df = pd.DataFrame(rows)
    df, _ = add_engagement(df)
    return df


def _appearance_flags(feed_df):
    """List[bool] — was each served row appearance-theme?"""
    return [
        is_appearance_theme(row.appearance_comparison, row.topic)
        for row in feed_df.itertuples(index=False)
    ]


def _longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


class TestNarrativeSaturation(unittest.TestCase):
    """Step 7: break sustained appearance-theme runs of individually-safe clips."""

    def test_saturation_breaks_the_run(self):
        df = make_appearance_saturation_data()
        weights, _ = get_mode_settings("entertainment")

        feed_off = build_prototype_feed(
            df, weights, {"disable_narrative_saturation": True}, k=12)
        feed_on = build_prototype_feed(
            df, weights, {"disable_narrative_saturation": False}, k=12)

        flags_off = _appearance_flags(feed_off)
        flags_on = _appearance_flags(feed_on)

        # Detector strictly reduces both total appearance items and the longest run.
        self.assertLess(sum(flags_on), sum(flags_off))
        self.assertLess(_longest_run(flags_on), _longest_run(flags_off))

        # A safe off-theme item is served within 2 picks after saturation triggers.
        first_off = next((i for i, f in enumerate(flags_on) if not f), None)
        self.assertIsNotNone(first_off)
        self.assertLessEqual(first_off, NARRATIVE_THRESHOLD + 1)  # 4-of-6 trigger -> by index 5
```

Also add `is_appearance_theme`, `get_mode_settings`, `add_engagement`, `NARRATIVE_THRESHOLD` to the test imports (the `from core.algorithm import (...)` block already has `get_mode_settings`, `add_engagement`; add `is_appearance_theme` from `core.algorithm` and `NARRATIVE_THRESHOLD` via `from core.constants import NARRATIVE_THRESHOLD`).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3.13 -m pytest tests/test_algorithm.py::TestNarrativeSaturation::test_saturation_breaks_the_run -v`
Expected: FAIL — with the detector unimplemented, `feed_on` == `feed_off`, so `assertLess` fails (values equal).

- [ ] **Step 3: Implement Step 7 in `build_prototype_feed`**

3a. Add state init. After the Step 6 state block:

```python
        # --- Step 6: Emotional amplification rabbit hole state ---
        emotional_amplification_streak = 0
        EMOTIONAL_STREAK_INTERRUPT = 2
```

insert:

```python
        # --- Step 7: Narrative-saturation state (appearance/body theme) ---
        narrative_enabled = not bool(user_profile.get("disable_narrative_saturation", False))
        narrative_window_history: List[bool] = []
        narrative_threshold = (
            NARRATIVE_THRESHOLD - 1 if age_group == "13-15" else NARRATIVE_THRESHOLD
        )
        narrative_saturated = False
```

(`age_group` is already extracted above in Step 1 of the function.)

3b. Add the per-candidate remedy. Inside the `for row in remaining.itertuples(index=False):` scoring loop, immediately after the existing Step 6 penalty block:

```python
            # Step 6: Penalize emotional amplification rabbit hole continuation
            if emotional_amplification_streak >= EMOTIONAL_STREAK_INTERRUPT:
                if row_eng > 0.6 and row_risk > 0.5:
                    s -= 0.30 * age_protection_factor
```

insert:

```python
            # Step 7: Narrative saturation — break sustained appearance-theme runs
            if narrative_enabled and narrative_saturated:
                if is_appearance_theme(getattr(row, "appearance_comparison", 0.0), topic):
                    s -= NARRATIVE_DAMP * age_protection_factor
                elif row_risk < 0.3:
                    s += NARRATIVE_DIVERSIFY * age_protection_factor
```

3c. Add the state update. After the Step 6 streak update near the end of the pick loop:

```python
        # Step 6: Update emotional amplification streak for next iteration
        _is_amplification = (
            float(best_row.get("engagement", 0.0)) > 0.6
            and float(best_row.get("risk", 0.0)) > 0.5
        )
        emotional_amplification_streak = (
            emotional_amplification_streak + 1 if _is_amplification else 0
        )
```

insert:

```python
        # Step 7: Update narrative-saturation window for next iteration
        _is_appearance = is_appearance_theme(
            best_row.get("appearance_comparison", 0.0), best_row.get("topic", "")
        )
        narrative_window_history.append(_is_appearance)
        if len(narrative_window_history) > NARRATIVE_WINDOW:
            narrative_window_history.pop(0)
        narrative_saturated = sum(narrative_window_history) >= narrative_threshold
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python3.13 -m pytest tests/test_algorithm.py::TestNarrativeSaturation::test_saturation_breaks_the_run -v`
Expected: PASS.

- [ ] **Step 5: Add the remaining three behavioral tests**

Append to `TestNarrativeSaturation`:

```python
    def test_age_breaks_pattern_sooner_for_13_15(self):
        df = make_appearance_saturation_data()
        weights, _ = get_mode_settings("entertainment")

        feed_teen = build_prototype_feed(df, weights, {"age_group": "13-15"}, k=12)
        feed_adult = build_prototype_feed(df, weights, {"age_group": None}, k=12)

        first_off_teen = next(
            (i for i, f in enumerate(_appearance_flags(feed_teen)) if not f), 99)
        first_off_adult = next(
            (i for i, f in enumerate(_appearance_flags(feed_adult)) if not f), 99)

        # 13-15 saturates at 3-of-6 vs 4-of-6, so its first off-theme item is earlier.
        self.assertLess(first_off_teen, first_off_adult)

    def test_no_false_positive_on_normal_feed(self):
        # A feed with essentially no appearance content must be unchanged by the detector.
        df = make_sample_data(120)
        df["appearance_comparison"] = 0.0
        df["topic"] = np.where(df["topic"] == "art", "science", df["topic"])  # keep off-theme
        weights, _ = get_mode_settings("entertainment")

        feed_off = build_prototype_feed(
            df, weights, {"disable_narrative_saturation": True}, k=30)
        feed_on = build_prototype_feed(
            df, weights, {"disable_narrative_saturation": False}, k=30)

        self.assertEqual(
            feed_off["view_count"].tolist(), feed_on["view_count"].tolist())

    def test_does_not_override_crisis_step5(self):
        # An eating_disorder-heavy pool must still route through Step 5 (wellness injection),
        # not be silently governed only by Step 7. We assert Step 5's suppression still bites:
        # high-risk crisis items are pushed down relative to a detector that ignored them.
        rows = []
        for i in range(8):
            rows.append({
                "view_count": 100000, "topic": "eating_disorder", "channel": f"c{i}",
                "prosocial": 0, "risk": 0.9, "appearance_comparison": 0.8,
                "creator_trait": "casual", "active_engagement_ratio": 0.2,
                "opinion_comparison": 0.0, "creator_authenticity": 0.5,
                "is_wellness_resource": 0,
            })
        for i in range(8):
            rows.append({
                "view_count": 40000, "topic": "wellness", "channel": f"w{i}",
                "prosocial": 1, "risk": 0.0, "appearance_comparison": 0.0,
                "creator_trait": "casual", "active_engagement_ratio": 0.2,
                "opinion_comparison": 0.0, "creator_authenticity": 0.5,
                "is_wellness_resource": 1,
            })
        df = pd.DataFrame(rows)
        df, _ = add_engagement(df)
        weights, _ = get_mode_settings("entertainment")

        feed = build_prototype_feed(df, weights, {}, k=12)
        # Step 5 crisis routing should surface wellness resources, not an all-crisis feed.
        wellness_served = int((feed["is_wellness_resource"] == 1).sum())
        self.assertGreater(wellness_served, 0)
```

- [ ] **Step 6: Run the whole algorithm test module**

Run: `.venv/bin/python3.13 -m pytest tests/test_algorithm.py -v`
Expected: PASS — all pre-existing tests plus the new `TestAppearanceThemeMembership` (5) and `TestNarrativeSaturation` (4).

- [ ] **Step 7: Commit**

```bash
git add core/algorithm.py tests/test_algorithm.py
git commit -m "feat: Step 7 narrative-saturation detector for appearance/body theme

Breaks sustained runs of individually-safe appearance clips (#skinnytok),
age-scaled trigger + remedy, ranking-only. Spec 2026-07-02.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Full-suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python3.13 -m pytest -q`
Expected: PASS — no regressions in any module. (If a pre-existing unrelated test is already failing on `main`, note it; do not fix out-of-scope.)

- [ ] **Step 2: Confirm no stray changes**

Run: `git status` and `git diff --stat`
Expected: only `core/constants.py`, `core/algorithm.py`, `tests/test_algorithm.py` touched across the two feature commits.

---

## Notes for the implementer

- The detector is intentionally invisible to users in v1 (ranking-only). Do not add captions, API fields, or frontend changes — those are separate planned specs (gaps #2–#4).
- Numeric defaults (`NARRATIVE_WINDOW=6`, `NARRATIVE_THRESHOLD=4`, damp/diversify magnitudes) are starting values. If `test_saturation_breaks_the_run` passes but the break feels too eager/too slow in the simulation-agent, tune the constants — the tests assert *relative* behavior and should still hold.
- Keep `APPEARANCE_TOPICS` free of crisis topics; Step 5 owns those and the crisis-boundary test guards it.
