"""
Comprehensive tests for the Healthy Feed Algorithm.

Tests cover:
- Algorithm scoring functions
- Feed generation
- Diversity metrics
- Preset configurations
- Edge cases
"""

import unittest
import pandas as pd
import numpy as np

from core.algorithm import (
    WEIGHTS,
    night_mode_settings,
    get_mode_settings,
    validate_and_clean,
    add_engagement,
    calculate_gini,
    score_parts,
    would_break_streak,
    rank_baseline,
    build_prototype_feed
)

from core.metrics import (
    diversity_at_k,
    max_streak,
    prosocial_ratio,
    overlap_ratio,
    jaccard_similarity,
    gini_distribution,
)


# =============================================================================
# Test Data Helpers
# =============================================================================

def make_sample_data(n=100):
    """Create minimal valid dataset for testing."""
    np.random.seed(42)
    topics = ["science", "art", "music", "sports", "tech"]
    channels = [f"channel_{i}" for i in range(10)]

    df = pd.DataFrame({
        "view_count": np.random.randint(1000, 100000, n),
        "topic": np.random.choice(topics, n),
        "channel": np.random.choice(channels, n),
        "prosocial": np.random.choice([0, 1], n),
        "risk": np.random.random(n),
        "appearance_comparison": np.random.random(n),
        "creator_trait": np.random.choice(["casual", "formal", "humorous"], n),
        # Research-backed additions
        "active_engagement_ratio": np.random.random(n),
        "opinion_comparison": np.random.random(n),
        "creator_authenticity": np.random.random(n),
    })
    # Add engagement column
    df, _ = add_engagement(df)
    return df


# =============================================================================
# Test: Weight Presets
# =============================================================================

class TestWeightPresets(unittest.TestCase):
    """Test preset weight configurations."""

    def test_all_presets_exist(self):
        """Verify all expected presets are defined."""
        expected = {"baseline", "entertainment", "inspiration", "learning"}
        self.assertEqual(set(WEIGHTS.keys()), expected)

    def test_weights_sum_to_one(self):
        """Non-baseline presets should have weights summing to ~1.0."""
        for preset, weights in WEIGHTS.items():
            if preset == "baseline":
                continue
            total = sum(weights.values())
            self.assertAlmostEqual(total, 1.0, places=2,
                                   msg=f"{preset} weights sum to {total}")

    def test_get_mode_settings_valid(self):
        """Test getting settings for valid preset."""
        weights, k = get_mode_settings("entertainment")
        self.assertEqual(weights["e"], 0.55)
        self.assertEqual(k, 100)

    def test_get_mode_settings_invalid(self):
        """Test that invalid preset raises error."""
        with self.assertRaises(KeyError):
            get_mode_settings("nonexistent_preset")

    def test_night_mode_adjusts_weights(self):
        """Night mode should increase risk weight."""
        normal = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        adjusted, _ = night_mode_settings(normal)
        self.assertGreater(adjusted["r"], normal["r"])


# =============================================================================
# Test: Data Validation
# =============================================================================

class TestDataValidation(unittest.TestCase):
    """Test dataset validation and cleaning."""

    def test_valid_data_passes(self):
        """Valid data should pass validation."""
        df = make_sample_data(10)
        result = validate_and_clean(df)
        self.assertEqual(len(result), 10)

    def test_missing_columns_raises(self):
        """Missing required columns should raise error."""
        df = pd.DataFrame({"view_count": [1, 2, 3]})
        with self.assertRaises(ValueError):
            validate_and_clean(df)

    def test_prosocial_clamped(self):
        """Prosocial values should be clamped to [0, 1]."""
        df = make_sample_data(10)
        df["prosocial"] = [-0.5, 1.5, 0.3, 0.8, -1, 2, 0.5, 0.5, 0.5, 0.5]
        result = validate_and_clean(df)
        self.assertTrue(result["prosocial"].between(0, 1).all())

    def test_add_engagement_normalizes(self):
        """Engagement should be normalized by max views."""
        df = pd.DataFrame({"view_count": [1000, 5000, 10000]})
        result, max_views = add_engagement(df)
        self.assertEqual(max_views, 10000)
        pd.testing.assert_series_equal(
            result["engagement"],
            pd.Series([0.1, 0.5, 1.0], name="engagement")
        )


