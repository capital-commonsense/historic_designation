"""Nomination charts from data/joined/nominations.csv."""

import matplotlib.pyplot as plt
import pandas as pd

from historic_preservation.charts import MUTED, PALETTE, save, style
from historic_preservation.config import JOINED

DECIDED = ("designated", "amended", "denied", "withdrawn", "de-designated")
TOP_N = 5
WELL_ATTRIBUTED = (2010, 2022)  # fiscal years whose HPO updates name nominators


def entities() -> pd.DataFrame:
    """Decided nominations FY2006+, with the first-named filer as the entity."""
    n = pd.read_csv(JOINED / "nominations.csv")
    d = n[n["outcome"].isin(DECIDED) & (n["fy"] >= 2006) & (n["kind"] != "thematic_document")].copy()
    d["fy"] = d["fy"].astype(int)
    d["entity"] = d["filers"].fillna("").str.split("; ").str[0]
    d.loc[d["filer_type"].isin(["owner", "owner_cosponsor"]), "entity"] = "Property owners"
    d.loc[d["entity"].isin(["individual", "private owner"]), "entity"] = "Individuals"
    d.loc[d["filer_type"] == "unknown", "entity"] = "Unknown"
    return d


def by_entity_and_year() -> None:
    d = entities()
    named = d[~d["entity"].isin(["Unknown", "Property owners", "Individuals"])]
    top = named["entity"].value_counts().head(TOP_N).index.tolist()
    d["group"] = d["entity"].where(d["entity"].isin(top + ["Property owners", "Unknown"]), "Other named filers")
    order = top + ["Other named filers", "Property owners", "Unknown"]
    table = d.pivot_table(index="fy", columns="group", values="nomination_id", aggfunc="count", fill_value=0)
    table = table.reindex(columns=order, fill_value=0).reindex(range(d["fy"].min(), d["fy"].max() + 1), fill_value=0)

    lo, hi = WELL_ATTRIBUTED
    window = table.loc[lo:hi]
    attributed = window.drop(columns="Unknown").to_numpy().sum()
    leader = window.drop(columns=["Unknown", "Other named filers", "Property owners"]).sum().idxmax()
    lead_n = int(window[leader].sum())
    title = (f"{leader} filed {lead_n} of {attributed} nominations with a known filer decided in FY{lo}–{str(hi)[2:]}"
             f" ({lead_n / attributed:.0%})")

    fig, ax = plt.subplots(figsize=(10, 5.6))
    bottom = pd.Series(0, index=table.index)
    colors = PALETTE[:TOP_N] + ["#8C8C8C", PALETTE[5], MUTED]
    for col, color in zip(order, colors):
        ax.bar(table.index, table[col], bottom=bottom, color=color, label=col, width=0.8,
               hatch="///" if col == "Unknown" else None, edgecolor="white" if col != "Unknown" else "#999999",
               linewidth=0.4)
        bottom += table[col]
    ax.axvspan(lo - 0.5, hi + 0.5, color="#F2F2F2", zorder=0)
    ax.text((lo + hi) / 2, bottom.max() * 1.02, f"FY{lo}–{hi}: HPO's annual updates name the nominator",
            ha="center", fontsize=8, color="#555555")
    style(ax)
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold")
    ax.set_ylabel("Nominations decided by HPRB")
    ax.set_xlabel("Fiscal year of decision")
    ax.set_xticks(table.index)
    ax.set_xticklabels([str(y)[2:] if y % 2 else str(y) for y in table.index], fontsize=8)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5, title="First-named filer",
              title_fontsize=8.5, reverse=True)
    fig.subplots_adjust(bottom=0.16)
    save(fig, "nominations_by_entity_year", table,
         "Counts landmark and district nominations HPRB designated, amended, denied, withdrew or revoked, by fiscal "
         "year of the decision, by first-named filer; nominations an owner filed or co-filed are counted as 'Property owners'. Filers from HPO's Inventory updates (FY2010–22), "
         "HPO staff reports and HPRB actions; types inferred from names. 'Unknown': no source names the filer, "
         "mostly FY2006–09 and FY2023–26. Source: data/joined/nominations.csv.")
