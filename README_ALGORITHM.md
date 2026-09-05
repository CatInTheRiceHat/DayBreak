# Chrysalis: Core Algorithm Logic

This document consolidates the key mathematical formulas and ranking functions used within the `algorithm.py` Recommender System engine. This reference is designed for external UX/UI and Design firms (e.g., Flames.blue) to map visual feedback systems and transparency tags accurately to the underlying mathematics.

---

## 1. The Passive Consumption Decay

**Purpose**: To detect and forcefully interrupt infinite doomscrolling.

**Mechanic**: If a user consumes $N$ consecutive videos passively (without explicit engagement triggers like liking, sharing, or tapping into the comments), the baseline engagement potential weight ($W_e$) is algorithmically decayed.

### Equation

Let $W_e$ be the baseline engagement weight (typically ~0.55).
Let $N_{passive}$ be the current consecutive count of passively consumed feeds (the "passive streak").
Let $\text{Decay Rate}$ = 0.8.

The effective engagement weight $W_e'$ is calculated as:

$$ W_e' = W_e \times (\text{Decay Rate})^{N_{passive}} $$

### Code Implementation (`algorithm.py: score_parts`)

```python
# Decay Function
decay_rate = 0.8
e_weight = w["e"] * (decay_rate ** passive_streak)
```

*UI Impact: As the passive streak increases, $W_e'$ approaches zero, forcing the algorithm to aggressively prioritize high-diversity (Serendipity) or highly Prosocial content to break the loop.*

---

## 2. The Similarity Mindset / Upward Comparison Modifier

**Purpose**: To protect youth from upward comparison envy (e.g., body image issues or wealth gaps) by neutralizing highly "idealized" content if it clashes with the user's demographic traits.

### Equation

Let $r$ be the baseline risk score of the video (0 to 1).
Let $C_{appearance}$ be the algorithm's calculation of "appearance comparison triggers" within the video (0 to 1).
Let $S$ be the Similarity Coefficient between the Creator and the User. If they share a demographic trait, $S = 1$. If they differ, $S = -1$.

If $C_{appearance} > 0.5$:

$$ R_{effective} = r \times (1 - S) $$

### Code Implementation (`algorithm.py: score_parts`)

```python
r_effective = r
if appearance_comp > 0.5:
    # If similar (1), risk is mitigated (1 - 1 = 0).
    # If not similar (-1), risk is doubled (1 - -1 = 2).
    r_effective = r * (1 - similarity)
    r_effective = max(0.0, r_effective)
```

*UI Impact: When connected to the UI's "Similarity Mindset Mod" slider, increasing the weight punishes $R_{effective}$ harshly. A video featuring high appearance ideals from an unrelatable creator ($S=-1$) will dramatically lower its final recommendation score.*

---

## 3. The Gini Coefficient (Serendipity / Diversity Engine)

**Purpose**: To prevent restrictive "Filter Bubbles" by forcing mathematical content equality.

### Equation

The platform evaluates the rolling history of topics ($N_{recent} = 10$). The Gini coefficient ($G$) measures the inequality of this distribution. Lower values indicate higher diversity.

When considering a new video candidate ($V_{new}$):

$$ \Delta G = G_{current} - G_{hypothetical\_with\_V} $$

### Code Implementation

```python
def calculate_gini(distribution: List[int]) -> float:
    if not distribution or sum(distribution) == 0:
        return 0.0
    arr = np.sort(np.array(distribution, dtype=float))
    n = len(arr)
    index = np.arange(1, n + 1)
    return (np.sum((2 * index - n - 1) * arr)) / (n * np.sum(arr))

# Diversity Score (d) calculation:
d = (base_gini - new_gini) * serendipity_multiplier
```

*UI Impact: The UI's "Serendipity" slider acts as the final multiplier for $d$. Higher Serendipity artificially inflates the value of videos that break the user out of their filter bubble.*

---

