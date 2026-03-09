import os
import pandas as pd
import matplotlib.pyplot as plt
import sys 


XLSX_PATH = r"./ppd_ds_comparison_with_verdicts_appscore_1460.xlsx"


OUTPUT_DIR = r"./risk_figures2"


THRESHOLD = 0.7  # 70%

# Thresholds for risk tiers (overall SRS-O-weighted)
THRESH_LOW = 0.30    # below this = Low
THRESH_HIGH = 0.70   # between low & high = Medium, above high = High


def risk_tier(x: float) -> str:
    """Map a continuous SRS value into Low / Medium / High."""
    if pd.isna(x):
        return "NA"
    if x < THRESH_LOW:
        return "Low"
    elif x < THRESH_HIGH:
        return "Medium"
    else:
        return "High"


def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

  
    # PART 1: Threshold summary
 
    df = pd.read_excel(XLSX_PATH, sheet_name="Sensitivity_scores")

    total_apps = len(df)
    print(f"Total apps: {total_apps}")

    cols = ["SRS-C", "SRS-S", "SRS-O", "SRS-O-weighted"]

    for col in cols:
        if col not in df.columns:
            print(f"Column {col} not found in sheet, skipping.")
            continue

        n_above = (df[col] > THRESHOLD).sum()
        pct_above = n_above / total_apps if total_apps > 0 else 0
        print(f"{col}: {n_above} apps ({pct_above:.2%}) above {THRESHOLD:.0%}")

        vals = df[col].dropna()
        n_low = (vals < THRESH_LOW).sum()
        n_med = ((vals >= THRESH_LOW) & (vals < THRESH_HIGH)).sum()
        n_high = (vals >= THRESH_HIGH).sum()

        pct_low = n_low / total_apps if total_apps > 0 else 0
        pct_med = n_med / total_apps if total_apps > 0 else 0
        pct_high = n_high / total_apps if total_apps > 0 else 0

        print(f"  Low (< {THRESH_LOW:.0%}):    {n_low} apps ({pct_low:.2%})")
        print(f"  Medium ({THRESH_LOW:.0%}–{THRESH_HIGH:.0%}): {n_med} apps ({pct_med:.2%})")
        print(f"  High (≥ {THRESH_HIGH:.0%}):  {n_high} apps ({pct_high:.2%})")


    # PART 2: Tiering + bar plots + scatter plots
   

    # Compute risk tiers 
    df["risk_tier_overall"] = df["SRS-O-weighted"].apply(risk_tier)
    df["risk_tier_collect"] = df["SRS-C"].apply(risk_tier)
    df["risk_tier_share"] = df["SRS-S"].apply(risk_tier)

    # Print counts and percentages for overall tier
    counts = df["risk_tier_overall"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0).astype(int)
    print("\nCounts per tier (overall weighted):")
    print(counts)

    print("\nCounts and percentages per tier (overall weighted):")
    for tier in ["Low", "Medium", "High"]:
        c = counts.get(tier, 0)
        p = (c / len(df)) if len(df) > 0 else 0.0
        print(f"  {tier:6s}: {c} apps ({p:.2%})")

  
    # Visualization 1: Bar chart of #apps per overall tier
   
    plt.figure(figsize=(6, 5))
    counts.plot(kind="bar")
    ax = plt.gca()

    plt.xlabel("Risk tier")
    plt.ylabel("Number of apps")
    plt.title("Apps by Sensitivity Risk Tier (Overall Weighted)")
    plt.xticks(rotation=0)

    lines = [
        f"Low:    SRS-O-w < {THRESH_LOW:.2f}",
        f"Medium: {THRESH_LOW:.2f} ≤ SRS-O-w < {THRESH_HIGH:.2f}",
        f"High:   SRS-O-w ≥ {THRESH_HIGH:.2f}",
    ]
    textstr = "Tier ranges:\n" + "\n".join(lines)
    ax.text(
        0.98, 0.98,
        textstr,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox=dict(
            boxstyle="round",
            facecolor="none",
            edgecolor="black",
            linewidth=0.8
        )
    )

    plt.tight_layout()
    fig1_path = os.path.join(OUTPUT_DIR, "apps_by_Sensitivity_Risk_Tier_overall_weighted.png")
    plt.savefig(fig1_path, dpi=300)
    plt.show()

   
    # Visualization 2: Top 20 highest-risk apps (overall weighted)

    top20 = df.sort_values("SRS-O-weighted", ascending=False).head(20)

    plt.figure(figsize=(8, 6))
    plt.barh(top20["appname"], top20["SRS-O-weighted"])
    plt.gca().invert_yaxis()
    plt.xlabel("SRS-O-weighted")
    plt.title("Top 20 Highest Sensitivity Risk Apps (Overall Weighted)")
    plt.tight_layout()
    fig2_path = os.path.join(OUTPUT_DIR, "top20_highest_Sensitivity_Risk_Apps_overall_weighted.png")
    plt.savefig(fig2_path, dpi=300)
    plt.show()

  
    # Visualization 3 (UPDATED): Option B scatter
    X_COL = "SRS-O-weighted"
    Y_COL = "SRS-S" 
    # drop NA rows for plotting
    dfp = df.dropna(subset=[X_COL, Y_COL]).copy()

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5), sharex=True, sharey=True)

    # ---- Left: unlabeled apps ----
    axes[0].scatter(dfp[X_COL], dfp[Y_COL], alpha=0.7)
    axes[0].axvline(THRESH_LOW, linestyle="--", linewidth=2)
    axes[0].axvline(THRESH_HIGH, linestyle="--", linewidth=2)
    axes[0].set_title("Unlabeled apps")
    axes[0].set_xlabel("Overall weighted risk score (SRS-O-w)")
    axes[0].set_ylabel("Sharing risk score (SRS-S)" if Y_COL == "SRS-S" else "Collection risk score (SRS-C)")
    axes[0].set_xlim(0, 1)
    axes[0].set_ylim(0, 1)

    # ---- Right: clustered by overall tier (based on SRS-O-w) ----
    tier_colors = {
        "Low": "tab:green",
        "Medium": "gold",
        "High": "tab:red",
    }

    for tier, color in tier_colors.items():
        subset = dfp[dfp["risk_tier_overall"] == tier]
        if subset.empty:
            continue
        axes[1].scatter(
            subset[X_COL],
            subset[Y_COL],
            alpha=0.7,
            label=tier,
            color=color
        )

    axes[1].axvline(THRESH_LOW, linestyle="--", linewidth=2)
    axes[1].axvline(THRESH_HIGH, linestyle="--", linewidth=2)
    axes[1].set_title("Clustered by overall weighted tier")
    axes[1].set_xlabel("Overall weighted risk score (SRS-O-w)")
    axes[1].legend(title="Risk tier")

    plt.tight_layout()
    fig3_path = os.path.join(OUTPUT_DIR, "scatter_SRS-Ow_vs_SRS-S_unlabeled_and_clustered.png")
    plt.savefig(fig3_path, dpi=300)
    plt.show()

    print("\nSaved figures to:", OUTPUT_DIR)


    # -------------------------------------------------
    # Visualization 3 (Option B, two panels):
    # x = SRS-O-weighted (vertical tier lines)
    # y = SRS-S (left) and y = SRS-C (right)
    # -------------------------------------------------
    X_COL = "SRS-O-weighted"

    dfp = df.dropna(subset=[X_COL, "SRS-S", "SRS-C"]).copy()

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)

    tier_colors = {"Low": "tab:green", "Medium": "gold", "High": "tab:red"}

    def plot_panel(ax, y_col, title):
        # points colored by overall tier
        for tier, color in tier_colors.items():
            sub = dfp[dfp["risk_tier_overall"] == tier]
            if sub.empty:
                continue
            ax.scatter(sub[X_COL], sub[y_col], alpha=0.7, s=35, label=tier, color=color)

        # tier boundaries on x-axis
        ax.axvline(THRESH_LOW, linestyle="--", linewidth=2)
        ax.axvline(THRESH_HIGH, linestyle="--", linewidth=2)

        ax.set_title(title)
        ax.set_xlabel("Overall weighted risk score (SRS-O-w)")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    # Left: Sharing
    plot_panel(axes[0], "SRS-S", "Overall risk vs Sharing risk (SRS-S)")
    axes[0].set_ylabel("Sharing risk score (SRS-S)")
    axes[0].legend(title="Risk tier", loc="upper left")

    # Right: Collection
    plot_panel(axes[1], "SRS-C", "Overall risk vs Collection risk (SRS-C)")
    axes[1].set_ylabel("Collection risk score (SRS-C)")

    plt.tight_layout()
    fig3_path = os.path.join(OUTPUT_DIR, "scatter_SRS-Ow_vs_SRS-S_and_SRS-C_clustered.png")
    plt.savefig(fig3_path, dpi=300)
    plt.show()

    # -------------------------------------------------
    # Visualization 3 (UPDATED, Option B + keep unlabeled):
    # 2x2 grid
    # x = SRS-O-weighted (vertical tier lines at 0.30 and 0.70)
    # y = SRS-S and y = SRS-C
    # top row: unlabeled
    # bottom row: clustered by overall tier
    # -------------------------------------------------
    X_COL = "SRS-O-weighted"
    Y_COLS = [("SRS-S", "Sharing risk score (SRS-S)"),
            ("SRS-C", "Collection risk score (SRS-C)")]

    # drop NA rows for plotting
    dfp = df.dropna(subset=[X_COL, "SRS-S", "SRS-C"]).copy()

    tier_colors = {"Low": "tab:green", "Medium": "gold", "High": "tab:red"}

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True, sharey=True)

    def add_boundaries(ax):
        ax.axvline(THRESH_LOW, linestyle="--", linewidth=2)
        ax.axvline(THRESH_HIGH, linestyle="--", linewidth=2)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    # ----- Top row: unlabeled -----
    for j, (ycol, ylabel) in enumerate(Y_COLS):
        ax = axes[0, j]
        ax.scatter(dfp[X_COL], dfp[ycol], alpha=0.7, s=30)
        add_boundaries(ax)
        ax.set_title("Unlabeled apps")
        ax.set_xlabel("Overall weighted risk score (SRS-O-w)")
        ax.set_ylabel(ylabel)

    # ----- Bottom row: clustered by overall tier -----
    for j, (ycol, ylabel) in enumerate(Y_COLS):
        ax = axes[1, j]
        for tier, color in tier_colors.items():
            subset = dfp[dfp["risk_tier_overall"] == tier]
            if subset.empty:
                continue
            ax.scatter(subset[X_COL], subset[ycol], alpha=0.7, s=30, label=tier, color=color)

        add_boundaries(ax)
        ax.set_title("Clustered by overall weighted tier")
        ax.set_xlabel("Overall weighted risk score (SRS-O-w)")
        ax.set_ylabel(ylabel)
        if j == 0:  # show legend only once
            ax.legend(title="Risk tier", loc="upper left")

    plt.tight_layout()
    fig3_path = os.path.join(OUTPUT_DIR, "scatter_SRS-Ow_vs_SRS-S_and_SRS-C_unlabeled_and_clustered.png")
    plt.savefig(fig3_path, dpi=300)
    plt.show()


    # -------------------------------------------------
    # Visualization 4: Histogram of SRS-O-weighted (overall weighted)
    # with tier boundary lines at 0.30 and 0.70
    # -------------------------------------------------
    plt.figure(figsize=(7.5, 5.2))

    vals = df["SRS-O-weighted"].dropna()

    # histogram
    plt.hist(vals, bins=30, alpha=0.85)
    
   # tier boundary lines (tier definitions)
    plt.axvline(THRESH_LOW, linestyle="--", linewidth=2,
                label=f"Low: score < {THRESH_LOW:.2f} | Medium: {THRESH_LOW:.2f} \u2264 score < {THRESH_HIGH:.2f}")

    plt.axvline(THRESH_HIGH, linestyle="--", linewidth=2,
                label=f"High: score \u2265 {THRESH_HIGH:.2f}")



    plt.xlim(0, 1)
    plt.xlabel("Overall weighted sensitivity risk score (SRS-O-w)")
    plt.ylabel("Number of apps")
    plt.title("Histogram of Overall Weighted Sensitivity Risk (SRS-O-w)")

    # optional: show tier counts on the plot
    n_low = (vals < THRESH_LOW).sum()
    n_med = ((vals >= THRESH_LOW) & (vals < THRESH_HIGH)).sum()
    n_high = (vals >= THRESH_HIGH).sum()
    total = len(vals)

    textstr = (
        f"Low: {n_low} ({n_low/total:.1%})\n"
        f"Med: {n_med} ({n_med/total:.1%})\n"
        f"High:{n_high} ({n_high/total:.1%})"
    )
    ax = plt.gca()
    ax.text(
        0.98, 0.98,
        textstr,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="none", edgecolor="black", linewidth=0.8)
    )

    plt.legend(loc="upper left")
    plt.tight_layout()

    fig4_path = os.path.join(OUTPUT_DIR, "hist_SRS-O-weighted_with_tier_lines.png")
    plt.savefig(fig4_path, dpi=300)
    plt.show()



# ---------- Tee stdout to file + console ----------
class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)

    def flush(self):
        for f in self.files:
            f.flush()


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "risk_console_output.txt")

    with open(log_path, "w", encoding="utf-8") as log_file:
        orig_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, log_file)
        try:
            main()
        finally:
            sys.stdout = orig_stdout
