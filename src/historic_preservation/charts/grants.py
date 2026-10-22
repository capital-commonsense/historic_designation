"""HPO's Historic Homeowner Grant program by fiscal year: money available, awarded and spent; applicants and awards."""

import json

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import DARK, GREY, INK, LIGHT, PAPER, RED, headline, save, style
from historic_preservation.config import ANALYSIS

# Red: spending, the finding (well under what was available or awarded).
DOLLARS = (("available", "Funds available", LIGHT), ("awarded_dollars", "Awarded", DARK), ("expended", "Spent", RED))
COUNTS = (("applicants", "Applicants", LIGHT), ("awarded_count", "Grants awarded", DARK))


def homeowner_grants() -> None:
    t = pd.read_csv(ANALYSIS / "homeowner_grants_by_year.csv", index_col="fy")
    s = json.loads((ANALYSIS / "homeowner_grants_summary.json").read_text())
    fig, (top, bot) = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12})
    w = 0.27
    for i, (key, name, color) in enumerate(DOLLARS):
        top.bar(t.index + (i - 1) * w, t[key].fillna(0), width=w, color=color, label=name)
    for y, v in t["expended"].dropna().items():
        top.text(y + w, v + 12e3, f"{v / 1e3:,.0f}", ha="center", va="bottom", fontsize=6.5, color=RED)
    style(top)
    top.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e3:,.0f}K"))
    top.legend(loc="upper right", ncol=3, fontsize=8.5)
    top.annotate("26 of 31 awards to owners\nin the Kenesaw Apartments", (2022, 577e3), (2019.4, 760e3), fontsize=7.5,
                 color=GREY, ha="left", arrowprops=dict(arrowstyle="-", color=GREY, lw=0.6))
    top.set_ylim(0, max(t[["available", "awarded_dollars", "expended"]].max()) * 1.18)

    for i, (key, name, color) in enumerate(COUNTS):
        bot.bar(t.index + (i - 0.5) * w * 1.3, t[key].fillna(0), width=w * 1.3, color=color, label=name)
    bot.plot(t.index, t["projects"], "o", mfc=INK, mec=PAPER, mew=1, ms=5.5, label="Projects with spending that year")
    for y in t.index[t["no_new_round"] == 1]:
        bot.text(y, 22, "no new\nround", ha="center", va="bottom", fontsize=6.5, color=GREY)
    style(bot)
    bot.legend(loc="upper right", ncol=3, fontsize=8.5)
    bot.set_ylim(0, t[["applicants", "awarded_count", "projects"]].max().max() * 1.25)
    bot.set_xticks(t.index)
    bot.set_xticklabels([f"{y % 100:02d}" if y > t.index.min() else f"FY{y}" for y in t.index], fontsize=8)

    a0, a1 = s["available_window"]
    headline(fig, f"DC's historic homeowner grants have paid out ${s['expended_total'] / 1e6:.1f}M since "
                  f"{s['expended_years'][0]}; in {a0}–{a1}, HPO spent ${s['expended_total_window'] / 1e6:.1f}M of the "
                  f"${s['available_total'] / 1e6:.1f}M available",
             f"Historic Homeowner Grant program, by fiscal year, FY{t.index.min()}–{t.index.max()}")
    fig.subplots_adjust(bottom=0.13)
    save(fig, "homeowner_grants", t,
         "Source: DC HPO annual reports FY2007–2023 (inputs/homeowner_grants.csv, each figure with the report text it "
         "comes from). Funds available and awarded are labels on HPO's own bar charts (FY2016–22, \\$ thousands); "
         "spending is each year's report text, labelled in \\$ thousands. HPO's later charts revise some years' "
         "spending (e.g. 2008 \\$989K, 2013 \\$129K, 2016 \\$188K). Applicants: Part I applications (FY2007), "
         "applications (2009, 2021), applicants in a new round (2013–14), else homeowners HPO worked with seeking "
         "awards; not reported for 2008, 2022–23. Awards: grants awarded or selected that year (2019: the FY2019 "
         "report says 7, later reports 12). FY2023: the FY2022 awards, disbursed; excludes \\$1.5M OP awarded to the "
         "Kenesaw Apartments separately.")
