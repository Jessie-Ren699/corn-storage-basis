# Data dictionary

The project asks: on Oct 15, should a Central Illinois farmer store corn until Apr 15
(hedged with May futures) or sell at harvest? These tables hold the prices and rates
needed to answer it. All tables live in `data/clean/corn.db` (SQLite). Each one except
`calendar` is also saved as a CSV: `gold_yearly` in `data/gold/`, the rest in `data/clean/`. Dates are `YYYY-MM-DD`. Prices are $/bu
unless the column name ends in `_cents`. Blank values are NULL and never filled.

| Table | One row = | Primary key | Built by |
|---|---|---|---|
| corn_bids_current | one region's cash bid from one buyer type on one day | (`date`, `region`, `buyer_type`) | `03_build_silver.py`; loaded into the db as `corn_bids` by `06_build_db.py` |
| may_futures | one May corn futures settlement on one hedge date | `date` | `04_clean_futures.py`; loaded by `06_build_db.py` |
| tbill_decision | the T-bill rate on one decision date | `decision_date` | `05_tbill_rates.py`; loaded by `06_build_db.py` |
| calendar | one calendar day | `date` | `06_build_db.py` (generated) |
| gold_yearly | one region in one decision year | (`decision_year`, `region`) | `07_build_gold.py` → `data/gold/gold_yearly.csv` and the db table |
| storage_costs (input file, not a db table) | one decision year's storage cost cases | `decision_year` | typed by hand into `data/raw/storage_costs.csv`; read by `07_build_gold.py` |

## corn_bids_current

What local grain elevators and processors offered farmers for corn, by Illinois region
and day. It comes from USDA MyMarketNews report 3192 (Illinois Grain Bids). It supplies
the cash side of basis. 3,024 rows. The 8 empty `¢/Bu` rows were dropped (see
`processing_log.md`).

**Primary key:** (`date`, `region`, `buyer_type`)

| Column | Meaning |
|---|---|
| date | The day USDA reported the bids (USDA `report_date`). |
| commodity | Always `Corn`; soybeans and wheat were filtered out. |
| region | The Illinois trading region the bids come from (USDA `trade_loc`), e.g. North Central, South Central, Wabash. 12 regions. |
| buyer_type | The kind of buyer posting the bid (USDA `delivery_point`): Country Elevators (local elevators that buy from farmers), Barge Loading Elevators (on the river, ship by barge), Mills and Processors (e.g. ethanol plants), Terminal Elevators. |
| deliver_now | Spot vs. forward (USDA `current`). True = the elevator's bid for corn delivered now; False = a forward contract for later delivery. All rows are True because we kept only spot bids. Stored as 1 in the database. |
| cash_price | The local cash price: the average bid posted by grain elevators in that region that day (USDA `avg_price`). It is an offer to buy, not a price for corn already delivered. It is NOT the futures price; cash minus futures is the basis. |
| cash_price_low | The lowest bid among those elevators that day (USDA `price Min`). |
| cash_price_high | The highest bid among those elevators that day (USDA `price Max`). |
| price_unit | Always `$ Per Bushel`. |
| grain_class | Always `Yellow`, which is regular field corn. |
| grain_grade | Always `US #2`, the standard quality grade that bids and futures are quoted for. |
| price_point | `Delivered` (USDA `freight`): the price the farmer gets when they bring the grain to the buyer, so the farmer pays the transport. |
| transport_mode | Every row is `Truck` because that's how the data came: farmers haul corn to elevators by truck. It is not a filter we applied. |

## may_futures

The price of the CBOT May corn futures contract on each hedge date, typed by hand from
Barchart. Selling May futures in October locks in the futures price. Buying them back in
April closes the hedge. With the hedge in place, only the change in basis is left at risk. 12 rows: 6 decision years × an Oct (open)
and an Apr (close) date, on the same contract both times.

**Primary key:** `date`

