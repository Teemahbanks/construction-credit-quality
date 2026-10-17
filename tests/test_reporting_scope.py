"""Verify the reporting scope of the retained balance-sheet fields."""

from pathlib import Path
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class ReportingScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = pd.read_csv(
            ROOT / "data/processed/ffiec_construction_bank_panel_2021_2025.csv",
            dtype={"IDRSSD": str},
        ).set_index(["year", "IDRSSD"])

    def test_domestic_deposits_match_original_schedules(self):
        for year in range(2021, 2026):
            path = ROOT / f"data/ffiec_raw/{year}/FFIECCDRCallScheduleRC1231{year}.txt"
            source = pd.read_csv(
                path,
                sep="\t",
                skiprows=[1],
                dtype=str,
                encoding="latin1",
                low_memory=False,
            ).set_index("IDRSSD")
            observed = self.panel.loc[year, "total_deposits"].sort_index()
            expected = pd.to_numeric(source.RCON2200).reindex(observed.index)
            pd.testing.assert_series_equal(
                observed, expected, check_names=False, check_dtype=False
            )

    def test_control_preference_preserves_available_reported_values(self):
        fields = [
            ("total_assets", "RCON2170", "RCFD2170"),
            ("total_loans", "RCONB528", "RCFDB528"),
            ("equity", "RCON3210", "RCFD3210"),
        ]
        for year in range(2021, 2026):
            path = ROOT / f"data/ffiec_raw/{year}/FFIECCDRCallScheduleRC1231{year}.txt"
            source = pd.read_csv(
                path,
                sep="\t",
                skiprows=[1],
                dtype=str,
                encoding="latin1",
                low_memory=False,
            ).set_index("IDRSSD")
            for output, domestic, consolidated in fields:
                d = pd.to_numeric(source[domestic], errors="coerce")
                c = pd.to_numeric(source[consolidated], errors="coerce")
                self.assertEqual(int((d.notna() & c.notna()).sum()), 0)
                expected = d.combine_first(c)
                observed = self.panel.loc[year, output].sort_index()
                pd.testing.assert_series_equal(
                    observed,
                    expected.reindex(observed.index),
                    check_names=False,
                    check_dtype=False,
                )

    def test_absent_optional_commitments_remain_missing(self):
        self.assertTrue(self.panel.unfunded_construction_commitments.isna().all())


if __name__ == "__main__":
    unittest.main()
