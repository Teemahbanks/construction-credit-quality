#!/usr/bin/env python3
"""Retrieve year-end FDIC BankFind Suite financials, 2012–2025.

Separate FDIC historical series: do not splice into FFIEC national totals.
The BankFind financial API field metadata documents each requested variable.
Every annual original HTTP JSON response is stored compressed with a SHA-256
of the uncompressed response and a manifest. No employer/proprietary data.
"""

import argparse
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RAW = DATA / "fdic_historical_raw"
OUT = DATA / "fdic_historical_analysis"
API = "https://api.fdic.gov/banks/financials"
FIELDS = [
    "CERT",
    "RSSDID",
    "NAME",
    "REPDTE",
    "LNRECNFM",
    "LNRECNOT",
    "P3RECNFM",
    "P9RECNFM",
    "NARECNFM",
    "P3RECNOT",
    "P9RECNOT",
    "NARECNOT",
    "DRRECNFM",
    "CRRECNFM",
    "DRRECNOT",
    "CRRECNOT",
    "ASSET",
    "LNLSGR",
    "EQ",
]
MONETARY = FIELDS[4:]


def obtain(year, session):
    url_params = {
        "filters": f"REPDTE:{year}1231",
        "fields": ",".join(FIELDS),
        "limit": 10000,
    }
    path = RAW / f"fdic_financials_{year}1231.json.gz"
    if path.exists():
        payload = gzip.decompress(path.read_bytes())
        source = "cached official response"
    else:
        response = session.get(API, params=url_params, timeout=65)
        response.raise_for_status()
        payload = response.content
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(payload, compresslevel=7, mtime=0))
        source = "live official API"
        time.sleep(0.6)
    parsed = json.loads(payload)
    meta = parsed.get("meta", {})
    if meta.get("total") != len(parsed.get("data", [])):
        raise ValueError(
            f'{year}: API result was paginated or incomplete: {meta.get("total")} != {len(parsed.get("data",[]))}'
        )
    if meta.get("parameters", {}).get("filters") != url_params["filters"]:
        raise ValueError(f"{year}: wrong reporting period returned")
    data = pd.DataFrame([row["data"] for row in parsed["data"]])
    if not set(FIELDS).issubset(data):
        raise ValueError(
            f"{year}: absent official FDIC fields: {set(FIELDS)-set(data)}"
        )
    if set(data.REPDTE.astype(str)) != {f"{year}1231"}:
        raise ValueError(f"{year}: observed bank records from another date")
    # The FDIC universe includes foreign branches that do not report this Call
    # Report construction schedule and therefore are absent from FFIEC's filer table.
    missing_core = data.LNRECNFM.isna() | data.LNRECNOT.isna()
    data = data.loc[~missing_core].copy()
    data["IDRSSD"] = data.RSSDID.astype("Int64").astype(str)
    if (~data.IDRSSD.str.fullmatch(r"\d+")).any() or data.IDRSSD.duplicated().any():
        raise ValueError(f"{year}: FDIC RSSD mapping missing or duplicates")
    for col in MONETARY:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["year"] = year
    data["funded_construction"] = data.LNRECNFM + data.LNRECNOT
    for cat, codes in [
        ("residential", ["P3RECNFM", "P9RECNFM", "NARECNFM"]),
        ("other", ["P3RECNOT", "P9RECNOT", "NARECNOT"]),
    ]:
        data[f"problem_{cat}"] = data[codes].sum(axis=1, min_count=len(codes))
    data["problem_total"] = data.problem_residential + data.problem_other
    data["residential_problem_share"] = data.problem_residential / data.LNRECNFM.where(
        data.LNRECNFM.gt(0)
    )
    data["other_problem_share"] = data.problem_other / data.LNRECNOT.where(
        data.LNRECNOT.gt(0)
    )
    data["construction_concentration"] = data.funded_construction / data.LNLSGR.where(
        data.LNLSGR.gt(0)
    )
    data["equity_ratio"] = data.EQ / data.ASSET.where(data.ASSET.gt(0))
    data["gross_construction_chargeoffs_ytd"] = data.DRRECNFM + data.DRRECNOT
    data["net_construction_chargeoffs_ytd"] = data.gross_construction_chargeoffs_ytd - (
        data.CRRECNFM + data.CRRECNOT
    )
    data["problem_share"] = data.problem_total / data.funded_construction.where(
        data.funded_construction.gt(0)
    )
    if data.funded_construction.lt(0).any():
        raise ValueError(f"{year}: negative funded balance")
    if data.problem_share.dropna().gt(1.00001).any():
        raise ValueError(f"{year}: impossible reported problem share")
    quality_coverage = (
        data[
            [
                "LNRECNFM",
                "LNRECNOT",
                "problem_residential",
                "problem_other",
                "LNLSGR",
                "ASSET",
                "EQ",
            ]
        ]
        .notna()
        .sum()
        .to_dict()
    )
    item = {
        "year": year,
        "report_date": f"{year}1231",
        "source_url": API,
        "query_filters": url_params["filters"],
        "query_fields": url_params["fields"],
        "api_total_rows": len(parsed["data"]),
        "excluded_without_core_call_report": int(missing_core.sum()),
        "retained_bank_ids": len(data),
        "complete_problem_bank_ids": int(data.problem_total.notna().sum()),
        "source_json_gzip": path.name,
        "raw_response_sha256": sha256(payload).hexdigest(),
        "retrieved_or_cached": source,
        "api_index_name": meta.get("index", {}).get("name"),
        "nonmissing_counts": json.dumps(quality_coverage, sort_keys=True),
    }
    return data, item


