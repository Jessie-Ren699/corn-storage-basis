"""FGP side project, step 05: OLS models with robust standard errors.

Input : data/fgp/river_basis_panel.csv
Output: printed coefficient tables only (no files written)

Model B (main, user decision 2026-11-11): basis_cents ~ River * Y2022 * Post
Model A (alternative)                   : basis_cents ~ River + flow_100k + River:flow_100k

Standard errors:
- HC1: robust to uneven noise only (full tables).
- Newey-West (HAC), maxlags = 5 (key rows): also allows basis to be correlated over
  up to 5 trading days. Applied within each region x year series (statsmodels
  "hac-panel"), so lag 5 = 5 trading days of the same region, and Nov 2021 is not
  treated as the day before Sep 2022.
- For comparison only: plain row-order HAC, which treats the stacked panel as one
  time series, so 5 lags there is only about 1 trading day (4 regions per day).
"""
import pandas as pd
import statsmodels.formula.api as smf

IN = "data/fgp/river_basis_panel.csv"
MAXLAGS = 5
MODELS = {  # name -> (formula, key term)
    "Model B (main)": ("basis_cents ~ River * Y2022 * Post", "River:Y2022:Post"),
    "Model A (alternative)": ("basis_cents ~ River + flow_100k + River:flow_100k", "River:flow_100k"),
}

df = pd.read_csv(IN, parse_dates=["date"])
assert df[["basis_cents", "River", "flow_100k", "Y2022", "Post"]].notna().all().all()
# hac-panel needs rows grouped by series and in time order inside each series
df = df.sort_values(["region", "date"]).reset_index(drop=True)
series_id = pd.factorize(df["region"] + "_" + df["date"].dt.year.astype(str))[0]  # 8 series

key_rows = []
for name, (formula, key) in MODELS.items():
    model = smf.ols(formula, data=df)
    hc1 = model.fit(cov_type="HC1")
    nw = model.fit(cov_type="hac-panel", cov_kwds={"groups": series_id, "maxlags": MAXLAGS})
    nw_rows = model.fit(cov_type="HAC", cov_kwds={"maxlags": MAXLAGS})

    table = pd.DataFrame({"coef": hc1.params, "se_HC1": hc1.bse, "t": hc1.tvalues, "p": hc1.pvalues,
                          "ci_low": hc1.conf_int()[0], "ci_high": hc1.conf_int()[1]})
    print(f"\n{name}: {formula}")
    print(f"n = {int(hc1.nobs)}, R² = {hc1.rsquared:.3f}, adj. R² = {hc1.rsquared_adj:.3f}")
    print(table.round(3).to_string())

    for label, fit in [("HC1", hc1), (f"Newey-West, {MAXLAGS} trading days per region-year", nw),
                       (f"(comparison) row-order HAC, {MAXLAGS} rows", nw_rows)]:
        key_rows.append({"model": name, "term": key, "SE type": label, "coef": fit.params[key],
                         "SE": fit.bse[key], "p": fit.pvalues[key]})

print("\nKey rows:")
print(pd.DataFrame(key_rows).round(3).to_string(index=False))