## 4. Active Engagement Bonus

**Purpose**: Reward content that provokes active responses (comments, shares) rather
than passive silent completion — the fundamental distinction in research §2.1.

### Equation

Let $R_{active}$ be the content's historical active engagement ratio (comments + shares / total views), normalized to $[0, 1]$.

$$ \text{Score} += 0.15 \times R_{active} $$

### Code Implementation

```python
# 4. Active engagement bonus
active_boost = 0.15 * active_engagement_ratio      # additive, 0–0.15
```

*UI Impact: Content that sparks conversation scores up to +0.15 higher than identical content that only gets passive views. As passive_streak grows, this bonus becomes increasingly important for item selection.*

---

## 5. Creator Authenticity Multiplier

**Purpose**: Reward creators with temporal consistency in voice and style; penalize algorithmic trend-chasers (research §2.4).

### Equation

Let $A$ be the creator's authenticity score $\in [0, 1]$ (1 = highly consistent, 0 = volatile trend-chaser).

$$ e_{effective} = e_{base} \times (1 + \text{affinity\_bonus} + 0.15 \times A) $$

### Code Implementation

```python
# 2. Affinity bonus + creator authenticity (both multiplicative)
auth_bonus  = 0.15 * creator_authenticity        # 0–0.15 based on creator consistency
e_effective = e * (1.0 + affinity_bonus + auth_bonus)
```

*UI Impact: Genuine creators get up to a +15% boost on their effective engagement score. This surfaces stable authentic voices over viral chameleons optimizing for trending formats.*

---

## 6. Opinion Comparison Bonus

**Purpose**: Distinguish between psychologically harmful *appearance/ability* comparisons (penalized via risk) and psychologically beneficial *opinion/discourse* comparisons (rewarded) — research §2.3.

### Equation

Let $C_{opinion}$ be the opinion comparison score $\in [0, 1]$.

If $C_{opinion} > 0.5$:

$$ \text{Score} += 0.05 \times C_{opinion} $$

### Code Implementation

```python
# 5. Opinion comparison bonus — discourse content is identity-positive
opinion_bonus = 0.05 * opinion_comp if opinion_comp > 0.5 else 0.0
```

*UI Impact: Discussion content, debate videos, and civic discourse get a small positive nudge. This is intentionally modest (max +0.05) to complement — not override — the diversity and prosocial signals.*

---

## 7. UCRS Control Keys (`user_profile` dict)

**Purpose**: Implement a lightweight User-Controllable Recommender System allowing users to directly manipulate feed composition in real time (research §2.5).

| Key | Type | Default | Effect |
|---|---|---|---|
| `passive_streak` | int | 0 | Consecutive passive views — drives engagement weight decay |
| `user_trait` | str | `""` | Preferred creator trait — drives affinity bonus + risk mitigation |
| `novelty_tolerance` | float 0–1 | 0.5 | Scales `serendipity_multiplier`: `2.0 × (0.5 + tol)` → range [1.0, 3.0] |
| `boost_topics` | list[str] | `[]` | Named topics get their diversity score multiplied by 1.5 |
| `reduce_topics` | list[str] | `[]` | Named topics are excluded from the feed entirely (score = −∞) |
| `override_passive_history` | bool | False | When `True`, treats `passive_streak` as 0 — resets doomscrolling decay for the session |

### Code Implementation

```python
boost_topics    = set(user_profile.get("boost_topics", []))
reduce_topics   = set(user_profile.get("reduce_topics", []))
override        = user_profile.get("override_passive_history", False)
passive_streak_eff = 0 if override else passive_streak
novelty_tolerance  = float(user_profile.get("novelty_tolerance", 0.5))
serendipity_multiplier = 2.0 * (0.5 + novelty_tolerance)
```

*UI Impact: Maps directly to physical UI controls — topic sliders for boost/reduce, a "Reset My History" button for override, and a Serendipity dial for novelty tolerance.*
