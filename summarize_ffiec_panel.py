#!/usr/bin/env python3
"""Combine vetted annual FFIEC bank-year CSVs and make descriptive 2021–2025 outputs.

Run after prepare_ffiec_bank_year.py for each year. This script does not estimate
causal effects or validate a loan-level construction-stage model.
"""

from pathlib import Path
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main(indir: Path, outdir: Path, years: list[int]):
    outdir.mkdir(parents=True, exist_ok=True)
    frames = []
    for y in years:
        p = indir / f"ffiec_bank_year_{y}.csv"
        if not p.is_file():
            raise FileNotFoundError(p)
        d = pd.read_csv(p, dtype={"IDRSSD": str})
        if len(d) == 0 or set(d.year) != {y} or d.IDRSSD.duplicated().any():
            raise ValueError(
                f"{p}: wrong year, empty data, or duplicate bank identifiers"
            )
        frames.append(d)
    panel = pd.concat(frames, ignore_index=True)
    if panel.duplicated(["year", "IDRSSD"]).any():
        raise ValueError("Duplicated bank-year identifier")
    panel = panel.sort_values(["IDRSSD", "year"]).reset_index(drop=True)
    outpanel = outdir / "ffiec_construction_bank_panel_2021_2025.csv"
    panel.to_csv(outpanel, index=False)

    rows = []
    for y, group in panel.groupby("year", sort=True):
        construction = group.construction_loans.sum(min_count=1)
        problem = group.problem_loans.sum(min_count=1)
        rows.append(
            dict(
                year=y,
                institutions=len(group),
                positive_construction=int(group.construction_loans.gt(0).sum()),
                residential_1to4_construction_thousand_usd=group.residential_construction.sum(
                    min_count=1
                ),
                other_construction_land_thousand_usd=group.other_construction_land.sum(
                    min_count=1
                ),
                construction_thousand_usd=construction,
                problem_thousand_usd=problem,
                past_due_30_89_thousand_usd=group.pd30.sum(min_count=1),
                past_due_90_plus_thousand_usd=group.pd90.sum(min_count=1),
                nonaccrual_thousand_usd=group.nonaccrual.sum(min_count=1),
                gross_chargeoffs_ytd_thousand_usd=group.gross_chargeoffs_ytd.sum(
                    min_count=1
                ),
                net_chargeoffs_ytd_thousand_usd=group.net_chargeoffs_ytd.sum(
                    min_count=1
                ),
                problem_share_of_construction=problem / construction,
                nonaccrual_share_of_construction=group.nonaccrual.sum(min_count=1)
                / construction,
            )
        )
    annual = pd.DataFrame(rows)
    outannual = outdir / "ffiec_annual_descriptive_2021_2025.csv"
    annual.to_csv(outannual, index=False)

    per_year = {y: set(group.IDRSSD) for y, group in panel.groupby("year")}
    pairs = pd.DataFrame(
        [
            {
                "from_year": a,
                "to_year": b,
                "banks_in_both": len(per_year[a] & per_year[b]),
                "banks_in_start": len(per_year[a]),
                "banks_in_end": len(per_year[b]),
            }
            for a, b in zip(years[:-1], years[1:])
        ]
    )
    outpairs = outdir / "ffiec_year_pair_coverage_2021_2025.csv"
    pairs.to_csv(outpairs, index=False)

    plt.rcParams.update({"font.size": 11, "font.family": "DejaVu Sans"})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), layout="constrained")
    years_plot = annual.year.astype(str)
    axes[0].bar(
        years_plot, annual.construction_thousand_usd / 1_000_000, color="#24466c"
    )
    axes[0].set(
        title="Funded construction loans",
        ylabel="USD billions",
        xlabel="December reporting year",
    )
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].plot(
        years_plot,
        annual.problem_share_of_construction * 100,
        color="#a54a36",
        marker="o",
        linewidth=2.2,
    )
    axes[1].set(
        title="Past-due or nonaccrual share",
        ylabel="% of funded construction loans",
        xlabel="December reporting year",
    )
    axes[1].grid(axis="y", alpha=0.22)
    fig.suptitle(
        "FFIEC construction and land-development lending, 2021–2025", fontweight="bold"
    )
    fig.text(
        0.5,
        -0.01,
        "Source: FFIEC single-period year-end Call Reports. Ratios use aggregate balances; not causal effects.",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    image = outdir / "ffiec_construction_2021_2025_descriptive.png"
    fig.savefig(image, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Bank-years:", len(panel), "unique banks:", panel.IDRSSD.nunique())
    print(
        annual[
            [
                "year",
                "institutions",
                "positive_construction",
                "construction_thousand_usd",
                "problem_thousand_usd",
                "gross_chargeoffs_ytd_thousand_usd",
                "problem_share_of_construction",
            ]
        ].to_string(index=False)
    )
    print("Output:", outpanel, outannual, outpairs, image, sep="\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--indir", type=Path, default=Path(__file__).parent / "data/processed"
    )
    p.add_argument(
        "--outdir", type=Path, default=Path(__file__).parent / "data/processed"
    )
    p.add_argument("--years", type=int, nargs="+", default=list(range(2021, 2026)))
    a = p.parse_args()
    main(a.indir, a.outdir, a.years)
