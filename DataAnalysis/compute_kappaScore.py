


import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score
import matplotlib.pyplot as plt
import os
import sys  


EXCEL_PATH = "./ppd_ds_comparison_with_verdicts_1460.xlsx"
SHEET_NAME = "Verdicts"


OUTPUT_CATEGORY_KAPPA_XLSX = "./kappa_by_category.xlsx"

OUTPUT_FIG_DIR = "./figures"



def main():
   
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)

   
    df = df.dropna(subset=["PPD", "DS"])
    df["PPD"] = df["PPD"].astype(int)
    df["DS"]  = df["DS"].astype(int)

    # ----------------------------
    # Overall Kappa by operation
    # ----------------------------
    df_collect = df[df["Operation"] == "collected"].copy()
    df_share   = df[df["Operation"] == "shared"].copy()

    kappa_collect = cohen_kappa_score(df_collect["PPD"], df_collect["DS"])
    kappa_share   = cohen_kappa_score(df_share["PPD"],  df_share["DS"])

    print("=== Overall Kappa by Operation ===")
    print(f"Kappa (collection): {kappa_collect:.3f}")
    print(f"Kappa (sharing):   {kappa_share:.3f}")
    print(f"Difference (sharing - collection): {kappa_share - kappa_collect:.3f}")
    print()

    # Optional: bootstrap CI for the difference
    diffs, ci_low, ci_high = bootstrap_kappa_difference(df)
    print("=== Bootstrap 95% CI for (kappa_share - kappa_collect) ===")
    print(f"95% CI: [{ci_low:.3f}, {ci_high:.3f}]")
    print(f"Proportion of bootstrap diffs >= 0: {(diffs >= 0).mean():.3f}")
    print()

  
    # Category-level Kappa
   
    df_kappa_collect = kappa_by_category(df, op_label="collected", category_col="Category")
    df_kappa_share   = kappa_by_category(df, op_label="shared",   category_col="Category")

    print("=== Category-level Kappa: COLLECTION ===")
    print(df_kappa_collect.to_string(index=False))
    print()
    print("=== Category-level Kappa: SHARING ===")
    print(df_kappa_share.to_string(index=False))
    print()

    df_kappa_all = pd.concat([df_kappa_collect, df_kappa_share], ignore_index=True)
    df_kappa_all.to_excel(OUTPUT_CATEGORY_KAPPA_XLSX, index=False)
    print(f"Saved category-level Kappa table to: {OUTPUT_CATEGORY_KAPPA_XLSX}")

  
    # PLOTS
    make_overall_kappa_boxplot(df, B=1000, random_state=42)
    make_overall_kappa_violinplot(df, B=1000, random_state=42)        
    make_kappa_difference_histogram(df, B=1000, random_state=42)      #


def bootstrap_kappa_difference(df: pd.DataFrame, B: int = 1000, random_state: int = 42):
    rng = np.random.default_rng(random_state)

    df_collect = df[df["Operation"] == "collected"].reset_index(drop=True)
    df_share   = df[df["Operation"] == "shared"].reset_index(drop=True)

    n_collect = len(df_collect)
    n_share   = len(df_share)

    diffs = []

    for _ in range(B):
        idx_c = rng.integers(0, n_collect, n_collect)
        idx_s = rng.integers(0, n_share,   n_share)

        sample_collect = df_collect.loc[idx_c]
        sample_share   = df_share.loc[idx_s]

        k_c = cohen_kappa_score(sample_collect["PPD"], sample_collect["DS"])
        k_s = cohen_kappa_score(sample_share["PPD"],   sample_share["DS"])

        diffs.append(k_s - k_c)

    diffs = np.array(diffs)
    ci_low, ci_high = np.percentile(diffs, [2.5, 97.5])
    return diffs, ci_low, ci_high


def kappa_by_category(df: pd.DataFrame, op_label: str, category_col: str = "Category") -> pd.DataFrame:
    df_op = df[df["Operation"] == op_label].copy()

    rows = []
    for cat, g in df_op.groupby(category_col):
        if g["PPD"].nunique() == 1 and g["DS"].nunique() == 1:
            kappa = np.nan
        else:
            try:
                kappa = cohen_kappa_score(g["PPD"], g["DS"])
            except ValueError:
                kappa = np.nan

        rows.append({
            "Operation": op_label,
            "Category": cat,
            "N": len(g),
            "Kappa": kappa
        })

    out = pd.DataFrame(rows)
    out = out.sort_values(["Kappa", "Category"], ascending=[True, True]).reset_index(drop=True)
    return out




