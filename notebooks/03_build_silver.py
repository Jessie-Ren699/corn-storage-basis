"""Step 03: build the silver table of current corn cash bids from report 3192.

Input : data/raw/3192_YYYY-MM.csv (12 monthly pulls; the test file is skipped)
Output: data/clean/corn_bids_current.csv

Run from the project folder:
    python notebooks/03_build_silver.py              # build + summary, no save if output exists
    python notebooks/03_build_silver.py --overwrite  # replace an existing output file

data/raw/ is only read, never changed.
"""
import os
import sys

import pandas as pd

# The 12 Oct/Apr pulls, listed by name (2026-11-11). A glob ("3192_20*.csv") stopped
# working once the FGP side project added Aug/Sep/Nov files to data/raw/.
RAW_FILES = [f"data/raw/3192_{ym}.csv" for ym in [
    "2020-10",
    "2021-04", "2021-10",
    "2022-04", "2022-10",
    "2023-04", "2023-10",
    "2024-04", "2024-10",
    "2025-04", "2025-10",
    "2026-04",
]]
OUT = "data/clean/corn_bids_current.csv"
MISSING = "MISSING"

KEEP = ["report_date", "commodity", "trade_loc", "delivery_point", "current",
        "avg_price", "price Min", "price Max", "price_unit",
        "class", "grade", "freight", "trans_mode"]
RENAME = {
    "report_date": "date",
    "trade_loc": "region",
    "delivery_point": "buyer_type",
    "current": "deliver_now",
    "avg_price": "cash_price",
    "price Min": "cash_price_low",
    "price Max": "cash_price_high",
    "class": "grain_class",
    "grade": "grain_grade",
    "freight": "price_point",
    "trans_mode": "transport_mode",
}
PRICE_COLS = ["cash_price", "cash_price_low", "cash_price_high"]

# 1. Read the 12 monthly files
files = RAW_FILES
missing_files = [f for f in files if not os.path.exists(f)]
assert not missing_files, f"raw files not found: {missing_files}"
raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

# 2. Keep only the needed columns
df = raw[KEEP].copy()

# 3. Corn, current delivery only; all regions and buyer types kept
df = df[(df["commodity"] == "Corn") & (df["current"] == "Yes")]

# 4. Rename; current "Yes"/"No" -> True/False
df = df.rename(columns=RENAME)
df["deliver_now"] = df["deliver_now"].map({"Yes": True, "No": False})

# 5. Real dates (USDA format is MM/DD/YYYY)
df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
df = df.sort_values(["date", "region", "buyer_type"]).reset_index(drop=True)

# 6. Drop the 8 empty ¢/Bu rows (South Illinois River barge, Oct 2022, no price).
# Each one shares date/region/buyer_type with a real "$ Per Bushel" row, so no price is lost.
empty_cents = (df["price_unit"] == "¢/Bu") & df[PRICE_COLS].isna().all(axis=1)
assert empty_cents.sum() == 8, f"expected 8 empty ¢/Bu rows, found {empty_cents.sum()}"
df = df[~empty_cents].reset_index(drop=True)

# 7. Duplicate check: must be 0 on the primary key
PK = ["date", "region", "buyer_type"]
n_dup = int(df.duplicated(PK).sum())
if n_dup > 0:
    print(f"STOPPED: {n_dup} duplicate rows on {PK}. Nothing saved.")
    print(df[df.duplicated(PK, keep=False)].sort_values(PK).to_string(index=False))
    sys.exit(1)

# 8. Primary key (date, region, buyer_type): unique, and the table is sorted by it
assert df[PK].notna().all().all(), "primary key has blank values"
df = df.sort_values(PK).reset_index(drop=True)

# Any other blank prices stay blank (never filled); written as MISSING in the CSV.
n_missing = df[PRICE_COLS].isna().sum()

# Summary
print("rows:", len(df), f"(dropped {int(empty_cents.sum())} empty ¢/Bu rows)")
print(f"duplicates on {PK}: {n_dup}  -> primary key {PK} is unique")
print("date range:", df["date"].min().date(), "to", df["date"].max().date())
for c in ["price_unit", "grain_class", "grain_grade", "price_point", "transport_mode", "deliver_now"]:
    print(f"{c}:", df[c].value_counts(dropna=False).to_dict())
print("MISSING prices per column:", n_missing.to_dict())
print("rows with any MISSING price:", int(df[PRICE_COLS].isna().any(axis=1).sum()))
print(df[df[PRICE_COLS].isna().any(axis=1)][["date", "region", "buyer_type", "price_unit"]].to_string(index=False))

# 9. Save (refuses to replace an existing file unless --overwrite is given)
if os.path.exists(OUT) and "--overwrite" not in sys.argv:
    print(f"\nNOT SAVED: {OUT} already exists. Re-run with --overwrite to replace it.")
else:
    df.to_csv(OUT, index=False, na_rep=MISSING, date_format="%Y-%m-%d")
    print(f"\nSaved {OUT} ({len(df)} rows)")
