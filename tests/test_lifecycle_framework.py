"""Unit tests for arithmetic and input contracts; constants are not loan data."""

import unittest

from lifecycle_framework import (
    Stage,
    StageInput,
    exposure_at_default,
    illustrative_pd_lgd_ead_product,
)


class LifecycleFrameworkTests(unittest.TestCase):
    def test_exposure_arithmetic(self):
        self.assertEqual(exposure_at_default(100, 50, 0.5), 125)

    def test_illustrative_pd_lgd_product(self):
        item = StageInput(Stage.CONSTRUCTION_DRAW, 0.02, 0.4, 100, 50, 0.5)
        self.assertAlmostEqual(illustrative_pd_lgd_ead_product(item), 1.0)

    def test_invalid_inputs_are_rejected(self):
        for values in [(-1, 10, 0.5), (100, -1, 0.5), (100, 50, 1.1)]:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    exposure_at_default(*values)
        item = StageInput(Stage.STABILIZATION, float("nan"), 0.5, 100, 0, 0)
        with self.assertRaises(ValueError):
            illustrative_pd_lgd_ead_product(item)


if __name__ == "__main__":
    unittest.main()
