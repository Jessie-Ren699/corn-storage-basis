# Processing log

What each script does to the data, and what happened when it last ran.
A new entry is added after every data change. Scripts only ever read `data/raw/`. The one exception was
the user-approved hand entry of the futures prices (see Change entries, 2026-11-08).

## Summary

| Step | Input → Output | Status (last run) |
|---|---|---|
| 03 build_silver | 71 raw grain-bid files for 6 states, listed in `raw/usda_bids/manifest.csv` → `clean/corn_bids_current.csv` | ✅ 2026-11-21: 9,935 rows, 6 states (IL rows byte-identical to the previous output) |
| 04 clean_futures | `raw/may_futures.csv` → `clean/may_futures.csv` | ✅ 2026-11-08: 12 rows, 0 MISSING prices |
| 05 tbill_rates | `raw/fred_dtb6.csv` → `clean/tbill_decision.csv` | ✅ 2026-11-08: 6 rows (unchanged) |
| 06 build_db | 3 clean CSVs → `clean/corn.db` | ✅ 2026-11-21: 4 tables, checks passed; `corn_bids` 9,935 rows, PK with `state` and `transport_mode` |
| 07 build_gold | `corn.db` + `raw/storage_costs.csv` → `gold_yearly` table + `gold/gold_yearly.csv` | ✅ 2026-11-21: 12 rows × 27 cols, 0 missing; Illinois only; byte-identical to 2026-11-13 |
| 08 charts | `gold/gold_yearly.csv` → `outputs/*.png` | ✅ 2026-11-13: 2 charts saved; bar chart shows gap closed vs. low/mid/high hurdles |
| 09 walk_forward | `gold/gold_yearly.csv` → `outputs/walk_forward_predictions.csv`, `outputs/scoreboard.csv` | ✅ 2026-11-21: 6 test rows, 12 scoreboard rows; byte-identical to 2026-11-13 |

## Raw vs Clean

Counted from the actual files on 2026-11-08; Storage costs and Gold rows updated 2026-11-13 (rows exclude the header).

| Dataset | Raw file | Raw rows | Raw cols | Clean file | Clean rows | Clean cols | Rows dropped and why |
|---|---|---|---|---|---|---|---|
| Cash bids (6 states, updated 2026-11-21) | 71 files listed in `raw/usda_bids/manifest.csv` | 39,958 | 55 (+`state`) | `clean/corn_bids_current.csv` | 9,935 | 14 | 30,023: 24,354 not corn; 5,514 corn but not current delivery; 147 White corn (Indiana); 8 empty `¢/Bu` rows (Illinois) that duplicated a real row's key. Illinois alone: 12,486 → 3,024, as before |
| May futures | `raw/may_futures.csv` | 12 | 5 | `clean/may_futures.csv` | 12 | 8 | 0. Added `contract_name`, `leg` and `may_futures_price` ($/bu) |
| T-bill | `raw/fred_dtb6.csv` | 17,707 | 2 | `clean/tbill_decision.csv` | 6 | 7 | Summarized, not dropped: 755 blank holiday rows skipped; 41 daily values in the six 10-day windows averaged into 6 rows (1 per decision date) |
| Storage costs | `raw/storage_costs.csv` (typed from articles) | 6 | 7 | (read directly by `07`; no clean copy) | n/a | n/a | 0. One row per decision year; low/mid/high cents for a 6-month hold |
| Gold | (built from `clean/corn.db` + `raw/storage_costs.csv`) | n/a | n/a | `gold/gold_yearly.csv` | 12 | 27 | Selection, not dropped: 2 regions × Country Elevators × 6 years, Oct and Apr dates only |

**Run order:** `03` → `04` → `05` → `06 --overwrite` → `07` → `08` → `09`.
`06` rebuilds `corn.db` from scratch, which removes `gold_yearly`, so `07` must always
run after it.

---

## 03_build_silver.py: cash bids (silver table)

