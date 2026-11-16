"""FGP side project, step 03: build the river basis panel. One row = region x trading day.

Inputs : data/raw/3192_{2021,2022}-10.csv (Oct, shared with the main project)
         fgp_river_basis/data/raw/3192_{2021,2022}-{08,09,11}.csv (FGP only)
         fgp_river_basis/data/raw/usgs_07032000_flow_2021-08_2022-11.rdb
Output : fgp_river_basis/data/river_basis_panel.csv

Run from the project folder:
    python fgp_river_basis/notebooks/fgp_03_build_panel.py              # build + summary, no save if output exists
    python fgp_river_basis/notebooks/fgp_03_build_panel.py --overwrite  # replace an existing output file

Decisions (user, 2026-11-11):
- 4 regions; River = 1 for North and South Illinois River (barge loading elevators).
- basis_cents = (basis Min + basis Max) / 2, in cents/bu. Exception to the $/bu rule,
  for this side project only.
- Futures month as reported; keep only dates where all 4 regions are quoted against
  December (Z) on both the low and the high bid.
- Post = 1 from Oct 1 in both years (option b, user decision 2026-11-11). The first rule
  (Post from Sept 15) left 2022 with no Post = 0 rows, because 2022's first all-December
  date is Sept 15 itself.
- river_flow_cfs = USGS Memphis daily mean flow (one value per day, same for all regions).
- Drought index skipped for now (listed as a limitation).
Raw files are only read, never changed.
"""
import os
import sys

import pandas as pd

YEARS = [2021, 2022]
MONTHS = [8, 9, 10, 11]
# Oct pulls are also used by the main project, so they stay in data/raw/ (moved 2026-11-15).
SHARED_RAW = "data/raw"
FGP_RAW = "fgp_river_basis/data/raw"
RAW_3192 = [f"{SHARED_RAW if m == 10 else FGP_RAW}/3192_{y}-{m:02d}.csv" for y in YEARS for m in MONTHS]
RAW_USGS = f"{FGP_RAW}/usgs_07032000_flow_2021-08_2022-11.rdb"
OUT = "fgp_river_basis/data/river_basis_panel.csv"
MISSING = "MISSING"
Z = "December (Z)"

REGIONS = {  # region -> River dummy; all four checked to have one buyer type each
    "North Illinois River": 1,  # Barge Loading Elevators
    "South Illinois River": 1,  # Barge Loading Elevators
    "North Central": 0,         # Country Elevators
    "South Central": 0,         # Country Elevators
}

# 1. USDA bids: corn, current delivery, the 4 regions
raw = pd.concat([pd.read_csv(f) for f in RAW_3192], ignore_index=True)
df = raw[(raw["commodity"] == "Corn") & (raw["current"] == "Yes")
         & raw["trade_loc"].isin(REGIONS)].copy()
df["date"] = pd.to_datetime(df["report_date"], format="%m/%d/%Y")
n_start = len(df)

# 2. Drop empty duplicate rows: USDA sometimes adds a second row for the same
# date x region with price_unit "¢/Bu" and no basis or price at all. Each one has a
# real twin row, so no data is lost (same quirk handled in 03_build_silver.py).
empty = df["basis_unit"].isna() & df[["basis Min", "basis Max", "avg_price"]].isna().all(axis=1)
key = ["date", "trade_loc"]
assert df[empty].set_index(key).index.isin(df[~empty].set_index(key).index).all(), \
    "an empty row has no real twin"
df = df[~empty]
assert not df.duplicated(key).any(), "duplicate date x region rows"

# 3. Basis midpoint and futures month
df["basis_cents"] = (df["basis Min"] + df["basis Max"]) / 2
df["futures_month"] = df["basis Min Futures Month"].where(
    df["basis Min Futures Month"] == df["basis Max Futures Month"],
    df["basis Min Futures Month"] + " / " + df["basis Max Futures Month"])  # mixed range

# 4. Keep only dates where all 4 regions are quoted vs December on both the low and the high
df["is_z"] = (df["basis Min Futures Month"] == Z) & (df["basis Max Futures Month"] == Z)
by_date = df.groupby("date").agg(n=("is_z", "size"), all_z=("is_z", "all"))
keep_dates = by_date.index[(by_date["n"] == len(REGIONS)) & by_date["all_z"]]
dropped_dates = by_date.index.difference(keep_dates)

switch = {y: keep_dates[keep_dates.year == y].min() for y in YEARS}
# Dates that are not all-December but come after the switch (e.g. the roll to March)
late = {y: [d.date() for d in dropped_dates if d.year == y and d > switch[y]] for y in YEARS}
df = df[df["date"].isin(keep_dates)].copy()

# 5. Dummies
df["region"] = df["trade_loc"]
df["River"] = df["region"].map(REGIONS)
df["Y2022"] = (df["date"].dt.year == 2022).astype(int)
post_start = {y: pd.Timestamp(y, 10, 1) for y in YEARS}  # same cutoff both years
df["Post"] = (df["date"] >= df["date"].dt.year.map(post_start)).astype(int)

# 6. USGS Memphis flow (rdb = tab-separated, '#' comment lines, then a format line)
flow = pd.read_csv(RAW_USGS, sep="\t", comment="#", dtype=str).iloc[1:]  # skip "5s 15s ..." line
val_col = [c for c in flow.columns if c.endswith("_00060_00003")][0]
flow = pd.DataFrame({"date": pd.to_datetime(flow["datetime"]),
                     "river_flow_cfs": pd.to_numeric(flow[val_col], errors="coerce"),
                     "flow_code": flow[val_col + "_cd"]})
df = df.merge(flow[["date", "river_flow_cfs"]], on="date", how="left")  # blanks stay blank
# Flow in units of 100,000 cfs, so a regression coefficient reads "per 100k cfs" (user, 2026-11-11)
df["flow_100k"] = df["river_flow_cfs"] / 100_000

# 7. Final table
COLS = ["date", "region", "basis_cents", "futures_month", "River", "Y2022", "Post", "river_flow_cfs", "flow_100k"]
df = df[COLS].sort_values(["date", "region"]).reset_index(drop=True)
assert not df.duplicated(["date", "region"]).any()

# Summary
print(f"bid rows (corn, current, 4 regions): {n_start}; empty twin rows dropped: {int(empty.sum())}")
print(f"trading days: {by_date.shape[0]}, kept {len(keep_dates)}, dropped {len(dropped_dates)} (not all-December)")
for y in YEARS:
    print(f"{y}: first all-December date {switch[y].date()}; Post starts {post_start[y].date()}; "
          f"non-December dates after the switch (dropped): {late[y]}")
print("USGS flow codes in the panel window:",
      flow[flow["date"].isin(df["date"])]["flow_code"].value_counts().to_dict())
print(f"\nrows: {len(df)}")
print(df.groupby([df["date"].dt.year.rename("year"), "Post"]).size().unstack().to_string())
print("\nfirst 10 rows:")
print(df.head(10).to_string(index=False))
print("\nmissing values per column:", df.isna().sum().to_dict())
print("\nkey numbers:")
print(df.groupby("region")["basis_cents"].agg(["min", "max", "mean"]).round(1).to_string())
print(df["river_flow_cfs"].agg(["min", "max", "mean"]).round(0).to_string())

# 8. Save (refuses to replace an existing file unless --overwrite is given)
if os.path.exists(OUT) and "--overwrite" not in sys.argv:
    print(f"\nNOT SAVED: {OUT} already exists. Re-run with --overwrite to replace it.")
else:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False, na_rep=MISSING, date_format="%Y-%m-%d")
    print(f"\nSaved {OUT} ({len(df)} rows)")
