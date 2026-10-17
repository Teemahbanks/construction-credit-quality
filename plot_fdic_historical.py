#!/usr/bin/env python3
"""Plot separate FDIC 2012–2025 bank construction exposure and reported credit-quality stocks."""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

R = Path(__file__).parent
p = pd.read_csv(R / "data/fdic_historical_analysis/fdic_bank_panel_2012_2025.csv")
rows = []
for y, g in p.groupby("year"):
    for category, balance, problem in [
        ("1–4-family residential construction", "LNRECNFM", "problem_residential"),
        ("Other construction / land development", "LNRECNOT", "problem_other"),
    ]:
        rows.append(
            dict(
                year=y,
                category=category,
                funded_b=g[balance].sum() / 1e6,
                reported_problem_pct=100 * g[problem].sum() / g[balance].sum(),
            )
        )
s = pd.DataFrame(rows)
colors = {
    "1–4-family residential construction": "#146b8a",
    "Other construction / land development": "#b05b22",
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5})
fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
for cat, g in s.groupby("category"):
    axes[0].plot(
        g.year,
        g.funded_b,
        "o-",
        label=cat,
        color=colors[cat],
        linewidth=2,
        markersize=4,
    )
    axes[1].plot(
        g.year,
        g.reported_problem_pct,
        "o-",
        label=cat,
        color=colors[cat],
        linewidth=2,
        markersize=4,
    )
for a in axes:
    a.set_xlim(2012, 2025)
    a.set_xticks([2012, 2014, 2016, 2018, 2020, 2022, 2024])
    a.grid(axis="y", alpha=0.25)
    a.spines[["top", "right"]].set_visible(False)
    a.set_xlabel("December year-end")
axes[0].set_title("FDIC reported construction balances", loc="left", weight="bold")
axes[0].set_ylabel("USD billions (year-end stock)")
axes[0].legend(frameon=False, loc="upper left", fontsize=8)
axes[1].set_title(
    "FDIC reported past-due / nonaccrual shares", loc="left", weight="bold"
)
axes[1].set_ylabel("Percent of category funded balance")
fig.suptitle(
    "U.S. bank construction lending across 14 year-ends · FDIC BankFind, 2012–2025",
    fontsize=12.5,
    weight="bold",
)
fig.text(
    0.5,
    -0.012,
    "Source: FDIC BankFind financial API. Domestic-office construction balances; this figure uses the separate FDIC series.",
    ha="center",
    fontsize=7.7,
)
out = R / "data/fdic_historical_analysis/fdic_construction_long_history.png"
fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
print(out)
