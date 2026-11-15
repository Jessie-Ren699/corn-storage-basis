"""FGP side project, step 01: pull USDA report 3192 (Illinois Grain Bids), one month per request.

Output: data/raw/3192_YYYY-MM.csv (same format as the earlier pulls)

Method check (2026-11-11): re-pulling Oct 2021 with this exact request gave a file
identical to the existing data/raw/3192_2021-10.csv (976 rows x 55 columns).

Run from the project folder:
    python notebooks/fgp_01_pull_3192.py

Never overwrites an existing raw file (data/raw/ is evidence).
The API key is read from .env and is never printed.
"""
import calendar
import os

import pandas as pd
import requests
from dotenv import dotenv_values

URL = "https://marsapi.ams.usda.gov/services/v1.2/reports/3192/Report Detail"
RECORD_CAP = 100_000  # MyMarketNews limit per request
MONTHS = [(2021, 8), (2021, 9), (2021, 11), (2022, 8), (2022, 9), (2022, 11)]  # approved 2026-11-11

key = dotenv_values(".env")["API_KEY"]

for year, month in MONTHS:
    out = f"data/raw/3192_{year}-{month:02d}.csv"
    if os.path.exists(out):
        print(f"{out}: already exists, NOT pulled again")
        continue
    last = calendar.monthrange(year, month)[1]
    q = f"report_begin_date={month:02d}/01/{year}:{month:02d}/{last}/{year}"
    r = requests.get(URL, params={"q": q}, auth=(key, ""), timeout=120)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["results"])
    # Stop if we hit the cap: the month would be cut off, so the data would be incomplete.
    assert len(df) < RECORD_CAP, f"{year}-{month:02d}: {len(df)} rows hit the {RECORD_CAP} cap"
    assert len(df) > 0, f"{year}-{month:02d}: 0 rows returned"
    df.to_csv(out, index=False)
    print(f"{out}: {len(df):,} rows, {df.shape[1]} cols, "
          f"{df['report_date'].nunique()} report days")