def bootstrap_kappa_for_plot(df: pd.DataFrame, B: int = 1000, random_state: int = 42):
    rng = np.random.default_rng(random_state)

    df_collect = df[df["Operation"] == "collected"].reset_index(drop=True)
    df_share   = df[df["Operation"] == "shared"].reset_index(drop=True)

    n_collect = len(df_collect)
    n_share   = len(df_share)

    k_collect_samples = []
    k_share_samples   = []

    for _ in range(B):
        idx_c = rng.integers(0, n_collect, n_collect)
        idx_s = rng.integers(0, n_share,   n_share)

        sample_collect = df_collect.loc[idx_c]
        sample_share   = df_share.loc[idx_s]

        k_c = cohen_kappa_score(sample_collect["PPD"], sample_collect["DS"])
        k_s = cohen_kappa_score(sample_share["PPD"],   sample_share["DS"])

        k_collect_samples.append(k_c)
        k_share_samples.append(k_s)

    return np.array(k_collect_samples), np.array(k_share_samples)




def make_overall_kappa_boxplot(df: pd.DataFrame, B: int = 1000, random_state: int = 42) -> None:
    os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)

    k_collect_samples, k_share_samples = bootstrap_kappa_for_plot(
        df, B=B, random_state=random_state
    )

    data = [k_share_samples, k_collect_samples]  
    labels = ["shared", "collected"]

    plt.figure(figsize=(5, 4))
    plt.boxplot(data, labels=labels)
    plt.xlabel("Data Operation")
    plt.ylabel("Cohen's Kappa")
    plt.title("PPD Vs. DSL Cohen's Kappa by data operation")
    plt.ylim(0.00, 0.40)
   

    out_path = os.path.join(OUTPUT_FIG_DIR, "kappa_boxplot_by_operation.png")
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"Saved Kappa boxplot to: {out_path}")








def make_overall_kappa_violinplot(df: pd.DataFrame, B: int = 1000, random_state: int = 42) -> None:
    """
    Violin plot of bootstrap Kappa distributions for shared vs collected.
    """
    os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)

    k_collect_samples, k_share_samples = bootstrap_kappa_for_plot(
        df, B=B, random_state=random_state
    )

    data = [k_share_samples, k_collect_samples]   # shared, collected
    labels = ["shared", "collected"]
    positions = np.arange(1, len(data) + 1)

    fig, ax = plt.subplots(figsize=(5, 4))
    vp = ax.violinplot(data, positions=positions, showmeans=True,
                       showmedians=True, showextrema=True)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_label("Data Operation")
    ax.set_ylabel("Cohen's Kappa")
    ax.set_title("PPD Vs. DSL Cohen's Kappa by data operation")
    ax.set_ylim(0.00, 0.40)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_FIG_DIR, "kappa_violin_by_operation.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved Kappa violin plot to: {out_path}")




def make_kappa_difference_histogram(df: pd.DataFrame, B: int = 1000, random_state: int = 42) -> None:
    """
    Histogram of bootstrap differences (kappa_share - kappa_collect).
    """
    os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)

    diffs, ci_low, ci_high = bootstrap_kappa_difference(df, B=B, random_state=random_state)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.hist(diffs, bins=30, edgecolor="black")
    ax.axvline(0, linestyle="--")  # reference line at 0
    ax.axvline(diffs.mean(), linestyle="-")  # mean difference
    ax.set_xlabel("Difference in Kappa (sharing - collection)")
    ax.set_ylabel("Frequency")
    ax.set_title(f"Bootstrap distribution of Kappa difference\n"
                 f"mean={diffs.mean():.3f}, 95% CI=[{ci_low:.3f}, {ci_high:.3f}]")
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_FIG_DIR, "kappa_difference_histogram.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved Kappa difference histogram to: {out_path}")




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
    os.makedirs(OUTPUT_FIG_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_FIG_DIR, "kappa_console_output.txt")

    with open(log_path, "w", encoding="utf-8") as log_file:
        orig_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, log_file)   
        try:
            main()
        finally:
            sys.stdout = orig_stdout             
