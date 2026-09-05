"""
Main entry point for the Healthy Feed Algorithm project!
"""

from pathlib import Path
import pandas as pd

from core.algorithm import get_mode_settings, add_engagement, build_prototype_feed
from core.metrics import diversity_at_k, max_streak, prosocial_ratio


# -----------------------------
# Config
# -----------------------------

DATA_PATH = Path(__file__).parent.parent / "datasets" / "processed_dataset.csv"

PRESET = "entertainment"
K_DEFAULT = 100
RECENT_WINDOW = 10
NIGHT_MODE = True

SHOW_COLS = ["video_id", "topic", "channel", "prosocial",
             "risk", "engagement", "diversity", "score"]


# -----------------------------
# Demo helpers
# -----------------------------

def print_metrics(feed, label):
    """
    Print metrics for a generated feed.
    """
    d10 = diversity_at_k(feed, k=10, topic_col="topic")
    topic_streak = max_streak(feed, "topic")
    creator_streak = max_streak(feed, "channel")
    p_ratio = prosocial_ratio(feed, prosocial_col="prosocial")

    print(f"Metrics ({label})\n")
    print("diversity@10 =", d10, "(target >= 4)")
    print("max topic streak =", topic_streak, "(target <= 2)")
    print("max creator streak =", creator_streak, "(target <= 2)")
    print("prosocial ratio =", round(p_ratio, 3), "(target >= 0.25)")


def run_demo(df, preset, night_mode):
    """
    Build a feed and print a preview + metrics.
    """
    weights, k = get_mode_settings(
        preset, night_mode=night_mode, k_default=K_DEFAULT)
    label = f"{preset} ({'night mode' if night_mode else 'normal'}, k={k})"
    feed = build_prototype_feed(
        df, weights=weights, k=k, recent_window=RECENT_WINDOW,
        user_profile={"age_group": None})

    print(f"{label} top 10:")
    print(feed[SHOW_COLS].head(10))

    print("\nPreset:", PRESET, "| Night mode:", NIGHT_MODE, "| k:", k)
    print_metrics(feed, label)


# -----------------------------
# Main
# -----------------------------

def main():
    # Load dataset
    df = pd.read_csv(DATA_PATH)
    print("Loaded:", df.shape)

    # Ensure engagement exists (needed for scoring)
    df, max_views = add_engagement(df)
    print("max_views:", max_views)

    # Run demo
    run_demo(df, PRESET, night_mode=NIGHT_MODE)


if __name__ == "__main__":
    main()
