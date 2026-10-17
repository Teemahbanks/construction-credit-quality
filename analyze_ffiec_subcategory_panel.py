#!/usr/bin/env python3
"""Run subtype-specific fixed-effects sensitivity analyses on FFIEC bank-year data.

Category past-due and nonaccrual stocks—not defaults—are measured against the
same-year category balance, and lagged exposure is available at t-1. Results
cover both balance floors and outcome definitions.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

ROOT = Path(__file__).parent
p = pd.read_csv(
    ROOT / "data/processed/ffiec_construction_bank_panel_2021_2025.csv",
    dtype={"IDRSSD": str},
).sort_values(["IDRSSD", "year"])
rows = []
for category, balance, problem, nonacc in [
    (
        "1-4-family residential construction",
        "residential_construction",
        "problem_residential",
        "nonaccrual_res",
    ),
    (
        "other construction and land-development",
        "other_construction_land",
        "problem_other_construction",
        "nonaccrual_other",
    ),
]:
    d = p.copy()
    d["exposure_share_of_total_loans"] = d[balance] / d.total_loans.where(
        d.total_loans.gt(0)
    )
    d["category_problem_share"] = d[problem] / d[balance].where(d[balance].gt(0))
    d["category_nonaccrual_share"] = d[nonacc] / d[balance].where(d[balance].gt(0))
    for c in [
        balance,
        "exposure_share_of_total_loans",
        "category_problem_share",
        "total_assets",
        "equity_share_assets",
    ]:
        d["lag_" + c] = d.groupby("IDRSSD", sort=False)[c].shift(1)
    d["lag_log_assets"] = np.log(d.lag_total_assets.where(d.lag_total_assets.gt(0)))
    d["previous_year"] = d.groupby("IDRSSD", sort=False).year.shift(1)
    for floor in [1000, 5000]:
        sample = d[
            d.year.between(2022, 2025)
            & d.previous_year.eq(d.year - 1)
            & d["lag_" + balance].ge(floor)
            & d[balance].ge(floor)
        ].copy()
        regressors = [
            "lag_exposure_share_of_total_loans",
            "lag_category_problem_share",
            "lag_log_assets",
            "lag_equity_share_assets",
        ]
        sample = sample.dropna(
            subset=regressors + ["category_problem_share", "category_nonaccrual_share"]
        )
        reg = sample.set_index(["IDRSSD", "year"]).sort_index()
        w = reg["lag_" + balance] / reg["lag_" + balance].mean()
        for target in ["category_problem_share", "category_nonaccrual_share"]:
            fitted = PanelOLS.from_formula(
                target
                + " ~ 1 + "
                + " + ".join(regressors)
                + " + EntityEffects + TimeEffects",
                reg,
                weights=w,
                drop_absorbed=True,
            ).fit(cov_type="clustered", cluster_entity=True)
            v = "lag_exposure_share_of_total_loans"
            ci = fitted.conf_int().loc[v]
            rows.append(
                dict(
                    category=category,
                    outcome=target,
                    minimum_both_year_balance_thousand_usd=floor,
                    n_bank_years=int(fitted.nobs),
                    n_bank_ids=sample.IDRSSD.nunique(),
                    concentration_coefficient=float(fitted.params[v]),
                    bank_clustered_95_low=float(ci.iloc[0]),
                    bank_clustered_95_high=float(ci.iloc[1]),
                    bank_clustered_p=float(fitted.pvalues[v]),
                    within_r2=float(fitted.rsquared_within),
                )
            )
o = ROOT / "data/followon_results"
o.mkdir(exist_ok=True)
result = pd.DataFrame(rows)
result.to_csv(o / "subcategory_bank_year_fe_sensitivity.csv", index=False)
print(result.to_string(index=False))
