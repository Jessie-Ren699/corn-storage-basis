"""Step 05: T-bill rate for the hurdle, one row per decision date.

Input : data/raw/fred_dtb6.csv  (FRED DTB6, 6-month T-bill, percent; never modified)
Output: data/clean/tbill_decision.csv

Rule: for each decision date D, average DTB6 over the 10 calendar days
D-9 .. D (D included). Blank (holiday) rows are ignored, not filled.
No date after D is ever used.

Run from the project folder:
    python notebooks/05_tbill_rates.py
"""
import sys

import pandas as pd

RAW = "data/raw/fred_dtb6.csv"
OUT = "data/clean/tbill_decision.csv"
MISSING = "MISSING"
WINDOW_DAYS = 10

# Same dates as the Oct rows of data/clean/may_futures.csv
# (Oct 15, or the nearest prior trading day)
DECISION_DATES = ["2020-10-15", "2021-10-15", "2022-10-14",
                  "2023-10-13", "2024-10-15", "2025-10-15"]

# 1. Read; blank DTB6 rows are bond-market holidays, so they are dropped, not filled
raw = pd.read_csv(RAW, dtype=str, keep_default_na=False)
raw["observation_date"] = pd.to_datetime(raw["observation_date"])
raw = raw[raw["DTB6"].str.strip() != ""].copy()
raw["DTB6"] = raw["DTB6"].astype(float)

# 2-3. 10-calendar-day average ending ON the decision date
rows = []
for d in pd.to_datetime(DECISION_DATES):
    start = d - pd.Timedelta(days=WINDOW_DAYS - 1)
    win = raw[(raw["observation_date"] >= start) & (raw["observation_date"] <= d)]
    assert win["observation_date"].max() <= d, "date after decision date used"
    avg = win["DTB6"].mean() if len(win) else None
    rows.append({
        "decision_year": d.year,
        "decision_date": d.strftime("%Y-%m-%d"),
        "window_start": start.strftime("%Y-%m-%d"),
        "window_end": d.strftime("%Y-%m-%d"),
        "n_days_used": len(win),
        # 4. Percent mark kept for reading (rounded to 2 decimals, like FRED)
        "dtb6_avg_pct": f"{avg:.2f}%" if avg is not None else MISSING,
        # Full precision for the InterestCost calculation
        "rate_decimal": avg / 100 if avg is not None else MISSING,
    })
df = pd.DataFrame(rows)

# 5. Primary key: decision_date
if df["decision_date"].duplicated().any():
    print("STOPPED: duplicate decision_date. Nothing saved.")
    print(df[df["decision_date"].duplicated(keep=False)].to_string(index=False))
    sys.exit(1)

df.to_csv(OUT, index=False)
print(f"Saved {OUT} ({len(df)} rows)")

# 8. Compare with the single-day rate on each decision date
single = raw.set_index("observation_date")["DTB6"]
show = df.copy()
show["single_day_pct"] = [f"{single[pd.Timestamp(d)]:.2f}%" if pd.Timestamp(d) in single.index
                          else MISSING for d in df["decision_date"]]
print(show.to_string(index=False))
