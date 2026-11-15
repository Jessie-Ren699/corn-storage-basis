"""Step 07: build the gold table gold_yearly from data/clean/corn.db.

One row = one region x one decision year (2020-2025), Country Elevators only.

  gap_oct_cents    = (oct_futures - oct_cash) x 100              (X)
  gap_apr_cents    = (apr_futures - apr_cash) x 100
  gap_closed_cents = gap_oct_cents - gap_apr_cents               (Y)
                   = Basis(Apr) - Basis(Oct) in the README, in cents
  interest_cents   = rate_decimal x 0.5 x oct_cash x 100
  breakeven_storage_cents = gap_closed_cents - interest_cents
                   = the most a 6-month storage could cost and storing still break even

  For each storage case c in (low, mid, high), 6-month hold Oct 15 -> Apr 15:
  storage_c_cents  = from data/raw/storage_costs.csv (typed from articles, approved 2026-11-13)
  hurdle_c_cents   = storage_c_cents + interest_cents
  net_gain_c_cents = gap_closed_cents - storage_c_cents - interest_cents
  store_wins_c     = net_gain_c_cents > 0
  The corn is sold on Apr 15, the day the hedge closes: no holding period after Apr 15.

PK (decision_year, region). If any cash price, futures price, rate or storage cost is
missing, the script stops, shows the rows and saves nothing.

Outputs: table gold_yearly in data/clean/corn.db and data/gold/gold_yearly.csv.
Run from the project folder:
    python notebooks/07_build_gold.py              # refuses if outputs exist
    python notebooks/07_build_gold.py --overwrite  # replace existing outputs
"""
import os
import sqlite3
import sys

import pandas as pd

DB = "data/clean/corn.db"
CSV = "data/gold/gold_yearly.csv"
REGIONS = ("North Central", "South Central")
BUYER_TYPE = "Country Elevators"
YEARS = range(2020, 2026)
STORAGE_CSV = "data/raw/storage_costs.csv"  # read only, never changed
CASES = ("low", "mid", "high")

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON")

# 1-2. Oct and Apr legs: cash and May futures on the same date.
# LEFT JOINs so a missing price shows up as NULL instead of silently dropping the row.
LEG_SQL = """
SELECT f.decision_year, r.region, f.date, b.cash_price, f.may_futures_price
FROM may_futures f
CROSS JOIN (SELECT ? AS region UNION ALL SELECT ?) r
LEFT JOIN corn_bids b
       ON b.date = f.date AND b.region = r.region AND b.buyer_type = ?
WHERE f.leg = ?
"""
def leg(name, prefix):
    df = pd.read_sql(LEG_SQL, con, params=(*REGIONS, BUYER_TYPE, name))
    return df.rename(columns={"date": f"{prefix}_date", "cash_price": f"{prefix}_cash",
                              "may_futures_price": f"{prefix}_futures"})

oct_ = leg("Oct (open hedge)", "oct")
apr_ = leg("Apr (close hedge)", "apr")
gold = oct_.merge(apr_, on=["decision_year", "region"], how="outer")

# 4. Rate matched on the Oct decision date
rate = pd.read_sql("SELECT decision_date AS oct_date, rate_decimal FROM tbill_decision", con)
gold = gold.merge(rate, on="oct_date", how="left")
gold.insert(2, "buyer_type", BUYER_TYPE)

# 5. Storage cost cases, matched on decision_year (low = on-farm, high = commercial)
storage = pd.read_csv(STORAGE_CSV)
storage_cols = [f"storage_{c}_cents" for c in CASES]
assert sorted(storage["decision_year"]) == list(YEARS), "storage_costs.csv must have one row per year"
assert not storage["decision_year"].duplicated().any(), "duplicate year in storage_costs.csv"
assert ((storage["storage_low_cents"] + storage["storage_high_cents"]) / 2
        - storage["storage_mid_cents"]).abs().max() < 1e-9, "mid is not (low + high) / 2"
gold = gold.merge(storage[["decision_year"] + storage_cols], on="decision_year", how="left")
gold = gold.sort_values(["decision_year", "region"]).reset_index(drop=True)

# Checks: every region x year present, PK unique, nothing missing
expected = {(y, r) for y in YEARS for r in REGIONS}
found = set(zip(gold["decision_year"], gold["region"]))
problems = []
if found != expected:
    problems.append(f"region x year rows missing: {sorted(expected - found)}; extra: {sorted(found - expected)}")
if gold.duplicated(["decision_year", "region"]).any():
    problems.append("duplicate (decision_year, region)")
