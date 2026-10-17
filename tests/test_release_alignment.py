"""Checks for source integrity and agreement with the corrected manuscript."""

from hashlib import sha256
from pathlib import Path
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAlignmentTests(unittest.TestCase):
    def test_original_ffiec_files_match_manifest(self):
        manifest = pd.read_csv(ROOT / "data/ffiec_source_manifest.csv")
        self.assertEqual(len(manifest), 28)
        for row in manifest.itertuples(index=False):
            path = ROOT / row.file
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), row.sha256)

    def test_corrected_domestic_scope_totals(self):
        panel = pd.read_csv(
            ROOT / "data/processed/ffiec_construction_bank_panel_2021_2025.csv"
        )
        year = panel.loc[panel.year.eq(2025)]
        self.assertEqual(year.residential_construction.sum(), 91066499)
        self.assertEqual(year.other_construction_land.sum(), 365001408)
        self.assertEqual(year.construction_loans.sum(), 456067907)
        self.assertEqual(year.problem_loans.sum(), 6103112)
        self.assertEqual(int(year.construction_loans.gt(0).sum()), 3969)

    def test_ffiec_estimates_match_manuscript(self):
        estimates = pd.read_csv(
            ROOT / "data/model_results/ffiec_panel_exploratory_coefficients.csv"
        )
        main = estimates.loc[
            estimates.variable.eq("lag_construction_share_loans")
            & estimates.interaction.eq(False)
            & estimates.weighted_by_prior_construction.eq(True)
        ].set_index("outcome")
        self.assertAlmostEqual(
            main.loc["problem_share_construction", "coefficient"], 0.01607, places=5
        )
        self.assertAlmostEqual(
            main.loc["nonaccrual_share_construction", "coefficient"], 0.01800, places=5
        )
        comparisons = pd.read_csv(
            ROOT / "data/model_results/ffiec_2025_holdout_benchmarks.csv"
        ).set_index("benchmark")
        self.assertAlmostEqual(
            comparisons.loc[
                "lagged_predictor_wls", "prior_exposure_weighted_mae_percentage_points"
            ],
            0.955,
            places=3,
        )
        self.assertAlmostEqual(
            comparisons.loc[
                "lagged_bank_share", "prior_exposure_weighted_mae_percentage_points"
            ],
            0.890,
            places=3,
        )

    def test_fdic_holdout_comparison(self):
        results = pd.read_csv(
            ROOT / "data/fdic_historical_analysis/fdic_rolling_2018_2025_forecast.csv"
        )
        self.assertEqual(set(results.holdout_year), set(range(2018, 2026)))
        mae = results.pivot(
            index="holdout_year",
            columns="predictor",
            values="weighted_mae_percentage_points",
        )
        rmse = results.pivot(
            index="holdout_year",
            columns="predictor",
            values="weighted_rmse_percentage_points",
        )
        self.assertTrue((mae.lagged_predictor_wls > mae.prior_bank_share).all())
        self.assertTrue((rmse.lagged_predictor_wls < rmse.prior_bank_share).all())


if __name__ == "__main__":
    unittest.main()
