"""Step 06: build the SQLite database data/clean/corn.db from the clean CSVs.

Tables:
  calendar        PK (date)                        every date 2020-01-01 .. 2026-12-31
  corn_bids       PK (date, state, region, buyer_type, transport_mode)
                                                   FK date -> calendar(date)
  may_futures     PK (date)                        FK date -> calendar(date)
  tbill_decision  PK (decision_date)               FK decision_date -> calendar(date)

Every PK is checked for duplicates and every FK for dates missing from calendar
BEFORE anything is loaded; any problem stops the script and nothing is saved.

Run from the project folder:
    python notebooks/06_build_db.py              # refuses if corn.db exists
    python notebooks/06_build_db.py --overwrite  # replace an existing corn.db
"""
import os
import sqlite3
import sys

import pandas as pd

DB = "data/clean/corn.db"
CAL_START, CAL_END = "2020-01-01", "2026-12-31"

SCHEMA = """
CREATE TABLE calendar (
    date TEXT PRIMARY KEY                     -- YYYY-MM-DD
);

CREATE TABLE corn_bids (
    date            TEXT NOT NULL REFERENCES calendar(date),
    state           TEXT NOT NULL,            -- IL, IA, NE, SD, MN, IN
    commodity       TEXT,
    region          TEXT NOT NULL,
    buyer_type      TEXT NOT NULL,
    deliver_now     INTEGER,                  -- 1 = True, 0 = False
    cash_price      REAL,                     -- $/bu
    cash_price_low  REAL,                     -- $/bu
    cash_price_high REAL,                     -- $/bu
    price_unit      TEXT,
    grain_class     TEXT,
    grain_grade     TEXT,
    price_point     TEXT,
    transport_mode  TEXT NOT NULL,
    PRIMARY KEY (date, state, region, buyer_type, transport_mode)
);

CREATE TABLE may_futures (
    decision_year     INTEGER,
    date              TEXT PRIMARY KEY REFERENCES calendar(date),
    futures_contract  TEXT,
    contract_name     TEXT,
    leg               TEXT,
    settle_raw        TEXT,                   -- as typed, cents and eighths (e.g. 583-2)
    source            TEXT,
    may_futures_price REAL                    -- $/bu, converted from settle_raw
);

CREATE TABLE tbill_decision (
    decision_year INTEGER,
    decision_date TEXT PRIMARY KEY REFERENCES calendar(date),
    window_start  TEXT,
    window_end    TEXT,
    n_days_used   INTEGER,
    dtb6_avg_pct  TEXT,                       -- e.g. "4.02%", for reading only
    rate_decimal  REAL                        -- use this in calculations
);
"""

# table -> (csv, primary key, FK column -> calendar.date, column types)
TABLES = {
    "corn_bids": ("data/clean/corn_bids_current.csv",
                  ["date", "state", "region", "buyer_type", "transport_mode"], "date",
                  {"deliver_now": "bool", "cash_price": "real", "cash_price_low": "real",
                   "cash_price_high": "real"}),
    "may_futures": ("data/clean/may_futures.csv", ["date"], "date",
                    {"decision_year": "int", "may_futures_price": "real"}),
    "tbill_decision": ("data/clean/tbill_decision.csv", ["decision_date"], "decision_date",
                       {"decision_year": "int", "n_days_used": "int", "rate_decimal": "real"}),
}


def convert(value, kind):
    # Blank and MISSING become NULL; never filled
    if value in ("", "MISSING"):
        return None
    if kind == "real":
        return float(value)
    if kind == "int":
        return int(value)
    if kind == "bool":
        return {"True": 1, "False": 0}[value]
    return value


# 1. Calendar
calendar = pd.date_range(CAL_START, CAL_END, freq="D").strftime("%Y-%m-%d")
cal_set = set(calendar)

# Read CSVs as text so nothing is reinterpreted
frames = {t: pd.read_csv(csv, dtype=str, keep_default_na=False) for t, (csv, *_) in TABLES.items()}

# 2-4. Checks before loading
problems = []
if pd.Series(calendar).duplicated().any():
    problems.append("calendar: duplicate dates")
for t, (csv, pk, fk, _) in TABLES.items():
    df = frames[t]
    dup = df[df.duplicated(pk, keep=False)]
    if len(dup):
        problems.append(f"{t}: {len(dup)} rows share a PK {pk}\n{dup.sort_values(pk).to_string(index=False)}")
    blank = df[(df[pk] == "").any(axis=1)]
    if len(blank):
        problems.append(f"{t}: {len(blank)} rows with a blank PK value\n{blank.to_string(index=False)}")
    orphan = df[~df[fk].isin(cal_set)]
    if len(orphan):
        problems.append(f"{t}: {len(orphan)} rows with {fk} not in calendar\n{orphan.to_string(index=False)}")
if problems:
    print("STOPPED: problems found. Nothing saved.\n")
    print("\n\n".join(problems))
    sys.exit(1)
print("Checks passed: no duplicate PKs, no FK dates missing from calendar.")

# 5. Build
if os.path.exists(DB):
    if "--overwrite" not in sys.argv:
        print(f"NOT SAVED: {DB} already exists. Re-run with --overwrite to replace it.")
        sys.exit(0)
    os.remove(DB)

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = ON")
con.executescript(SCHEMA)
con.executemany("INSERT INTO calendar (date) VALUES (?)", [(d,) for d in calendar])
for t, (csv, pk, fk, types) in TABLES.items():
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
    df = frames[t]
    # Columns not in the CSV yet (may_futures_price) are loaded as NULL
    rows = [tuple(convert(r[c], types.get(c, "text")) if c in df.columns else None for c in cols)
            for _, r in df.iterrows()]
    con.executemany(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
con.commit()

# Double check inside SQLite
assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
assert con.execute("PRAGMA foreign_key_check").fetchall() == [], "foreign key violations"
print(f"Saved {DB}\n")

for t in ["calendar", *TABLES]:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"--- {t}: {n} rows")
    print(con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (t,)).fetchone()[0], "\n")
con.close()
