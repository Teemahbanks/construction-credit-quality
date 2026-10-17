#!/usr/bin/env python3
"""Run FDIC fixed-effects sensitivity checks for residential and other construction.

Results are associational rather than causal or loan-stage estimates. The output
covers both categories, sample periods, and outcome definitions.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

R = Path(__file__).parent
p = pd.read_csv(
    R / "data/fdic_historical_analysis/fdic_bank_panel_2012_2025.csv",
    dtype={"IDRSSD": str},
).sort_values(["IDRSSD", "year"])
rows = []
for category, loan, problem, nonacc in [
    (
        "1-4-family residential construction",
        "LNRECNFM",
        "problem_residential",
        "NARECNFM",
    ),
    (
        "other construction and land development",
        "LNRECNOT",
        "problem_other",
        "NARECNOT",
    ),
]:
    d = p.copy()
    d["category_exposure_share"] = d[loan] / d.LNLSGR.where(d.LNLSGR.gt(0))
    d["category_problem_share"] = d[problem] / d[loan].where(d[loan].gt(0))
    d["category_nonaccrual_share"] = d[nonacc] / d[loan].where(d[loan].gt(0))
    for v in [
        loan,
        "category_exposure_share",
        "category_problem_share",
        "ASSET",
        "equity_ratio",
    ]:
        d["lag_" + v] = d.groupby("IDRSSD", sort=False)[v].shift(1)
    d["lag_log_assets"] = np.log(d.lag_ASSET.where(d.lag_ASSET.gt(0)))
    d["previous_year"] = d.groupby("IDRSSD", sort=False).year.shift(1)
    features = [
        "lag_category_exposure_share",
        "lag_category_problem_share",
        "lag_log_assets",
        "lag_equity_ratio",
    ]
    for since in [2013, 2017]:
        sample = d[
            d.year.between(since, 2025)
            & d.previous_year.eq(d.year - 1)
            & d["lag_" + loan].ge(1000)
            & d[loan].ge(1000)
        ]
        sample = sample.dropna(
            subset=features + ["category_problem_share", "category_nonaccrual_share"]
        )
        reg = sample.set_index(["IDRSSD", "year"]).sort_index()
        w = reg["lag_" + loan] / reg["lag_" + loan].mean()
        for target in ["category_problem_share", "category_nonaccrual_share"]:
            fit = PanelOLS.from_formula(
                target
                + " ~ 1 + "
                + " + ".join(features)
                + " + EntityEffects + TimeEffects",
                reg,
                weights=w,
                drop_absorbed=True,
            ).fit(cov_type="clustered", cluster_entity=True)
            term = "lag_category_exposure_share"
            ci = fit.conf_int().loc[term]
            rows.append(
                dict(
                    category=category,
                    first_outcome_year=since,
                    last_outcome_year=2025,
                    outcome=target,
                    min_balance_both_years_thousand_usd=1000,
                    n_bank_years=fit.nobs,
                    n_bank_ids=sample.IDRSSD.nunique(),
                    coefficient=float(fit.params[term]),
                    ci_95_low=float(ci.iloc[0]),
                    ci_95_high=float(ci.iloc[1]),
                    p_value_bank_clustered=float(fit.pvalues[term]),
                    within_r2=float(fit.rsquared_within),
                )
            )
o = pd.DataFrame(rows)
out = R / "data/fdic_historical_analysis/fdic_subcategory_fe_sensitivity.csv"
o.to_csv(out, index=False)
print(o.to_string(index=False))
