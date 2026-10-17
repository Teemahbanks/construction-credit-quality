#!/usr/bin/env python3
"""Quantify overlap and item-level comparability for two official bank datasets."""

from pathlib import Path
import pandas as pd

R = Path(__file__).parent
f = pd.read_csv(
    R / "data/processed/ffiec_construction_bank_panel_2021_2025.csv",
    dtype={"IDRSSD": str},
)
d = pd.read_csv(
    R / "data/fdic_historical_analysis/fdic_bank_panel_2012_2025.csv",
    dtype={"IDRSSD": str},
)
out = R / "data/fdic_historical_analysis"
rows = []
items = [
    ("residential_construction", "LNRECNFM"),
    ("other_construction_land", "LNRECNOT"),
    ("problem_residential", "problem_residential"),
    ("problem_other_construction", "problem_other"),
    ("nonaccrual_res", "NARECNFM"),
    ("nonaccrual_other", "NARECNOT"),
    ("co_res", "DRRECNFM"),
    ("co_other", "DRRECNOT"),
]
for y in range(2021, 2026):
    a = f[f.year.eq(y)]
    b = d[d.year.eq(y)]
    m = a.merge(
        b,
        on=["IDRSSD", "year"],
        how="outer",
        validate="one_to_one",
        indicator=True,
        suffixes=("_ffiec", "_fdic"),
    )
    same = m[m._merge.eq("both")]
    for ff, fd in items:
        x = ff + ("_ffiec" if ff in b.columns else "")
        z = fd + ("_fdic" if fd in a.columns else "")
        v = same[x]
        w = same[z]
        rows.append(
            dict(
                year=y,
                ffiec_field=ff,
                fdic_field=fd,
                ffiec_banks=len(a),
                fdic_banks=len(b),
                both_bank_ids=len(same),
                ffiec_only=int(m._merge.eq("left_only").sum()),
                fdic_only=int(m._merge.eq("right_only").sum()),
                exact_equal_bank_ids=int((v - w).abs().le(0.01).sum()),
                ffiec_total_thousand_usd=v.sum(),
                fdic_total_thousand_usd=w.sum(),
                difference_fdic_minus_ffiec_thousand_usd=w.sum() - v.sum(),
            )
        )
r = pd.DataFrame(rows)
r.to_csv(out / "fdic_ffiec_overlap_crosswalk_2021_2025.csv", index=False)
print(
    r[
        [
            "year",
            "ffiec_field",
            "both_bank_ids",
            "exact_equal_bank_ids",
            "difference_fdic_minus_ffiec_thousand_usd",
        ]
    ].to_string(index=False)
)
