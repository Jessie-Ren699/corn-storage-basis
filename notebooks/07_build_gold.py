"""Step 07: build the gold table gold_yearly from data/clean/corn.db.

One row = one region x one decision year (2020-2025), Country Elevators, Truck, in all 6 states
(IL, IA, NE, SD, MN, IN). region_id = state + " " + region (e.g. "IL North Central"), because
region names repeat across states.

  Cash bid on each hedge date: the Country Elevators / Truck bid of that region on the futures date;
  if there is none, the nearest PRIOR report within 7 days (oct/apr_bid_date_lag_days = days back).
  If there is none within 7 days, the region-year is dropped and listed.
  Futures, T-bill rate and storage costs are the same for every region.

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

PK (decision_year, region_id). If any futures price, rate or storage cost is missing, the script
stops, shows the rows and saves nothing.

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
STATES = ("IL", "IA", "NE", "SD", "MN", "IN")
BUYER_TYPE = "Country Elevators"
TRANSPORT = "Truck"
MAX_LAG_DAYS = 7                            # how far back a bid may be taken from
YEARS = range(2020, 2026)
STORAGE_CSV = "data/raw/storage_costs.csv"  # read only, never changed
CASES = ("low", "mid", "high")
LEGS = {"oct": "Oct (open hedge)", "apr": "Apr (close hedge)"}

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON")

# 1. Inputs: futures (one row per hedge date) and the Country Elevators / Truck bids of every region
futures = pd.read_sql("SELECT decision_year, date, leg, may_futures_price FROM may_futures", con)
bids = pd.read_sql("SELECT date, state, region, cash_price FROM corn_bids "
                   "WHERE buyer_type = ? AND transport_mode = ?", con, params=(BUYER_TYPE, TRANSPORT))
futures["date"] = pd.to_datetime(futures["date"])
bids["date"] = pd.to_datetime(bids["date"])
regions = bids[["state", "region"]].drop_duplicates().sort_values(["state", "region"])
assert set(regions["state"]) == set(STATES), f"states with bids: {sorted(set(regions['state']))}"

# 2. Each hedge date x each region: the bid on that date, or the nearest prior one within 7 days
def leg(prefix):
    f = futures[futures["leg"] == LEGS[prefix]].merge(regions, how="cross").sort_values("date")
    b = bids.rename(columns={"date": "bid_date"}).sort_values("bid_date")
    m = pd.merge_asof(f, b, left_on="date", right_on="bid_date", by=["state", "region"],
                      direction="backward", tolerance=pd.Timedelta(days=MAX_LAG_DAYS))
    m["bid_date_lag_days"] = (m["date"] - m["bid_date"]).dt.days      # 0 = bid on the futures date
    return m.rename(columns={"date": f"{prefix}_date", "bid_date": f"{prefix}_bid_date",
                             "bid_date_lag_days": f"{prefix}_bid_date_lag_days",
                             "cash_price": f"{prefix}_cash", "may_futures_price": f"{prefix}_futures"}
                    ).drop(columns="leg")

gold = leg("oct").merge(leg("apr"), on=["decision_year", "state", "region"], how="outer")

# 3. Drop (and list) region-years without a bid within 7 days on either hedge date
no_bid = gold["oct_cash"].isna() | gold["apr_cash"].isna()
dropped = gold.loc[no_bid, ["decision_year", "state", "region"]].copy()
dropped["reason"] = [
    " and ".join(f"no {p.capitalize()} bid within {MAX_LAG_DAYS} days before {r[f'{p}_date'].date()}"
                 for p in LEGS if pd.isna(r[f"{p}_cash"]))
    for _, r in gold[no_bid].iterrows()]
gold = gold[~no_bid].copy()

# 4. Rate matched on the Oct decision date; storage cost cases matched on decision_year
rate = pd.read_sql("SELECT decision_date AS oct_date, rate_decimal FROM tbill_decision", con)
rate["oct_date"] = pd.to_datetime(rate["oct_date"])
gold = gold.merge(rate, on="oct_date", how="left")
storage = pd.read_csv(STORAGE_CSV)
storage_cols = [f"storage_{c}_cents" for c in CASES]
assert sorted(storage["decision_year"]) == list(YEARS), "storage_costs.csv must have one row per year"
assert not storage["decision_year"].duplicated().any(), "duplicate year in storage_costs.csv"
assert ((storage["storage_low_cents"] + storage["storage_high_cents"]) / 2
        - storage["storage_mid_cents"]).abs().max() < 1e-9, "mid is not (low + high) / 2"
gold = gold.merge(storage[["decision_year"] + storage_cols], on="decision_year", how="left")

# 5. Keys and labels
gold["region_id"] = gold["state"] + " " + gold["region"]
gold["buyer_type"] = BUYER_TYPE
gold["transport_mode"] = TRANSPORT
for p in LEGS:
    gold[f"{p}_date"] = gold[f"{p}_date"].dt.strftime("%Y-%m-%d")
    gold[f"{p}_bid_date"] = gold[f"{p}_bid_date"].dt.strftime("%Y-%m-%d")
    gold[f"{p}_bid_date_lag_days"] = gold[f"{p}_bid_date_lag_days"].astype(int)
gold = gold.sort_values(["decision_year", "region_id"]).reset_index(drop=True)

# Checks: PK unique, nothing missing
problems = []
if gold.duplicated(["decision_year", "region_id"]).any():
    problems.append("duplicate (decision_year, region_id)")
NEEDED = ["oct_date", "apr_date", "oct_cash", "oct_futures", "apr_cash", "apr_futures",
          "rate_decimal"] + storage_cols
missing = gold[gold[NEEDED].isna().any(axis=1)]
if len(missing):
    problems.append(f"{len(missing)} rows have a missing value\n"
                    + missing[["decision_year", "region_id"] + NEEDED].to_string(index=False))
if problems:
    print("STOPPED: problems found. Nothing saved.\n")
    print("\n\n".join(problems))
    sys.exit(1)

# 6. Gaps in cents
gold["gap_oct_cents"] = (gold["oct_futures"] - gold["oct_cash"]) * 100
gold["gap_apr_cents"] = (gold["apr_futures"] - gold["apr_cash"]) * 100
gold["gap_closed_cents"] = gold["gap_oct_cents"] - gold["gap_apr_cents"]
# Interest in cents
gold["interest_cents"] = gold["rate_decimal"] * 0.5 * gold["oct_cash"] * 100
# Break-even storage cost: storing pays only if storage costs less than this
gold["breakeven_storage_cents"] = gold["gap_closed_cents"] - gold["interest_cents"]
# 7. Hurdle, net gain and the store/sell call for each storage case.
# Sold on Apr 15, the day the hedge closes, so no extra holding period is costed.
for c in CASES:
    gold[f"hurdle_{c}_cents"] = gold[f"storage_{c}_cents"] + gold["interest_cents"]
    gold[f"net_gain_{c}_cents"] = gold["gap_closed_cents"] - gold[f"storage_{c}_cents"] - gold["interest_cents"]
    gold[f"store_wins_{c}"] = gold[f"net_gain_{c}_cents"] > 0

# Summary
print(f"regions: {len(regions)} ({regions.groupby('state').size().reindex(STATES).to_dict()})")
print(f"region-years: {len(regions) * len(YEARS)} possible, {len(gold)} kept, {len(dropped)} dropped")
print("bid date lags (days, both legs):",
      pd.concat([gold["oct_bid_date_lag_days"], gold["apr_bid_date_lag_days"]]).value_counts().sort_index().to_dict())
print("gold rows by state:", gold["state"].value_counts().reindex(STATES).to_dict())
print("\nDropped region-years:")
print(dropped.to_string(index=False) if len(dropped) else "none")

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
    region_id        TEXT    NOT NULL,     -- state + " " + region, e.g. "IL North Central"
    state            TEXT    NOT NULL,
    region           TEXT    NOT NULL,
    buyer_type       TEXT    NOT NULL,     -- Country Elevators
    transport_mode   TEXT    NOT NULL,     -- Truck
    oct_date         TEXT    NOT NULL REFERENCES calendar(date),   -- futures (decision) date
    oct_bid_date     TEXT    NOT NULL REFERENCES calendar(date),   -- date of the cash bid used
    oct_bid_date_lag_days INTEGER,         -- oct_date - oct_bid_date (0-7)
    oct_cash         REAL,                 -- $/bu
    oct_futures      REAL,                 -- $/bu, May contract
    apr_date         TEXT    NOT NULL REFERENCES calendar(date),
    apr_bid_date     TEXT    NOT NULL REFERENCES calendar(date),
    apr_bid_date_lag_days INTEGER,
    apr_cash         REAL,                 -- $/bu
    apr_futures      REAL,                 -- $/bu, same May contract
    rate_decimal     REAL,                 -- from tbill_decision on oct_date
    gap_oct_cents    REAL,                 -- X
    gap_apr_cents    REAL,
    gap_closed_cents REAL,                 -- Y
    interest_cents   REAL,
    breakeven_storage_cents REAL,          -- gap_closed - interest: max storage cost to break even
    storage_low_cents  REAL,               -- on-farm, 6 months (weaker source)
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
    PRIMARY KEY (decision_year, region_id)
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
print(f"\nSaved table gold_yearly in {DB} and {CSV} ({len(gold)} rows x {len(cols)} columns)")