- **Input (since 2026-11-21):** every file listed in `data/raw/usda_bids/manifest.csv`: the 12 Illinois
  pulls `data/raw/3192_YYYY-MM.csv` plus 59 files for IA, NE, SD, MN, IN in `data/raw/usda_bids/<STATE>/`.
  Each file's SHA-256 must match the manifest. A `state` column is added; the new filter keeps Yellow corn
  only, and the primary key is (`date`, `state`, `region`, `buyer_type`, `transport_mode`). See the
  2026-11-21 change entry. The steps below describe the earlier Illinois-only version.
- **Input (until 2026-11-21):** `data/raw/3192_YYYY-MM.csv`, the 12 monthly USDA MyMarketNews pulls of report
  3192 (Oct and Apr, 2020-10 to 2026-04). `test_3192_2024-10.csv` is skipped.
- **What it did:**
  1. Stacked the 12 files and kept 13 columns.
  2. Kept corn, current (deliver now) bids only. All regions and buyer types kept.
  3. Renamed the columns to project names (see `data_dictionary.md`). `Yes`/`No` became `True`/`False`.
  4. Converted dates from MM/DD/YYYY to YYYY-MM-DD.
  5. Dropped the 8 empty `¢/Bu` rows: South Illinois River / Barge Loading Elevators,
     2022-10-03 to 10-13. They had no price, and each one duplicated the key of a real `$ Per Bushel` row.
  6. Sorted by the primary key (`date`, `region`, `buyer_type`).
- **Output:** `data/clean/corn_bids_current.csv`, 3,024 rows.
- **Checks:**
  - exactly 12 raw files;
  - exactly 8 empty `¢/Bu` rows dropped;
  - 0 duplicates on the primary key (otherwise it shows the rows and stops);
  - no blank key values;
  - won't overwrite without `--overwrite`.
- **Last run:** 2026-11-05.
  - 3,024 rows, 0 duplicates, 0 MISSING prices.
  - All rows are in `$ Per Bushel`.
  - `cash_price` from $3.4975 to $8.2935, mean $5.1044.
  - The new file matched the old one minus the 8 rows.

## 04_clean_futures.py: May futures

- **Input:** `data/raw/may_futures.csv`, 12 rows (6 decision years × Oct/Apr), typed by
  hand from Barchart.
- **What it does:**
  1. Renames `contract` to `futures_contract`.
  2. Adds `contract_name` (ZCK21 → "May 2021 corn").
  3. Adds `leg` from the month: Oct (open hedge) / Apr (close hedge).
  4. Converts `settle_raw` from cents and eighths to `may_futures_price` in $/bu
     (`583-2` = 583.25¢ = $5.8325, not rounded). Blank cells stay blank.
  5. Puts the columns in a fixed order.
- **Output:** `data/clean/may_futures.csv`.
- **Checks:**
  - contract code must match `ZCK##`;
  - month must be Oct or Apr;
  - `settle_raw` must look like `583-2` (eighths 0-7), otherwise it stops;
  - prints the number of MISSING prices.
- **Last run:** 2026-11-08 (first full run; this replaced the earlier one-off version of the file).
  - 12 rows × 8 columns, 0 MISSING prices.
  - `may_futures_price` from $4.0925 to $7.9025, mean $5.3660.

## 05_tbill_rates.py: T-bill rate for the hurdle

- **Input:** `data/raw/fred_dtb6.csv` (FRED DTB6, 6-month T-bill, percent, daily).
- **What it did:**
  1. Dropped blank (holiday) rows.
  2. For each of the 6 decision dates D, averaged DTB6 over the 10 calendar days D-9 to D
     (D included).
  3. Stored the average as text with a % sign (`4.02%`, 2 decimals) and as `rate_decimal`
     (full precision).
- **Output:** `data/clean/tbill_decision.csv`, 6 rows. Primary key: `decision_date`.
- **Checks:**
  - no date after D used;
  - `decision_date` unique (otherwise it shows the rows and stops).
