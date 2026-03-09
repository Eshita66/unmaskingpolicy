
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


XLSX_PATH   = r"G:\policyCode\ppd_ds_comparison_with_verdicts_appscore_1460_metadata.xlsx"
SHEET_NAME  = "Sensitivity_scores_with_meta"   # sheet that has Category + SRS columns



OUTPUT_DIR = r"G:\policyCode\risk_figures_category_popularity"


# Thresholds for risk tiers 
THRESH_LOW  = 0.30
THRESH_HIGH = 0.70

def risk_tier(x: float) -> str:
    if x < THRESH_LOW:
        return "Low"
    elif x < THRESH_HIGH:
        return "Medium"
    else:
        return "High"

def parse_km(val):
    """
    Parse strings like '50.7K', '10M+', '1,234', '500K+' into numeric counts.
    Returns float or NaN.
    """
    if isinstance(val, str):
        s = val.strip().replace("+", "")
        s = s.replace(",", "")
        if s.endswith("K"):
            try:
                return float(s[:-1]) * 1_000
            except ValueError:
                return np.nan
        if s.endswith("M"):
            try:
                return float(s[:-1]) * 1_000_000
            except ValueError:
                return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan
    return np.nan


def main():
  
    os.makedirs(OUTPUT_DIR, exist_ok=True)

  
    df = pd.read_excel(XLSX_PATH, sheet_name=SHEET_NAME)

  
    df = df.dropna(subset=["Category", "SRS-O-weighted"])

  
    # 1) BAR CHART: mean SRS-O-weighted by Category
    #    (limit to TOP 20 categories by mean SRS)
  
    cat_stats = (
        df.groupby("Category")["SRS-O-weighted"]
          .agg(["count", "mean", "median", "std"])
          .sort_values("mean", ascending=False)
    )

    print("Category-level stats (SRS-O-weighted):")
    print(cat_stats)

    cat_stats_top20 = cat_stats.head(20)
    top_categories = cat_stats_top20.index.tolist()

    plt.figure(figsize=(8, 4))
    cat_stats_top20["mean"].plot(kind="bar")
    plt.ylabel("Mean SRS-O-weighted")
    plt.xlabel("App category")
    plt.title("Mean Sensitivity Risk Score by App Category (Top 20)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig1_path = os.path.join(OUTPUT_DIR, "mean_SRS_by_category_top20.png")
    plt.savefig(fig1_path, dpi=300)
    plt.show()
    print(f"Saved: {fig1_path}")


    # 2) STACKED BAR: risk tier distribution by Category
    
    # assign risk tiers
    df["risk_tier_overall"] = df["SRS-O-weighted"].apply(risk_tier)

    # restrict df to the same top 20 categories
    df_top = df[df["Category"].isin(top_categories)]

    # crosstab of Category x risk tier
    ctab = pd.crosstab(df_top["Category"], df_top["risk_tier_overall"])

    # ensure consistent column order
    for tier in ["Low", "Medium", "High"]:
        if tier not in ctab.columns:
            ctab[tier] = 0
    ctab = ctab[["Low", "Medium", "High"]]

    # convert to row-wise percentages
    ctab_pct = ctab.div(ctab.sum(axis=1), axis=0)

    print("\nRisk tier distribution by category (proportions, top 20 categories):")
    print(ctab_pct.round(3))

    plt.figure(figsize=(8, 4))
    bottom = None
    handles = {}   # to build legend: tier -> one bar handle

    for tier in ["Low", "Medium", "High"]:
        if tier not in ctab_pct.columns:
            continue

        if bottom is None:
            bars = plt.bar(ctab_pct.index, ctab_pct[tier])
            bottom = ctab_pct[tier]
        else:
            bars = plt.bar(ctab_pct.index, ctab_pct[tier], bottom=bottom)
            bottom = bottom + ctab_pct[tier]

        # store one representative handle for each tier for the legend
        handles[tier] = bars[0]

    plt.ylabel("Proportion of apps")
    plt.xlabel("App category")
    plt.title(
        "Risk tier distribution by category (Top 20)\n"
        f"Low < {THRESH_LOW:.2f}, "
        f"{THRESH_LOW:.2f} ≤ Medium < {THRESH_HIGH:.2f}, "
        f"High ≥ {THRESH_HIGH:.2f}"
    )
    plt.xticks(rotation=45, ha="right")

    # Legend: color ↔ tier mapping
    plt.legend(
        handles.values(),
        handles.keys(),
        title="Risk tier",
        loc="upper right"
    )

    plt.tight_layout()
    fig2_path = os.path.join(OUTPUT_DIR, "risk_tier_distribution_by_category_top20.png")
    plt.savefig(fig2_path, dpi=300)
    plt.show()
    print(f"Saved: {fig2_path}")

  
    # 3) POPULARITY vs RISK
    #    - rating vs SRS-O-weighted
    #    - downloads vs SRS-O-weighted (log scale)
  

    # Parse reviews/downloads to numeric
    if "reviews" in df.columns:
        df["reviews_num"] = df["reviews"].apply(parse_km)
    else:
        df["reviews_num"] = np.nan

    if "downloads" in df.columns:
        df["downloads_num"] = df["downloads"].apply(parse_km)
    else:
        df["downloads_num"] = np.nan

    # --- Scatter: rating vs SRS-O-weighted ---
    pop_rating = df.dropna(subset=["rating", "SRS-O-weighted"])

    if not pop_rating.empty:
        plt.figure(figsize=(6, 5))
        plt.scatter(pop_rating["rating"], pop_rating["SRS-O-weighted"], alpha=0.5)
        plt.xlabel("App rating")
        plt.ylabel("SRS-O-weighted")
        plt.title("Popularity vs Risk: Rating vs Sensitivity Risk Score")
        plt.tight_layout()
        fig3_path = os.path.join(OUTPUT_DIR, "rating_vs_SRS-O-weighted.png")
        plt.savefig(fig3_path, dpi=300)
        plt.show()
        print(f"Saved: {fig3_path}")
    else:
        print("No valid data for rating vs SRS-O-weighted plot.")

    # --- Scatter: downloads (log10) vs SRS-O-weighted ---
    pop_down = df.dropna(subset=["downloads_num", "SRS-O-weighted"])
    pop_down = pop_down[pop_down["downloads_num"] > 0]

    if not pop_down.empty:
        plt.figure(figsize=(6, 5))
        plt.scatter(np.log10(pop_down["downloads_num"]), pop_down["SRS-O-weighted"], alpha=0.5)
        plt.xlabel("log10(Downloads)")
        plt.ylabel("SRS-O-weighted")
        plt.title("Popularity vs Risk: Downloads vs Sensitivity Risk Score")
        plt.tight_layout()
        fig4_path = os.path.join(OUTPUT_DIR, "downloads_vs_SRS-O-weighted_log10.png")
        plt.savefig(fig4_path, dpi=300)
        plt.show()
        print(f"Saved: {fig4_path}")
    else:
        print("No valid data for downloads vs SRS-O-weighted plot.")

    # Optional: print correlation matrix for interpretation
    corr_cols = ["SRS-O-weighted", "rating", "reviews_num", "downloads_num"]
    print("\nCorrelation matrix (SRS vs popularity metrics):")
    print(df[corr_cols].corr().round(3))


if __name__ == "__main__":
    main()
