# Processing log: FGP river basis panel

What each FGP script does to the data, and what happened when it last ran. A new entry is added after
every data change. Raw files are only ever read.

**Paths:** entries dated before 2026-11-15 use the old locations (`notebooks/fgp_*.py`, `data/fgp/`,
`outputs/fgp_basis_chart.png`, `data/raw/` for all raw files). See the 2026-11-15 entry for the move.

## Change entries

### 2026-11-11: FGP side project, river basis panel built

- **Scope:** separate class side project (user decision). The main plan is unchanged.
- **New raw files (pulled, never edited):**
  - USDA 3192, "Report Detail" section, one month per request
    (method check: re-pulling Oct 2021 gave a file identical to the existing `3192_2021-10.csv`):
    `3192_2021-08.csv` 1,074 rows; `3192_2021-09.csv` 1,029; `3192_2021-11.csv` 992;
    `3192_2022-08.csv` 1,127; `3192_2022-09.csv` 1,062; `3192_2022-11.csv` 960 (all 55 cols).
  - `usgs_07032000_flow_2021-08_2022-11.rdb`: USGS Memphis daily mean flow, 487 days.
- **Output:** `data/fgp/river_basis_panel.csv`, 448 rows (112 dates x 4 regions), 8 cols, 0 MISSING.
- **Units exception (user decision):** `basis_cents` is in cents/bu, for this side project only.
  Everywhere else, prices stay in $/bu.
- **Rows dropped:**
  - 29 empty `¢/Bu` twin rows (no basis or price; each has a real row for the same date x region).
  - 55 of 167 trading days where not all 4 regions quote December (Z) on both the low and high bid:
    Aug and early Sep (September contract or mixed), and 2021-11-30 (North Central starts the roll to March).
- **December switch:** first all-December date 2021-09-01 and 2022-09-15.
  Post starts Sep 15 in both years (Sep 15 is not before the switch).
  **Flag:** this leaves 2022 with 0 pre-period (Post = 0) rows.
- **Not done:** drought index (skipped, listed as a limitation).
- **Side effect:** `03_build_silver.py` expects exactly 12 files matching `3192_20*.csv`; there are now 18,
  so it will stop at its first check (nothing is overwritten) until its file list is fixed.

### 2026-11-11: FGP Post rule changed; FGP chart saved

1. **Post rule (user choice, option b):** Post = 1 from **Oct 1 in both years** (was Sep 15).
   `fgp_03_build_panel.py --overwrite` rerun: still 448 rows, 0 MISSING; only `Post` changed (96 rows),
   all other columns identical to the previous file (backup in the session scratch folder).
   Post = 0 / Post = 1 rows: 2021 84 / 156; 2022 48 / 160.
   Oct 1, 2022 was a Saturday, so the first 2022 Post = 1 trading day is Oct 3.
2. *(Moved to the main project log on 2026-11-15: the `03_build_silver.py` file-list fix.)*
3. **New chart:** `notebooks/fgp_04_chart.py` -> `outputs/fgp_basis_chart.png`
   (basis by region, 2021 and 2022 side by side, dotted line at Oct 1).

### 2026-11-11: FGP flow_100k column added; first OLS models

- **Data change:** `fgp_03_build_panel.py` now adds `flow_100k = river_flow_cfs / 100,000`.
  Rerun with `--overwrite`: 448 rows, 9 cols, 0 MISSING. All old columns are identical to the
  previous file (backup in the session scratch folder). `flow_100k` 1.47 to 5.25 (mean 2.905).
- **Note:** the copy at `~/Desktop/ACCY 512/river_basis_panel.csv` (made earlier today) is the
  old 8-column version; it was not updated.
- **Models:** `notebooks/fgp_05_models.py` (prints only, no files written). OLS, HC1 robust SEs, n = 448.
  - Model A: `basis_cents ~ River + flow_100k + River:flow_100k`. R² 0.166.
    River:flow_100k = **1.575** cents per 100k cfs (SE 0.880, p = 0.074, 95% CI -0.15 to 3.30).
    flow_100k = 3.460 (SE 0.532). River = -1.899 (SE 2.765).
  - Model B: `basis_cents ~ River * Y2022 * Post`. R² 0.218.
    River:Y2022:Post = **-20.035** cents (SE 4.181, p < 0.001).
- **Check (not saved):** Model A with SEs clustered by date: River:flow_100k SE 0.913, p = 0.084.
- **Flags:** HC1 does not allow for day-to-day correlation in basis, so the SEs are likely too small.
  Flow barely overlaps between years (2021: 2.67 to 5.25; 2022: 1.47 to 3.08) and falls through
  the season (correlation with date order -0.66), so the flow terms also pick up year and season effects.

### 2026-11-11: FGP Desktop copy replaced; Newey-West SEs; Model B is now the main model

1. **Desktop copy:** `~/Desktop/ACCY 512/FInal Project/river_basis_panel.csv` (the user had moved it
   into `FInal Project`) was checked to be the old 8-column file, then replaced with the 9-column
   project file (byte-for-byte identical, 448 rows).
2. **Newey-West (HAC) SEs, maxlags = 5,** added to `fgp_05_models.py`. Applied within each
   region x year series (statsmodels `hac-panel`, 8 series), so 5 lags = 5 trading days of one region.
   Coefficients are unchanged; only the SEs change.

   | Model | Term | coef | SE HC1 (p) | SE Newey-West (p) |
   |---|---|---|---|---|
   | B (main) | River:Y2022:Post | -20.035 | 4.181 (0.000) | 8.369 (0.017) |
   | A (alternative) | River:flow_100k | 1.575 | 0.880 (0.074) | 1.872 (0.400) |

   Comparison only: plain row-order HAC (5 rows, about 1 trading day) gives SE 8.334 (p 0.016) and
   1.856 (p 0.396), so the conclusions do not depend on which version is used.
3. **Main model:** Model B (`basis_cents ~ River * Y2022 * Post`) is now the main model (user decision);
   Model A (flow) is the alternative. Script labels and README updated. Replaces the "Model A (main)"
   label in the previous entry.

### 2026-11-15: moved to `fgp_river_basis/`; paths updated; outputs identical

- **Moved with `git mv`** from the main project (history kept): `notebooks/fgp_01..05` -> `notebooks/`,
  `data/fgp/river_basis_panel.csv` -> `data/`, `outputs/fgp_basis_chart.png` -> `outputs/`,
  7 FGP-only raw files -> `data/raw/` (all paths here relative to `fgp_river_basis/`).
- **Shared raw files** `3192_2021-10.csv`, `3192_2022-10.csv` stay in the main `data/raw/`; `fgp_03` now reads
  Oct from there and Aug/Sep/Nov + USGS from `fgp_river_basis/data/raw/`.
- **Checks:** SHA-256 of the 7 moved raw files unchanged. Rerun `fgp_03 --overwrite` -> `fgp_04` -> `fgp_05`:
  panel CSV (448 rows) and chart PNG **byte-for-byte identical** to the pre-move files; `fgp_05` printout identical.