- **Last run:** 2026-11-08. The output is byte-for-byte identical to the 2026-11-05 run.
  - 6 rows, 0 MISSING.
  - Averages range from 0.06% (2021) to 5.33% (2023).
  - The largest gap from the single-day rate is 2022: 4.02% vs 4.17%.
  - 2024 used 6 days, because 2024-10-14 is blank in FRED.
- **Related one-off change (same day, not a script):** deleted the older
  `data/clean/fred_dtb6.csv`, which used the prior day's single rate with a % sign. A backup was kept
  in the session scratch folder.

## 06_build_db.py: SQLite database

- **Input:** `data/clean/corn_bids_current.csv`, `may_futures.csv`, `tbill_decision.csv`.
- **What it did:**
  1. Created `data/clean/corn.db` with foreign keys on.
  2. Built 4 tables:
     - `calendar` (every date 2020-01-01 to 2026-12-31);
     - `corn_bids`;
     - `may_futures`;
     - `tbill_decision`.
  3. Stored blanks/`MISSING` as NULL and `deliver_now` as 1/0.
- **Output:** `data/clean/corn.db`.
- **Checks (before loading):**
  - no duplicate primary keys;
  - no blank key values;
  - every foreign-key date exists in `calendar`.

  After loading: SQLite `foreign_key_check` is empty. Won't overwrite without `--overwrite`.
- **Last run:** 2026-11-08 (`--overwrite`).
  - Rows: calendar 2,557, corn_bids 3,024, may_futures 12 (now with prices), tbill_decision 6.
  - All checks passed.

## 07_build_gold.py: gold table

- **Input:** `data/clean/corn.db`. Regions North Central and South Central, Country
  Elevators, decision years 2020-2025.