| Column | Meaning |
|---|---|
| decision_year | The harvest year the store-or-sell decision belongs to (2020-2025). |
| date | Oct 15 or Apr 15, or the nearest prior trading day if the market was closed. |
| futures_contract | Exchange code, e.g. `ZCK21` (ZC = corn, K = May, 21 = 2021). |
| contract_name | The code in words, e.g. `May 2021 corn`. |
| leg | `Oct (open hedge)`: sell futures when storing starts. `Apr (close hedge)`: buy them back when the corn is sold. |
| settle_raw | The exchange's official end-of-day price as quoted, in cents and eighths (`583-2` = 583.25¢). Typed by hand from Barchart. |
| source | Where it was read: `Barchart settlement`. |
| may_futures_price | `settle_raw` converted to $/bu (`583-2` → 5.8325), not rounded. |

## tbill_decision

The 6-month T-bill rate (FRED DTB6) on each decision date. Storing corn means waiting
6 months for the money instead of investing it, and this rate prices that opportunity
cost (the interest part of the hurdle). Rate = average of DTB6 over the 10 calendar
days ending on the decision date. The decision date counts because the farmer can buy a T-bill at the
market rate that day; FRED publishes it about a day later. 6 rows.

**Primary key:** `decision_date`

| Column | Meaning |
|---|---|
| decision_year | The harvest year of the decision (2020-2025). |
| decision_date | The Oct decision date (same dates as the Oct rows of `may_futures`). |
| window_start | First day of the 10-day averaging window. |
| window_end | Last day of the window (the decision date). |
| n_days_used | How many days in the window had a published rate (none on weekends and holidays). |
| dtb6_avg_pct | The average rate as text, e.g. `4.02%`. For reading only. |
| rate_decimal | The same rate as a decimal, e.g. 0.040229. Use this in calculations. |

## calendar

Every day from 2020-01-01 to 2026-12-31 (2,557 rows), including weekends and holidays. It
has no business content. It lets the database reject any date that doesn't exist.

**Primary key:** `date`

| Column | Meaning |
|---|---|
| date | One calendar day. |

## gold_yearly

The analysis table: for each region and decision year, everything needed to judge
"store or sell". It holds the October and April prices, how much the gap between futures
and cash narrowed while storing, and the cost of waiting. Covers Country Elevators in North Central
and South Central, 2020-2025 (12 rows). Saved both as the db table and as
`data/gold/gold_yearly.csv`.

**Primary key:** (`decision_year`, `region`)

| Column | Meaning |
|---|---|
| decision_year | The harvest year of the decision (2020-2025). |
| region | `North Central` or `South Central`. |
| buyer_type | Always `Country Elevators`, the buyers a farmer would actually deliver to. |
| oct_date | The Oct decision date. |
| oct_cash | Local cash bid on `oct_date`: what selling at harvest would pay. |
| oct_futures | May futures on `oct_date`: the price the hedge locks in. |
| apr_date | The Apr exit date. |
| apr_cash | Local cash bid on `apr_date`: what the stored corn sells for. |
| apr_futures | The same May contract on `apr_date`: where the hedge is closed. |
| rate_decimal | T-bill rate on `oct_date`, from `tbill_decision`. |
| gap_oct_cents | How far cash sits below futures in October, in cents: (`oct_futures` − `oct_cash`) × 100. This is X. |
| gap_apr_cents | The same gap in April. |
| gap_closed_cents | How much the gap narrowed while storing: `gap_oct_cents` − `gap_apr_cents`. This is Y, the gain from a hedged storage, equal to the README's Target. |
| interest_cents | What waiting 6 months costs in lost T-bill interest: `rate_decimal` × 0.5 × `oct_cash` × 100. |
| breakeven_storage_cents | The most a 6-month storage could cost and storing still break even: `gap_closed_cents` − `interest_cents`. Storing wins in a case when that case's storage cost is below this. |
| storage_low_cents | Storage cost for the 6-month hold, low case = on-farm bins: 1.5¢/bu/month × 6 = 9¢. Weaker source (see `storage_costs`). |
| storage_mid_cents | Middle case: (low + high) / 2. |
| storage_high_cents | High case = commercial elevator: farmdoc physical storage ($/bu/year) × 0.5 × 100. |
| hurdle_low_cents, hurdle_mid_cents, hurdle_high_cents | What storing must earn to pay off: storage (that case) + `interest_cents`. |
| net_gain_low_cents, net_gain_mid_cents, net_gain_high_cents | Gain from storing after all costs: `gap_closed_cents` − storage − `interest_cents`. Positive = storing beat selling at harvest. The corn is sold on Apr 15, the day the hedge closes, so there is no extra holding period. |
| store_wins_low, store_wins_mid, store_wins_high | True if that case's net gain > 0. Stored as 1/0 in the database. |

