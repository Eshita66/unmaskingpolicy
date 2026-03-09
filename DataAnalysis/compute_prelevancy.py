
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np  
import os   
import sys        

EXCEL_PATH = "./ppd_ds_comparison_with_verdicts_1460.xlsx"


OUTPUT_DIR = r"G:\policyCode\prevalence_plot"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)

    def flush(self):
        for f in self.files:
            f.flush()

log_path = os.path.join(OUTPUT_DIR, "prevalence_console_output.txt")
log_file = open(log_path, "w", encoding="utf-8")

orig_stdout = sys.stdout
sys.stdout = Tee(sys.stdout, log_file)
# ---------------------------------------------------------

df = pd.read_excel(EXCEL_PATH, sheet_name="Verdicts")

# Create inconsistency flags
df["is_under"] = (df["verdict"] == "UNDER").astype(int)
df["is_over"]  = (df["verdict"] == "OVER").astype(int)
df["is_mis"]   = ((df["verdict"] == "UNDER") | (df["verdict"] == "OVER")).astype(int)



# 1) Overall prevalence 

overall = (
    df.groupby("Operation")[["is_mis", "is_under", "is_over"]]
      .sum()
)
counts = df.groupby("Operation").size().rename("N_cells")
overall = overall.join(counts)

overall["misalign_rate"] = overall["is_mis"]   / overall["N_cells"]
overall["under_rate"]    = overall["is_under"] / overall["N_cells"]
overall["over_rate"]     = overall["is_over"]  / overall["N_cells"]

print("Cell-level prevalence by operation:")
print(overall)


# 2) Prevalence per category & operation 

cat_stats = (
    df.groupby(["Operation", "Category"])[["is_mis", "is_under", "is_over"]]
      .sum()
)
cat_counts = df.groupby(["Operation", "Category"]).size().rename("N_cells")
cat_stats = cat_stats.join(cat_counts)

cat_stats["misalign_rate"] = cat_stats["is_mis"]   / cat_stats["N_cells"]
cat_stats["under_rate"]    = cat_stats["is_under"] / cat_stats["N_cells"]
cat_stats["over_rate"]     = cat_stats["is_over"]  / cat_stats["N_cells"]

print("\nCategory-level prevalence (head):")
print(cat_stats)

app_op = (
    df.groupby(["appname", "Operation"])[["is_mis", "is_under", "is_over"]]
      .max()        # any misalignment in any category for this app+operation
      .reset_index()
)

app_overall = (
    app_op.groupby("Operation")[["is_mis", "is_under", "is_over"]]
          .sum()
)

N_apps = app_op.groupby("Operation")["appname"].nunique().rename("N_apps")
app_overall = app_overall.join(N_apps)

# Rename columns to clarify these are app-level indicators
app_overall = app_overall.rename(columns={
    "is_mis":   "any_mis_app",
    "is_under": "any_under_app",
    "is_over":  "any_over_app",
})

app_overall["misalign_rate_app"] = app_overall["any_mis_app"]   / app_overall["N_apps"]
app_overall["under_rate_app"]    = app_overall["any_under_app"] / app_overall["N_apps"]
app_overall["over_rate_app"]     = app_overall["any_over_app"]  / app_overall["N_apps"]

print("\nApp-level prevalence by operation:")
print(app_overall)


# 3) PLOTTING


# ---------- 3a. Overall 
fig, ax = plt.subplots(figsize=(6, 4))

ops = overall.index.tolist()
x = range(len(ops))
width = 0.25
ax.bar([i - width for i in x], overall["misalign_rate"], width, label="Misalignment in ALL")
ax.bar(x,                            overall["under_rate"],  width, label="Misalignment in DSL only")
ax.bar([i + width for i in x], overall["over_rate"],   width, label="Misalignment in PPD only")

ax.set_xticks(list(x))
ax.set_xticklabels(ops)
ax.set_xlabel("Data Operation")
ax.set_ylabel("Rate (over app-data-category)")
ax.set_title("Overall Misalignment by Data Operation")
ax.set_ylim(0, 1)
ax.legend()

plt.tight_layout()
plt.show()
fig.savefig(os.path.join(OUTPUT_DIR, "overall_cell_prevalence_by_operation.png"), dpi=300)

# ---------- 3b. Category-level rates 
cat_stats_reset = cat_stats.reset_index()  


metrics = [
    ("misalign_rate", "Category-level Misalignment in ALL (PPD vs DSL)", "Misalignment Rate", "category_level_misalignment.png"),
    ("under_rate",    "Category-level Misalignment in DSL only (PPD vs DSL)", "Misalignment in DSL only Rate", "category_level_under.png"),
    ("over_rate",     "Category-level Misalignment in PPD only (PPD vs DSL)", "Misalignment in PPD only Rate", "category_level_over.png"),
]
for metric_col, title, ylabel, outfile in metrics:
    # Pivot to wide: rows = Category, columns = Operation, values = the metric
    cat_metric = cat_stats_reset.pivot(index="Category", columns="Operation", values=metric_col)

    # Ensure consistent column order
    columns_in_order = [c for c in ["collected", "shared"] if c in cat_metric.columns]
    cat_metric = cat_metric[columns_in_order]

    categories = cat_metric.index.tolist()
    x = np.arange(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))

    if "collected" in cat_metric.columns:
        ax.bar(x - width/2, cat_metric["collected"], width, label="Collected")
    if "shared" in cat_metric.columns:
        ax.bar(x + width/2, cat_metric["shared"],    width, label="Shared")

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha="right")
    ax.set_xlabel("Data category")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0, 1)
    ax.legend()

    plt.tight_layout()
    plt.show()
    # ---- uncommented & routed to OUTPUT_DIR ----
    fig.savefig(os.path.join(OUTPUT_DIR, outfile), dpi=300)

