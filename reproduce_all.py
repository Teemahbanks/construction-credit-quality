#!/usr/bin/env python3
"""Rebuild the analysis from the public source files included in this release."""

from hashlib import sha256
from pathlib import Path
import csv
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def check_sources():
    """Check source files before rebuilding any derived results."""
    manifest = ROOT / "data/ffiec_source_manifest.csv"
    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 28:
        raise ValueError("Expected 28 FFIEC core schedule files")
    for row in rows:
        source = ROOT / row["file"]
        if (
            not source.is_file()
            or sha256(source.read_bytes()).hexdigest() != row["sha256"]
        ):
            raise ValueError(f"FFIEC source is missing or changed: {row['file']}")
    required = [
        "data/processed/ffiec_macro_context_2021_2025.csv",
        "data/fdic_historical_analysis/fdic_historical_macro_2012_2025.csv",
    ]
    required.extend(
        f"data/fdic_historical_raw/fdic_financials_{year}1231.json.gz"
        for year in range(2012, 2026)
    )
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing included sources: " + ", ".join(missing))


def run_step(label, arguments, number, start):
    """Run one step and retain its output for inspection."""
    print(f"[{time.monotonic() - start:6.1f}s] {label}", flush=True)
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    log = ROOT / "logs" / f"{number:02d}_{Path(arguments[0]).stem}.txt"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        print(result.stdout + result.stderr, file=sys.stderr)
        raise SystemExit(f"Step failed: {label}. See {log.relative_to(ROOT)}")


def main():
    start = time.monotonic()
    check_sources()
    (ROOT / "logs").mkdir(exist_ok=True)
    steps = []
    for year in range(2021, 2026):
        steps.append(
            (
                f"Prepare FFIEC {year} records",
                [
                    "prepare_ffiec_bank_year.py",
                    "--year",
                    str(year),
                    "--input",
                    f"data/ffiec_raw/{year}",
                    "--outdir",
                    "data/processed",
                ],
            )
        )
    steps.extend(
        [
            ("Combine the FFIEC panel", ["summarize_ffiec_panel.py"]),
            ("Prepare the cached FDIC history", ["prepare_fdic_historical.py"]),
            ("Estimate FFIEC panel models", ["analyze_ffiec_credit_risk.py"]),
            (
                "Run FFIEC category and sensitivity checks",
                ["analyze_ffiec_followon.py"],
            ),
            ("Run FFIEC rolling holdouts", ["analyze_ffiec_rolling.py"]),
            ("Estimate FFIEC category models", ["analyze_ffiec_subcategory_panel.py"]),
            (
                "Estimate FDIC historical models and holdouts",
                ["analyze_fdic_historical.py"],
            ),
            ("Estimate FDIC category models", ["analyze_fdic_subcategories.py"]),
            ("Reconcile FDIC and FFIEC sources", ["crosscheck_fdic_ffiec.py"]),
            ("Create the FFIEC category figure", ["plot_ffiec_followon.py"]),
            ("Create the FDIC history figure", ["plot_fdic_historical.py"]),
            ("Check source hashes and outputs", ["verify_extended_analysis.py"]),
            ("Run unit tests", ["-m", "unittest", "discover", "-s", "tests", "-v"]),
        ]
    )
    for number, (label, arguments) in enumerate(steps, 1):
        run_step(label, arguments, number, start)
    print(
        f"PASS: {len(steps)} analysis steps completed in "
        f"{time.monotonic() - start:.1f} seconds.",
        flush=True,
    )
    print("Results are in data/; step logs are in logs/.", flush=True)


if __name__ == "__main__":
    main()
