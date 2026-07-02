"""
Generates final science-fair charts from experiment summary results.
It loads: results/data/experiment_summary.csv
It saves PNG figures to: results/figures/
"""

from pathlib import Path
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# Config
# -----------------------------

DEFAULT_SUMMARY_PATH = "results/data/experiment_summary.csv"
DEFAULT_OUTDIR = "results/figures"

COL_PRESET = "preset"
COL_NIGHT_MODE = "night_mode"
COL_K = "k"

METRICS = {
    "prosocial_ratio": {
        "mean": "prosocial_ratio_mean",
        "std": "prosocial_ratio_std",
        "title": "Prosocial Ratio by Preset and Mode (Mean ± Std)",
        "ylabel": "Prosocial ratio",
        "filename": "01_prosocial_ratio.png",
    },
    "diversity_at_10": {
        "mean": "diversity_at_10_mean",
        "std": "diversity_at_10_std",
        "title": "Diversity@10 by Preset and Mode (Mean ± Std)",
        "ylabel": "Unique topics in top 10",
        "filename": "02_diversity_at10.png",
    },
    "max_topic_streak": {
        "mean": "max_topic_streak_mean",
        "std": "max_topic_streak_std",
        "title": "Max Topic Streak by Preset and Mode (Mean ± Std)",
        "ylabel": "Max consecutive topic streak",
        "filename": "03_max_topic_streak.png",
    },
    "overlap_ratio_top10": {
        "mean": "overlap_ratio_top10_mean",
        "std": "overlap_ratio_top10_std",
        "title": "Top-10 Overlap vs Engagement-Only Baseline (Mean ± Std)",
        "ylabel": "Overlap ratio (0–1)",
        "filename": "04_overlap_top10.png",
    },
}

# Higher-is-better direction for delta chart
METRIC_DIRECTIONS = {
    "prosocial_ratio": 1,
    "diversity_at_10": 1,
    "max_topic_streak": -1,
}

# Metrics to show in grouped baseline-vs-improved chart
GROUPED_METRICS = {
    "prosocial_ratio": {
        "mean": "prosocial_ratio_mean",
        "title": "Prosocial Ratio",
        "ylabel": "Ratio",
    },
    "diversity_at_10": {
        "mean": "diversity_at_10_mean",
        "title": "Diversity@10",
        "ylabel": "Unique topics in top 10",
    },
    "max_topic_streak": {
        "mean": "max_topic_streak_mean",
        "title": "Max Topic Streak (lower is better)",
        "ylabel": "Max consecutive topic streak",
    },
    "max_creator_streak": {
        "mean": "max_creator_streak_mean",
        "title": "Max Creator Streak (lower is better)",
        "ylabel": "Max consecutive creator streak",
    },
    "runtime_sec_per_100": {
        "mean": "runtime_sec_per_100_mean",
        "title": "Runtime per 100 (lower is better)",
        "ylabel": "Seconds per 100 posts",
    },
    "overlap_ratio_top10": {
        "mean": "overlap_ratio_top10_mean",
        "title": "Overlap Ratio Top 10",
        "ylabel": "Overlap ratio (0–1)",
    },
    "overlap_ratio_topk": {
        "mean": "overlap_ratio_topk_mean",
        "title": "Overlap Ratio Top k",
        "ylabel": "Overlap ratio (0–1)",
    },
    "pass_rate": {
        "mean": "pass_rate",
        "title": "Pass Rate",
        "ylabel": "Rate (0–1)",
    },
}

# -----------------------------
# Helpers
# -----------------------------


def ensure_outdir(outdir):
    """
    Create output directory if it does not exist.
    """
    os.makedirs(outdir, exist_ok=True)


def mode_label(value):
    """
    Normalize night_mode values into readable labels.
    """
    if isinstance(value, bool):
        if value:
            return "Night Mode ON"
        return "Night Mode OFF"

    s = str(value).strip().lower()
    if s in ["true", "1", "yes"]:
        return "Night Mode ON"
    if s in ["false", "0", "no"]:
        return "Night Mode OFF"
    return str(value)


def night_mode_bool(value):
    """
    Normalize night_mode values into strict booleans.
    """
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ["true", "1", "yes"]:
        return True
    if s in ["false", "0", "no"]:
        return False
    return None


