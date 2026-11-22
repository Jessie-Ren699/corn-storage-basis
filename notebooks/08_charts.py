"""Step 08: charts from data/gold/gold_yearly.csv (all regions, 6 states).

1. outputs/scatter_gap.png   "decision" chart: x = gap_oct_cents (known on Oct 15),
                             y = breakeven_storage_cents (gap closed - interest = what was left
                             to pay for storage). One dot per region-year, colored AND shaped by
                             state; one pooled OLS line; storage cost cases from
                             data/raw/storage_costs.csv in gray: low = dotted line, mid and
                             high = shaded min-max bands. A dot above a case means storing beat
                             selling at that storage cost. Also prints the regression with
                             state fixed effects (one intercept per state, one common slope).
2. outputs/bars_by_year.png  one panel: bar = median "left for storage" across regions per year,
                             whisker = 10th-90th percentile; storage costs as step lines
                             (low / mid / high); under each year the % of regions where storing won.

Run from the project folder:
    python notebooks/08_charts.py
Testing only (made-up data, watermarked):
    python notebooks/08_charts.py --test <csv> <out_dir>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TEST = "--test" in sys.argv
args = [a for a in sys.argv[1:] if a != "--test"]
CSV = args[0] if args else "data/gold/gold_yearly.csv"
OUT = args[1] if len(args) > 1 else "outputs"
STORAGE_CSV = "data/raw/storage_costs.csv"  # read only, never changed

if not os.path.exists(CSV):
    print(f"STOPPED: {CSV} not found. Build it first with notebooks/07_build_gold.py.")
    sys.exit(1)

df = pd.read_csv(CSV, na_values="MISSING")
CASES = ("low", "mid", "high")
need = ["decision_year", "state", "region_id", "gap_oct_cents", "breakeven_storage_cents"] + \
       [f"storage_{c}_cents" for c in CASES] + [f"store_wins_{c}" for c in CASES]
if df[need].isna().any().any():
    print("STOPPED: missing values in", df[need].columns[df[need].isna().any()].tolist())
    sys.exit(1)
storage = pd.read_csv(STORAGE_CSV)
X_COL, Y_COL = "gap_oct_cents", "breakeven_storage_cents"

# Colors. States: categorical slots 1, 3, 4, 5, 6, 8 (orange left out: it means storage in the bar
# chart). No 6-color set passes the all-pairs colorblind check (best: CVD dE 6.1, normal 13.2), so each
# state also has its own marker shape (user decision 2026-11-21); state names are in the legend.
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
STATE_STYLE = {"IL": ("#2a78d6", "o"), "IA": ("#1baf7a", "s"), "NE": ("#eda100", "^"),
               "SD": ("#e87ba4", "D"), "MN": ("#008300", "v"), "IN": ("#e34948", "P")}
STATES = [s for s in STATE_STYLE if s in set(df["state"])]
if not set(df["state"]) <= set(STATE_STYLE):
    print("STOPPED: no color for states", sorted(set(df["state"]) - set(STATE_STYLE)))
    sys.exit(1)
# Scatter storage cases in neutral gray (so they never compete with the state colors)
GRAY_STYLE = {"low": ("#52514e", (0, (1, 1.5))), "mid": ("#8a8984", 0.16), "high": ("#52514e", 0.16)}
# Bar chart: blue bars; storage cases one orange hue light -> dark (ordinal ramp, validated)
BAR_COLOR = "#2a78d6"
HURDLE_STYLE = {"low": ("#f29a70", (0, (1, 1.5)), "low: on-farm"),
                "mid": ("#eb6834", (0, (4, 2)), "mid"),
                "high": ("#a8400f", "-", "high: commercial")}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def watermark(fig):
    if TEST:
        fig.text(0.5, 0.5, "TEST DATA - NOT REAL", ha="center", va="center", fontsize=40,
                 color="#d0021b", alpha=0.25, rotation=25)


def fit(x, y):
    # Ordinary least squares line and its R² (squared correlation)
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept, np.corrcoef(x, y)[0, 1] ** 2


def fit_state_effects(d):
    # OLS of y on x plus one dummy per state (IL = baseline): one common slope, one intercept per state
    others = [s for s in STATES if s != "IL"]
    Xm = np.column_stack([np.ones(len(d)), d[X_COL]] + [(d["state"] == s).astype(float) for s in others])
    beta, *_ = np.linalg.lstsq(Xm, d[Y_COL].to_numpy(), rcond=None)
    resid = d[Y_COL] - Xm @ beta
    r2 = 1 - (resid ** 2).sum() / ((d[Y_COL] - d[Y_COL].mean()) ** 2).sum()
    return beta[1], beta[0], dict(zip(others, beta[2:])), r2


# ---------------------------------------------------------------- regressions and checks
n = len(df)
slope, intercept, r2 = fit(df[X_COL], df[Y_COL])
print(f"Pooled OLS {Y_COL} ~ {X_COL}: slope = {slope:.4f}, intercept = {intercept:.4f}, R² = {r2:.4f}, n = {n}")
fe_slope, fe_icpt, fe_eff, fe_r2 = fit_state_effects(df)
print(f"With state fixed effects: slope = {fe_slope:.4f}, R² = {fe_r2:.4f}, n = {n}; "
      f"intercept IL = {fe_icpt:.2f}; other states vs IL: "
      + ", ".join(f"{s} {v:+.2f}" for s, v in fe_eff.items()))

assert storage["storage_low_cents"].nunique() == 1, "low case is expected to be one value for all years"
low_cost = storage["storage_low_cents"].iloc[0]
x_at_low = (low_cost - intercept) / slope       # Oct gap where the pooled line reaches the low cost
x_min, x_max = df[X_COL].min(), df[X_COL].max()
in_range = x_min <= x_at_low <= x_max
print(f"X (Oct gap where the pooled line reaches {low_cost:g}¢) = {x_at_low:.1f}¢ "
      f"({'inside' if in_range else 'OUTSIDE'} the observed range {x_min:.1f} to {x_max:.1f}¢)")

# Dots above each case: low = the fixed 9¢; mid and high = each year's own cost.
# Must equal store_wins_c in gold (net gain > 0 is the same as breakeven > storage).
wins = {}
for c in CASES:
    above = int((df[Y_COL] > df[f"storage_{c}_cents"]).sum())
    wins[c] = int(df[f"store_wins_{c}"].astype(str).isin(["True", "1"]).sum())
    print(f"dots above {c}: {above} of {n} (gold store_wins_{c}: {wins[c]})")
    if above != wins[c]:
        print("STOPPED: dot count does not match gold")
        sys.exit(1)

band = {c: (storage[f"storage_{c}_cents"].min(), storage[f"storage_{c}_cents"].max()) for c in ("mid", "high")}
overlap = (max(band["mid"][0], band["high"][0]), min(band["mid"][1], band["high"][1]))
has_overlap = overlap[0] < overlap[1]

# ---------------------------------------------------------------- 1. decision scatter
fig, ax = plt.subplots(figsize=(10, 7))
ax.grid(color=GRID, lw=0.6, zorder=0)
pad_x = 0.04 * (x_max - x_min)
XL = (x_min - pad_x, x_max + 0.22 * (x_max - x_min))           # room on the right for band labels
YL = (min(0, df[Y_COL].min() - 5), max(band["high"][1], df[Y_COL].max()) + 8)
ax.axhline(0, color=INK_2, lw=0.8, zorder=1)
for c in ("mid", "high"):
    color, alpha = GRAY_STYLE[c]
    lo, hi = band[c]
    ax.axhspan(lo, hi, color=color, alpha=alpha, lw=0, zorder=1)
    label_y = (lo + hi) / 2 if c == "high" else (lo + (overlap[0] if has_overlap else hi)) / 2
    name = HURDLE_STYLE[c][2]
    ax.text(XL[1] - 0.5, label_y, f"{name}\n{lo:g}-{hi:g}¢", ha="right", va="center", fontsize=8.5,
            color=INK_2, zorder=4)
if has_overlap:
    ax.text(XL[1] - 0.5, overlap[1] + 0.3, f"mid and high overlap at {overlap[0]:g}-{overlap[1]:g}¢",
            ha="right", va="bottom", fontsize=7.5, color=INK_2, style="italic", zorder=4)
color, ls = GRAY_STYLE["low"]
ax.axhline(low_cost, color=color, ls=ls, lw=2, zorder=2)
ax.text(XL[1] - 0.5, low_cost + 0.8, f"low: on-farm {low_cost:g}¢", ha="right", va="bottom",
        fontsize=8.5, color=INK_2, zorder=4)

for st in STATES:
    d = df[df["state"] == st]
    color, marker = STATE_STYLE[st]
    ax.scatter(d[X_COL], d[Y_COL], s=34, color=color, marker=marker, alpha=0.75, edgecolor=SURFACE,
               linewidth=0.8, zorder=5, label=f"{st} (n = {len(d)})")

xs = np.linspace(x_min, x_max, 50)          # pooled line only over the observed Oct gaps
ax.plot(xs, intercept + slope * xs, color=INK, lw=2, zorder=6,
        label=f"Pooled OLS: y = {intercept:.2f} + {slope:.3f}x\nR² = {r2:.2f}, n = {n}")
if in_range:
    ax.axvline(x_at_low, color=INK_2, ls="--", lw=1.2, zorder=3)
    ax.text(x_at_low + 0.8, YL[1] - 3, f"Oct gap > {x_at_low:.1f}¢ → on-farm storage pays (pooled line, on average)",
            fontsize=9, color=INK, va="top", zorder=4)
else:
    ax.text(XL[0] + 1, low_cost - 1.5,
            f"Pooled line stays above {low_cost:g}¢ at every observed Oct gap "
            f"({x_min:.0f}-{x_max:.0f}¢): on-farm storage paid on average throughout.",
            fontsize=8.5, color=INK_2, va="top", zorder=4)

ax.set_xlim(*XL)
ax.set_ylim(*YL)
ax.set_xlabel("October gap: May futures − cash (cents/bu), known on Oct 15")
ax.set_ylabel("Gap closed − interest (cents/bu)\n= what was left to pay for storage")
fig.suptitle("Does a wider October gap leave more to pay for storage?", x=0.01, ha="left", fontsize=12)
ax.set_title("Dots above a band: storing beat selling at that storage cost "
             "(a band spans the years' costs; inside it, it depends on that year).\n"
             f"Country Elevators, every region in {len(STATES)} states, decision years "
             f"{df['decision_year'].min()}-{df['decision_year'].max()}.",
             loc="left", fontsize=9, color=INK_2)
ax.legend(frameon=False, loc="lower right", fontsize=8.5, ncol=2)
watermark(fig)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scatter_gap.png"), dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 2. one-panel bars by year
years = sorted(df["decision_year"].unique())
g = df.groupby("decision_year")[Y_COL]
stats = pd.DataFrame({"n_regions": g.size(), "p10": g.quantile(0.10), "median": g.median(),
                      "p90": g.quantile(0.90)})
won = df.groupby("decision_year")[[f"store_wins_{c}" for c in CASES]].mean().mul(100)
won.columns = list(CASES)
print("\nLeft for storage by year (cents/bu) and % of regions where storing won:")
print(pd.concat([stats.round(1), won.round(0).astype(int).add_prefix("% won ")], axis=1).to_string())

x = np.arange(len(years))
fig, ax = plt.subplots(figsize=(12, 6.2))
ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
ax.axhline(0, color=INK_2, lw=0.8, zorder=1)
ax.bar(x, stats["median"], 0.5, color=BAR_COLOR, edgecolor=SURFACE, linewidth=2, zorder=2)
ax.errorbar(x, stats["median"], yerr=[stats["median"] - stats["p10"], stats["p90"] - stats["median"]],
            fmt="none", ecolor=INK, elinewidth=1.2, capsize=5, zorder=4)
for xi, v in zip(x, stats["median"]):
    ax.text(xi, 1.2, f"{v:.1f}", ha="center", va="bottom", fontsize=8, color="white", zorder=5)
# Storage costs by year as step lines across the year slots
cost = storage.set_index("decision_year").reindex(years)
edges = np.append(x - 0.5, x[-1] + 0.5)
for c in CASES:
    color, ls, label = HURDLE_STYLE[c]
    vals = cost[f"storage_{c}_cents"].to_numpy()
    ax.step(edges, np.append(vals, vals[-1]), where="post", color=color, ls=ls, lw=2.2, zorder=3)
    ax.annotate(f"{label} storage", (edges[-1], vals[-1]), xytext=(4, 0), textcoords="offset points",
                fontsize=8.5, color=INK_2, va="center")
ax.set_xticks(x, [f"{y}\n{won.loc[y, 'low']:.0f}% / {won.loc[y, 'mid']:.0f}% / {won.loc[y, 'high']:.0f}%\n"
                  f"n = {stats.loc[y, 'n_regions']}" for y in years])
ax.set_xlim(-0.6, len(years) - 0.4 + 0.9)
ax.set_xlabel("Decision year (Oct to next Apr).  Under each year: % of regions where storing won, "
              "low / mid / high storage cost;  n = regions")
ax.set_ylabel("Gap closed − interest (cents/bu)\n= what was left to pay for storage")
fig.suptitle("What was left to pay for storage, by year, against three storage costs", x=0.01, ha="left",
             fontsize=12)
ax.set_title("Bar = median across regions; whisker = 10th to 90th percentile. "
             f"Country Elevators, every region in {len(STATES)} states. Storing wins where a region is above a line.",
             loc="left", fontsize=9, color=INK_2)
watermark(fig)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "bars_by_year.png"), dpi=150)
plt.close(fig)

print(f"\nSaved {OUT}/scatter_gap.png and {OUT}/bars_by_year.png")