## storage_costs (input file `data/raw/storage_costs.csv`)

The cost of physically storing corn from Oct 15 to Apr 15 (6 months), in three cases. Typed by hand from
articles (user-approved 2026-11-13). Not loaded into `corn.db`; `07_build_gold.py` reads it directly and
copies the three cost columns into `gold_yearly`. 6 rows.

**Primary key:** `decision_year`

| Column | Meaning |
|---|---|
| decision_year | The harvest year of the decision (2020-2025). Marketing year 2020 = storage from Oct 2020. |
| storage_low_cents | On-farm case: 9¢ every year (1.5¢/bu/month × 6, the middle of Iowa Farm Bureau's 1-2¢ range for owning on-farm bins; 2016, figure not attributed, so a **weaker source**). No interest included. |
| storage_mid_cents | (low + high) / 2. |
| storage_high_cents | Commercial case: farmdoc daily "physical storage" ($/bu per 12 months, commercial, Ohio country elevator) × 0.5. 2020-2023 read from the article's Figure 1 chart (±0.02 $/bu/yr); 2024 stated in text ($1.30); 2025 = 2024 value carried forward (flagged). Physical only, not total, because interest is counted separately from T-bills. |
| source_url_low | Link to the low-case source. |
| source_url_high | Link to the high-case source (the farmdoc article; for 2024-2025 the OSU companion article that states $1.30). |
| note | How each number was obtained ("typed from article", "read from chart", carried forward). |

**Known limits:** ×0.5 probably understates commercial cost, because elevators often charge a flat fee then monthly (about 68% of the yearly cost for this 6-month hold under 2014 central-Illinois rates); the commercial rate is Ohio, not Illinois.

## Keys and relationships

**Foreign keys are off by default in SQLite.** Run `PRAGMA foreign_keys = ON;` every time
you open a connection, or they are not enforced.

| Table (in corn.db) | Primary key | Foreign key |
|---|---|---|
| calendar | `date` | none |
| corn_bids | (`date`, `region`, `buyer_type`) | `date` → `calendar(date)` |
| may_futures | `date` | `date` → `calendar(date)` |
| tbill_decision | `decision_date` | `decision_date` → `calendar(date)` |
| gold_yearly | (`decision_year`, `region`) | `oct_date`, `apr_date` → `calendar(date)` |

```
                     calendar (date)
              1 /          | 1          \ 1
               /           |             \
       0..many/            | 0..1         \ 0..1
     corn_bids          may_futures     tbill_decision
  (date, region,          (date)        (decision_date)
   buyer_type)
```

- **calendar → corn_bids** (one-to-many): a date has zero or many bids, one per region
  and buyer type. Weekends and holidays have none.
- **calendar → may_futures** (one-to-zero-or-one): only the 12 Oct/Apr hedge dates.
- **calendar → tbill_decision** (one-to-zero-or-one): only the 6 Oct decision dates.
- **calendar → gold_yearly** (via `oct_date` and `apr_date`): each gold row points to
  one Oct and one Apr date.
- **Joining one decision year:** the Oct leg of `may_futures.date` = `tbill_decision.decision_date`
  = `corn_bids.date` gives the Oct cash price, futures and rate. The Apr leg joins
  `may_futures.date` to `corn_bids.date`. Both legs share `decision_year`. This is how
  `07_build_gold.py` builds `gold_yearly`.
