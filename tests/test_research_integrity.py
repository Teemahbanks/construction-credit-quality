"""Integrity tests for committed FFIEC-derived public records; no simulated data."""

from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from analyze_ffiec_credit_risk import prepare

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"


class PublicResearchIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = pd.read_csv(
            DATA / "ffiec_construction_bank_panel_2021_2025.csv", dtype={"IDRSSD": str}
        )
        cls.macro = pd.read_csv(DATA / "ffiec_macro_context_2021_2025.csv")

    def test_bank_year_unique_and_historic_coverage(self):
        d = self.panel
        self.assertEqual(len(d), 23221)
        self.assertEqual(d.IDRSSD.nunique(), 4930)
        self.assertEqual(d.duplicated(["IDRSSD", "year"]).sum(), 0)
        self.assertEqual(
            d.groupby("year").size().to_dict(),
            {2021: 4887, 2022: 4756, 2023: 4641, 2024: 4543, 2025: 4394},
        )

    def test_2025_accounting_and_derived_share(self):
        y = self.panel[self.panel.year.eq(2025)]
        self.assertEqual(y.construction_loans.sum(), 456067907)
        self.assertEqual(y.problem_loans.sum(), 6103112)
        self.assertEqual(y.residential_construction.sum(), 91066499)
        self.assertAlmostEqual(
            y.problem_loans.sum() / y.construction_loans.sum(), 6103112 / 456067907
        )

    def test_2025_unemployment_missing_month_is_visible(self):
        self.assertEqual(
            self.macro.set_index("year").loc[2025, "unemployment_months_observed"], 11
        )
        self.assertEqual(
            self.macro.set_index("year").loc[2024, "unemployment_months_observed"], 12
        )

    def test_holdout_cohort_never_requires_future_construction_balance(self):
        sample, forecast = prepare(self.panel, self.macro)
        hold = forecast[forecast.year.eq(2025)]
        self.assertEqual(len(sample), 11090)
        self.assertEqual(len(hold), 2853)
        self.assertTrue(hold.lag_construction_loans.ge(5000).all())
        self.assertTrue((hold.previous_year == 2024).all())
        self.assertTrue(
            np.allclose(
                hold.future_problem_to_prior_balance,
                hold.problem_loans / hold.lag_construction_loans,
            )
        )
        self.assertGreater(len(hold), len(sample[sample.year.eq(2025)]))


if __name__ == "__main__":
    unittest.main()
