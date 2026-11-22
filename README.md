# Corn Storage Basis Analysis

**Question:** On October 15, should a Central Illinois corn holder store until
April 15 (hedged with May futures) or sell at harvest? And can a simple, honest
model make that call better than "always sell at harvest"?

The answer is measured through **basis gain** against a single futures contract,
compared with the cost of storage plus the opportunity cost of capital.

**Walkthrough:** [notebooks/00_walkthrough.ipynb](notebooks/00_walkthrough.ipynb) shows every pipeline step,
from the raw USDA pull to the walk-forward scoreboard, with a table or chart for each.

## Pipeline

| Step | Script | Input → output |
|---|---|---|
| Cash bids | `03_build_silver.py` | USDA grain bids for 6 states (IL, IA, NE, SD, MN, IN; listed in `data/raw/usda_bids/manifest.csv`) → `data/clean/corn_bids_current.csv` |
| May futures | `04_clean_futures.py` | `data/raw/may_futures.csv` → `data/clean/may_futures.csv` ($/bu) |
| T-bill | `05_tbill_rates.py` | `data/raw/fred_dtb6.csv` → `data/clean/tbill_decision.csv` |
| Database | `06_build_db.py` | the 3 clean CSVs → `data/clean/corn.db` (keys checked) |
| Gold | `07_build_gold.py` | `corn.db` + `data/raw/storage_costs.csv` → `data/gold/gold_yearly.csv` (every Country Elevators / Truck region in the 6 states: 34 regions, 194 region-years) |
| Charts | `08_charts.py` | gold → `outputs/scatter_gap.png`, `outputs/bars_by_year.png` |
| Walk-forward | `09_walk_forward.py` | gold → `outputs/walk_forward_predictions.csv`, `outputs/scoreboard.csv` |

Run in order 03 → 09 from the project folder (`06` and `07` need `--overwrite` to replace existing outputs).

## Plan

- **Location:** the question is framed for one Central Illinois region (USDA report **3192**). Since 2026-11-21 the
  analysis is run on every Country Elevators region in IL, IA, NE, SD, MN and IN (34 regions). See *To be determined*.
- **Commodity:** corn
- **Decision date:** Oct 15
- **Exit date:** Apr 15
- **Futures reference:** the **May contract** on both dates
- **Strategy tested:** storage hedge (store + sell May futures on Oct 15; sell corn and
  buy back futures on Apr 15) when the rule says store; otherwise sell at harvest.
- **Target variable:** `Basis(Apr 15) - Basis(Oct 15)`

## Definitions

```
Basis(t)      = CashPrice(t) - MayFutures(t)
Target        = Basis(Apr 15) - Basis(Oct 15)
Target_hat    = predicted Target, using only data available on Oct 15
StorageCost   = commercial storage charge, Oct 15 to Apr 15 (structure TBD)
InterestCost  = annual rate x 0.5 x CashPrice(Oct 15)
Hurdle        = StorageCost + InterestCost
Store if        Target_hat > Hurdle
```

- Holding the futures leg fixed at the May contract on both dates keeps the target a
  clean measure of local cash-market strength, free of contract-roll effects.
- Once hedged, the outcome depends on basis, not on the direction of corn prices.
- `annual rate` is the **6-month Treasury bill rate (FRED series DTB6)**, averaged over
  the **10 calendar days ending on the decision date** (decision date included), used
  **as a decimal** (FRED reports percent: 4.5 -> 0.045). 0.5 = the 6-month holding period.
- Including the decision date is allowed: the farmer can buy a T-bill at the market rate
  on the decision date; FRED publishes it about a day later.
- Interest is an **opportunity cost**: the T-bill return given up by holding corn
  instead of cash.

## Data sources

