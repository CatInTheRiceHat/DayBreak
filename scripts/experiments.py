"""
Runs multiple simulated sessions of the prototype feed and compares each run to an engagement-only baseline.
It records design metrics + baseline overlap for every run, then saves raw results and summary stats to CSV files.
Outputs: results/experiment_raw.csv and results/experiment_summary.csv.

Usage:
    python experiments.py --n_sessions 10 --dataset datasets/processed_dataset.csv
"""

from pathlib import Path
import os
import time
import argparse
import pandas as pd

from core.algorithm import (
    validate_and_clean,
    get_mode_settings,
    add_engagement,
    rank_baseline,
    build_prototype_feed
)

from core.metrics import (
    diversity_at_k,
    max_streak,
    prosocial_ratio,
    overlap_ratio,
)

# -----------------------------
# Design Criteria Targets
# -----------------------------

TARGET_DIVERSITY_AT_10 = 4
TARGET_MAX_STREAK = 2
TARGET_PROSOCIAL_RATIO = 0.25
TARGET_RUNTIME_SEC_PER_100 = 2.0

# -----------------------------
# Config
# -----------------------------

PRESETS = ["entertainment", "inspiration", "learning"]

ID_COL = "video_id"
TOPIC_COL = "topic"
CREATOR_COL = "channel"
PROSOCIAL_COL = "prosocial"

K_DEFAULT = 100


# -----------------------------
# Helpers
# -----------------------------

def feed_ids(feed, id_col=ID_COL):
    """
    Convert a feed DataFrame into a list of IDs for overlap checking.
    """
    if feed is None or len(feed) == 0:
        return []
    if id_col not in feed.columns:
        raise ValueError(f"Feed missing id column '{id_col}'.")
    return feed[id_col].astype(str).tolist()


def runtime_per_100(runtime_sec, k):
    """
    Scale runtime to seconds per 100 posts so k=15 and k=100 compare fairly.
    """
    if k <= 0:
        return float("inf")
    return runtime_sec * (100.0 / float(k))


# -----------------------------
# One Trial
# -----------------------------

def run_one(df_seed, preset, night_mode, seed, recent_window, overlap_topn):
    """
    One trial:
    - Build prototype feed (preset + night_mode)
    - Build baseline feed (engagement-only) using SAME k for fair overlap
    - Compute metrics + pass/fail + overlap
    """
    weights, k = get_mode_settings(
        preset=preset, night_mode=night_mode, k_default=K_DEFAULT)

    # Prototype feed (timed)
    t0 = time.perf_counter()
    proto_feed = build_prototype_feed(
        df_seed, weights=weights, k=k, recent_window=recent_window)
    t1 = time.perf_counter()

    t_sec = float(t1 - t0)
    t_per_100 = runtime_per_100(t_sec, k)

    # Baseline feed (timed)
    t0_base = time.perf_counter()
    base_feed = rank_baseline(df_seed, k=k).reset_index(drop=True)
    t1_base = time.perf_counter()
    t_sec_base = float(t1_base - t0_base)
    t_per_100_base = runtime_per_100(t_sec_base, k)

    # Metrics
    d10 = diversity_at_k(proto_feed, k=10, topic_col=TOPIC_COL)
    topic_streak = max_streak(proto_feed, TOPIC_COL)
    creator_streak = max_streak(proto_feed, CREATOR_COL)
    psr = prosocial_ratio(proto_feed, prosocial_col=PROSOCIAL_COL)

    # Pass/fail checks
    pass_div = (d10 >= TARGET_DIVERSITY_AT_10)
    pass_topic = (topic_streak <= TARGET_MAX_STREAK)
    pass_creator = (creator_streak <= TARGET_MAX_STREAK)
    pass_prosocial = (psr >= TARGET_PROSOCIAL_RATIO)
    pass_runtime = (t_per_100 <= TARGET_RUNTIME_SEC_PER_100)
    overall_pass = all([pass_div, pass_topic, pass_creator,
                       pass_prosocial, pass_runtime])

    # Overlap vs baseline
    proto_ids = feed_ids(proto_feed, ID_COL)
    base_ids = feed_ids(base_feed, ID_COL)

    overlap10 = overlap_ratio(proto_ids, base_ids, top_n=overlap_topn)
    overlapk = overlap_ratio(proto_ids, base_ids, top_n=min(
        k, len(proto_ids), len(base_ids)))

    # Baseline metrics
    base_d10 = diversity_at_k(base_feed, k=10, topic_col=TOPIC_COL)
    base_topic_streak = max_streak(base_feed, TOPIC_COL)
    base_creator_streak = max_streak(base_feed, CREATOR_COL)
    base_psr = prosocial_ratio(base_feed, prosocial_col=PROSOCIAL_COL)

    base_pass_div = (base_d10 >= TARGET_DIVERSITY_AT_10)
    base_pass_topic = (base_topic_streak <= TARGET_MAX_STREAK)
    base_pass_creator = (base_creator_streak <= TARGET_MAX_STREAK)
    base_pass_prosocial = (base_psr >= TARGET_PROSOCIAL_RATIO)
    base_pass_runtime = (t_per_100_base <= TARGET_RUNTIME_SEC_PER_100)
    base_overall_pass = all([
        base_pass_div,
        base_pass_topic,
        base_pass_creator,
        base_pass_prosocial,
        base_pass_runtime,
    ])

    base_overlap10 = overlap_ratio(base_ids, base_ids, top_n=overlap_topn)
    base_overlapk = overlap_ratio(
        base_ids, base_ids, top_n=min(k, len(base_ids))
    )

    proto_row = {
        "preset": preset,
        "night_mode": night_mode,
        "seed": seed,
        "k": k,
        "diversity_at_10": d10,
        "max_topic_streak": topic_streak,
        "max_creator_streak": creator_streak,
        "prosocial_ratio": psr,
        "runtime_sec": t_sec,
        "runtime_sec_per_100": t_per_100,
        "pass_diversity": pass_div,
        "pass_topic_streak": pass_topic,
        "pass_creator_streak": pass_creator,
        "pass_prosocial": pass_prosocial,
        "pass_runtime": pass_runtime,
        "overall_pass": overall_pass,
        "overlap_ratio_top10": overlap10,
        "overlap_ratio_topk": overlapk,
    }

    base_row = {
        "preset": "baseline",
        "night_mode": night_mode,
        "seed": seed,
        "k": k,
        "diversity_at_10": base_d10,
        "max_topic_streak": base_topic_streak,
        "max_creator_streak": base_creator_streak,
        "prosocial_ratio": base_psr,
        "runtime_sec": t_sec_base,
        "runtime_sec_per_100": t_per_100_base,
        "pass_diversity": base_pass_div,
        "pass_topic_streak": base_pass_topic,
        "pass_creator_streak": base_pass_creator,
        "pass_prosocial": base_pass_prosocial,
        "pass_runtime": base_pass_runtime,
        "overall_pass": base_overall_pass,
        "overlap_ratio_top10": base_overlap10,
        "overlap_ratio_topk": base_overlapk,
    }

    return [proto_row, base_row]


