"""
Evaluation metrics for the Healthy Feed Algorithm project.

Metrics:
- Diversity@k: number of unique topics in the top k posts
- Max streak: longest consecutive streak of the same value in a column
- Prosocial ratio: fraction of posts labeled prosocial
"""

import pandas as pd


# -----------------------------
# Diversity
# -----------------------------

def diversity_at_k(feed, k=10, topic_col="topic"):
    """
    Diversity@k:
    Counts how many unique topics appear in the top k recommended posts.
    """
    if feed is None or len(feed) == 0:
        return 0
    if topic_col not in feed.columns:
        raise ValueError(f"Missing column '{topic_col}' in feed")

    k = min(k, len(feed))
    return int(feed.head(k)[topic_col].nunique(dropna=True))


# -----------------------------
# Streaks / repetition caps
# -----------------------------

def max_streak(feed, col):
    """
    Max streak:
    Finds the longest consecutive streak of the same value in a column.
    """
    if feed is None or len(feed) == 0:
        return 0
    if col not in feed.columns:
        raise ValueError(f"Missing column '{col}' in feed")

    vals = feed[col].astype(str).tolist()

    best = 1
    cur = 1

    for i in range(1, len(vals)):
        if vals[i] == vals[i - 1]:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 1

    return best


# -----------------------------
# Prosocial ratio
# -----------------------------

def prosocial_ratio(feed, prosocial_col="prosocial"):
    """
    Prosocial ratio:
    Calculates the fraction of recommendations labeled prosocial (0/1).
    """
    if feed is None or len(feed) == 0:
        return 0.0
    if prosocial_col not in feed.columns:
        raise ValueError(f"Missing column '{prosocial_col}' in feed")

    vals = pd.to_numeric(feed[prosocial_col], errors="coerce").fillna(0)
    vals = vals.clip(0, 1)

    return float(vals.mean())


# -----------------------------
# Overlap vs baseline (similarity)
# -----------------------------

def overlap_ratio(ids_a, ids_b, top_n=10):
    """
    Overlap ratio:
    Looks at the first top_n IDs from two feeds and returns:
    (# of shared IDs) / top_n

    Example: 0.3 means 3 of the top 10 are the same.
    """
    if top_n <= 0:
        return 0.0

    set_a = set(ids_a[:top_n])
    set_b = set(ids_b[:top_n])
    return len(set_a & set_b) / float(top_n)


def jaccard_similarity(ids_a, ids_b, top_n=10):
    """
    Jaccard similarity:
    Another similarity score:
    |A ∩ B| / |A ∪ B|

    Higher = more similar overall.
    0.0 = no overlap, 1.0 = identical sets.
    """
    set_a = set(ids_a[:top_n])
    set_b = set(ids_b[:top_n])
    union_size = len(set_a | set_b)
    if union_size == 0:
        return 0.0
    return len(set_a & set_b) / float(union_size)

def gini_distribution(feed, col, all_categories):
    """
    Calculates the Gini coefficient for a specified column's distribution in the feed.
    """
    import numpy as np
    if feed is None or len(feed) == 0:
        return 0.0
    if col not in feed.columns:
        raise ValueError(f"Missing column '{col}' in feed")

    target_counts = {c: 0 for c in all_categories}
    for val in feed[col].astype(str):
        if val in target_counts:
            target_counts[val] += 1
            
    arr = np.sort(np.array(list(target_counts.values()), dtype=float))
    n = len(arr)
    if np.sum(arr) == 0:
        return 0.0
    index = np.arange(1, n + 1)
    return (np.sum((2 * index - n - 1) * arr)) / (n * np.sum(arr))


def feed_valence_index(feed, risk_col="risk"):
    """
    Mean risk score across the feed. Proxy for negative emotional tone.

    Range: 0.0 (no negative valence) to 1.0 (maximally negative).
    Research-informed targets:
      - 13-15 year old feeds: < 0.20
      - 16-17 year old feeds: < 0.30
      - Adult feeds:          < 0.40
    """
    import pandas as pd
    if feed is None or len(feed) == 0:
        return 0.0
    if risk_col not in feed.columns:
        raise ValueError(f"Missing column '{risk_col}' in feed")
    vals = pd.to_numeric(feed[risk_col], errors="coerce").fillna(0).clip(0, 1)
    return float(vals.mean())