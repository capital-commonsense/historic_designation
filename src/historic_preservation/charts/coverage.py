"""Coverage of the scraped nominations against HPO's published counts, by fiscal year."""

import matplotlib.pyplot as plt
import pandas as pd

from historic_preservation.charts import GREY, INK, LIGHT, MID, MOBILE_WIDTH, RED, RULE, headline, pick, save, sparse_years, style
from historic_preservation.config import ANALYSIS

THRESHOLD = 0.8


def by_year() -> None:
    c = pd.read_csv(ANALYSIS / "coverage_by_year.csv").set_index("fy")
    t = c.loc[c["hpo_received"].notna(), ["hpo_received", "scraped_cases", "coverage_ratio", "approved_coverage",
                                           "adequate", "records_request_cases"]]
    ok = int(t["adequate"].sum())

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=pick((10, 6.4), (MOBILE_WIDTH, 8)), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})
    fig.subplots_adjust(hspace=pick(0.2, 0.5))
    ax1.bar(t.index - 0.2, t["hpo_received"], width=0.4, color=LIGHT, label="HPO: applications received")
    ax1.bar(t.index + 0.2, t["scraped_cases"], width=0.4, color=INK, label="Scraped: nominations decided")
    if t["records_request_cases"].notna().any():
        ax1.plot(t.index, t["records_request_cases"], "o", color=GREY, label="Records request")
    style(ax1)
    ax1.set_ylabel("Cases")
    above = dict(loc="lower left", bbox_to_anchor=(0, 1.0, 1, 0), mode="expand", ncol=1)  # phones: each legend above its panel, off the data
    ax1.legend(frameon=False, fontsize=8.5, **pick({}, above))
    ax2.plot(t.index, t["coverage_ratio"], "-o", color=INK, lw=2, ms=4, label="Scraped ÷ HPO received")
    ax2.plot(t.index, t["approved_coverage"], "-s", color=MID, lw=1.6, ms=4, label="Scraped designations ÷ HPO approved")
    ax2.axhline(THRESHOLD, color=RED, lw=1.2, ls="--")
    ax2.text(t.index.max() + 0.7, THRESHOLD, f"{THRESHOLD}\nthreshold", fontsize=8, color=RED, fontweight="semibold",
             va="center")
    for fy in t.index[~t["adequate"].astype(bool)]:
        ax2.axvspan(fy - 0.5, fy + 0.5, color="#F4F3F0", zorder=0)
    style(ax2)
    ax2.set_ylabel("Coverage ratio")
    ax2.legend(frameon=False, fontsize=8.5, **pick(dict(loc="upper left"), above))
    ax2.set_xticks(t.index)
    ax2.set_xticklabels(pick([str(y)[2:] if y % 2 else str(y) for y in t.index], sparse_years(t.index)), fontsize=8)
    ax2.set_xlabel("Fiscal year (shaded: below the threshold; rates are not reported for these years)")
    fig.subplots_adjust(bottom=0.14)
    headline(fig, f"Scraped records meet the {THRESHOLD} coverage threshold in {ok} of the {len(t)} fiscal years "
             "HPO reports", f"Scraped nominations against HPO's published counts, FY{t.index.min()}–{t.index.max()}")
    save(fig, "coverage_by_year", t,
         "HPO counts as printed in its annual reports and Inventory updates (the latest edition covering each year); "
         "scraped counts from data/joined/nominations.csv. A ratio above 1 means the scrape found more decided cases "
         "than HPO reported received that year (applications and decisions fall in different years). 'Adequate' "
         "follows data/analysis/coverage_by_year.csv. Source: data/analysis/coverage_by_year.csv.")
