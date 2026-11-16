"""FGP side project, step 04: basis-by-region chart.

Input : fgp_river_basis/data/river_basis_panel.csv
Output: fgp_river_basis/outputs/fgp_basis_chart.png

Colors: default categorical palette, slots 1-4, checked with the colorblind validator
(all checks pass). Two colors are low-contrast on white, so every line is labeled directly.
River regions are solid lines, country-elevator regions dashed (a second cue besides color).
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

IN = "fgp_river_basis/data/river_basis_panel.csv"
OUT = "fgp_river_basis/outputs/fgp_basis_chart.png"
COLORS = {"North Illinois River": "#2a78d6", "South Illinois River": "#eb6834",
          "North Central": "#1baf7a", "South Central": "#eda100"}

df = pd.read_csv(IN, parse_dates=["date"])
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for ax, y in zip(axs, (2021, 2022)):
    d = df[df["date"].dt.year == y]
    for region, color in COLORS.items():
        s = d[d["region"] == region]
        ax.plot(s["date"], s["basis_cents"], color=color, lw=2,
                ls="-" if "River" in region else (0, (4, 2)), label=region)
        ax.annotate(region, (s["date"].iloc[-1], s["basis_cents"].iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", fontsize=7.5, color="#3d3d3a", va="center")
    # Post rule = Oct 1 in both years (same as fgp_03). In 2022 Oct 1 is a Saturday,
    # so the first Post = 1 trading day is Oct 3; the line still marks the rule date.
    post = pd.Timestamp(y, 10, 1)
    assert d.loc[d["Post"] == 1, "date"].min() >= post > d.loc[d["Post"] == 0, "date"].max()
    ax.axvline(post, color="#8a8a85", lw=1, ls=":")
    ax.text(post, 10, "  Post = 1\n  from Oct 1", fontsize=8, color="#6b6b66", va="top")
    ax.set_title(str(y), loc="left", fontsize=11)
    ax.grid(axis="y", color="#e6e5e0", lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_xlim(pd.Timestamp(y, 9, 1), pd.Timestamp(y, 12, 20))
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
axs[0].set_ylabel("Basis vs December futures (cents/bu)")
axs[1].legend(fontsize=8, frameon=False, loc="lower left")
fig.suptitle("Corn basis, 4 Illinois regions (solid = barge-loading river, dashed = country elevator)",
             x=0.01, ha="left", fontsize=11)
fig.text(0.01, 0.005, "Source: USDA AMS report 3192 (midpoint of low/high bid). "
         "Only dates where all 4 regions quote December (Z).", fontsize=7.5, color="#6b6b66")
fig.tight_layout(rect=(0, 0.03, 1, 0.95))
fig.savefig(OUT, dpi=130)
print(f"Saved {OUT}")