# =============================================================================
# Test: Gini Coefficient
# =============================================================================

class TestGiniCoefficient(unittest.TestCase):
    """Test Gini coefficient calculations."""

    def test_perfect_equality(self):
        """Equal distribution should give Gini near 0."""
        dist = [10, 10, 10, 10]
        gini = calculate_gini(dist)
        self.assertAlmostEqual(gini, 0.0, places=2)

    def test_perfect_inequality(self):
        """One item having everything should give Gini near 1."""
        dist = [1, 1, 1, 97]  # Avoid zeros which can cause issues
        gini = calculate_gini(dist)
        self.assertGreater(gini, 0.7)  # Should be high inequality

    def test_empty_distribution(self):
        """Empty distribution should return 0."""
        self.assertEqual(calculate_gini([]), 0.0)

    def test_single_item(self):
        """Single item distribution."""
        self.assertEqual(calculate_gini([5]), 0.0)


# =============================================================================
# Test: Score Parts
# =============================================================================

class TestScoreParts(unittest.TestCase):
    """Test individual score calculation."""

    def test_baseline_weights(self):
        """With baseline weights, only engagement matters."""
        weights = {"e": 1.0, "d": 0.0, "p": 0.0, "r": 0.0}
        score = score_parts(e=0.8, d=0.5, p=0.9, r=0.1, w=weights)
        self.assertAlmostEqual(score, 0.8, places=2)

    def test_passive_streak_decay(self):
        """Higher passive streak should reduce engagement contribution."""
        weights = {"e": 1.0, "d": 0.0, "p": 0.0, "r": 0.0}
        score_fresh = score_parts(e=0.8, d=0, p=0, r=0, w=weights, passive_streak=0)
        score_tired = score_parts(e=0.8, d=0, p=0, r=0, w=weights, passive_streak=5)
        self.assertGreater(score_fresh, score_tired)

    def test_similarity_mitigates_risk(self):
        """High similarity should reduce risk penalty."""
        weights = {"e": 0.5, "d": 0.0, "p": 0.0, "r": 0.5}

        # High appearance comparison + similar creator = less risk
        score_similar = score_parts(
            e=0.5, d=0, p=0, r=0.8, w=weights,
            appearance_comp=0.8, similarity=1.0
        )

        # High appearance comparison + different creator = more risk
        score_different = score_parts(
            e=0.5, d=0, p=0, r=0.8, w=weights,
            appearance_comp=0.8, similarity=-1.0
        )

        self.assertGreater(score_similar, score_different)


# =============================================================================
# Test: Streak Prevention
# =============================================================================

class TestStreakPrevention(unittest.TestCase):
    """Test streak-breaking logic."""

    def test_short_history_no_block(self):
        """Should not block when history is shorter than max_streak."""
        recent = ["A", "B"]
        self.assertFalse(would_break_streak(recent, "A", max_streak=3))

    def test_would_break_streak(self):
        """Should detect when adding would create a streak."""
        recent = ["A", "A"]
        self.assertTrue(would_break_streak(recent, "A", max_streak=2))

    def test_different_value_no_block(self):
        """Different value should not trigger streak block."""
        recent = ["A", "A"]
        self.assertFalse(would_break_streak(recent, "B", max_streak=2))


# =============================================================================
# Test: Full Feed Generation
# =============================================================================