# ---------- 3c. Heatmap of misalignment by category & operation ----------
cat_stats_reset = cat_stats.reset_index()  

cat_mis_heat = cat_stats_reset.pivot(
    index="Category",
    columns="Operation",
    values="misalign_rate"
)

# Ensure consistent column order
columns_in_order = [c for c in ["collected", "shared"] if c in cat_mis_heat.columns]
cat_mis_heat = cat_mis_heat[columns_in_order]

fig3, ax3 = plt.subplots(figsize=(6, 6))
im = ax3.imshow(cat_mis_heat.values, aspect="auto")

ax3.set_xticks(range(len(cat_mis_heat.columns)))
ax3.set_xticklabels(cat_mis_heat.columns)
ax3.set_yticks(range(len(cat_mis_heat.index)))
ax3.set_yticklabels(cat_mis_heat.index)



ax3.set_title("Misalignment in ALL by Data Category and Operation")
cbar = plt.colorbar(im, ax=ax3)
cbar.set_label("Misalignment in ALL rate")

plt.tight_layout()
plt.show()
# ---- changed: use OUTPUT_DIR ----
fig3.savefig(os.path.join(OUTPUT_DIR, "misalignment_heatmap.png"), dpi=300, bbox_inches="tight")

# ---------- 3d. App-level bar plot (new) ----------
fig4, ax4 = plt.subplots(figsize=(6, 4))

ops_app = app_overall.index.tolist()
x = range(len(ops_app))
width = 0.25

ax4.bar([i - width for i in x], app_overall["misalign_rate_app"], width, label="Misaligned (app-level)")
ax4.bar(x,                      app_overall["under_rate_app"],    width, label="Under-reported (app-level)")
ax4.bar([i + width for i in x], app_overall["over_rate_app"],     width, label="Over-reported (app-level)")

ax4.set_xticks(list(x))
ax4.set_xticklabels(ops_app)
ax.set_xlabel("Data operation")
ax4.set_ylabel("Rate (app-level)")
ax4.set_title("App-level prevalence by operation")
ax4.set_ylim(0, 1)
ax4.legend()

plt.tight_layout()
plt.show()
# ---- changed: use OUTPUT_DIR ----
fig4.savefig(os.path.join(OUTPUT_DIR, "app_level_prevalence_by_operation.png"), dpi=300)



overall["agree_rate"] = 1.0 - overall["misalign_rate"]

fig5, ax5 = plt.subplots(figsize=(6, 4))

ops = overall.index.tolist()
x = np.arange(len(ops))

agreement = overall["agree_rate"].values
dsl_only  = overall["under_rate"].values
ppd_only  = overall["over_rate"].values

# --- Grouped bars (not stacked) ---
width = 0.25
x_agree = x - width
x_dsl   = x
x_ppd   = x + width

ax5.bar(x_agree, agreement, width=width, label="Agreement (PPD = DSL)")
ax5.bar(x_dsl,   dsl_only,  width=width, label="Misalignment in DSL only")
ax5.bar(x_ppd,   ppd_only,  width=width, label="Misalignment in PPD only")

ax5.set_ylim(0, 1)  # set before labeling

def add_pct_labels(ax, x_positions, heights, bottoms=None, min_height_inside=0.06,
                   label_override=None):
    if bottoms is None:
        bottoms = np.zeros_like(heights)
    if label_override is None:
        label_override = {}

    y_min, y_max = ax.get_ylim()
    eps = 0.01 * (y_max - y_min)

    for idx, (xi, h, b) in enumerate(zip(x_positions, heights, bottoms)):
        if h <= 0:
            continue

        label = f"{h*100:.1f}%"
        if idx in label_override:
            label = label_override[idx]

        # ALWAYS place label at the top of the bar
        y = b + h + eps
        va = "bottom"

        # If it would go outside the plot, pull it slightly inside
        if y >= y_max - eps:
            y = b + h - eps
            va = "top"

        ax.text(xi, y, label, ha="center", va=va, fontsize=9)

# Indices
collected_idx = ops.index("collected")
shared_idx    = ops.index("shared")

agreement_overrides = {
    collected_idx: "66.8%",
    shared_idx:    "69.0%",
}

# Labels (no stacking -> bottoms are zeros)
add_pct_labels(
    ax5, x_agree, agreement,
    bottoms=np.zeros_like(agreement),
    label_override=agreement_overrides
)
add_pct_labels(ax5, x_dsl, dsl_only, bottoms=np.zeros_like(dsl_only))
add_pct_labels(ax5, x_ppd, ppd_only, bottoms=np.zeros_like(ppd_only))

# Axis labels / title
ax5.set_xticks(x)
ax5.set_xticklabels(ops)
ax5.set_xlabel("Data Operation")
ax5.set_ylabel("Rate (over app-data-category)")
ax5.set_title("Agreement vs Misalignment by Data Operation")
ax5.legend()

plt.tight_layout()
plt.show()
fig5.savefig(os.path.join(OUTPUT_DIR, "overall_consistency.png"), dpi=300)



sys.stdout = orig_stdout
log_file.close()


