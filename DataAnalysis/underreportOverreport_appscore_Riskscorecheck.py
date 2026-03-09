

import os
import pandas as pd
import matplotlib.pyplot as plt
import sys  


XLSX_PATH = r"./ppd_ds_comparison_with_verdicts_appscore_1460.xlsx"



OUTPUT_DIR = r"./risk_figures"


# Threshold used for "above X%" counts
THRESHOLD = 0.7  # 70%

# Thresholds for risk tiers (overall SRS-O-weighted)
THRESH_LOW = 0.30    # below this = Low
THRESH_HIGH = 0.70   # between low & high = Medium, above high = High


def risk_tier(x: float) -> str:
    """Map a continuous SRS value into Low / Medium / High."""
    if x < THRESH_LOW:
        return "Low"
    elif x < THRESH_HIGH:
        return "Medium"
    else:
        return "High"


def main():
  
    os.makedirs(OUTPUT_DIR, exist_ok=True)

   
    # PART 1: Threshold summary 
    # Read the Sensitivity_scores sheet
    df = pd.read_excel(XLSX_PATH, sheet_name="Sensitivity_scores")

    total_apps = len(df)
    print(f"Total apps: {total_apps}")

    # Columns to check
    cols = ["SRS-C", "SRS-S", "SRS-O", "SRS-O-weighted"]

    for col in cols:
        if col not in df.columns:
            print(f"Column {col} not found in sheet, skipping.")
            continue

        n_above = (df[col] > THRESHOLD).sum()
        pct_above = n_above / total_apps if total_apps > 0 else 0
        print(f"{col}: {n_above} apps ({pct_above:.2%}) above {THRESHOLD:.0%}")

        # Extra: Low / Medium / High breakdown for this SRS column
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
    df["risk_tier_share"]   = df["SRS-S"].apply(risk_tier)

    # Print counts and percentages for overall tier
    counts = df["risk_tier_overall"].value_counts().reindex(["Low", "Medium", "High"])
    print("\nCounts per tier (overall weighted):")
    print(counts)

    print("\nPercentages per tier (overall weighted):")
    percentages = counts / len(df) if len(df) > 0 else 0
    print(percentages.round(3))

        # Extra: nicely formatted counts + percentages per tier (also goes to log)
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
    plt.title("Apps by Sensitivity Risk Tier (Overall)")
    plt.xticks(rotation=0)

  
    if isinstance(percentages, pd.Series):
        lines = [
            f"Low:    SRS-O < {THRESH_LOW:.2f}",
            f"Medium: {THRESH_LOW:.2f} ≤ SRS-O < {THRESH_HIGH:.2f}",
            f"High:   SRS-O ≥ {THRESH_HIGH:.2f}",
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
                facecolor="none",   # no fill
                edgecolor="black",  # outline only
                linewidth=0.8)
        )

    plt.tight_layout()
    fig1_path = os.path.join(OUTPUT_DIR, "apps_by_Sensitivity_Risk_Tier_overall.png")
    plt.savefig(fig1_path, dpi=300)
    plt.show()

    # Visualization 2: Top 20 highest-risk apps
    top20 = (
        df.sort_values("SRS-O-weighted", ascending=False)
          .head(20)
    )

    plt.figure(figsize=(8, 6))
    plt.barh(top20["appname"], top20["SRS-O-weighted"])
    plt.gca().invert_yaxis()  # Highest risk at the top
    plt.xlabel("SRS-O-weighted")
    plt.title("Top 20 Highest Sensitivity Risk Apps (Overall Weighted)")
    plt.tight_layout()
    fig2_path = os.path.join(OUTPUT_DIR, "top20_highest_Sensitivity_Risk_Apps_overall_weighted.png")
    plt.savefig(fig2_path, dpi=300)
    plt.show()

    # Visualization 3: Scatter-style clusters like the example
    # X-axis: collection sensitivity (SRS-C)
    # Y-axis: sharing sensitivity (SRS-S)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5), sharex=True, sharey=True)

    # ---- Left: unlabeled data (all apps same color) ----
    axes[0].scatter(df["SRS-C"], df["SRS-S"], alpha=0.7)
    axes[0].set_title("Unlabeled apps")
    axes[0].set_xlabel("Collection sensitivity Risk Score (SRS-C)")
    axes[0].set_ylabel("Sharing sensitivity Risk Score (SRS-S)")

    # ---- Right: clustered by overall risk tier ----
    # choose colors per tier
    tier_colors = {
        "Low": "tab:green",
        "Medium": "gold",
        "High": "tab:red",
    }

    for tier, color in tier_colors.items():
        subset = df[df["risk_tier_overall"] == tier]
        if subset.empty:
            continue
        axes[1].scatter(
            subset["SRS-C"],
            subset["SRS-S"],
            alpha=0.7,
            label=tier,
            color=color
        )

    axes[1].set_title("Clustered by sensitivity tier (overall)")
    axes[1].set_xlabel("Collection sensitivity Risk Score (SRS-C)")
    # y-label shared with left axis
    axes[1].legend(title="Risk tier")

    plt.tight_layout()
    fig3_path = os.path.join(OUTPUT_DIR, "scatter_SRS-C_vs_SRS-S_unlabeled_and_clustered.png")
    plt.savefig(fig3_path, dpi=300)
    plt.show()




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
