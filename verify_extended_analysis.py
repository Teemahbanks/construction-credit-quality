#!/usr/bin/env python3
"""Verify source hashes, panel coverage, and the complete 2012–2025 output set."""

from pathlib import Path
from hashlib import sha256
import gzip
import json
import pandas as pd

R = Path(__file__).parent
out = R / "data/fdic_historical_analysis"
raw = R / "data/fdic_historical_raw"
manifest = pd.read_csv(out / "fdic_api_source_manifest_2012_2025.csv")
assert manifest.year.tolist() == list(range(2012, 2026))
for row in manifest.itertuples(index=False):
    payload = gzip.decompress((raw / row.source_json_gzip).read_bytes())
    assert sha256(payload).hexdigest() == row.raw_response_sha256
    assert len(json.loads(payload)["data"]) == row.api_total_rows
panel = pd.read_csv(out / "fdic_bank_panel_2012_2025.csv", dtype={"IDRSSD": str})
assert not panel[["IDRSSD", "year"]].duplicated().any()
assert panel.year.nunique() == 14
assert not panel.problem_total.isna().any()
assert panel.groupby("year").size().to_dict() == dict(
    zip(manifest.year, manifest.retained_bank_ids)
)
x = pd.read_csv(out / "fdic_ffiec_overlap_crosswalk_2021_2025.csv")
assert (x[["ffiec_only", "fdic_only"]] == 0).all().all()
for field in [
    "problem_residential",
    "problem_other_construction",
    "nonaccrual_res",
    "nonaccrual_other",
    "co_res",
    "co_other",
]:
    g = x[x.ffiec_field.eq(field)]
    assert len(g) == 5
    assert (g.exact_equal_bank_ids == g.both_bank_ids).all()
res = x[x.ffiec_field.eq("residential_construction")].set_index("year")
other = x[x.ffiec_field.eq("other_construction_land")].set_index("year")
assert (
    res.loc[[2021, 2022, 2024, 2025], "difference_fdic_minus_ffiec_thousand_usd"] == 0
).all()
assert (
    other.loc[[2021, 2022, 2024, 2025], "difference_fdic_minus_ffiec_thousand_usd"] == 0
).all()
assert res.loc[2023, "difference_fdic_minus_ffiec_thousand_usd"] == 1103
assert other.loc[2023, "difference_fdic_minus_ffiec_thousand_usd"] == 37096
perf = pd.read_csv(out / "fdic_rolling_2018_2025_forecast.csv")
assert set(perf.holdout_year) == set(range(2018, 2026))
assert perf.groupby("holdout_year").size().eq(3).all()
b = perf.pivot(
    index="holdout_year", columns="predictor", values="weighted_mae_percentage_points"
)
assert (b.lagged_predictor_wls > b.prior_bank_share).all()
for f in [
    "construction_subcategories_2021_2025.csv",
    "same_id_all_five_years.csv",
    "rolling_2024_2025_holdout_benchmarks.csv",
    "balance_threshold_fe_sensitivity.csv",
    "subcategory_bank_year_fe_sensitivity.csv",
]:
    assert (R / "data/followon_results" / f).is_file()
print(
    "PASS: 14 official FDIC responses match source hashes; 14-year panel and five-year bank overlap reconcile."
)
print(
    "PASS: all eight FDIC holdouts and five-year sensitivity results are present and not cherry-picked."
)
