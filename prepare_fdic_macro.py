#!/usr/bin/env python3
"""Prepare 2011–2025 macro context from primary-government series via FRED.

Rates and unemployment are annual means of monthly observations; building
permits are annual means of monthly seasonally adjusted *annualized* rates.
FHFA HPI Q4 changes compare Q4 in consecutive years. Missing months remain
missing; revised series are not real-time information vintages.
"""

from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import io
import requests
import pandas as pd

R = Path(__file__).parent / "data"
raw = R / "fdic_historical_raw"
out = R / "fdic_historical_analysis"
raw.mkdir(exist_ok=True)
out.mkdir(exist_ok=True)
old_manifest = out / "fdic_macro_source_manifest.csv"
previous = {}
if old_manifest.exists():
    previous = {r.series: r for r in pd.read_csv(old_manifest).itertuples(index=False)}
series = {}
manifest = []
for code in ["FEDFUNDS", "UNRATE", "PERMIT", "USSTHPI"]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd=2011-01-01&coed=2025-12-31"
    path = raw / f"FRED_{code}_2011_2025.csv"
    if path.exists():
        payload = path.read_bytes()
    else:
        response = requests.get(url, timeout=40)
        response.raise_for_status()
        payload = response.content
        path.write_bytes(payload)
    x = pd.read_csv(io.BytesIO(payload))
    assert len(x.columns) == 2 and code in x
    x["observation_date"] = pd.to_datetime(x.observation_date)
    x[code] = pd.to_numeric(x[code], errors="coerce")
    x["year"] = x.observation_date.dt.year
    x["month"] = x.observation_date.dt.month
    for year in range(2011, 2026):
        obs = x[x.year == year]
        assert len(obs) == (4 if code == "USSTHPI" else 12), (code, year, len(obs))
    series[code] = x
    digest = sha256(payload).hexdigest()
    old = previous.get(code)
    recorded = (
        old.retrieved_at_utc
        if old is not None and old.sha256 == digest
        else datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    manifest.append(
        dict(
            series=code,
            url=url,
            source_filename=path.name,
            sha256=digest,
            data_coverage="2011-2025",
            retrieved_at_utc=recorded,
        )
    )
years = pd.DataFrame({"year": range(2011, 2026)})
for code, target in [
    ("FEDFUNDS", "funds_rate_annual_mean_pct"),
    ("UNRATE", "unemployment_annual_available_mean_pct"),
    ("PERMIT", "building_permits_annual_mean_thousands_saar"),
]:
    years = years.merge(
        series[code].groupby("year")[code].mean().rename(target).reset_index(),
        on="year",
        validate="one_to_one",
    )
years = years.merge(
    series["UNRATE"]
    .groupby("year")
    .UNRATE.count()
    .rename("unemployment_reported_months")
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
years["funds_rate_mean_change_pp"] = years.funds_rate_annual_mean_pct.diff()
years["unemployment_mean_change_pp"] = (
    years.unemployment_annual_available_mean_pct.diff()
)
years["house_price_q4_yoy_pct"] = years.house_price_q4_index.pct_change() * 100
years[years.year.between(2012, 2025)].to_csv(
    out / "fdic_historical_macro_2012_2025.csv", index=False
)
pd.DataFrame(manifest).to_csv(out / "fdic_macro_source_manifest.csv", index=False)
print(years.tail(6).to_string(index=False))
