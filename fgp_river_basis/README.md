# FGP: Illinois River Basis Panel

**ACCY 512 class project.** Separate from the main corn store-or-sell project in the
[repository root](../README.md); it does not change that project's plan, roadmap or evaluation.

**Walkthrough:** [walkthrough.ipynb](walkthrough.ipynb) shows each step, from the raw USDA and USGS
pulls to the regression results, with a table or chart for each.

## Research question

After Oct 1, 2022, did corn basis at Illinois River barge-loading elevators fall relative to
country elevators, compared with the same window in 2021, and how does that relate to
Mississippi River flow?

## Data sources

| Data | Source | Used for |
|---|---|---|
| Daily corn bids and basis | USDA AMS [MyMarketNews](https://mymarketnews.ams.usda.gov/), report **3192** (Illinois Grain Bids), via the MARS API; report page: [viewReport/3192](https://mymarketnews.ams.usda.gov/viewReport/3192) | `basis_cents` by region and day, Aug-Nov 2021 and 2022 |
| River flow | USGS site **07032000**, Mississippi River at Memphis, daily mean discharge (parameter 00060), via [USGS Water Services](https://waterservices.usgs.gov/nwis/dv/); site page: [USGS-07032000](https://waterdata.usgs.gov/monitoring-location/USGS-07032000/) | `river_flow_cfs`, `flow_100k` |

USGS has no daily river stage (feet) at this site, so flow is used instead.

## Run order

Run from the repository root with Python:

```
python fgp_river_basis/notebooks/fgp_01_pull_3192.py        # pull USDA 3192 Aug/Sep/Nov (needs API_KEY in .env)
python fgp_river_basis/notebooks/fgp_02_pull_usgs_flow.py   # pull USGS daily flow
python fgp_river_basis/notebooks/fgp_03_build_panel.py      # build the panel (--overwrite to replace)
python fgp_river_basis/notebooks/fgp_04_chart.py            # basis-by-region chart
python fgp_river_basis/notebooks/fgp_05_models.py           # regressions (prints only)
```

`fgp_01` and `fgp_02` never overwrite an existing raw file. The October 2021 and 2022 pulls
(`3192_2021-10.csv`, `3192_2022-10.csv`) are shared with the main project, so they stay in the
root `data/raw/`; the other raw files are in `fgp_river_basis/data/raw/`.

## Panel

`data/river_basis_panel.csv`: one row = region x trading day, 448 rows (112 dates x 4 regions), 0 missing.

- **Regions (report 3192):** North Illinois River and South Illinois River (`River = 1`, barge loading
  elevators); North Central and South Central (`River = 0`, country elevators).
- **Dates:** Aug-Nov 2021 and 2022, kept only on days when all 4 regions quote the December (Z) futures.
- **Columns:** `date`, `region`, `basis_cents`, `futures_month`, `River`, `Y2022`, `Post`,
  `river_flow_cfs`, `flow_100k`.
- **`Post`** = 1 from Oct 1 in both years. **`Y2022`** = 1 in 2022.
- **Units:** basis is kept in **cents/bu** here (the main project uses $/bu).

## Method: difference-in-differences

- **Model B (main):** `basis_cents ~ River * Y2022 * Post`. The key term `River:Y2022:Post` asks how much
  more (or less) river basis changed after Oct 1 in 2022 than in 2021, relative to country elevators.
- **Model A (alternative):** `basis_cents ~ River + flow_100k + River:flow_100k`. The key term asks how
  river basis moves with Mississippi flow, relative to country elevators.
- OLS with HC1 robust standard errors, plus Newey-West (HAC, 5 trading days) standard errors within
  each region x year series.

Results and every data decision are recorded in [processing_log.md](processing_log.md).

## Limitations

- Only 2 years and 4 regions; flow barely overlaps between the two years, so flow terms also pick up
  year and season effects.
- No drought index (US Drought Monitor skipped).

## Folder layout

```
fgp_river_basis/
├── data/
│   ├── raw/                    # FGP-only raw pulls (never edited)
│   └── river_basis_panel.csv
├── notebooks/                  # fgp_01 ... fgp_05
├── outputs/fgp_basis_chart.png
├── processing_log.md
├── README.md
└── walkthrough.ipynb
```
