#!/usr/bin/env python3
"""Produce subtype, cohort, sensitivity, and holdout analyses for 2021–2025 FFIEC data.

The analysis uses bank-level public Call Reports and is exploratory rather than
causal. Loan-stage features are not observed.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from analyze_ffiec_credit_risk import prepare, FEATURES, forecast_holdout

ROOT = Path(__file__).parent
DATA = ROOT / "data/processed"
OUT = ROOT / "data/followon_results"
OUT.mkdir(parents=True, exist_ok=True)
panel = pd.read_csv(
    DATA / "ffiec_construction_bank_panel_2021_2025.csv", dtype={"IDRSSD": str}
)
macro = pd.read_csv(DATA / "ffiec_macro_context_2021_2025.csv")
assert len(panel) == 23221 and panel[["IDRSSD", "year"]].duplicated().sum() == 0

# Balances remain in the source unit of thousands of U.S. dollars. Component
# sums use available nonmissing values and must reconcile with each aggregate.
for aggregate, components in [
    ("construction_loans", ["residential_construction", "other_construction_land"]),
    ("problem_loans", ["problem_residential", "problem_other_construction"]),
    ("nonaccrual", ["nonaccrual_res", "nonaccrual_other"]),
    ("gross_chargeoffs_ytd", ["co_res", "co_other"]),
]:
    diff = panel[aggregate] - panel[components].sum(axis=1, min_count=1)
    if diff.abs().gt(0.01).any():
        raise ValueError(f"{aggregate} does not reconcile to {components}")

rows = []
for y, g in panel.groupby("year"):
    for category, exposure, problem, nonaccrual, chargeoff in [
        (
            "one_to_four_family_residential_construction",
            "residential_construction",
            "problem_residential",
            "nonaccrual_res",
            "co_res",
        ),
        (
            "other_construction_and_land_development",
            "other_construction_land",
            "problem_other_construction",
            "nonaccrual_other",
            "co_other",
        ),
    ]:
        e = g[exposure].sum()
        p = g[problem].sum()
        rows.append(
            dict(
                year=int(y),
                category=category,
                reporting_bank_ids=len(g),
                positive_balance_bank_ids=int(g[exposure].gt(0).sum()),
                funded_stock_thousand_usd=e,
                problem_stock_thousand_usd=p,
                nonaccrual_stock_thousand_usd=g[nonaccrual].sum(),
                gross_chargeoffs_ytd_thousand_usd=g[chargeoff].sum(),
                problem_pct=100 * p / e,
                nonaccrual_pct=100 * g[nonaccrual].sum() / e,
            )
        )
subtype = pd.DataFrame(rows)
subtype.to_csv(OUT / "construction_subcategories_2021_2025.csv", index=False)

# The balanced panel requires the same public ID in all five years. Ownership
# changes and portfolio transfers are not adjusted for.
continuous_ids = panel.groupby("IDRSSD").year.nunique().loc[lambda s: s == 5].index
balanced = panel[panel.IDRSSD.isin(continuous_ids)]
balanced_rows = []
for y, g in balanced.groupby("year"):
    total = g.construction_loans.sum()
    problem = g.problem_loans.sum()
    res = g.residential_construction.sum()
    resproblem = g.problem_residential.sum()
    balanced_rows.append(
        dict(
            year=int(y),
            same_public_bank_ids=len(g),
            funded_construction_thousand_usd=total,
            problem_stock_thousand_usd=problem,
            problem_pct=100 * problem / total,
            residential_funded_thousand_usd=res,
            residential_problem_stock_thousand_usd=resproblem,
            residential_problem_pct=100 * resproblem / res,
        )
    )
pd.DataFrame(balanced_rows).to_csv(OUT / "same_id_all_five_years.csv", index=False)

# Quartiles are defined from 2021. End-date coverage is reported for the
# original cohort rather than restricting the sample to 2025 reporters.
base = panel.query(
    "year==2021 and construction_loans >= 5000 and total_loans > 0"
).copy()
base["baseline_quartile"] = pd.qcut(
    base.construction_share_loans, 4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"]
)
base = base[
    ["IDRSSD", "baseline_quartile", "construction_share_loans", "construction_loans"]
].rename(
    columns={
        "construction_share_loans": "baseline_concentration",
        "construction_loans": "baseline_construction_thousand_usd",
    }
)
joined = panel.merge(base, on="IDRSSD", how="inner", validate="many_to_one")
coverage = []
cohorts = []
for (label, y), g in joined.groupby(["baseline_quartile", "year"], observed=True):
    n0 = int(base.baseline_quartile.eq(label).sum())
    coverage.append(
        dict(
            baseline_quartile=str(label),
            year=int(y),
            bank_ids_base_2021=n0,
            bank_ids_reported_year=len(g),
            missing_ids_since_2021=n0 - len(g),
            missing_share_pct=100 * (n0 - len(g)) / n0,
        )
    )
    funded = g.construction_loans.sum()
    residential = g.residential_construction.sum()
    cohorts.append(
        dict(
            baseline_quartile=str(label),
            year=int(y),
            bank_ids_reported_year=len(g),
            construction_stock_thousand_usd=funded,
            problem_stock_thousand_usd=g.problem_loans.sum(),
            problem_pct=100 * g.problem_loans.sum() / funded if funded > 0 else np.nan,
            residential_stock_thousand_usd=residential,
            residential_problem_pct=(
                100 * g.problem_residential.sum() / residential
                if residential > 0
                else np.nan
            ),
        )
    )
pd.DataFrame(coverage).sort_values(["baseline_quartile", "year"]).to_csv(
    OUT / "baseline_2021_bank_id_coverage.csv", index=False
)
pd.DataFrame(cohorts).sort_values(["baseline_quartile", "year"]).to_csv(
    OUT / "baseline_2021_quartile_cohort_trajectories.csv", index=False
)

# This sensitivity grid applies the exploratory specification to both outcomes
# across four minimum construction-balance thresholds. It was not preregistered;
# the end-year floor excludes contraction.
lagged = panel.sort_values(["IDRSSD", "year"]).copy()
for name in [
    "construction_loans",
    "construction_share_loans",
    "problem_share_construction",
    "total_assets",
    "equity_share_assets",
]:
    lagged["lag_" + name] = lagged.groupby("IDRSSD", sort=False)[name].shift(1)
lagged["previous_year"] = lagged.groupby("IDRSSD", sort=False).year.shift(1)
lagged["lag_log_assets"] = np.log(
    lagged.lag_total_assets.where(lagged.lag_total_assets.gt(0))
)
lagged = lagged.loc[
    lagged.year.between(2022, 2025) & lagged.previous_year.eq(lagged.year - 1)
].copy()
base_required = FEATURES + [
    "nonaccrual_share_construction",
    "problem_share_construction",
    "lag_construction_loans",
]
lagged = lagged.dropna(subset=base_required)
sensitivity = []
for threshold in [1000, 5000, 10000, 25000]:
    sample = lagged[
        lagged.lag_construction_loans.ge(threshold)
        & lagged.construction_loans.ge(threshold)
    ].copy()
    reg = sample.set_index(["IDRSSD", "year"]).sort_index()
    w = reg.lag_construction_loans / reg.lag_construction_loans.mean()
    for target in ["nonaccrual_share_construction", "problem_share_construction"]:
        model = PanelOLS.from_formula(
            target
            + " ~ 1 + "
            + " + ".join(FEATURES)
            + " + EntityEffects + TimeEffects",
            reg,
            weights=w,
            drop_absorbed=True,
        )
        result = model.fit(cov_type="clustered", cluster_entity=True)
        v = "lag_construction_share_loans"
        ci = result.conf_int().loc[v]
        sensitivity.append(
            dict(
                outcome=target,
                minimum_both_year_balances_thousand_usd=threshold,
                n_bank_years=int(result.nobs),
                n_bank_ids=int(sample.IDRSSD.nunique()),
                n_by_year=json.dumps(
                    {
                        str(y): int(n)
                        for y, n in sample.year.value_counts().sort_index().items()
                    }
                ),
                concentration_coefficient=float(result.params[v]),
                bank_clustered_95_low=float(ci.iloc[0]),
                bank_clustered_95_high=float(ci.iloc[1]),
                bank_clustered_p=float(result.pvalues[v]),
                within_r2=float(result.rsquared_within),
            )
        )
sens = pd.DataFrame(sensitivity)
sens.to_csv(OUT / "balance_threshold_fe_sensitivity.csv", index=False)

# Predictive eligibility is based on 2024 filings rather than the 2025 balance.
# Bank-level 2025 outcomes are used only to measure forecast errors.
_, forecast = prepare(panel, macro)
_, meta, _ = forecast_holdout(forecast, panel)
q2024 = panel[panel.year == 2024][["IDRSSD", "construction_share_loans"]].rename(
    columns={"construction_share_loans": "concentration_2024"}
)
h = meta.merge(q2024, on="IDRSSD", validate="one_to_one")
assert len(h) == 2853 and h.IDRSSD.is_unique
h["lag_concentration_quartile"] = pd.qcut(
    h.concentration_2024, 4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"]
)
perf = []
for label, g in h.groupby("lag_concentration_quartile", observed=True):
    a = g.future_problem_to_prior_balance.to_numpy()
    w = g.lag_construction_loans.to_numpy()
    for model, col in [
        ("prior_bank_share", "prediction_persistence"),
        ("lagged_predictor_wls", "prediction_wls"),
    ]:
        p = g[col].to_numpy()
        perf.append(
            dict(
                lag_concentration_quartile=str(label),
                n_holdout_banks=len(g),
                predictor=model,
                weighted_mae_percentage_points=100 * np.average(abs(a - p), weights=w),
                unweighted_mae_percentage_points=100 * np.mean(abs(a - p)),
                weighted_rmse_percentage_points=100
                * np.sqrt(np.average((a - p) ** 2, weights=w)),
            )
        )
pd.DataFrame(perf).to_csv(OUT / "holdout_by_2024_concentration.csv", index=False)

# The paired-bank bootstrap quantifies conditional uncertainty within the 2025
# holdout cross-section; it does not assess year-to-year macro robustness.
rng = np.random.default_rng(20261003)
a = h.future_problem_to_prior_balance.to_numpy()
w = h.lag_construction_loans.to_numpy()
e_model = abs(a - h.prediction_wls.to_numpy())
e_base = abs(a - h.prediction_persistence.to_numpy())
observed = 100 * np.average(e_model - e_base, weights=w)
boots = np.empty(1000)
for i in range(len(boots)):
    ix = rng.integers(0, len(h), size=len(h))
    boots[i] = 100 * np.average(e_model[ix] - e_base[ix], weights=w[ix])
bootstrap = dict(
    holdout_year=2025,
    n_holdout_banks=len(h),
    weighted_mae_model_minus_persistence_percentage_points=observed,
    paired_bank_resample_percentile_2_5=float(np.percentile(boots, 2.5)),
    paired_bank_resample_percentile_97_5=float(np.percentile(boots, 97.5)),
    resamples=len(boots),
    random_seed=20261003,
    caveat="Conditional on the observed single 2025 year, selected 2024 eligible banks, and trained models; does not account for common national shocks, historical vintages, or future out-of-time years.",
)
(OUT / "holdout_paired_bootstrap.json").write_text(
    json.dumps(bootstrap, indent=2) + "\n", encoding="utf-8"
)
print("Subtype yearly rows:", len(subtype))
print(
    subtype[["year", "category", "funded_stock_thousand_usd", "problem_pct"]].to_string(
        index=False
    )
)
print(
    "\nSame-ID five-year comparison:\n",
    pd.DataFrame(balanced_rows).to_string(index=False),
)
print(
    "\n2021 cohort coverage at 2025:\n",
    pd.DataFrame(coverage).query("year==2025").to_string(index=False),
)
print(
    "\nThreshold sensitivities:\n",
    sens[
        [
            "outcome",
            "minimum_both_year_balances_thousand_usd",
            "n_bank_years",
            "concentration_coefficient",
            "bank_clustered_p",
        ]
    ].to_string(index=False),
)
print(
    "\n2025 holdout paired model-minus-persistence weighted MAE (percentage points):",
    bootstrap["weighted_mae_model_minus_persistence_percentage_points"],
    "conditional bootstrap interval:",
    (
        boots.quantile([0.025, 0.975])
        if hasattr(boots, "quantile")
        else np.percentile(boots, [2.5, 97.5])
    ),
)
