"""Make the public historical source checks part of the offline test suite."""

import subprocess
import sys
import unittest
from pathlib import Path


class HistoricalSourceChecks(unittest.TestCase):
    def test_official_source_hashes_and_overlap(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(repo / "verify_extended_analysis.py")],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=45,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
        self.assertIn("14 official FDIC responses match source hashes", result.stdout)


if __name__ == "__main__":
    unittest.main()
