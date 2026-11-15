"""Step 08: charts from data/gold/gold_yearly.csv.

1. outputs/scatter_gap.png   x = gap_oct (X), y = gap_closed (Y), one color per region,
                             year labels, best-fit line per region and pooled (slope and
                             R² in the legend), orange dash at each year's interest hurdle.
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
OUT = args[1] if len(args) > 1 else "outputs"

if not os.path.exists(CSV):
    print(f"STOPPED: {CSV} not found. Build it first with notebooks/07_build_gold.py.")
    sys.exit(1)

df = pd.read_csv(CSV, na_values="MISSING")
CASES = ("low", "mid", "high")
need = ["decision_year", "region", "gap_oct_cents", "gap_closed_cents", "interest_cents"] + \
       [f"hurdle_{c}_cents" for c in CASES]
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


# 1. Scatter: gap_oct vs gap_closed, with each year's interest hurdle
fig, ax = plt.subplots(figsize=(9, 6.5))
ax.axhline(0, color=GRID, lw=1, zorder=0)
ax.grid(color=GRID, lw=0.6, zorder=0)
for region in REGIONS:
    d = df[df["region"] == region]
    c = REGION_COLOR[region]
    slope, intercept, r2 = fit(d["gap_oct_cents"], d["gap_closed_cents"])
    print(f"{region}: slope = {slope:.4f}, intercept = {intercept:.4f}, R² = {r2:.4f}, n = {len(d)}")
    # Thin line from each year's hurdle dash up (or down) to its dot
    ax.vlines(d["gap_oct_cents"], d["interest_cents"], d["gap_closed_cents"],
              color=c, lw=0.8, alpha=0.6, zorder=1)
    ax.scatter(d["gap_oct_cents"], d["gap_closed_cents"], s=60, color=c, edgecolor=SURFACE,
               linewidth=2, zorder=3,
               label=f"{region} (n = {len(d)}): slope {slope:.2f}, R² = {r2:.2f}")
    for _, r in d.iterrows():
        ax.annotate(str(int(r["decision_year"])), (r["gap_oct_cents"], r["gap_closed_cents"]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8, color=INK_2)
    xs = np.linspace(d["gap_oct_cents"].min(), d["gap_oct_cents"].max(), 50)
    ax.plot(xs, slope * xs + intercept, color=c, lw=2, zorder=2)

# Interest hurdle: one short orange dash per dot, at that year's interest cost
ax.plot(df["gap_oct_cents"], df["interest_cents"], linestyle="none", marker="_",
        markersize=14, markeredgewidth=2.5, color=INTEREST_COLOR, zorder=2,
        label="interest hurdle (varies by year)")

# Pooled best fit: both regions, all points
slope, intercept, r2 = fit(df["gap_oct_cents"], df["gap_closed_cents"])
print(f"Pooled: slope = {slope:.4f}, intercept = {intercept:.4f}, R² = {r2:.4f}, n = {len(df)}")
xs = np.linspace(df["gap_oct_cents"].min(), df["gap_oct_cents"].max(), 50)
ax.plot(xs, slope * xs + intercept, color=POOLED_COLOR, lw=2, linestyle="--", zorder=2,
        label=f"Pooled (n = {len(df)}): slope {slope:.2f}, R² = {r2:.2f}")

ax.set_xlabel("Oct gap: May futures minus cash (cents/bu)   [X]")
ax.set_ylabel("Gap closed, Oct to Apr (cents/bu)   [Y]")
ax.set_title("A wider October gap vs. how much of it closed by April\n"
             "Country Elevators, decision years 2020-2025.\n"
             "Orange dashes show the interest cost only; storage cases are in bars_by_year.png.",
             loc="left", fontsize=11)
ax.legend(frameon=False, loc="lower right", fontsize=9)
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
