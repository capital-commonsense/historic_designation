"""DC against New York, Philadelphia and Boston: designated land over time and today."""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import PALETTE, save, style
from historic_preservation.config import ANALYSIS

COLORS = {"Washington": PALETTE[5], "New York": PALETTE[0], "Philadelphia": PALETTE[2], "Boston": PALETTE[1]}


def designated_land() -> None:
    path = ANALYSIS / "comps_by_year.csv"
    if not path.exists():
        return
    y = pd.read_csv(path)
    cur = pd.read_csv(ANALYSIS / "comps_current.csv").set_index("city").reindex(list(COLORS))
    t = y.pivot(index="year", columns="city", values="designated_area_share_excl_parkland")[list(COLORS)]
    dc = cur.loc["Washington", "designated_area_share_excl_parkland"]
    others = cur.drop("Washington")["designated_area_share_excl_parkland"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 5.4), gridspec_kw={"width_ratios": [1.6, 1]})
    for city, color in COLORS.items():
        ax.step(t.index, t[city], where="post", color=color, lw=2.2 if city == "Washington" else 1.6, label=city)
    style(ax)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Share of city land area designated (excluding parkland)")
    ax.set_xlabel("Year of designation (today's boundaries)")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_title("Over time", loc="left", fontsize=10)

    x = range(len(cur))
    ax2.bar([i - 0.2 for i in x], cur["designated_area_share"], width=0.4, color=[COLORS[c] for c in cur.index],
            alpha=0.45, label="All designations")
    ax2.bar([i + 0.2 for i in x], cur["designated_area_share_excl_parkland"], width=0.4,
            color=[COLORS[c] for c in cur.index], label="Excluding parkland")
    style(ax2)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax2.set_xticks(list(x))
    short = {"Washington": "DC", "New York": "NYC", "Philadelphia": "Phila.", "Boston": "Boston"}
    ax2.set_xticklabels([f"{short[c]}\n{cur.loc[c, 'landmarks_per_100k']:.0f}" for c in cur.index], fontsize=9)
    ax2.set_xlabel("Second line: landmarks per 100,000 residents (each city's own unit)", fontsize=8)
    ax2.set_ylim(bottom=0)
    ax2.legend(frameon=False, fontsize=8.5)
    ax2.set_title("Today (lighter: including parkland)", loc="left", fontsize=10)
    fig.suptitle(f"DC has designated {dc:.0%} of its land outside parks; New York, Philadelphia and Boston "
                 f"{others.min():.0%}–{others.max():.0%}", x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(bottom=0.24, top=0.86, wspace=0.22)
    out = pd.concat({"by_year": t, "current": cur.T}, names=["table"])
    save(fig, "comps_designated_land", out,
         "Union of each city's historic districts and individual landmark polygons, clipped to the 2020 Census city "
         "boundary and divided by Census land area; equal-area projection. Parkland: designations that are mainly parks "
         "(inputs/comps_parkland.csv; e.g. DC's Rock Creek Park and Fort Circle Parks districts, Boston's Franklin Park); "
         "New York's scenic landmarks are not in its layer. Today's boundaries are dated by each feature's designation "
         "(NYC extensions carry their own dates); undated designations are left out of the time series. Landmark units "
         "differ: NYC landmark sites, Philadelphia registered parcels, Boston approved landmarks, DC Inventory landmarks. "
         "Sources: DC GIS; NYC Open Data (LPC); City of Philadelphia ArcGIS; City of Boston ArcGIS; Census TIGERweb.")
