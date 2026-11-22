"""Step 08: charts from data/gold/gold_yearly.csv.

1. outputs/scatter_gap.png   "decision" chart: x = gap_oct_cents (known on Oct 15),
                             y = breakeven_storage_cents (gap closed - interest = what was left
                             to pay for storage). One dot per region-year, colored by state;
                             one pooled OLS line (slope, intercept, R², n in the legend);
                             storage cost cases from data/raw/storage_costs.csv: low = dotted
                             line, mid and high = shaded min-max bands. A dot above a case
                             means storing beat selling at that storage cost.
2. outputs/bars_by_year.png  gap_closed (green bar) vs. the three hurdles (storage + interest)
                             for the low / mid / high storage cases, by decision year,
                             one panel per region. Storing wins where the bar is above a line.

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
STORAGE_CSV = "data/raw/storage_costs.csv"  # read only, never changed
OUT = args[1] if len(args) > 1 else "outputs"

if not os.path.exists(CSV):
    print(f"STOPPED: {CSV} not found. Build it first with notebooks/07_build_gold.py.")
    sys.exit(1)

df = pd.read_csv(CSV, na_values="MISSING")
CASES = ("low", "mid", "high")
need = ["decision_year", "region", "gap_oct_cents", "gap_closed_cents", "interest_cents",
        "breakeven_storage_cents"] + [f"hurdle_{c}_cents" for c in CASES] + \
       [f"storage_{c}_cents" for c in CASES] + [f"store_wins_{c}" for c in CASES]
if df[need].isna().any().any():
    print("STOPPED: missing values in", df[need].columns[df[need].isna().any()].tolist())
    sys.exit(1)

# Colors (validated for colorblind separation). Each color has one meaning across
# both charts; orange = interest in both.
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
REGION_COLOR = {"North Central": "#2a78d6", "South Central": "#7b2d8e"}  # blue, purple
GAP_COLOR, INTEREST_COLOR = "#006300", "#eb6834"                         # green, orange
POOLED_COLOR = "#8a8984"                                                 # gray
# Hurdles: one orange hue, light -> dark = low -> high storage cost (ordinal ramp, validated).
# Line style and a text label are a second cue, so the cases never rely on color alone.
HURDLE_STYLE = {"low": ("#f29a70", (0, (1, 1.5)), "low: on-farm"),
                "mid": ("#eb6834", (0, (4, 2)), "mid"),
                "high": ("#a8400f", "-", "high: commercial")}
REGIONS = [r for r in REGION_COLOR if r in set(df["region"])]
# Scatter dots are colored by state. The gold table is Illinois only for now (07 filters
# state = IL) and has no state column, so every dot is IL until other states are added.
STATE_COLOR = {"IL": "#2a78d6"}                                          # blue
LINE_COLOR = INK_2                                                       # pooled line: neutral ink

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


# 1. Decision chart: Oct gap (known on Oct 15) vs. what was left to pay for storage
x_col, y_col = "gap_oct_cents", "breakeven_storage_cents"
state = df["state"] if "state" in df.columns else pd.Series("IL", index=df.index)
if not set(state) <= set(STATE_COLOR):
    print("STOPPED: no color for states", sorted(set(state) - set(STATE_COLOR)))
    sys.exit(1)
storage = pd.read_csv(STORAGE_CSV)

# Pooled OLS of y on x, both regions, all years
slope, intercept, r2 = fit(df[x_col], df[y_col])
n = len(df)
low_cost = storage["storage_low_cents"].iloc[0]
assert storage["storage_low_cents"].nunique() == 1, "low case is expected to be one value for all years"
x_at_low = (low_cost - intercept) / slope     # Oct gap where the pooled line reaches the low cost
x_min, x_max = df[x_col].min(), df[x_col].max()
print(f"Pooled OLS {y_col} ~ {x_col}: slope = {slope:.4f}, intercept = {intercept:.4f}, "
      f"R² = {r2:.4f}, n = {n}")
in_range = x_min <= x_at_low <= x_max
print(f"X (Oct gap where the line reaches {low_cost:g}¢) = {x_at_low:.1f}¢ "
      f"({'inside' if in_range else 'OUTSIDE'} the observed range {x_min:.1f} to {x_max:.1f}¢)")

# Dots above each case: low = the fixed 9¢; mid and high = each year's own cost.
# Must equal store_wins_c in gold (net gain > 0 is the same as breakeven > storage).
for c in CASES:
    above = int((df[y_col] > df[f"storage_{c}_cents"]).sum())
    wins = int(df[f"store_wins_{c}"].astype(str).isin(["True", "1"]).sum())
    print(f"dots above {c}: {above} of {n} (gold store_wins_{c}: {wins})")
    if above != wins:
        print("STOPPED: dot count does not match gold")
        sys.exit(1)

fig, ax = plt.subplots(figsize=(9, 6.2))
ax.grid(color=GRID, lw=0.6, zorder=0)
XL, YL = (20, 80), (0, 70)
# Storage cost cases: mid and high as shaded min-max bands, low as a dotted line
high_lo = storage["storage_high_cents"].min()   # mid label sits below the high band
for c, alpha in (("mid", 0.16), ("high", 0.22)):
    color, _, label = HURDLE_STYLE[c]
    lo, hi = storage[f"storage_{c}_cents"].min(), storage[f"storage_{c}_cents"].max()
    ax.axhspan(lo, hi, color=color, alpha=alpha, lw=0, zorder=1)
    ax.text(XL[1] - 0.5, (lo + hi) / 2 if c == "high" else (lo + min(hi, high_lo)) / 2,
            f"{label}\n{lo:g}-{hi:g}¢", ha="right", va="center", fontsize=8.5, color=INK_2, zorder=4)
color, ls, label = HURDLE_STYLE["low"]
ax.axhline(low_cost, color=color, ls=ls, lw=2.2, zorder=2)
ax.text(XL[1] - 0.5, low_cost + 1.2, f"{label} {low_cost:g}¢", ha="right", va="bottom",
        fontsize=8.5, color=INK_2, zorder=4)

# Dots: one per region-year, colored by state, small and slightly transparent
for st in sorted(set(state)):
    d = df[state == st]
    ax.scatter(d[x_col], d[y_col], s=38, color=STATE_COLOR[st], alpha=0.8, edgecolor=SURFACE,
               linewidth=1, zorder=5, label=f"{st} (n = {len(d)} region-years)")

# One pooled line, drawn only over the observed Oct gaps (no extrapolation)
xs = np.linspace(x_min, x_max, 50)
ax.plot(xs, intercept + slope * xs, color=LINE_COLOR, lw=2, zorder=6,
        label=f"Pooled OLS: y = {intercept:.2f} + {slope:.3f}x, R² = {r2:.2f}, n = {n}")
if not in_range:
    ax.text(x_min, 3, f"Pooled line stays above {low_cost:g}¢ at every observed Oct gap "
            f"({x_min:.0f}-{x_max:.0f}¢): on-farm storage paid throughout.",
            fontsize=8.5, color=INK_2, ha="left", va="bottom", zorder=4)

ax.set_xlim(*XL)
ax.set_ylim(*YL)
ax.set_xlabel("October gap: May futures − cash (cents/bu), known on Oct 15")
ax.set_ylabel("Gap closed − interest (cents/bu)\n= what was left to pay for storage")
fig.suptitle("Does a wider October gap leave more to pay for storage?", x=0.01, ha="left",
             fontsize=12)
ax.set_title("Dots above a band: storing beat selling at that storage cost "
             "(a band spans the years' costs; inside it, it depends on that year).\n"
             "Illinois Country Elevators, North + South Central, decision years 2020-2025.",
             loc="left", fontsize=9, color=INK_2)
ax.legend(frameon=False, loc="upper left", fontsize=9)
watermark(fig)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "scatter_gap.png"), dpi=150)
plt.close(fig)

# 2. Gap closed (bar) vs. the three hurdles (short lines), one panel per region.
# Hurdle = storage (that case) + interest. Storing wins where the bar top is above the line.
years = sorted(df["decision_year"].unique())
x = np.arange(len(years))
w = 0.5
fig, axes = plt.subplots(1, len(REGIONS), figsize=(13, 5.6), sharey=True)
axes = np.atleast_1d(axes)
for ax, region in zip(axes, REGIONS):
    d = df[df["region"] == region].set_index("decision_year").reindex(years)
    ax.axhline(0, color=INK_2, lw=0.8, zorder=1)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    bars = ax.bar(x, d["gap_closed_cents"], w, color=GAP_COLOR, edgecolor=SURFACE, linewidth=2,
                  zorder=2, label="Gap closed (Y)")
    # Value label inside the bar near its base (white on dark green), clear of the hurdle lines;
    # the hurdle values are in gold_yearly.csv
    for xi, v in zip(x, d["gap_closed_cents"]):
        ax.text(xi, 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=8, color="white", zorder=4)
    for c in CASES:
        color, ls, label = HURDLE_STYLE[c]
        ax.hlines(d[f"hurdle_{c}_cents"], x - w * 0.75, x + w * 0.75, colors=color, linestyles=ls,
                  lw=2.5, zorder=3, label=f"Hurdle, {label} (storage + interest)")
    # Direct labels for the three lines, at the right of the last year
    last = d.iloc[-1]
    for c in CASES:
        ax.annotate(c, (x[-1] + w * 0.75, last[f"hurdle_{c}_cents"]), xytext=(3, 0),
                    textcoords="offset points", fontsize=8, color=INK_2, va="center")
    wins = {c: int(d[f"hurdle_{c}_cents"].lt(d["gap_closed_cents"]).sum()) for c in CASES}
    ax.set_title(f"{region}   (storing wins: low {wins['low']}/{len(years)}, "
                 f"mid {wins['mid']}/{len(years)}, high {wins['high']}/{len(years)})",
                 loc="left", fontsize=10)
    ax.set_xticks(x, [str(y) for y in years])
    ax.set_xlim(-0.6, len(years) - 0.2)
    ax.set_xlabel("Decision year (Oct to next Apr)")
axes[0].set_ylabel("cents/bu")
# Legend above the panels so it never covers a bar
handles, labels = axes[0].get_legend_handles_labels()
order = [labels.index("Gap closed (Y)")] + [i for i, l in enumerate(labels) if l != "Gap closed (Y)"]
fig.legend([handles[i] for i in order], [labels[i] for i in order], frameon=False,
           loc="upper right", ncol=2, fontsize=9)
fig.suptitle("Gap closed vs. the hurdle for three storage costs (Country Elevators)\n"
             "Storing beats selling at harvest where the green bar is above the line.",
             x=0.01, ha="left", fontsize=11)
watermark(fig)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "bars_by_year.png"), dpi=150)
plt.close(fig)

print(f"Saved {OUT}/scatter_gap.png and {OUT}/bars_by_year.png")
