#!/usr/bin/env python3
"""Exploratory bank-level construction credit risk analysis on public FFIEC data.

OUTCOME y_it is December year-end construction nonaccrual/problem share in t.
Predictors are December t-1 Call Report values (only consecutive bank IDs).
The same-bank 2025 holdout forecast uses no 2025 macro or bank predictors.
The FE sample requires >= $5m in t-1 AND t, while the separate forecast
cohort is selected exclusively on t-1 construction balance >= $5m.
All results are associational; with four outcome years shock inference is weak.
"""

import argparse
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels
import linearmodels
from linearmodels.panel import PanelOLS

LAGGED = [
    "construction_loans",
    "construction_share_loans",
    "problem_share_construction",
    "nonaccrual_share_construction",
    "total_assets",
    "equity_share_assets",
]
FEATURES = [
    "lag_construction_share_loans",
    "lag_problem_share_construction",
    "lag_log_assets",
    "lag_equity_share_assets",
]
SAMPLE_THRESHOLD_THOUSAND = 5000


def prepare(panel, macro):
    panel = panel.sort_values(["IDRSSD", "year"]).copy()
    bybank = panel.groupby("IDRSSD", sort=False)
    for name in LAGGED:
        panel["lag_" + name] = bybank[name].shift(1)
    panel["previous_year"] = bybank.year.shift(1)
    panel["lag_log_assets"] = np.log(
        panel.lag_total_assets.where(panel.lag_total_assets.gt(0))
    )
    panel = panel.merge(
        macro[["year", "funds_rate_year_mean_change_pp"]],
        on="year",
        validate="many_to_one",
    )
    panel["rate_exposure_interaction"] = (
        panel.lag_construction_share_loans * panel.funds_rate_year_mean_change_pp
    )
    matched = panel[
        (panel.year >= 2022)
        & (panel.year <= 2025)
        & panel.previous_year.eq(panel.year - 1)
        & panel.lag_construction_loans.ge(SAMPLE_THRESHOLD_THOUSAND)
        & panel.lag_total_assets.gt(0)
    ].copy()
    matched["future_problem_to_prior_balance"] = (
        matched.problem_loans / matched.lag_construction_loans
    )
    # Holdout eligibility never conditions on outcome-year construction balance.
    forecast = matched.dropna(
        subset=FEATURES + ["future_problem_to_prior_balance"]
    ).copy()
    sample = matched[matched.construction_loans.ge(SAMPLE_THRESHOLD_THOUSAND)].copy()
    required = FEATURES + [
        "nonaccrual_share_construction",
        "problem_share_construction",
        "rate_exposure_interaction",
        "lag_construction_loans",
    ]
    n_before = len(sample)
    sample = sample.dropna(subset=required)
    if len(sample) != n_before:
        print("Dropped for missing model variables:", n_before - len(sample))
    if (
        not sample.year.value_counts()
        .reindex([2022, 2023, 2024, 2025], fill_value=0)
        .ge(100)
        .all()
    ):
        raise ValueError("Too few banks in one annual outcome cohort")
    return sample, forecast


def panel_fit(sample, target, with_interaction=False, weighted=True):
    reg = sample.set_index(["IDRSSD", "year"]).sort_index()
    term = " + rate_exposure_interaction" if with_interaction else ""
    formula = (
        f"{target} ~ 1 + "
        + " + ".join(FEATURES)
        + term
        + " + EntityEffects + TimeEffects"
    )
    if weighted:
        weights = reg.lag_construction_loans / reg.lag_construction_loans.mean()
        model = PanelOLS.from_formula(formula, reg, weights=weights, drop_absorbed=True)
    else:
        model = PanelOLS.from_formula(formula, reg, drop_absorbed=True)
    result = model.fit(cov_type="clustered", cluster_entity=True)
    rows = []
    for term_name, value in result.params.items():
        interval = result.conf_int().loc[term_name]
        rows.append(
            dict(
                outcome=target,
                interaction=with_interaction,
                weighted_by_prior_construction=weighted,
                variable=term_name,
                coefficient=float(value),
                standard_error=float(result.std_errors[term_name]),
                lower_95=float(interval.iloc[0]),
                upper_95=float(interval.iloc[1]),
                p_value_bank_clustered=float(result.pvalues[term_name]),
                n_bank_years=int(result.nobs),
                n_banks=int(reg.index.get_level_values(0).nunique()),
                within_r2=float(result.rsquared_within),
            )
        )
    return result, rows


def weighted_mae(actual, prediction, weights):
    return float(np.average(np.abs(actual - prediction), weights=weights))


