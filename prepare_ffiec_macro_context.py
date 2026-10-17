#!/usr/bin/env python3
"""Download and annualize public FRED macro/housing series for FFIEC 2021–25 panel.

Input series are sourced from the Federal Reserve Board, BLS, Census/HUD, and
FHFA via FRED. PERMIT values are SAAR: yearly mean of monthly annual rates,
not the sum of twelve. Contemporary (future-year) shocks are scenarios,
not information known at the preceding year's lending decision date.
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io

import pandas as pd
import requests

ROOT = Path(__file__).parent / "data"
SERIES = {
    "FEDFUNDS": ("Board of Governors, H.15", "monthly percent, not SA"),
    "UNRATE": ("Bureau of Labor Statistics", "monthly percent, SA"),
    "PERMIT": ("Census Bureau / HUD", "monthly thousands of units, SAAR"),
    "USSTHPI": ("Federal Housing Finance Agency", "quarterly index, not SA"),
}


def main():
    raw = ROOT / "raw_public_macro"
    out = ROOT / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    old_manifest = out / "ffiec_macro_source_manifest_2020_2025.csv"
    old = {}
    if old_manifest.is_file():
        old = {
            row.series: row for row in pd.read_csv(old_manifest).itertuples(index=False)
        }
    info = []
    series = {}
    session = requests.Session()
    session.headers["User-Agent"] = "FFIEC-public-academic-project/1.0"
    for code, (publisher, units) in SERIES.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd=2020-01-01&coed=2025-12-31"
        path = raw / f"{code}_2020_2025.csv"
        cached = path.is_file()
        if cached:
            payload = path.read_bytes()
        else:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            payload = response.content
            path.write_bytes(payload)
        data = pd.read_csv(io.BytesIO(payload))
        if len(data.columns) != 2 or code not in data.columns:
            raise ValueError(f"Unexpected FRED columns in {code}: {list(data.columns)}")
        data["observation_date"] = pd.to_datetime(
            data["observation_date"], errors="raise"
        )
        data[code] = pd.to_numeric(data[code], errors="raise")
        data = data[data.observation_date.dt.year.between(2020, 2025)].copy()
        data["year"] = data.observation_date.dt.year
        data["month"] = data.observation_date.dt.month
        expected = 4 if code == "USSTHPI" else 12
        counts = data.groupby("year")[code].agg(["size", "count"])
        if not all(counts.loc[y, "size"] == expected for y in range(2020, 2026)):
            raise ValueError(
                f"Incomplete 2020-2025 {code} date coverage: {counts.to_dict()}"
            )
        # The October 2025 FRED unemployment value is missing. Preserve the gap and
        # report the observed monthly count rather than imputing a value.
        if code == "UNRATE":
            nonmissing = {int(y): int(n) for y, n in counts["count"].items()}
            if (
                any(n != 12 for y, n in nonmissing.items() if y != 2025)
                or nonmissing[2025] != 11
            ):
                raise ValueError(f"Unexpected UNRATE observation gap: {nonmissing}")
            missing = (
                data[data[code].isna()]["observation_date"]
                .dt.strftime("%Y-%m")
                .tolist()
            )
            if missing != ["2025-10"]:
                raise ValueError(f"Unexpected UNRATE missing month(s): {missing}")
        elif not all(counts.loc[y, "count"] == expected for y in range(2020, 2026)):
            raise ValueError(
                f"Incomplete numeric {code} observations: {counts.to_dict()}"
            )
        series[code] = data
        sha = hashlib.sha256(payload).hexdigest()
        original = old.get(code)
        observed_at = (
            original.retrieved_at_utc
            if cached and original is not None and original.sha256 == sha
            else datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        info.append(
            {
                "series": code,
                "upstream_publisher": publisher,
                "units_frequency": units,
                "url": url,
                "source_filename": path.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "retrieved_at_utc": observed_at,
            }
        )

    years = pd.DataFrame({"year": list(range(2020, 2026))})
    for code, label in [
        ("FEDFUNDS", "funds_rate_year_mean_pct"),
        ("UNRATE", "unemployment_year_mean_available_pct"),
        ("PERMIT", "permit_year_mean_thousand_units_saar"),
    ]:
        x = series[code].groupby("year")[code].mean().rename(label).reset_index()
        years = years.merge(x, on="year", validate="one_to_one")
    years = years.merge(
        series["UNRATE"]
        .groupby("year")["UNRATE"]
        .count()
        .rename("unemployment_months_observed")
        .reset_index(),
        on="year",
        validate="one_to_one",
    )
    hpi = (
        series["USSTHPI"]
        .query("month==10")[["year", "USSTHPI"]]
        .rename(columns={"USSTHPI": "house_price_q4_index"})
    )
    years = years.merge(hpi, on="year", validate="one_to_one")
    years["funds_rate_year_mean_change_pp"] = years.funds_rate_year_mean_pct.diff()
    years["unemployment_year_mean_change_pp"] = (
        years.unemployment_year_mean_available_pct.diff()
    )
    years["house_price_q4_yoy_pct"] = years.house_price_q4_index.pct_change() * 100
    years = years[years.year.between(2021, 2025)].copy()
    assert len(years) == 5 and not years.isna().any().any()
    p = out / "ffiec_macro_context_2021_2025.csv"
    years.to_csv(p, index=False)
    m = out / "ffiec_macro_source_manifest_2020_2025.csv"
    pd.DataFrame(info).to_csv(m, index=False)
    print(years.to_string(index=False))
    print("Saved", p, "and", m)


if __name__ == "__main__":
    main()