def load_summary(path):
    """
    Load summary CSV and add combined labels for plotting.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Missing summary CSV: " + str(path))

    df = pd.read_csv(p)

    required = [COL_PRESET, COL_NIGHT_MODE]
    for c in required:
        if c not in df.columns:
            raise ValueError(
                "experiment_summary.csv missing required column: " + c)

    df["mode_label"] = df[COL_NIGHT_MODE].apply(mode_label)
    df["night_mode_bool"] = df[COL_NIGHT_MODE].apply(night_mode_bool)
    df["label"] = df[COL_PRESET].astype(
        str) + " / " + df["mode_label"].astype(str)
    return df


def validate_metric_columns(df):
    """
    Ensure required mean columns exist for configured metrics.
    """
    missing = []
    for _, info in METRICS.items():
        if info["mean"] not in df.columns:
            missing.append(info["mean"])
        # std is optional (graph will still render if missing)
    if len(missing) > 0:
        print("Missing expected mean columns:")
        for m in missing:
            print(" -", m)
        print("\nAvailable columns:")
        print(list(df.columns))
        raise ValueError(
            "Update METRICS column names to match your summary CSV.")


def bar_mean_std(df, mean_col, std_col, title, ylabel, out_path):
    """
    Simple bar chart with optional std error bars.
    """
    x = list(range(len(df)))
    y = df[mean_col].astype(float)

    yerr = None
    if std_col in df.columns:
        # Some std columns may be empty/NaN if only 1 run; handle safely
        yerr = df[std_col].fillna(0).astype(float)

    plt.figure()
    plt.bar(x, y, yerr=yerr, capsize=4)
    plt.xticks(x, df["label"], rotation=30, ha="right")
    plt.title(title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def delta_vs_baseline(df, metrics, out_path):
    """
    Diverging bar chart of improvement vs baseline.
    Improvement = (mean - baseline_mean) * direction.
    """
    # Build baseline lookup keyed by (night_mode, k if present)
    key_cols = ["night_mode_bool"]
    if COL_K in df.columns:
        key_cols.append(COL_K)

    baseline_df = df[df[COL_PRESET] == "baseline"].copy()
    if baseline_df.empty:
        raise ValueError("No baseline rows found (preset == 'baseline').")

    baseline_lookup = {}
    for _, row in baseline_df.iterrows():
        key = tuple(row[c] for c in key_cols)
        baseline_lookup[key] = row

    # Exclude baseline rows from comparisons
    comp_df = df[df[COL_PRESET] != "baseline"].copy().reset_index(drop=True)
    if comp_df.empty:
        raise ValueError("No non-baseline rows found to compare.")

    # Build improvement table
    records = []
    for _, row in comp_df.iterrows():
        key = tuple(row[c] for c in key_cols)
        base = baseline_lookup.get(key)
        if base is None:
            continue
        rec = {"label": row["label"]}
        for metric_key, info in metrics.items():
            mean_col = info["mean"]
            if mean_col not in df.columns:
                continue
            direction = METRIC_DIRECTIONS.get(metric_key, 1)
            rec[metric_key] = (
                float(row[mean_col]) - float(base[mean_col])
            ) * direction
        records.append(rec)

    if not records:
        raise ValueError("No matching baseline rows for comparisons.")

    imp = pd.DataFrame(records)

    # Plot: one subplot per metric
    plot_metrics = [m for m in metrics.keys() if m in imp.columns]
    n = len(plot_metrics)
    if n == 0:
        raise ValueError("No metrics available for delta chart.")

    fig, axes = plt.subplots(n, 1, figsize=(8, 2.4 * n), sharex=False)
    if n == 1:
        axes = [axes]

    for ax, metric_key in zip(axes, plot_metrics):
        vals = imp[metric_key].astype(float)
        labels = imp["label"].tolist()
        y = list(range(len(labels)))

        ax.barh(y, vals, color="#1f77b4")
        ax.axvline(0, color="black", linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_title(
            f"Improvement vs Baseline: {metric_key.replace('_', ' ').title()}"
        )
        ax.set_xlabel("Improvement (positive is better)")

    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def grouped_vs_baseline(df, metrics, out_path):
    """
    Grouped bar charts showing baseline vs improved (night off/on) for each metric.
    Baseline uses night_mode OFF.
    """
    df_use = df.copy().reset_index(drop=True)

    baseline_all = df_use[df_use[COL_PRESET] == "baseline"]
    baseline = baseline_all[baseline_all["night_mode_bool"] == False]
    if baseline.empty:
        # Fallback if night_mode_bool couldn't be parsed
        baseline = baseline_all[
            baseline_all[COL_NIGHT_MODE].astype(str).str.strip().str.lower().isin(
                ["false", "0", "no"]
            )
        ]
    if baseline.empty and not baseline_all.empty:
        # Last-resort: use any baseline row to avoid crashing
        baseline = baseline_all
    if baseline.empty:
        raise ValueError("No baseline rows found (preset == 'baseline').")

    # One baseline row (per k, if present)
    baseline_row = baseline.iloc[0]

    # Only improved presets
    comp_df = df_use[df_use[COL_PRESET] != "baseline"].copy()
    presets = sorted(comp_df[COL_PRESET].unique())

    # Build lookup for improved modes (bool first, then string fallback)
    if "night_mode_bool" in comp_df.columns:
        nm_bool = comp_df["night_mode_bool"]
        improved_off = comp_df[nm_bool == False]
        improved_on = comp_df[nm_bool == True]
    else:
        improved_off = comp_df.iloc[0:0]
        improved_on = comp_df.iloc[0:0]

    if improved_off.empty or improved_on.empty:
        nm_str = comp_df[COL_NIGHT_MODE].astype(str).str.strip().str.lower()
        improved_off = comp_df[nm_str.isin(["false", "0", "no"])]
        improved_on = comp_df[nm_str.isin(["true", "1", "yes"])]

    # Subplots: 2 columns
    plot_metrics = [m for m in metrics.keys() if metrics[m]
                    ["mean"] in df_use.columns]
    n = len(plot_metrics)
    if n == 0:
        raise ValueError("No metrics available for grouped chart.")

    ncols = 2
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 3.3 * nrows))
    axes = axes.flatten()

    bar_w = 0.22
    x = list(range(len(presets)))

    for i, metric_key in enumerate(plot_metrics):
        ax = axes[i]
        mean_col = metrics[metric_key]["mean"]

        base_vals = [float(baseline_row[mean_col]) for _ in presets]
        off_vals = []
        on_vals = []
        for p in presets:
            row_off = improved_off[improved_off[COL_PRESET] == p]
            row_on = improved_on[improved_on[COL_PRESET] == p]
            off_vals.append(
                float(row_off.iloc[0][mean_col]) if not row_off.empty else float("nan"))
            on_vals.append(
                float(row_on.iloc[0][mean_col]) if not row_on.empty else float("nan"))

        ax.bar(
            [v - bar_w for v in x],
            base_vals,
            width=bar_w,
            label="Baseline",
            color="#bfe2eaff",
        )
        ax.bar(
            x,
            off_vals,
            width=bar_w,
            label="Improved (Night OFF)",
            color="#3f9bc7",
        )
        ax.bar(
            [v + bar_w for v in x],
            on_vals,
            width=bar_w,
            label="Improved (Night ON)",
            color="#2f3b7a",
        )

        ax.set_xticks(x)
        ax.set_xticklabels(presets, rotation=20, ha="right")
        ax.set_title(metrics[metric_key]["title"])
        ax.set_ylabel(metrics[metric_key]["ylabel"])

    # Remove unused axes
    for j in range(n, len(axes)):
        fig.delaxes(axes[j])

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_path, dpi=200)
    plt.close()

    return {
        "baseline_rows": int(len(baseline)),
        "improved_off_rows": int(len(improved_off)),
        "improved_on_rows": int(len(improved_on)),
    }


# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default=DEFAULT_SUMMARY_PATH)
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    args = ap.parse_args()

    ensure_outdir(args.outdir)

    df = load_summary(args.summary)
    print("Summary columns:")
    print(list(df.columns))

    validate_metric_columns(df)

    # Sort for consistent display (preset first, then night_mode)
    if COL_K in df.columns:
        df = df.sort_values([COL_PRESET, COL_NIGHT_MODE,
                            COL_K]).reset_index(drop=True)
    else:
        df = df.sort_values([COL_PRESET, COL_NIGHT_MODE]
                            ).reset_index(drop=True)

    # Create all charts in METRICS
    for key in METRICS.keys():
        info = METRICS[key]
        out_path = os.path.join(args.outdir, info["filename"])
        bar_mean_std(
            df=df,
            mean_col=info["mean"],
            std_col=info["std"],
            title=info["title"],
            ylabel=info["ylabel"],
            out_path=out_path,
        )
        print("Saved", out_path)

    # Delta vs baseline chart (improvement)
    delta_out = os.path.join(args.outdir, "05_delta_vs_baseline.png")
    delta_vs_baseline(df, METRICS, delta_out)
    print("Saved", delta_out)

    # Grouped baseline vs improved chart (all metrics)
    grouped_out = os.path.join(args.outdir, "06_grouped_vs_baseline.png")
    grouped_counts = grouped_vs_baseline(df, GROUPED_METRICS, grouped_out)
    print("Saved", grouped_out)
    print("Grouped chart rows:", grouped_counts)

    print("\nDone. Figures saved in:")
    print(args.outdir)

    cols = [COL_PRESET, COL_NIGHT_MODE]
    if COL_K in df.columns:
        cols.append(COL_K)

    for key in METRICS.keys():
        cols.append(METRICS[key]["mean"])

    cols = [c for c in cols if c in df.columns]
    print("\nKey summary values (means):")
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
