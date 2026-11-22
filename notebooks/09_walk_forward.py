"""Step 09: walk-forward test of the store/sell rule.

Input : data/gold/gold_yearly.csv (read only)
Output: outputs/walk_forward_predictions.csv  one row per test row (year x region)
        outputs/scoreboard.csv                one row per storage case x strategy

Setup (user, 2026-11-13):
- All regions pooled (since 2026-11-21: every Country Elevators / Truck region in IL, IA, NE, SD,
  MN, IN; one row per region_id per decision year; until then IL North + South Central only).
- Test years 2023, 2024, 2025. Each round trains ONLY on decision years before the test year.
  No future data: a training year's gap_closed is known by Apr 15 of the next calendar year,
  before the test year's Oct 15. gap_oct, interest and storage are known on Oct 15.
- Forecasts of gap_closed for each test row:
    regression   : OLS gap_closed ~ gap_oct on the training rows, applied to the test row's gap_oct
    past average : mean gap_closed of the training rows
- Rule (per storage case c): store if predicted gap_closed - interest > storage_c.
- Strategies: always sell (net 0), always store, past average, regression.
- Net gain per test row = gap_closed - storage_c - interest if store, else 0 (= net_gain_c_cents).
- Correct call = matches the hindsight best choice (store if actual net_gain_c_cents > 0).

Run from the project folder:
    python notebooks/09_walk_forward.py
"""
import numpy as np
import pandas as pd

GOLD = "data/gold/gold_yearly.csv"
OUT_PRED = "outputs/walk_forward_predictions.csv"
OUT_SCORE = "outputs/scoreboard.csv"
TEST_YEARS = [2023, 2024, 2025]
CASES = ("low", "mid", "high")
STRATEGIES = ("always sell", "always store", "past average", "regression")

gold = pd.read_csv(GOLD)
need = ["decision_year", "region_id", "gap_oct_cents", "gap_closed_cents", "interest_cents"] + \
       [f"storage_{c}_cents" for c in CASES] + [f"net_gain_{c}_cents" for c in CASES]
assert gold[need].notna().all().all(), "missing values in gold"
assert not gold.duplicated(["decision_year", "region_id"]).any(), "duplicate (decision_year, region_id)"

# 1. Walk-forward forecasts
rows = []
for rnd, test_year in enumerate(TEST_YEARS, start=1):
    train = gold[gold["decision_year"] < test_year]          # past years only
    test = gold[gold["decision_year"] == test_year]
    assert train["decision_year"].max() < test_year
    slope, intercept = np.polyfit(train["gap_oct_cents"], train["gap_closed_cents"], 1)  # OLS
    avg = train["gap_closed_cents"].mean()
    years = f"{train['decision_year'].min()}-{train['decision_year'].max()}"
    print(f"Round {rnd}: train {years} (n = {len(train)}) -> predict {test_year}: "
          f"intercept = {intercept:.3f}, slope = {slope:.4f}; past average = {avg:.3f}")
    for _, r in test.iterrows():
        rows.append({
            "round": rnd, "test_year": test_year, "region_id": r["region_id"],
            "train_years": years, "n_train": len(train),
            "intercept": intercept, "slope": slope,
            "gap_oct_cents": r["gap_oct_cents"],
            "actual_gap_closed_cents": r["gap_closed_cents"],
            "pred_regression_cents": intercept + slope * r["gap_oct_cents"],
            "pred_past_average_cents": avg,
            "interest_cents": r["interest_cents"],
            **{f"storage_{c}_cents": r[f"storage_{c}_cents"] for c in CASES},
            **{f"net_gain_{c}_cents": r[f"net_gain_{c}_cents"] for c in CASES},
        })
pred = pd.DataFrame(rows)
pred["err_regression_cents"] = pred["pred_regression_cents"] - pred["actual_gap_closed_cents"]
pred["err_past_average_cents"] = pred["pred_past_average_cents"] - pred["actual_gap_closed_cents"]

# 2. Store/sell calls for each case and strategy (all inputs known on Oct 15)
for c in CASES:
    storage, interest = pred[f"storage_{c}_cents"], pred["interest_cents"]
    pred[f"best_store_{c}"] = pred[f"net_gain_{c}_cents"] > 0             # hindsight
    pred[f"store_always_store_{c}"] = True
    pred[f"store_past_average_{c}"] = pred["pred_past_average_cents"] - interest > storage
    pred[f"store_regression_{c}"] = pred["pred_regression_cents"] - interest > storage

# 3. Scoreboard
KEY = {"always sell": None, "always store": "always_store",
       "past average": "past_average", "regression": "regression"}
score = []
for c in CASES:
    for s in STRATEGIES:
        store = (pd.Series(False, index=pred.index) if KEY[s] is None
                 else pred[f"store_{KEY[s]}_{c}"])
        net = np.where(store, pred[f"net_gain_{c}_cents"], 0.0)
        score.append({"storage_case": c, "strategy": s, "n_test_rows": len(pred),
                      "times_stored": int(store.sum()),
                      "total_net_gain_cents": net.sum(),
                      "mean_net_gain_cents": net.mean(),
                      "worst_row_cents": net.min(),
                      "correct_calls": int((store == pred[f"best_store_{c}"]).sum())})
score = pd.DataFrame(score)

# Print results
pd.set_option("display.width", 200)
show = pred[["test_year", "region_id", "gap_oct_cents", "actual_gap_closed_cents",
             "pred_regression_cents", "err_regression_cents",
             "pred_past_average_cents", "err_past_average_cents"]].copy()
print("\nPart 1: predicted vs. actual gap_closed (cents/bu); error = predicted - actual")
print(show.round(2).to_string(index=False, max_rows=12))
mae = {"regression": pred["err_regression_cents"].abs().mean(),
       "past average": pred["err_past_average_cents"].abs().mean()}
print(f"MAE over {len(pred)} test rows: regression {mae['regression']:.2f}, "
      f"past average {mae['past average']:.2f}")

print("\nPart 2: calls per test row (S = store, - = sell; best = hindsight)")
for c in CASES:
    t = pred[["test_year", "region_id"]].copy()
    t["actual_net"] = pred[f"net_gain_{c}_cents"].round(1)
    for col, name in [(f"best_store_{c}", "best"), (f"store_past_average_{c}", "past_avg"),
                      (f"store_regression_{c}", "regression")]:
        t[name] = pred[col].map({True: "S", False: "-"})
    print(f"\n[{c}] calls per test year (S = store, n = {len(t)} test rows):")
    print(t.groupby("test_year")[["best", "past_avg", "regression"]].agg(lambda s: f"{(s == 'S').sum()}/{len(s)} store").to_string())

print(f"\nScoreboard (cents/bu, {len(pred)} test rows):")
print(score.round(2).to_string(index=False))

# Save (outputs only; no data files are touched)
pred.to_csv(OUT_PRED, index=False)
score.to_csv(OUT_SCORE, index=False)
print(f"\nSaved {OUT_PRED} ({len(pred)} rows) and {OUT_SCORE} ({len(score)} rows)")
