"""Charts of designated property from the tax roll joined to districts and landmarks (H8, H9).

Units are ITSPE tax records (a condo unit is a record) and today's assessed value;
designation status and boundaries are today's.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from historic_preservation.analysis import eras
from historic_preservation.charts import DARK, GREY, INK, LIGHT, MID, MOBILE_WIDTH, RED, headline, mobile, pick, save, style
from historic_preservation.config import ANALYSIS, JOINED

CLASSES = (("residential", INK), ("commercial", DARK), ("institutional", MID), ("vacant", LIGHT))
SOURCE = "Source: DC Office of Tax and Revenue ITSPE tax roll joined to DC GIS historic districts and landmarks (data/joined/itspe_status.parquet)."


def joined() -> pd.DataFrame:
    return pd.read_parquet(JOINED / "itspe_status.parquet")


def billions(axis) -> None:
    axis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e9:,.0f}B"))


def designated_share_over_time() -> None:
    j = joined()
    rec = eras.record_first_dates(j)
    years = range(1950, pd.Timestamp.today().year + 1)
    year = rec["first_date"].dt.year
    taxable = ~j["zero_tax"]
    rows = []
    for y in years:
        inn = year <= y
        rows.append({"year": y,
                     "records": inn.sum() / len(j),
                     "assessed_value": rec.loc[inn, "assessment"].sum() / j["assessment"].sum(),
                     "assessed_value_taxable": rec.loc[inn & taxable.reindex(rec.index), "assessment"].sum()
                                               / j.loc[taxable, "assessment"].sum()})
    t = pd.DataFrame(rows).set_index("year")
    undated_records = rec["first_date"].isna().sum() / len(j)
    undated_value = rec.loc[rec["first_date"].isna(), "assessment"].sum() / j["assessment"].sum()
    v1990 = t.loc[1990, "assessed_value"] / t["assessed_value"].iloc[-1]

    fig, ax = plt.subplots(figsize=pick((10, 5.4), (MOBILE_WIDTH, 6.4)))
    ax.step(t.index, t["assessed_value"], where="post", color=RED, lw=2.6, label="Share of assessed value")
    ax.step(t.index, t["assessed_value_taxable"], where="post", color=MID, lw=1.4, ls="--",
            label="Share of assessed value, taxable property only")
    ax.step(t.index, t["records"], where="post", color=INK, lw=2.2, label="Share of tax records")
    a1990, now = t.loc[1990, "assessed_value"], t["assessed_value"].iloc[-1]
    ax.plot([1990, t.index[-1]], [a1990, now], "o", color=RED, ms=6)
    ax.annotate(f"1990: {a1990:.0%} of all value,\n{v1990:.0%} of today's {now:.0%}", (1990, a1990),
                xytext=(-10, 10), textcoords="offset points", ha="right", va="bottom", color=RED, fontweight="semibold")
    ax.annotate(f"{now:.0%}", (t.index[-1], now), xytext=(0, 8), textcoords="offset points", ha="center",
                va="bottom", color=RED, fontweight="semibold")
    ax.axvline(1979, color=MID, lw=0.8)
    ax.text(1979.5, 0.02, "1979: DC preservation law\ntakes effect", fontsize=8, color=GREY)
    style(ax)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, max(t.max().max() * 1.1, 0.1))
    ax.set_xlabel("Year of first DC designation (district or landmark)")
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    headline(fig, f"{v1990:.0%} of today's designated assessed value was protected by 1990",
             f"Cumulative share of today's DC tax roll inside a historic district or landmark, 1950–{t.index[-1]}")
    fig.subplots_adjust(bottom=0.2)
    save(fig, "designated_share_over_time", t,
         f"Cumulative share of today's DC tax records and assessed value inside a historic district or landmark, by the year "
         f"each record was first covered; today's boundaries, so later boundary expansions count from the district's "
         f"original year. Not shown: designated records with no dated designation ({undated_records:.1%} of records, "
         f"{undated_value:.1%} of value; mostly condo units in landmarks). {SOURCE}")


def value_by_designation_era() -> None:
    j = joined()
    lots = eras.lot_first_dates(j, eras.district_first_dates())
    lots["class"] = eras.property_class(lots["proptype"])
    t = lots.pivot_table(index="era", columns="class", values="assessment", aggfunc="sum", fill_value=0)
    t = t.reindex([e for e in eras.ERA_ORDER if e in t.index]).reindex(columns=[c for c, _ in CLASSES], fill_value=0)
    pre1990 = t.loc[[e for e in t.index if e in ("1950", "1964 list", "1960s other", "1970s", "1980s")]].to_numpy().sum()
    share = pre1990 / t.to_numpy().sum()

    fig, ax = plt.subplots(figsize=pick((10, 5.4), (MOBILE_WIDTH, 6.4)))
    bottom = pd.Series(0.0, index=t.index)
    bars = pick(ax.bar, ax.barh)  # phones: eras down the side, where their names fit
    for c, color in CLASSES:
        bars(t.index[::pick(1, -1)], t[c][::pick(1, -1)], pick(0.7, 0.66), bottom[::pick(1, -1)], color=color,
             label=c.capitalize())
        bottom += t[c]
    style(ax, grid=pick("y", "x"))
    billions(ax.xaxis if mobile() else ax.yaxis)
    era = "Era the district was first designated (the earliest, for lots in overlapping districts)"
    ax.set_ylabel(pick("Today's assessed value", ""))  # phones: the era labels speak for themselves
    ax.set_xlabel(pick(era, "Today's assessed value"))
    if mobile():
        ax.tick_params(axis="y", labelcolor=INK)
    ax.legend(frameon=False, fontsize=8.5, reverse=True)
    headline(fig, f"{share:.0%} of today's value under district protection lies in districts first designated "
             "before 1990", "Today's assessed value inside historic districts, by era of first designation")
    fig.subplots_adjust(bottom=0.2)
    save(fig, "value_by_designation_era", t,
         "Today's assessed value of tax records inside historic districts, by the era of the district's first DC "
         "designation, by property class (from the tax roll's property type). Expansions count from the original "
         "year (only current boundaries are published); individual landmarks outside districts are excluded. "
         f"Includes tax-exempt property. {SOURCE}")


def designated_share_by_ward() -> None:
    s = pd.read_csv(ANALYSIS / "designated_shares_by_ward.csv")
    s = s[(s["view"] == "all") & (s["zero_tax"] == "included")]
    t = s.pivot_table(index="ward", columns="metric", values="share").sort_index()
    t.index = t.index.astype(int)
    top = t["assessed_value"].idxmax()

    fig, ax = plt.subplots(figsize=pick((10, 5.2), (MOBILE_WIDTH, 5.6)))
    x = range(len(t))
    ax.bar([i - 0.2 for i in x], t["records"], width=0.4, color=MID, label="Share of tax records")
    ax.bar([i + 0.2 for i in x], t["assessed_value"], width=0.4, color=INK, label="Share of assessed value")
    ax.bar([list(t.index).index(top) + 0.2], [t.loc[top, "assessed_value"]], width=0.4, color=RED)
    ax.text(list(t.index).index(top) + 0.2, t.loc[top, "assessed_value"] + 0.01, f"{t.loc[top, 'assessed_value']:.0%}",
            ha="center", va="bottom", color=RED, fontweight="semibold")
    style(ax)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_xticks(list(x))
    ax.set_xticklabels([pick(f"Ward {w}", str(w)) for w in t.index])
    if pick(False, True):
        ax.set_xlabel("Ward")
    ax.legend(frameon=False, fontsize=8.5)
    headline(fig, f"Ward {top}: {t.loc[top, 'assessed_value']:.0%} of assessed value and "
             f"{t.loc[top, 'records']:.0%} of tax records are designated",
             "Share of each ward's tax records and assessed value inside a historic district or landmark, today")
    fig.subplots_adjust(bottom=0.16)
    save(fig, "designated_share_by_ward", t,
         "Share of each ward's tax records and assessed value inside a historic district or individual landmark, "
         f"today's boundaries; includes tax-exempt property. {SOURCE}")


def top_districts_by_value(n: int = 15) -> None:
    j = joined()
    names = j.loc[j["in_district"], "historic_districts"].str.split(";").explode().str.strip()
    # newtotal/newland, not assessment: some exempt federal parcels carry assessment 0 but a full
    # proposed value (e.g. PAR 03160015), so land would exceed "assessed" value.
    d = j.loc[names.index, ["newtotal", "newland"]].assign(district=names.values)
    t = d.groupby("district")[["newtotal", "newland"]].sum()
    outside = j[j["is_landmark"] & ~j["in_district"]]
    t.loc["Landmarks outside districts"] = [outside["newtotal"].sum(), outside["newland"].sum()]
    t = t.sort_values("newtotal", ascending=False)
    shown = t.head(n).iloc[::-1]

    fig, ax = plt.subplots(figsize=pick((10, 6.2), (MOBILE_WIDTH, 10)))
    y = range(len(shown))
    d, hgt = pick((0.2, 0.4), (0.15, 0.3))  # phones: thinner bars, leaving room for each name above its pair
    ax.barh([i + d for i in y], shown["newtotal"], height=hgt, color=INK, label="Total value (land + improvements)")
    ax.barh([len(shown) - 1 + d], [shown["newtotal"].iloc[-1]], height=hgt, color=RED)  # the leader
    ax.barh([i - d for i in y], shown["newland"], height=hgt, color=MID, label="Land value")
    names = shown.index.str.replace(" Historic District", "")
    ax.set_yticks(list(y))
    ax.set_yticklabels(pick(names, [""] * len(names)), fontsize=8.5, color=INK)
    for i, name in enumerate(names if mobile() else ()):  # phones: each name above its bars, so the bars get the width
        ax.text(0, i + 0.32, name, fontsize=8.5, color=INK, va="bottom")
    style(ax, grid="x")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v / 1e9:,.0f}B"))
    ax.legend(frameon=False, fontsize=8.5, loc="lower right", reverse=True)
    lead = t.index[0]
    lead_land = t.iloc[0]["newland"] / t.iloc[0]["newtotal"]
    headline(fig, f"{lead.replace(' Historic District', '')} holds ${t.iloc[0]['newtotal'] / 1e9:,.0f}B of property "
             f"value, the most of any district; {lead_land:.0%} of it is land",
             f"Today's assessed value of tax records in each historic district, top {n}")
    fig.subplots_adjust(bottom=0.14, left=0.3)  # long names inside the figure, so the headline sits flush left
    save(fig, "top_districts_by_value", t,
         f"OTR's proposed total and land values (newtotal, newland; used here because some exempt parcels show an "
         f"assessment of $0) of tax records in each historic district (top {n} shown; all in the data file); "
         "a record in overlapping districts counts in each. Includes tax-exempt property (federal, District and "
         f"institutional). {SOURCE}")
