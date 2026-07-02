# Passive consumption decay
PASSIVE_DECAY_RATE = 0.8

# Emotional valence threshold for mood rebalancing
VALENCE_THRESHOLD = 0.45

# Age-differentiated protection factors
AGE_PROTECTION_FACTORS: dict = {"13-15": 1.5, "16-17": 1.15, None: 1.0}

# Session post caps by age group
SESSION_CAPS: dict = {"13-15": 40, "16-17": 60, None: 100}

# Crisis detection window
CRISIS_WINDOW = 5
CRISIS_THRESHOLD = 2

# Night mode adjustments
NIGHT_RISK_BOOST = 0.05
NIGHT_PROSOCIAL_BOOST = 0.03
NIGHT_FEED_CAP = 15

# Scoring bonuses
ACTIVE_ENGAGEMENT_BONUS = 0.15
OPINION_COMPARISON_BONUS = 0.05

# Scroll count before session fatigue kicks in
FATIGUE_ONSET = 25

# Risk score above which content is treated as high-risk for crisis detection
HIGH_RISK_THRESHOLD = 0.8

# Narrative-saturation detector (appearance/body theme) — spec 2026-07-02
NARRATIVE_WINDOW = 6              # rolling window of served items
NARRATIVE_THRESHOLD = 4           # appearance-theme items in window to trigger (13-15 uses -1)
APPEARANCE_COMP_THRESHOLD = 0.5   # appearance_comparison at/above = appearance-theme
NARRATIVE_DAMP = 0.30             # score penalty for continuing the theme (x age factor)
NARRATIVE_DIVERSIFY = 0.20        # score bonus for safe off-theme content (x age factor)
# Appearance subset of HIGH_RISK_TOPICS; excludes crisis topics owned by Step 5.
APPEARANCE_TOPICS = frozenset({"body_image", "eating_disorder", "weight_loss", "appearance"})
