"""
Testing different algorithms for the project.

Baseline: engagement-only ranking
Prototype: engagement (decayed) + diversity (Gini) + prosocial - risk (similarity mindset)
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

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
)


# -----------------------------
# Presets / Modes
# -----------------------------

WEIGHTS: Dict[str, Dict[str, float]] = {
    "baseline": {"e": 1.00, "d": 0.00, "p": 0.00, "r": 0.00},
    "entertainment": {"e": 0.55, "d": 0.20, "p": 0.15, "r": 0.10},
    "inspiration": {"e": 0.30, "d": 0.40, "p": 0.20, "r": 0.10},
    "learning": {"e": 0.30, "d": 0.30, "p": 0.30, "r": 0.10},
}

# Feed length cap for night mode — imported from constants as NIGHT_FEED_CAP

# Topics that warrant tighter streak caps due to documented adolescent harm
HIGH_RISK_TOPICS = frozenset({
    "body_image", "eating_disorder", "self_harm", "depression",
    "suicide", "anxiety", "weight_loss", "appearance",
})

# Topics that trigger crisis re-routing and wellness injection
CRISIS_TOPICS = frozenset({
    "self_harm", "suicide", "eating_disorder", "depression",
    "crisis", "mental_health_crisis",
})


def night_mode_settings(w, risk_boost=NIGHT_RISK_BOOST, prosocial_boost=NIGHT_PROSOCIAL_BOOST):
    """
    Adjusts weights for night-time viewing.
    Raises risk sensitivity AND prosocial weight (research: night mode should
    protect against harmful content AND promote calming prosocial content).
    Both boosts are applied then the full weight vector is re-normalised to 1.0.
    """
    w2 = dict(w)
    w2["r"] = w2.get("r", 0.0) + risk_boost
    w2["p"] = w2.get("p", 0.0) + prosocial_boost

    total = sum(w2.values())
    if total != 0:
        for key in w2:
            w2[key] = w2[key] / total

    return w2, NIGHT_FEED_CAP


def get_mode_settings(preset, night_mode=False, k_default=100):
    if preset not in WEIGHTS:
        raise KeyError(
            f"Unknown preset: {preset}. Options: {list(WEIGHTS.keys())}")

    w = WEIGHTS[preset]
    k = k_default

    if night_mode:
        w, k = night_mode_settings(w)

    return w, k


# -----------------------------
# Dataset prep / validation
# -----------------------------

REQUIRED_COLUMNS = {
    "view_count", "topic", "channel", "prosocial", "risk",
    "appearance_comparison", "creator_trait",
    # Research-backed additions
    "active_engagement_ratio",  # comments+shares / views — active vs. passive signal
    "opinion_comparison",       # opinion/discourse comparison content (identity-positive)
    "creator_authenticity",     # temporal consistency of creator voice (0=trend-chaser, 1=genuine)
}

def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Dataset is missing required columns: {sorted(missing)}")

    out = df.copy()

    for col in ("prosocial", "risk", "appearance_comparison",
                "active_engagement_ratio", "opinion_comparison", "creator_authenticity"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).clip(0, 1)

    return out


def add_engagement(df: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    out = df.copy()
    max_views = out["view_count"].max()
    if not max_views or max_views == 0:
        max_views = 1
    out["engagement"] = out["view_count"] / max_views
    return out, float(max_views)


# -----------------------------
# Scoring helpers
# -----------------------------

def calculate_gini(distribution: List[int]) -> float:
    """Calculates the Gini coefficient of a frequency distribution."""
    if not distribution or sum(distribution) == 0:
        return 0.0
    arr = np.sort(np.array(distribution, dtype=float))
    n = len(arr)
    index = np.arange(1, n + 1)
    return (np.sum((2 * index - n - 1) * arr)) / (n * np.sum(arr))

def score_parts(e: float, d: float, p: float, r: float, w: Dict[str, float],
                passive_streak: int = 0, similarity: float = 0.0,
                appearance_comp: float = 0.0,
                active_engagement_ratio: float = 0.0,
                opinion_comp: float = 0.0,
                creator_authenticity: float = 0.0) -> float:
    """
    Total score with all research-backed dimensions.

    passive_streak decay:
        Weight shifts from engagement toward diversity + prosocial as passive
        viewing continues, keeping total weight budget constant at 1.0.

    similarity mindset:
        similarity=+1.0  (creator trait matches user trait)
            * affinity bonus on effective engagement
            * mitigates risk when appearance comparison is high
        similarity=-1.0  (mismatch)
            * no affinity bonus
            * amplifies risk when appearance comparison is high

    active_engagement_ratio  [0, 1]:
        Content-side signal. Videos that historically provoke comments/shares
        receive an additive score bonus (up to +0.15), rewarding active rather
        than passive consumption (research §2.1).

    creator_authenticity  [0, 1]:
        Temporal consistency of creator voice. Genuine creators get up to a
        +15% multiplicative boost on their effective engagement (research §2.4).

    opinion_comp  [0, 1]:
        Discourse / opinion comparison content. Above 0.5, adds a small
        positive bonus (up to +0.05) because opinion comparison supports
        healthy identity formation, unlike appearance comparison (research §2.3).
    """
    # 1. Passive-streak decay: shift weight from engagement to d+p
    decay_factor = PASSIVE_DECAY_RATE ** passive_streak   # in [0, 1]
    # engagement weight shrinks; the freed budget goes equally to d and p
    w_e = w["e"] * decay_factor
    freed = w["e"] - w_e                          # weight shed by engagement
    w_d = w["d"] + freed * 0.5
    w_p = w["p"] + freed * 0.5
    w_r = w["r"]

    # 2. Affinity bonus (user-trait match) + creator authenticity (both multiplicative)
    affinity_bonus = 0.20 * max(0.0, similarity)        # 0.20 if match, 0 if mismatch
    auth_bonus     = ACTIVE_ENGAGEMENT_BONUS * creator_authenticity        # 0–0.15 based on creator consistency
    e_effective = e * (1.0 + affinity_bonus + auth_bonus)

    # 3. Similarity mindset on risk
    r_effective = r
    if appearance_comp > 0.5:
        # similar creator mitigates risk; dissimilar amplifies it
        r_effective = r * (1.0 - similarity * 0.5)
        r_effective = max(0.0, r_effective)

    # 4. Active engagement bonus — content that drives comments/shares, not just watch time
    active_boost = ACTIVE_ENGAGEMENT_BONUS * active_engagement_ratio      # additive, 0–0.15

    # 5. Opinion comparison bonus — discourse content is identity-positive
    opinion_bonus = OPINION_COMPARISON_BONUS * opinion_comp if opinion_comp > 0.5 else 0.0

    return (
        (e_effective * w_e)
        + (d * w_d)
        + (p * w_p)
        - (r_effective * w_r)
        + active_boost
        + opinion_bonus
    )


def would_break_streak(recent_list: List[str], candidate_value: str, max_streak: int = 2) -> bool:
    if len(recent_list) < max_streak:
        return False
    tail = recent_list[-max_streak:]
    return all(x == candidate_value for x in tail)


# -----------------------------
# Algorithms
# -----------------------------

def rank_baseline(df: pd.DataFrame, k: int = 100) -> pd.DataFrame:
    return df.sort_values("engagement", ascending=False).head(k)


def build_prototype_feed(
    df: pd.DataFrame,
    weights: Dict[str, float],
    user_profile: dict,
    k: int = 100,
    recent_window: int = 10,
    max_streak: int = 2,
    cocoon_cap: int | None = None,
) -> pd.DataFrame:
    """
    Prototype algorithm using Gini coefficient for diversity
    and user profile attributes for similarity and engagement decay.

    user_profile keys
    -----------------
    passive_streak          int   (default 0)   consecutive passive views so far
    user_trait              str   (default '')   user's self-identified creator-trait preference
    novelty_tolerance       float (default 0.5) 0=low comfort with novelty, 1=high;
                                                scales serendipity_multiplier between 1.0–3.0
    boost_topics            list[str] (default [])
                                                UCRS: topics to amplify in ranking
    reduce_topics           list[str] (default [])
                                                UCRS: topics to exclude from feed entirely
    override_passive_history bool (default False)
                                                UCRS: treat passive_streak as 0 for this session
    """
    remaining = df.copy().reset_index(drop=True)
    feed_rows: List[dict] = []

    recent_topics: List[str] = []
    recent_channels: List[str] = []

    # Pre-extract all possible topics for Gini distribution tracking
    all_topics = sorted(list(remaining["topic"].unique()))

    # --- User profile extraction ---
    passive_streak  = user_profile.get("passive_streak", 0)
    user_trait      = user_profile.get("user_trait", "")
    boost_topics    = set(user_profile.get("boost_topics", []))
    reduce_topics   = set(user_profile.get("reduce_topics", []))
    override        = user_profile.get("override_passive_history", False)

    # UCRS: override_passive_history resets streak effect for this session
    passive_streak_eff = 0 if override else passive_streak

    # Novelty tolerance scales how aggressively serendipity is pushed
    # tolerance=0.0 → multiplier=1.0 (gentle), tolerance=1.0 → multiplier=3.0 (bold)
    novelty_tolerance      = float(user_profile.get("novelty_tolerance", 0.5))
    novelty_tolerance      = max(0.0, min(1.0, novelty_tolerance))  # clamp
    serendipity_multiplier = 2.0 * (0.5 + novelty_tolerance)        # range [1.0, 3.0]

    # --- Step 1: Age-differentiated protection ---
    # age_group: "13-15", "16-17", or None (adult/unset)
    age_group = user_profile.get("age_group", None)
    age_protection_factor = AGE_PROTECTION_FACTORS.get(age_group, 1.0)
    # Tighter streak cap for high-risk topics (13-15 → max 1 consecutive)
    age_streak_cap = 1 if age_group == "13-15" else max_streak

    # --- Step 4: Session duration fatigue protection ---
    session_posts_served = int(user_profile.get("session_posts_served", 0))
    session_cap = cocoon_cap if cocoon_cap is not None else SESSION_CAPS.get(age_group, 100)
    effective_k = max(0, min(k, session_cap - session_posts_served))

    # Escalating prosocial boost for fatigue (mirrors night_mode_settings pattern)
    weights = dict(weights)  # don't mutate caller's dict
    if session_posts_served > FATIGUE_ONSET:
        fatigue_factor = min(1.0, (session_posts_served - FATIGUE_ONSET) / float(FATIGUE_ONSET))
        fatigue_prosocial_boost = 0.08 * fatigue_factor * age_protection_factor
        weights["p"] = weights.get("p", 0.0) + fatigue_prosocial_boost
        weights["r"] = weights.get("r", 0.0) + (fatigue_prosocial_boost * 0.5)
        _total = sum(weights.values())
        if _total > 0:
            weights = {_k: _v / _total for _k, _v in weights.items()}

    # --- Step 3: Emotional valence tracking state ---
    valence_window_size = 8
    valence_history: List[float] = []
    negative_valence_index = 0.0

    # --- Step 5: Crisis re-routing state ---
    crisis_window_history: List[bool] = []
    CRISIS_TRIGGER_THRESHOLD = CRISIS_THRESHOLD
    crisis_signal_active = bool(user_profile.get("crisis_mode", False))

    # --- Step 6: Emotional amplification rabbit hole state ---
    emotional_amplification_streak = 0
    EMOTIONAL_STREAK_INTERRUPT = 2

    def _score_row(row, topic, d, passive_streak_eff):
        """Helper that reads optional new columns safely (default 0.0 for legacy data)."""
        creator_trait = getattr(row, "creator_trait", "")
        similarity    = 1.0 if creator_trait == user_trait else -1.0
        return score_parts(
            e=getattr(row, "engagement"),
            d=d,
            p=getattr(row, "prosocial"),
            r=getattr(row, "risk"),
            w=weights,
            passive_streak=passive_streak_eff,
            similarity=similarity,
            appearance_comp=getattr(row, "appearance_comparison", 0.0),
            active_engagement_ratio=getattr(row, "active_engagement_ratio", 0.0),
            opinion_comp=getattr(row, "opinion_comparison", 0.0),
            creator_authenticity=getattr(row, "creator_authenticity", 0.0),
        )

    for _ in range(effective_k):
        if remaining.empty:
            break

        window_topics   = recent_topics[-recent_window:]
        window_channels = recent_channels[-recent_window:]

        # Calculate base Gini across recent topics
        topic_counts = {t: 0 for t in all_topics}
        for t in window_topics:
            topic_counts[t] += 1
        base_gini = calculate_gini(list(topic_counts.values()))

        diversity_list: List[float] = []
        score_list: List[float] = []

        for row in remaining.itertuples(index=False):
            topic   = getattr(row, "topic")
            channel = getattr(row, "channel")

            # UCRS: hard-exclude reduce_topics
            if topic in reduce_topics:
                diversity_list.append(0.0)
                score_list.append(float("-inf"))
                continue

            # Step 2: High-risk topics use tighter age-differentiated streak cap
            topic_is_high_risk = (
                topic in HIGH_RISK_TOPICS
                or (getattr(row, "risk", 0.0) >= 0.7 and getattr(row, "appearance_comparison", 0.0) >= 0.6)
            )
            effective_streak_cap = age_streak_cap if topic_is_high_risk else max_streak

            if (
                would_break_streak(recent_topics, topic, max_streak=effective_streak_cap)
                or would_break_streak(recent_channels, channel, max_streak=max_streak)
            ):
                diversity_list.append(0.0)
                score_list.append(float("-inf"))
                continue

            # Gini Coefficient Diversity Score
            hypothetical_counts = dict(topic_counts)
            hypothetical_counts[topic] += 1
            new_gini = calculate_gini(list(hypothetical_counts.values()))

            d = (base_gini - new_gini) * serendipity_multiplier
            d = max(0.0, d + 0.1)

            # UCRS: amplify diversity score for boost_topics
            if topic in boost_topics:
                d *= 1.5

            # Step 6: Boost diversity of safe content when in emotional amplification rabbit hole
            row_risk = getattr(row, "risk", 0.0)
            row_eng  = getattr(row, "engagement", 0.0)
            if emotional_amplification_streak >= EMOTIONAL_STREAK_INTERRUPT and row_risk < 0.3:
                d = d * (1.0 + 0.5 * age_protection_factor)

            s = _score_row(row, topic, d, passive_streak_eff)

            # Step 3: Mood rebalancing when feed is trending emotionally negative
            if negative_valence_index > VALENCE_THRESHOLD:
                overage = negative_valence_index - VALENCE_THRESHOLD
                mood_rebalance_bonus = 0.25 * overage * age_protection_factor
                if getattr(row, "prosocial", 0) == 1:
                    s += mood_rebalance_bonus
                if row_risk > 0.5:
                    s -= mood_rebalance_bonus * 0.5

            # Step 5: Crisis re-routing — inject wellness, suppress further crisis content
            if crisis_signal_active:
                crisis_inject_bonus = 0.40 * age_protection_factor
                if getattr(row, "is_wellness_resource", 0):
                    s += crisis_inject_bonus
                elif getattr(row, "prosocial", 0) == 1 and row_risk < 0.2:
                    s += crisis_inject_bonus * 0.4
                if row_risk >= HIGH_RISK_THRESHOLD or topic in CRISIS_TOPICS:
                    s -= 0.50

            # Step 6: Penalize emotional amplification rabbit hole continuation
            if emotional_amplification_streak >= EMOTIONAL_STREAK_INTERRUPT:
                if row_eng > 0.6 and row_risk > 0.5:
                    s -= 0.30 * age_protection_factor

            diversity_list.append(d)
            score_list.append(s)

        remaining = remaining.copy()
        remaining["diversity"] = diversity_list
        remaining["score"]     = score_list

        if remaining["score"].max() == float("-inf"):
            # All items blocked by streak rule (or reduce_topics) — relax streak for one pick
            # Note: reduce_topics items remain at -inf even in fallback
            diversity_list = []
            score_list     = []
            for row in remaining.itertuples(index=False):
                topic = getattr(row, "topic")

                # UCRS: still respect hard exclusions in fallback
                if topic in reduce_topics:
                    diversity_list.append(0.0)
                    score_list.append(float("-inf"))
                    continue

                hypothetical_counts = dict(topic_counts)
                hypothetical_counts[topic] += 1
                new_gini = calculate_gini(list(hypothetical_counts.values()))
                d = max(0.0, (base_gini - new_gini) * serendipity_multiplier + 0.1)

                if topic in boost_topics:
                    d *= 1.5

                s = _score_row(row, topic, d, passive_streak_eff)
                diversity_list.append(d)
                score_list.append(s)

            remaining["diversity"] = diversity_list
            remaining["score"]     = score_list

        best_idx = remaining["score"].idxmax()
        best_row = remaining.loc[best_idx]

        feed_rows.append(best_row.to_dict())
        recent_topics.append(best_row["topic"])
        recent_channels.append(best_row["channel"])

        # Step 3: Update valence history for next iteration's mood rebalancing
        valence_history.append(float(best_row.get("risk", 0.0)))
        if len(valence_history) > valence_window_size:
            valence_history.pop(0)
        negative_valence_index = (
            sum(valence_history) / len(valence_history) if valence_history else 0.0
        )

        # Step 5: Update crisis window for next iteration
        _is_crisis_post = (
            best_row.get("topic", "") in CRISIS_TOPICS
            or float(best_row.get("risk", 0.0)) >= HIGH_RISK_THRESHOLD
        )
        crisis_window_history.append(_is_crisis_post)
        if len(crisis_window_history) > CRISIS_WINDOW:
            crisis_window_history.pop(0)
        crisis_signal_active = (
            sum(crisis_window_history) >= CRISIS_TRIGGER_THRESHOLD
            or bool(user_profile.get("crisis_mode", False))
        )

        # Step 6: Update emotional amplification streak for next iteration
        _is_amplification = (
            float(best_row.get("engagement", 0.0)) > 0.6
            and float(best_row.get("risk", 0.0)) > 0.5
        )
        emotional_amplification_streak = (
            emotional_amplification_streak + 1 if _is_amplification else 0
        )

        remaining = remaining.drop(index=best_idx).reset_index(drop=True)

    return pd.DataFrame(feed_rows)