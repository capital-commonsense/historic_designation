"""DC against New York, Philadelphia and Boston: designated land over time and today."""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.charts import BLUE, GOLD, GREEN, INK, MOBILE_WIDTH, PAPER, RED, RULE, headline, pick, save, style
from historic_preservation.config import ANALYSIS

# Same coding as the animated version: red for DC (the finding), the shared hues for the others.
COLORS = {"Washington": RED, "New York": BLUE, "Philadelphia": GREEN, "Boston": GOLD}


def designated_land() -> None:
    path = ANALYSIS / "comps_by_year.csv"
    if not path.exists():
        return
    y = pd.read_csv(path)
    cur = pd.read_csv(ANALYSIS / "comps_current.csv").set_index("city").reindex(list(COLORS))
    t = y.pivot(index="year", columns="city", values="designated_area_share_excl_parkland")[list(COLORS)]
    dc = cur.loc["Washington", "designated_area_share_excl_parkland"]
    others = cur.drop("Washington")["designated_area_share_excl_parkland"]

    fig, (ax, ax2) = plt.subplots(*pick((1, 2), (2, 1)), figsize=pick((12, 5.4), (MOBILE_WIDTH, 10)),
                                  gridspec_kw=pick({"width_ratios": [1.6, 1]}, {"height_ratios": [1.3, 1]}))
    for city, color in COLORS.items():
        ax.step(t.index, t[city], where="post", color=color, lw=2.8 if city == "Washington" else 1.6, label=city)
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
    fig.subplots_adjust(bottom=0.24, wspace=0.22, hspace=0.45)
    headline(fig, f"DC has designated {dc:.0%} of its land outside parks; New York, Philadelphia and Boston "
             f"{others.min():.0%}–{others.max():.0%}",
             f"Share of city land inside historic districts and landmarks, {int(t.index.min())}–{int(t.index.max())}")
    out = pd.concat({"by_year": t, "current": cur.T}, names=["table"])
    save(fig, "comps_designated_land", out,
         "Union of each city's historic districts and individual landmark polygons, clipped to the 2020 Census city "
         "boundary and divided by Census land area; equal-area projection. Parkland: designations that are mainly parks "
         "(inputs/comps_parkland.csv; e.g. DC's Rock Creek Park and Fort Circle Parks districts, Boston's Franklin Park); "
         "New York's scenic landmarks are not in its layer. Today's boundaries are dated by each feature's designation "
         "(NYC extensions carry their own dates); undated designations are left out of the time series. Landmark units "
         "differ: NYC landmark sites, Philadelphia registered parcels, Boston approved landmarks, DC Inventory landmarks. "
         "Sources: DC GIS; NYC Open Data (LPC); City of Philadelphia ArcGIS; City of Boston ArcGIS; Census TIGERweb.")


SHARES = (("designated_area_share_excl_parkland", "Land, excluding parkland"),
          ("designated_area_share", "Land, all designations"),
          ("official_buildings_designated_share_excl_parkland", "Buildings, city address data"),
          ("osm_buildings_designated_share_excl_parkland", "Buildings, OpenStreetMap"))


def coverage_measures() -> None:
    """Every share measure side by side: designated land and buildings, with and without parkland."""
    path = ANALYSIS / "comps_current.csv"
    if not path.exists():
        return
    cur = pd.read_csv(path).set_index("city").reindex(list(COLORS))
    shares = [(c, label) for c, label in SHARES if c in cur and cur[c].notna().all()]
    fig, ax = plt.subplots(figsize=pick((10, 5), (MOBILE_WIDTH, 6)))
    rows = list(range(len(shares)))[::-1]
    for y, (col, label) in zip(rows, shares):
        vals = cur[col]
        ax.plot([vals.min(), vals.max()], [y, y], color=RULE, lw=6, solid_capstyle="round", zorder=1)
        for city, v in vals.items():
            dc = city == "Washington"
            ax.scatter(v, y, s=120 if dc else 70, color=COLORS[city], zorder=3 if dc else 2,
                       edgecolor=PAPER, linewidth=1, label=city if y == rows[0] else None)
        ax.text(vals["Washington"] + 0.012, y, f"{vals['Washington']:.0%}", va="center", fontsize=8.5)
    ax.set_yticks(rows)
    ax.set_yticklabels([label for _, label in shares])
    ax.tick_params(axis="y", labelcolor=INK)
    style(ax, grid="x")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, cur[[c for c, _ in shares]].max().max() * 1.15)
    ax.set_ylim(-0.6, len(shares) - 0.4)
    ax.set_xlabel("Share inside a historic district or landmark")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4, frameon=False)
    fig.subplots_adjust(left=0.24, right=0.97, bottom=0.26)

    ratios = [cur.loc["Washington", c] / cur.drop("Washington")[c].max() for c, _ in shares]
    headline(fig, f"By land or by buildings, DC has designated {min(ratios):.1f}–{max(ratios):.1f} times as much as "
             "the next city", "Washington, New York, Philadelphia and Boston, designations in force today")
    save(fig, "comps_coverage_measures", cur[[c for c, _ in shares] + ["official_buildings", "osm_buildings"]],
         "Land: union of historic districts and landmark polygons within the 2020 Census city boundary, over Census "
         "land area (parkland exclusions in inputs/comps_parkland.csv). Buildings: one point per addressed building "
         "(DC MAR building addresses; NYC address points by building ID; Boston SAM by building ID; Philadelphia "
         "assessed non-vacant properties, one per location), and OpenStreetMap footprints as a check; parkland excluded. "
         "Sources: DC GIS; NYC Open Data; City of Philadelphia; City of Boston; Census; OpenStreetMap (Geofabrik). "
         "Table: data/analysis/comps_current.csv.")
