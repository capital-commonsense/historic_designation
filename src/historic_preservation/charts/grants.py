"""HPO's Historic Homeowner Grant program by fiscal year: money available, awarded and spent; applicants and awards."""

import json

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import DARK, GREY, LIGHT, MOBILE_WIDTH, RED, headline, mobile, pick, save, style
from historic_preservation.config import ANALYSIS

# Red: awards, in both panels.
DOLLARS = (("available", "Funds available", LIGHT), ("awarded_dollars", "Awarded", RED), ("expended", "Spent", DARK))
COUNTS = (("applicants", "Applicants", LIGHT), ("awarded_count", "Grants awarded", RED))


def homeowner_grants() -> None:
    t = pd.read_csv(ANALYSIS / "homeowner_grants_by_year.csv", index_col="fy")
    s = json.loads((ANALYSIS / "homeowner_grants_summary.json").read_text())
    fig, (top, bot) = plt.subplots(2, 1, figsize=pick((10, 7.2), (MOBILE_WIDTH, 9)), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": pick(0.12, 0.45)})
    w = 0.27
    for i, (key, name, color) in enumerate(DOLLARS):
        top.bar(t.index + (i - 1) * w, t[key].fillna(0), width=w, color=color, label=name)
    style(top)
    top.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e3:,.0f}K"))
    # Phones: each legend above its panel, where the bars can't reach it, and no wider than the panel.
    legend_at = pick(dict(loc="upper right", ncol=3), dict(loc="lower left", bbox_to_anchor=(0, 1.0, 1, 0), mode="expand", ncol=3))
    top.legend(fontsize=8.5, **legend_at)
    # Phones: the note ends inside the plot, so it doesn't push the plot's right edge in.
    top.annotate("26 of 31 awards to owners\nin the Kenesaw Apartments", (2022, 577e3),
                 pick((2019.4, 760e3), (2023.4, 760e3)), fontsize=7.5, color=GREY, ha=pick("left", "right"),
                 arrowprops=dict(arrowstyle="-", color=GREY, lw=0.6))
    top.set_ylim(0, max(t[["available", "awarded_dollars", "expended"]].max()) * 1.18)

    for i, (key, name, color) in enumerate(COUNTS):
        bot.bar(t.index + (i - 0.5) * w * 1.3, t[key].fillna(0), width=w * 1.3, color=color, label=name)
    gaps = t.index[t["no_new_round"] == 1]
    for y in gaps if not mobile() else ():
        bot.text(y, 3, "no new\nround", ha="center", va="bottom", fontsize=6.5, color=GREY)
    runs = [list(g) for _, g in pd.Series(gaps).groupby(pd.Series(gaps).diff().ne(1).cumsum())] if mobile() else []
    for run in runs:  # phones: one label over each run of years
        bot.text((run[0] + run[-1]) / 2, 3, "no new\nround" + ("s" if len(run) > 1 else ""), ha="center", va="bottom",
                 fontsize=6.5, color=GREY)
    style(bot)
    bot.legend(fontsize=8.5, **(legend_at | pick({}, dict(ncol=2))))
    bot.set_ylim(0, t[["applicants", "awarded_count"]].max().max() * 1.25)
    bot.set_xticks(t.index)
    bot.set_xticklabels([pick(f"{y % 100:02d}" if y > t.index.min() else f"FY{y}", f"{y % 100:02d}") for y in t.index],
                        fontsize=8)
    bot.set_xlabel(pick("", "Fiscal year"))

    a0, a1 = s["available_window"]
    headline(fig, f"DC's historic homeowner grants have paid out ${s['expended_total'] / 1e6:.1f}M since "
                  f"{s['expended_years'][0]}; in {a0}–{a1}, HPO spent ${s['expended_total_window'] / 1e6:.1f}M of the "
                  f"${s['available_total'] / 1e6:.1f}M available",
             f"Historic Homeowner Grant program, by fiscal year, FY{t.index.min()}–{t.index.max()}")
    fig.subplots_adjust(bottom=0.13)
    save(fig, "homeowner_grants", t.drop(columns="projects"),
         "Source: DC HPO annual reports FY2007–2023 (inputs/homeowner_grants.csv, each figure with the report text it "
         "comes from). Funds available and awarded are labels on HPO's own bar charts (FY2016–22, \\$ thousands); "
         "spending is each year's report text. HPO's later charts revise some years' "
         "spending (e.g. 2008 \\$989K, 2013 \\$129K, 2016 \\$188K). Applicants: Part I applications (FY2007), "
         "applications (2009, 2021), applicants in a new round (2013–14), else homeowners HPO worked with seeking "
         "awards; not reported for 2008, 2022–23. Awards: grants awarded or selected that year (2019: the FY2019 "
         "report says 7, later reports 12). FY2023: the FY2022 awards, disbursed; excludes \\$1.5M OP awarded to the "
         "Kenesaw Apartments separately.")
