#!/usr/bin/env python3
"""Plot observed bank-level public FFIEC construction subcategories, 2021–25."""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
s = pd.read_csv(ROOT / "data/followon_results/construction_subcategories_2021_2025.csv")
colors = {
    "one_to_four_family_residential_construction": "#146b8a",
    "other_construction_and_land_development": "#b05b22",
}
labels = {
    "one_to_four_family_residential_construction": "1–4-family residential construction",
    "other_construction_and_land_development": "Other construction / land development",
}
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})
fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.7), layout="constrained")
fig.set_constrained_layout_pads(h_pad=0.23, w_pad=0.06)
for category, g in s.groupby("category"):
    color = colors[category]
    axes[0].plot(
        g.year,
        g.funded_stock_thousand_usd / 1e6,
        marker="o",
        linewidth=2.3,
        color=color,
        label=labels[category],
    )
    axes[1].plot(
        g.year,
        g.problem_pct,
        marker="o",
        linewidth=2.3,
        color=color,
        label=labels[category],
    )
for a in axes:
    a.set_xticks([2021, 2022, 2023, 2024, 2025])
    a.grid(True, axis="y", alpha=0.25)
    a.spines[["top", "right"]].set_visible(False)
    a.set_xlabel("December year-end")
axes[0].set_title("Reported funded balances", loc="left", weight="bold")
axes[0].set_ylabel("USD billions (year-end stock)")
axes[0].set_ylim(0, 440)
axes[1].set_title("Reported past-due or nonaccrual share", loc="left", weight="bold")
axes[1].set_ylabel("Percent of same-category funded balance")
axes[1].set_ylim(0, 1.7)
axes[0].legend(loc="upper left", frameon=False, fontsize=8)
fig.suptitle(
    "U.S. bank construction credit: residential and other categories, 2021–2025",
    fontsize=13,
    weight="bold",
)
fig.text(
    0.5,
    -0.01,
    "Source: FFIEC Call Reports, December single-period public schedules. Ratios are reported stocks, not annual defaults or effects of a policy.",
    ha="center",
    fontsize=8,
)
out = ROOT / "data/followon_results/construction_subcategories_2021_2025.png"
fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
print("Saved", out)