def main(start, end):
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "academic-public-FFIEC-construction-credit-research/0.1"
    tables = []
    manifest = []
    for year in range(start, end + 1):
        d, entry = obtain(year, s)
        tables.append(d)
        manifest.append(entry)
        print(
            year,
            entry["retained_bank_ids"],
            "banks;",
            entry["complete_problem_bank_ids"],
            "complete problem outcomes;",
            f"${d.funded_construction.sum()/1e6:.3f}B funded",
            flush=True,
        )
    panel = pd.concat(tables, ignore_index=True)
    if panel[["IDRSSD", "year"]].duplicated().any():
        raise ValueError("Repeated bank/year IDs")
    output = OUT / f"fdic_bank_panel_{start}_{end}.csv"
    panel.to_csv(output, index=False)
    pd.DataFrame(manifest).to_csv(
        OUT / f"fdic_api_source_manifest_{start}_{end}.csv", index=False
    )
    sums = []
    for y, g in panel.groupby("year"):
        # In early years, missing past-due components remain unknown. Annual rates
        # use banks with all six reported categories.
        good = g[g.problem_total.notna()].copy()
        sums.append(
            dict(
                year=y,
                bank_records=len(g),
                complete_quality_banks=len(good),
                total_funded_usd_b=g.funded_construction.sum() / 1e6,
                complete_bank_funded_usd_b=good.funded_construction.sum() / 1e6,
                complete_bank_residential_funded_usd_b=good.LNRECNFM.sum() / 1e6,
                complete_bank_problem_usd_b=good.problem_total.sum() / 1e6,
                complete_bank_residential_problem_usd_b=good.problem_residential.sum()
                / 1e6,
                problem_share_pct=100
                * good.problem_total.sum()
                / good.funded_construction.sum(),
                residential_problem_share_pct=100
                * good.problem_residential.sum()
                / good.LNRECNFM.sum(),
                chargeoffs_ytd_usd_m=good.gross_construction_chargeoffs_ytd.sum()
                / 1000,
            )
        )
    pd.DataFrame(sums).to_csv(
        OUT / f"fdic_annual_summary_{start}_{end}.csv", index=False
    )
    print("Saved source-specific bank panel, yearly summary, and manifest to", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=int, default=2012)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()
    if args.start < 2012 or args.end > 2025 or args.start > args.end:
        ap.error(
            "Use dates from 2012 through 2025; 2010–2011 have incomplete FDIC category past-due coverage"
        )
    main(args.start, args.end)
