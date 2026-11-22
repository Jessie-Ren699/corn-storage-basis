"""Step 03: build the silver table of current corn cash bids, 6 states.

Input : data/raw/usda_bids/manifest.csv, the list of every raw USDA grain-bid file:
          IL (report 3192): data/raw/3192_YYYY-MM.csv (12 Oct/Apr pulls; the test file is not listed)
          IA 2850, NE 3225, SD 3186, MN 3049, IN 3463: data/raw/usda_bids/<STATE>/<report_id>_YYYY-MM.csv
        Months with no data (IN 2020-10) have no file and are skipped.
Output: data/clean/corn_bids_current.csv

Run from the project folder:
    python notebooks/03_build_silver.py              # build + summary, no save if output exists
    python notebooks/03_build_silver.py --overwrite  # replace an existing output file

data/raw/ is only read, never changed.
"""
import hashlib
import os
import sys

import pandas as pd

MANIFEST = "data/raw/usda_bids/manifest.csv"
STATES = ["IL", "IA", "NE", "SD", "MN", "IN"]
OUT = "data/clean/corn_bids_current.csv"
MISSING = "MISSING"

KEEP = ["report_date", "state", "commodity", "trade_loc", "delivery_point", "current",
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

# 1. Read every file listed in the manifest; each must exist and match its recorded checksum
man = pd.read_csv(MANIFEST)
man = man[man["file"].notna()]                        # MISSING months have no file
assert sorted(set(man["state"])) == sorted(STATES), f"states in manifest: {sorted(set(man['state']))}"
missing_files = [f for f in man["file"] if not os.path.exists(f)]
assert not missing_files, f"raw files not found: {missing_files}"
changed = [f for f, h in zip(man["file"], man["sha256"])
           if hashlib.sha256(open(f, "rb").read()).hexdigest() != h]
assert not changed, f"raw files differ from the manifest checksum: {changed}"
raw = pd.concat([pd.read_csv(f).assign(state=s) for f, s in zip(man["file"], man["state"])],
                ignore_index=True)

# 2. Keep only the needed columns
df = raw[KEEP].copy()

# 3. Corn, current delivery, Yellow only; all regions and buyer types kept
#    (Yellow filter added 2026-11-21: Indiana also reports White corn, a different product;
#     futures are for Yellow #2. Illinois is all Yellow, so its rows are unchanged.)
counts = [("raw", len(df))]
df = df[df["commodity"] == "Corn"];  counts.append(("corn only", len(df)))
df = df[df["current"] == "Yes"];     counts.append(("deliver now only", len(df)))
df = df[df["class"] == "Yellow"];    counts.append(("Yellow corn only", len(df)))

# 4. Rename; current "Yes"/"No" -> True/False
df = df.rename(columns=RENAME)
df["deliver_now"] = df["deliver_now"].map({"Yes": True, "No": False})

# 5. Real dates (USDA format is MM/DD/YYYY)
df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")

# 6. Drop the 8 empty ¢/Bu rows (Illinois, South Illinois River barge, Oct 2022, no price).
# Each one shares its key with a real "$ Per Bushel" row, so no price is lost.
empty_cents = (df["price_unit"] == "¢/Bu") & df[PRICE_COLS].isna().all(axis=1)
assert empty_cents.sum() == 8, f"expected 8 empty ¢/Bu rows, found {empty_cents.sum()}"
df = df[~empty_cents];               counts.append(("drop empty ¢/Bu rows", len(df)))

# 7. Duplicate check: must be 0 on the primary key.
# transport_mode is in the key because Indiana's Ohio River barge elevators post a Truck and a
# Truck/Rail bid on the same day.
PK = ["date", "state", "region", "buyer_type", "transport_mode"]
n_dup = int(df.duplicated(PK).sum())
if n_dup > 0:
    print(f"STOPPED: {n_dup} duplicate rows on {PK}. Nothing saved.")
    print(df[df.duplicated(PK, keep=False)].sort_values(PK).to_string(index=False))
    sys.exit(1)

# 8. Primary key: no blanks, and the table is sorted by it
assert df[PK].notna().all().all(), "primary key has blank values"
df = df.sort_values(PK).reset_index(drop=True)

# Any other blank prices stay blank (never filled); written as MISSING in the CSV.
n_missing = df[PRICE_COLS].isna().sum()

# Summary
for (_, before), (step, after) in zip(counts, counts[1:]):
    print(f"{step}: {before:,} → {after:,}")
print(f"duplicates on {PK}: {n_dup}  -> primary key is unique")
print("date range:", df["date"].min().date(), "to", df["date"].max().date())
print("rows by state:", df["state"].value_counts().reindex(STATES).to_dict())
for c in ["price_unit", "grain_class", "grain_grade", "price_point", "transport_mode", "deliver_now"]:
    print(f"{c}:", df[c].value_counts(dropna=False).to_dict())
print("MISSING prices per column:", n_missing.to_dict())

# 9. Save (refuses to replace an existing file unless --overwrite is given)
if os.path.exists(OUT) and "--overwrite" not in sys.argv:
    print(f"\nNOT SAVED: {OUT} already exists. Re-run with --overwrite to replace it.")
else:
    df.to_csv(OUT, index=False, na_rep=MISSING, date_format="%Y-%m-%d")
    print(f"\nSaved {OUT} ({len(df)} rows)")
