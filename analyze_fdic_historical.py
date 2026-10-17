#!/usr/bin/env python3
"""Analyze the 2012–2025 FDIC construction bank panel separately from FFIEC.

Compare the two source series only after an overlap check. Bank predictors are
lagged, and loan-level stages are not observed.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

R = Path(__file__).parent
OUT = R / "data/fdic_historical_analysis"
p = pd.read_csv(
    OUT / "fdic_bank_panel_2012_2025.csv", dtype={"IDRSSD": str}
).sort_values(["IDRSSD", "year"])
m = pd.read_csv(OUT / "fdic_historical_macro_2012_2025.csv")
assert len(p) > 70000 and p[["IDRSSD", "year"]].duplicated().sum() == 0
LAG = [
    "funded_construction",
    "construction_concentration",
    "problem_share",
    "ASSET",
    "equity_ratio",
]
FEATURES = [
    "lag_construction_concentration",
    "lag_problem_share",
    "lag_log_assets",
    "lag_equity_ratio",
]
for name in LAG:
    p["lag_" + name] = p.groupby("IDRSSD", sort=False)[name].shift(1)
p["lag_log_assets"] = np.log(p.lag_ASSET.where(p.lag_ASSET.gt(0)))
p["previous_year"] = p.groupby("IDRSSD", sort=False).year.shift(1)
p = p.merge(m[["year", "funds_rate_mean_change_pp"]], on="year", validate="many_to_one")
p["rate_exposure_interaction"] = (
    p.lag_construction_concentration * p.funds_rate_mean_change_pp
)
p["nonaccrual_share"] = (p.NARECNFM + p.NARECNOT) / p.funded_construction.where(
    p.funded_construction.gt(0)
)
p["future_problem_to_prior_balance"] = (
    p.problem_total / p.lag_funded_construction.where(p.lag_funded_construction.gt(0))
)
matched = (
    p[
        p.previous_year.eq(p.year - 1)
        & p.year.between(2013, 2025)
        & p.lag_funded_construction.ge(5000)
        & p.lag_ASSET.gt(0)
    ]
    .dropna(subset=FEATURES + ["future_problem_to_prior_balance"])
    .copy()
)
print(
    "Forecast-matched sample:",
    len(matched),
    "bank-years",
    matched.IDRSSD.nunique(),
    "bank IDs",
)
coeff = []
for since in [2013, 2017]:
    for outcome in ["problem_share", "nonaccrual_share"]:
        sample = (
            matched[matched.year.ge(since) & matched.funded_construction.ge(5000)]
            .dropna(subset=[outcome])
            .copy()
        )
        reg = sample.set_index(["IDRSSD", "year"]).sort_index()
        weights = reg.lag_funded_construction / reg.lag_funded_construction.mean()
        formula = (
            outcome
            + " ~ 1 + "
            + " + ".join(FEATURES)
            + " + EntityEffects + TimeEffects"
        )
        fit = PanelOLS.from_formula(
            formula, reg, weights=weights, drop_absorbed=True
        ).fit(cov_type="clustered", cluster_entity=True)
        term = "lag_construction_concentration"
        ci = fit.conf_int().loc[term]
        coeff.append(
            dict(
                first_outcome_year=since,
                last_outcome_year=2025,
                outcome=outcome,
                specification="lagged-bank-predictors+bank-FE+year-FE",
                cluster="bank",
                n_bank_years=fit.nobs,
                n_bank_ids=sample.IDRSSD.nunique(),
                n_outcome_years=sample.year.nunique(),
                exposure_coefficient=float(fit.params[term]),
                ci_95_low=float(ci.iloc[0]),
                ci_95_high=float(ci.iloc[1]),
                p_value=float(fit.pvalues[term]),
                within_r2=float(fit.rsquared_within),
            )
        )

# The rate interaction combines the contemporaneous annual national shock with
# lagged exposure, so it is unsuitable for prior-year prediction. Bank- and
# two-way-clustered standard errors are compared, but 13 year clusters are too
# few for reliable inference on common shocks.
sample = (
    matched[matched.funded_construction.ge(5000)]
    .dropna(subset=["nonaccrual_share", "rate_exposure_interaction"])
    .copy()
)
reg = sample.set_index(["IDRSSD", "year"]).sort_index()
w = reg.lag_funded_construction / reg.lag_funded_construction.mean()
formula = (
    "nonaccrual_share ~ 1 + "
    + " + ".join(FEATURES)
    + " + rate_exposure_interaction + EntityEffects + TimeEffects"
)
model = PanelOLS.from_formula(formula, reg, weights=w, drop_absorbed=True)
for label, kwargs in [
    ("bank", dict(cluster_entity=True)),
    ("bank_and_year", dict(cluster_entity=True, cluster_time=True)),
]:
    fit = model.fit(cov_type="clustered", **kwargs)
    for term in ["lag_construction_concentration", "rate_exposure_interaction"]:
        ci = fit.conf_int().loc[term]
        coeff.append(
            dict(
                first_outcome_year=2013,
                last_outcome_year=2025,
                outcome="nonaccrual_share",
                specification="lagged-bank-predictors+rate-change-interaction+bank-FE+year-FE",
                cluster=label,
                n_bank_years=fit.nobs,
                n_bank_ids=sample.IDRSSD.nunique(),
                n_outcome_years=sample.year.nunique(),
                exposure_coefficient=float(fit.params[term]),
                ci_95_low=float(ci.iloc[0]),
                ci_95_high=float(ci.iloc[1]),
                p_value=float(fit.pvalues[term]),
                within_r2=float(fit.rsquared_within),
                term=term,
            )
        )
pd.DataFrame(coeff).to_csv(OUT / "fdic_extended_fe_sensitivity.csv", index=False)

# Training cutoffs and eligibility use prior-year information rather than the
# holdout-year funded balance. The output includes every 2018–2025 holdout.
forecast = []
for y in range(2018, 2026):
    train = matched[matched.year.between(2013, y - 1)]
    hold = matched[matched.year.eq(y)]
    if len(train) < 5000 or len(hold) < 1000:
        raise ValueError(f"{y}: incomplete rolling cohort")
    fit = sm.WLS(
        train.future_problem_to_prior_balance,
        sm.add_constant(train[FEATURES], has_constant="add"),
        weights=train.lag_funded_construction,
    ).fit()
    preds = np.asarray(
        fit.predict(sm.add_constant(hold[FEATURES], has_constant="add"))
    ).clip(min=0)
    base = hold.lag_problem_share.to_numpy().clip(min=0)
    last = p[p.year.eq(y - 1)]
    prior_rate = last.problem_total.sum() / last.funded_construction.sum()
    all_predictions = {
        "prior_bank_share": base,
        "prior_year_portfolio_mean": np.repeat(prior_rate, len(hold)),
        "lagged_predictor_wls": preds,
    }
    target = hold.future_problem_to_prior_balance.to_numpy()
    wt = hold.lag_funded_construction.to_numpy()
    for name, a in all_predictions.items():
        forecast.append(
            dict(
                holdout_year=y,
                training_outcome_years=(
                    f"2013-{y-1}" if name == "lagged_predictor_wls" else str(y - 1)
                ),
                n_test_banks=len(hold),
                predictor=name,
                mae_percentage_points=100 * float(abs(target - a).mean()),
                weighted_mae_percentage_points=100
                * float(np.average(abs(target - a), weights=wt)),
                weighted_rmse_percentage_points=100
                * float(np.sqrt(np.average((target - a) ** 2, weights=wt))),
            )
        )
h = pd.DataFrame(forecast)
h.to_csv(OUT / "fdic_rolling_2018_2025_forecast.csv", index=False)
print(
    "\nFDIC historical FE:\n",
    pd.DataFrame(coeff)[
        [
            "first_outcome_year",
            "outcome",
            "specification",
            "cluster",
            "n_bank_years",
            "exposure_coefficient",
            "p_value",
        ]
    ].to_string(index=False),
)
print(
    "\nFDIC rolling holdout weighted MAE, percentage points:\n",
    h.pivot(
        index="holdout_year",
        columns="predictor",
        values="weighted_mae_percentage_points",
    )
    .round(3)
    .to_string(),
)