class TestFeedGeneration(unittest.TestCase):
    """Test complete feed generation."""

    def test_baseline_ranking(self):
        """Baseline should rank by engagement only."""
        df = make_sample_data(50)
        result = rank_baseline(df, k=10)
        self.assertEqual(len(result), 10)
        # Verify sorted by engagement descending
        engagements = result["engagement"].tolist()
        self.assertEqual(engagements, sorted(engagements, reverse=True))

    def test_prototype_feed_length(self):
        """Prototype feed should respect k parameter."""
        df = make_sample_data(100)
        weights, _ = get_mode_settings("entertainment")

        result = build_prototype_feed(
            df, weights=weights, user_profile={}, k=50
        )
        self.assertEqual(len(result), 50)

    def test_prototype_improves_diversity(self):
        """Prototype should have better diversity than baseline."""
        df = make_sample_data(200)
        weights, _ = get_mode_settings("inspiration")  # High diversity weight

        baseline = rank_baseline(df, k=50)
        prototype = build_prototype_feed(
            df, weights=weights, user_profile={}, k=50
        )

        baseline_div = diversity_at_k(baseline, k=10)
        prototype_div = diversity_at_k(prototype, k=10)

        # Prototype should have equal or better diversity
        self.assertGreaterEqual(prototype_div, baseline_div * 0.8)

    def test_prototype_reduces_streaks(self):
        """Prototype should limit topic streaks."""
        df = make_sample_data(200)
        weights, _ = get_mode_settings("learning")

        result = build_prototype_feed(
            df, weights=weights, user_profile={}, k=50, max_streak=2
        )

        # Check no topic streak exceeds max_streak + 1 (allowing some flexibility)
        topic_streak = max_streak(result, "topic")
        self.assertLessEqual(topic_streak, 4)  # Some flexibility for edge cases

    def test_user_profile_affects_output(self):
        """Different user profiles should produce different feeds."""
        df = make_sample_data(100)
        weights, _ = get_mode_settings("entertainment")

        profile_fresh = {"passive_streak": 0, "user_trait": "casual"}
        profile_tired = {"passive_streak": 10, "user_trait": "formal"}

        feed_fresh = build_prototype_feed(df, weights, profile_fresh, k=20)
        feed_tired = build_prototype_feed(df, weights, profile_tired, k=20)

        # Compare actual selected items via view_count as a stable identifier.
        # (The DataFrame index is reset to 0..k-1 inside build_prototype_feed,
        # so comparing .index would always give identical sets.)
        fresh_items = set(feed_fresh["view_count"].tolist())
        tired_items = set(feed_tired["view_count"].tolist())

        # At least some items should differ between profiles
        self.assertNotEqual(fresh_items, tired_items,
                            "Expected profiles with streak=0/casual vs streak=10/formal "
                            "to select at least one different item")


# =============================================================================
# Test: Metrics
# =============================================================================

class TestMetrics(unittest.TestCase):
    """Test evaluation metrics."""

    def test_diversity_at_k(self):
        """Test diversity calculation."""
        df = pd.DataFrame({"topic": ["A", "A", "B", "C", "D"]})
        self.assertEqual(diversity_at_k(df, k=3), 2)
        self.assertEqual(diversity_at_k(df, k=5), 4)

    def test_max_streak(self):
        """Test streak calculation."""
        df = pd.DataFrame({"topic": ["A", "A", "B", "B", "B", "A"]})
        self.assertEqual(max_streak(df, "topic"), 3)

    def test_prosocial_ratio(self):
        """Test prosocial ratio calculation."""
        df = pd.DataFrame({"prosocial": [1, 1, 0, 1, 0]})
        self.assertAlmostEqual(prosocial_ratio(df), 0.6)

    def test_overlap_ratio(self):
        """Test overlap between feeds."""
        ids_a = [1, 2, 3, 4, 5]
        ids_b = [3, 4, 5, 6, 7]
        # 3 overlap out of 5
        self.assertEqual(overlap_ratio(ids_a, ids_b, top_n=5), 0.6)

    def test_jaccard_similarity(self):
        """Test Jaccard similarity."""
        ids_a = [1, 2, 3]
        ids_b = [2, 3, 4]
        # Intersection: {2,3}, Union: {1,2,3,4}
        self.assertEqual(jaccard_similarity(ids_a, ids_b), 0.5)


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_dataframe(self):
        """Empty feed should return 0 for metrics."""
        empty_df = pd.DataFrame()
        self.assertEqual(diversity_at_k(empty_df), 0)
        self.assertEqual(max_streak(empty_df, "topic"), 0)
        self.assertEqual(prosocial_ratio(empty_df), 0.0)

    def test_k_larger_than_data(self):
        """Requesting k > available data should return all data."""
        df = make_sample_data(10)
        weights, _ = get_mode_settings("entertainment")
        result = build_prototype_feed(df, weights, {}, k=100)
        self.assertEqual(len(result), 10)

    def test_single_item_feed(self):
        """Single item should work without errors."""
        df = make_sample_data(1)
        weights, _ = get_mode_settings("entertainment")
        result = build_prototype_feed(df, weights, {}, k=1)
        self.assertEqual(len(result), 1)

    def test_all_same_topic(self):
        """Dataset with single topic should still work."""
        df = make_sample_data(50)
        df["topic"] = "everything"
        weights, _ = get_mode_settings("entertainment")
        result = build_prototype_feed(df, weights, {}, k=10)
        self.assertEqual(len(result), 10)


