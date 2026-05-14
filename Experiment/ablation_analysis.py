"""
Ablation study analysis for Transportation Science paper.
Reads CSVs from results_ablation_csv/ and produces figures + LaTeX table.

Run: python Experiment/ablation_analysis.py
Output: Experiment/figures/*.pdf  and  Experiment/ablation_table.tex
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
EXPERIMENT_PATH = Path(__file__).resolve().parent
CSV_ROOT = EXPERIMENT_PATH / "results_ablation_csv"
FIGURES_DIR = EXPERIMENT_PATH / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# ── Display names and order ────────────────────────────────────────────────
EXPERIMENTS = [
    ("ablation_origin", "Gaseline"),
    ("ablation_wo_e",   "w/o Exploration"),
    ("ablation_wo_ws",  "w/o Warm-start"),
    ("ablation_all_e",  "Standalone"),
    ("ablation_all_g",  "Greedy"),
]
EXP_KEYS   = [k for k, _ in EXPERIMENTS]
EXP_LABELS = {k: v for k, v in EXPERIMENTS}

# Consistent color palette across all figures
PALETTE = {
    "ablation_origin": "#1f77b4",   # blue
    "ablation_wo_e":   "#ff7f0e",   # orange
    "ablation_wo_ws":  "#2ca02c",   # green
    "ablation_all_e":  "#d62728",   # red
    "ablation_all_g":  "#9467bd",   # purple
}

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "legend.fontsize": 10,
    "figure.dpi": 150,
})


# ── Data loading ───────────────────────────────────────────────────────────

def load_table(table: str) -> pd.DataFrame:
    frames = []
    for key, _ in EXPERIMENTS:
        path = CSV_ROOT / key / f"{table}.csv"
        if path.exists():
            frames.append(pd.read_csv(path))
        else:
            print(f"  [Warning] missing: {path}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── Figure 1: Convergence curves ───────────────────────────────────────────

def fig_convergence(history: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for key in EXP_KEYS:
        df = history[history["experiment"] == key].copy()
        if df.empty:
            continue
        df = df.sort_values("runningtime")
        df["global_best"] = df["score"].cummin()
        # Step curve: each point holds until the next improvement
        ax.step(df["runningtime"], df["global_best"],
                where="post",
                label=EXP_LABELS[key],
                color=PALETTE[key],
                linewidth=1.5)

    ax.set_title("Convergence History")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Best Score")
    ax.set_xlim(0, 36000)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(7200))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out = FIGURES_DIR / "convergence.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


# ── Figure 2: Improvement rate per hour ────────────────────────────────────

def fig_improvement_rate(impr: pd.DataFrame):
    bins = np.arange(0, 36001, 3600)
    bin_labels = [f"{int(b/3600)}-{int(b/3600)+1}h" for b in bins[:-1]]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    n = len(EXP_KEYS)
    width = 0.8 / n
    x = np.arange(len(bin_labels))

    for i, key in enumerate(EXP_KEYS):
        df = impr[impr["experiment"] == key]
        counts = pd.cut(df["recording_time"], bins=bins, right=True).value_counts().sort_index()
        ax.bar(x + (i - n/2 + 0.5) * width, counts.values,
               width=width,
               label=EXP_LABELS[key],
               color=PALETTE[key],
               alpha=0.85)

    ax.set_xlabel("Time window")
    ax.set_ylabel("Number of global-best improvements")
    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels, rotation=30, ha="right")
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out = FIGURES_DIR / "improvement_rate.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


# ── Figure 3: Algorithm contribution (survivor_stats) ──────────────────────

def fig_survivor(survivor: pd.DataFrame):
    # Normalise algo names to short labels
    def shorten(name):
        name = str(name)
        if "HGS" in name:      return "HGS"
        if "etaMax1" in name or "stoppingTime18000" in name: return "AILS2-E"
        if "etaMax0.01" in name or "stoppingTime9000" in name: return "AILS2-WS"
        if "stoppingTime1800" in name: return "AILS2-G"
        return name

    survivor = survivor.copy()
    survivor["algo_short"] = survivor["algo_name"].apply(shorten)
    all_algos = survivor["algo_short"].unique()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bottom = np.zeros(len(EXP_KEYS))
    cmap = plt.get_cmap("tab10")
    algo_colors = {a: cmap(j) for j, a in enumerate(all_algos)}

    for algo in all_algos:
        vals = []
        for key in EXP_KEYS:
            sub = survivor[(survivor["experiment"] == key) & (survivor["algo_short"] == algo)]
            vals.append(sub["seed_count"].sum() if not sub.empty else 0)
        ax.bar(range(len(EXP_KEYS)), vals, bottom=bottom,
               label=algo, color=algo_colors[algo], alpha=0.85)
        bottom += np.array(vals)

    ax.set_xticks(range(len(EXP_KEYS)))
    ax.set_xticklabels([EXP_LABELS[k] for k in EXP_KEYS], rotation=15, ha="right")
    ax.set_ylabel("Times holding global best")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out = FIGURES_DIR / "survivor_stats.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


# ── Figure 4: Improvement size distribution ────────────────────────────────

def fig_improvement_dist(impr: pd.DataFrame):
    data = [impr[impr["experiment"] == key]["improvement"].dropna().values
            for key in EXP_KEYS]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bp = ax.boxplot(data, patch_artist=True, notch=False,
                    medianprops=dict(color="black", linewidth=1.5))
    for patch, key in zip(bp["boxes"], EXP_KEYS):
        patch.set_facecolor(PALETTE[key])
        patch.set_alpha(0.75)

    ax.set_xticks(range(1, len(EXP_KEYS) + 1))
    ax.set_xticklabels([EXP_LABELS[k] for k in EXP_KEYS], rotation=15, ha="right")
    ax.set_ylabel("Score improvement per event")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out = FIGURES_DIR / "improvement_dist.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


# ── Table 1: Summary LaTeX table ───────────────────────────────────────────

def latex_table(history: pd.DataFrame, impr: pd.DataFrame, best: pd.DataFrame):
    rows = []
    for key in EXP_KEYS:
        gb   = best[best["experiment"] == key]
        imp  = impr[impr["experiment"] == key]
        hist = history[history["experiment"] == key]

        final_score   = gb["score"].iloc[0]          if not gb.empty  else float("nan")
        time_to_best  = gb["runningtime"].iloc[0]    if not gb.empty  else float("nan")
        best_algo     = gb["algo_name"].iloc[0]      if not gb.empty  else "—"
        n_improvements = len(imp)
        time_first    = imp["recording_time"].min()  if not imp.empty else float("nan")

        # Shorten algo name for table
        def shorten_algo(name):
            if "HGS" in str(name): return "HGS-TV"
            if "etaMax1" in str(name) or "stoppingTime18000" in str(name): return "AILS2-E"
            if "etaMax0.01" in str(name) or "stoppingTime9000" in str(name): return "AILS2-WS"
            if "stoppingTime1800" in str(name): return "AILS2-G"
            return str(name)

        rows.append({
            "Variant":          EXP_LABELS[key],
            "Final cost":       f"{int(final_score):,}",
            "\\# improvements": n_improvements,
            "Time to first (s)": f"{time_first:.0f}" if not np.isnan(time_first) else "—",
            "Time to best (s)":  f"{time_to_best:.0f}" if not np.isnan(time_to_best) else "—",
            "Best by":           shorten_algo(best_algo),
        })

    df = pd.DataFrame(rows)
    cols = list(df.columns)

    lines = []
    lines.append(r"\begin{tabular}{l" + "r" * (len(cols) - 1) + "}")
    lines.append(r"\toprule")
    lines.append(" & ".join(cols) + r" \\")
    lines.append(r"\midrule")
    for _, row in df.iterrows():
        lines.append(" & ".join(str(row[c]) for c in cols) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    tex = "\n".join(lines)
    out = EXPERIMENT_PATH / "ablation_table.tex"
    out.write_text(tex)
    print(f"Saved: {out}")
    print("\n" + tex)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    history  = load_table("solution_history")
    impr     = load_table("improvement_stats")
    best     = load_table("global_best")
    survivor = load_table("survivor_stats")

    print("\nGenerating figures...")
    fig_convergence(history)
    fig_improvement_rate(impr)
    fig_survivor(survivor)
    fig_improvement_dist(impr)

    print("\nGenerating LaTeX table...")
    latex_table(history, impr, best)

    print("\nDone. Figures in:", FIGURES_DIR)


if __name__ == "__main__":
    main()