- **What it does:**
  1. Takes cash and May futures prices on the Oct and Apr dates, plus the rate on the Oct date.
  2. Computes, in cents/bu:
     - `gap_oct` = futures − cash (X);
     - `gap_apr`;
     - `gap_closed` = `gap_oct` − `gap_apr` (Y, the README's Target);
     - `interest` = rate × 0.5 × Oct cash.
  3. Leaves `storage_cents` blank.
- **Output:** table `gold_yearly` in `corn.db` and `data/gold/gold_yearly.csv`.
  Primary key: (`decision_year`, `region`).
- **Checks:**
  - all 12 region × year rows present;
  - key unique;
  - no missing price or rate (otherwise it shows the rows and stops, saving nothing).
- **Last run:** 2026-11-08.
  - 12 rows × 15 columns, 0 missing prices or rates.
  - The `gold_yearly` table in the db matches the CSV.
  - `foreign_key_check` is empty.

## 08_charts.py: charts

- **Input:** `data/gold/gold_yearly.csv`.
- **What it does:**
  - `outputs/scatter_gap.png`: gap_oct vs gap_closed, one color per region, year
    labels, best-fit line per region plus a pooled gray dashed line (slope and R² in the
    legend). An orange dash marks each year's interest hurdle, with a thin line to its dot.
  - `outputs/bars_by_year.png`: gap_closed vs interest by year, one panel per region,
    with the note "Hurdle shows interest only; storage not added yet."
- **Output:** the two PNGs in `outputs/`.
- **Checks:** stops if the input file is missing or any plotted value is missing.
- **Last run:** 2026-11-08 (rerun after the color and hurdle changes). Saved `outputs/scatter_gap.png` and
  `outputs/bars_by_year.png`.
  - North Central: slope 0.4931, R² 0.8009 (n = 6).
  - South Central: slope 0.3580, R² 0.6303 (n = 6).
  - Pooled: slope 0.4126, R² 0.6739 (n = 12).

---

## Change entries

New entries go below, newest last: date, what changed, files, row counts, checks.

### 2026-11-08: data dictionary rewritten (documentation only)

- **Changed:** `docs/data_dictionary.md`.
  - Added a summary table and a short intro on the project question.
  - Each table now has the same format: description, primary key, `Column | Meaning`.
  - The first section is renamed `corn_bids_current` (the database table is still `corn_bids`).
  - The `corn_bids_current` columns now carry business meaning: spot vs. forward, cash bid vs. futures, delivered price, why Truck.
  - `may_futures` has its own section.
  - Keys and Relationships are kept at the end.
  - The old line about blank prices being written as `MISSING` was removed.
- **Data files:** none changed. Row counts unchanged.

### 2026-11-08: May futures prices entered in raw file (one-time raw edit, approved by user)

- **Changed:** `data/raw/may_futures.csv`, column `settle_raw` only. The 12 values were typed by the user from
  Barchart's "Latest" column: 409-2, 590-0, 538-6, 790-2, 697-2, 666-2, 516-4, 431-4, 426-0,
  481-2, 441-0, 451-2.
- **Checks:**
  - all 12 match the cents-and-eighths format (eighths 0-7);
  - each value was matched to its row by date + contract;
  - the other 4 columns are identical to before, and still 12 rows × 5 columns;
  - the backup of the blank version was kept in the session scratch folder.
- **Preview (not saved):**
  - $/bu from 4.0925 to 7.9025, mean 5.3660.
  - The gap (futures − cash) at North/South Central Country Elevators runs 29-67¢ in Oct and −0.2 to 25¢ in Apr.
- **Not yet run:** 04 → 08, waiting for the user's approval of the $/bu values.

### 2026-11-08: full pipeline run 04 → 08 (prices approved by user)

- **Code changes:** `07_build_gold.py` now writes its CSV to the new folder `data/gold/`
  (it creates the folder if needed). `08_charts.py` now reads from there. The `gold_yearly`
  table stays in `corn.db`.
- **Files written:**
  - `data/clean/may_futures.csv` (12 × 8, now with `may_futures_price`);
  - `data/clean/tbill_decision.csv` (unchanged);
  - `data/clean/corn.db` (rebuilt, plus `gold_yearly`);
  - `data/gold/gold_yearly.csv` (12 × 15);
  - `outputs/scatter_gap.png` and `outputs/bars_by_year.png`.

  `corn_bids_current.csv` was not touched (03 not run).
- **Checks:**
  - all 04-08 checks passed;
  - 0 missing values in gold;
  - gold PK unique;
  - gold CSV = db table;
  - the files before the run were backed up in the session scratch folder.
- **Gold summary (cents/bu):**
  - `gap_oct` 29.4 to 66.6 (mean 46.6);
  - `gap_apr` −0.2 to 25.3 (mean 16.0);
  - `gap_closed` 20.0 to 43.4 (mean 30.6);
  - `interest` 0.15 to 13.3 (mean 6.8).
  - `gap_closed` > `interest` in 12 of 12 rows; storage not included yet.

### 2026-11-08: 08 rerun, slope and R² added to the scatter legend

- **Code change:** `08_charts.py` now computes each region's OLS slope, intercept and R²
  (R² = squared correlation of gap_oct and gap_closed). It prints them and shows slope and R² in the legend.
- **Files written:** `outputs/scatter_gap.png`, `outputs/bars_by_year.png` (the bar chart is unchanged).
  No data files changed, so the Raw vs Clean counts are unchanged.
- **Result:** North Central slope 0.49, R² 0.80; South Central slope 0.36, R² 0.63 (n = 6 each).

### 2026-11-08: 08 rerun, new colors, hurdle dashes and pooled fit

- **Code changes in `08_charts.py`:**
  - Scatter colors: North Central blue `#2a78d6`, South Central purple `#7b2d8e`.
  - Bar colors: gap closed green `#006300`, interest orange `#eb6834`.
  - Orange means interest in both charts. No other color is shared between them.
  - Scatter: an orange dash at each year's `interest_cents`, with a thin line to the dot;
    legend entry "interest hurdle (varies by year)".
  - Pooled OLS line (12 points) as a gray dashed line, with slope and R² in the legend.
  - The scatter title now also says "Hurdle shows interest only; storage not added yet."
- **Color checks (colorblind validator):**
  - The requested green `#008300` + orange failed for red-green colorblindness (ΔE 3.2), so it was darkened to `#006300` (passes, ΔE 13.0).
  - The palette violet `#6250d6` was too close to the blue, so the deeper purple `#7b2d8e` was used (passes, ΔE 13.1).
- **Files written:** `outputs/scatter_gap.png`, `outputs/bars_by_year.png`. No data files changed;
  the Raw vs Clean counts are unchanged.
- **Result:** pooled slope 0.41, R² 0.67 (n = 12). The per-region values are unchanged.

### 2026-11-11: 03 file list fixed (after the FGP pulls)

*(Split out on 2026-11-15 from the mixed entry "FGP Post rule changed; 03 file list fixed; FGP chart saved";
the FGP parts are now in `fgp_river_basis/processing_log.md`.)*

- **`03_build_silver.py`:** the 12 Oct/Apr raw files are now listed by name instead of
  matched with `3192_20*.csv` (the FGP pulls had raised the match count to 18).
  Rerun with `--overwrite`: 3,024 rows, output **byte-for-byte identical** to the previous
  `clean/corn_bids_current.csv`. Steps 04-08 do not need a rerun.
### 2026-11-13: storage cost cases added to gold (06 → 07 → 08 rerun)

- **New raw file (user-approved hand entry):** `data/raw/storage_costs.csv`, 6 rows × 7 cols
  (`decision_year`, `storage_low/mid/high_cents`, `source_url_low`, `source_url_high`, `note`).
  Values for a 6-month hold (Oct 15 → Apr 15), cents/bu:

  | decision_year | low | mid | high | high from (farmdoc physical storage, $/bu/yr × 0.5) |
  |---|---|---|---|---|
  | 2020 | 9.0 | 22.25 | 35.5 | 0.71, read from farmdoc Fig. 1 (±0.02) |
  | 2021 | 9.0 | 22.5 | 36.0 | 0.72, read from chart (±0.02) |
  | 2022 | 9.0 | 22.5 | 36.0 | 0.72, read from chart (±0.02) |
  | 2023 | 9.0 | 37.0 | 65.0 | 1.30, read from chart (±0.02) |
  | 2024 | 9.0 | 37.0 | 65.0 | 1.30, stated in text (OSU companion article) |
  | 2025 | 9.0 | 37.0 | 65.0 | **FLAG:** 2024 value carried forward |

  - **High (commercial):** Zulauf, Paulson & Janzen, farmdoc daily (15):181, Oct 2, 2025,
    https://farmdocdaily.illinois.edu/2025/10/annual-cost-of-storing-us-corn-and-soybeans-since-1973.html .
    Physical storage only (not total), because interest is already counted from DTB6.
    The article prints no yearly values, so 2020-2023 were measured from the Figure 1 image (pixel
    calibration; it reproduces the stated 2023 and 2024 totals, $1.57 and $1.46).
  - **Low (on-farm), weaker source:** Iowa Farm Bureau (2016, figure not attributed), "1 to 2 cents per
    bushel per month" ownership cost, no interest; midpoint 1.5¢ × 6 = 9¢, same every year.
    Iowa State Ag Decision Maker A2-33 was checked but gives no total per-bushel figure.
  - **Mid:** (low + high) / 2.
- **Code change, `07_build_gold.py`:** reads `raw/storage_costs.csv` (checks: one row per year, mid =
  (low + high) / 2, no missing). The always-blank `storage_cents` column was replaced by 12 new columns:
  `storage_{c}_cents`, `hurdle_{c}_cents` = storage + interest,
  `net_gain_{c}_cents` = gap_closed − storage − interest, `store_wins_{c}` = net_gain > 0, for c = low, mid, high.
  The corn is sold on Apr 15, the day the hedge closes, so no holding period after Apr 15 is costed.
- **Rerun:** `06 --overwrite` → `07 --overwrite` → `08`. Backups of the previous `corn.db`, gold CSV and both
  charts are in the session scratch folder.
- **Checks:**
  - gold has 12 rows × 26 cols and 0 missing;
  - all 14 earlier gold columns are identical to the previous file;
  - the gold CSV matches the db table;
  - FK check is clean;
  - `corn_bids`, `may_futures` and `tbill_decision` are unchanged in the db.
- **Result (cents/bu, 12 region-years):**
  - low: storing wins 12/12, mean net +14.8 (min +5.8);
  - mid: wins 1/12 (2020 South Central, +7.1), mean −5.9;
  - high: wins 0/12, mean −26.6 (max −6.2).
- **Limitations (user-approved):**
  - A. Halving the annual commercial cost probably understates it. Under flat-fee-then-monthly pricing
    (2014 central-IL survey: 18¢ to Dec 31, then 3¢/month), Oct 15 → Apr 15 is about 68% of the
    12-month cost, not 50%.
  - B. The commercial rate is from one Ohio country elevator, not Central Illinois.
  - Also: the low case is a single 2016 range, the same every year, and leaves out shrink and handling.
- **Not changed:** `08_charts.py` still draws gap closed vs. interest only, and its titles still say
  "storage not added yet". The charts were redrawn but are identical in content.

### 2026-11-13: breakeven column, new bar chart, README storage item resolved

- **`07_build_gold.py`:** new column `breakeven_storage_cents` = `gap_closed_cents` − `interest_cents`,
  the most a 6-month storage could cost and storing still break even.
  - Named with the `_cents` suffix used for all cents columns.
  - Range 14.8 to 35.6 (mean 23.8).
  - Checks: all 26 earlier columns are identical; CSV = db; `store_wins_c` = (breakeven > `storage_c`) in every row.
- **`08_charts.py`:**
  - `bars_by_year.png` now shows gap closed (green bar) against the three hurdles as short lines:
    - low (light orange, dotted);
    - mid (orange, dashed);
    - high (dark orange, solid).
  - Each panel title gives the win count:
    - North Central: low 6/6, mid 0/6, high 0/6;
    - South Central: low 6/6, mid 1/6, high 0/6.
  - Hurdle colors: one orange hue, light → dark; passes the ordinal colorblind check. Line style and text
    labels are a second cue, because low and mid are close in color.
  - Both "storage not added yet" notes were removed. The scatter title now says its orange dashes are
    interest only and points to the bar chart.
- **Rerun:** `06 --overwrite` → `07 --overwrite` → `08`. Previous files are backed up in the session scratch folder.
- **README:** "Commercial storage rate and structure" under *To be determined* is marked resolved,
  pointing to `data/raw/storage_costs.csv`.

### 2026-11-13: 09 walk-forward test (first out-of-sample results)

- **New script:** `notebooks/09_walk_forward.py`. It reads `gold/gold_yearly.csv` and writes only to `outputs/`.
  Data files were checked unchanged by checksum.
- **Setup:**
  - North + South Central pooled, 2 rows per year.
  - Test years 2023, 2024, 2025, each trained only on earlier decision years (3 rounds: n_train = 6, 8, 10).
  - A training year's gap_closed is known by the next Apr 15, before the test Oct 15, so there is no leakage.
- **Forecasts of gap_closed:**
  - regression: OLS on gap_oct;
  - past average: mean of the training rows.
  - Rule: store if forecast − interest > storage.
  - Correct call = matches hindsight (actual net_gain > 0).
- **Fitted lines:**
  - Round 1 (2020-22): intercept 34.38, slope **−0.264**;
  - Round 2 (2020-23): 18.49, 0.215;
  - Round 3 (2020-24): 11.25, 0.418.
- **Part 1, MAE (6 rows, cents/bu):** regression **7.16**, past average 8.38.
- **Part 2, scoreboard (total net gain over 6 rows, cents/bu; correct calls of 6):**

  | case | always sell | always store | past average | regression |
  |---|---|---|---|---|
  | low | 0 (0/6) | +106.5 (6/6) | +106.5 (6/6) | +86.5 (4/6) |
  | mid | 0 (6/6) | −61.5 (0/6) | 0 (6/6) | 0 (6/6) |
  | high | 0 (6/6) | −229.5 (0/6) | 0 (6/6) | 0 (6/6) |

- **Note:** the regression had the lower MAE but the worse low-case decisions. Its round-1 slope was negative
  (fitted on 6 points), so it forecast 2023 too low and said "sell" in 2023, missing +19.9¢ in total.
- **Files written:** `outputs/walk_forward_predictions.csv` (6 rows), `outputs/scoreboard.csv` (12 rows).

### 2026-11-15: FGP side project moved to `fgp_river_basis/` (no data values changed)

- **Moved with `git mv`** (history kept): the 5 `fgp_*.py` scripts, `data/fgp/river_basis_panel.csv`,
  `outputs/fgp_basis_chart.png`, and the 7 FGP-only raw files (`3192_2021/2022-08, -09, -11`,
  `usgs_07032000_flow_2021-08_2022-11.rdb`) into `fgp_river_basis/data/raw/`.
- **Raw files unchanged:** SHA-256 checksums of all 7 moved raw files match before and after the move.
- **Stay in `data/raw/`:** `3192_2021-10.csv` and `3192_2022-10.csv`, used by both projects
  (`03_build_silver.py` and `fgp_03_build_panel.py`). All 12 files listed in `03_build_silver.py` are present.
- **FGP log entries** (2026-11-11) moved to `fgp_river_basis/processing_log.md`; the `03_build_silver.py`
  file-list fix stays here as its own entry.
- Main-project data, scripts and outputs: not touched.

### 2026-11-15: FGP project moved to its own repository (no main-project data changed)

- **New repository:** https://github.com/Jessie-Ren699/river-basis-did, created with
  `git subtree split --prefix=fgp_river_basis` (keeps the 3 commits after the folder move). Pushed and verified
  before anything was removed here; its rerun of `fgp_03` -> `fgp_05` gave byte-identical outputs.
- **Removed here:** `fgp_river_basis/` (`git rm -r`). The files remain in this repository's git history.
- **Kept:** `data/raw/3192_2021-10.csv` and `3192_2022-10.csv` (used by `03_build_silver.py`). Exact copies
  (SHA-256 checked) are in the new repository. All 12 files listed in `03_build_silver.py` are present.
- **README:** the side-project line now links to the new repository; `fgp_river_basis/` removed from the folder layout.
- Earlier entries that mention `fgp_river_basis/` describe the layout at that time.

### 2026-11-21: USDA grain bids pulled for 5 more states (raw only, no cleaning)

- **Goal (user):** Oct and Apr cash bids for IL, IA, NE, SD, MN, IN. The plan was Oct 2010 → Apr 2026, but the
  MyMarketNews API has no bid detail before mid-2020 (headers from 2020-02-24, detail from 2020-07/08; Indiana from
  2020-11-10). The user approved **Oct 2020 → Apr 2026** (12 Oct/Apr months, decision years 2020-2025).
- **Reports:** IA 2850 (Iowa Daily Cash Grain Bids), NE 3225 (Nebraska Daily Elevator Grain Bids), SD 3186 (South Dakota
  Daily Grain Bids), MN 3049 (Southern Minnesota Daily Grain Bids; user chose 3049 only, not the barge report 3043),
  IN 3463 (Indiana Grain Bids). IL 3192: the existing `data/raw/3192_*.csv` files were **not re-pulled or copied**,
  only listed in the manifest.
- **Pull method (also how the IL files were made):** MARS API v1.2, `reports/<id>/Report Detail`,
  `q=report_begin_date=MM/01/YYYY:MM/<last day>/YYYY`, one month per request; results saved with
  `pd.DataFrame(results).to_csv(index=False)`, nothing changed. Re-pulling IL Oct 2020 this way gave a file
  **byte-identical** to `data/raw/3192_2020-10.csv`. Every request returned all its rows (well under the 100,000 cap).
  The pull script is in the session scratch folder (not in the repo).
- **New files:** `data/raw/usda_bids/<STATE>/<report_id>_<YYYY-MM>.csv`, 59 files, 27,472 rows, 55 columns each
  (same columns as 3192), plus `data/raw/usda_bids/manifest.csv` (72 rows: `file`, `rows`, `sha256`, `state`,
  `report_id`, `month`, `status`; includes the 12 IL files).
- **Rows by state (12 months):** IL 12,486 (existing), IA 3,750, NE 5,598, SD 5,383, MN 639, IN 12,102.
- **Missing:** IN 2020-10: API returned 0 rows, so no file was saved (manifest says MISSING).
- **Flags for cleaning:**
  - IN 2021-04, 2021-10, 2022-04 are weekly (4 report days); the last report on or before the 15th is the 13th, 12th and
    13th, not the futures dates. All other state-months have a report on the decision date (15th or the prior trading day).
  - MN from 2025-04 also reports forward bids (`current = No`), so its rows double; spot bids stay ~21-23 per month.
  - MN has one region (South); IN adds Barge Loading and Terminal elevators; NE and SD are Country Elevators only.
- **Checks:** existing `data/raw/*.csv` checksums unchanged; no file overwritten; API key read from `.env`, not printed.

### 2026-11-21: cash bids for 6 states in the pipeline (03, 06, 07 changed; rerun 03 → 09)

- **Why (user):** make the new state data part of the normal pipeline. The decision question stays Central Illinois.
- **`03_build_silver.py`:**
  - Reads every file listed in `data/raw/usda_bids/manifest.csv` (12 IL + 59 IA/NE/SD/MN/IN; IN 2020-10 has no file)
    and stops if any file's SHA-256 differs from the manifest. Adds a `state` column.
  - Filters, with rows after each: raw 39,958 → corn 15,604 → deliver now 10,090 → **Yellow corn 9,943** →
    drop 8 empty `¢/Bu` rows 9,935.
  - **New filter (user decision): Yellow corn only.** Indiana also reports White corn (147 rows, Ohio River barge
    elevators), a different product; futures are for Yellow #2. Illinois is all Yellow.
  - **New primary key:** (`date`, `state`, `region`, `buyer_type`, `transport_mode`). With (`date`, `state`, `region`,
    `buyer_type`), 469 Indiana rows repeated a key: Ohio River barge elevators post a Truck and a Truck/Rail bid on
    the same day (user chose to widen the key). 0 duplicates on the new key.
  - Output 9,935 rows × 14 cols: IL 3,024, IA 1,771, NE 1,750, SD 1,256, MN 255, IN 1,879. 0 MISSING prices.
- **`06_build_db.py`:** `corn_bids` gets `state` (NOT NULL) and the new 5-column PK; `transport_mode` is NOT NULL.
- **`07_build_gold.py`:** the cash-bid join also requires `state = 'IL'` (Iowa and South Dakota also have regions
  named North Central / South Central).
- **Rerun:** `03 --overwrite` → `04` → `05` → `06 --overwrite` → `07 --overwrite` → `08` → `09`. Previous outputs backed up in
  the session scratch folder.
- **Checks:**
  - The IL rows of the new `corn_bids_current.csv`, with `state` dropped, are **byte-identical** to the previous file (3,024 rows).
  - **Byte-identical to before:** `gold/gold_yearly.csv`, `outputs/scoreboard.csv`, `outputs/walk_forward_predictions.csv`,
    both charts, `clean/may_futures.csv`, `clean/tbill_decision.csv`.
  - 06: no duplicate PKs, every FK date in `calendar`, `foreign_key_check` empty; `corn_bids` 9,935 rows.
- **Changed files:** `data/clean/corn_bids_current.csv`, `data/clean/corn.db`. `data/raw/` not touched.
- **Docs:** `data_dictionary.md` (`state` column, new key, 6 states), README (pipeline map, cash-bid source).
