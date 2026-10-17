#!/usr/bin/env python3
"""Prepare one FFIEC December Call Report bank-year dataset and QA report.

Use only official public single-period, tab-delimited bulk files. Input can be the
original FFIEC ZIP or a directory containing its unmodified extracted TXT files.
Values remain in thousands of U.S. dollars except *_share variables (unit ratios).
"""

import argparse
import hashlib
import io
from pathlib import Path
import re
import zipfile

import numpy as np
import pandas as pd


def members(source):
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            return [n for n in z.namelist() if n.lower().endswith(".txt")]
    if source.is_dir():
        return [str(p) for p in source.rglob("*.txt")]
    raise ValueError("Input must be an original FFIEC .zip or extracted TXT directory.")


def one(member_names, source, suffix):
    matches = [n for n in member_names if Path(n).name == suffix]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {suffix}; found {len(matches)}. Wrong product/year or incomplete package?"
        )
    name = matches[0]
    if source.is_file():
        with zipfile.ZipFile(source) as z:
            return name, z.read(name)
    return name, Path(name).read_bytes()


def load(member_names, source, filename, *, por=False):
    name, data = one(member_names, source, filename)
    # Schedule row 1 contains codes; row 2 contains descriptions. POR starts
    # directly with observations under its descriptive header.
    df = pd.read_csv(
        io.BytesIO(data),
        sep="\t",
        dtype=str,
        encoding="latin1",
        skiprows=[] if por else [1],
        low_memory=False,
    )
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    if "IDRSSD" not in df:
        raise ValueError(f"{name}: missing bank identifier IDRSSD")
    df["IDRSSD"] = (
        df["IDRSSD"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )
    df = df.loc[df["IDRSSD"].str.fullmatch(r"\d+")].copy()
    duplicates = int(df["IDRSSD"].duplicated().sum())
    if duplicates:
        raise ValueError(
            f"{name}: {duplicates} duplicate IDRSSD values; cannot safely merge."
        )
    return df


def numeric(s):
    return pd.to_numeric(s, errors="coerce")


def pick(df, *codes):
    present = [c for c in codes if c in df]
    if not present:
        raise ValueError("No required source columns found among " + ", ".join(codes))
    out = numeric(df[present[0]])
    for c in present[1:]:
        out = out.combine_first(numeric(df[c]))
    return out


def add(df, output, **spec):
    result = pd.DataFrame({"IDRSSD": df["IDRSSD"]})
    for name, codes in spec.items():
        result[name] = pick(df, *codes)
    return result


def sum_parts(df, columns):
    return df[columns].sum(axis=1, min_count=1)


def build(year, source, outdir):
    names = members(source)
    suffix = "1231" + str(year)
    pre = "FFIECCDRCall"
    por = load(names, source, f"{pre}BulkPOR{suffix}.txt", por=True)
    rc = load(names, source, f"{pre}ScheduleRC{suffix}.txt")
    rcci = load(names, source, f"{pre}ScheduleRCCI{suffix}.txt")
    available = {Path(n).name for n in names}
    rcn_single = f"{pre}ScheduleRCN{suffix}.txt"
    rcn_first = f"{pre}ScheduleRCN{suffix}(1of2).txt"
    rcn_second = f"{pre}ScheduleRCN{suffix}(2of2).txt"
    if rcn_single in available and rcn_first in available:
        raise ValueError(
            f"{year}: both single-file and split RC-N versions found; choose one official package."
        )
    rcn = load(names, source, rcn_single if rcn_single in available else rcn_first)
    if rcn_second in available and rcn_first in available:
        # Historical split part 2 does not contain construction F172-F177,
        # but should identify exactly the same filers as part 1.
        rcn_extra = load(names, source, rcn_second)
        if set(rcn["IDRSSD"]) != set(rcn_extra["IDRSSD"]):
            raise ValueError(
                f"{year}: split RC-N parts have mismatched bank identifiers."
            )
    ribi = load(names, source, f"{pre}ScheduleRIBI{suffix}.txt")
    optional_names = [
        f"{pre}ScheduleRIBII{suffix}.txt",
        f"{pre}ScheduleRCL{suffix}(1of2).txt",
        f"{pre}ScheduleRCL{suffix}(2of2).txt",
    ]
    optional_present = all(name in available for name in optional_names)
    optional_any = any(name in available for name in optional_names)
    if optional_any and not optional_present:
        raise ValueError(
            "Optional set incomplete: provide RI-B II and both RC-L parts, or none."
        )
    if optional_present:
        ribii = load(names, source, optional_names[0])
        rcl1 = load(names, source, optional_names[1])
        rcl2 = load(names, source, optional_names[2])
        rcl = rcl1.merge(rcl2, on="IDRSSD", how="outer", validate="one_to_one")

    base = add(
        rcci,
        "rcci",
        residential_construction=("RCONF158",),
        other_construction_land=("RCONF159",),
    )
    base["construction_loans"] = sum_parts(
        base, ["residential_construction", "other_construction_land"]
    )

    late = add(
        rcn,
        "rcn",
        pd30_res=("RCONF172",),
        pd30_other=("RCONF173",),
        pd90_res=("RCONF174",),
        pd90_other=("RCONF175",),
        nonaccrual_res=("RCONF176",),
        nonaccrual_other=("RCONF177",),
    )
    late["pd30"] = sum_parts(late, ["pd30_res", "pd30_other"])
    late["pd90"] = sum_parts(late, ["pd90_res", "pd90_other"])
    late["nonaccrual"] = sum_parts(late, ["nonaccrual_res", "nonaccrual_other"])
    late["problem_loans"] = sum_parts(late, ["pd30", "pd90", "nonaccrual"])
    late["problem_residential"] = sum_parts(
        late, ["pd30_res", "pd90_res", "nonaccrual_res"]
    )
    late["problem_other_construction"] = sum_parts(
        late, ["pd30_other", "pd90_other", "nonaccrual_other"]
    )
    late = late[
        [
            "IDRSSD",
            "pd30",
            "pd90",
            "nonaccrual",
            "problem_loans",
            "problem_residential",
            "problem_other_construction",
            "nonaccrual_res",
            "nonaccrual_other",
        ]
    ]

    losses = add(
        ribi,
        "ribi",
        co_res=("RIADC891",),
        rec_res=("RIADC892",),
        co_other=("RIADC893",),
        rec_other=("RIADC894",),
    )
    losses["gross_chargeoffs_ytd"] = sum_parts(losses, ["co_res", "co_other"])
    losses["recoveries_ytd"] = sum_parts(losses, ["rec_res", "rec_other"])
    losses["net_chargeoffs_ytd"] = (
        losses["gross_chargeoffs_ytd"] - losses["recoveries_ytd"]
    )
    losses = losses[
        [
            "IDRSSD",
            "gross_chargeoffs_ytd",
            "recoveries_ytd",
            "net_chargeoffs_ytd",
            "co_res",
            "rec_res",
            "co_other",
            "rec_other",
        ]
    ]

    if optional_present:
        commitment = add(
            rcl,
            "rcl",
            comm_res=("RCONF164", "RCFDF164"),
            comm_other=("RCONF165", "RCFDF165"),
        )
        # RC-L commitments follow the available domestic or consolidated reporting scope.
        parts = commitment[["comm_res", "comm_other"]]
        if parts.isna().any().any() or parts.lt(0).any().any():
            raise ValueError(
                "Supplied construction commitments must be complete and nonnegative"
            )
        commitment["unfunded_construction_commitments"] = sum_parts(
            commitment, ["comm_res", "comm_other"]
        )
        commitment = commitment[["IDRSSD", "unfunded_construction_commitments"]]

    # Some FFIEC 031 filers report only consolidated versions of these RC controls.
    controls = add(
        rc,
        "rc",
        total_assets=("RCON2170", "RCFD2170"),
        total_loans=("RCONB528", "RCFDB528"),
        total_deposits=("RCON2200",),
        equity=("RCON3210", "RCFD3210"),
    )
    if optional_present:
        provisions = add(
            ribii,
            "ribii",
            allowance_total=("RIAD3123",),
            provision_total_ytd=("RIAD4230",),
        )
        # Provision and allowance are BANK-WIDE, not specific to construction loans.

    bank = base.copy()
    frames = [late, losses, controls]
    if optional_present:
        frames.extend([commitment, provisions])
    for frame in frames:
        bank = bank.merge(frame, on="IDRSSD", how="left", validate="one_to_one")
    if not optional_present:
        for name in [
            "unfunded_construction_commitments",
            "allowance_total",
            "provision_total_ytd",
        ]:
            bank[name] = np.nan
    porcols = ["IDRSSD", "Financial Institution Name", "Financial Institution State"]
    present_porcols = [c for c in porcols if c in por.columns]
    bank = bank.merge(
        por[present_porcols], on="IDRSSD", how="left", validate="one_to_one"
    )
    bank.insert(0, "year", year)
    bank["construction_share_loans"] = bank["construction_loans"].div(
        bank["total_loans"].where(bank["total_loans"].gt(0))
    )
    bank["nonaccrual_share_construction"] = bank["nonaccrual"].div(
        bank["construction_loans"].where(bank["construction_loans"].gt(0))
    )
    bank["problem_share_construction"] = bank["problem_loans"].div(
        bank["construction_loans"].where(bank["construction_loans"].gt(0))
    )
    bank["problem_share_residential"] = bank["problem_residential"].div(
        bank["residential_construction"].where(bank["residential_construction"].gt(0))
    )
    bank["problem_share_other_construction"] = bank["problem_other_construction"].div(
        bank["other_construction_land"].where(bank["other_construction_land"].gt(0))
    )
    bank["equity_share_assets"] = bank["equity"].div(
        bank["total_assets"].where(bank["total_assets"].gt(0))
    )
    for category_total, parts in [
        ("problem_loans", ["problem_residential", "problem_other_construction"]),
        ("gross_chargeoffs_ytd", ["co_res", "co_other"]),
    ]:
        mismatch = bank[parts].notna().all(axis=1) & (
            bank[parts].sum(axis=1) - bank[category_total]
        ).abs().gt(0.01)
        if mismatch.any():
            raise ValueError(
                f"{year}: {int(mismatch.sum())} construction subcategory totals fail reconciliation"
            )
    bank = bank.sort_values("IDRSSD")

    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / f"ffiec_bank_year_{year}.csv"
    bank.to_csv(output, index=False)
    expected = {"construction_loans": 456067907} if year == 2025 else {}
    if year == 2025:
        # Funded balances and credit-quality stocks use the same domestic-office scope.
        for col, reference in expected.items():
            actual = bank[col].sum(skipna=True)
            assert (
                abs(actual - reference) <= 1500
            ), f"{col}: {actual:,.0f} deviates from verified 2025 total"

    counts = {
        c: int(bank[c].notna().sum())
        for c in [
            "construction_loans",
            "pd30",
            "pd90",
            "nonaccrual",
            "gross_chargeoffs_ytd",
            "unfunded_construction_commitments",
            "total_assets",
            "total_loans",
            "allowance_total",
            "provision_total_ytd",
        ]
    }
    state = (
        bank["Financial Institution State"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )
    positive = bank["construction_loans"].gt(0)
    valid_state = state.str.fullmatch(r"[A-Z]{2}")
    valid_positive = positive & valid_state
    sha = (
        hashlib.sha256(source.read_bytes()).hexdigest()
        if source.is_file()
        else "directory input: hash original ZIP separately"
    )
    report = outdir / f"ffiec_quality_{year}.md"
    commitment_display = (
        f"{bank.unfunded_construction_commitments.sum():,.0f}"
        if optional_present
        else "not supplied (not zero)"
    )
    report.write_text(
        f"# FFIEC {year} year-end quality check\n\n"
        f"- Input: `{source}`\n- Source SHA-256: `{sha}`\n"
        f'- Input scope: **{"five core schedules plus three optional" if optional_present else "five core schedules only"}**\n'
        f"- Parsed reporting institutions (RC-C): **{len(bank):,}**\n"
        f'- Matched institution profiles: **{bank.get("Financial Institution Name", pd.Series(dtype=str)).notna().sum():,}**\n'
        f"- Positive construction balances: **{int(bank.construction_loans.gt(0).sum()):,}**\n"
        f"- Positive balances with valid two-letter headquarters jurisdiction: **{int(valid_positive.sum()):,}**\n"
        f"- Headquarters jurisdictions among valid positive-balance institutions: **{state[valid_positive].nunique():,}**\n"
        f"- Construction balances (source thousands USD): **{bank.construction_loans.sum():,.0f}**\n"
        f"- Unfunded commitments (source thousands USD): **{commitment_display}**\n"
        f"- Problem loans (source thousands USD): **{bank.problem_loans.sum():,.0f}**\n"
        f"- Gross charge-offs (source thousands USD): **{bank.gross_chargeoffs_ytd.sum():,.0f}**\n\n"
        "## Nonmissing coverage\n\n| Measure | Banks |\n|---|---:|\n"
        + "".join(f"| {name} | {value:,} |\n" for name, value in counts.items())
        + "\n**Limits:** Construction delinquency and nonaccrual are year-end stocks; "
        "charge-offs and provisions are year-to-date flows. Allowance and provision here "
        "are bank-wide. FFIEC does not report individual loan lifecycle stages. "
        "Ratios are undefined where their denominators are missing or zero.\n",
        encoding="utf-8",
    )
    print(
        f"Prepared {len(bank):,} bank records for {year}: {output}\nQuality report: {report}"
    )
    return output, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Original ZIP or extracted TXT directory",
    )
    parser.add_argument(
        "--outdir", type=Path, default=Path(__file__).parent / "data" / "processed"
    )
    args = parser.parse_args()
    build(args.year, args.input, args.outdir)