def forecast_holdout(forecast, full_panel):
    train = forecast[forecast.year <= 2024].copy()
    test = forecast[forecast.year == 2025].copy()
    target = "future_problem_to_prior_balance"
    xtrain = sm.add_constant(train[FEATURES], has_constant="add")
    xtest = sm.add_constant(test[FEATURES], has_constant="add")
    fit = sm.WLS(train[target], xtrain, weights=train.lag_construction_loans).fit()
    predictions = np.asarray(fit.predict(xtest)).clip(min=0)
    persistence = test.lag_problem_share_construction.to_numpy().clip(min=0)
    # The previous year's portfolio-wide ratio was public at end of 2024.
    prior = full_panel[full_panel.year == 2024]
    constant = float(prior.problem_loans.sum() / prior.construction_loans.sum())
    benchmarks = {
        "lagged_bank_share": persistence,
        "prior_year_portfolio_mean": np.repeat(constant, len(test)),
        "lagged_predictor_wls": predictions,
    }
    actual = test[target].to_numpy()
    weight = test.lag_construction_loans.to_numpy()
    out = []
    for label, pred in benchmarks.items():
        out.append(
            dict(
                benchmark=label,
                training_outcome_years=(
                    "2022-2024" if label == "lagged_predictor_wls" else "2024 alone"
                ),
                holdout_year=2025,
                n_test_banks=len(test),
                mae_percentage_points=100 * float(np.abs(actual - pred).mean()),
                prior_exposure_weighted_mae_percentage_points=100
                * weighted_mae(actual, pred, weight),
                prior_exposure_weighted_rmse_percentage_points=100
                * float(np.sqrt(np.average((actual - pred) ** 2, weights=weight))),
            )
        )
    detailed = test[
        [
            "IDRSSD",
            "year",
            "lag_construction_loans",
            "lag_construction_share_loans",
            "lag_problem_share_construction",
            target,
        ]
    ].copy()
    detailed["prediction_wls"] = predictions
    detailed["prediction_persistence"] = persistence
    return out, detailed, fit


def main(indir: Path, outdir: Path):
    panel = pd.read_csv(
        indir / "ffiec_construction_bank_panel_2021_2025.csv", dtype={"IDRSSD": str}
    )
    macro = pd.read_csv(indir / "ffiec_macro_context_2021_2025.csv")
    sample, forecast = prepare(panel, macro)
    outdir.mkdir(parents=True, exist_ok=True)
    sample.to_csv(outdir / "ffiec_model_sample_2022_2025.csv", index=False)
    results = []
    specs = [
        ("nonaccrual_share_construction", False, True),
        ("problem_share_construction", False, True),
        ("nonaccrual_share_construction", True, True),
        ("nonaccrual_share_construction", False, False),
    ]
    texts = []
    for outcome, interaction, weighted in specs:
        fitted, rows = panel_fit(sample, outcome, interaction, weighted)
        label = f"{outcome}_interaction_{interaction}_weighted_{weighted}"
        texts.append(f"\n\n===== {label} =====\n" + str(fitted.summary))
        results.extend(rows)
    coefficients = pd.DataFrame(results)
    coefficients.to_csv(
        outdir / "ffiec_panel_exploratory_coefficients.csv", index=False
    )
    (outdir / "ffiec_panel_full_statistical_summaries.txt").write_text(
        "".join(texts), encoding="utf-8"
    )
    comparisons, details, forecast_fit = forecast_holdout(forecast, panel)
    pd.DataFrame(comparisons).to_csv(
        outdir / "ffiec_2025_holdout_benchmarks.csv", index=False
    )
    details.to_csv(outdir / "ffiec_2025_holdout_predictions.csv", index=False)
    (outdir / "ffiec_2025_holdout_model_summary.txt").write_text(
        str(forecast_fit.summary()), encoding="utf-8"
    )
    metadata = {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "statsmodels": statsmodels.__version__,
        "linearmodels": linearmodels.__version__,
        "years_outcomes": [2022, 2023, 2024, 2025],
        "n_bank_years": len(sample),
        "n_distinct_banks": sample.IDRSSD.nunique(),
        "n_by_outcome_year": {
            str(k): int(v) for k, v in sample.year.value_counts().sort_index().items()
        },
        "minimum_construction_balance_both_years_thousand_usd": SAMPLE_THRESHOLD_THOUSAND,
        "predictive_holdout_year": 2025,
        "holdout_population_rule": "bank files in adjacent years; prior-year construction balance >= $5m; no current-year construction-balance restriction",
        "holdout_target": "next-year problem balance / prior-year construction balance",
        "holdout_banks_2025": int((forecast.year == 2025).sum()),
        "prediction_features": FEATURES,
        "caveats": [
            "FFIEC bank-level categories do not identify loan stages",
            "Only four consecutive annual outcomes; bank clustering alone does not correct common macro shocks",
            "FE sample conditions on >=$5m outcome-year exposure; forecast cohort does not",
            "Present-vintage macro series cannot stand in for real-time forecast vintages",
            "Year FE absorb national-level main effects; interaction only exploratory",
        ],
    }
    (outdir / "ffiec_model_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print("Sample bank-years:", len(sample), "banks:", sample.IDRSSD.nunique())
    print(
        coefficients[
            [
                "outcome",
                "interaction",
                "weighted_by_prior_construction",
                "variable",
                "coefficient",
                "standard_error",
                "p_value_bank_clustered",
            ]
        ].to_string(index=False)
    )
    print(
        "\nOut-of-time benchmarks (2025)\n",
        pd.DataFrame(comparisons).to_string(index=False),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--indir", type=Path, default=Path(__file__).parent / "data/processed"
    )
    parser.add_argument(
        "--outdir", type=Path, default=Path(__file__).parent / "data/model_results"
    )
    args = parser.parse_args()
    main(args.indir, args.outdir)