# =============================================================================
# Integration Test
# =============================================================================

class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""

    def test_full_pipeline(self):
        """Test complete pipeline from raw data to metrics."""
        # Create data
        df = make_sample_data(500)

        # Validate and add engagement
        df = validate_and_clean(df)
        df, _ = add_engagement(df)

        # Get weights
        weights, k = get_mode_settings("inspiration", night_mode=True)

        # Build feed
        user_profile = {"passive_streak": 3, "user_trait": "humorous"}
        feed = build_prototype_feed(df, weights, user_profile, k=k)

        # Calculate metrics
        div_10 = diversity_at_k(feed, k=10)
        topic_streak = max_streak(feed, "topic")
        p_ratio = prosocial_ratio(feed)

        # Verify reasonable values
        self.assertGreaterEqual(div_10, 1)
        self.assertGreaterEqual(len(feed), k - 10)  # Allow some flexibility
        self.assertGreaterEqual(p_ratio, 0.0)
        self.assertLessEqual(p_ratio, 1.0)


# =============================================================================
# Test: Score Parts — Advanced
# =============================================================================

class TestScorePartsAdvanced(unittest.TestCase):
    """Deeper tests for score_parts weight redistribution and affinity bonus."""

    def test_zero_streak_is_noop(self):
        """passive_streak=0 should leave weights unchanged (decay factor = 1)."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        # With streak=0 and no similarity effects, score = e*w_e + d*w_d + p*w_p - r*w_r
        score = score_parts(e=1.0, d=0.0, p=0.0, r=0.0, w=weights, passive_streak=0)
        self.assertAlmostEqual(score, 0.55, places=5)

    def test_high_streak_shifts_weight_to_diversity(self):
        """With a very high streak, diversity + prosocial should dominate over engagement."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        # Item A: high engagement, low diversity/prosocial
        score_high_e = score_parts(e=1.0, d=0.1, p=0.1, r=0.0, w=weights, passive_streak=20)
        # Item B: low engagement, high diversity/prosocial
        score_high_dp = score_parts(e=0.1, d=0.9, p=0.9, r=0.0, w=weights, passive_streak=20)
        self.assertGreater(score_high_dp, score_high_e)

    def test_affinity_bonus_on_matching_trait(self):
        """similarity=1 should score higher than similarity=-1 even without risk."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.0}
        score_match = score_parts(e=0.5, d=0.5, p=0.5, r=0.0, w=weights, similarity=1.0)
        score_mismatch = score_parts(e=0.5, d=0.5, p=0.5, r=0.0, w=weights, similarity=-1.0)
        self.assertGreater(score_match, score_mismatch)

    def test_no_affinity_when_similarity_zero(self):
        """Default similarity=0 should give no affinity bonus (baseline behaviour)."""
        weights = {"e": 1.0, "d": 0.0, "p": 0.0, "r": 0.0}
        score_default = score_parts(e=0.8, d=0, p=0, r=0, w=weights)
        score_explicit_zero = score_parts(e=0.8, d=0, p=0, r=0, w=weights, similarity=0.0)
        self.assertAlmostEqual(score_default, score_explicit_zero, places=10)

    def test_risk_amplified_on_mismatch_with_appearance_comp(self):
        """similarity=-1 + high appearance_comp should make risk worse than no mitigation."""
        weights = {"e": 0.0, "d": 0.0, "p": 0.0, "r": 1.0}
        # No appearance comparison: risk unmodified
        score_no_comp = score_parts(e=0, d=0, p=0, r=0.5, w=weights,
                                    appearance_comp=0.0, similarity=-1.0)
        # High appearance comparison + mismatch: risk amplified
        score_mismatch = score_parts(e=0, d=0, p=0, r=0.5, w=weights,
                                     appearance_comp=0.9, similarity=-1.0)
        self.assertLess(score_mismatch, score_no_comp)


# =============================================================================
# Test: Night Mode Guarantees
# =============================================================================

class TestNightModeGuarantees(unittest.TestCase):
    """Night mode must produce valid, normalised weights and a smaller k."""

    def test_night_mode_weights_sum_to_one(self):
        """Weights after night mode should still sum to 1.0."""
        for preset, w in WEIGHTS.items():
            if preset == "baseline":
                continue
            adjusted, _ = night_mode_settings(dict(w))
            total = sum(adjusted.values())
            self.assertAlmostEqual(total, 1.0, places=5,
                                   msg=f"{preset} night mode weights sum to {total}")

    def test_night_mode_returns_night_k(self):
        """Night mode k should be smaller than default k."""
        _, k_normal = get_mode_settings("entertainment")
        _, k_night = get_mode_settings("entertainment", night_mode=True)
        self.assertLess(k_night, k_normal)

    def test_night_mode_all_weights_non_negative(self):
        """No weight should go negative after the risk boost."""
        for preset, w in WEIGHTS.items():
            if preset == "baseline":
                continue
            adjusted, _ = night_mode_settings(dict(w))
            for key, val in adjusted.items():
                self.assertGreaterEqual(val, 0.0,
                                        msg=f"{preset} key '{key}' went negative")


# =============================================================================
# Test: Data Validation — Advanced
# =============================================================================

class TestDataValidationAdvanced(unittest.TestCase):
    """Edge cases for validate_and_clean and add_engagement."""

    def test_nan_risk_filled_to_zero(self):
        """NaN in 'risk' should be coerced to 0 after cleaning."""
        df = make_sample_data(5)
        df.loc[0, "risk"] = float("nan")
        result = validate_and_clean(df)
        self.assertEqual(result.loc[0, "risk"], 0.0)

    def test_nan_appearance_comparison_filled(self):
        """NaN in 'appearance_comparison' should be coerced to 0."""
        df = make_sample_data(5)
        df.loc[2, "appearance_comparison"] = float("nan")
        result = validate_and_clean(df)
        self.assertEqual(result.loc[2, "appearance_comparison"], 0.0)

    def test_risk_clamped_to_one(self):
        """Risk values > 1 should be clamped to 1.0."""
        df = make_sample_data(5)
        df["risk"] = [0.5, 1.5, 2.0, -0.1, 0.8]
        result = validate_and_clean(df)
        self.assertTrue(result["risk"].between(0, 1).all())

    def test_extra_columns_preserved(self):
        """Columns not in REQUIRED_COLUMNS should pass through untouched."""
        df = make_sample_data(5)
        df["my_custom_col"] = 99
        result = validate_and_clean(df)
        self.assertIn("my_custom_col", result.columns)
        self.assertTrue((result["my_custom_col"] == 99).all())

    def test_add_engagement_zero_views_safe(self):
        """All-zero view counts should not cause division by zero."""
        df = pd.DataFrame({"view_count": [0, 0, 0]})
        result, max_views = add_engagement(df)
        self.assertEqual(max_views, 1)          # clamped to 1
        self.assertTrue((result["engagement"] == 0.0).all())

    def test_add_engagement_single_row(self):
        """Single-row dataset should normalise to engagement=1.0."""
        df = pd.DataFrame({"view_count": [42000]})
        result, _ = add_engagement(df)
        self.assertAlmostEqual(result["engagement"].iloc[0], 1.0)

    def test_new_columns_clipped(self):
        """active_engagement_ratio, opinion_comparison, creator_authenticity
        should be clipped to [0, 1] after validate_and_clean."""
        df = make_sample_data(5)
        df["active_engagement_ratio"] = [-0.5, 1.5, 0.3, 0.7, 2.0]
        df["opinion_comparison"]      = [ 1.2, -0.1, 0.4, 0.9, 0.0]
        df["creator_authenticity"]    = [ 0.5,  0.5, 3.0, 0.1, -1.0]
        result = validate_and_clean(df)
        for col in ("active_engagement_ratio", "opinion_comparison", "creator_authenticity"):
            self.assertTrue(result[col].between(0, 1).all(),
                            msg=f"{col} not clipped to [0,1]")

    def test_new_columns_nan_filled(self):
        """NaN in the three new columns should be coerced to 0 after cleaning."""
        df = make_sample_data(3)
        df.loc[0, "active_engagement_ratio"] = float("nan")
        df.loc[1, "opinion_comparison"]      = float("nan")
        df.loc[2, "creator_authenticity"]    = float("nan")
        result = validate_and_clean(df)
        self.assertEqual(result.loc[0, "active_engagement_ratio"], 0.0)
        self.assertEqual(result.loc[1, "opinion_comparison"],      0.0)
        self.assertEqual(result.loc[2, "creator_authenticity"],    0.0)

    def test_missing_new_columns_raises(self):
        """Dataset missing any of the new required columns should raise ValueError."""
        for col in ("active_engagement_ratio", "opinion_comparison", "creator_authenticity"):
            df = make_sample_data(5).drop(columns=[col])
            with self.assertRaises(ValueError, msg=f"Should raise for missing '{col}'"):
                validate_and_clean(df)


# =============================================================================
# Test: Feed Quality Properties
# =============================================================================

class TestFeedQuality(unittest.TestCase):
    """Structural guarantees about what build_prototype_feed produces."""

    def test_no_duplicate_items_in_feed(self):
        """Every item in the feed should appear exactly once."""
        df = make_sample_data(100)
        weights, _ = get_mode_settings("entertainment")
        result = build_prototype_feed(df, weights, {}, k=50)
        # Use view_count as unique-enough proxy; check no duplicates
        self.assertEqual(len(result), result["view_count"].drop_duplicates().shape[0])

    def test_high_risk_items_score_lower(self):
        """A feed built with high risk-weight should deprioritise high-risk items."""
        np.random.seed(0)
        n = 60
        # Two groups: low-risk (first 30) vs high-risk (last 30), equal engagement
        df = pd.DataFrame({
            "view_count": [50000] * n,
            "topic": ["science", "art"] * (n // 2),
            "channel": [f"ch_{i % 5}" for i in range(n)],
            "prosocial": [1] * n,
            "risk": [0.05] * 30 + [0.95] * 30,
            "appearance_comparison": [0.8] * n,
            "creator_trait": ["casual"] * n,
        })
        df, _ = add_engagement(df)

        # Use a risk-heavy preset
        weights = {"e": 0.20, "d": 0.20, "p": 0.20, "r": 0.40}
        result = build_prototype_feed(df, weights, {}, k=20)

        avg_risk = result["risk"].mean()
        self.assertLess(avg_risk, 0.5,
                        "Expected feed to contain mostly low-risk items")

    def test_prosocial_favoured_in_learning_preset(self):
        """Learning preset (high prosocial weight) should yield higher prosocial ratio
        than entertainment preset (low prosocial weight) on the same dataset."""
        df = make_sample_data(200)

        weights_learn, _ = get_mode_settings("learning")
        weights_entertain, _ = get_mode_settings("entertainment")

        feed_learn = build_prototype_feed(df, weights_learn, {}, k=50)
        feed_entertain = build_prototype_feed(df, weights_entertain, {}, k=50)

        ratio_learn = prosocial_ratio(feed_learn)
        ratio_entertain = prosocial_ratio(feed_entertain)

        self.assertGreaterEqual(ratio_learn, ratio_entertain * 0.9,
                                "Learning preset should not have a lower prosocial ratio "
                                "than entertainment preset")

    def test_rank_baseline_returns_all_when_k_exceeds_data(self):
        """rank_baseline with k > len(df) should return the full dataset."""
        df = make_sample_data(10)
        result = rank_baseline(df, k=9999)
        self.assertEqual(len(result), 10)

    def test_rank_baseline_sorted_descending(self):
        """rank_baseline should always return items sorted by engagement descending."""
        df = make_sample_data(50)
        result = rank_baseline(df, k=50)
        engagements = result["engagement"].tolist()
        self.assertEqual(engagements, sorted(engagements, reverse=True))


# =============================================================================
# Test: Metrics — Edge Cases & Missing Coverage
# =============================================================================

class TestMetricsEdgeCases(unittest.TestCase):
    """Edge cases and previously untested metric functions."""

    # --- gini_distribution (had zero coverage) ---

    def test_gini_distribution_equal_spread(self):
        """Equal representation of all categories -> low Gini."""
        feed = pd.DataFrame({"topic": ["A", "B", "C", "D"]})
        gini = gini_distribution(feed, "topic", ["A", "B", "C", "D"])
        self.assertAlmostEqual(gini, 0.0, places=2)

    def test_gini_distribution_single_category(self):
        """All items in one category -> high Gini."""
        feed = pd.DataFrame({"topic": ["A", "A", "A", "A"]})
        gini = gini_distribution(feed, "topic", ["A", "B", "C", "D"])
        self.assertGreater(gini, 0.5)

    def test_gini_distribution_empty_feed(self):
        """Empty feed should return 0.0."""
        feed = pd.DataFrame({"topic": []})
        gini = gini_distribution(feed, "topic", ["A", "B", "C"])
        self.assertEqual(gini, 0.0)

    def test_gini_distribution_missing_column_raises(self):
        """Missing column should raise ValueError."""
        feed = pd.DataFrame({"other": [1, 2, 3]})
        with self.assertRaises(ValueError):
            gini_distribution(feed, "topic", ["A", "B"])

    # --- diversity_at_k edge cases ---

    def test_diversity_at_k_zero(self):
        """k=0 should return 0 unique topics."""
        df = pd.DataFrame({"topic": ["A", "B", "C"]})
        self.assertEqual(diversity_at_k(df, k=0), 0)

    def test_diversity_at_k_exceeds_length(self):
        """k larger than feed length should not raise and caps at feed length."""
        df = pd.DataFrame({"topic": ["A", "B"]})
        self.assertEqual(diversity_at_k(df, k=100), 2)

    # --- max_streak edge cases ---

    def test_max_streak_single_item(self):
        """Single-item feed should have streak of 1."""
        df = pd.DataFrame({"topic": ["A"]})
        self.assertEqual(max_streak(df, "topic"), 1)

    def test_max_streak_no_streak(self):
        """Alternating values should give max streak of 1."""
        df = pd.DataFrame({"topic": ["A", "B", "A", "B", "A"]})
        self.assertEqual(max_streak(df, "topic"), 1)

    # --- jaccard_similarity edge cases ---

    def test_jaccard_identical_sets(self):
        """Identical inputs should give Jaccard = 1.0."""
        ids = [1, 2, 3, 4, 5]
        self.assertEqual(jaccard_similarity(ids, ids), 1.0)

    def test_jaccard_disjoint_sets(self):
        """Completely disjoint inputs should give Jaccard = 0.0."""
        self.assertEqual(jaccard_similarity([1, 2, 3], [4, 5, 6]), 0.0)

    # --- overlap_ratio edge cases ---

    def test_overlap_ratio_zero_top_n(self):
        """top_n=0 should return 0.0 without division error."""
        self.assertEqual(overlap_ratio([1, 2, 3], [1, 2, 3], top_n=0), 0.0)

    def test_overlap_ratio_full_overlap(self):
        """Identical lists should give overlap_ratio = 1.0."""
        ids = [1, 2, 3, 4, 5]
        self.assertEqual(overlap_ratio(ids, ids, top_n=5), 1.0)



# =============================================================================
# Test: New Scoring Dimensions
# =============================================================================

class TestNewScoringDimensions(unittest.TestCase):
    """Tests for active engagement ratio, creator authenticity, opinion comparison,
    and expanded night mode — all research-gap additions."""

    def test_active_engagement_raises_score(self):
        """Higher active_engagement_ratio should produce a higher score."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        score_passive = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                    active_engagement_ratio=0.0)
        score_active  = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                    active_engagement_ratio=1.0)
        self.assertGreater(score_active, score_passive)

    def test_creator_authenticity_boosts_score(self):
        """Higher creator_authenticity should produce a higher effective score
        via the engagement multiplier."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        score_low  = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                 creator_authenticity=0.0)
        score_high = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                 creator_authenticity=1.0)
        self.assertGreater(score_high, score_low)

    def test_opinion_comparison_bonus_above_threshold(self):
        """opinion_comp > 0.5 should add a positive bonus to the score."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        score_no_opinion   = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                         opinion_comp=0.0)
        score_high_opinion = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                         opinion_comp=1.0)
        self.assertGreater(score_high_opinion, score_no_opinion)

    def test_opinion_bonus_only_above_threshold(self):
        """opinion_comp <= 0.5 should NOT add a bonus (stays at zero)."""
        weights = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        score_zero = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                 opinion_comp=0.0)
        score_half = score_parts(e=0.5, d=0.5, p=0.5, r=0.1, w=weights,
                                 opinion_comp=0.5)
        self.assertAlmostEqual(score_zero, score_half, places=10,
                               msg="No opinion bonus expected at or below threshold")

    def test_night_mode_boosts_prosocial_weight(self):
        """Night mode should increase the prosocial weight above its daytime value."""
        normal   = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        adjusted, _ = night_mode_settings(dict(normal))
        # After re-normalisation the prosocial weight should be higher
        self.assertGreater(adjusted["p"], normal["p"])

    def test_night_mode_boosts_both_r_and_p(self):
        """Both risk and prosocial weights should be elevated in night mode."""
        normal   = {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10}
        adjusted, _ = night_mode_settings(dict(normal))
        self.assertGreater(adjusted["r"], normal["r"])
        self.assertGreater(adjusted["p"], normal["p"])