| Data | Source | How collected | Used for |
|---|---|---|---|
| Cash bids | [USDA AMS MyMarketNews](https://mymarketnews.ams.usda.gov/) (MARS) API, state grain-bid reports: IL 3192 (Illinois Grain Bids), IA 2850, NE 3225, SD 3186, MN 3049, IN 3463; Oct/Apr, Oct 2020 to Apr 2026 (the API has no earlier data) | API, one month per request; files and checksums in `data/raw/usda_bids/manifest.csv` | Cash price on Oct 15 and Apr 15 (every Country Elevators / Truck region) |
| May corn futures | CBOT settlements (ZCK21-ZCK26), read from [Barchart](https://www.barchart.com/futures/quotes/ZCK26/overview) | 12 settlements (Oct 15 and Apr 15, 6 contracts) typed by hand as raw quotes (e.g. `583-2`) | Basis on both dates; hedge result |
| Interest rate | [FRED, series DTB6](https://fred.stlouisfed.org/series/DTB6) (6-month T-bill, secondary market, discount basis) | Download | InterestCost |
| Storage costs | [farmdoc daily](https://farmdocdaily.illinois.edu/2025/10/annual-cost-of-storing-us-corn-and-soybeans-since-1973.html) (physical storage cost series); on-farm low case from Iowa Farm Bureau | Typed by hand into `data/raw/storage_costs.csv`, with source per row | StorageCost (low / mid / high cases) |
The MyMarketNews API is documented in USDA's [MyMarketNews API guide](https://mymarketnews.ams.usda.gov/mymarketnews-api).

## Units

- Futures are quoted in **cents and eighths**: `583-2` = 583 and 2/8 cents =
  **$5.8325/bu**. Parse the fraction before converting; reading `583-2` as 583.2 is wrong.
- **All prices are stored in $/bushel**, at least 4 decimals.
- Interest rates are converted from percent to decimal before use.

## Data range

- **Phase 1:** Jul 2020 to present, decision years **2020-2025**.
- **Phase 2:** backfill pre-2020 history (target ~20 decision years).

## Method

- **Walk-forward test:** each decision year is predicted using only earlier years.
  Example: train on 2020-2022, predict 2023; add 2023, predict 2024; and so on.
- **Minimum training window:** 3 years. In Phase 1 this leaves only 2023-2025 as test
  years (see *Limitations*).
- **No future leakage:** every input used for a decision on Oct 15 must have been
  published on or before Oct 15 of that year.
- **Region choice** is made on data coverage only, never on results.

## Evaluation (fixed before any results are seen)

**Benchmark:** sell everything on Oct 15. Because interest is counted inside the hurdle,
the benchmark scores **0 cents/bu** every year.

**Strategies compared (net of storage and interest, cents/bu):**

| Strategy | Rule |
|---|---|
| Benchmark | Always sell at harvest (0) |
| Always store | Store and hedge every year |
| Baseline rule | Store if the average realized gain of all prior years > hurdle |
| Model rule | Store if `Target_hat` > hurdle |
| Oracle | Perfect foresight: an upper bound, not a strategy |

**Scoreboard 1: prediction** (model vs. baseline forecast)
- Mean absolute error (MAE) of predicted vs. actual basis gain, cents/bu
- Out-of-sample R-squared vs. the baseline forecast (> 0 means the model beats it)
- Decision hit rate: share of years where the store/sell call was correct

**Scoreboard 2: money** (each strategy vs. the benchmark)
- Average net gain, cents/bu per year (headline result)
- Worst single year
- Share of years with a positive result
- Total dollars on 200,000 bushels (illustrative farm size)
- Sensitivity: results re-run with storage rate +/- 1 cent/bu/month

Both scoreboards are always reported. A more accurate forecast does not guarantee
better decisions; only errors near the hurdle change the decision.

## Limitations

- **Phase 1 is practice, not a conclusion:** 6 decision years, only 3 test years.
  Results can easily be luck.
- The T-bill is the risk-free rate. Farms with operating debt face a higher interest
  cost, which would raise the hurdle.
- **Ignored for now:** futures commissions, margin interest, grain shrink and
  quality risk.
- Six states and 34 regions, but regions in the same year share the same futures, rate and weather year, so they are
  not independent; results may not transfer to other states.
- **Storage cost (commercial, high case) is halved from a 12-month figure.** Elevators often charge a flat
  fee and then a monthly rate, so a 6-month hold likely costs more than half (about 68% under 2014
  central-Illinois rates). The high case may understate commercial storage cost.
- **Storage cost rate is from Ohio:** the farmdoc physical storage series uses one Ohio country elevator,
  not a Central Illinois rate.
- **On-farm storage (low case) rests on a weaker source** (Iowa Farm Bureau 2016, figure not attributed),
  the same 9¢ every year.
- A low October basis is not always temporary (e.g. a local buyer closing), so
  "low" alone is not a signal.

## To be determined

- **Region name:** which Central Illinois region within report 3192. Chosen by the
  most complete Oct/Apr coverage.
- ~~**Commercial storage rate and structure**~~ **Resolved 2026-11-13:** three cases for the 6-month hold,
  saved in `data/raw/storage_costs.csv` with sources: low = on-farm 9¢ (weaker source), high = farmdoc
  daily physical storage × 0.5 (commercial, Ohio elevator), mid = their average. Limits are listed
  under *Limitations*.
- **Predictors for Step 4:** candidate clues known on Oct 15 (October basis itself,
  stocks-to-use, barge rates, export inspections). At most 2-3 will be used, given
  the small number of years.

## Roadmap

- [x] 0 Question, definitions and evaluation fixed; folder built
- [ ] 1 Data: cash bids (3192), May futures, T-bill
- [ ] 2 Baseline forecast
- [ ] 3 Costs (storage + interest)
- [ ] 4 Clues known on Oct 15
- [ ] 5 Model + walk-forward test
- [ ] 6 Decision rule + scoreboards

## Future extensions (parking lot)

- Phase 2 backfill to ~20 years
- Compare the model with the elevator's **forward contract** bid for April delivery
- Interest at a farm operating-loan rate instead of the T-bill
- Write up the full set of grain marketing strategies (cash sale, storage hedge,
  unhedged storage, forward, hedge-to-arrive, basis contract, sell and re-own, options)
- Additional regions

## Folder layout

```
corn_analysis/
├── data/
│   ├── raw/      # untouched source pulls (committed; never edited)
│   └── clean/    # tidy, analysis-ready tables
├── docs/         # reference documents
├── notebooks/    # numbered steps: 01_pull_data, 02_baseline, ...
├── outputs/      # figures, tables, final results
├── .env          # API key (git-ignored)
├── .env.example  # template showing required variable names
├── .gitignore
├── CLAUDE.md     # working rules for Claude
└── README.md
```

## Setup

1. Copy `.env.example` to `.env` and fill in `API_KEY`.
2. Pull raw data into `data/raw/`; write cleaned tables to `data/clean/`.
3. `data/raw/` is committed as evidence: never edit it; re-pull with the scripts if needed.

## Notes

- MyMarketNews caps each API request at 100,000 records, so cash bids are pulled one
  month at a time. See USDA's [MyMarketNews API guide](https://mymarketnews.ams.usda.gov/mymarketnews-api).
- If Oct 15 or Apr 15 is not a trading day, use the nearest **prior** trading day and
  record which day was used.

## Side project

The ACCY 512 class project on Illinois River basis (separate from this plan) now has its own repository: [river-basis-did](https://github.com/Jessie-Ren699/river-basis-did).
