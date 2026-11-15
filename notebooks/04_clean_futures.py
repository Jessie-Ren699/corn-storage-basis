"""Clean May corn futures settlements.

Input:  data/raw/may_futures.csv   (never modified)
Output: data/clean/may_futures.csv

Steps:
1. Rename contract -> futures_contract.
2. Add contract_name (e.g. ZCK21 -> "May 2021 corn").
3. Add leg from the date's month (Oct = open hedge, Apr = close hedge).
4. Keep all other columns unchanged.
5. Convert settle_raw (cents and eighths, e.g. 583-2) to may_futures_price in $/bu.
   Blank settle_raw rows stay blank (MISSING); nothing is filled or guessed.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/may_futures.csv"
CLEAN = ROOT / "data/clean/may_futures.csv"

# Read as strings so nothing in the raw values gets reinterpreted
df = pd.read_csv(RAW, dtype=str, keep_default_na=False)

# 1. Rename
df = df.rename(columns={"contract": "futures_contract"})

# 2. Contract code -> words. ZC = corn, K = May, 21 = 2021.
MONTHS = {"K": "May"}  # only May is expected; anything else should fail loudly
def contract_name(code):
    m = re.fullmatch(r"ZC([A-Z])(\d{2})", code)
    if not m or m.group(1) not in MONTHS:
        raise ValueError(f"Unexpected contract code: {code}")
    return f"{MONTHS[m.group(1)]} 20{m.group(2)} corn"
df["contract_name"] = df["futures_contract"].map(contract_name)

# 3. Leg from the date's month
LEGS = {10: "Oct (open hedge)", 4: "Apr (close hedge)"}
month = pd.to_datetime(df["date"]).dt.month
if not month.isin(LEGS.keys()).all():
    raise ValueError(f"Unexpected months: {sorted(set(month) - set(LEGS))}")
df["leg"] = month.map(LEGS)

# 5. Cents and eighths -> $/bu: "583-2" = 583 + 2/8 cents = $5.8325.
# Reading "583-2" as 583.2 would be wrong, so the format is checked strictly.
# Not rounded: odd eighths need 5 decimals (583-1 = $5.83125).
def to_dollars(raw):
    raw = raw.strip()
    if raw == "":
        return None  # MISSING: skip blank rows for now
    m = re.fullmatch(r"(\d+)-([0-7])", raw)
    if not m:
        raise ValueError(f"Unexpected settle_raw format: {raw!r} (expected e.g. 583-2)")
    cents = int(m.group(1)) + int(m.group(2)) / 8
    return cents / 100
df["may_futures_price"] = df["settle_raw"].map(to_dollars).astype(float)

# Column order: descriptive columns before the price and source
df = df[["decision_year", "date", "futures_contract", "contract_name", "leg",
         "settle_raw", "source", "may_futures_price"]]

missing = df["may_futures_price"].isna().sum()
print(f"Rows: {len(df)}, MISSING may_futures_price: {missing}")

df.to_csv(CLEAN, index=False)
print(f"Saved {CLEAN.relative_to(ROOT)}")
print(df.to_string(index=False))