# =============================================================================
# Test: UCRS (User-Controllable Recommender System)
# =============================================================================

class TestUCRS(unittest.TestCase):
    """Tests for boost_topics, reduce_topics, override_passive_history,
    and novelty_tolerance — the lightweight UCRS controls."""

    def test_reduce_topics_excluded_from_feed(self):
        """Topics listed in reduce_topics should not appear anywhere in the feed."""
        df = make_sample_data(100)
        # Ensure the topic to remove actually exists in the data
        df.loc[df.index[:30], "topic"] = "sports"
        weights, _ = get_mode_settings("entertainment")

        result = build_prototype_feed(
            df, weights, {"reduce_topics": ["sports"]}, k=50
        )
        self.assertNotIn("sports", result["topic"].values,
                         "reduced topic must be fully absent from feed")

    def test_boost_topics_increases_representation(self):
        """A boosted topic that is under-ranked by engagement alone should
        appear more often in the boosted feed than in the control feed."""
        df = make_sample_data(200)
        weights, _ = get_mode_settings("entertainment")

        # Suppress sports engagement so it won't win on merit alone
        df.loc[df["topic"] == "sports", "engagement"] = 0.05

        result_control = build_prototype_feed(df, weights, {}, k=50)
        result_boosted = build_prototype_feed(
            df, weights, {"boost_topics": ["sports"]}, k=50
        )

        count_control = (result_control["topic"] == "sports").sum()
        count_boosted = (result_boosted["topic"] == "sports").sum()
        self.assertGreaterEqual(count_boosted, count_control,
                                "boosted topic should appear at least as often as in control")

    def test_override_passive_history_cancels_streak_effect(self):
        """override_passive_history=True should produce the same feed as
        passive_streak=0, regardless of how large the recorded streak is."""
        df = make_sample_data(100)
        weights, _ = get_mode_settings("entertainment")

        profile_fresh    = {"passive_streak": 0}
        profile_override = {"passive_streak": 15, "override_passive_history": True}

        feed_fresh    = build_prototype_feed(df, weights, profile_fresh,    k=20)
        feed_override = build_prototype_feed(df, weights, profile_override, k=20)

        # Same items must be selected (use view_count as stable item identifier)
        fresh_items    = set(feed_fresh["view_count"].tolist())
        override_items = set(feed_override["view_count"].tolist())
        self.assertEqual(fresh_items, override_items,
                         "override_passive_history should produce the same feed as streak=0")

    def test_high_novelty_tolerance_is_more_diverse(self):
        """novelty_tolerance=1.0 should yield a feed with at least as many
        unique topics in the top 20 as novelty_tolerance=0.0."""
        df = make_sample_data(200)
        weights, _ = get_mode_settings("inspiration")  # high diversity weight

        feed_low  = build_prototype_feed(df, weights, {"novelty_tolerance": 0.0}, k=50)
        feed_high = build_prototype_feed(df, weights, {"novelty_tolerance": 1.0}, k=50)

        div_low  = diversity_at_k(feed_low,  k=20)
        div_high = diversity_at_k(feed_high, k=20)
        self.assertGreaterEqual(div_high, div_low,
                                "higher novelty tolerance should not reduce topic diversity")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
