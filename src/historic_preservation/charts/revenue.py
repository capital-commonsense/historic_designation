"""Property tax billed on historic and other property, with the DC Policy Center growth-gap scenario."""

import json

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import DARK, GREY, LIGHT, PAPER, RED, headline, save, style
from historic_preservation.config import ANALYSIS


def property_tax() -> None:
    path = ANALYSIS / "property_tax_by_year.csv"
    if not path.exists():
        return
    t = pd.read_csv(path, index_col=0) / 1e6
    s = json.loads((ANALYSIS / "property_tax_summary.json").read_text())
    last = t.index[-1]
    gap, stock = t.loc[last, "scenario_gap_total"], t.loc[last, "scenario_gap_existing_stock"]
    share = s["historic_share"][str(last)]
    ward = s["same_records_gap_last_year"]

    fig, ax = plt.subplots(figsize=(10, 5.6))
    layers = [("other", "Other property", LIGHT), ("historic", "Historic districts and landmarks", DARK),
              ("scenario_gap_total", "Scenario: older districts' homes grow at the rest of the city's rate", RED)]
    ax.stackplot(t.index, *[t[c] for c, _, _ in layers], colors=[c for _, _, c in layers], edgecolor=PAPER, lw=0.6)
    base = t["other"] + t["historic"]
    ax.plot(t.index, base + t["scenario_gap_existing_stock"], color=PAPER, lw=1.2, ls=(0, (3, 2)))
    x = last + 0.15
    for y, text, color in [(t.loc[last, "other"] / 2, f"Other property\n${t.loc[last, 'other'] / 1e3:,.2f}B", GREY),
                           (t.loc[last, "other"] + t.loc[last, "historic"] / 2,
                            f"Historic districts\nand landmarks\n${t.loc[last, 'historic'] / 1e3:,.2f}B ({share:.0%})", GREY),
                           (base[last] + gap / 2, f"Scenario gap\n${gap:,.0f}M", RED)]:
        ax.text(x, y, text, va="center", ha="left", color=color, fontsize=8.5,
                fontweight="semibold" if color == RED else "normal")
    ax.annotate(f"Dashed: existing buildings only, ${stock:,.0f}M", (last - 1, base[last - 1] + t.loc[last - 1, "scenario_gap_total"]),
                xytext=(0, 14), textcoords="offset points", ha="right", va="bottom", color=RED, fontsize=8,
                arrowprops={"arrowstyle": "-", "color": RED, "lw": 0.8})
    style(ax)
    ax.set_xlim(t.index[0], last)
    ax.set_xticks(t.index)
    ax.set_ylim(0, (base + t["scenario_gap_total"]).max() * 1.08)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e3:,.1f}B"))
    ax.set_xlabel("Tax year")
    fig.subplots_adjust(right=0.8, bottom=0.24)
    headline(fig, f"If homes in DC's older historic districts had kept pace with the rest of the city, "
                  f"they would pay about ${gap:,.0f}M more property tax in {last}",
             f"Property tax billed, TY{t.index[0]}–{last}, with a scenario built on the DC Policy Center's 2006–21 growth gap")
    save(fig, "property_tax_scenario", t.round(3),
         f"Tax levied per record on today's DC tax roll (OTR ITSPE billing history), split by whether the record's district "
         f"or landmark was designated by that year. Red: the tax on residential buildings in districts designated before "
         f"2006, compounded from 2006 at DCPC's measured gap in total assessed value growth (6.2% a year outside historic "
         f"districts, 4.9% inside, 2006–21, carried forward), minus what they pay; the dashed line uses DCPC's gap for "
         f"buildings standing in 2006 (94% vs 85%). A scenario, not a measured loss: DCPC's gap includes new construction "
         f"outside the districts and where neighborhoods started, and DCPC does not attribute it to designation. On the "
         f"roll's own records, TY{s['years'][0]}–{last}, the same homes fall \\${ward['citywide_rate'] / 1e6:,.0f}M behind "
         f"the city's other homes but come out \\${-ward['within_ward_rates'] / 1e6:,.0f}M ahead compared ward by ward. "
         f"Source: data/analysis/property_tax_by_year.csv; DCPC, April 2022 (inputs/dcpc_growth_2006_2021.csv).")
