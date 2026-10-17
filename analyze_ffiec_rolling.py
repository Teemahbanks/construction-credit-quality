#!/usr/bin/env python3
"""Rolling-origin bank-level construction problem-balance diagnostic, 2024–25.

Prior-year bank data define cohorts, denominators, and features. Fitted WLS uses
previous outcome years only. Later-amended historical filing vintages and common
shocks prevent this from being a real-time validated deployment forecast.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from analyze_ffiec_credit_risk import prepare, FEATURES, forecast_holdout

ROOT = Path(__file__).parent
p = pd.read_csv(
    ROOT / "data/processed/ffiec_construction_bank_panel_2021_2025.csv",
    dtype={"IDRSSD": str},
)
m = pd.read_csv(ROOT / "data/processed/ffiec_macro_context_2021_2025.csv")
_, forecast = prepare(p, m)
out = ROOT / "data/followon_results"
out.mkdir(exist_ok=True)
rows = []
for year in [2024, 2025]:
    train = forecast[forecast.year.between(2022, year - 1)]
    test = forecast[forecast.year == year].copy()
    assert len(train) > 2000 and len(test) > 1000
    fit = sm.WLS(
        train.future_problem_to_prior_balance,
        sm.add_constant(train[FEATURES], has_constant="add"),
        weights=train.lag_construction_loans,
    ).fit()
    pred = np.asarray(
        fit.predict(sm.add_constant(test[FEATURES], has_constant="add"))
    ).clip(min=0)
    prev = p[p.year == year - 1]
    avg = float(prev.problem_loans.sum() / prev.construction_loans.sum())
    target = test.future_problem_to_prior_balance.to_numpy()
    w = test.lag_construction_loans.to_numpy()
    for name, v in [
        (
            "lagged_bank_share",
            test.lag_problem_share_construction.to_numpy().clip(min=0),
        ),
        ("prior_year_portfolio_mean", np.repeat(avg, len(test))),
        ("lagged_predictor_wls", pred),
    ]:
        rows.append(
            dict(
                holdout_year=year,
                n_test_banks=len(test),
                training_outcome_years=(
                    f"2022-{year-1}"
                    if name == "lagged_predictor_wls"
                    else str(year - 1)
                ),
                benchmark=name,
                mae_percentage_points=100 * np.mean(abs(target - v)),
                prior_exposure_weighted_mae_percentage_points=100
                * np.average(abs(target - v), weights=w),
                prior_exposure_weighted_rmse_percentage_points=100
                * np.sqrt(np.average((target - v) ** 2, weights=w)),
                observed_problem_to_prior_balance_pct=100
                * np.average(target, weights=w),
            )
        )
    if year == 2025:
        prior = pd.DataFrame(forecast_holdout(forecast, p)[0])
        new = pd.DataFrame(rows).query("holdout_year==2025")
        for n in prior.benchmark:
            a = prior[prior.benchmark == n].iloc[0]
            b = new[new.benchmark == n].iloc[0]
            assert (
                abs(
                    a.prior_exposure_weighted_mae_percentage_points
                    - b.prior_exposure_weighted_mae_percentage_points
                )
                < 1e-10
            )
f = pd.DataFrame(rows)
f.to_csv(out / "rolling_2024_2025_holdout_benchmarks.csv", index=False)
print(f.to_string(index=False))