# -----------------------------
# Summary
# -----------------------------

def summarize(df_raw):
    """
    Grouped mean/std/min/max + pass_rate per preset/mode/k.
    pass_rate is the average of overall_pass (True=1, False=0).
    """
    group_cols = ["preset", "night_mode", "k"]

    metric_cols = [
        "diversity_at_10",
        "max_topic_streak",
        "max_creator_streak",
        "prosocial_ratio",
        "runtime_sec_per_100",
        "overlap_ratio_top10",
        "overlap_ratio_topk",
    ]

    agg = {c: ["mean", "std", "min", "max"] for c in metric_cols}
    agg["overall_pass"] = ["mean"]

    df_sum = df_raw.groupby(group_cols).agg(agg).reset_index()

    # Flatten multi-index columns -> "metric_mean", "metric_std", ...
    df_sum.columns = [
        col[0] if col[1] == "" else f"{col[0]}_{col[1]}"
        for col in df_sum.columns.to_flat_index()
    ]

    if "overall_pass_mean" in df_sum.columns:
        df_sum = df_sum.rename(columns={"overall_pass_mean": "pass_rate"})

    return df_sum


# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="datasets/shorts_dataset_tagged.csv")
    ap.add_argument("--outdir", default="results/data")
    ap.add_argument("--n_sessions", type=int, default=10)  # seeds 0..n-1
    ap.add_argument("--recent_window", type=int, default=10)
    ap.add_argument("--overlap_topn", type=int, default=10)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load + clean + add engagement
    df = pd.read_csv(Path(args.dataset))
    df = validate_and_clean(df)
    df, _ = add_engagement(df)

    rows = []

    for seed in range(args.n_sessions):
        # Shuffle per seed (this is your "simulated session" randomness)
        df_seed = df.sample(frac=1, random_state=seed).reset_index(drop=True)

        for preset in PRESETS:
            for night_mode in [False, True]:
                rows.extend(
                    run_one(
                        df_seed=df_seed,
                        preset=preset,
                        night_mode=night_mode,
                        seed=seed,
                        recent_window=args.recent_window,
                        overlap_topn=args.overlap_topn,
                    )
                )

    df_raw = pd.DataFrame(rows)
    df_sum = summarize(df_raw)

    raw_path = os.path.join(args.outdir, "experiment_raw.csv")
    sum_path = os.path.join(args.outdir, "experiment_summary.csv")
    df_raw.to_csv(raw_path, index=False)
    df_sum.to_csv(sum_path, index=False)

    print("\nSaved:")
    print(" -", raw_path)
    print(" -", sum_path)

    print("\nPass rates:")
    print(df_sum[["preset", "night_mode", "k",
          "pass_rate"]].to_string(index=False))


if __name__ == "__main__":
    main()