NEEDED = ["oct_date", "apr_date", "oct_cash", "oct_futures", "apr_cash", "apr_futures",
          "rate_decimal"] + storage_cols
missing = gold[gold[NEEDED].isna().any(axis=1)]
if len(missing):
    counts = gold[NEEDED].isna().sum()
    problems.append(f"{len(missing)} of {len(gold)} rows have a missing value. "
                    f"Missing per column: {counts[counts > 0].to_dict()}\n"
                    + missing[["decision_year", "region"] + NEEDED].to_string(index=False))
if problems:
    print("STOPPED: problems found. Nothing saved.\n")
    print("\n\n".join(problems))
    sys.exit(1)

# 3. Gaps in cents
gold["gap_oct_cents"] = (gold["oct_futures"] - gold["oct_cash"]) * 100
gold["gap_apr_cents"] = (gold["apr_futures"] - gold["apr_cash"]) * 100
gold["gap_closed_cents"] = gold["gap_oct_cents"] - gold["gap_apr_cents"]
# 4. Interest in cents
gold["interest_cents"] = gold["rate_decimal"] * 0.5 * gold["oct_cash"] * 100
# Break-even storage cost: storing pays only if storage costs less than this
gold["breakeven_storage_cents"] = gold["gap_closed_cents"] - gold["interest_cents"]
# 6. Hurdle, net gain and the store/sell call for each storage case.
# Sold on Apr 15, the day the hedge closes, so no extra holding period is costed.
for c in CASES:
    gold[f"hurdle_{c}_cents"] = gold[f"storage_{c}_cents"] + gold["interest_cents"]
    gold[f"net_gain_{c}_cents"] = gold["gap_closed_cents"] - gold[f"storage_{c}_cents"] - gold["interest_cents"]
    gold[f"store_wins_{c}"] = gold[f"net_gain_{c}_cents"] > 0

# Save
exists = os.path.exists(CSV) or con.execute(
    "SELECT 1 FROM sqlite_master WHERE name = 'gold_yearly'").fetchone()
if exists and "--overwrite" not in sys.argv:
    print("NOT SAVED: gold_yearly already exists. Re-run with --overwrite to replace it.")
    sys.exit(0)

con.executescript("""
DROP TABLE IF EXISTS gold_yearly;
CREATE TABLE gold_yearly (
    decision_year    INTEGER NOT NULL,
    region           TEXT    NOT NULL,
    buyer_type       TEXT    NOT NULL,
    oct_date         TEXT    NOT NULL REFERENCES calendar(date),
    oct_cash         REAL,                 -- $/bu
    oct_futures      REAL,                 -- $/bu, May contract
    apr_date         TEXT    NOT NULL REFERENCES calendar(date),
    apr_cash         REAL,                 -- $/bu
    apr_futures      REAL,                 -- $/bu, same May contract
    rate_decimal     REAL,                 -- from tbill_decision on oct_date
    gap_oct_cents    REAL,                 -- X
    gap_apr_cents    REAL,
    gap_closed_cents REAL,                 -- Y
    interest_cents   REAL,
    breakeven_storage_cents REAL,          -- gap_closed - interest: max storage cost to break even
    storage_low_cents  REAL,              -- on-farm, 6 months (weaker source)
    storage_mid_cents  REAL,               -- (low + high) / 2
    storage_high_cents REAL,               -- commercial: farmdoc physical x 0.5
    hurdle_low_cents   REAL,               -- storage + interest
    hurdle_mid_cents   REAL,
    hurdle_high_cents  REAL,
    net_gain_low_cents  REAL,              -- gap_closed - storage - interest
    net_gain_mid_cents  REAL,
    net_gain_high_cents REAL,
    store_wins_low   INTEGER,              -- 1 = net gain > 0
    store_wins_mid   INTEGER,
    store_wins_high  INTEGER,
    PRIMARY KEY (decision_year, region)
);
""")
cols = [r[1] for r in con.execute("PRAGMA table_info(gold_yearly)")]
gold = gold[cols]
con.executemany(f"INSERT INTO gold_yearly VALUES ({', '.join('?' * len(cols))})",
                gold.astype(object).where(gold.notna(), None).itertuples(index=False))
con.commit()
assert con.execute("PRAGMA foreign_key_check").fetchall() == [], "foreign key violations"
con.close()

os.makedirs(os.path.dirname(CSV), exist_ok=True)
gold.to_csv(CSV, index=False, na_rep="MISSING")
print(f"Saved table gold_yearly in {DB} and {CSV} ({len(gold)} rows)")
print(gold.to_string(index=False))
