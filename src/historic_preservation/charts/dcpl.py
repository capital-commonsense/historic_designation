"""DC Preservation League finances (H10): 990 revenue by source, mitigation funds, grants awarded."""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import MUTED, PALETTE, save, style
from historic_preservation.config import INPUTS, NORMALIZED

SOURCES = (("contributions_grants", "Contributions and grants", PALETTE[0]),
           ("program_service_revenue", "Program service revenue", PALETTE[1]),
           ("other", "Investment and other", MUTED))


def revenue_and_funds() -> None:
    s = pd.read_csv(NORMALIZED / "dcpl_990_summary.csv").dropna(subset=["total_revenue"])
    s["year"] = s["tax_period"].astype(str).str[:4].astype(int)
    s["other"] = s["total_revenue"] - s["contributions_grants"] - s["program_service_revenue"]
    t = s.set_index("year")[[k for k, _, _ in SOURCES] + ["total_revenue"]]
    g = pd.read_csv(NORMALIZED / "dcpl_grant_awards.csv")
    grants = g[~g["repeated_in_document"]].groupby("year")["amount"].sum()
    t = t.reindex(range(min(t.index.min(), grants.index.min()), t.index.max() + 1))
    t["grants_awarded"] = grants.reindex(t.index)
    funds = pd.read_csv(INPUTS / "dcpl_funds.csv")
    funds = funds[funds["fund"] != "DCPL grants"]

    big = t[t["total_revenue"] >= 1e6]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    bottom = pd.Series(0.0, index=t.index)
    for key, name, color in SOURCES:
        ax.bar(t.index, t[key].fillna(0), bottom=bottom, color=color, label=name, width=0.7)
        bottom += t[key].fillna(0)
    ax.plot(t.index, t["grants_awarded"], "o", color="#000000", ms=5, label="Grants DCPL awarded (its grant lists)")
    style(ax)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e3:,.0f}K"))
    ymax = t["total_revenue"].max()
    for r in funds.itertuples():
        if pd.notna(r.year) and t.index.min() <= r.year <= t.index.max():
            ax.axvline(r.year, color="#999999", lw=0.8, ls=":")
            ax.text(r.year + 0.1, ymax * 0.95, f"{r.fund}\n({r.funder})", fontsize=7, color="#555555", va="top")
    missing = [y for y in t.index if pd.isna(t.loc[y, "total_revenue"])]
    ax.set_xticks(t.index)
    ax.set_xticklabels([str(y) for y in t.index], fontsize=8, rotation=45)
    ax.set_ylabel("Dollars per filing year")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(0, 0.85))
    main = {y: ("program service revenue" if r.program_service_revenue > r.contributions_grants else "contributions")
            for y, r in big.iterrows()}
    ax.set_title(f"DCPL's revenue topped $1M in {len(big)} years: "
                 + "; ".join(f"{y}, mostly {m}" for y, m in main.items()), loc="left", fontsize=11.5, fontweight="bold")
    outside = funds[~funds["year"].between(t.index.min(), t.index.max())]
    fig.subplots_adjust(bottom=0.2)
    save(fig, "dcpl_revenue_and_funds", t,
         "DC Preservation League (EIN 52-1038849) revenue by source from its Form 990s via ProPublica, by the year "
         "the tax period ends (fiscal years ended in March until 2019, then December). No bar: no itemized 990 "
         f"available ({', '.join(map(str, missing)) or 'none'}; FY2009–10 were 990-EZ). Dots: grants listed in "
         "DCPL's grant-award PDFs. Mitigation funds DCPL administers (inputs/dcpl_funds.csv; amounts unverified) "
         "get a dotted line when they fall within the 990 years; outside them: " + "; ".join(f"{r.fund} ({r.funder}, {int(r.year)})" for r in outside.itertuples()
                                                     if pd.notna(r.year)) + ".")
